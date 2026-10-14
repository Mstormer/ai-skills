# PreToolUse Safety Hooks — install guide

This guide is for any coding agent (Claude Code, Codex or others) installing the hook for a user, and for the user. Follow the steps in order.

## What it does

`Destruction_blocker.py` runs **before each shell command the agent runs**. It blocks commands that would destroy a disk or partition, the operating system, the home folder, standard personal folders, other users' homes, mounted drives, backups and snapshots, or the Trash / Recycle Bin. It also protects the agent's own settings files and the hook file. It only reads the command text and never runs anything.

Deleting specific files, project folders and build output still works, including a named folder inside a personal folder (`rm -rf ~/Documents/OldProject` is allowed). What is blocked is deleting a protected folder itself or everything in it (`rm -rf ~/Downloads/*`, `cd ~ && rm -rf *`).

It is a safety net against agent mistakes (a wrong variable, a wrong folder, a glob that is too broad), not a security boundary. See "Use with a sandbox" and "Limitations".

**Tamper guard: only the user changes the hook, by hand.** Once installed in its own folder (Step 3), the hook blocks any agent command or file edit that would change, move, rename, replace or delete that folder or anything in it, or change the hook's registration in the agent settings. That covers shell commands however the path is written (`~`, `$HOME`, relative after `cd`, wildcards, redirection, code inside `python -c` and similar) and Claude Code's own Edit / Write / MultiEdit / NotebookEdit tools. Reading the hook, running it, and editing other settings stay allowed. Adding `disableAllHooks` to any settings file is blocked. To update or remove the hook, the user does it by hand in a terminal or editor, outside the agent.

## Folder layout

```
PreToolUse Safety Hooks/
├── INSTALL.md                     ← this guide
├── macos/Destruction_blocker.py   ← for macOS
├── linux/Destruction_blocker.py   ← for Linux, including WSL
├── windows/Destruction_blocker.py ← for Windows (reads each command as PowerShell, cmd.exe and Git Bash)
└── tests/
    ├── run_cases.py               ← offline test runner (passes commands to the hook as data, never runs them)
    └── cases_macos.jsonl, cases_linux.jsonl, cases_windows.jsonl
```

## Step 1 — Pick the right version

Find the operating system that **the agent's shell commands run on**:

```bash
python3 -c "import platform; print(platform.system())"
```

On Windows, use `py -3` or `python` instead of `python3` if needed.

| Output | Use | Notes |
|---|---|---|
| `Darwin` | `macos/Destruction_blocker.py` | |
| `Linux` | `linux/Destruction_blocker.py` | Includes WSL: if the agent itself runs inside WSL, its commands are Linux commands. |
| `Windows` | `windows/Destruction_blocker.py` | Covers PowerShell, cmd.exe and Git Bash commands. |

Install only the one file that matches, and always under the name `Destruction_blocker.py`.

## What each version protects

All versions follow the shell's own rules: quoting and escapes, flag order (`rm -fr`, `rm -r -f`), full paths (`/bin/rm`), `~` / `$HOME`, variables set earlier in the same command, globs and `{a,b}` braces, symlinks, `cd` / `pushd` before the delete, wrappers (`sudo`, `env`, `nice`, `timeout`, `nohup`, `xargs`, `bash -c '…'`, `eval`, `$(…)`, backticks), text piped or heredoc-fed into a shell, `find -delete` / `-exec rm`, `rsync --delete`, `git clean -f`, and `xargs` fed by `find`, `ls`, `echo` or `printf`. A variable whose value is unknown is treated as possibly empty, so `rm -rf "$OUT"/*` is blocked because it could mean `rm -rf /*`.

