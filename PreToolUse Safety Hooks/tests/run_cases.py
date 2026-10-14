#!/usr/bin/env python3
"""Check a Destruction_blocker hook against a JSONL file of cases. Never executes the test commands.

Each case is sent to the hook as a JSON payload on stdin, exactly as an agent would send it, and the
reply is validated strictly: exit code 0, nothing on stderr, a reply within the time limit, and stdout
either empty (allow) or exactly one deny object in the documented schema. A crash, a timeout or a
malformed reply fails the case, whatever the case expected.

The macOS and Linux hooks run against a sandbox home folder with standard folders, files and symlinks
(created in the system temp folder, reused between runs, never deleted), so their path, glob and
symlink checks see a real filesystem. Test them on a macOS or Linux machine. The Windows hook's command
and path logic can be tested from any machine, but its filesystem checks (globs, junctions, short 8.3
names) only work on Windows: cases marked "host": "windows" are skipped elsewhere and reported as skipped.

Usage: python3 run_cases.py <macos|linux|windows> [--hook PATH] [--cases FILE] [--guard] [-v]
--guard runs the tamper-guard cases (cases_guard_posix.jsonl / cases_guard_windows.jsonl) against a copy of the hook
installed in the sandbox's dedicated folder ~/.claude/hooks/destruction-blocker/, with a settings file registering it.

Case fields (one JSON object per line):
  expect           "deny" or "allow" (required)
  command          the shell command, given to the hook as data          } exactly one
  raw              the exact text to send on stdin instead of a payload  } of these
  encode           true: send `powershell -EncodedCommand <command as base64 UTF-16LE>` instead
  repeat           build a large command: prefix + command repeated N times + suffix
  prefix, suffix   text around the repeated command (only with repeat)
  cwd             working directory to report (default: @HOME@/Documents/Project)
  tool             tool_name to report (default "Bash")
  env              extra environment variables for the hook process
  host             only run on this host OS: "macos", "linux" or "windows"
  reason_contains  text the deny reason must contain (case-insensitive)
  note             free text, shown when the case fails
Placeholders @HOME@, @SANDBOX@ and @CWD@ are replaced in command, raw, cwd and env values.
The exit code is the number of failures (capped at 100).
"""
import argparse
import base64
import json
import os
import platform
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOST = {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}.get(platform.system(), "other")
TIMEOUT_SECONDS = 10
SLOW_SECONDS = 3.0  # a reply slower than this fails the case

SANDBOX_FOLDERS = (
    "Applications", "Desktop", "Documents/Project/build", "Documents/Project/src", "Downloads",
    "Library", "Movies", "Music", "Pictures", "Public", "Templates", "Videos",
    ".ssh", ".config", ".gnupg", ".cache/pip", ".claude/hooks", ".codex", ".Trash",
    ".local/share/Trash/files",
)
SANDBOX_FILES = (
    "Documents/Project/notes.txt", "Documents/Project/build/out.o", "Documents/Project/src/main.c",
    "Downloads/installer.dmg", ".cache/pip/wheel.whl", ".Trash/old.txt",
)


def posix_sandbox():
    """Create (or reuse) a sandbox home folder; return (home, sandbox root)."""
    root = os.path.realpath(os.path.join(tempfile.gettempdir(), f"destruction-blocker-sandbox-{os.getuid()}"))
    home = os.path.join(root, "home", "tester")
    for folder in SANDBOX_FOLDERS:
        os.makedirs(os.path.join(home, folder), exist_ok=True)
    for name in SANDBOX_FILES:
        path = os.path.join(home, name)
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write("sandbox file\n")
    scratch = os.path.join(root, "scratch")
    os.makedirs(scratch, exist_ok=True)
    for link, target in (("link-to-home", home), ("link-to-docs", os.path.join(home, "Documents"))):
        path = os.path.join(scratch, link)
        if not os.path.islink(path):
            os.symlink(target, path)
    return home, root


