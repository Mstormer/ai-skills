#!/usr/bin/env python3
"""Destruction_blocker (Windows): PreToolUse hook for AI coding agents (Claude Code, Codex, ...).

Denies commands that would destroy a disk, Windows, the home folder, personal folders, other users' homes, drive or
share roots, shadow copies or the Recycle Bin; deleting specific files and project subfolders stays allowed. It only
reads the command text, as Git Bash (the shared POSIX core on a Windows path model), as PowerShell and as cmd.exe:
any denial wins, and a reading that does not parse belongs to another dialect. Sections: WINDOWS CONFIG | SHARED
POSIX CORE (identical to the macOS hook) | POWERSHELL, CMD AND WINDOWS PROGRAMS | ENTRY POINT.
Allow = print nothing; deny = one JSON line; always exit 0.
"""
import fnmatch, io, itertools, json, os, posixpath, re, sys, time

# ==== WINDOWS CONFIG ====
# The core's OS interface (contract: see the macOS hook) on canonical paths: drive C: is /c, a share is /unc:/srv/share,
# a raw device is /dev/X; other absolute paths are Git Bash's own (/, /usr, /tmp). Names compare ignoring case (NTFS).
try: _ENV = {k.upper(): v for k, v in os.environ.items()}
except Exception: _ENV = {}
_WABS = re.compile(r"[A-Za-z]:[\\/]|\\\\[^\\]")
_SD = _ENV.get("SYSTEMDRIVE", "C:")[:2] if re.match(r"[A-Za-z]:$", _ENV.get("SYSTEMDRIVE", "")) else "C:"
WIN_HOME = next((h for h in (_ENV.get("USERPROFILE", ""), _ENV.get("HOMEDRIVE", "") + _ENV.get("HOMEPATH", ""))
                 if _WABS.match(h)), _SD + "\\Users\\" + (_ENV.get("USERNAME") or "user")).rstrip("\\/")
_LAD = _ENV.get("LOCALAPPDATA") or WIN_HOME + "\\AppData\\Local"
_DEFAULTS = {"userprofile": WIN_HOME, "homedrive": WIN_HOME[:2], "homepath": WIN_HOME[2:], "systemdrive": _SD,
             "systemroot": _SD + "\\Windows", "windir": _SD + "\\Windows", "programfiles": _SD + "\\Program Files",
             "programfiles(x86)": _SD + "\\Program Files (x86)", "programdata": _SD + "\\ProgramData",
             "appdata": WIN_HOME + "\\AppData\\Roaming", "localappdata": _LAD, "temp": _LAD + "\\Temp",
             "tmp": _LAD + "\\Temp"}

def win_env(name):  # an environment variable (any case), with Windows defaults; None if unknown
  v = _ENV.get(name.upper())
  return v if v is not None else _DEFAULTS.get(name.lower())

def os_path_chars(chars):
  """Readings as canonical chars (\\ is a separator): C:\\x, \\\\?\\C:\\x, /mnt/c/x are /c/x, \\\\srv\\share is
  /unc:/srv/share, \\\\.\\X is /dev/X, \\x is on the system drive, C:x is read from C:\\ and from the cwd; trailing
  dots and ::$DATA are dropped and 8.3 names (PROGRA~1) become globs."""
  t = "".join(c for c, _ in chars)
  k = len(t) - len(re.sub(r"(?i)^(?:microsoft\.powershell\.core\\)?filesystem::", "", t))
  ch, low = [("/", False) if c == "\\" else (c, g) for c, g in chars[k:]], t[k:].replace("\\", "/").lower()
  m = re.match(r"//[?.]/(?:([a-z]):/|(unc)/)?|(//)(?!/)|([a-z?*]|\[[^]/]*\]):(/?)|/(?:mnt|cygdrive)(?=/[a-z](?:/|$))|",
               low)
  e, pre = m.end(), "/" + _SD[0].lower() if t[k:k + 1] == "\\" and t[k + 1:k + 2] != "\\" else ""
  if m.group(1) or m.group(2) or m.group(3) or low[:4] in ("//?/", "//./"):
    pre = "/%s/" % m.group(1) if m.group(1) else "/unc:/" if m.group(2) or m.group(3) else "/dev/"
  pre = [(c, False) for c in pre] if not m.group(4) else [("/", 0)] + ch[:m.end(4)] + [("/", 0)]
  out = []
  for r in [pre + ch[m.end(4) + 1 if m.group(4) else e:]] + [ch[m.end(4) + 1:]] * bool(m.group(4) and not m.group(5)):
    res, comp = [], []
    for c in r + [("/", 0)]:
      if c[0] != "/":
        comp.append(c)
        continue
      s = "".join(x for x, _ in comp)
      m2 = s not in (".", "..") and re.match(r"(?i)([^~*?[]{1,6})~\d{1,6}(?:\.[^.]{0,3})?$|(.*?)(?:::\$index_alloca"
                                             r"tion|:\$i30:\$index_allocation|::\$data)?[. ]*$", s)
      res += (comp[:len(m2.group(1))] + [("*", True)] if m2.group(1) else comp[:len(m2.group(2))] or comp) if m2 \
          else comp
      res.append(c)
      comp = []
    out.append(res[:-1])
  return out

def _canon(p):  # canonical form of an absolute path ("" if relative)
  t = "".join(c for c, _ in os_path_chars([(c, False) for c in p])[0])
  return re.sub("^/+", "/", posixpath.normpath(t)) if t[:1] == "/" else ""

if ";" in _ENV.get("CDPATH", "") or _WABS.match(_ENV.get("CDPATH", "")):  # the core reads CDPATH as /-paths
  os.environ["CDPATH"] = ":".join(_canon(d) or d for d in _ENV["CDPATH"].split(";"))

def _win(p):  # Windows form of a canonical path
  m = re.match(r"/([A-Za-z])(?=/|$)", p)
  if m: return m.group(1).upper() + ":" + (p[2:] or "/").replace("/", "\\")
  return "\\\\" + p[6:].replace("/", "\\") if p[:6].lower() == "/unc:/" else p

def os_forms(path):
  out = [_norm(path if path[:1] == "/" else _canon(path) or path)]
  if os.name == "nt" and re.match(r"/[a-z](?:/|$)", out[0], re.I):  # Windows host: junctions, links, 8.3 names
    try: out.append(_canon(os.path.realpath(_win(out[0]))))
    except Exception: pass
  return out

OS_CASE_INSENSITIVE = True
OS_HOME = _canon(WIN_HOME) or "/"
OS_TRASH_HINT = "move them to the Recycle Bin"
OS_DISK_HINT = "Ask the user to run disk, partition and backup operations themselves."
OS_DEVICE_RE = re.compile(r"/dev/(?:sd|hd|vd|xvd|nvme|mmcblk|sr|loop|md|dm-|mapper/|disk/by-|r?disk\d|physicaldrive|"
                          r"harddisk|volume\{|cdrom|globalroot|[a-z]:/?$)", re.I)
OS_DEVICE_SAMPLES = ("/dev/sda /dev/sda1 /dev/hda /dev/vda /dev/nvme0n1 /dev/nvme0n1p1 /dev/disk0 /dev/disk9 "
                     "/dev/disk/by-id/usb-0 /dev/PhysicalDrive0 /dev/C:").split()
OS_SLOW_ROOTS = ("/unc:",)
OS_RISKY = (r"rm srm grm ri rmdir rd del erase remove-item format diskpart format-volume clear-disk initialize-disk "
            r"remove-partition reset-physicaldisk remove-physicaldisk remove-virtualdisk remove-storagepool vssadmin "
            r"wmic wbadmin robocopy clear-recyclebin clear-content set-content out-file forfiles sdelete\d* "
            r"remove-ciminstance remove-wmiobject dd gdd shred mkfs[\w.]* mke2fs mkswap wipefs blkdiscard fdisk gdisk "
            r"cfdisk sfdisk sgdisk parted").split()
OS_RISKY_COMBOS = ((r"\bg?find\b", r"-(?:delete|exec|execdir|ok|okdir)\b"), (r"\brsync\b", r"--(?:del|remove-s)"),
                   (r"\bgit\b", r"\bclean\b"), (r"\.delete\w*\s*\(|::\s*delete|deletedirectory|deletefile", ""),
                   (r"(?:>|\bof=)\s*['\"]?(?:/dev/(?!(?:null|zero|std(?:in|out|err)|tty|u?random)\b|fd/)|[\\/]{2}[.?])",
                    ""))
_HG = re.sub(r"([*?[])", r"[\1]", OS_HOME)
_HN = ("Desktop Documents Downloads Music Pictures Videos Favorites Contacts Links Searches OneDrive AppData "
       "AppData/Local AppData/Roaming AppData/LocalLow .ssh .gnupg .config .claude .codex").split()
try: _ME = os.path.basename(__file__)
except Exception: _ME = "Destruction_blocker.py"
_EXTRA = [_ENV.get(v, "") for v in "SYSTEMROOT WINDIR PROGRAMFILES PROGRAMFILES(X86) PROGRAMDATA APPDATA".split()]
for _v in (_ENV.get(v, "") for v in ("ONEDRIVE", "ONEDRIVECONSUMER", "ONEDRIVECOMMERCIAL")):
  _EXTRA += [_v] + [_v + "\\" + n for n in ("Desktop", "Documents", "Pictures")] if _v else []
if os.name == "nt":  # redirected known folders (Documents on D:, in OneDrive, ...)
  try:
    import winreg
    _k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
    _EXTRA += [winreg.ExpandEnvironmentStrings(str(winreg.EnumValue(_k, i)[1]))
               for i in range(winreg.QueryInfoKey(_k)[1])]
  except Exception: pass
OS_PROTECTED = (
    [("d", p) for p in ["/", "/?", "/unc:/*/*", "/usr", "/usr/bin", "/bin", "/etc", "/lib", "/mingw64", "/dev/*",
                        "/mnt/*", "/cygdrive/*", "/home/*", _HG] + ["/?/" + n for n in (
                        "Windows", "Windows/System32", "Program Files", "Program Files (x86)", "ProgramData", "Users",
                        "Users/*", "Recovery", "Boot", "Documents and Settings")]]
    + [("t", "/?/" + n) for n in ("$Recycle.Bin", "Recycler", "System Volume Information")]
    + [("d", d + "/" + n) for d in ("/?/Users/*", _HG) for n in _HN]
    + [("d", _HG + "/OneDrive*" + n) for n in ("", "/Desktop", "/Documents", "/Pictures")]
    + [("f", _HG + "/" + f) for f in (".claude/settings.json", ".claude/settings.local.json", ".codex/hooks.json",
                                      ".codex/config.toml", ".claude/hooks/" + _ME, ".codex/hooks/" + _ME)]
    + [("d", p) for p in map(_canon, (x for x in _EXTRA if _WABS.match(x))) if p.count("/") > 1])

def os_user_home(name):
  return posixpath.join(posixpath.dirname(OS_HOME), name)

def os_command_name(word):
  n = word.replace("\\", "/").rsplit("/", 1)[-1].lower()
  n = "fd" if n == "fdfind" else n[:-4] if n[-4:] in (".exe", ".com", ".bat", ".cmd") else n
  return n[1:] if n[:1] == "g" and n[1:] in ("rm", "find", "timeout", "xargs", "dd", "shred", "tee", "cp", "env",
                                             "ls", "echo", "printf", "cat", "realpath", "readlink", "pwd") else n

def os_tool_reason(name, args, stdin_text):  # Linux disk tools (Git Bash, WSL); Windows ones: see win_program
  low = [a.lower() for a in args]
  o = set("".join(a[1:] for a in args if a[:1] == "-" and a[:2] != "--"))
  o |= {a.split("=")[0] for a in low if a[:2] == "--"}
  dev = any(a[:5] == "/dev/" or a[:4] in ("\\\\.\\", "//./") for a in low)
  if (name[:4] == "mkfs" or name in ("mke2fs", "mkswap", "mkntfs", "mkdosfs")) and (dev or not set(low) <= {"-h", "-v",
          "--help", "--version"}) or dev and (name == "blkdiscard" or name == "wipefs" and o & {"a", "o", "--all",
          "--offset"} and not o & {"n", "--no-act"} or name == "fdisk" and not o & {"l", "x", "--list",
          "--list-details"} or name in ("gdisk", "cfdisk", "parted") and not o & {"l", "--list"} or name in (
          "sfdisk", "sgdisk") and (not o or o - set("ldJsVgFpivbLPO") - {"--list", "--dump", "--json", "--show-size",
                                                                        "--verify", "--print", "--info", "--backup",
                                                                        "--pretend"})):
    return "Blocked: %s erases, repartitions or formats a disk. %s" % (name, OS_DISK_HINT)
  return None


# ==== SHARED POSIX CORE: keep identical in macos/ and linux/ (and the POSIX pass in windows/) ====
# Parser -> Node tree -> run() walks it with a State (possible cwds, variables, dir stack); simple commands are
# expanded into fields and dispatched to handlers that raise Deny. What is not understood raises Unsure or calls
# ctx.doubt(), and analyze() applies S1 (deny only if RISKY). Left to S1 on purpose (rare for agents):
# case/select/coproc, functions, arrays, ${x/a/b} and other exotic ${...}, shift, printf -v, pushd +N, parallel.
OPAQUE = "\0"          # unknown text inside a path
UNKNOWN_DIR = "\0cwd"  # an unknown working directory
MAX_INPUT, TIME_BUDGET, MAX_STEPS = 200000, 1.6, 400000
MAX_DEPTH, MAX_NEST, MAX_BRACE, MAX_GLOB, MAX_ALTS, MAX_FORKS = 8, 60, 256, 5000, 32, 3
E_VALUE, N_VALUE = (("E", ""),), (("N", ""),)

class Deny(Exception):
  """A definite reason to block the command."""

class Unsure(Exception):
  """Analysis cannot finish (budget, depth, construct not understood): S1 decides."""

class Ctx:
  """Budgets and bookkeeping of one analysis."""

  def __init__(self):
    self.deadline, self.steps, self.check, self.depth = time.monotonic() + TIME_BUDGET, 0, 64, 0
    self.unsure, self.listings, self.produced, self.proc = [], [], None, None

  def tick(self, n=1):
    self.steps += n
    if self.steps > self.check:
      self.check = self.steps + 64
      if self.steps > MAX_STEPS or time.monotonic() > self.deadline:
        raise Unsure("the command is too complex to analyze")

  def doubt(self, reason):
    self.unsure.append(reason)

  def listing(self, items):
    self.listings.append(items)
    return str(len(self.listings) - 1)

def _nested(ctx, fn, *args):
  """Run fn one level deeper (shell inside shell, substitution, xargs/find -exec): S1 beyond MAX_DEPTH."""
  if ctx.depth >= MAX_DEPTH: raise Unsure("commands are nested too deeply")
  ctx.depth += 1
  try: return fn(*args)
  finally: ctx.depth -= 1

class Node:
  """Syntax node: list, andor, pipe, simple, sub, group, block, for, arith, redir."""

  def __init__(self, kind, **kw):
    self.kind, self.redirs = kind, []
    self.__dict__.update(kw)

class Produced:
  """What a command writes to stdout: text, listed items [(field, State)], values; None = unknown."""

  def __init__(self, text=None, items=None, value=None):
    self.text, self.items, self.value = text, items, value

# ---------- lexer and parser ----------
# Word parts: ("lit", text, quoted) | ("var", name, op, arg parts, dq) | ("cmd", node, dq) | ("arith", parts, dq)
# | ("proc", node, "<" or ">") | ("tilde", [paths]) (made by expansion).
_OPS = ("&&", "||", "|&", "&>>", "&>", "<<<", "<<-", "<<", "<>", "<&", ">&", ">>", ">|", "<", ">", ";", "&", "|",
        "(", ")")
_REDIR = frozenset(_OPS[3:15])
_TOKEN = re.compile(r"([0-9]+)(?=[<>])|" + "|".join(map(re.escape, _OPS)))
_SPECIAL = {"w": " \t\n;&|<>()'\"\\$`", "q": "\"\\$`", "h": "\\$`", "b": "{}'\"\\$`", "B": "{}\"\\$`", "a": "()'\"\\$`"}
_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_ANSI = {"n": "\n", "t": "\t", "r": "\r", "e": "\x1b"}
_BLOCKS = {"if": ("then", "elif", "else", "fi"), "while": ("do", "done"), "until": ("do", "done")}
_DECL = ("export", "declare", "typeset", "local", "readonly")

def _lit(parts):
  return "".join(p[1] for p in parts) if all(p[0] == "lit" for p in parts) else None