| | macOS | Linux | Windows |
|---|---|---|---|
| System | `/`, `/Applications`, `/Library`, `/System`, `/Users`, `/Volumes`, `/bin`, `/etc`, `/opt`, `/private`, `/sbin`, `/usr`, `/usr/local`, `/var` | `/`, `/bin`, `/boot/efi`, `/dev`, `/etc`, `/lib*`, `/opt`, `/proc`, `/root`, `/sbin`, `/snap`, `/srv`, `/sys`, the main `/usr` folders, `/var/log`, package databases, `/nix/store` | every drive root and network share root, `Windows`, `Program Files`, `Program Files (x86)`, `ProgramData`, `Users`, `Recovery`, `Boot`; Git Bash `/usr`, `/bin`, `/etc` |
| Homes and drives | every home in `/Users`, every volume in `/Volumes` | every home in `/home`, drives in `/media`, `/run/media`, `/mnt`, Windows folders under WSL's `/mnt/<letter>/` | every home in `C:\Users`, folders redirected to other drives or OneDrive |
| In each home | the home itself, `Applications`, `Desktop`, `Documents`, `Downloads`, `Library` (and iCloud Drive, CloudStorage, Keychains, Mail), `Movies`, `Music`, `Pictures`, `Public`, `.ssh`, `.gnupg`, `.claude`, `.codex`, `.Trash` | the home itself, `Desktop`, `Documents`, `Downloads`, `Music`, `Pictures`, `Public`, `Templates`, `Videos` (and their localized names), `.config`, `.gnupg`, `.ssh`, `.claude`, `.codex`, the Trash, keyrings, `.password-store`, browser and mail profiles | the home itself, `Desktop`, `Documents`, `Downloads`, `Music`, `Pictures`, `Videos`, `OneDrive*`, `AppData`, `.ssh`, `.gnupg`, `.config`, `.claude`, `.codex` |
| Backups and Trash | Time Machine backups and local snapshots, volume `.Trashes`; emptying the Trash (`trash -e`, AppleScript "empty trash") | Timeshift, Back In Time, `.snapshots`, drive `.Trash-*`; `gio trash --empty`, `trash-empty`, `trash-rm` | `$Recycle.Bin`, `System Volume Information`, `Clear-RecycleBin`, `vssadmin delete`, `wmic shadowcopy delete`, `wbadmin delete`, deleting `Win32_ShadowCopy` |
| Disk tools | `diskutil` erase/partition/delete verbs, `mkfs*`, `newfs*`, writing `fdisk`/`gpt`, `asr restore`, `tmutil delete…`, writes to `/dev/disk*` (`dd`, `>`, `cp`, `tee`, `pv`) | `mkfs*`, `mke2fs`, `mkswap`, erasing `wipefs`, `blkdiscard`, writing `fdisk`/`gdisk`/`cfdisk`/`sfdisk`/`sgdisk`/`parted`, LVM/ZFS/btrfs/cryptsetup/mdadm/nvme destroy commands, writes to disk devices. Read-only forms such as `fdisk -l` stay allowed | `format`, `diskpart`, `Format-Volume`, `Clear-Disk`, `Initialize-Disk`, `Remove-Partition`, writes to `\\.\PhysicalDriveN` |
| Hook and settings (tamper guard) | the hook's install folder against any change; `~/.claude/settings.json`, `~/.claude/settings.local.json`, `~/.codex/hooks.json`, `~/.codex/config.toml` against shell changes, and against agent file edits that change the hook's registration | same | same (PowerShell `Move-Item`, `Copy-Item`, `Rename-Item`, `Set-Content` …, cmd `move`/`copy`, Git Bash) |
| Windows only | | | `Remove-Item` and its aliases, `Get-ChildItem … \| Remove-Item`, `.Delete()`, `[IO.Directory]::Delete`, `rd /s`, `del /s`, `forfiles`, `robocopy /MIR`/`/PURGE`, `sdelete`; looks inside `powershell -Command`/`-EncodedCommand`, `cmd /c`, `Invoke-Expression`, `Start-Process`, `wsl` |

Every version also blocks the harmless **canary** command `echo PRETOOLUSE_HOOK_CANARY` on purpose, so you can prove the hook is firing (Step 6) without going near a dangerous command.

## Rules for the installing agent

1. **Merge, never overwrite, config files.** Read the existing settings/hooks file first and add the hook entry next to what is there. If an entry running `Destruction_blocker.py` already exists, update it instead of adding a second one.
2. **Never delete an existing hook script.** If `Destruction_blocker.py` already exists at the destination, move it to the Trash / Recycle Bin (see "Deleting safely") before copying the new one in.
3. **Upgrade older installs.** Earlier versions were installed as `destructive_commands.py` or directly in `hooks/` (not in its own folder). If you find one, move that script to the Trash / Recycle Bin and point its config entry at the new location, so only one copy runs.
4. **Never test with a real destructive command**, not even quoted inside another command. Test offline with `tests/run_cases.py` and live with the canary only.
5. Do the live check (Step 6) in a **new** session.
6. **Install in this order: copy, test, then register last, and validate the JSON before saving.** Once the hook is registered and a session starts, the tamper guard blocks agents (including you) from changing the hook or its registration, by design. If an existing install must be updated or fixed, give the user the exact steps to do it by hand instead.

## Requirements

Python 3.8 or newer (tested with 3.9), standard library only.

## Step 2 — Find the Python command

