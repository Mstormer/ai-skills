#!/usr/bin/env python3
"""Block destructive shell commands for AI coding agents (Claude Code, Codex, ...) on Windows, as a PreToolUse hook.

Understands commands written for Git Bash, PowerShell and cmd.exe:
- rm / Remove-Item and its aliases (ri, rmdir, rd, del, erase) on protected folders,
  including `Get-ChildItem <folder> | Remove-Item`
- find -delete / find -exec rm (Git Bash)
- format, diskpart, Format-Volume, Clear-Disk, Initialize-Disk, Remove-Partition,
  dd to a physical drive, and deleting shadow copies / backups (vssadmin, wmic, wbadmin)
It sees through wrappers (sudo, env, bash -c, powershell -Command / -EncodedCommand, cmd /c,
Invoke-Expression, $(...)), ~ / $HOME / $env:USERPROFILE / %USERPROFILE%, Git Bash and WSL
paths (/c/Users/..., /mnt/c/...), globs, and `cd X; Remove-Item *`.

This never executes anything; it only reads the command text.
"""

import base64
import glob
import json
import ntpath
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
    ("rm -rf /", "Never delete the root filesystem."),
)

# Shell separators. This intentionally does not execute or fully parse shell syntax.
SEGMENT_RE = re.compile(r"(?:^|[;|&\n])(?:\s*[;&|]\s*)*")

ENV = {key.upper(): value for key, value in os.environ.items()}
SYSTEM_DRIVE = (ENV.get("SYSTEMDRIVE") or "C:").rstrip("\\/")
HOME = ENV.get("USERPROFILE") or ntpath.join(SYSTEM_DRIVE + "\\", "Users", ENV.get("USERNAME", "user"))

