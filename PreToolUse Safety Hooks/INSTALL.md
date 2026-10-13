# PreToolUse Safety Hooks — install guide

This file is written for any coding agent (Claude Code, Codex, or others) installing the hook on behalf of a user, and for the user themselves. Follow the steps in order.

## What it does

`Destruction_blocker.py` runs **before every shell command an agent executes** and blocks commands that would wipe a disk, the operating system, or a whole important folder. It only reads the command text; it never executes anything. Normal work, including deleting specific files or project subfolders, is unaffected.

## Folder layout

```
PreToolUse Safety Hooks/
├── INSTALL.md                     ← this guide
├── macos/Destruction_blocker.py   ← for macOS
├── linux/Destruction_blocker.py   ← for Linux, including WSL
├── windows/Destruction_blocker.py ← for Windows (PowerShell, cmd.exe and Git Bash)
└── tests/
    ├── run_cases.py               ← offline test runner (never executes test commands)
    └── cases_macos.jsonl, cases_linux.jsonl, cases_windows.jsonl
```

## Step 1 — Pick the right version

Find the operating system **the agent's shell commands run on**:

```bash
python3 -c "import platform; print(platform.system())"
```

On Windows, use `py -3` or `python` instead of `python3` if needed.

| Output | Use | Notes |
|---|---|---|
| `Darwin` | `macos/Destruction_blocker.py` | |
| `Linux` | `linux/Destruction_blocker.py` | Includes WSL: if the agent itself runs inside WSL, its commands are Linux commands. |
| `Windows` | `windows/Destruction_blocker.py` | Covers PowerShell, cmd.exe and Git Bash commands. |

Install only the one file that matches. Always install it under the name `Destruction_blocker.py`.

## What each version blocks

All versions see through spelling variations: flag order (`rm -fr`, `rm -r -f`), full paths (`/bin/rm`), quoting, `~` / `$HOME` / `${HOME}`, globs (`~/*`), wrappers (`sudo`, `env`, `nohup`, `timeout`, `bash -c '…'`, `eval`, `$(…)`, backticks), and moving first then deleting (`cd ~ && rm -rf *`, `rm -rf ../..`).