class Parser:
  """Quote-aware POSIX/bash lexer and recursive-descent parser (never executes anything)."""

  def __init__(self, src, ctx, nest=0):
    self.s, self.n, self.i, self.ctx, self.tok, self.pending, self.nest = src, len(src), 0, ctx, None, [], nest

  def peek(self):
    if self.tok is None: self.tok = self._next()
    return self.tok

  def take(self):
    t, self.tok = self.peek(), None
    return t

  def _next(self):
    s = self.s
    self.ctx.tick()
    self.i = re.compile(r"(?:[ \t]|\\\n|#[^\n]*)*").match(s, self.i).end()
    if self.i >= self.n: return ("eof",)
    c = s[self.i]
    if c == "\n":
      self.i += 1
      self._heredocs()
      return ("nl",)
    if c in "<>" and s.startswith("(", self.i + 1):
      self.i += 2
      return ("w", [("proc", self._sub(), c)] + self._scan("w"))
    m = _TOKEN.match(s, self.i)
    if not m: return ("w", self._scan("w"))
    self.i = m.end()
    return ("io", m.group(1)) if m.group(1) else ("op", m.group())

  def _scan(self, mode):
    """Parts up to the end of: a word (w), "..." (q), a heredoc (h), ${x op WORD} (b; B in "..."), ((...)) (a)."""
    s, n, parts, buf, depth, q = self.s, self.n, [], [], 0, mode in "qhB"
    run = re.compile("[^%s]+" % re.escape(_SPECIAL[mode]))
    while True:
      self.ctx.tick()
      if self.i >= n:
        if mode in "wh": break
        raise Unsure("a quote or expansion is not closed")
      c = s[self.i]
      if mode == "w" and c in " \t\n;&|<>()" or mode == "q" and c == '"' or not depth and (
              mode in "bB" and c == "}" or mode == "a" and c == ")"):
        if mode == "a" and not s.startswith("))", self.i): raise Unsure("unbalanced parentheses")
        self.i += {"w": 0, "a": 2}.get(mode, 1)
        break
      if c == "\\":
        d = s[self.i + 1:self.i + 2]
        if q and d not in ("$", "`", "\\", "\n") and (d != '"' or mode == "h"):
          buf.append(c)  # a backslash that escapes nothing stays
          self.i += 1
          continue
        self.i += 2
        if q or d == "\n":
          buf.append(d.strip("\n"))
          continue
      elif c not in "$`'\"" or c == '"' and mode == "h" or c == "'" and q:
        if mode in "bB" and c in "{}" or mode == "a" and c in "()": depth += 1 if c in "{(" else -1
        m = run.match(s, self.i) if c not in _SPECIAL[mode] else None
        buf.append(m.group() if m else c)
        self.i = m.end() if m else self.i + 1
        continue
      if buf:
        parts.append(("lit", "".join(buf), q))
        buf = []
      if c == "\\":
        parts.append(("lit", d or "\\", True))
      elif c == "'":
        j = s.find("'", self.i + 1)
        if j < 0: raise Unsure("a quote is not closed")
        parts.append(("lit", s[self.i + 1:j], True))
        self.i = j + 1
      elif c == '"':
        self.i += 1
        parts += self._scan("q")
      else:
        parts += self._dollar(q) if c == "$" else [self._backtick(q)]
    if buf or q and not parts: parts.append(("lit", "".join(buf), q))
    return parts

  def _dollar(self, dq):
    s, i = self.s, self.i + 1
    c = s[i:i + 1]
    if s.startswith("((", i):
      self.i = i + 2
      return [("arith", self._arith(), dq)]
    if c in ("(", "{") or c in ("'", '"') and not dq:
      self.i = i + 1
      if c == "(": return [("cmd", self._sub(), dq)]
      if c == "{": return [self._param(dq)]
      if c == '"': return self._scan("q")
      m = re.compile(r"(?:[^'\\]|\\.)*'", re.S).match(s, self.i)
      if not m: raise Unsure("a quote is not closed")
      self.i = m.end()
      return [("lit", re.sub(r"\\(.)", lambda e: _ANSI.get(e.group(1), e.group(1)), m.group()[:-1], flags=re.S),
               True)]  # $'...': common escapes only (\xHH, \uHHHH and octal are not decoded)
    m = re.compile(_NAME + r"|[@*#?$!0-9-]").match(s, i)
    self.i = m.end() if m else i
    return [("var", m.group(), None, None, dq)] if m else [("lit", "$", dq)]

  def _param(self, dq):  # ${...} after '${'; unsupported forms are S1 doubts with unknown values
    s, i, pat = self.s, self.i, re.compile(_NAME + r"|[0-9]+|[@*#?$!-]")
    m = pat.match(s, i + 1) if s.startswith("#", i) else None
    if m and s.startswith("}", m.end()):  # ${#name}: a length
      self.i = m.end() + 1
      return ("var", "#", None, None, dq)
    m = pat.match(s, i)
    if m:
      name, i = m.group(), m.end()
      if s.startswith("}", i):
        self.i = i + 1
        return ("var", name, None, None, dq)
      for op in (":-", ":=", ":?", ":+", "##", "%%", "-", "=", "?", "+", "#", "%"):
        if s.startswith(op, i):
          self.i = i + len(op)
          return ("var", name, op, self._scan("B" if dq else "b"), dq)
    self.ctx.doubt("an unsupported ${...} expansion")
    self._scan("B" if dq else "b")
    return ("var", None, None, None, dq)

  def _arith(self):
    """Substitutions inside ((...)); text that looks like commands is a doubt (bash may read nested subshells)."""
    start = self.i
    parts = self._scan("a")
    if is_risky(self.s[start:self.i]): self.ctx.doubt("an arithmetic expression may hide commands")
    return [p for p in parts if p[0] in ("cmd", "arith")]

  def _backtick(self, dq):
    m = re.compile(r"(?:[^`\\]|\\.)*`", re.S).match(self.s, self.i + 1)
    if not m: raise Unsure("a backtick substitution is not closed")
    self.i = m.end()
    text = re.sub(r'\\([`$\\"])' if dq else r"\\([`$\\])", r"\1", m.group()[:-1])
    return ("cmd", Parser(text, self.ctx, self.nest + 1).parse(), dq)

  def _sub(self):  # $( ... ) or <( ... ) up to the closing ')'
    self.nest += 1
    if self.nest > MAX_NEST: raise Unsure("commands are nested too deeply")
    body = self.plist((")",))
    if self.take() != ("op", ")"): raise Unsure("a $( ... ) substitution is not closed")
    self.nest -= 1
    return body

  def _heredocs(self):
    s, n = self.s, self.n
    for r in self.pending:
      lines = []
      while self.i < n:
        self.ctx.tick()
        j = s.find("\n", self.i) % (n + 1)
        line, self.i = s[self.i:j], j + 1
        line = line.lstrip("\t") if r.strip else line
        if line == r.delim: break
        lines.append(line + "\n")
      r.body = "".join(lines)
      if not r.quoted: r.parts = Parser(r.body, self.ctx, self.nest + 1)._scan("h")
    self.pending = []

  # ---------- grammar ----------
  def parse(self):
    body = self.plist(())
    if self.peek()[0] != "eof": raise Unsure("unexpected syntax")
    self._heredocs()
    return body

  def kw(self, t, words):  # the reserved word that token t is (one of `words`), else None
    if t[0] == "w" and len(t[1]) == 1 and t[1][0][0] == "lit" and not t[1][0][2] and t[1][0][1] in words:
      return t[1][0][1]
    return None

  def expect(self, *words):
    w = self.kw(self.take(), words)
    if w is None: raise Unsure("unexpected syntax")
    return w

  def stop(self, t, stops):
    return t[0] == "eof" or t == ("op", ")") and ")" in stops or self.kw(t, stops) is not None

  def skipnl(self):
    while self.peek()[0] == "nl": self.take()

  def plist(self, stops):
    items = []
    while True:
      self.skipnl()
      if self.stop(self.peek(), stops): return Node("list", items=items)
      node = self.andor()
      t = self.peek()
      if t in (("op", ";"), ("op", "&"), ("nl",)): self.take()
      elif not self.stop(t, stops): raise Unsure("unexpected syntax")
      items.append((node, t == ("op", "&")))

  def andor(self):
    nodes, ops = [self.pipeline()], []
    while self.peek() in (("op", "&&"), ("op", "||")):
      ops.append(self.take()[1])
      self.skipnl()
      nodes.append(self.pipeline())
    return Node("andor", nodes=nodes, ops=ops) if ops else nodes[0]

  def pipeline(self):
    neg = False
    while self.kw(self.peek(), ("!",)):
      self.take()
      neg = not neg
    cmds = [self.command()]
    while self.peek() in (("op", "|"), ("op", "|&")):
      self.take()
      self.skipnl()
      cmds.append(self.command())
    return Node("pipe", cmds=cmds, neg=neg) if len(cmds) > 1 or neg else cmds[0]

  def command(self):
    self.nest += 1
    if self.nest > MAX_NEST: raise Unsure("commands are nested too deeply")
    t, node = self.peek(), None
    w = self.kw(t, ("{", "for", "case", "select", "function", "coproc") + tuple(_BLOCKS))
    if t == ("op", "("):
      self.take()
      if self.s.startswith("(", self.i):  # '((': arithmetic, or else nested subshells
        save = self.i
        try:
          self.i += 1
          node = Node("arith", parts=self._arith())
        except Unsure:
          self.i, self.tok = save, None
      if node is None:
        node = Node("sub", body=self.plist((")",)))
        if self.take() != ("op", ")"): raise Unsure("a ( ... ) group is not closed")
    elif w:
      node = self.compound(w)
    elif t[0] in ("w", "io") or t[0] == "op" and t[1] in _REDIR:
      node = self.simple()
    else:
      raise Unsure("unexpected syntax")
    while node.kind != "simple" and (self.peek()[0] == "io" or self.peek()[0] == "op" and self.peek()[1] in _REDIR):
      node.redirs.append(self.redir())
    self.nest -= 1
    return node

  def compound(self, w):
    self.take()
    if w in ("case", "select", "function", "coproc"): raise Unsure("'%s' is not analyzed" % w)
    if w in _BLOCKS:  # if/while/until: the parts between their keywords
      segs = []
      while True:
        segs.append(self.plist(_BLOCKS[w]))
        if self.expect(*_BLOCKS[w]) == _BLOCKS[w][-1]: return Node("block", segs=segs, loop=w != "if")
    if w == "{":
      body = self.plist(("}",))
      self.expect("}")
      return Node("group", body=body)
    var, words, arith = None, None, []
    if self.peek() == ("op", "(") and self.s.startswith("(", self.i):  # for ((...))
      self.take()
      self.i += 1
      arith = self._arith()
    else:
      t = self.take()
      var = _lit(t[1]) if t[0] == "w" else None
      if not var or not re.match(_NAME + "$", var): raise Unsure("unexpected syntax")
      self.skipnl()
      if self.kw(self.peek(), ("in",)):
        self.take()
        words = []
        while self.peek()[0] == "w": words.append(self.take()[1])
    if self.peek() == ("op", ";"): self.take()
    self.skipnl()
    self.expect("do")
    body = self.plist(("done",))
    self.expect("done")
    return Node("for", var=var, words=words, arith=arith, body=body)

  def simple(self):
    assigns, words, awords, redirs = [], [], set(), []
    while True:
      t = self.peek()
      if t[0] == "io" or t[0] == "op" and t[1] in _REDIR:
        redirs.append(self.redir())
        continue
      if t[0] != "w": break
      self.take()
      p = t[1][0] if t[1] else ("",)
      m = None if words and _lit(words[0]) not in _DECL or p[0] != "lit" or p[2] else \
          re.match(r"(%s)(\+?)=" % _NAME, p[1])
      if m and not words:
        value = ([("lit", p[1][m.end():], False)] if p[1][m.end():] else []) + t[1][1:]
        if not value and self.s.startswith("(", self.i): raise Unsure("arrays are not analyzed")
        assigns.append((m.group(1), value, bool(m.group(2))))
        continue
      if m: awords.add(len(words))  # NAME=value argument of a declaration builtin
      words.append(t[1])
      if len(words) == 1 and self.peek() == ("op", "("): raise Unsure("functions are not analyzed")
    if not (assigns or words or redirs): raise Unsure("unexpected syntax")
    node = Node("simple", assigns=assigns, words=words, awords=awords)
    node.redirs = redirs
    return node

  def redir(self):
    t = self.take()
    if t[0] == "io": t = self.take()  # the fd number does not matter here
    w = self.take()
    if t[0] != "op" or t[1] not in _REDIR or w[0] != "w": raise Unsure("bad redirection")
    r = Node("redir", op=t[1], target=w[1], body="", parts=None)
    if t[1] in ("<<", "<<-"):
      r.quoted, r.strip = any(p[0] == "lit" and p[2] for p in w[1]), t[1] == "<<-"
      r.delim = "".join(p[1] if p[0] == "lit" else "$" + str(p[1] or "") for p in w[1])
      self.pending.append(r)
    return r

# ---------- fields and values ----------
# A field (one argument after expansion) and a variable value are tuples of segments (kind, text):
#   Q quoted literal   G unquoted literal (glob active; splits on blanks)   E unknown text that may be empty
#   N unknown non-empty text   P items listed by an earlier command (text = index into ctx.listings)
# A variable holds a tuple of alternative values; () is the empty string.
def lit_field(text):
  return (("Q", text),)

def ftext(f):  # literal text of a field, or None if part of it is unknown
  return None if any(k not in "QG" for k, _ in f) else "".join(t for _, t in f)

def fopaque(f):
  return "".join(t if k in "QG" else OPAQUE for k, t in f)

def fscript(f):  # a field as shell code to re-parse; unknown parts become internal variables (see lookup)
  return "".join(t if k in "QG" else "${__DB_%s%s}" % (k, t) for k, t in f)

def fprefix(f):
  return fopaque(f).split(OPAQUE)[0]

def fdrop(f, n):  # the field without its first n literal characters (None if they are not literal)
  out = list(f)
  while n and out:
    k, t = out[0]
    if k not in "QG": return None
    if len(t) > n: out[0], n = (k, t[n:]), 0
    else: n, _ = n - len(t), out.pop(0)
  return None if n else tuple(out)

def to_value(f, literal=False):
  return tuple(("Q" if literal and k == "G" else k, t) for k, t in f)

def from_value(v, dq):
  return v if dq else tuple(("G" if k == "Q" else k, t) for k, t in v)

def _maybe_empty(v):
  return not any(k in "NP" or k in "QG" and t for k, t in v)

def _merge(segs):
  out = []
  for k, t in segs:
    if k in "QG" and not t: continue
    if out and out[-1][0] == k and k in "QGEN": out[-1] = (k, out[-1][1] + t)
    else: out.append((k, t))
  return tuple(out)

def _split(f, kinds="G"):  # split on blanks inside `kinds` segments ("QG": how xargs and read see a line)
  out = [[]]
  for k, t in f:
    if k not in kinds:
      out[-1].append((k, t))
      continue
    for j, piece in enumerate(re.split(r"[ \t\n]+", t)):
      if j: out.append([])
      if piece: out[-1].append((k if kinds == "G" else "Q", piece))
  return [tuple(x) for x in out if x]

def _union(a, b, unknown):
  out = list(dict.fromkeys(tuple(a) + tuple(b)))
  return tuple(out if len(out) <= MAX_ALTS else out[:MAX_ALTS - 1] + [unknown])

# ---------- word expansion ----------
def environ_get(name):
  try: return os.environ.get(name)
  except Exception: return None

def lookup(name, st):
  """Value alternatives of a variable, or None if unknown."""
  if name.startswith("__DB_"): return [((name[5], name[6:]),)]
  if name.isdigit() or name in ("@", "*"):
    if st.pos is None: return [N_VALUE] if name == "0" else None
    if not name.isdigit(): return list(st.pos[1:]) or [()]
    return [st.pos[int(name)] if int(name) < len(st.pos) else N_VALUE if name == "0" else ()]
  if name in "#?$!-" or name in ("RANDOM", "UID", "EUID", "PPID", "LINENO", "BASHPID", "SECONDS"): return [N_VALUE]
  if name in st.vars: return list(st.vars[name])
  dirs = st.cwds if name == "PWD" else st.oldpwd if name == "OLDPWD" else None
  if dirs: return [lit_field(c) if c != UNKNOWN_DIR else N_VALUE for c in dirs]
  if name == "HOME": return [lit_field(OS_HOME)]
  v = environ_get(name)
  return None if v is None else [lit_field(v.replace(OPAQUE, ""))]

def _tilde(parts, st, assign):  # ~, ~/x, ~+, ~-, ~user at the start of a word (in assignments after NAME=)
  p = parts[0] if parts else ("",)
  m = p[0] == "lit" and not p[2] and re.match(r"((?:%s\+?=)?)~([^/:]*)" % _NAME if assign else r"()~([^/]*)", p[1])
  if not m or m.end() == len(p[1]) and len(parts) > 1: return parts
  user = m.group(2)
  if user == "":
    paths = [ftext(v) for v in st.vars["HOME"]] if "HOME" in st.vars else [OS_HOME]
  elif user in ("+", "-"):
    paths = list(st.cwds if user == "+" else st.oldpwd or [None])
  elif re.match(r"[A-Za-z0-9._][A-Za-z0-9._-]*$", user):
    paths = [_norm(os_user_home(user))]
    protect("d", paths[0], "the home folder of " + user)
  else:
    return parts
  return [("lit", m.group(1), True), ("tilde", paths), ("lit", p[1][m.end():], False)] + parts[1:]

def _capture(node, st, ctx):
  """Analyze `node` in a subshell; return what its last simple command produced."""
  ctx.produced = None
  _nested(ctx, run, node, st.copy(stdin=None), ctx)
  prod, ctx.produced = ctx.produced, None
  return prod

def _run_subs(parts, st, ctx):  # the command substitutions found inside arithmetic
  for p in parts:
    if p[0] == "cmd": _capture(p[1], st, ctx)
    else: _run_subs(p[1], st, ctx)

def _trim(t, pat, op):
  for k in (range(len(t) + 1) if op in ("#", "%%") else range(len(t), -1, -1)):
    if op[0] == "#" and fnmatch.fnmatchcase(t[:k], pat): return t[k:]
    if op[0] == "%" and fnmatch.fnmatchcase(t[k:], pat): return t[:k]
  return t

def _var(p, st, ctx):
  _, name, op, arg, dq = p
  vals = (lookup(name, st) or None) if name else None
  dflt = [to_value(f) for f in _expand_parts(arg, st, ctx, tilde=not dq)] if arg else [()]
  if op is None:
    res = vals or [E_VALUE]
  elif op in (":-", "-", ":=", "="):
    res = dflt if vals is None else [x for v in vals for x in ([v] if v else []) + (dflt if _maybe_empty(v) else [])]
    if op[-1] == "=": st.vars[name] = tuple(res[:MAX_ALTS])
  elif op in (":?", "?"):
    res = [tuple(("N", "") if k == "E" else (k, t) for k, t in v) or N_VALUE for v in vals or [()]]
  elif op in (":+", "+"):
    res = [x for v in vals or [E_VALUE] for x in ([()] if _maybe_empty(v) else []) + (dflt if v else [])]
  else:  # # ## % %%: trimming a known value with a literal pattern
    pat, res = _lit(arg or []), []
    for v in vals or [E_VALUE]:
      t = ftext(v)
      ctx.tick(len(t or ""))
      res.append(E_VALUE if t is None or pat is None or len(t) > 4096 else lit_field(_trim(t, pat, op)))
  return [from_value(v, dq) for v in res[:MAX_ALTS]] or [()]

