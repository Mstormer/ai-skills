#!/usr/bin/env python3
"""Block destructive Bash commands for AI coding agents (Claude Code, Codex, ...) on Linux, as a PreToolUse hook.

Two layers:
1. BLOCKED_PREFIXES: a literal prefix list.
2. Token-aware checks that see through spelling variations: flag order (rm -fr, rm -r -f),
   wrappers (sudo, env, nohup, ionice, timeout, xargs, bash -c, eval, $(...)), full paths (/bin/rm),
   quoting, ~ / $HOME / ${HOME}, globs (~/*), and `cd X && rm -rf *`.
   Also blocks formatting, wiping and repartitioning disks (mkfs, wipefs, shred, blkdiscard,
   fdisk, sfdisk, sgdisk, parted, dd to /dev).

This never executes anything; it only reads the command text.
"""

import glob
import json
import os
import re
import shlex
import sys


# Harmless command that is always blocked, so agents can confirm the hook is live.
CANARY_COMMAND = "echo PRETOOLUSE_HOOK_CANARY"
CANARY_REASON = "PreToolUse hook is installed and working (this harmless canary command is blocked on purpose)."

BLOCKED_PREFIXES = (
    ("rm -rf /*", "Never delete the contents of the root filesystem."),
    ("rm -rf ~", "Never delete the entire home directory."),
    ("rm -rf $HOME", "Never delete the entire home directory."),
    ("rm -rf /home", "Never delete all user directories."),
    ("rm -rf /", "Never delete the root filesystem."),
    ("mkfs", "Never format a filesystem."),
)

# Shell separators. This intentionally does not execute or fully parse shell syntax.
SEGMENT_RE = re.compile(r"(?:^|[;|&\n])(?:\s*[;&|]\s*)*")

HOME = os.path.normpath(os.path.expanduser("~"))

# Deleting any of these (or everything inside them) is never allowed.
PROTECTED_PATHS = {
    "/", "/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/lib32", "/lib64", "/libx32",
    "/media", "/mnt", "/opt", "/proc", "/root", "/run", "/sbin", "/snap", "/srv", "/sys",
    "/usr", "/var",
    HOME,
} | {
    os.path.join(HOME, name)
    for name in (
        "Desktop", "Documents", "Downloads", "Music", "Pictures", "Public", "Templates",
        "Videos", ".config", ".gnupg", ".ssh", ".claude", ".codex",
    )
}
# Every user's home folder and every mounted drive (/mnt/c is the Windows C: drive under WSL).
PROTECTED_PARENTS = ("/home", "/media", "/mnt", "/run/media")
# Drives mounted per user, e.g. /media/<user>/<drive>.
PROTECTED_GRANDPARENTS = ("/media", "/run/media")

# A final path component that means "everything in this folder".
WHOLE_DIR_GLOBS = {"*", ".*", "*.*", ".[!.]*", "..?*"}

# Commands that run another command; value = their flags that take an argument.
WRAPPERS = {
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U"},
    "doas": {"-u", "-C"},
    "env": {"-u", "-P", "-C"},
    "nice": {"-n"},
    "ionice": {"-c", "-n", "-p", "-P", "-u"},
    "stdbuf": {"-i", "-o", "-e"},
    "exec": {"-a"},
    "xargs": {"-I", "-L", "-n", "-P", "-s", "-E", "-d", "-a"},
    "nohup": set(), "time": set(), "setsid": set(), "command": set(), "builtin": set(),
    "!": set(), "{": set(), "if": set(), "then": set(), "else": set(),
    "do": set(), "while": set(), "until": set(),
}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}

# Partitioning tools: flags that only read. Any other use on a /dev path is blocked.
PARTITION_READ_ONLY = {
    "fdisk": {"-l", "--list", "-x", "--list-details"},
    "gdisk": {"-l"},
    "cfdisk": set(),
    "sfdisk": {"-l", "--list", "-d", "--dump", "-J", "--json", "-s", "--show-size",
               "-V", "--verify", "-g", "--show-geometry"},
}
SGDISK_READ_ONLY = {"-p", "--print", "-i", "--info", "-v", "--verify", "-b", "--backup",
                    "-L", "--list-types", "-P", "--pretend"}
PARTED_WRITE_VERBS = {"mklabel", "mktable", "rm", "mkpart", "mkpartfs", "resizepart", "resize", "rescue"}
DISK_FORMATTERS = ("mkfs", "mke2fs", "mkswap", "mkntfs", "mkdosfs")
DISK_WIPERS = {"wipefs", "shred", "blkdiscard"}

ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SUBSTITUTION_RE = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")
GLOB_CHARS = set("*?[")


def command_segments(command):
    return (segment.strip() for segment in SEGMENT_RE.split(command) if segment.strip())


def denial(reason):
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def tokenize(command):
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        return command.split()


def word_lists(tokens):
    """Split tokens into simple commands at ; & | ( ) and drop redirection operators."""
    current = []
    for token in tokens:
        if token and all(c in ";&|()<>" for c in token):
            if any(c in ";&|()" for c in token) and current:
                yield current
                current = []
            continue
        current.append(token)
    if current:
        yield current


def unwrap(words):
    """Strip VAR=value prefixes and wrappers like sudo/env/nohup to reach the real command."""
    i = 0
    while i < len(words):
        name = os.path.basename(words[i])
        if ASSIGNMENT_RE.match(words[i]):
            i += 1
            continue
        if name == "timeout":
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 1
            i += 1  # duration
            continue
        if name not in WRAPPERS:
            break
        takes_arg = WRAPPERS[name]
        i += 1
        while i < len(words) and words[i].startswith("-") and words[i] != "-":
            flag = words[i]
            i += 1
            if flag == "--":
                break
            if flag in takes_arg:
                i += 1
    return words[i:]