| | macOS | Linux | Windows |
|---|---|---|---|
| Delete commands checked | `rm`, `find -delete`, `find -exec rm` | `rm`, `find -delete`, `find -exec rm` | `Remove-Item` / `ri` / `rm` / `rmdir` / `rd` / `del` / `erase`, `Get-ChildItem … \| Remove-Item`, Git Bash `rm` and `find` |
| Protected system folders | `/`, `/Applications`, `/Library`, `/System`, `/Users`, `/Volumes`, `/bin`, `/etc`, `/opt`, `/private`, `/sbin`, `/usr`, `/var` | `/`, `/bin`, `/boot`, `/dev`, `/etc`, `/home`, `/lib*`, `/media`, `/mnt`, `/opt`, `/proc`, `/root`, `/run`, `/sbin`, `/snap`, `/srv`, `/sys`, `/usr`, `/var` | every drive root (`C:\`, `D:\` …), `Windows`, `Program Files`, `Program Files (x86)`, `ProgramData`, `Users`, `Recovery` |
| Other users / drives | everything in `/Users` and `/Volumes` | everything in `/home`, `/mnt`, `/media`, `/run/media` | everything in `C:\Users` |
| Protected in home folder | the home folder, `Applications`, `Desktop`, `Documents`, `Downloads`, `Library`, `Movies`, `Music`, `Pictures`, `Public`, `.ssh`, `.claude`, `.codex` | the home folder, `Desktop`, `Documents`, `Downloads`, `Music`, `Pictures`, `Public`, `Templates`, `Videos`, `.config`, `.gnupg`, `.ssh`, `.claude`, `.codex` | the home folder, `Desktop`, `Documents`, `Downloads`, `Music`, `Pictures`, `Videos`, `OneDrive`, `AppData`, `.ssh`, `.claude`, `.codex` |
| Disk tools blocked | `diskutil` erase/partition/delete, `mkfs*`, `newfs*`, `dd of=/dev/…` | `mkfs*`, `mke2fs`, `mkswap`, `wipefs`, `shred`/`blkdiscard` on `/dev/…`, writing with `fdisk`/`gdisk`/`cfdisk`/`sfdisk`/`sgdisk`/`parted`, `dd of=/dev/…` (read-only uses like `fdisk -l` are allowed) | `format X:`, `diskpart`, `Format-Volume`, `Clear-Disk`, `Initialize-Disk`, `Remove-Partition`, `dd` to a physical drive |
| Extra | | | sees through `powershell -Command`, `-EncodedCommand`, `cmd /c`, `Invoke-Expression` / `iex`, `$env:USERPROFILE`, `%USERPROFILE%`, Git Bash `/c/…` and `/mnt/c/…` paths; blocks deleting shadow copies and backups (`vssadmin delete`, `wmic shadowcopy delete`, `wbadmin delete`) |

Every version also blocks the harmless **canary** command `echo PRETOOLUSE_HOOK_CANARY` on purpose. It exists so you can prove the hook is firing (Step 6) without going near a dangerous command.

## Rules for the installing agent

1. **Merge, never overwrite, config files.** Read the existing settings/hooks file first and add the hook entry alongside whatever is there. If an entry running `Destruction_blocker.py` is already registered, update it instead of adding a second one.
2. **Never delete an existing hook script.** If `Destruction_blocker.py` already exists at the destination, move it to the Trash/Recycle Bin (see "Deleting safely" below) before copying the new one in.
3. **Upgrade older installs.** Earlier versions were installed as `destructive_commands.py`. If you find one, move that script to the Trash/Recycle Bin and change its config entry to point at `Destruction_blocker.py`, so only one copy runs.
4. **Never test with a real destructive command**, not even quoted inside another command. Test offline with `tests/run_cases.py` and live with the canary only.
5. Hooks are loaded when a session starts. The live check (Step 6) must happen in a new session.

## Requirements

Python 3.8 or newer, standard library only.

## Step 2 — Find the Python command

- **macOS / Linux:** `python3`
- **Windows:** try `py -3 --version`, then `python --version`, then `python3 --version`. Use the first one that prints `Python 3.x`. Ignore any that open the Microsoft Store.

## Step 3 — Copy the script

Destination folders:

| Agent | macOS / Linux | Windows |
|---|---|---|
| Claude Code | `~/.claude/hooks/` | `%USERPROFILE%\.claude\hooks\` |
| Codex | `~/.codex/hooks/` | `%USERPROFILE%\.codex\hooks\` |

macOS / Linux example (Claude Code; from inside this folder, with `<os>` = `macos` or `linux`):

```bash
mkdir -p ~/.claude/hooks && cp "<os>/Destruction_blocker.py" ~/.claude/hooks/Destruction_blocker.py
```

Windows example (PowerShell, Claude Code):

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\hooks" | Out-Null; Copy-Item "windows\Destruction_blocker.py" "$env:USERPROFILE\.claude\hooks\Destruction_blocker.py"
```

## Step 4 — Register the hook

In the `command` field below, `<python>` is the command from Step 2 and `<script>` is the full path to the copied file.

- **macOS / Linux:** `~/.claude/hooks/Destruction_blocker.py` works as the script path.
- **Windows:** use an absolute path with forward slashes, e.g. `C:/Users/<name>/.claude/hooks/Destruction_blocker.py`. This works whether the agent runs hooks through PowerShell, cmd.exe or Git Bash.

### Claude Code

Merge into `~/.claude/settings.json` for all projects (Windows: `%USERPROFILE%\.claude\settings.json`), or into `<project>/.claude/settings.json` for one project. If `hooks.PreToolUse` already exists, append to that array.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "<python> <script>",
            "statusMessage": "Checking command for destructive operations"
          }
        ]
      }
    ]
  }
}
```

- **macOS / Linux:** `"matcher": "Bash"`, `"command": "python3 ~/.claude/hooks/Destruction_blocker.py"`.
- **Windows:** use `"matcher": "Bash|PowerShell"` so both shell tools are covered. Listing a tool that doesn't exist is harmless. Example command: `"py -3 C:/Users/<name>/.claude/hooks/Destruction_blocker.py"`.

### Codex

Merge into `~/.codex/hooks.json` (Windows: `%USERPROFILE%\.codex\hooks.json`). Create the file if it's missing; if `hooks.PreToolUse` exists, append to it. Codex matchers are regular expressions.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "^Bash$",
        "hooks": [
          {
            "type": "command",
            "command": "<python> <script>",
            "statusMessage": "Checking command for destructive operations"
          }
        ]
      }
    ]
  }
}
```