def _alts(p, st, ctx):
  k = p[0]
  if k == "lit": return [(("Q" if p[2] else "G", p[1]),)]
  if k == "tilde": return [lit_field(x) if x and x != UNKNOWN_DIR else N_VALUE for x in p[1]]
  if k == "var": return _var(p, st, ctx)
  if k == "arith":
    _run_subs(p[1], st, ctx)
    return [N_VALUE]
  prod = _capture(p[1], st, ctx)
  if k == "proc":
    ctx.proc = prod
    return [N_VALUE]
  if prod and prod.value is not None: return [from_value(v, p[2]) for v in prod.value[:MAX_ALTS]] or [()]
  return [(("P", ctx.listing(prod.items)),)] if prod and prod.items is not None else [E_VALUE]

def _expand_parts(parts, st, ctx, assign=False, tilde=True):  # brace-free parts -> alternative fields (unsplit)
  combos = [()]
  for p in (_tilde(parts, st, assign) if tilde else parts):
    alts = _alts(p, st, ctx)
    combos = [c + a for c in combos for a in alts]
    if len(combos) > MAX_ALTS:
      ctx.doubt("a word has too many possible values")
      combos = combos[:MAX_ALTS]
    ctx.tick(len(combos))
  return [_merge(c) for c in combos]

def _brace(s, ctx, depth=0):
  """Brace expansion of a string ({a,b}, {1..5}); Unsure above MAX_BRACE results."""
  if depth > 32: raise Unsure("a brace expansion is too large")
  out, start, i = [""], 0, s.find("{")
  while i >= 0:
    level, commas, close = 0, [], None
    for j in range(i, len(s)):
      level += (s[j] == "{") - (s[j] == "}")
      if not level:
        close = j
        break
      if s[j] == "," and level == 1: commas.append(j)
    ctx.tick(1 + (close or len(s)) - i)
    if close is None: break
    if commas: alts = [x for a, c in zip([i] + commas, commas + [close]) for x in _brace(s[a + 1:c], ctx, depth + 1)]
    else: alts = _sequence(s[i + 1:close])
    if alts is not None:
      if len(out) * len(alts) > MAX_BRACE or len(out) * len(alts) * len(s) > 4000000:
        raise Unsure("a brace expansion is too large")
      out, start = [r + s[start:i] + a for r in out for a in alts], close + 1
    i = s.find("{", close + 1 if alts is not None else i + 1)
  return [r + s[start:] for r in out]

def _sequence(inner):  # {1..5}, {a..e}, {1..10..2}
  m = re.match(r"(-?[0-9]{1,18}|[A-Za-z])\.\.(-?[0-9]{1,18}|[A-Za-z])(?:\.\.(-?[0-9]{1,18}))?$", inner)
  if not m or m.group(1).isalpha() != m.group(2).isalpha(): return None
  a, b = [ord(x) if x.isalpha() else int(x) for x in m.group(1, 2)]
  step = abs(int(m.group(3) or 1)) or 1
  if abs(b - a) // step >= MAX_BRACE: raise Unsure("a brace expansion is too large")
  return [chr(x) if m.group(1).isalpha() else str(x) for x in range(a, b + (1 if b >= a else -1),
                                                                     step if b >= a else -step)]

def _braces(word, ctx):  # unquoted literal text is brace-expanded; other parts ride along as placeholders
  if len(word) > 6000 or not any(p[0] == "lit" and not p[2] and "{" in p[1] for p in word): return [word]
  text = "".join(p[1] if p[0] == "lit" and not p[2] else chr(0xE000 + k) for k, p in enumerate(word))
  return [[word[ord(x) - 0xE000] if len(x) == 1 and "\ue000" <= x <= "\uf8ff" else ("lit", x, False)
           for x in re.split("([\ue000-\uf8ff])", r) if x] for r in _brace(text, ctx)]

def expand_alts(word, st, ctx, split=True, assign=False):
  """Alternatives (variables may have several values), each the list of fields the word expands to."""
  try:
    variants = [word] if assign else _braces(word, ctx)
  except Unsure as u:
    ctx.doubt(u.args[0])
    variants = [word]
  if len(variants) == 1: alts = [[f] for f in _expand_parts(variants[0], st, ctx, assign)]
  else: alts = [[f for v in variants for f in _expand_parts(v, st, ctx)]]
  keep = any(p[0] == "lit" and p[2] or p[0] in ("var", "cmd", "arith") and p[-1] for p in word)
  return [[x for f in fields for x in ((_split(f) if split else [f]) if f else [f] if keep else [])] for fields in alts]

def expand(word, st, ctx, split=True, assign=False):
  return [f for alt in expand_alts(word, st, ctx, split, assign) for f in alt]

# ---------- protected locations ----------
_PROT = []      # ([(component, is_pattern)], display, kind); components case-folded where paths ignore case
_NAMES = set()  # basenames of protected folders (unknown-cwd rule)

def _key(s):
  return s.lower() if OS_CASE_INSENSITIVE else s

def _norm(p):
  p = posixpath.normpath(p or "/")
  return "/" + p.lstrip("/") if p.startswith("//") else p

def _pretty(p):
  return "~" + p[len(OS_HOME):] if OS_HOME != "/" and (p + "/").startswith(OS_HOME + "/") else p

def _magic(s):
  return re.search(r"[*?[]", s) is not None

def protect(kind, path, disp=None):  # register a protected location (all its forms, unless it is a pattern)
  for form in [path] if _magic(path) else os_forms(path):
    comps = [(c, _magic(c)) for c in _key(form).split("/") if c]
    _PROT.append((comps, disp or _pretty(path), kind))
    if kind != "f" and comps and not comps[-1][1]: _NAMES.add(comps[-1][0])

def _cmatch(c, e):  # can path component c = (literal, pattern, magic), case-folded, name protected component e?
  if OPAQUE in c[0]: return e[1]
  if c[2]: return e[1] or fnmatch.fnmatchcase(e[0], c[1])
  return fnmatch.fnmatchcase(c[0], e[0]) if e[1] else c[0] == e[0]

def protected(comps, files=False):
  """Protected location that deleting `comps` destroys (files=True: files too; "only": just files), or None."""
  comps, n = [(_key(a), _key(b), m) for a, b, m in comps], len(comps)
  for ents, disp, kind in _PROT:
    m = len(ents)
    if files == "only" and (kind != "f" or n != m) or n > m and kind != "t" or n == m and kind == "f" and not files:
      continue
    if all(_cmatch(c, e) for c, e in zip(comps, ents)): return disp
  return None

def _esc(text):  # glob-escape
  return re.sub(r"([*?[])", r"[\1]", text)

def _scomps(path):
  return [(c, _esc(c), False) for c in path.split("/") if c]

def _join(names):
  return "/" + "/".join(names)

def _hit(path, files=False):
  for form in os_forms(path):
    h = protected(_scomps(form), files)
    if h: return h
  return None

for _kind, _path in OS_PROTECTED: protect(_kind, _path)
try: protect("f", os.path.realpath(__file__), "this safety hook")
except Exception: pass

# ---------- path checks ----------
def _variants(field):
  """Readings as path characters [(char, glob_active)]: E parts once empty (the "$UNSET/*" accident), once unknown."""
  out = []
  for empty in (True, False) if any(k == "E" for k, _ in field) else (False,):
    out += os_path_chars([x for k, t in field for x in ([(c, k == "G") for c in t] if k in "QG" else
                                                        [] if empty and k == "E" else [(OPAQUE, False)])])
  return out

def _comps(chars):  # -> (absolute, [(literal, glob pattern, has magic)])
  out, cur = [], []
  for c in chars + [("/", False)]:
    if c[0] != "/":
      cur.append(c)
      continue
    if cur:
      pat = "".join(ch if g else _esc(ch) for ch, g in cur)
      out.append(("".join(ch for ch, _ in cur), pat, any(g and ch in "*?[" for ch, g in cur)))
    cur = []
  return bool(chars) and chars[0][0] == "/", out

def _normalize(comps, absolute=True):
  out = []
  for c in comps:
    if c[0] == ".." and out and out[-1][0] != "..":
      if OPAQUE in out[-1][0]: return None
      out.pop()
    elif c[0] != "." and (c[0] != ".." or not absolute):
      out.append(c)
  return out

def _paths(field, st, verb=None):
  """(components, raw path) of each reading in each cwd; unknown cwd: the unknown-cwd rule (deletions only)."""
  for chars in _variants(field):
    absolute, comps = _comps(chars)
    raw = "".join(c for c, _ in chars)
    for base in ([""] if absolute else st.cwds) if chars else ():  # an empty operand names nothing
      if base == UNKNOWN_DIR:
        if verb: _unknown_cwd(comps, verb)
        continue
      full = _normalize(([] if absolute else _scomps(base)) + comps)
      if full is not None: yield full, raw if absolute else base + "/" + raw  # None: '..' after unknown text

def _whole_dir(name):  # a last component like *, .*, *.*, ?*, [!.]* that matches (nearly) everything
  s = re.sub(r"\[[^\]]*\]", "?", name)
  return "*" in s and all(ch in "*?." for ch in s)

def _matches(pattern, ctx):
  """Filesystem matches of an absolute glob (never recursive; '**' acts like '*'), bounded by MAX_GLOB."""
  comps = [c for c in pattern.split("/") if c]

  def walk(base, i):
    c, last = comps[i], i == len(comps) - 1
    try: ents = [(e.name, e) for e in os.scandir(base or "/")] if _magic(c) else [(re.sub(r"\[(.)\]", r"\1", c), 0)]
    except OSError: return
    for name, e in ents:
      ctx.tick()
      p = base + "/" + name
      if e and (p in OS_SLOW_ROOTS or name[0] == "." and c[0] != "." or not fnmatch.fnmatchcase(name, c)):
        continue
      try: ok = (e or os.path.lexists(p)) if last else e.is_dir() if e else os.path.isdir(p)
      except OSError: ok = False
      if ok: yield from [p] if last else walk(p, i + 1)
  try:
    for k, m in enumerate(walk("", 0)):
      if k >= MAX_GLOB: return ctx.doubt("a wildcard matches too many files")
      yield m
  except (OSError, ValueError, UnicodeError, RecursionError, IndexError):
    return

def _deny(verb, target, hit, whole=False):
  raise Deny("Blocked: %s would delete %s%s, which is protected (%s). Delete specific files or project "
             "subfolders instead, or %s." % (verb, "everything in " if whole else "", target, hit, OS_TRASH_HINT))

def _unknown_cwd(comps, verb):  # relative target, unknown cwd: deny '.', '..', whole-folder globs, protected names
  norm = _normalize(comps, False)
  if norm is None: return
  first = norm[0] if norm else None
  if all(c[0] == ".." for c in norm) or norm[-1][2] and _whole_dir(norm[-1][0]) and \
          all(c[0] == ".." for c in norm[:-1]) or first[0] != ".." and OPAQUE not in first[0] and \
          (any(fnmatch.fnmatchcase(n, _key(first[1])) for n in _NAMES) if first[2] else _key(first[0]) in _NAMES):
    raise Deny("Blocked: %s %s runs in an unknown working directory and could hit a protected folder. Use an "
               "absolute path, or %s." % (verb, "/".join(c[0] for c in comps).replace(OPAQUE, "?"), OS_TRASH_HINT))

def check_target(field, st, ctx, verb, files=False):
  """Deny if deleting what `field` names (recursively) destroys a protected location (files=True: also files)."""
  ctx.tick()
  if field and field[0][0] == "P" and all(k in "QG" and not t.strip("/") for k, t in field[1:]):
    for f, s in ctx.listings[int(field[0][1])] or []:  # None: unknowable producer (documented limitation)
      check_target(f, s, ctx, verb + " (on items listed by an earlier command)", files)
    return
  for full, raw in _paths(field, st, verb):
    whole = full and full[-1][2] and _whole_dir(full[-1][0])
    for cs, w in ((full[:-1], True), (full, False)) if whole else ((full, False),):
      path, f = _join(c[0] for c in cs), files and not w
      hit = protected(cs, f) if any(c[2] or OPAQUE in c[0] for c in cs) else _hit(path if w else raw, f)
      if hit: _deny(verb, _pretty(path).replace(OPAQUE, "?"), hit, w)
      for m in _matches(_join(c[1] for c in cs), ctx) if any(c[2] for c in cs) else ():
        hit = _hit(m, f)
        if hit: _deny(verb, _pretty(m), hit, w)

def check_write(field, st, ctx, tool, truncate):
  """Deny writing raw data to a disk device, or truncating a protected file."""
  for full, raw in _paths(field, st):
    if OPAQUE in raw: continue
    pat = _join(c[1] for c in full)
    if any(c[2] for c in full):  # a wildcard target: decided from the pattern alone
      hit = truncate and protected(full, "only")
      dev = next((d for d in OS_DEVICE_SAMPLES if d.count("/") == pat.count("/") and fnmatch.fnmatchcase(d, pat)), 0)
    else:
      hit = truncate and _hit(raw, "only")
      dev = any(OS_DEVICE_RE.match(f) for f in os_forms(raw)) and raw
    if hit: raise Deny("Blocked: %s would overwrite %s. Edit that file deliberately instead." % (tool, hit))
    if dev: raise Deny("Blocked: %s would write raw data to the disk device %s, destroying what is on it. %s"
                       % (tool, dev, OS_DISK_HINT))

# ---------- shell state and execution ----------
class State:
  """cwds/$OLDPWD (possible values), pushd stack, vars (value alternatives), exports, $0.. (None = unknown)."""
  __slots__ = ("cwds", "oldpwd", "stack", "vars", "exported", "pos", "errexit", "stdin")

  def __init__(self, cwds):
    self.cwds, self.oldpwd, self.stack, self.vars, self.exported = cwds, None, (), {}, set()
    self.pos, self.errexit, self.stdin = None, False, None

  def copy(self, **kw):
    s = State(self.cwds)
    s.oldpwd, s.stack, s.vars, s.exported = self.oldpwd, self.stack, dict(self.vars), set(self.exported)
    s.pos, s.errexit, s.stdin = self.pos, self.errexit, self.stdin
    for k, v in kw.items(): setattr(s, k, v)
    return s

def initial_state(cwd):
  rd = os_path_chars([(c, False) for c in cwd]) if isinstance(cwd, str) and cwd and OPAQUE not in cwd else []
  p = "".join(c for c, _ in rd[0]) if rd else ""
  if not p.startswith("/"):
    try: p = os.getcwd()
    except Exception: p = ""
  st = State((_norm(p),) if p.startswith("/") else (UNKNOWN_DIR,))
  old = environ_get("OLDPWD") or ""
  st.oldpwd = (_norm(old),) if old.startswith("/") else None
  return st

def merge(*states):
  """Union of possible states (None = that outcome cannot happen)."""
  live = []
  for s in states:
    if s is not None and all(s is not x for x in live): live.append(s)
  if len(live) < 2: return live[0] if live else None
  out = live[0].copy()
  for s in live[1:]:
    out.cwds = _union(out.cwds, s.cwds, UNKNOWN_DIR)
    out.oldpwd = out.oldpwd and s.oldpwd and _union(out.oldpwd, s.oldpwd, UNKNOWN_DIR)
    out.stack = max(out.stack, s.stack, key=len)
    for k in set(out.vars) | set(s.vars):
      a, b = out.vars.get(k), s.vars.get(k)
      if a != b: out.vars[k] = _union(a or lookup(k, out) or [E_VALUE], b or lookup(k, s) or [E_VALUE], E_VALUE)
    out.exported |= s.exported
    out.pos = out.pos if out.pos == s.pos else None
    out.errexit = out.errexit and s.errexit
  return out

def _restdin(s, stdin):
  return s if s is None or s.stdin is stdin else s.copy(stdin=stdin)

def run(node, st, ctx):
  """Analyze `node` from `st`: (state on success, state on failure), None where impossible (after exit)."""
  if st is None: return None, None
  ctx.tick()
  stdin = _redirs(node.redirs, st, ctx) if node.redirs and node.kind != "simple" else None
  if stdin is None: return _run(node, st, ctx)
  s, f = _run(node, st.copy(stdin=stdin), ctx)
  return _restdin(s, st.stdin), _restdin(f, st.stdin)

def _run(node, st, ctx):
  k = node.kind
  if k == "simple": return run_simple(node, st, ctx)
  if k == "list":
    cur, last = st, (st, st)
    for item, bg in node.items:
      if cur is None: break
      s, f = run(item, cur, ctx)
      if bg:  # a background job runs in a subshell
        last = (cur, cur)
        continue
      x = s or f
      cur, last = (None if x is None else s if x.errexit else merge(s, f)), (s, f)
    return last
  if k == "andor":
    s, f = run(node.nodes[0], st, ctx)
    for op, part in zip(node.ops, node.nodes[1:]):
      if op == "&&":
        s, f2 = run(part, s, ctx)
        f = merge(f, f2)
      else:
        s2, f = run(part, f, ctx)
        s = merge(s, s2)
    return s, f
  if k == "pipe":
    prod, last = st.stdin, (st, st)
    for cmd in node.cmds:
      ctx.produced = None
      last = run(cmd, st.copy(stdin=prod), ctx)
      prod = ctx.produced
    ctx.produced = prod
    s, f = [_restdin(merge(st, x), st.stdin) for x in last]  # bash: subshells; zsh: last stage in this shell
    return (f, s) if node.neg else (s, f)
  if k == "sub":
    run(node.body, st.copy(), ctx)
    return st, st
  if k == "group": return run(node.body, st, ctx)
  if k == "block": return _block(node.segs, st, ctx, node.loop)
  if k == "for":
    _run_subs(node.arith, st, ctx)
    if not node.var: return _block([node.body], st, ctx, True)
    if node.words is None: vals = list(st.pos[1:]) if st.pos else [E_VALUE]
    else: vals = list(dict.fromkeys(to_value(f) for w in node.words for f in expand(w, st, ctx)))
    if len(vals) > MAX_BRACE: ctx.doubt("a loop has too many values")
    out = merge(st, *[_block([node.body], st.copy(vars=dict(st.vars, **{node.var: tuple(vals[j:j + MAX_ALTS])})),
                             ctx, True)[0] for j in range(0, min(len(vals), MAX_BRACE), MAX_ALTS)])
    return out, out
  _run_subs(node.parts, st, ctx)  # arith
  return st, st

