# PreToolUse Safety Hooks

`Destruction_blocker.py` is a PreToolUse hook for AI coding agents (Claude Code, Codex and others). It checks every shell command, and the agent's own file edits, **before they run**, and blocks the ones that would destroy a disk, the operating system, your home or personal folders, backups or the Trash. Everyday work, including deleting specific files and project folders, keeps working. It only reads the command text and never runs anything.

Install: follow [INSTALL.md](INSTALL.md), or ask your agent to. Pick the version for the system the agent's commands run on.

## macOS — `macos/Destruction_blocker.py`

- **Protects** `/`, the system folders (`/System`, `/Library`, `/Applications`, `/usr`, `/etc`, …), every user's home in `/Users`, every drive in `/Volumes`, and in your home: the home itself, Desktop, Documents, Downloads, Library (with iCloud Drive, Keychains, Mail), Movies, Music, Pictures, Public, `.ssh`, `.gnupg`, `.claude`, `.codex` and the Trash.
- **Allows** deleting specific files or subfolders inside them, such as `rm ~/Desktop/photo.jpg` or `rm -rf ~/Documents/OldProject`. Blocks deleting a protected folder itself or everything in it, such as `rm -rf ~/Desktop/*` or `cd ~ && rm -rf *`.
- **Reads commands the way the shell does:**
  - quoting and escapes
  - `~`, `$HOME` and variables set earlier in the command; an unset variable counts as empty, so `rm -rf "$OUT"/*` is caught
  - `{a,b}` braces, wildcards and symlinks
  - `cd`, `pushd` and subshells before the delete
  - `&&`, `||`, `;` and pipes
  - wrappers: `sudo`, `env`, `nice`, `timeout`, `nohup`, `xargs`, `bash -c`, `eval`, `$(…)`, heredocs
- **Covers more than `rm`:** `find -delete` / `-exec rm`, `rsync --delete`, `git clean -fdx`, and raw writes to disks (`dd`, `>`, `cp`, `tee`).
- **Blocks Mac disk and backup tools:** `diskutil` erase / partition / delete, `newfs`, writing `fdisk` / `gpt`, `asr restore`, `tmutil delete`, and emptying the Trash (`trash -e`, AppleScript "empty trash").
- **Fails safe:** if a command uses a delete or disk tool in a way the hook can't fully understand, such as shell functions, arrays or `case`, it is blocked with "Could not verify this command is safe". The same constructs without a risky tool pass.
- **Guards itself.** Once installed in its own `destruction-blocker` folder, agents can't change, move, replace or delete the hook, by command or by Claude Code's Edit/Write tools. They also can't remove its entry from the agent settings, narrow its matcher, or set `disableAllHooks`. Only the user changes it, by hand. Reading and running it, and editing other settings, stay allowed.
- **Explains itself:** every block says what was protected, why, and what to do instead, for example "move items to the Trash with: trash <path>". A harmless canary command, `echo PRETOOLUSE_HOOK_CANARY`, is always blocked so you can confirm the hook is live.

## Linux — `linux/Destruction_blocker.py`

- **Protects** `/`, `/boot`, `/etc`, `/usr`, `/root` and the other system folders, every home in `/home`, drives in `/media`, `/run/media` and `/mnt` (including Windows drives under WSL), and in your home: the home itself, Desktop, Documents, Downloads, Music, Pictures, Public, Templates and Videos (including renamed or translated versions such as `~/Dokumente`), `.config`, `.ssh`, `.gnupg`, `.claude`, `.codex`, keyrings and the Trash.
- **Same engine as macOS:** the shell-reading engine is byte-identical to the macOS hook, so everything in the macOS list about quoting, variables, `cd`, wrappers, `find` / `rsync` / `git clean`, failing safe, self-guarding, messages and the canary applies here too.
- **Blocks Linux disk tools:**
  - `mkfs` / `mke2fs` / `mkswap`
  - erasing `wipefs`
  - `shred` or `blkdiscard` on a disk
  - writing `fdisk`, `gdisk`, `cfdisk`, `sfdisk`, `sgdisk` or `parted`
  - LVM / ZFS / btrfs / cryptsetup / mdadm destroy commands
  - `dd` and other writes to disk devices
- **Allows read-only forms** such as `fdisk -l`, `parted -l`, `wipefs -n` and `--help`.
- **Protects backups and the Trash:** Timeshift, Back In Time and `.snapshots` are protected; `gio trash --empty`, `trash-empty` and `trash-rm` are blocked. Suggests `gio trash` / `trash-put` for safe deletes.
- **Case-sensitive paths**, as on Linux filesystems. Home folders and user names come from the system, never hard-coded.

## Windows — `windows/Destruction_blocker.py`

- **Protects** every drive root and network share root, `Windows`, `Program Files`, `Program Files (x86)`, `ProgramData`, `Users`, `Recovery`, every user's home, and in your home: the home itself, Desktop, Documents, Downloads, Music, Pictures, Videos, OneDrive (including redirected folders), AppData, `.ssh`, `.claude`, `.codex`, plus the Recycle Bin and System Volume Information.
- **Reads every command three ways**, and any block wins:
  - as Git Bash, using the same engine as macOS and Linux (that's what Claude Code uses on Windows)
  - as PowerShell
  - as cmd.exe
- **Understands every Windows path form:** `C:\x`, `C:/x`, `/c/x`, `/mnt/c/x`, `\\server\share`, `%USERPROFILE%`, `$env:X` and `~`, all compared ignoring case.
- **PowerShell checks:**
  - `Remove-Item` and its aliases (`ri`, `rm`, `del`, `rd`, `erase`)
  - `Get-ChildItem … | Where-Object … | Remove-Item` pipelines
  - `.Delete()` and `[IO.Directory]::Delete`
  - `Set-Content` / `Out-File` overwrites
  - code run through `Invoke-Expression`, `Start-Process`, `powershell -Command` and `-EncodedCommand`
- **Allowed on purpose:** `-WhatIf` dry runs and moves to the Recycle Bin.
- **cmd checks:** `rd /s`, `del /s`, `cmd /c …`, `forfiles`, and `robocopy /MIR` / `/PURGE` onto protected folders.
- **Blocks Windows disk and backup tools:** `format`, `diskpart`, `Format-Volume`, `Clear-Disk`, `Initialize-Disk`, `Remove-Partition`, writes to `\\.\PhysicalDriveN`, deleting shadow copies (`vssadmin`, `wmic`, CIM), `wbadmin delete` and `Clear-RecycleBin`.
- **Guards itself and explains itself** the same way as on macOS and Linux, including PowerShell `Move-Item`, `Copy-Item`, `Rename-Item` and cmd `move` / `copy` aimed at the hook or the agent settings.

## Tests

`tests/run_cases.py` sends each test command to the hook as data and never runs it. It checks the exit code, the output format and the speed, and it builds a sandbox home folder with real files and symlinks. Run `python3 tests/run_cases.py <macos|linux|windows>` for the main suite, or add `--guard` for the self-protection tests.

## Limits

The hook is a safety net against agent mistakes, not a security boundary. For that, pair it with the agent's sandbox. It can't see:
- commands inside script files, or code run by other interpreters
- input it can't know, such as `curl … | bash`
- Codex `apply_patch` edits
- damage outside its scope, such as project files, git history or remote systems

See [INSTALL.md](INSTALL.md) for details.