def setup(target):
    """Return (base environment, home, sandbox) for the target hook."""
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "LANG") if key in os.environ}
    if target == "windows":
        home = "C:\\Users\\tester"
        sandbox = tempfile.mkdtemp(prefix="destruction-blocker-") if HOST == "windows" else "C:\\Sandbox"
        env.update({"USERPROFILE": home, "SYSTEMDRIVE": "C:", "USERNAME": "tester",
                    "HOMEDRIVE": "C:", "HOMEPATH": "\\Users\\tester"})
        return env, home, sandbox
    home, sandbox = posix_sandbox()
    env.update({"HOME": home, "USER": "tester", "LOGNAME": "tester"})
    return env, home, sandbox


def fill(value, places):
    for key, replacement in places.items():
        value = value.replace("@" + key + "@", replacement)
    return value


def judge(proc):
    """Return (verdict, detail): verdict is 'allow', 'deny', or None for an invalid reply."""
    if proc.returncode != 0:
        last = (proc.stderr.strip().splitlines() or ["(no stderr)"])[-1]
        return None, f"exit code {proc.returncode}: {last}"
    if proc.stderr.strip():
        return None, f"wrote to stderr: {proc.stderr.strip().splitlines()[-1]}"
    out = proc.stdout.strip()
    if not out:
        return "allow", ""
    try:
        reply = json.loads(out)
    except ValueError:
        return None, f"stdout is not one JSON object: {out[:120]!r}"
    inner = reply.get("hookSpecificOutput") if isinstance(reply, dict) else None
    valid = (
        isinstance(reply, dict) and set(reply) == {"hookSpecificOutput"} and isinstance(inner, dict)
        and set(inner) == {"hookEventName", "permissionDecision", "permissionDecisionReason"}
        and inner["hookEventName"] == "PreToolUse" and inner["permissionDecision"] == "deny"
        and isinstance(inner["permissionDecisionReason"], str) and inner["permissionDecisionReason"].strip()
    )
    if not valid:
        return None, f"stdout is not the documented deny object: {out[:120]!r}"
    return "deny", inner["permissionDecisionReason"]