def _block(segs, st, ctx, loop):
  """if/while/until/for: each part may run or not after the ones before (loops: twice if the state changes)."""
  cur = st
  for _ in range(1 + loop):
    prev = cur
    for seg in segs: cur = merge(cur, *run(seg, cur, ctx))
    if cur.cwds == prev.cwds and cur.vars == prev.vars: break
  return cur, cur

def _text_produced(fields, st):
  return Produced("".join(fscript(f) for f in fields), [(w, st) for f in fields for w in _split(f, "QG")],
                  [to_value(f, True) for f in fields[:1]])

def _redirs(redirs, st, ctx):
  """Check redirection targets; return the Produced that feeds stdin (None = inherited)."""
  stdin = None
  for r in redirs:
    ctx.tick()
    if r.op in ("<<", "<<-"):
      fields = [lit_field(r.body)] if r.parts is None else _expand_parts(r.parts, st, ctx, tilde=False) or [()]
      stdin = _text_produced(fields, st)
      continue
    ctx.proc = None
    fields = expand(r.target, st, ctx, split=False)
    if r.op == "<<<": stdin = _text_produced([f + lit_field("\n") for f in fields or [()]], st)
    elif r.op == "<": stdin = ctx.proc if r.target[0][0] == "proc" and ctx.proc else Produced()
    elif r.op != "<&" and not (r.op == ">&" and all(re.match(r"[0-9]+$|-$", ftext(f) or "") for f in fields)):
      for f in fields:
        hit = _tamper_hit(f, st)
        if hit: _tamper_deny("the redirection " + r.op, hit)
        check_write(f, st, ctx, "the redirection " + r.op, r.op in (">", ">|", "&>", ">&"))
  return stdin

def run_simple(node, st, ctx):
  st, env = st.copy(), {}
  for name, value, append in node.assigns:
    vals = tuple(to_value(f, True) for f in _expand_parts(value, st, ctx, assign=True)) or ((),)
    env[name] = tuple(p + v for p in lookup(name, st) or [()] for v in vals)[:MAX_ALTS] if append else vals
  stdin = _redirs(node.redirs, st, ctx)
  if not node.words:
    ctx.produced = None
    st.vars.update(env)
    return st, st
  first = expand_alts(node.words[0], st, ctx)
  rest = [f for k, w in enumerate(node.words[1:], 1)
          for f in expand(w, st, ctx, k not in node.awords, k in node.awords)]
  if len(first) > 8: ctx.doubt("a command name has too many possible values")
  ctx.produced = None
  res = [dispatch(list(f) + rest, st, ctx, env, stdin or st.stdin) for f in first[:8]]
  return merge(*[r[0] for r in res]), merge(*[r[1] for r in res])

def analyze_text(text, st, ctx):  # shell code found inside the command (bash -c, eval, heredoc, ...)
  return _nested(ctx, lambda: run(Parser(text, ctx).parse(), st, ctx))

def _child(st, env, pos=None, errexit=False):  # a child shell: exported variables only, fresh positional values
  c = st.copy(stack=(), pos=pos, errexit=errexit, stdin=None)
  c.vars = {k: v for k, v in st.vars.items() if k in st.exported or environ_get(k) is not None}
  c.vars.update(env)
  c.exported = set(c.vars)
  return c

def _with_cwd(st, field, ctx):
  return st.copy(cwds=_resolve_dirs(field, st, ctx) if field is not None else (UNKNOWN_DIR,))

def _resolve_dirs(field, st, ctx):
  """Possible directories after `cd field` ('..' resolved lexically, like cd -L)."""
  out = list(st.cwds) if _maybe_empty(field) else []  # cd "" stays put
  out += [UNKNOWN_DIR] if ftext(field) is None or UNKNOWN_DIR in st.cwds else []
  if fprefix(field)[:1] not in ("", ".", "/"):  # cd NAME also searches $CDPATH
    st = st.copy(cwds=st.cwds + tuple(_norm(d) for v in lookup("CDPATH", st) or []
                                      for d in (ftext(v) or "").split(":") if d[:1] == "/"))
  for full, _ in _paths(field, st):
    if any(c[2] for c in full) and not any(OPAQUE in c[0] for c in full):
      out += [_norm(m) for m, _ in zip(_matches(_join(c[1] for c in full), ctx), range(8))] + [UNKNOWN_DIR]
    elif not any(OPAQUE in c[0] for c in full):
      out.append(_join(c[0] for c in full))
  return _union((), out, UNKNOWN_DIR) or (UNKNOWN_DIR,)

# ---------- dispatch and builtins ----------
def dispatch(argv, st, ctx, env, stdin):
  """Analyze one simple command given as expanded fields; returns (success, failure) states."""
  ctx.tick()
  if not argv: return st, st
  word = ftext(argv[0])
  if word is None:  # an unknown command name; if it may be empty ($SUDO rm ...) the rest may run
    return dispatch(argv[1:], st, ctx, env, stdin) if all(k == "E" for k, _ in argv[0]) else (st, st)
  name = os_command_name(word)
  _tamper(name, argv[1:], st, ctx)
  h = _HANDLERS.get(name) or (_h_wrapper if name in _WRAPPERS else _h_shell if name in _SHELLS else _h_other)
  return h(name, argv[1:], st, ctx, env, stdin) or (st, st)

def _h_other(name, args, st, ctx, env, stdin):
  reason = os_tool_reason(name, [fopaque(a) for a in args], stdin.text if stdin else None)
  if reason: raise Deny(reason)
  ctx.produced = _produce(name, args, st, ctx, stdin)

def _operands(args, valopts=""):  # GNU-style: '--' ends options; options may follow operands
  out, i, done = [], 0, False
  while i < len(args):
    t = ftext(args[i])
    if not done and t and t[0] == "-" and len(t) > 1:
      done = t == "--"
      i += 1 + (t in valopts.split())
      continue
    out.append(args[i])
    i += 1
  return out

def _printf(fmt, args):
  fmt = re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), fmt)
  specs, out, k = re.split(r"(%[-+ #0]*[0-9]*(?:\.[0-9]+)?[a-zA-Z%])", fmt), [], 0
  while True:
    for j, piece in enumerate(specs):
      out.append(piece if j % 2 == 0 else "%" if piece == "%%" else args[k] if k < len(args) else "")
      k += j % 2 == 1 and piece != "%%"
    if k >= len(args) or all(s == "%%" for s in specs[1::2]): return "".join(out)

_FILTERS = frozenset("grep egrep fgrep rg sort uniq head tail sed awk cut tr tac nl fold column paste rev shuf fmt "
                     "strings iconv".split())

def _produce(name, args, st, ctx, stdin):
  """What a command writes to stdout (pipes into xargs/shells, $(...)), or None if unknown."""
  if name == "echo":
    while args and re.match(r"-[neE]+$", ftext(args[0]) or ""): args = args[1:]
    val = tuple(s for k, f in enumerate(args) for s in ((("Q", " "),) if k else ()) + f)
    return Produced(" ".join(fscript(f) for f in args) + "\n", [(f, st) for f in args], [val])
  if name == "printf" and args:
    if ftext(args[0]) == "-v": return ctx.doubt("printf -v is not analyzed")
    fmt, rest = ftext(args[0]), args[1:]
    if fmt is None: return Produced(None, [(f, st) for f in rest] or None)
    text, lits = _printf(fmt, [fscript(f) for f in rest]), [ftext(f) for f in rest]
    items = [(f, st) for f in rest] or [(lit_field(w), st) for w in text.split()]
    return Produced(text, items, None if None in lits else [lit_field(_printf(fmt, lits))])
  if name == "cat": return stdin if all(ftext(a) == "-" for a in _operands(args)) else None
  if name in _FILTERS: return stdin and Produced(None, stdin.items)
  if name in ("ls", "fd"):  # fd: its first operand is a pattern; listing "." too is conservative
    ops = _operands(args)
    return Produced(None, [(f, st) for f in ops if name == "ls"] or [(f, st) for f in ops + [lit_field(".")]])
  if name == "pwd":
    return Produced(None, [(lit_field(c), st) for c in st.cwds if c != UNKNOWN_DIR] or None,
                    [lit_field(c) if c != UNKNOWN_DIR else N_VALUE for c in st.cwds])
  ops = _operands(args)
  if name in ("realpath", "readlink") and ops and (name == "realpath" or
                                                   any(re.match(r"-\w*[fem]", ftext(a) or "") for a in args)):
    t = ftext(ops[0])
    return Produced(None, [(f, st) for f in ops], [E_VALUE] if t is None else [
        lit_field(_norm(c + "/" + t)) if c != UNKNOWN_DIR else N_VALUE for c in ([""] if t[:1] == "/" else st.cwds)])
  return None

def _h_cd(name, args, st, ctx, env, stdin):
  i = 0
  while i < len(args) and re.match(r"-[A-Za-z@]+$|--$", ftext(args[i]) or ""):
    i += 1
    if ftext(args[i - 1]) == "--": break
  ops, s = args[i:] or (lookup("HOME", st) or [N_VALUE])[:1] * (name == "cd"), st.copy(oldpwd=st.cwds)
  if name != "cd" and (not ops and name == "pushd" or ops and re.match(r"[+-][0-9]+$", ftext(ops[0]) or "")):
    return ctx.doubt("pushd/popd stack rotation is not analyzed")
  if name == "popd":
    if not st.stack: return st, st
    s.cwds, s.stack = st.stack[0], st.stack[1:]
  elif name == "pushd": s.cwds, s.stack = _resolve_dirs(ops[0], st, ctx), (st.cwds,) + st.stack
  elif ftext(ops[0]) == "-": s.cwds = st.oldpwd or (UNKNOWN_DIR,)
  else: s.cwds = _resolve_dirs(ops[0], st, ctx)  # no operand: $HOME
  return s, st

def _h_decl(name, args, st, ctx, env, stdin):
  s, new = st.copy(), {}
  export = name == "export" or any(re.match(r"-\w*x", ftext(a) or "") for a in args)
  for a in args:
    m = re.match(r"(%s)(\+?=)?" % _NAME, fprefix(a))
    if m and export: s.exported.add(m.group(1))
    if m and m.group(2):
      rest = fdrop(a, m.end())
      new.setdefault(m.group(1), []).append(E_VALUE if rest is None else to_value(rest, True))
  for k, v in new.items(): s.vars[k] = _union((), v, E_VALUE)
  return s, s

def _h_unset(name, args, st, ctx, env, stdin):
  s = st.copy()
  s.vars.update({ftext(a): ((),) for a in args if (ftext(a) or "-")[0] != "-"})
  return s, s

def _h_set(name, args, st, ctx, env, stdin):
  s, i, dashdash = st.copy(), 0, False
  while i < len(args) and (ftext(args[i]) or "")[:1] in ("-", "+") and ftext(args[i]) != "-":
    t = ftext(args[i])
    i += 1
    if t == "--":
      dashdash = True
      break
    if "o" in t and i < len(args):
      s.errexit = t[0] == "-" if ftext(args[i]) == "errexit" else s.errexit
      i += 1
    if "e" in t[1:]: s.errexit = t[0] == "-"
  if dashdash or i < len(args): s.pos = ((st.pos or (N_VALUE,))[0],) + tuple(to_value(f) for f in args[i:])
  return s, s

def _h_read(name, args, st, ctx, env, stdin):
  s, names, i = st.copy(), [], 0
  while i < len(args) and ftext(args[i]) is not None:
    t = ftext(args[i])
    i += 1
    if t[:1] != "-" or len(t) < 2: names.append(t)
    elif t[-1] in "adnNptui":  # an option with a value (-a NAME also names a variable)
      names += [ftext(args[i])] if t[-1] == "a" and i < len(args) else []
      i += 1
  val = (("P", ctx.listing(stdin.items)),) if stdin and stdin.items is not None else E_VALUE
  for nm in names or ["REPLY"]:
    if nm: s.vars[nm] = (val,)
  return s, s

def _h_eval(name, args, st, ctx, env, stdin):
  if name == "trap": args = args[:1] if len(args) > 1 else []
  return analyze_text(" ".join(fscript(a) for a in args), st.copy(), ctx) if args else None

# ---------- commands that run other commands ----------
# Unknown options are read both ways (taking a value or not), and a risky command name among the wrapper's own
# words is also analyzed, so only what changes the outcome is listed: "options naming the cwd|words to skip
# after the options (j = the rest is one command string)|options whose value is shell code (plus the rest)".
_WRAPPERS = dict.fromkeys("doas pkexec nice ionice stdbuf nohup time command builtin exec caffeinate arch busybox "
                          "setsid unbuffer fakeroot strace ltrace eatmydata nocache chronic ifne numactl prlimit "
                          "unshare nsenter firejail sandbox-exec".split(), "")
_WRAPPERS.update({"sudo": "-D --chdir", "run0": "-D --chdir", "systemd-run": "--working-directory", "timeout": "|1",
                  "env": "-C --chdir||-S --split-string", "chrt": "|1", "taskset": "|1", "chroot": "|1",
                  "setarch": "|1", "flock": "|1|-c --command", "script": "|1|-c --command", "watch": "|j",
                  "su": "||-c --command --session-command", "runuser": "||-c --command --session-command"})
_SHELLS = frozenset("sh bash zsh dash ksh mksh yash fish rbash ash posh source .".split())

def _starts(cwdopts, skip, args, ctx):  # where the wrapped command may start: [(index, cwd field or None)]
  out = {}

  def walk(i, cwd, forks):
    while i < len(args):
      ctx.tick()
      t = ftext(args[i])
      if t is None or t[:1] != "-" or t == "-": break
      i += 1
      if t == "--": break
      opt = next((o for o in cwdopts if t == o or t.startswith(o + ("=" if o[1] == "-" else ""))), None)
      if opt:
        cwd = fdrop(args[i - 1], len(opt) + (opt[1] == "-")) if t != opt else args[i] if i < len(args) else None
        i += t == opt
      elif "=" not in t and forks < MAX_FORKS:
        walk(i + 1, cwd, forks + 1)
    out.setdefault(min(i + skip, len(args)), cwd)
  walk(0, None, 0)
  return list(out.items())

def _h_wrapper(name, args, st, ctx, env, stdin):
  cwdopts, skip, sopts = (_WRAPPERS[name] + "||").split("|")[:3]
  for k, a in enumerate(args):  # -c CODE of su/flock/script, env -S STRING
    nm, eq, _ = (ftext(a) or "").partition("=")
    code = (fdrop(a, len(nm) + 1) if eq else (args + [None])[k + 1]) if nm in sopts.split() else None
    if code is not None:
      analyze_text(" ".join(fscript(f) for f in [code] + args[k + 2 - bool(eq):]), _child(st, env), ctx)
  if name in ("su", "runuser") and stdin and stdin.text is not None and not any(  # no -c: the shell reads stdin
      (ftext(a) or "").partition("=")[0] in sopts.split() for a in args):
    analyze_text(stdin.text, _child(st, env), ctx)
  starts, res, prod = _starts(cwdopts.split(), int(skip) if skip.isdigit() else 0, args, ctx), [], None
  for i, cwd in starts:
    if skip == "j":
      analyze_text(" ".join(fscript(f) for f in args[i:]), _child(st, env), ctx)
      continue
    e, rest = dict(env), args[i:]
    while rest and re.match(_NAME + "=", fprefix(rest[0])):  # NAME=value words before the command
      nm = fprefix(rest[0]).split("=", 1)[0]
      val = fdrop(rest[0], len(nm) + 1)
      e[nm], rest = ((to_value(val, True),) if val is not None else (E_VALUE,)), rest[1:]
    res.append(dispatch(rest, _with_cwd(st, cwd, ctx) if cwd is not None else st, ctx, e, stdin))
    prod = ctx.produced or prod  # the last known stdout listing (nice -n 5 find ~ | xargs rm)
  for k in range(min(i for i, _ in starts)):  # safety net: a risky command name among the wrapper's own words
    if re.match(_RISKY_NAME, os_command_name(ftext(args[k]) or ""), _RX): dispatch(args[k:], st, ctx, env, stdin)
  ctx.produced = ctx.produced or prod
  return (merge(*[r[0] for r in res]), merge(*[r[1] for r in res])) if name in ("command", "builtin") and res else None

def _h_shell(name, args, st, ctx, env, stdin):
  """sh -c CODE, a shell fed by stdin (heredoc, here-string, pipe), source /dev/stdin; script files are not visible."""
  i, cmd, sin, ee = 0, False, False, False
  while i < len(args) and (ftext(args[i]) or "")[:1] in ("-", "+") and name not in ("source", "."):
    t = ftext(args[i])
    i += 1
    if t in ("-", "--"):
      sin |= t == "-"
      break
    if t[:2] == "--":
      i += t in ("--rcfile", "--init-file")
      continue
    cmd, sin, ee = cmd or "c" in t, sin or "s" in t, ee or t[0] == "-" and "e" in t
    i += t.count("o") + t.count("O")
  pos = tuple(to_value(f) for f in args[i + cmd:])
  if cmd and i < len(args): analyze_text(fscript(args[i]), _child(st, env, pos, ee), ctx)
  elif cmd or i < len(args) and not sin and ftext(args[i]) not in ("/dev/stdin", "/dev/fd/0", "-"): return None
  elif stdin and stdin.text is not None:
    analyze_text(stdin.text, _child(st, env, (N_VALUE,) + pos[i < len(args) and not sin:], ee), ctx)