- **macOS / Linux:** `python3`
- **Windows:** try `py -3 --version`, then `python --version`, then `python3 --version`. Use the first one that prints `Python 3.x`. Ignore any that opens the Microsoft Store.

## Step 3 — Copy the script into its own folder

The hook must live in a folder of its own named `destruction-blocker`. The tamper guard protects that whole folder; a folder name without "destruction" makes it protect only the file itself, and other hooks next to it stay editable.

| Agent | macOS / Linux | Windows |
|---|---|---|
| Claude Code | `~/.claude/hooks/destruction-blocker/` | `%USERPROFILE%\.claude\hooks\destruction-blocker\` |
| Codex | `~/.codex/hooks/destruction-blocker/` | `%USERPROFILE%\.codex\hooks\destruction-blocker\` |

macOS / Linux (Claude Code; from this folder, with `<os>` = `macos` or `linux`):

```bash
mkdir -p ~/.claude/hooks/destruction-blocker && cp "<os>/Destruction_blocker.py" ~/.claude/hooks/destruction-blocker/Destruction_blocker.py
```

Windows (PowerShell, Claude Code):

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\hooks\destruction-blocker" | Out-Null; Copy-Item "windows\Destruction_blocker.py" "$env:USERPROFILE\.claude\hooks\destruction-blocker\Destruction_blocker.py"
```

## Step 4 — Register the hook

In `command`, `<python>` is the command from Step 2 and `<script>` is the path of the copied file.

- **macOS / Linux:** `~/.claude/hooks/destruction-blocker/Destruction_blocker.py` (or `~/.codex/hooks/destruction-blocker/…`) works as the path.
- **Windows:** use the absolute path with forward slashes **in double quotes**, because a profile folder can contain spaces: `py -3 \"C:/Users/<name>/.claude/hooks/destruction-blocker/Destruction_blocker.py\"` inside the JSON string. This works whether hooks run through Git Bash or PowerShell.

`timeout` is in seconds in both Claude Code and Codex (both default to 600). The hook answers in well under a second, so 10 is plenty.

### Claude Code

Merge into `~/.claude/settings.json` for all projects (Windows: `%USERPROFILE%\.claude\settings.json`), or `<project>/.claude/settings.json` for one project. If `hooks.PreToolUse` exists, append to that array.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Edit|Write|MultiEdit|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/destruction-blocker/Destruction_blocker.py",
            "timeout": 10,
            "statusMessage": "Checking command for destructive operations"
          }
        ]
      }
    ]
  }
}
```

- The matcher includes the file-editing tools so the tamper guard sees them; for those tools the hook only checks the hook's own folder and its registration, and allows everything else.
- **Windows:** `"matcher": "Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit"` and `"command": "py -3 \"C:/Users/<name>/.claude/hooks/destruction-blocker/Destruction_blocker.py\""`.
- **Fail closed (recommended, Claude Code v2.1.295 or later; check with `claude --version`):** add `"onFailure": "block"` next to `timeout`. By default, a hook that cannot start (for example Python is missing), times out or exits with an error does **not** block the command; Claude Code shows a notice and the command runs. With `"block"`, such a failure blocks the command, so a broken install is visible instead of silently unprotected. The cost: if Python goes missing, every shell command is blocked until it is fixed.

### Codex

Merge into `~/.codex/hooks.json` (Windows: `%USERPROFILE%\.codex\hooks.json`), or `<repo>/.codex/hooks.json` for one project. Create the file if it is missing; if `hooks.PreToolUse` exists, append to it. Codex matchers are regular expressions, and its shell tools (including unified exec) match as `Bash`.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "^Bash$",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.codex/hooks/destruction-blocker/Destruction_blocker.py",
            "timeout": 10,
            "statusMessage": "Checking command for destructive operations"
          }
        ]
      }
    ]
  }
}
```

- **Windows:** `"command": "py -3 \"C:/Users/<name>/.codex/hooks/destruction-blocker/Destruction_blocker.py\""`.
- Keep the matcher at `^Bash$`. Codex also puts `apply_patch` patch text in `tool_input.command`, and this hook would read a patch as a shell command. As a result, the tamper guard does not see Codex's `apply_patch` file edits (see "Limitations").
- Codex runs a new or changed hook only after the user reviews and trusts it (`/hooks` in the CLI). The user must approve that themselves.
- What Codex does when a hook fails to start or times out is not stated in its hooks docs; check your Codex version's docs.

### Any other agent

The script follows this contract. Any agent whose pre-tool hooks speak it can use it directly; for others, a small adapter can wrap it.