# Variables that can appear in paths, as $env:NAME, %NAME%, $NAME or ${NAME} (names are case-insensitive).
VARIABLES = {
    "userprofile": HOME,
    "home": HOME,
    "systemdrive": SYSTEM_DRIVE,
    "systemroot": ENV.get("SYSTEMROOT", SYSTEM_DRIVE + "\\Windows"),
    "windir": ENV.get("WINDIR", SYSTEM_DRIVE + "\\Windows"),
    "programfiles": ENV.get("PROGRAMFILES", SYSTEM_DRIVE + "\\Program Files"),
    "programfiles(x86)": ENV.get("PROGRAMFILES(X86)", SYSTEM_DRIVE + "\\Program Files (x86)"),
    "programdata": ENV.get("PROGRAMDATA", SYSTEM_DRIVE + "\\ProgramData"),
    "appdata": ENV.get("APPDATA", HOME + "\\AppData\\Roaming"),
    "localappdata": ENV.get("LOCALAPPDATA", HOME + "\\AppData\\Local"),
    "onedrive": ENV.get("ONEDRIVE", HOME + "\\OneDrive"),
    "public": ENV.get("PUBLIC", SYSTEM_DRIVE + "\\Users\\Public"),
}
VARIABLE_RE = re.compile(
    r"\$env:([A-Za-z_][A-Za-z0-9_]*)|%([^%\s]+)%|\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)


def norm(path):
    return ntpath.normpath(path).lower()


# Deleting any of these (or everything inside them) is never allowed. Every drive root is also protected.
PROTECTED_PATHS = {
    norm(path)
    for path in (
        VARIABLES["systemroot"], VARIABLES["programfiles"], VARIABLES["programfiles(x86)"],
        VARIABLES["programdata"], SYSTEM_DRIVE + "\\Users", SYSTEM_DRIVE + "\\Recovery",
        SYSTEM_DRIVE + "\\System Volume Information", HOME,
    )
} | {
    norm(ntpath.join(HOME, name))
    for name in (
        "Desktop", "Documents", "Downloads", "Music", "Pictures", "Videos", "OneDrive",
        "AppData", ".ssh", ".claude", ".codex",
    )
}
# Every user's home folder.
PROTECTED_PARENTS = {norm(SYSTEM_DRIVE + "\\Users")}
DRIVE_ROOT_RE = re.compile(r"^[a-z]:\\$")

# A final path component that means "everything in this folder".
WHOLE_DIR_GLOBS = {"*", "*.*", ".*"}

# Commands that run another command; value = their flags that take an argument.
WRAPPERS = {
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U"},
    "env": {"-u", "-P"},
    "exec": {"-a"},
    "xargs": {"-I", "-L", "-n", "-P", "-s", "-E", "-d", "-a"},
    "nohup": set(), "time": set(), "command": set(), "builtin": set(),
    "!": set(), "{": set(), "if": set(), "then": set(), "else": set(),
    "do": set(), "while": set(), "until": set(),
}
SHELLS = {"sh", "bash", "zsh", "dash"}
POWERSHELLS = {"powershell", "pwsh", "powershell_ise"}
PS_VALUE_FLAGS = {
    "-executionpolicy", "-ep", "-ex", "-windowstyle", "-w", "-workingdirectory", "-wd",
    "-configurationname", "-settingsfile", "-outputformat", "-of", "-inputformat", "-if",
    "-version", "-psconsolefile", "-custompipename",
}

DELETE_COMMANDS = {"rm", "ri", "remove-item", "rmdir", "rd", "del", "erase"}
LIST_COMMANDS = {"get-childitem", "gci", "dir", "ls", "get-item", "gi"}
CMD_STYLE = {"rmdir", "rd", "del", "erase", "dir"}  # accept /s-style switches
PATH_PARAMS = {"-path", "-literalpath", "-lp", "-pspath"}
VALUE_PARAMS = {"-include", "-exclude", "-filter", "-credential", "-stream", "-depth", "-attributes"}
CMD_SWITCH_RE = re.compile(r"^/[a-z](:\S*)?$")

ALWAYS_BLOCKED = {
    "format-volume": "Never format a drive.",
    "clear-disk": "Never erase a disk.",
    "initialize-disk": "Never re-initialize a disk.",
    "remove-partition": "Never delete a partition.",
    "reset-physicaldisk": "Never reset a disk.",
    "diskpart": "diskpart can erase or repartition disks; the user must run it themselves.",
}

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


def unquote(token):
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
        return token[1:-1]
    return token


def tokenize(command):
    # Non-POSIX mode keeps backslashes in Windows paths intact.
    lexer = shlex.shlex(command.replace("\r", "").replace("\n", " ; "), posix=False, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        tokens = command.split()
    return [unquote(token) for token in tokens]


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


def command_name(word):
    name = ntpath.basename(word).lower()
    return name[:-4] if name.endswith(".exe") else name


def unwrap(words):
    """Strip VAR=value prefixes and wrappers like sudo/env/nohup to reach the real command."""
    i = 0
    while i < len(words):
        name = command_name(words[i])
        if ASSIGNMENT_RE.match(words[i]):
            i += 1
            continue
        if name == "timeout":
            if i + 1 < len(words) and words[i + 1].startswith("/"):
                break  # cmd's `timeout /t 5` is a sleep, not a wrapper
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


def substitute(target):
    def replace(match):
        name = next(group for group in match.groups() if group)
        return VARIABLES.get(name.lower(), match.group(0))

    return VARIABLE_RE.sub(replace, target)


def expand(target, cwd):
    """Resolve variables, ~, Git Bash/WSL paths and relative paths to a lowercase Windows path."""
    target = substitute(unquote(target))
    if target == "~" or target.startswith(("~/", "~\\")):
        target = HOME + target[1:]
    git_bash = re.match(r"^(?:/mnt)?/([A-Za-z])(?=/|$)(.*)$", target)
    if git_bash:
        target = git_bash.group(1) + ":" + (git_bash.group(2) or "\\")
    target = target.replace("/", "\\")
    drive, rest = ntpath.splitdrive(target)
    if not drive:
        if rest.startswith("\\"):
            target = ((ntpath.splitdrive(cwd)[0] if cwd else "") or SYSTEM_DRIVE) + rest
        elif cwd is None:
            return None
        else:
            target = ntpath.join(cwd, rest)
    elif not rest.startswith("\\"):
        target = drive + "\\" + rest
    return norm(target)


def is_protected(path):
    return bool(DRIVE_ROOT_RE.match(path)) or path in PROTECTED_PATHS or ntpath.dirname(path) in PROTECTED_PARENTS


def protected_target(target, cwd):
    """Return the protected path that `target` would destroy, if any."""
    path = expand(target, cwd)
    if path is None:
        last = re.split(r"[\\/]", target.rstrip("\\/"))[-1]
        return target if last in WHOLE_DIR_GLOBS | {".", ".."} else None
    candidates = [path]
    if GLOB_CHARS & set(path):
        candidates = [norm(match) for match in glob.glob(path)] if os.name == "nt" else []
        if ntpath.basename(path) in WHOLE_DIR_GLOBS:
            candidates.append(ntpath.dirname(path))
    for candidate in candidates:
        if is_protected(candidate):
            return candidate
    return None


def path_arguments(args, cmd_style):
    """Paths given to rm/Remove-Item/Get-ChildItem style commands (positional or -Path)."""
    paths = []
    i = 0
    options_done = False
    while i < len(args):
        arg = args[i]
        i += 1
        if not options_done and arg == "--":
            options_done = True
            continue
        if not options_done and arg.startswith("-") and len(arg) > 1:
            name, colon, value = arg.partition(":")
            if name.lower() in PATH_PARAMS:
                if colon:
                    paths.append(value)
                elif i < len(args):
                    paths.append(args[i])
                    i += 1
            elif name.lower() in VALUE_PARAMS and not colon:
                i += 1
            continue
        if cmd_style and CMD_SWITCH_RE.match(arg.lower()):
            continue
        paths.append(arg)
    # PowerShell accepts comma-separated lists of paths.
    return [part for path in paths for part in path.split(",") if part]


def check_delete(name, args, state):
    targets = path_arguments(args, name in CMD_STYLE)
    for target in targets:
        hit = protected_target(target, state["cwd"])
        if hit:
            return f"Never delete {hit} or everything in it (blocked: {name} {target})."
    if not targets and state.get("listed"):
        return f"Never delete {state['listed']} or everything in it (blocked: listing piped into {name})."
    return None


def check_find(args, cwd):
    deletes = "-delete" in args or any(
        arg in ("-exec", "-execdir", "-ok", "-okdir")
        and i + 1 < len(args)
        and command_name(args[i + 1]) == "rm"
        for i, arg in enumerate(args)
    )
    if not deletes:
        return None
    starts = []
    i = 0
    while i < len(args) and args[i] in ("-H", "-L", "-P"):
        i += 1
    while i < len(args) and not args[i].startswith("-") and args[i] not in ("(", "!"):
        starts.append(args[i])
        i += 1
    for start in starts or ["."]:
        hit = protected_target(start, cwd)
        if hit:
            return f"Never bulk-delete inside {hit} with find (move specific files to the Recycle Bin instead)."
    return None


def check_powershell(args, state, depth):
    i = 0
    while i < len(args):
        low = args[i].lower()
        if not low.startswith("-"):  # Windows PowerShell treats bare text as -Command
            return check_command(" ".join(args[i:]), state["cwd"], depth + 1)
        if low in ("-c", "-command") or (len(low) > 3 and "-command".startswith(low)):
            return check_command(" ".join(args[i + 1:]), state["cwd"], depth + 1)
        if low in ("-e", "-ec") or (len(low) > 3 and "-encodedcommand".startswith(low)):
            if i + 1 >= len(args):
                return None
            try:
                decoded = base64.b64decode(args[i + 1]).decode("utf-16-le")
            except ValueError:
                return "Could not decode a PowerShell -EncodedCommand to check it; run it without encoding."
            return check_command(decoded, state["cwd"], depth + 1)
        if low in ("-f", "-file") or (len(low) > 3 and "-file".startswith(low)):
            return None
        i += 2 if low in PS_VALUE_FLAGS else 1
    return None


def check_cd(args, state):
    dest = None
    i = 0
    while i < len(args):
        arg = args[i]
        i += 1
        if arg == "-":
            state["cwd"] = None
            return
        if arg.lower() == "/d" or arg in ("-L", "-P"):
            continue
        if arg.lower() in ("-path", "-literalpath"):
            dest = args[i] if i < len(args) else None
            break
        if not arg.startswith("-"):
            dest = arg
            break
    state["cwd"] = expand(dest or "~", state["cwd"])


def check_disk_tool(name, args):
    low_args = [a.lower() for a in args]
    if name in ALWAYS_BLOCKED:
        return ALWAYS_BLOCKED[name]
    if name == "format" and any(re.match(r"^[a-z]:\\?$", a) for a in low_args):
        return "Never format a drive."
    if name == "dd" and any(a.startswith(("of=/dev/", "of=\\\\.\\")) for a in low_args):
        return "Never write raw data to a disk device."
    if name == "vssadmin" and ("delete" in low_args or "resize" in low_args):
        return "Never delete shadow copies (Windows restore points and backups)."
    if name == "wmic" and "shadowcopy" in low_args and "delete" in low_args:
        return "Never delete shadow copies (Windows restore points and backups)."
    if name == "wbadmin" and "delete" in low_args:
        return "Never delete Windows backups."
    return None


def check_words(words, state, depth):
    words = unwrap(words)
    if not words:
        return None
    name = command_name(words[0])
    args = words[1:]
    listed = state.pop("listed", None)

    if name in ("cd", "chdir", "pushd", "set-location", "sl"):
        check_cd(args, state)
        return None
    if name in SHELLS:
        for i, arg in enumerate(args):
            if arg.startswith("-") and not arg.startswith("--") and "c" in arg[1:]:
                scripts = [a for a in args[i + 1:] if not a.startswith("-")]
                if scripts:
                    return check_command(scripts[0], state["cwd"], depth + 1)
        return None
    if name in POWERSHELLS:
        return check_powershell(args, state, depth)
    if name == "cmd":
        for i, arg in enumerate(args):
            if arg.lower() in ("/c", "/k", "/r"):
                return check_command(" ".join(args[i + 1:]), state["cwd"], depth + 1)
        return None
    if name in ("eval", "invoke-expression", "iex"):
        rest = [a for a in args if a.lower() != "-command"]
        return check_command(" ".join(rest), state["cwd"], depth + 1)
    if name in LIST_COMMANDS:
        for target in path_arguments(args, name in CMD_STYLE) or ["."]:
            hit = protected_target(target, state["cwd"])
            if hit:
                state["listed"] = hit
        return None
    if name in DELETE_COMMANDS:
        state["listed"] = listed
        return check_delete(name, args, state)
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

    cwd = expand(payload.get("cwd") or os.getcwd(), None)
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