def _placeholder(f, token, lid):  # `token` ({} or the xargs -I string) inside a field -> listing placeholder
  out = []
  for k, t in f:
    for j, piece in enumerate(t.split(token) if k in "QG" and token else [t]):
      out += ([("P", lid)] if j else []) + ([(k, piece)] if piece or k not in "QG" else [])
  return tuple(out)

def _h_xargs(name, args, st, ctx, env, stdin):
  repl, i, items = None, 0, stdin.items if stdin else None
  while i < len(args) and (ftext(args[i]) or "")[:1] == "-" and ftext(args[i]) != "-":
    t = ftext(args[i])
    nm, eq, val = t.partition("=")
    i += 1
    if t == "--": break
    if nm == "--replace" or t[:2] == "-i": repl = val or t[2:] or "{}"
    elif nm == "--arg-file" or t[:2] == "-a": items, i = None, i + (not (eq or t[2:] and t[:2] == "-a"))
    elif nm in ("--max-args", "--max-procs", "--max-chars", "--delimiter", "--max-lines", "--eof"): i += not eq
    elif t[:2] != "--" and t[1] in "IJLnPsEdRS":
      repl = (t[2:] or ftext((args + [()])[i])) if t[1] in "IJ" else repl
      i += not t[2:]
  cmd, lid = list(args[i:]) or [lit_field("echo")], ctx.listing(items)
  cmd = [_placeholder(f, repl, lid) for f in cmd] if repl else cmd + [(("P", lid),)]
  _nested(ctx, dispatch, cmd, st, ctx, {}, None)
  ctx.produced = None

# ---------- deletion, copy and disk-writing commands ----------
def _h_rm(name, args, st, ctx, env, stdin):
  for a in _operands(args):
    if name in ("rm", "srm", "unlink") or a and a[0][0] == "P": check_target(a, st, ctx, name, True)
    if name in ("shred", "truncate"): check_write(a, st, ctx, name, True)  # listed items count as deletion

def _h_find(name, args, st, ctx, env, stdin):
  i, starts = 0, []
  while i < len(args):
    t = ftext(args[i])
    if t in ("-H", "-L", "-P", "-E", "-X", "-d", "-s", "-x") or t and re.match(r"-O[0-9]*$", t): i += 1
    elif t in ("-D", "-f") and i + 1 < len(args):
      starts += [args[i + 1]] if t == "-f" else []
      i += 2
    else: break
  while i < len(args) and not re.match(r"-.|[(!),]$", ftext(args[i]) or "x"):
    starts.append(args[i])
    i += 1
  starts = starts or [lit_field(".")]
  lid, expr, delete, j = ctx.listing([(f, st) for f in starts]), args[i:], False, 0
  while j < len(expr):
    t = ftext(expr[j])
    delete |= t == "-delete"
    if t in ("-exec", "-execdir", "-ok", "-okdir"):
      k = j + 1
      while k < len(expr) and ftext(expr[k]) != ";" and not (ftext(expr[k]) == "+" and "{}" in fopaque(expr[k - 1])):
        k += 1
      if k > j + 1: _nested(ctx, dispatch, [_placeholder(f, "{}", lid) for f in expr[j + 1:k]], st, ctx, {}, None)
      j = k
    j += 1
  for f in starts if delete else []: check_target(f, st, ctx, "find -delete", True)
  ctx.produced = Produced(None, ctx.listings[int(lid)])

_RSYNC_VAL = ("--exclude --include --filter --files-from --exclude-from --include-from --backup-dir --link-dest "
              "--compare-dest --copy-dest --partial-dir --temp-dir --rsh --rsync-path --chmod --chown --log-file "
              "--out-format --max-size --min-size --timeout --bwlimit --port --password-file --suffix -e -f -T -B -M")

def _h_rsync(name, args, st, ctx, env, stdin):
  texts = [ftext(a) or "" for a in args]
  if any(t == "--dry-run" or re.match(r"-[a-zA-Z]*n", t) for t in texts): return None
  ops = _operands(args, _RSYNC_VAL)
  delete = any(t == "--del" or t.startswith("--delete") for t in texts)
  remove = {"--remove-source-files", "--remove-sent-files"} & set(texts)
  for k, f in enumerate(ops if len(ops) > 1 else []):  # remote paths (host:path, rsync://) are not local
    last = k == len(ops) - 1
    if (delete if last else remove) and not re.match(r"rsync://|[^/]*:", fprefix(f)):
      check_target(f, st, ctx, "rsync --delete" if last else "rsync --remove-source-files", not last)

def _h_git(name, args, st, ctx, env, stdin):
  i, sub, wt = 0, st, None
  while i < len(args) and (ftext(args[i]) or "x")[0] == "-":
    t = ftext(args[i])
    if t in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env") and i + 1 < len(args):
      sub = _with_cwd(sub, args[i + 1], ctx) if t == "-C" else sub
      wt = args[i + 1] if t == "--work-tree" else wt
      i += 1
    wt = fdrop(args[i], 12) if t.startswith("--work-tree=") else wt
    i += 1
  cmd, rest = (ftext(args[i]), args[i + 1:]) if i < len(args) else (None, [])
  if cmd == "ls-files": ctx.produced = Produced(None, [(lit_field("."), sub)])
  flags = "".join({"--force": "f", "--dry-run": "n"}.get(t, t[1:].split("e")[0] if t[:2] != "--" else "")  # -eVAL
                  for t in (ftext(a) or "" for a in rest) if t[:1] == "-")
  if cmd == "clean" and "n" not in flags and "f" in flags and set(flags) & set("dxX"):
    base = _with_cwd(sub, wt, ctx) if wt is not None else sub
    for p in [lit_field(".")] + _operands(rest, "-e --exclude"): check_target(p, base, ctx, "git clean")

def _h_dd(name, args, st, ctx, env, stdin):
  notrunc = any("notrunc" in fopaque(a) for a in args if fprefix(a).startswith("conv="))
  for a in args:
    if fprefix(a).startswith("of="): check_write(fdrop(a, 3) or (), st, ctx, name, not notrunc)

def _h_copy(name, args, st, ctx, env, stdin):  # cp, tee, pv -o, ddrescue: no raw writes to disk devices
  texts = [ftext(a) or "" for a in args]
  ops = _operands(args, "-o --output -t --target-directory -S --suffix")
  dests = [args[k + 1] for k, t in enumerate(texts[:-1]) if t in ("-o", "--output", "-t", "--target-directory")]
  dests += ops if name == "tee" else [] if name == "pv" else ops[1:]
  if name == "tee": ctx.produced = stdin
  trunc = name == "pv" or name == "tee" and not any(re.match(r"-[a-zA-Z]*a|--append", t) for t in texts)
  for d in dests: check_write(d, st, ctx, name, trunc)

def _const(*result):
  return lambda name, args, st, ctx, env, stdin: tuple(st if r else None for r in result)

def _unsupported(name, args, st, ctx, env, stdin):
  ctx.doubt("'%s' is not analyzed" % name)

_HANDLERS = {
    "cd": _h_cd, "pushd": _h_cd, "popd": _h_cd, "export": _h_decl, "declare": _h_decl, "typeset": _h_decl,
    "local": _h_decl, "readonly": _h_decl, "unset": _h_unset, "set": _h_set, "read": _h_read, "eval": _h_eval,
    "trap": _h_eval, "xargs": _h_xargs, "rm": _h_rm, "srm": _h_rm, "unlink": _h_rm, "shred": _h_rm, "truncate": _h_rm,
    "find": _h_find, "rsync": _h_rsync, "git": _h_git, "dd": _h_dd, "dcfldd": _h_dd, "cp": _h_copy, "tee": _h_copy,
    "pv": _h_copy, "ddrescue": _h_copy, "exit": _const(0, 0), "return": _const(0, 0), "logout": _const(0, 0),
    "true": _const(1, 0), ":": _const(1, 0), "false": _const(0, 1), "shift": _unsupported, "parallel": _unsupported,
}

# ---------- tamper guard: only the user, by hand, may change the installed hook or the agent settings ----------
# Guarded: this hook's own folder when it has a dedicated install folder (a name containing "destruction"), else its
# file; and the agent settings files (OS_PROTECTED "f"). Reading them and running the hook stay allowed.
_TAMPER = []  # (case-folded components, display, is_folder)
_READ_ONLY = frozenset("cat less more head tail grep egrep fgrep rg ag wc diff cmp ls stat file md5 md5sum shasum "
                       "sha1sum sha256sum sha512sum cksum cd pushd popd pwd echo printf test [ true false type which "
                       "realpath readlink dirname basename sort uniq cut tr nl column jq xxd od hexdump strings tree du "
                       "find get-content gc get-item gi get-childitem gci dir select-string sls test-path resolve-path "
                       "rvpa get-filehash measure-object compare-object findstr fc write-output write-host "
                       "convertfrom-json convertto-json select-object select where-object where ? sort-object "
                       "out-string out-host format-list fl format-table ft get-member gm".split())
_FIND_WRITES = r"-(?:delete|exec|execdir|ok|okdir|fprint0?|fprintf|fls)$"
_PYTHONS = ("python", "python3", "py")

def _guard(path, disp, folder):
  for form in os_forms(path):
    _TAMPER.append(([_key(c) for c in form.split("/") if c], disp, folder))

_HOOK_AT = "its install folder"
try:
  _SELF = os.path.realpath(__file__)
  _dedicated = "destruction" in os.path.basename(os.path.dirname(_SELF)).lower()
  _HOOK_AT = _pretty(_norm(os.path.dirname(_SELF) if _dedicated else _SELF).replace("\\", "/"))
  _guard(os.path.dirname(_SELF) if _dedicated else _SELF, "hook", _dedicated)
except Exception: pass
for _kind, _path in OS_PROTECTED:
  if _kind == "f": _guard(re.sub(r"\[([*?[])\]", r"\1", _path), "settings", False)
_MENTIONS = {"disableallhooks": "switch"}  # case-folded text forms of the guarded locations -> what they are
for _c, _d, _f in _TAMPER:
  _p, _h = "/" + "/".join(_c).lower(), OS_HOME.lower().rstrip("/")
  _MENTIONS[_p] = _d
  if _h and _p.startswith(_h + "/"): _MENTIONS.update({_p[len(_h):]: _d, _p[len(_h):].replace("/", "\\"): _d})
  if _f: _MENTIONS[_c[-1].lower()] = _d

_WHY = {  # why each guarded thing is blocked, and what is still allowed (shown to the agent and the user)
    "hook": "would change the Destruction_blocker safety hook itself (%s). Only the user can change, move or remove "
            "it, by hand, outside the agent. Reading and running it are allowed." % _HOOK_AT,
    "settings": "would change an agent settings file (~/.claude/settings.json, settings.local.json, ~/.codex/hooks.json "
                "or config.toml). These files register the Destruction_blocker safety hook, so shell commands may not "
                "change them. To change another setting, use the agent's file-editing tool (allowed as long as the "
                "safety hook's entry stays the same) or edit the file by hand. Reading it is allowed.",
    "registration": "would change or remove the Destruction_blocker safety hook's own entry in the agent settings "
                    "(its command or matcher). Other settings in this file can be edited; the hook's entry can only "
                    "be changed by the user, by hand.",
    "switch": "would turn on disableAllHooks, which switches off every hook including the Destruction_blocker safety "
              "hook. Only the user can do that, by hand.",
}

def _tamper_hit(field, st, move=False):
  """Guarded location that `field` names (or contains, if `move`), or None."""
  for full, _ in _paths(field, st):
    comps = [(_key(a), _key(b), m) for a, b, m in full]
    for ents, disp, folder in _TAMPER:
      n, m = len(comps), len(ents)
      if (n == m or n > m and folder or n < m and move) and all(_cmatch(c, (e, False)) for c, e in zip(comps, ents)):
        return disp
  return None

def _tamper_deny(what, kind):
  raise Deny("Blocked by the safety hook: %s %s" % (what, _WHY[kind]))

def _tamper(name, args, st, ctx):
  """Deny any command except reading and running the hook that touches a guarded location or runs inside it."""
  texts = [ftext(a) or "" for a in args]
  if not _TAMPER or name in _READ_ONLY and not (name == "find" and any(re.match(_FIND_WRITES, t) for t in texts)):
    return
  if name in _PYTHONS and [t for t in texts if t != "-3"][:1] == [t for t in texts if t != "-3"] \
          and texts and texts[-1].lower().endswith("destruction_blocker.py"):
    return  # python3 HOOK: running the hook changes nothing
  for c in st.cwds:
    hit = c != UNKNOWN_DIR and _tamper_hit(lit_field(c), st)
    if hit: _tamper_deny("%s (run inside it)" % name, hit)
  for a in args:
    hit = _tamper_hit(a, st, name in ("mv", "rename"))
    if hit: _tamper_deny(name, hit)

def tamper_text(text):
  """Deny reason when the text names a guarded location (e.g. inside python -c code) and is not read-only."""
  low = text.lower()
  named = lambda t: next((k for m, k in _MENTIONS.items() if re.search(re.escape(m) + r"(?![\w.-])", t)), None)
  if not named(low): return None
  kind = next(filter(None, map(named, re.findall(r"\d?>>?\|?\s*([^\s;&|<>]+)", low))), None)  # redirected onto
  for seg in re.split(r"\$\(|`|&&|\|\||[;&|\n(){}]", low):
    if not named(seg): continue  # only the parts that name a guarded location (variables: see _tamper)
    w =[x for x in (x.strip("'\"") for x in seg.split()) if x]
    while w and re.match(r"[a-z_][a-z0-9_]*=", w[0]): w = w[1:]
    while len(w) > 1 and w[0] in ("cmd", "cmd.exe") and w[1] in ("/c", "/k", "/r"): w = w[2:]  # cmd /c CMD
    if not w or "-whatif" in w: continue  # PowerShell -WhatIf: a dry run
    n = re.split(r"[/\\]", w[0])[-1]
    n = n[:-4] if n.endswith(".exe") else n
    rest = [x for x in w[1:] if x != "-3"]
    if n in _PYTHONS and len(rest) == 1 and rest[0].endswith("destruction_blocker.py"): continue
    if n in _READ_ONLY and not (n == "find" and any(re.match(_FIND_WRITES, x) for x in rest)): continue
    kind = kind or named(seg)
  return kind and "Blocked by the safety hook: this command %s" % _WHY[kind]

_FILE_TOOLS = ("edit", "write", "multiedit", "notebookedit")
_HOOK_LINE = re.compile(r"destruction[_-]?blocker|destructive_commands|disableallhooks", re.I)

def _registration(text, path):
  """What decides whether the hook runs: (matcher, key, value) of every hook entry and disableAllHooks (JSON);
  the lines mentioning hooks (other formats). None if a JSON file does not parse."""
  if not path.lower().endswith(".json"): return sorted(l.strip() for l in text.splitlines() if "hook" in l.lower())
  try: data = json.loads(text) if text.strip() else {}
  except ValueError: return None
  regs = []

  def walk(x, matcher=None):
    if isinstance(x, dict):
      matcher = x.get("matcher", matcher)
      for k, v in x.items():
        if isinstance(v, str) and _HOOK_LINE.search(v): regs.append((str(matcher), k, v))
        walk(v, matcher)
    elif isinstance(x, list):
      for v in x: walk(v, matcher)
  walk(data)
  return sorted(regs), data.get("disableAllHooks") if isinstance(data, dict) else None

def file_tool(tool, ti, cwd):
  """Deny reason for an agent's own file-editing tool (Edit, Write, ...) touching the hook or its registration."""
  path = ti.get("file_path") or ti.get("notebook_path")
  if not isinstance(path, str) or not path.strip(): return None
  hit = _tamper_hit(lit_field(path), initial_state(cwd))
  edits = [e for e in ti.get("edits") or [] if isinstance(e, dict)] + [ti]
  new = "\n".join(str(e.get(k) or "") for e in edits for k in ("new_string", "content", "new_source"))
  if hit == "hook": _tamper_deny("this %s" % tool, hit)
  if re.search(r"disableallhooks", new, re.I) and re.search(r"settings(\.local)?\.json$", path, re.I):
    _tamper_deny("this %s" % tool, "switch")
  if hit:  # a settings file: other settings may change, the hook's registration may not (the edit is simulated)
    try:
      with open(os.path.expanduser(path), encoding="utf-8") as f: before = f.read()
    except Exception: before = ""
    after = ti.get("content") if tool == "write" else before
    for e in edits if tool != "write" else []:
      old, rep = e.get("old_string"), e.get("new_string")
      if isinstance(old, str) and old and isinstance(rep, str):
        after = after.replace(old, rep) if e.get("replace_all") else after.replace(old, rep, 1)
    a, b = _registration(before, path), _registration(after if isinstance(after, str) else "", path)
    if a is None or b is None or a != b: _tamper_deny("this %s" % tool, "registration")
  return None

# ---------- S1: fail closed only when the command looks risky ----------
_RX = re.I if OS_CASE_INSENSITIVE else 0
_RISKY = r"(?<![\w.-])(?:" + "|".join(OS_RISKY) + r")(?![\w-])"
_RISKY_NAME = r"(?:" + "|".join(OS_RISKY) + r"|find|rsync|git|osascript|trash|unlink|truncate)$"

def is_risky(text):  # delete/disk/backup tools anywhere in the text (also with quotes removed)
  return any(re.search(_RISKY, t, _RX) or any(re.search(a, t, _RX) and re.search(b, t, _RX) for a, b in OS_RISKY_COMBOS)
             for t in (text, re.sub(r"[\"'\\]", "", text)))

def s1(command, why):
  reason = "Could not verify this command is safe (%s); run a simpler command or ask the user." % why
  return reason if is_risky(command) else None