- **Input (stdin):** JSON with `tool_input.command` (the shell command) and optionally `cwd` (the agent's working directory; otherwise the hook's own working directory is used). Payloads without a string `tool_input.command` are allowed, so the hook is harmless on other tools.
- **Output (stdout):** nothing means allow. To block, it prints one line:
  ```json
  {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "Blocked: rm would delete ~/Documents, which is protected …"}}
  ```
- **Exit code:** the script itself always exits 0 and writes nothing to stderr, whatever the input. It cannot report a failure to start (Python missing) or being killed by a timeout; how that is handled is up to the agent.

If the agent expects another format (for example "exit code 2 + reason on stderr" to block), write a tiny wrapper that runs this script and translates a `deny` on stdout into that format.

Validate any JSON you edited, e.g. `python3 -m json.tool ~/.claude/settings.json`.

## Step 5 — Verify offline

From this folder:

```bash
python3 tests/run_cases.py <os> [--hook PATH] [--cases FILE] [-v]
```

`<os>` is `macos`, `linux` or `windows`. Without `--hook` it tests the copy in this folder; pass `--hook` with the installed path to test that copy. `-v` prints every case. On Windows, use the Python command from Step 2.

- Add `--guard` to run the tamper-guard tests: the runner installs a copy of the hook in a dedicated `destruction-blocker` folder inside its sandbox home (with a settings file registering it) and checks that changes to the hook or its registration are blocked while reading and running it are not.
- The macOS and Linux suites must run on macOS or Linux (they build a sandbox home folder with real files and symlinks in the system temp folder).
- The Windows suite runs anywhere, but cases that need a real Windows filesystem (globs, junctions, short 8.3 names) are skipped on other hosts.

Expected results: `macos: 541/541 passed`, `linux: 815/815 passed`, `windows: 774/774 passed, 5 skipped` on a non-Windows host (779/779 on Windows). The hook protects the folders that contain its own file, so testing a copy placed in an unusual folder such as `/tmp` can fail a case that uses that folder; the installed location is fine.

## Step 6 — Verify live with the canary

Start a **new** session of the agent and ask it to run exactly:

```
echo PRETOOLUSE_HOOK_CANARY
```

- **Hook working:** the command is blocked with "PreToolUse hook is installed and working".
- **Tamper guard check:** also ask it to run `touch ~/.claude/hooks/destruction-blocker/guard-check` (Windows: `New-Item $env:USERPROFILE\.claude\hooks\destruction-blocker\guard-check`). It must be blocked with "Only the user may change it, by hand". If it is not blocked, an empty file was created; the user can remove it by hand.
- **Text printed instead:** the hook is not firing. Check, then retry the canary:
  - **Matcher:** it must match the name of the agent's shell tool. In Claude Code you can widen it to `"*"` to test.
  - **Python command and script path:** run `<python> <script>` by hand with `{}` on stdin. It should exit silently.
  - **Trust:** Claude Code holds back hooks in an interactive session until the folder's workspace trust dialog is accepted. Codex needs the hook trusted in `/hooks`, and hooks must not be turned off (`[features] hooks = false` in `~/.codex/config.toml`).
  - **JSON:** the settings file is valid.

## Uninstall (by the user, by hand)

The tamper guard blocks agents from removing the hook, so uninstalling is done by the user in their own terminal or text editor, **outside the agent**. An agent asked to uninstall it should show the user these steps instead of trying them. Do the steps in this order: if the files are removed while the hook is still registered, the agent tries to run a missing script on every command (with `"onFailure": "block"`, every command is then blocked).

**1. Unregister the hook.** Open the settings file in a text editor and delete only the `PreToolUse` entry whose `command` runs `Destruction_blocker.py`, keeping any other hooks. If that leaves `"PreToolUse": []` or `"hooks": {}`, those can go too.

| Agent | macOS / Linux | Windows |
|---|---|---|
| Claude Code | `~/.claude/settings.json` (and any project `.claude/settings.json` you added it to) | `%USERPROFILE%\.claude\settings.json` |
| Codex | `~/.codex/hooks.json` | `%USERPROFILE%\.codex\hooks.json` |

Check that the file is still valid JSON:

```bash
python3 -m json.tool ~/.claude/settings.json
```

For Codex, the trust record left under `[hooks.state]` in `~/.codex/config.toml` is harmless; delete it by hand if you want.

**2. Close and restart the agent** so it stops loading the hook.

**3. Move the hook's folder to the Trash / Recycle Bin.**