def expand(target, cwd):
    """Resolve ~, $HOME and relative paths to an absolute path, or None if unknowable."""
    for var in ("${HOME}", "$HOME"):
        if target == var or target.startswith(var + "/"):
            target = HOME + target[len(var):]
    if target == "~" or target.startswith("~/"):
        target = HOME + target[1:]
    if not os.path.isabs(target):
        if cwd is None:
            return None
        target = os.path.join(cwd, target)
    return re.sub(r"^/+", "/", os.path.normpath(target))


def is_protected(path):
    parent = os.path.dirname(path)
    return (
        path in PROTECTED_PATHS
        or parent in PROTECTED_PARENTS
        or os.path.dirname(parent) in PROTECTED_GRANDPARENTS
    )


def protected_target(target, cwd):
    """Return the protected path that `target` would destroy, if any."""
    path = expand(target, cwd)
    if path is None:
        last = target.rstrip("/").rsplit("/", 1)[-1]
        return target if last in WHOLE_DIR_GLOBS | {".", ".."} else None
    candidates = [path]
    if GLOB_CHARS & set(path):
        candidates = glob.glob(path)
        if os.path.basename(path) in WHOLE_DIR_GLOBS:
            candidates.append(os.path.dirname(path))
    for candidate in candidates:
        candidate = os.path.normpath(candidate)
        if is_protected(candidate):
            return candidate
    return None


def check_rm(args, cwd):
    options_done = False
    for arg in args:
        if not options_done and arg == "--":
            options_done = True
            continue
        if not options_done and arg.startswith("-") and len(arg) > 1:
            continue
        hit = protected_target(arg, cwd)
        if hit:
            return f"Never delete {hit} or everything in it (blocked: rm {arg})."
    return None


def check_find(args, cwd):
    deletes = "-delete" in args or any(
        arg in ("-exec", "-execdir", "-ok", "-okdir")
        and i + 1 < len(args)
        and os.path.basename(args[i + 1]) == "rm"
        for i, arg in enumerate(args)
    )
    if not deletes:
        return None
    starts = []
    i = 0
    while i < len(args) and (args[i] in ("-H", "-L", "-P", "-D") or args[i].startswith("-O")):
        i += 2 if args[i] == "-D" else 1
    while i < len(args) and not args[i].startswith("-") and args[i] not in ("(", "!"):
        starts.append(args[i])
        i += 1
    for start in starts or ["."]:
        hit = protected_target(start, cwd)
        if hit:
            return f"Never bulk-delete inside {hit} with find (move specific files to the trash instead)."
    return None


def check_disk_tool(name, args):
    devices = [a for a in args if a.startswith("/dev/")]
    flags = {a.split("=", 1)[0] for a in args if a.startswith("-")}
    if name.startswith(DISK_FORMATTERS):
        return "Never format a filesystem."
    if name == "dd" and any(a.startswith("of=/dev/") for a in args):
        return "Never write raw data to a disk device."
    dry_run = name == "wipefs" and flags & {"-n", "--no-act"}
    if name in DISK_WIPERS and devices and not dry_run:
        return f"Never wipe a disk device ({devices[0]})."
    if name in PARTITION_READ_ONLY and devices and not flags & PARTITION_READ_ONLY[name]:
        return f"Never repartition a disk ({devices[0]})."
    if name == "sgdisk" and devices and flags - SGDISK_READ_ONLY:
        return f"Never repartition a disk ({devices[0]})."
    if name == "parted" and PARTED_WRITE_VERBS & {a.lower() for a in args}:
        return "Never repartition a disk."
    return None


def check_words(words, state, depth):
    words = unwrap(words)
    if not words:
        return None
    name = os.path.basename(words[0])
    args = words[1:]

    if name in ("cd", "pushd"):
        dests = [a for a in args if not a.startswith("-") or a == "-"]
        dest = dests[0] if dests else "~"
        state["cwd"] = None if dest == "-" else expand(dest, state["cwd"])
        return None
    if name in SHELLS:
        for i, arg in enumerate(args):
            if arg.startswith("-") and not arg.startswith("--") and "c" in arg[1:]:
                scripts = [a for a in args[i + 1:] if not a.startswith("-")]
                if scripts:
                    return check_command(scripts[0], state["cwd"], depth + 1)
        return None
    if name == "eval":
        return check_command(" ".join(args), state["cwd"], depth + 1)
    if name == "rm":
        return check_rm(args, state["cwd"])
    if name == "find":
        return check_find(args, state["cwd"])
    return check_disk_tool(name, args)


def check_command(command, cwd, depth=0):
    if depth > 5:
        return None
    for segment in command_segments(command):
        for prefix, reason in BLOCKED_PREFIXES:
            if segment.startswith(prefix):
                return reason
    for groups in SUBSTITUTION_RE.findall(command):
        for inner in groups:
            if inner:
                reason = check_command(inner, cwd, depth + 1)
                if reason:
                    return reason
    state = {"cwd": cwd}
    for words in word_lists(tokenize(command)):
        reason = check_words(words, state, depth)
        if reason:
            return reason
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        return 0

    tool_input = payload.get("tool_input", {})
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(command, str):
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    try:
        reason = CANARY_REASON if command.strip() == CANARY_COMMAND else check_command(command, cwd)
    except Exception:  # never let a parser bug crash the hook
        reason = None
    if reason:
        json.dump(denial(reason), sys.stdout)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