def analyze(command, cwd):
  """Deny reason for `command` run in working directory `cwd` (None = unknown), or None."""
  if len(command) > MAX_INPUT: return s1(command, "the command is too long to analyze")
  ctx = Ctx()
  try:  # a shell stops at NUL; also read it as a separator to be safe
    for text in [command] if OPAQUE not in command else [command.split(OPAQUE)[0], command.replace(OPAQUE, " ")]:
      run(Parser(text, ctx).parse(), initial_state(cwd), ctx)
  except Deny as d:
    return d.args[0]
  except Unsure as u:
    return s1(command, u.args[0])
  except RecursionError:
    return s1(command, "the command is nested too deeply")
  except Exception:
    return s1(command, "an internal error occurred while analyzing it")
  return s1(command, ctx.unsure[0]) if ctx.unsure else None

# ==== POWERSHELL, CMD AND WINDOWS PROGRAMS ====
# PowerShell is parsed without effects (it runs nothing that does not parse), then evaluated: a value is a list of core
# fields, ("B", text) script blocks, ("T", type) or ("S", "") shadow copies; paths are checked by the core. Left to S1:
# functions, classes, hashtables, unknown command names, path-building .NET calls, cmd for loops.
_SQ, _DQ, _DASH = "'\u2018\u2019\u201a\u201b", '"\u201c\u201d\u201e', "-\u2013\u2014\u2015"
_PS_WS = r"(?:[ \t\f\v\r\xa0]|`\r?\n|#[^\n]*|<#[\s\S]*?#>)*"
_PS_WSNL = r"(?:[ \t\f\v\r\n\xa0]|`\r?\n|#[^\n]*|<#[\s\S]*?#>)*"
_PS_KW = (r"(?i)(if|while|for|foreach|do|switch|try|trap|function|filter|param|begin|process|end|return|break|"
          r"continue|exit|throw|class|enum|using|workflow|configuration|data)(?=[\s({;]|$)")
_PS_VAR = r"\$(?:\{([^}]*)\}|((?:[A-Za-z_]\w*:)?\w+|[?$^]))"
_PS_BARE = r"(?:[^\s;|&(){},<>'\"`$\u2018-\u201e]|`[\s\S])+"
_PS_BIN = (r"(?i)\?\?(?!=)|\.\.|[*/%+](?!=)|[-\u2013\u2014\u2015](?:[ic]?(?:eq|ne|gt|ge|lt|le|like|notlike|match|"
           r"notmatch|contains|notcontains|in|notin|replace|split|join)|and|or|xor|band|bor|bxor|shl|shr|isnot|is|as|"
           r"f)(?![\w-])|[-\u2013\u2014\u2015](?=\s)")
_PS_ALIAS = {a: c for c, al in (
    ("remove-item", "ri rm rmdir rd del erase"), ("get-childitem", "gci ls dir"), ("get-item", "gi"), ("foreach-object",
    "% foreach"), ("where-object", "? where sort sort-object select select-object"), ("set-location", "cd sl chdir"),
    ("push-location", "pushd"), ("pop-location", "popd"), ("get-location", "gl pwd"), ("write-output", "echo write"),
    ("invoke-expression", "iex"), ("invoke-command", "icm sajb start-job start-threadjob"), ("start-process",
    "saps start"), ("set-content", "sc"), ("add-content", "ac"), ("clear-content", "clc"), ("new-item", "ni"),
    ("resolve-path", "rvpa cvpa convert-path"), ("tee-object", "tee"), ("get-ciminstance", "gcim gwmi get-wmiobject"),
    ("remove-ciminstance", "rcim rwmi remove-wmiobject"), ("get-psdrive", "gdr"), ("set-alias", "sal nal new-alias"),
    ("set-variable", "sv set nv new-variable")) for a in al.split()}
_PS_POS = {"remove-item": "path", "get-childitem": "path filter", "foreach-object": "process", "where-object":
           "filterscript", "invoke-command": "scriptblock", "start-process": "filepath argumentlist", "out-file":
           "filepath", "tee-object": "filepath", "join-path": "path childpath", "invoke-expression": "command",
           "set-variable": "name value", "set-alias": "name value"}
_PS_VALS = set("path literalpath filter include exclude credential stream depth attributes process begin end parallel "
               "membername inputobject argumentlist throttlelimit filterscript property value expandproperty first "
               "last skip scriptblock computername session name filepath verb workingdirectory windowstyle encoding "
               "width itemtype variable childpath command erroraction warningaction informationaction errorvariable "
               "warningvariable informationvariable outvariable outbuffer pipelinevariable progressaction".split())
_PS_AKA = dict(x.split("=") for x in "lp=literalpath pspath=literalpath args=argumentlist cn=computername "
               "type=itemtype wi=whatif cf=confirm ea=erroraction wa=warningaction ev=errorvariable "
               "ov=outvariable pv=pipelinevariable a=append".split())
_RI = ("path literalpath filter include exclude credential stream recurse force whatif confirm verbose debug "
       "erroraction warningaction informationaction errorvariable warningvariable informationvariable outvariable "
       "outbuffer pipelinevariable progressaction").split()
_PS_DISK = set("format-volume clear-disk initialize-disk remove-partition reset-physicaldisk remove-physicaldisk "
               "remove-virtualdisk remove-storagepool clear-recyclebin".split())
_SHADOW = "Blocked: this deletes shadow copies or backups (Windows restore points). " + OS_DISK_HINT

def _cat(*cols):  # all concatenations, one value per column
  acc = [()]
  for col in cols: acc = [_merge(a + b) for a in acc for b in col or [()]][:MAX_ALTS]
  return acc

def _ne(f):  # unknown parts made non-empty
  return tuple(("N", "") if k == "E" else (k, t) for k, t in f)

def _up(f):  # the parent folder
  return _ne(f) + (("Q", "\\.."),)

def _is(f, k):
  return f[:1] and f[0][0] == k

def _true(v):
  return bool(v) and all((ftext(f) or "").lower() == "true" for f in v)

def _pp(f, glob=False):  # a provider path: ~ is home; -Path wildcards are active
  t = f[0][1] if f and f[0][0] in "QG" else ""
  if t[:1] == "~" and t[1:2] in ("", "\\", "/"): f = ((f[0][0], WIN_HOME + t[1:]),) + f[1:]
  return tuple(("G" if glob and k == "Q" else k, t) for k, t in f)

def _write(f, st, ctx, tool, trunc):  # an unknown folder may also be home
  for s in (st, st.copy(cwds=(OS_HOME,))) if UNKNOWN_DIR in st.cwds else (st,): check_write(f, s, ctx, tool, trunc)

def _mark(ctx, t):  # S1 checks every analyzed text, also without ` and ^ (r`m, r^d)
  ctx.texts += [t, re.sub("[`^]", "", t)]

class _PSEnv:
  """PowerShell session state: folders (a core State), variables, aliases, block arguments."""

  def __init__(e, st, ctx):
    e.st, e.ctx, e.vars, e.alias, e.args = st, ctx, {}, {}, []

  def get(e, n):
    n = re.sub(r"^(?:global|script|local|private|using):", "", n)
    v = win_env(n[4:]) if n[:4] == "env:" else None
    if n[:4] == "env:": return e.ctx.wenv.get(n[4:]) or [lit_field(v) if v is not None else E_VALUE]
    if n in e.vars or n == "psitem": return e.vars.get(n, e.vars.get("_", [E_VALUE]))
    if n == "pwd": return [lit_field(_win(c)) if c != UNKNOWN_DIR else N_VALUE for c in e.st.cwds]
    return [lit_field(WIN_HOME if n == "home" else n.title())] if n in ("home", "true", "false") else \
        [()] if n == "null" else [E_VALUE]

  def set(e, n, v):
    n = re.sub(r"^(?:global|script|local|private):", "", n)
    if n[:4] == "env:": e.ctx.wenv[n[4:]] = v[:MAX_ALTS]
    elif n not in ("null", "true", "false"): e.vars[n] = v[:MAX_ALTS]