- **macOS:**
  ```bash
  trash ~/.claude/hooks/destruction-blocker
  ```
  (Codex: `~/.codex/hooks/destruction-blocker`. Without the `trash` command: `mv ~/.claude/hooks/destruction-blocker ~/.Trash/`.)
- **Linux:**
  ```bash
  gio trash ~/.claude/hooks/destruction-blocker
  ```
- **Windows (PowerShell):**
  ```powershell
  Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory("$env:USERPROFILE\.claude\hooks\destruction-blocker", 'OnlyErrorDialogs', 'SendToRecycleBin')
  ```

**4. Check it is gone:** in a new agent session, `echo PRETOOLUSE_HOOK_CANARY` now prints the text instead of being blocked.

To **update** instead of uninstall: the user replaces `Destruction_blocker.py` in the `destruction-blocker` folder by hand with the new version (moving the old one to the Trash), then restarts the agent; the registration stays as it is.

## Use with a sandbox

The hook reads command text; it cannot see what a script or program does once it runs. For a real boundary, also turn on the agent's sandbox, which the operating system enforces:

- **Claude Code:** run `/sandbox`, or set `"sandbox": {"enabled": true}` in settings. It limits writes from shell commands to the working directory, a temp folder and added folders. It runs on macOS, Linux and WSL2, not native Windows.
- **Codex:** `sandbox_mode = "workspace-write"` in `~/.codex/config.toml` (or `codex --sandbox workspace-write`).

Also tell the agent to move files to the Trash instead of deleting them (see "Deleting safely").

## Behaviour notes

- **Fail closed:** if a command contains a delete or disk tool and the hook cannot fully understand it, it is blocked with "Could not verify this command is safe (…); run a simpler command or ask the user." This covers shell functions, arrays, `case`/`select`, GNU `parallel`, rare `${…}` forms such as `${x/a/b}`, `pushd +N`, AppleScript `do shell script`, PowerShell splatting, the `-f` format operator, path-building .NET calls, cmd `for` loops, broken quoting, and commands that are too long (over 200 KB), too deeply nested or too slow to analyze. The same constructs in a command with no delete or disk tool are allowed.
- **Deliberate over-blocks** (simplest fix: name the files, `cd` into the project first, or use the Trash):
  - `find` with `-delete` or `-exec rm` that starts in a protected folder, even with filters: `find ~ -name .DS_Store -delete`. The same applies to `Get-ChildItem <protected folder> … | Remove-Item`.
  - An unset or unknown variable in a path: `rm -rf "$OUT"/*` (could be `/*`).
  - `if`/`while` bodies are checked as if each part may or may not run, so `if cd build; then rm -rf *; fi` run from the home folder is blocked. Write `cd build && rm -rf *`.
  - With an unknown working directory, relative targets such as `.`, `*` or `Documents` are blocked.
  - Linux: `at`/`batch` jobs and `gio remove` paths are checked as if run from an unknown folder.

## Limitations

The hook does **not** catch:

- Commands inside script files (`bash script.sh`, `source x.sh`, `pwsh -File x.ps1`, `make`, npm scripts), or code run by other interpreters (`python -c`, `node -e`, `perl -e`).
- Input it cannot know: `curl … | bash`, `cat list.txt | xargs rm -rf`, `xargs -a FILE`.
- Changes made through the agent's own file tools to anything other than the hook and its registration (Claude Code's Edit/Write are checked only for those). Codex `apply_patch` edits are not seen at all.
- Tampering by routes the hook never sees: other tools such as MCP file servers, a script file written and then run, or a program that builds the hook's path at run time. For a lock no agent can open, the user can additionally register the hook in the agent's administrator-managed settings and place it in a folder only an administrator can change (Claude Code on macOS: `/Library/Application Support/ClaudeCode/managed-settings.json`); agents run without the administrator password.
- Codex `write_stdin` input to an already running command; Codex does not re-run hooks for it.
- Some shell-running wrapper forms: `script -qc '…'`, `flock -c '…'`, `su -lc '…'`, `env -iS '…'`, and `sudo -s` / `sudo -i` fed by a pipe or heredoc.
- Damage outside its scope: project files, git history (`git reset --hard`, force push), databases, cloud or remote resources.

## Deleting safely

- **macOS:** `trash <path>` (built into recent macOS at `/usr/bin/trash`; otherwise `brew install trash`).
- **Linux:** `gio trash <path>`, or `trash-put <path>` from the `trash-cli` package.
- **Windows (PowerShell):**
  - files: `Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile('<path>', 'OnlyErrorDialogs', 'SendToRecycleBin')`
  - folders: use `DeleteDirectory` instead of `DeleteFile`.