def main():
    parser = argparse.ArgumentParser(usage=__doc__)
    parser.add_argument("target", choices=("macos", "linux", "windows"))
    parser.add_argument("--hook", help="hook to test (default: ../<target>/Destruction_blocker.py)")
    parser.add_argument("--cases", help="JSONL case file (default: cases_<target>.jsonl next to this script)")
    parser.add_argument("-v", "--verbose", action="store_true", help="print every case, not just failures")
    parser.add_argument("--guard", action="store_true",
                        help="tamper-guard tests: install a copy of the hook in the sandbox's dedicated folder "
                             "~/.claude/hooks/destruction-blocker/ (with a settings file registering it) and test that copy")
    args = parser.parse_args()
    if args.target != "windows" and HOST not in ("macos", "linux"):
        sys.exit(f"The {args.target} hook must be tested on macOS or Linux (this host is {HOST}).")

    hook = os.path.expanduser(args.hook) if args.hook else os.path.join(HERE, "..", args.target, "Destruction_blocker.py")
    default_cases = f"cases_guard_{'windows' if args.target == 'windows' else 'posix'}.jsonl" if args.guard \
        else f"cases_{args.target}.jsonl"
    cases_file = args.cases or os.path.join(HERE, default_cases)
    base_env, home, sandbox = setup(args.target)
    if args.guard and args.target != "windows":  # the Windows folder guard needs a Windows host; its cases use settings
        folder = os.path.join(home, ".claude", "hooks", "destruction-blocker")
        os.makedirs(folder, exist_ok=True)
        with open(hook, encoding="utf-8") as src, open(os.path.join(folder, "Destruction_blocker.py"), "w",
                                                       encoding="utf-8") as dst:
            dst.write(src.read())
        with open(os.path.join(home, ".claude", "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"hooks": {"PreToolUse": [{"matcher": "Bash|Edit|Write|MultiEdit|NotebookEdit", "hooks": [
                {"type": "command", "command": "python3 ~/.claude/hooks/destruction-blocker/Destruction_blocker.py"}]}]}},
                f, indent=2)
        hook = os.path.join(folder, "Destruction_blocker.py")
    sep = "\\" if args.target == "windows" else "/"
    default_cwd = sep.join((home, "Documents", "Project"))

    passed = failed = skipped = 0
    slowest = 0.0
    with open(cases_file, encoding="utf-8") as f:
        lines = [(n, line) for n, line in enumerate(f, 1) if line.strip()]
    for n, line in lines:
        case = json.loads(line)
        if case.get("expect") not in ("deny", "allow") or ("command" in case) == ("raw" in case):
            failed += 1
            print(f"FAIL line {n}: malformed case (needs expect deny/allow and exactly one of command/raw)")
            continue
        if case.get("host") and case["host"] != HOST:
            skipped += 1
            continue
        cwd = fill(case.get("cwd", default_cwd), {"HOME": home, "SANDBOX": sandbox})
        places = {"HOME": home, "SANDBOX": sandbox, "CWD": cwd}
        env = dict(base_env, **{k: fill(v, places) for k, v in case.get("env", {}).items()})
        if "raw" in case:
            payload = fill(case["raw"], places)
            shown = f"raw {payload!r}"
        else:
            command = fill(case["command"], places)
            shown = repr(command)
            if case.get("repeat"):
                command = case.get("prefix", "") + command * int(case["repeat"]) + case.get("suffix", "")
                shown = f"{case.get('prefix', '')!r} + {shown} x {case['repeat']} + {case.get('suffix', '')!r}"
            if case.get("encode"):
                command = "powershell -EncodedCommand " + base64.b64encode(command.encode("utf-16-le")).decode()
            payload = json.dumps({
                "session_id": "test", "hook_event_name": "PreToolUse", "tool_name": case.get("tool", "Bash"),
                "cwd": cwd, "tool_input": {"command": command},
            })
        start = time.monotonic()
        try:
            proc = subprocess.run([sys.executable, hook], input=payload, capture_output=True, text=True,
                                  encoding="utf-8", env=env, timeout=TIMEOUT_SECONDS)
            verdict, detail = judge(proc)
        except subprocess.TimeoutExpired:
            verdict, detail = None, f"no reply within {TIMEOUT_SECONDS}s"
        elapsed = time.monotonic() - start
        slowest = max(slowest, elapsed)
        if verdict is not None and elapsed > SLOW_SECONDS:
            verdict, detail = None, f"took {elapsed:.1f}s (limit {SLOW_SECONDS}s)"

        problem = None
        if verdict is None:
            problem = f"invalid reply ({detail})"
        elif verdict != case["expect"]:
            problem = f"expected {case['expect']}, got {verdict}" + (f": {detail}" if detail else "")
        elif verdict == "deny" and case.get("reason_contains", "").lower() not in detail.lower():
            problem = f"deny reason lacks {case['reason_contains']!r}: {detail}"
        if problem:
            failed += 1
            note = f" [{case['note']}]" if case.get("note") else ""
            print(f"FAIL line {n}{note}: {problem}\n     case: {shown}")
        else:
            passed += 1
            if args.verbose:
                print(f"ok   line {n}: {verdict:5} {shown}" + (f"  -> {detail}" if detail else ""))

    summary = f"{args.target}: {passed}/{passed + failed} passed"
    if skipped:
        summary += f", {skipped} skipped (need a {'/'.join(sorted({json.loads(l)['host'] for _, l in lines if json.loads(l).get('host') and json.loads(l)['host'] != HOST}))} host)"
    print(f"{summary}; slowest reply {slowest:.2f}s")
    sys.exit(min(failed, 100))


if __name__ == "__main__":
    main()