class PS:
  """PowerShell parser that evaluates while it parses (live) or only checks the syntax."""

  def __init__(s, src, env, live):
    s.s, s.i, s.n, s.e, s.live, s.nest, s.lastvar = src, 0, len(src), env, live, 0, None

  def c(s, k=0):
    return s.s[s.i + k:s.i + k + 1]

  def sp(s, nl=False):  # blanks, `-continuations, comments (and newlines)
    s.e.ctx.tick()
    s.i = re.compile(_PS_WSNL if nl else _PS_WS).match(s.s, s.i).end()
    if s.s.startswith("<#", s.i): raise Unsure("a quote is not closed")

  def err(s):
    raise Unsure("unexpected syntax")

  def rx(s, pat):
    return re.compile(pat).match(s.s, s.i)

  def doubt(s, what):
    if s.live: s.e.ctx.doubt("PowerShell %s is not analyzed" % what)
    return [E_VALUE]

  def stmts(s, end):  # statements up to `end` ("", "}", ")" or "]"); returns their output
    s.nest += 1
    if s.nest > 32: raise Unsure("commands are nested too deeply")
    out = []
    while True:
      s.sp(True)
      if s.c() == ";":
        s.i += 1
        continue
      if s.i >= s.n and end: s.err()
      if s.c() == end:
        s.i += len(end)
        s.nest -= 1
        return out
      before, kw = s.e.st.cwds, s.rx(_PS_KW)
      out += s.pipe()
      while s.s.startswith(("&&", "||"), s.i):
        s.i += 2
        out += s.pipe()
      s.sp()
      if s.e.st.cwds != before: s.e.st = s.e.st.copy(cwds=_union(before, s.e.st.cwds, UNKNOWN_DIR))  # cd may fail
      if s.c() == "&": s.i += 1  # a background job
      elif s.i < s.n and s.c() not in ";\n" + end and not kw: s.err()  # param(...) and blocks need no ;

  def pipe(s):
    s.sp(True)
    m = s.c() == ":" and s.rx(r":\w+\s+")  # a loop label
    s.i = m.end() if m else s.i
    m = s.rx(_PS_KW)
    if m: return s.keyword(m.group(1).lower(), m.end())
    inp = None
    while True:
      c, d = s.c(), s.c(1)
      if not c: s.err()
      if c in "&." and d in " \t{(\"'$" + _SQ + _DQ:  # call operator / dot-sourcing
        s.i += 1
        s.sp()
        inp = s.command(inp, s.arg1())
      elif c in "$'\"(@[{!,0123456789" + _SQ + _DQ or c in _DASH and d.isdigit():
        inp = s.expr(True)
        s.redirs()
      else: inp = s.command(inp)
      s.sp()
      if s.c() != "|" or s.c(1) == "|": return inp or []
      s.i += 1
      s.sp(True)

  def keyword(s, w, end):  # if, while, for(each), do, switch, try, trap, begin, ...
    s.i = end
    if w in ("class", "enum", "using", "workflow", "configuration", "data"): raise Unsure("'%s' is not analyzed" % w)
    s.sp()
    if w in ("return", "break", "continue", "exit", "throw"): return s.pipe() if s.c() not in ";\n)}" else []
    if w == "param": return s.params()
    if w in ("function", "filter"):
      s.word()
      s.sp()
      if s.c() == "(": s.dead(s.params)
      s.dead(s.body)
      return s.doubt("function") and []
    out, cont = [], {"if": "elseif|else", "try": "catch|finally", "do": "while|until"}.get(w)
    while True:  # ( ... ) and [types] before each { ... }; then only elseif/else, catch/finally, while/until
      s.sp(True)
      c = s.c()
      if c == "(":
        s.i += 1
        m = w == "foreach" and s.rx(r"(?i)\s*\$(\w+)\s+in\b")
        s.i = m.end() if m else s.i
        v = s.stmts(")")
        if m and s.live: s.e.set(m.group(1).lower(), v)
        if w in ("while", "until") and cont: return out  # do { } while ( )
      elif c == "[": s.typename()
      elif c == "," or c and c in _DASH and w == "switch": s.i += 1
      elif c == "{":
        out += s.clauses() if w == "switch" else s.body()
        j = s.i
        s.sp(True)
        m = cont and s.rx(r"(?i)(%s)(?=[\s({\[]|$)" % cont)
        if not m:
          s.i = j
          return out
        s.i, w = m.end(), m.group(1).lower()
      elif w == "switch" and re.match(r"\w", c): s.word()
      else: s.err()

  def body(s):  # { ... } run in place
    s.sp(True)
    if s.c() != "{": s.err()
    s.i += 1
    return s.stmts("}")

  def dead(s, f, *a):  # parse without effects
    live, s.live = s.live, False
    try: return f(*a)
    finally: s.live = live

  def clauses(s):  # switch body: pattern { ... } pairs
    s.i += 1
    out = []
    while True:
      s.sp(True)
      c = s.c()
      if c == "}":
        s.i += 1
        return out
      if not c: s.err()
      if c == ";": s.i += 1
      else:
        s.dead(s.primary) if c == "{" else s.word() if re.match(r"\w", c) else s.unary()
        out += s.body()

  def params(s):  # param(...): binds a block's positional arguments
    s.sp(True)
    if s.c() != "(": s.err()
    s.i += 1
    while True:
      s.sp(True)
      c = s.c()
      if c == ")":
        s.i += 1
        return []
      if c == "[": s.typename()
      elif c == ",": s.i += 1
      else:
        m = s.rx(_PS_VAR) or s.err()
        s.i = m.end()
        s.sp(True)
        d = None
        if s.c() == "=":
          s.i += 1
          d = s.expr()
        if s.live: s.e.set((m.group(1) or m.group(2)).lower(), s.e.args.pop(0) if s.e.args else d or [E_VALUE])

  def expr(s, stmt=False):  # an expression (stmt: an assignment too); returns values
    v = [f for el in s.binary() for f in el]
    m = stmt and s.rx(r"[ \t]*((?:[-+*/%\u2013]|\?\?)?=)(?!=)")
    if not m: return v
    name, s.i = s.lastvar, m.end()
    r = s.pipe()
    if s.live and name:
      s.e.set(name, r if m.group(1) == "=" else _cat(s.e.get(name), r) if m.group(1) == "+=" else [E_VALUE])
    return []

  def binary(s, comma=True):  # returns array elements (lists of values)
    left = s.operands(comma)
    while True:
      s.sp()
      m = s.rx(_PS_BIN)
      if m:
        s.i, op, s.lastvar = m.end(), m.group().lower()[-2:], None
        s.sp(True)
        right = s.operands(comma)
        L, R = [f for el in left for f in el], [f for el in right for f in el]
        left = left + right if op[-1] == "+" and (len(left) > 1 or len(right) > 1) else [_cat(L, R)] if op[-1] == "+" \
            else [[f for f in L if not _maybe_empty(f)] + R] if op == "??" else [s.doubt("-f")] if op[-1] == "f" and \
            op[0] in _DASH else [[E_VALUE]]
      elif s.c() == "?" and s.c(1) in " \t\n(":  # a ? b : c
        s.i += 1
        a = s.binary(comma)
        s.sp(True)
        if s.c() != ":": s.err()
        s.i += 1
        left, s.lastvar = [[f for el in a + s.binary(comma) for f in el]], None
      else: return left

  def operands(s, comma):  # a, b, c
    out = [s.unary()]
    while comma:
      s.sp()
      if s.c() != ",": return out
      s.i += 1
      s.sp(True)
      out.append(s.unary())
      s.lastvar = None
    return out

  def unary(s):
    s.sp()
    m = s.rx(r"(?i)!|[-\u2013\u2014\u2015](?:not|bnot|split|join)(?![\w-])|[-+](?=[\d$(.])|,")
    if m:
      s.i = m.end()
      v = s.unary()
      return v if m.group() == "," else [E_VALUE]
    if s.c() != "[": return s.postfix(s.primary())
    t = s.typename()
    if s.s.startswith("::", s.i): return s.postfix([(("T", t),)])
    s.sp()
    if s.c() and s.c() in "$(@['\"" + _SQ + _DQ or s.c().isdigit(): return s.unary()  # a cast
    return [(("T", t),)]

  def typename(s):  # [type] or [Attribute(...)]
    depth, j = 0, s.i
    while j < s.n:
      depth += (s.s[j] in "[(") - (s.s[j] in "])")
      j += 1
      if not depth: break
    t, s.i = s.s[s.i + 1:j - 1], j
    if depth or not re.match(r"[\w.+`,\[\]\s]*(?:\(.*\))?\s*$", t, re.S): s.err()
    return t

  def primary(s):
    s.lastvar, c, d = None, s.c(), s.c(1)
    if not c: s.err()
    if c in _SQ: return [s.squote()]
    if c in _DQ: return s.dquote()
    if c == "@" and d in _SQ + _DQ:  # @' ... '@ and @" ... "@
      m, j = re.compile(r"\n[%s]@" % (_DQ if d in _DQ else _SQ)).search(s.s, s.i), s.s.find("\n", s.i)
      if not m or j < 0: raise Unsure("a quote is not closed")
      s.i = j + 1
      v = [lit_field(s.s[j + 1:m.start()].rstrip("\r"))] if d in _SQ else s.dquote(m.start())
      s.i = m.end()
      return v
    if c == "@" and d in "({" or c == "$" and d == "(" or c in "({":
      s.i += 1 + (c in "$@")
      if c == "(" or d == "(": return s.stmts(")")
      j = s.i
      if c == "{":
        s.dead(s.stmts, "}")
        return [(("B", s.s[j:s.i - 1]),)]
      while s.sp(True) or s.c() != "}":  # @{ key = value; ... }
        m = s.c() == ";" or s.rx(r"""(?:[\w-]+|'[^']*'|"[^"]*")[ \t]*=""") or s.err()
        s.i = s.i + 1 if m is True else m.end()
        if m is not True: s.dead(s.pipe)
      s.i += 1
      return s.doubt("a hashtable")
    if c == "$": return s.variable()
    m = s.rx(r"(?i)0x[0-9a-f]+|\d+(?:\.\d+)?(?:e\d+)?(?:[kmgtp]b)?[dl]?") or s.err()
    s.i = m.end()
    return [lit_field(m.group())]

  def postfix(s, v):  # .member, .method(...), ::static, [index]
    while True:
      c, d = s.c(), s.c(1)
      if c == "[":
        s.i += 1
        s.stmts("]")
      elif c + d in ("++", "--"): s.i += 2
      elif c == "." and (d.isalpha() or d in "_'\"$") or c + d == "::":
        s.i += 1 + (c == ":")
        m = s.rx(r"\w+")
        name = s.squote() if d in _SQ else s.dquote()[0] if d in _DQ else s.variable()[0] if d == "$" else \
            lit_field(m.group() if m else s.err())
        s.i = m.end() if m and d not in "'\"$" + _SQ + _DQ else s.i
        a = s.call_args() if s.c() == "(" else None
        v = s.member(v, (ftext(name) or "").lower(), a, c == ":") if s.live else [E_VALUE]
      else: return v
      s.lastvar = None

  def call_args(s):  # (a, b) of a method call
    s.i += 1
    out = []
    while True:
      s.sp(True)
      if s.c() == ")":
        s.i += 1
        return out
      if out:
        if s.c() != ",": s.err()
        s.i += 1
      out.append([f for el in s.binary(False) for f in el])

  def variable(s):
    m = s.rx(_PS_VAR)
    if not m:
      s.i += 1
      return [lit_field("$")]
    s.i, s.lastvar = m.end(), (m.group(1) if m.group(1) is not None else m.group(2)).lower()
    return s.e.get(s.lastvar) if s.live else [E_VALUE]

  def squote(s):  # '...' ('' is a quote)
    m = s.rx("[%s]((?:[^%s]|[%s]{2})*)[%s]" % ((_SQ,) * 4))
    if not m: raise Unsure("a quote is not closed")
    s.i = m.end()
    return lit_field(re.sub("[%s]{2}" % _SQ, "'", m.group(1)))

  def dquote(s, stop=None):  # "..." or a here-string body up to `stop`
    s.i += stop is None
    cols, buf = [], []
    while True:
      if s.i >= (stop or s.n):
        if stop: break
        raise Unsure("a quote is not closed")
      c, d = s.s[s.i], s.c(1)
      if c in _DQ and not stop:
        s.i += 1
        if not d or d not in _DQ: break
        buf.append('"')
        s.i += 1
      elif c == "`":
        buf.append({"n": "\n", "t": "\t", "r": "\r", "0": OPAQUE}.get(d, d))
        s.i += 2
      elif c == "$" and (d == "(" or s.rx(_PS_VAR)):
        cols.append([lit_field("".join(buf))])
        buf = []
        s.i += 2 * (d == "(")
        cols.append(s.stmts(")") or [()] if d == "(" else s.variable())
      else:
        m = re.compile(r'[^"`$\u201c-\u201e]+').match(s.s, s.i, stop or s.n)
        buf.append(m.group() if m else c)
        s.i = m.end() if m else s.i + 1
    return _cat(*cols + [[lit_field("".join(buf))]]) if s.live else [E_VALUE]

  def word(s):  # a bareword
    m = s.rx(_PS_BARE) or s.err()
    s.i = m.end()
    return re.sub(r"`([\s\S])", r"\1", m.group()) if "`" in m.group() else m.group()

  def arg1(s):  # one argument; adjacent parts join ("$HOME"\x, $PWD\build)
    cols, start = [], s.i
    while True:
      c, d = s.c(), s.c(1)
      if not c or c in " \t\r\n\f\v\xa0;|&)},<>" or c in "({" and cols or c == "`" and d in "\r\n": break
      if c in "({" or c == "@" and d in "({" + _SQ + _DQ or c == "$" and d == "(": v = s.postfix(s.primary())
      elif c == "$": v = s.postfix(s.variable()) if s.i == start else s.variable()
      else: v = [s.squote()] if c in _SQ else s.dquote() if c in _DQ else [lit_field(s.word())]
      cols.append(v)
    return _cat(*cols) if cols else s.err()

  def redirs(s):
    while True:
      s.sp()
      m = s.c() in "123456*>" and s.c() and s.rx(r"[1-6*]?>>?(?:&[1-6])?")
      if not m: return
      s.i = m.end()
      if "&" in m.group(): continue
      s.sp()
      for f in s.arg1() if s.live else s.arg1() and ():
        _write(_pp(f), s.e.st, s.e.ctx, "the redirection " + m.group(), ">>" not in m.group())

  def command(s, inp, names=None):
    names, args = names or [lit_field(s.word())], []
    while True:
      s.redirs()
      c, d = s.c(), s.c(1)
      if not c or c in ";\n|)}" or c == "&" and d in "& \t\r\n": break
      if c == "<": s.err()
      m = s.rx(r"[-\u2013\u2014\u2015]([A-Za-z_?-][\w?-]*)(:?)")
      if s.s.startswith("--%", s.i):
        s.doubt("--%")
        s.i = (s.s.find("\n", s.i) + 1 or s.n + 1) - 1
      elif s.rx(r"@\w+(?=[\s;|)}]|$)"):  # splatting
        s.i = s.rx(r"@\w+").end()
        s.doubt("splatting")
      else:
        s.i = m.end() if m else s.i
        if m and m.group(2): s.sp()
        v = s.arg1() if not m or m.group(2) else None
        while v and s.rx(r"[ \t]*,"):  # an array argument a, b, c
          s.i = s.rx(r"[ \t]*,").end()
          s.sp(True)
          v += s.arg1()
        args.append(("p", m.group(1).lower(), v, m.group().rstrip(":")) if m else ("v", v))
    return [x for nm in names for x in s.call(nm, args, inp)] if s.live else []

  # ---------- evaluation ----------
  def invoke(s, text, args=(), inp=None):  # run a script block with $_, $args and param(...)
    e = s.e
    saved = dict(e.vars), e.args
    if inp is not None: e.vars["_"] = inp
    e.vars["args"], e.args = [f for a in args for f in a], list(args)
    try: return _nested(e.ctx, lambda: PS(text, e, True).stmts(""))
    finally: e.vars, e.args = saved

  def bind(s, args, cmd):  # parameters by name (or unique prefix) and position; None: Remove-Item refuses
    strict, b, rest, i = cmd == "remove-item", {}, [], 0
    names = _RI if strict else _PS_VALS
    while i < len(args):
      a, i = args[i], i + 1
      if a[0] == "v":
        rest.append(a[1])
        continue
      t = _PS_AKA.get(a[1], a[1])
      c = [x for x in names if x.startswith(t)]
      n, v = t if t in names else c[0] if len(c) == 1 else None, a[2]
      if n in _PS_VALS and v is None and i < len(args) and args[i][0] == "v": v, i = args[i][1], i + 1
      if strict and (n is None or n in _PS_VALS and v is None): return None
      b[n or t] = v if v is not None else [lit_field("True")]
    for n in _PS_POS.get(cmd, "path").split():
      if rest and n not in b: b[n] = rest.pop(0)
    if rest and strict: return None
    b["*"] = [f for r in rest for f in r]
    return b

  def targets(s, b, inp):  # -Path (wildcards), -LiteralPath, else the pipeline input
    out = []
    for f in [_pp(f, True) for f in b.get("path", [])] + [_pp(f) for f in b.get("literalpath", [])]:
      out += [_pp(x) for x in s.invoke(f[0][1], inp=inp or [E_VALUE])] if _is(f, "B") else [f]
    return out if out or "path" in b or "literalpath" in b else inp or []

  def member(s, v, n, a, static):  # .n, .n(a), [type]::n(a)
    st, ctx, a0 = s.e.st, s.e.ctx, (a or [[E_VALUE]])[0]
    t = re.sub(r"^system\.", "", "".join(f[0][1] for f in v if _is(f, "T")).lower().replace(" ", ""))
    if a is None: return [lit_field(n)] if static else [x for f in v for x in ([f] if n in (  # [Enum]::Value
        "fullname", "value", "path", "pspath", "root") else [_up(f)] if n in ("parent", "directory", "directoryname",
        "psparentpath") else [E_VALUE])]
    if static and t in ("io.directory", "io.file") and n == "delete" or t.endswith("fileio.filesystem") and n[:6] == \
            "delete" and "sendtorecyclebin" not in " ".join(fopaque(f) for x in a for f in x).lower() or \
            not static and n in ("deletefolder", "deletefile"):
      for f in a0: check_target(f, st, ctx, "%s.%s()" % (t, n), True)
    elif static and t == "io.file" and re.match(r"write|create$|open", n):
      for f in a0: _write(f, st, ctx, "[IO.File]::" + n, True)
    elif n == "delete" and not static:
      for f in v:
        if f == (("S", ""),): raise Deny(_SHADOW)
        if not ftext(f): s.doubt("deleting an object that is not known")
        check_target(f, st, ctx, ".Delete()", True)
    elif static and t in ("environment", "io.path", "scriptblock", "powershell", "io.directoryinfo", "io.fileinfo") \
            or n in ("foreach", "where", "invoke", "invokereturnasis", "addscript", "invokescript"):
      return s.doubt("[%s]::%s" % (t, n))
    return [E_VALUE]

  def call(s, nm, args, inp):
    e, ctx = s.e, s.e.ctx
    if _is(nm, "B"): return s.invoke(nm[0][1], [a[1] for a in args if a[0] == "v"], inp)
    name = ftext(nm)
    if not name: return s.doubt("a command name that")
    c = name.lower().replace("\\", "/").rsplit("/", 1)[-1]
    if c[-4:] not in (".exe", ".com", ".bat", ".cmd"):  # aliases and cmdlets before programs
      c = _PS_ALIAS.get(c, c)
      c = _PS_ALIAS.get(e.alias.get(c, c), e.alias.get(c, c))  # Set-Alias cannot replace built-in aliases
      if c == "sudo":
        k = next((k for k, a in enumerate(args) if a[0] == "v"), len(args))
        return s.call(args[k][1][0], args[k + 1:], inp) if k < len(args) else []
      b = s.bind(args, c)
      if c in _PS_CMDS: return _PS_CMDS[c](s, c, b, inp) or []
      if c in _PS_DISK:
        if not _true(b.get("whatif")):
          raise Deny("Blocked: %s permanently erases a disk, volume, partition or the Recycle Bin. %s" % (c, (
              "Leave emptying the Recycle Bin to the user." if "recycle" in c else OS_DISK_HINT)))
        return []
      if c.split("-")[0].isalpha() and "-" in c[1:-1]:  # another cmdlet: only its script blocks run
        for f in [f for v in b.values() for f in v if _is(f, "B")]: s.invoke(f[0][1], inp=inp or [E_VALUE])
        return [E_VALUE]
    words = [list(dict.fromkeys(([a[3] + ":" + fopaque(x) for x in a[2]] if a[2] else [a[3]]) if a[0] == "p" else [
        f[0][1] if _is(f, "B") else fopaque(f) for f in a[1]]))[:4] or [""] for a in args]
    text = "".join(ftext(f) + "\n" for f in inp or [] if ftext(f)) or None
    for ws in itertools.islice(itertools.product(*words), 8): win_program(name, list(ws), e.st, ctx, text)
    return [E_VALUE]

def _c_remove(s, cmd, b, inp):
  for f in s.targets(b, inp) if b is not None and not _true(b.get("whatif")) else ():
    check_target(f, s.e.st, s.e.ctx, "Remove-Item", True)

def _c_list(s, cmd, b, inp):  # Get-ChildItem X lists X\* (a whole-folder glob); Get-Item X is X
  out = []
  for f in s.targets(b, inp) or [lit_field(".")]:
    m = cmd == "get-item" and re.match(r"(?i)env:[\\/]?(\w+)$", ftext(f) or "")
    if cmd == "get-item": out += s.e.get("env:" + m.group(1).lower()) if m else [f]
    else: out += ([] if ftext(f) == "" else [_ne(f) + (("G", "\\*"),)]) + ([(("G", "*"),)] if _maybe_empty(f) else [])
  return out

def _c_cd(s, cmd, b, inp):
  st, d, ps = s.e.st, (), s.targets(b, inp)
  if cmd == "pop-location": s.e.st = st.copy(cwds=st.stack[0], stack=st.stack[1:]) if st.stack else st
  elif ps:
    for f in ps: d = _union(d, _resolve_dirs(f, st, s.e.ctx), UNKNOWN_DIR)
    s.e.st = st.copy(cwds=d, stack=((st.cwds,) + st.stack) if cmd == "push-location" else st.stack)

def _c_each(s, cmd, b, inp):  # ForEach-Object; Where-, Sort-, Select-Object pass the input on
  out = []
  for f in [f for k in ("process", "parallel", "begin", "end", "membername", "filterscript", "*") for f in b.get(k, [])
            ]:
    n = (ftext(f) or "").lower()
    out += s.invoke(f[0][1], inp=inp or [E_VALUE]) if _is(f, "B") else s.member(
        inp or [], n, [] if n == "delete" else None, False) if cmd[0] == "f" else []
  x = b.get("expandproperty")
  return out if cmd[0] == "f" else s.member(inp or [], (ftext(x[0]) or "").lower(), None, False) if x else inp

def _c_write(s, cmd, b, inp):  # Set-Content, Out-File, Clear-Content, New-Item -Force, Tee-Object
  if not _true(b.get("whatif")) and (cmd != "new-item" or _true(b.get("force")) and "file".startswith(
          (ftext((b.get("itemtype") or [lit_field("file")])[0]) or "?").lower())):
    ps = [_pp(f, True) for f in b.get("path", [])] + [_pp(f) for f in b.get("literalpath", []) + b.get("filepath", [])]
    for f in _cat(ps, [lit_field("\\")], b["name"]) if b.get("name") else ps:
      _write(f, s.e.st, s.e.ctx, cmd, cmd != "add-content" and not _true(b.get("append")))
  return inp if cmd == "tee-object" else []

def _c_run(s, cmd, b, inp):  # Invoke-Expression, Invoke-Command, Start-Job, Start-Process
  for f in b.get("command") or b.get("scriptblock") or b.get("filepath") or cmd[0] == "i" and inp or []:
    if cmd == "start-process" and ftext(f):  # the program reads one joined command line
      win_program(ftext(f), _argv(" ".join(fopaque(x) for x in b.get("argumentlist", []) + b["*"])), s.e.st, s.e.ctx)
    elif cmd == "invoke-command" and _is(f, "B"): s.invoke(f[0][1], [[x] for x in b.get("argumentlist", [])], inp)
    elif cmd == "invoke-expression" and ftext(f) is not None: ps_text(ftext(f), s.e.st, s.e.ctx, s.e)
    else: s.doubt(cmd + " of something that")

def _c_set(s, cmd, b, inp):  # Set-Variable, Set-Alias
  for f in b.get("name", []):
    n = (ftext(f) or "").lower()
    if cmd == "set-variable": s.e.set(n, b.get("value") or inp or [()])
    elif n not in _PS_ALIAS: s.e.alias[n] = (ftext((b.get("value") or [()])[0]) or "").lower()

def _c_path(s, cmd, b, inp):  # Join-Path, Split-Path (the parent folder), Resolve-Path
  if cmd[0] == "j":
    return _cat(b.get("path") or inp or [()], *[x for f in (b.get("childpath"), b["*"]) if f
                                                for x in ([lit_field("\\")], f)])
  ps = s.targets(b, inp)
  return ps if cmd[0] == "r" else [E_VALUE] if {"leaf", "leafbase", "extension", "qualifier", "noqualifier",
                                                "isabsolute"} & set(b) else [_up(f) for f in ps]

def _c_cim(s, cmd, b, inp):  # Get-CimInstance Win32_ShadowCopy | Remove-CimInstance
  shadow = any("shadowcopy" in fopaque(f).lower() for v in b.values() for f in v)
  if cmd[0] == "g": return [(("S", ""),)] if shadow else [E_VALUE]
  if shadow or (("S", ""),) in (inp or []): raise Deny(_SHADOW)

_PS_CMDS = {"remove-item": _c_remove, "get-childitem": _c_list, "get-item": _c_list, "set-location": _c_cd,
            "push-location": _c_cd, "pop-location": _c_cd, "foreach-object": _c_each, "where-object": _c_each,
            "set-content": _c_write, "add-content": _c_write, "clear-content": _c_write, "out-file": _c_write,
            "new-item": _c_write, "tee-object": _c_write, "invoke-expression": _c_run, "invoke-command": _c_run,
            "start-process": _c_run, "join-path": _c_path, "split-path": _c_path, "resolve-path": _c_path,
            "get-ciminstance": _c_cim, "remove-ciminstance": _c_cim, "get-location": lambda s, c, b, i: s.e.get("pwd"),
            "write-output": lambda s, c, b, i: b["*"] + b.get("path", []) or i, "set-alias": _c_set,
            "set-variable": _c_set, "get-psdrive": lambda s, c, b, i: [lit_field(
                (ftext(f) or "C")[:1] + ":\\") for f in b.get("path", [])]}

def ps_text(text, st, ctx, env=None, top=False):
  """PowerShell code: parsed first (nothing runs if it does not parse), then analyzed."""
  if text is None: return ctx.doubt("PowerShell code is not known")
  if not top: _mark(ctx, text)
  e = env or _PSEnv(st, ctx)
  try: PS(text, e, False).stmts("")
  except Unsure as u:
    if top: return u.args[0]
    raise
  _nested(ctx, lambda: PS(text, e, True).stmts(""))

# ---------- cmd.exe ----------
_CMD_TOK = r'[ \t\r]*(?:(\n)|(&&|\|\||[&|()])|(\d?(?:>>?|<)(?:&\d)?)|((?:[^\s&|()<>"^]|\^[\s\S]|"[^"\n]*"?)+))'
_CMD_BUILTIN = set("rd rmdir del erase cd chdir pushd popd dir echo set type copy move md mkdir ren rename call start "
                   "rem cls title ver vol path prompt pause exit goto shift setlocal endlocal verify date time color "
                   "mklink".split())