Codex may ask the user to trust a new or changed hook; it records this under `[hooks.state]` in `~/.codex/config.toml`. The user must approve that themselves.

### Any other agent

The script follows this contract. It works with any agent whose pre-tool hooks speak it, and a small adapter can wrap it for agents that don't.

- **Input (stdin):** JSON with `tool_input.command` (the shell command string) and optionally `cwd` (the agent's working directory; it falls back to the hook's own working directory). Payloads without `tool_input.command` are ignored, so it is safe to run the hook on every tool.
- **Output (stdout):** nothing means allow. To block, it prints:
  ```json
  {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "Never delete … "}}
  ```
- **Exit code:** always 0, including on unreadable input.

Register it to run before the agent's shell/terminal tool(s). If the agent expects a different format (for example "exit code 2 + reason on stderr" to block), write a tiny wrapper that runs this script and translates a `deny` on stdout into that format.

Validate any JSON you edited, e.g. `python3 -m json.tool ~/.claude/settings.json`.

## Step 5 — Verify offline

From this folder, run the test runner against the installed copy:

```bash
python3 tests/run_cases.py <os> <installed script path>
```

`<os>` is `macos`, `linux` or `windows`; on Windows use the Python command from Step 2. Expected results: `macos: 50/50`, `linux: 66/66`, `windows: 60/60`. The test commands are passed to the hook as data and never executed. The runner uses a fake home folder, so any OS's version can be tested from any machine.

## Step 6 — Verify live with the canary

Start a **new** session of the agent and ask it to run exactly:

```
echo PRETOOLUSE_HOOK_CANARY
```

- **Hook working:** the command is blocked with "PreToolUse hook is installed and working".
- **Text printed instead:** the hook is not firing. Check the following, then retry the canary:
  - **Matcher:** it must match the name the agent gives its shell tool. If unsure, widen it to `"*"` in Claude Code or `".*"` in Codex.
  - **Python command and script path:** run `<python> <script>` by hand with `{}` on stdin. It should exit silently.
  - **Codex only:** the hook has been trusted.
  - **JSON:** the settings file is valid.

## Behaviour notes

- **Original prefix rules are kept:** any command starting with `rm -rf /` or `rm -rf ~` is blocked. That includes harmless ones like `rm -rf /tmp/x` or `rm -rf ~/.cache/x`. Use a relative path, `rm -r`, or the Trash instead.
- **`find` from a protected folder is blocked:** `find` with `-delete` that starts in a protected folder is blocked even with filters, e.g. `find ~ -name .DS_Store -delete`. The same applies on Windows to `Get-ChildItem <protected folder> | Remove-Item`.
- **Not seen:**
  - paths fed through a pipe (`… | xargs rm -rf`)
  - variables other than the home and Windows system variables listed above
  - commands inside script files that are written and then run (`bash script.sh`, `pwsh -File x.ps1`)
  - Windows: `Start-Process` arguments, .NET calls such as `[IO.Directory]::Delete(…)`, and `robocopy /MIR` from an empty folder
- **It's a safety net, not a sandbox:** pair it with an instruction to the agent to send deleted files to the Trash instead of deleting them permanently.

## Deleting safely

- **macOS:** `trash <path>` (built into recent macOS at `/usr/bin/trash`; otherwise `brew install trash`).
- **Linux:** `gio trash <path>`, or `trash-put <path>` from the `trash-cli` package.
- **Windows (PowerShell):**
  - files: `Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile('<path>', 'OnlyErrorDialogs', 'SendToRecycleBin')`
  - folders: use `DeleteDirectory` instead of `DeleteFile`.