def _argv(t):  # a Windows command line split the way programs split it
  out, cur, q, has = [], "", False, False
  for m in re.finditer(r'(\\*)"|\\+|[^\s\\"]+|\s+', t):
    g, n = m.group(), len(m.group(1) or "")
    if g[-1] == '"': cur, has, q = cur + "\\" * (n // 2) + '"' * (n % 2), True, q != (n % 2 == 0)
    elif g[0].isspace() and not q: out, cur, has = out + [cur] * has, "", False
    else: cur, has = cur + g, True
  return out + [cur] * has

class _Cmd:
  """Runs cmd.exe tokens over a core State; top: the whole command read as cmd."""

  def __init__(c, st, ctx, top):
    c.st, c.ctx, c.top = st, ctx, top

  def w(c, toks, i):
    return toks[i][1].replace('"', "").lower() if i < len(toks) and toks[i][0] == "w" else None

  def seq(c, toks, i, group):  # up to the end or the ')' closing a group
    while i < len(toks):
      c.ctx.tick()
      if toks[i] == ("o", ")") and group: return i + 1
      if toks[i][0] == "n" or toks[i][0] == "o" and toks[i][1] != "(": i += 1
      else:
        before = c.st.cwds
        i = c.cmd(toks, i, group)
        c.st = c.st.copy(cwds=_union(before, c.st.cwds, UNKNOWN_DIR))  # a cd may fail
    return i

  def eol(c, toks, i):
    while i < len(toks) and toks[i][0] != "n": i += 1
    return i

  def cmd(c, toks, i, group):
    if toks[i] == ("o", "("): return _nested(c.ctx, c.seq, toks, i + 1, True)
    w0 = (c.w(toks, i) or "").lstrip("@")
    if w0 == "if":  # if [/i] [not] condition command [else command]
      i += 1
      while c.w(toks, i) in ("/i", "not"): i += 1
      w = c.w(toks, i)
      if w is None: return c.eol(toks, i)
      i += 2 if w in ("exist", "defined", "errorlevel", "cmdextversion") or w.endswith("==") else 3 if c.w(
          toks, i + 1) in ("==", "equ", "neq", "lss", "leq", "gtr", "geq") else 1
      i = c.cmd(toks, i, group) if i < len(toks) else i
      return c.cmd(toks, i + 1, group) if c.w(toks, i) == "else" and i + 1 < len(toks) else i
    if w0 in ("for", "rem") or w0[:1] == ":":  # for %x loops are not analyzed (S1)
      ws = [t[1].lower() for t in toks[i + 1:i + 8]]  # for [/d /r ROOT /f "opts"] %x in ( ... ) do ...
      k = next((k for k, t in enumerate(ws) if re.match(r"%%?\w$", t)), 9)
      if w0 == "for" and ws[k + 1:k + 3] == ["in", "("]: c.ctx.doubt("cmd for loops are not analyzed")
      return c.eol(toks, i)
    words, redirs = [], []
    while i < len(toks) and (toks[i][0] in "wr" or toks[i] == ("o", "(")):
      if toks[i][0] == "r" and c.w(toks, i + 1) is not None:
        redirs.append((toks[i][1], toks[i + 1][1]))
        i += 1
      elif toks[i][0] != "r": words.append(toks[i][1])
      i += 1
    c.simple(words, redirs)
    return i

  def simple(c, raws, redirs):
    for op, t in redirs:
      if ">" in op and "&" not in op:
        _write((("Q", t.replace('"', "")),), c.st, c.ctx, "the redirection " + op, ">>" not in op)
    m = re.match(r"@*([a-z]+)([/\\.+\"].*)$", raws[0] if raws else "", re.I | re.S)  # rd/s/q, cd\
    if m and m.group(1).lower() in _CMD_BUILTIN: raws = [m.group(1), m.group(2)] + raws[1:]
    if not raws: return
    name = raws[0].replace('"', "").lstrip("@").lower()
    args = [x for r in raws[1:] for x in (re.findall(r"/[^/]*", r) if r[:1] == "/" else [r.replace('"', "")])]
    if name in ("rd", "rmdir", "del", "erase"):
      for a in args:
        if a[:1] != "/": check_target((("G", a),), c.st, c.ctx, name, True)
    elif name in ("cd", "chdir", "pushd"):
      t = " ".join(a for a in args if a.lower() != "/d")
      d = _resolve_dirs((("Q", t),), c.st, c.ctx) if t else c.st.cwds
      if name != "pushd" and "/d" not in (a.lower() for a in args) and t[1:2] == ":":
        d = _union(d, c.st.cwds, UNKNOWN_DIR)  # another drive without /d: the current folder stays
      c.st = c.st.copy(cwds=d, stack=((c.st.cwds,) + c.st.stack) if name == "pushd" else c.st.stack)
    elif name == "popd" and c.st.stack: c.st = c.st.copy(cwds=c.st.stack[0], stack=c.st.stack[1:])
    elif len(name) == 2 and name[1] == ":": c.st = c.st.copy(cwds=("/" + name[0],))
    elif name in ("call", "start"):
      rest = raws[1:]
      while name == "start" and rest and rest[0][:1] in '"/':
        rest = rest[1 + (rest[0].lower() in ("/d", "/affinity", "/node")):]
      c.simple(rest, [])
    elif name == "cmd": _cmd_c(raws[1:], c.st, c.ctx)
    elif name not in _CMD_BUILTIN: win_program(name, _argv(" ".join(raws[1:])), c.st, c.ctx, top=c.top)

def cmd_text(text, st, ctx, top=False):
  """cmd.exe text (top: the whole command read as cmd; only Windows programs are checked there)."""
  if not top: _mark(ctx, text)

  def var(m):  # %NAME% (unknown ones stay), %CD%
    n, v = m.group(1).lower(), ctx.wenv.get(m.group(1).lower())
    v = ftext(v[0]) if v else _win(st.cwds[0]) if n == "cd" else win_env(n)
    return OPAQUE if ":" in n or "~" in n or v == UNKNOWN_DIR else m.group() if v is None else v
  text = re.sub(r"%([^%\s]+)%", var, text) if "%" in text else text
  toks = [("n", "\n") if m.group(1) else ("o", m.group(2)) if m.group(2) else ("r", m.group(3)) if m.group(3) else
          ("w", re.sub(r'\^([\s\S])|("[^"]*"?)', lambda x: x.group(2) or x.group(1), m.group(4)) if "^" in m.group(4)
           else m.group(4)) for m in re.compile(_CMD_TOK).finditer(text)]
  _nested(ctx, _Cmd(st, ctx, top).seq, toks, 0, False)

def _cmd_c(raws, st, ctx, stdin=None):  # cmd.exe arguments: /c, /k or /r runs the rest
  for k, r in enumerate(raws):
    m = re.match(r"(?i)/+([ckr])(.*)", r, re.S)
    if m:
      t = " ".join(([m.group(2)] if m.group(2) else []) + raws[k + 1:]).strip()
      q = t.rfind('"')
      if "!" in t and any(re.match(r"(?i)/+v:on$", x) for x in raws[:k]):
        ctx.doubt("cmd /v:on !variables! are not analyzed")
      return cmd_text((t[1:q] + t[q + 1:] if q > 0 else t[1:]) if t[:1] == '"' else t, st, ctx)
  if stdin: cmd_text(stdin, st, ctx)

# ---------- programs (from PowerShell, cmd and Git Bash) ----------
def _shw(w):  # an argument as a shell word: Cygwin expands ~, globs and braces of a word without blanks
  if w.split() != [w]: return "'%s'" % w.replace("'", "'\\''").replace(OPAQUE, "'\"${__DB_N}\"'")
  return "".join(x if x.isalnum() or x in "_-./:~*?[]{},=@%+^" else '"${__DB_N}"' if x == OPAQUE else "\\" + x
                 for x in w)

def _ps_exe(words, st, ctx, stdin):  # powershell.exe / pwsh.exe arguments
  k = 0
  while k < len(words):
    w = words[k].lower()
    if w in ("-", "/-"): break
    if w[:1] not in "-/": return ps_text(" ".join(words[k:]), st, ctx)
    nm, att, _ = w.lstrip("-/").partition(":")
    rest = ([words[k].split(":", 1)[1]] if att else []) + words[k + 1:]
    if nm == "c" or len(nm) > 1 and "command".startswith(nm):
      return ps_text(" ".join(rest), st, ctx) if " ".join(rest).strip() != "-" else stdin and ps_text(stdin, st, ctx)
    if nm in ("e", "ec", "en", "enc") or len(nm) > 2 and "encodedcommand".startswith(nm):
      if rest and OPAQUE in rest[0]: return ctx.doubt("PowerShell runs an encoded command that is not known")
      try: t = __import__("base64").b64decode(rest[0].strip("'\""), validate=True).decode("utf-16-le")
      except Exception: return  # PowerShell cannot decode it either
      return ps_text(t, st, ctx)
    if nm in ("f", "file", "fi", "fil"): return  # a script file: not visible
    k += 1 + (not att and (nm in ("ep", "ex", "w", "wd", "v", "o", "of", "if") or len(nm) > 2 and any(o.startswith(
        nm) for o in ("executionpolicy", "windowstyle", "workingdirectory", "version", "outputformat", "inputformat"))))
  if stdin: ps_text(stdin, st, ctx)

def win_program(name, words, st, ctx, stdin=None, top=False):
  """A program run by PowerShell, cmd or Git Bash, with its final arguments ("\\0" = unknown)."""
  n, low = os_command_name(name), [w.lower() for w in words]
  j, path = " ".join(low), lambda w: (("Q", w),)
  ctx.tick()
  if n in ("powershell", "pwsh", "powershell_ise"): _ps_exe(words, st, ctx, stdin)
  elif n in ("cmd", "start"):
    _cmd_c(["/c", "start"] * (n == "start") + ['"%s"' % w if w.split() != [w] and '"' not in w else w for w in words],
           st, ctx, stdin)
  elif n == "sudo":
    k = next((k for k, w in enumerate(words) if w[:1] != "-" and low[k - 1:k] not in (["-d"], ["--chdir"])), len(words))
    if k < len(words): win_program(words[k], words[k + 1:], st, ctx, stdin, top)
  elif n == "diskpart" or n == "format" and "/?" not in low and any(re.match(r"[a-z]:\\?$|\\\\[?.]\\", w)
                                                                    for w in low) \
          or n == "wmic" and re.search(r"\b(?:volume|logicaldisk)\b.*\bformat\b", j):
    raise Deny("Blocked: %s erases or repartitions disks. %s" % (n, OS_DISK_HINT))
  elif n == "vssadmin" and re.search(r"\b(?:delete|resize)\b", j) or n == "wmic" and "shadowcopy" in j and \
          re.search(r"\bdelete\b", j) or n == "wbadmin" and re.search(r"\bdelete\b", j):
    raise Deny(_SHADOW)
  elif n == "robocopy":  # /MIR and /PURGE delete what is not in the source; /MOVE empties the source
    ps, sw = [w for w in words if w[:1] != "/"], {w.split(":")[0] for w in low if w[:1] == "/"}
    if "/l" not in sw and len(ps) > 1:
      if sw & {"/mir", "/purge"}: check_target(path(ps[1]), st, ctx, "robocopy /MIR", False)
      if sw & {"/mov", "/move"}: check_target(path(ps[0]), st, ctx, "robocopy /MOVE", False)
  elif n == "forfiles":
    o = {low[k][1:]: words[k + 1] for k in range(len(words) - 1) if low[k][:1] in "/-"}
    if o.get("c"):
      cmd_text(re.sub(r"(?i)@(?:path|file|fname|relpath)", lambda m: '"%s\\*"' % o.get("p", ".").rstrip("\\/"),
                      re.sub(r"0x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), o["c"])), st, ctx)
  elif n in ("sdelete", "sdelete64"):
    for w in words if not {"-z", "-c", "/z", "/c", "-?", "/?"} & set(low) else ():
      if w[:1] not in "-/": check_target(path(w), st, ctx, n, True)
  elif n == "wsl":  # wsl [--cd DIR] [-e PROGRAM ARGS | -- COMMAND LINE | COMMAND LINE]
    k, pre = 0, ""
    while k < len(words) and low[k][:1] == "-" and low[k] not in ("--", "-e", "--exec"):
      pre = "cd %s && " % _shw(words[k + 1]) if low[k] == "--cd" and k + 1 < len(words) else pre
      k += 1 + (low[k] in ("--cd", "-d", "--distribution", "-u", "--user", "--shell-type"))
    rest = words[k + (k < len(words) and low[k] in ("--", "-e", "--exec")):]
    if rest or stdin: analyze_text(pre + (" ".join(rest) or stdin), st.copy(), ctx)
  elif not top and _HANDLERS.get(n) is not _h_win and not (n == "find" and any(w in ("-exec", "-execdir", "-ok",
          "-okdir") and not any(x == ";" or x == "+" and "{}" in y for y, x in zip(words[k:], words[k + 1:]))
          for k, w in enumerate(words))):
    line = " ".join(_shw(w) for w in [name] + words)  # Git tools, shells, git, ...: the POSIX core (find with an
    if (line, st.cwds, stdin) in ctx.seen: return  # unterminated -exec refuses to run); each program line once
    ctx.seen.add((line, st.cwds, stdin))
    _mark(ctx, line)
    analyze_text(line, st.copy(stdin=Produced(stdin) if stdin is not None else None), ctx)

def _msys(w, lone):  # how Git Bash hands an argument to a Windows program: //x is /x, /c/x is C:/x
  if w[:2] == "//": return w[1:]
  m = re.match(r"([^=/]*=)?/([A-Za-z])(/.*)?$", w, re.S)
  return (m.group(1) or "") + m.group(2).upper() + ":" + (m.group(3) or "/") if m and (m.group(3) or lone) else w

def _h_win(name, args, st, ctx, env, stdin):  # a Windows program from Git Bash (lone /x read both ways)
  alts = []
  for f in args:  # items listed for find {} or xargs are substituted
    out = [()]
    for k, t in f:
      out = [o + x for o in out
             for x in ([x for x, _ in ctx.listings[int(t)] or []][:4] if k == "P" else 0) or [((k, t),)]]
    alts.append(list(dict.fromkeys(fopaque(x) for x in out[:4])))
  for ws in itertools.islice(itertools.product(*alts), 8):
    for lone in (False, True): win_program(name, [_msys(w, lone) for w in ws], st, ctx, stdin.text if stdin else None)
  ctx.produced = None

for _n in "cmd start powershell pwsh powershell_ise format diskpart vssadmin wmic wbadmin robocopy forfiles sdelete " \
          "sdelete64 wsl".split():
  _HANDLERS[_n] = _h_win

# ==== ENTRY POINT ====
CANARY = "echo PRETOOLUSE_HOOK_CANARY"  # always blocked, so agents can confirm the hook is live

def analyze_windows(command, cwd):
  """Deny reason for `command` read as Git Bash, PowerShell and cmd (any denial wins), or None."""
  if len(command) > MAX_INPUT: return s1(command, "the command is too long to analyze")
  ctx, doubts, berr, perr = Ctx(), [], None, None
  ctx.texts, ctx.wenv, ctx.seen, st = [], {}, set(), initial_state(cwd)
  _mark(ctx, command)
  if isinstance(cwd, str) and cwd.strip() and not _canon(cwd): st.cwds = (UNKNOWN_DIR,)  # a relative folder
  for text in [command] if OPAQUE not in command else [command.split(OPAQUE)[0], command.replace(OPAQUE, " ")]:
    for k in range(3):
      try:
        if k == 0:
          try: tree = Parser(text, ctx).parse()
          except Unsure as u:
            berr = u.args[0]
            continue
          run(tree, st.copy(), ctx)
        elif k == 1: perr = ps_text(text, st.copy(), ctx, top=True) or perr
        else: cmd_text(text, st.copy(), ctx, top=True)
      except Deny as d: return d.args[0]
      except Unsure as u: doubts.append(u.args[0])
      except RecursionError: doubts.append("the command is nested too deeply")
      except Exception: doubts.append("an internal error occurred while analyzing it")
  # A reading that does not parse belongs to another dialect, unless the construct is not analyzed or neither bash
  # nor PowerShell parses it (quoting, [[ ... ]], a later line).
  hard = lambda r: r and re.search(r"too deeply|too complex|too large|not analyzed", r) and not (
      r == "functions are not analyzed" and not re.search(r"[\w.:-]+\s*\(\s*\)", command))
  doubts += [r for r in (berr, perr) if hard(r)] + ctx.unsure
  if berr and perr and ("quote" in perr or "[[" in command or "\n" in command.strip()):
    doubts.append("it could not be parsed")
  if doubts and any(map(is_risky, ctx.texts)):
    return "Could not verify this command is safe (%s); run a simpler command or ask the user." % doubts[0]
  return None

def decide(raw):
  """Deny reason for a raw hook payload (JSON text), or None to allow."""
  try: payload = json.loads(raw)
  except Exception: return s1(raw, "the hook input is not valid JSON")
  tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
  if not isinstance(tool_input, dict): return None
  command, tool = tool_input.get("command"), str(payload.get("tool_name") or "").lower()
  if not isinstance(command, str):  # the agent's own file tools (Edit, Write, ...): only the hook is checked
    if tool in _FILE_TOOLS or any(k in tool_input for k in ("content", "old_string", "edits", "new_source")):
      try: return file_tool(tool or "edit", tool_input, payload.get("cwd"))
      except Deny as d: return d.args[0]
      except Exception: return None
    return None
  if command.strip() == CANARY:
    return "PreToolUse hook is installed and working (this harmless canary command is blocked on purpose)."
  return tamper_text(command) or analyze_windows(command, payload.get("cwd"))

def main():
  sys.stderr = io.StringIO()  # the hook must never write to stderr
  try: reason = decide(sys.stdin.buffer.read().decode("utf-8", "replace"))
  except Exception: reason = None
  if reason:
    sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                        "permissionDecisionReason": str(reason)[:1500]}}) + "\n")

if __name__ == "__main__":
  try: main()
  except BaseException: pass
  sys.exit(0)
