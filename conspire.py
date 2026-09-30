#!/usr/bin/env python3
"""conspire: keep Claude Code instruction files, settings, and memory in
one git repo (your "home" repo), synced across machines.

Python 3.12+, stdlib only. ALL entry points -- the Claude Code session
hooks, the git hooks, cron, and the command line -- run a subcommand
of this module through bin/conspire (which locates python via
bin/find_python.sh). Direct invocation also works:

    python3 <conspire>/conspire.py <subcommand>

Subcommands:
    init           point conspire at a home repo (or create one with --new)
    bootstrap      one-time machine setup (idempotent)
    check          verify this machine's wiring
    sync           commit local changes, ff-only pull, push (lock + timeouts)
    register       register the current project's memory decision
    index          regenerate MEMORY.md indexes (--check: verify, don't write)
    session-start  Claude Code SessionStart hook: sync + status block
    session-end    stamp .session-end.log (stamp only, by design)
    kiro-sync      bridge to/from ~/.kiro (Kiro machines only)

Design rules: sync never merges, rebases, resets, or cleans --
divergence is reported and left to the human; MEMORY.md is derived,
never authored; the machine tag is chosen, not detected.

Where things live:
    <tool>            this repo (code, hooks, templates)
    <home>            your data repo: claude/, memory/, memory-registry.tsv
    ~/.conspire/home  path of <home> ($CONSPIRE_HOME overrides)
    ~/.conspire/machine  this machine's tag ($CONSPIRE_MACHINE overrides)
"""

import argparse
import filecmp
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

TOOL = Path(__file__).resolve().parent
USER_HOME = Path.home()
CONF_DIR = USER_HOME / ".conspire"
CLAUDE_DIR = USER_HOME / ".claude"
LOCK_STALE_S = 600
MAX_LINES = 200          # Claude Code loads only the first 200 lines /
MAX_BYTES = 25 * 1024    # 25KB of MEMORY.md; beyond that is silently dropped.

try:
    GIT_TIMEOUT_S = int(os.environ.get("CONSPIRE_GIT_TIMEOUT", "30"))
except ValueError:
    GIT_TIMEOUT_S = 30


# ---------------------------------------------------------------- helpers

def home_repo():
    """The data repo. $CONSPIRE_HOME, else ~/.conspire/home; exits if
    neither is set (run: conspire init)."""
    p = os.environ.get("CONSPIRE_HOME", "").strip()
    if not p:
        f = CONF_DIR / "home"
        if f.is_file():
            p = f.read_text(encoding="utf-8").strip()
    if not p:
        sys.exit("conspire: no home repo configured; run: conspire init <path>")
    home = Path(p).expanduser()
    if not home.is_dir():
        sys.exit(f"conspire: home repo {home} does not exist; run: conspire init <path>")
    return home


def tilde(path):
    """~/... form when under $HOME (Claude Code expands ~ in settings
    and @imports, and the form is the same on every machine)."""
    try:
        return "~/" + Path(path).relative_to(USER_HOME).as_posix()
    except ValueError:
        return str(path)


def machine_tag():
    tag = os.environ.get("CONSPIRE_MACHINE", "").strip()
    if tag:
        return tag
    for f in (CONF_DIR / "machine", CLAUDE_DIR / "machine-id"):   # 2nd: legacy
        if f.is_file():
            return f.read_text(encoding="utf-8").strip()
    return None


def git(*args, cwd, timeout=GIT_TIMEOUT_S):
    """Run git, capturing output. Raises subprocess.TimeoutExpired on
    timeout (git is killed; a stale .git/*.lock is possible then, which
    the next run will report loudly)."""
    return subprocess.run(["git", *args], cwd=str(cwd), timeout=timeout,
                          capture_output=True, text=True)


def git_said(cp):
    return (cp.stdout + cp.stderr).strip() or "(no output)"


def normalize_remote(url):
    """github.com/owner/repo form: lowercase, no scheme/user/port/.git."""
    u = url.strip().lower()
    u = re.sub(r"^[a-z+]+://", "", u)
    u = re.sub(r"^[^@/]+@", "", u)                  # user@host
    u = re.sub(r"^([^/:]+):(\d+)(?=/)", r"\1", u)   # drop :port
    u = u.replace(":", "/", 1)                      # scp-style host:path
    return re.sub(r"\.git$", "", u)


def remote_names(proj):
    r = git("remote", cwd=proj)
    return r.stdout.split() if r.returncode == 0 else []


def project_remotes(proj):
    out = set()
    for name in remote_names(proj):
        u = git("remote", "get-url", name, cwd=proj)
        if u.returncode == 0 and u.stdout.strip():
            out.add(normalize_remote(u.stdout.strip()))
    return out


def registry_path(home):
    return home / "memory-registry.tsv"


def registry_rows(home):
    rows = []
    reg = registry_path(home)
    if not reg.is_file():
        return rows
    for ln in reg.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        f = ln.split("\t")
        if len(f) != 4 or f[0] == "name":
            continue
        rows.append({"name": f[0], "remotes": f[1].split(),
                     "decision": f[2], "date": f[3]})
    return rows


def acquire_lock(lock):
    for _ in range(2):
        try:
            lock.mkdir()
            return True
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                continue                     # holder just released; retry
            if age > LOCK_STALE_S:
                try:
                    lock.rmdir()
                except OSError:
                    pass
                continue
            return False
    return False


def release_lock(lock):
    try:
        lock.rmdir()
    except OSError:
        pass


# ------------------------------------------------------------------- init

def cmd_init(args):
    target = Path(args.path).expanduser().resolve()
    if args.new:
        if target.exists() and any(target.iterdir()):
            print(f"error: {target} exists and is not empty")
            return 1
        shutil.copytree(TOOL / "templates" / "home", target, dirs_exist_ok=True)
        r = git("init", "--quiet", cwd=target)
        if r.returncode != 0:
            print(f"error: git init failed: {git_said(r)}")
            return 1
        print(f"created home repo {target} from templates/home")
        print("  (add a remote and push when ready; sync works without one)")
    elif not target.is_dir():
        print(f"error: {target} is not a directory (use --new to create one)")
        return 1
    elif not (target / "memory").is_dir():
        print(f"warning: {target} has no memory/ directory; is it a home repo?")
    CONF_DIR.mkdir(parents=True, exist_ok=True)
    (CONF_DIR / "home").write_text(str(target) + "\n", encoding="utf-8")
    print(f"home repo: {target} -> {CONF_DIR / 'home'}")
    print("next: conspire bootstrap")
    return 0


# ------------------------------------------------------------------- sync

def cmd_sync(args):
    home = home_repo()
    quiet = getattr(args, "quiet", False)
    lock = home / ".sync.lock"

    def say(msg):
        if not quiet:
            print(f"conspire: {msg}")

    def loud(msg):
        print(f"conspire: {msg}")

    if not acquire_lock(lock):
        loud(f"another sync holds {lock.name}; skipped "
             f"(a stale lock clears after {LOCK_STALE_S // 60} min)")
        return 1
    rc = 0
    try:
        tag = machine_tag() or "unset-machine"
        st = git("status", "--porcelain", cwd=home)
        if st.returncode != 0:
            loud(f"git status failed: {git_said(st)}")
            return 1
        if st.stdout.strip():
            git("add", "-A", cwd=home)
            c = git("commit", "--quiet", "-m", f"sync from {tag}", cwd=home)
            if c.returncode != 0:
                loud("COMMIT FAILED -- memory writes are NOT synced; "
                     "fix and re-run sync")
                loud(f"git said: {git_said(c)}")
                rc = 1
            else:
                say("committed local changes")
        origin = git("remote", "get-url", "origin", cwd=home)
        if origin.returncode != 0:
            say("no origin remote configured; skipping pull/push")
            return rc
        try:
            p = git("pull", "--ff-only", "--quiet", cwd=home)
            if p.returncode != 0:
                loud("cannot fast-forward (offline or diverged). "
                     f"If diverged: cd {home} && git pull --rebase")
                loud(f"git said: {git_said(p)}")
                rc = 1
            pu = git("push", "--quiet", cwd=home)
            if pu.returncode != 0:
                loud(f"push failed: {git_said(pu)}")
                rc = 1
        except subprocess.TimeoutExpired:
            loud(f"network git timed out after {GIT_TIMEOUT_S}s; "
                 "proceeding with stale state (next sync retries)")
            rc = 1
    finally:
        release_lock(lock)
    return rc


# ---------------------------------------------------------- session hooks

def sync_status_line(home):
    """Freshness computed from git state, not from 'the sync ran'."""
    parts = []
    r = git("rev-list", "--left-right", "--count", "@{upstream}...HEAD", cwd=home)
    if r.returncode == 0 and len(r.stdout.split()) == 2:
        behind, ahead = (int(x) for x in r.stdout.split())
        if ahead == 0 and behind == 0:
            parts.append("in sync with origin")
        else:
            note = (f" -- DIVERGED: cd {tilde(home)} && git pull --rebase"
                    if ahead and behind else "")
            parts.append(f"ahead {ahead} / behind {behind}{note}")
    else:
        parts.append("no upstream tracking info")
    st = git("status", "--porcelain", cwd=home)
    if st.returncode == 0 and st.stdout.strip():
        parts.append("uncommitted changes present")
    return "; ".join(parts)


def memory_state(home, proj):
    memdir = None
    for name in (".claude/settings.local.json", ".claude/settings.json"):
        f = proj / name
        if f.is_file():
            try:
                memdir = json.loads(f.read_text(encoding="utf-8")).get(
                    "autoMemoryDirectory")
            except Exception:
                memdir = None
            if memdir:
                break
    if memdir:
        try:
            Path(memdir).expanduser().resolve().relative_to(home.resolve())
            return "VERSION CONTROLLED", f"-> {memdir}"
        except ValueError:
            return "LOCAL (custom dir)", f"-> {memdir}"
    idents = project_remotes(proj) | {f"path:{proj}"}
    for row in registry_rows(home):
        if idents & set(row["remotes"]):
            if row["decision"] == "out":
                return "NOT VERSION CONTROLLED", f"(opted out {row['date']})"
            return ("UNREGISTERED on this machine",
                    f"(registered elsewhere as '{row['name']}'; "
                    "run: conspire register)")
    return ("UNREGISTERED",
            "(ask the user: register via `conspire register`, or opt out)")


def cmd_session_start(args):
    home = home_repo()
    cmd_sync(argparse.Namespace(quiet=True))
    tag = machine_tag() or "UNSET (run: conspire bootstrap)"
    proj = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    state, detail = memory_state(home, proj)
    print("conspire session status")
    print(f"  machine:  {tag}")
    print(f"  project:  {proj}")
    print(f"  memory:   {state} {detail}")
    print(f"  sync:     {sync_status_line(home)}")
    print("Claude: surface this block briefly in your first reply. If memory is")
    print("UNREGISTERED, poll the user: version-controlled memory, or opt out?")
    return 0


def cmd_session_end(args):
    # Stamp only, permanently: SessionEnd output goes nowhere and the
    # harness kills the hook ~1-2s in, so a sync failure here --
    # including a pre-commit refusal -- would be invisible and
    # unmanageable. A manual `conspire sync` at wrap-up and the next
    # session-start sync cover the gap.
    home = home_repo()
    stamp = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    tag = machine_tag() or "unset-machine"
    with open(home / ".session-end.log", "a", encoding="utf-8") as fh:
        fh.write(f"{stamp} {tag} {os.getcwd()}\n")
    return 0


# ------------------------------------------------------------------ index

def parse_frontmatter(text):
    """(name, description, problems) from a YAML-subset frontmatter block."""
    if not text.startswith("---"):
        return None, None, []
    end = text.find("\n---", 3)
    if end < 0:
        return None, None, ["unterminated frontmatter"]
    lines = text[3:end].splitlines()
    fields, problems = {}, []
    i = 0
    while i < len(lines):
        m = re.match(r"^(name|description):[ \t]*(.*)$", lines[i])
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val in ("", ">", "|", ">-", "|-"):
                # block scalar: gather the following indented lines
                block, j = [], i + 1
                while j < len(lines) and (not lines[j].strip()
                                          or lines[j][:1] in (" ", "\t")):
                    if lines[j].strip():
                        block.append(lines[j].strip())
                    j += 1
                val, i = " ".join(block), j - 1
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                inner = val[1:-1]
                if val[0] not in inner:
                    val = inner
                else:
                    problems.append(f"{key}: ambiguous quoting left as-is")
            if val:
                fields[key] = val
        i += 1
    return fields.get("name"), fields.get("description"), problems


def first_body_line(text):
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end >= 0:
            body = text[end + 4:]
    for line in body.splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line
    return "(empty)"


def build_index(store):
    """Return (content, warnings). Never raises on a bad memory file."""
    entries, warnings, names = [], [], {}
    files = sorted(p for p in store.iterdir()
                   if p.is_file() and p.suffix.lower() == ".md"
                   and p.name != "MEMORY.md")
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception as e:
            warnings.append(f"{store.name}/{f.name}: unreadable ({e}); skipped")
            continue
        name, desc, probs = parse_frontmatter(text)
        warnings.extend(f"{store.name}/{f.name}: {p}" for p in probs)
        if name is None and desc is None:
            warnings.append(f"{store.name}/{f.name}: no frontmatter "
                            "(using filename + first line)")
        if name and name != f.stem:
            warnings.append(f"{store.name}/{f.name}: name '{name}' != filename stem")
        title = name or f.stem
        if title in names:
            warnings.append(f"{store.name}/{f.name}: duplicate name '{title}' "
                            f"(also {names[title]})")
        names[title] = f.name
        entries.append(f"- [{title}]({f.name}) — {desc or first_body_line(text)}")
    content = "\n".join(["# Memory index", ""] + entries) + "\n"
    return content, warnings


def memory_stores(home):
    mem = home / "memory"
    if not mem.is_dir():
        return []
    return sorted(p for p in mem.iterdir() if p.is_dir())


def cmd_index(args):
    home = home_repo()
    stores = ([Path(s) for s in args.stores] if args.stores
              else memory_stores(home))
    rc = 0
    for store in stores:
        if not store.is_dir():
            print(f"error: not a directory: {store}", file=sys.stderr)
            rc = 1
            continue
        content, warnings = build_index(store)
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        n_lines, n_bytes = content.count("\n"), len(content.encode("utf-8"))
        if n_lines > MAX_LINES or n_bytes > MAX_BYTES:
            print(f"error: {store}/MEMORY.md would be {n_lines} lines / "
                  f"{n_bytes} bytes; limits are {MAX_LINES} lines / "
                  f"{MAX_BYTES} bytes (content past the limit silently never "
                  "loads). Merge or prune memories.", file=sys.stderr)
            rc = 1
            continue
        target = store / "MEMORY.md"
        if args.check:
            on_disk = (target.read_text(encoding="utf-8")
                       if target.is_file() else None)
            if on_disk == content:
                print(f"ok: {target} ({n_lines} lines, {n_bytes} bytes)")
            else:
                print(f"STALE: {target} does not match its files "
                      "(commit to regenerate, or run: conspire index)")
                rc = 1
        else:
            with open(target, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)
    return rc


# --------------------------------------------------------------- register

def upsert_registry(home, name, idents, decision):
    reg = registry_path(home)
    lines = (reg.read_text(encoding="utf-8").splitlines()
             if reg.is_file() else ["name\tremotes\tdecision\tdate"])
    out, found = [], False
    for ln in lines:
        f = ln.split("\t")
        if len(f) == 4 and f[0] == name:
            found = True
            have = f[1].split()
            f[1] = " ".join(have + [r for r in idents if r not in have])
            out.append("\t".join(f))
        else:
            out.append(ln)
    if not found:
        out.append("\t".join([name, " ".join(idents), decision,
                              date.today().isoformat()]))
    with open(reg, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")
    verb = "merged remotes into" if found else "recorded"
    print(f"registry: {verb} '{name}' ({decision})")


def cmd_register(args):
    home = home_repo()
    top = git("rev-parse", "--show-toplevel", cwd=Path.cwd())
    proj = Path(top.stdout.strip()) if top.returncode == 0 else Path.cwd()

    url = None
    for r in dict.fromkeys(["upstream", "origin"] + remote_names(proj)):
        u = git("remote", "get-url", r, cwd=proj)
        if u.returncode == 0 and u.stdout.strip():
            url = u.stdout.strip()
            break
    if url:
        base = re.sub(r"\.git$", "", url.rstrip("/").rsplit("/", 1)[-1])
    else:
        base = proj.name
        print("note: no git remote found; defaulting to directory name")
    default = base.lower().replace("_", "-")

    idents = sorted(project_remotes(proj)) or [f"path:{proj}"]
    print(f"project:  {proj}")
    print(f"remotes:  {' '.join(idents)}")
    name = input(f"canonical name [{default}]: ").strip() or default
    if not re.fullmatch(r"[a-z0-9-]+", name):
        print("error: name must match [a-z0-9-]+")
        return 1

    # Existing row? Checked BEFORE any write, so a name collision can't
    # silently point a different project at this name's store.
    row = next((r for r in registry_rows(home) if r["name"] == name), None)
    if row:
        decision = row["decision"]
        if set(idents) & set(row["remotes"]):
            print(f"registry: '{name}' already recorded "
                  f"(decision: {decision})")
            if input(f"wire {proj} to memory/{name}? [y/N]: "
                     ).strip().lower() != "y":
                print("nothing written")
                return 1
        else:
            print(f"registry: '{name}' is already recorded for: "
                  f"{' '.join(row['remotes'])}")
            if input("same project under a new remote? [y/N]: ").strip().lower() != "y":
                print(f"leaving '{name}' untouched; re-run and choose a different name")
                return 1
            print(f"registry: will merge this clone's remotes into '{name}'")
    else:
        decision = input(f"memory: version-controlled in {tilde(home)}, "
                         "or machine-local? [in/out]: ").strip()
        if decision not in ("in", "out"):
            print("error: answer 'in' or 'out'")
            return 1

    if decision == "in":
        (home / "memory" / name).mkdir(parents=True, exist_ok=True)
        memdir = f"{tilde(home)}/memory/{name}"
        sf = proj / ".claude" / "settings.local.json"
        try:
            settings = (json.loads(sf.read_text(encoding="utf-8"))
                        if sf.is_file() else {})
        except Exception as e:
            print(f"error: {sf} is not valid JSON ({e}); "
                  "fix it and re-run -- nothing recorded")
            return 1
        settings["autoMemoryDirectory"] = memdir
        sf.parent.mkdir(parents=True, exist_ok=True)
        sf.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        print(f"wrote autoMemoryDirectory -> {memdir} in {sf}")

    upsert_registry(home, name, idents, decision)
    print("done. Sync will pick this up (or run: conspire sync)")
    return 0


# ------------------------------------------------------------------ check

def instruction_stubs(home):
    """(target, import) pairs: every <home>/claude/*.md gets a one-line
    @import stub of the same name in ~/.claude/."""
    return [(CLAUDE_DIR / f.name, f"{tilde(home)}/claude/{f.name}")
            for f in sorted((home / "claude").glob("*.md"))]


def _in_repo(path, repo):
    try:
        path.resolve().relative_to(repo.resolve())
        return True
    except ValueError:
        return False


def cmd_check(args):
    home = home_repo()
    rc = 0

    def ok(msg):
        print(f"ok: {msg}")

    def fail(msg):
        nonlocal rc
        print(f"BROKEN: {msg}")
        rc = 1

    ok(f"home repo {home}")

    env_tag = os.environ.get("CONSPIRE_MACHINE", "").strip()
    if env_tag:
        ok(f"machine tag '{env_tag}' (env CONSPIRE_MACHINE)")
    elif (CONF_DIR / "machine").is_file():
        ok(f"machine tag '{machine_tag()}' ({CONF_DIR / 'machine'})")
    elif (CLAUDE_DIR / "machine-id").is_file():
        fail(f"machine tag only in legacy {CLAUDE_DIR / 'machine-id'} "
             "(run bootstrap to migrate)")
    else:
        fail("no machine tag (run bootstrap)")

    launcher = USER_HOME / ".local" / "bin" / "conspire"
    if launcher.is_symlink() and launcher.resolve() == (TOOL / "bin" / "conspire").resolve():
        ok(f"{launcher} -> {TOOL / 'bin' / 'conspire'}")
    elif launcher.is_file():
        if filecmp.cmp(launcher, TOOL / "bin" / "conspire", shallow=False):
            ok(f"{launcher} (copy, in sync)")
        else:
            fail(f"{launcher} is a copy that has drifted (re-run bootstrap)")
    else:
        fail(f"{launcher} missing (run bootstrap)")

    hp = git("config", "core.hooksPath", cwd=home)
    want = str(TOOL / "hooks")
    if hp.stdout.strip() == want:
        ok(f"core.hooksPath = {want}")
    else:
        fail(f"core.hooksPath is '{hp.stdout.strip() or 'unset'}', "
             f"expected '{want}' (run bootstrap)")

    for target, imp in instruction_stubs(home):
        if not target.exists():
            fail(f"{target} missing (run bootstrap)")
        elif target.is_symlink():
            ok(f"{target} (symlink; stub preferred but functional)")
        elif f"@{imp}" in [ln.strip() for ln in
                           target.read_text(encoding="utf-8").splitlines()]:
            ok(f"{target} -> @{imp}")
        else:
            fail(f"{target} exists but lacks '@{imp}' (an installer may have "
                 "overwritten it; re-run bootstrap, then merge its content "
                 "into the repo copy)")

    sj, repo_sj = CLAUDE_DIR / "settings.json", home / "claude" / "settings.json"
    if not repo_sj.is_file():
        ok("no claude/settings.json in home repo (not managed)")
    elif sj.is_symlink():
        if _in_repo(sj, home):
            ok(f"{sj} (symlink into home repo)")
        else:
            fail(f"{sj} symlinks outside the home repo")
    elif sj.is_file():
        if filecmp.cmp(sj, repo_sj, shallow=False):
            ok(f"{sj} (copy, in sync with home repo)")
        else:
            fail(f"{sj} is a copy that has drifted from claude/settings.json "
                 "(re-run bootstrap or reconcile by hand)")
    else:
        fail(f"{sj} missing (run bootstrap)")

    for name in ("output-styles", "skills"):
        osd, repo_osd = CLAUDE_DIR / name, home / "claude" / name
        if not repo_osd.is_dir():
            ok(f"no claude/{name} in home repo (not managed)")
        elif osd.is_symlink():
            if _in_repo(osd, home):
                ok(f"{osd} (symlink into home repo)")
            else:
                fail(f"{osd} symlinks outside the home repo")
        elif osd.is_dir():
            d = filecmp.dircmp(osd, repo_osd)
            if not (d.diff_files or d.left_only or d.right_only or d.funny_files):
                ok(f"{osd} (copy, in sync with home repo)")
            else:
                fail(f"{osd} is a copy that has drifted from claude/{name} "
                     "(re-run bootstrap or reconcile by hand)")
        else:
            fail(f"{osd} missing (run bootstrap)")

    # Index freshness AND limits: regenerate in memory, compare to disk.
    if cmd_index(argparse.Namespace(check=True, stores=[])) == 0:
        ok("memory indexes fresh and within load limits")
    else:
        fail("a MEMORY.md is stale or over load limits (see above)")

    # Kiro bridge (only on machines with ~/.kiro): mirror present,
    # steering placed, cron actually firing (last-sync mtime; assumes
    # at-least-daily cron, so >25h means it stopped).
    kiro = USER_HOME / ".kiro"
    if kiro.is_dir():
        mirror = kiro / "conspire"
        last = mirror / "last-sync"
        if not mirror.is_dir():
            fail(f"{mirror} missing (run: conspire kiro-sync)")
        elif not last.is_file():
            fail(f"{last} missing (run: conspire kiro-sync)")
        else:
            age_h = (time.time() - last.stat().st_mtime) / 3600
            if age_h > 25:
                fail(f"kiro mirror last synced {age_h:.0f}h ago — cron "
                     "dead? (run `conspire kiro-sync` by hand; check crontab)")
            else:
                ok(f"kiro mirror synced {age_h:.1f}h ago")
        missing = [f.name for f in kiro_steering_files(home)
                   if not (kiro / "steering" / f.name).is_file()]
        if missing:
            fail("kiro steering missing: " + " ".join(missing)
                 + " (run: conspire kiro-sync)")
        else:
            ok(f"kiro steering files present ({kiro / 'steering'})")

    return rc


# -------------------------------------------------------------- kiro-sync

def kiro_steering_files(home):
    """Steering shipped with the tool, then the home repo's own
    kiro/steering/*.md (same name in both: the home repo wins)."""
    files = {}
    for d in (TOOL / "templates" / "kiro" / "steering",
              home / "kiro" / "steering"):
        if d.is_dir():
            for f in sorted(d.glob("*.md")):
                files[f.name] = f
    return [files[k] for k in sorted(files)]


def cmd_kiro_sync(args):
    home = home_repo()
    kiro = USER_HOME / ".kiro"
    if not kiro.is_dir():
        return 0                      # not a Kiro machine; nothing to do
    mirror = kiro / "conspire"
    mirror.mkdir(parents=True, exist_ok=True)

    # 1. inbox pull: drafts move into the repo, quarantined under inbox/.
    inbox_root = mirror / "inbox"
    if inbox_root.is_dir():
        for d in sorted(p for p in inbox_root.iterdir() if p.is_dir()):
            store = home / "memory" / d.name
            if not store.is_dir():
                print(f"kiro-sync: unknown store in inbox: {d.name} (skipped)")
                continue
            for f in sorted(d.glob("*.md")):
                (store / "inbox").mkdir(exist_ok=True)
                shutil.move(str(f), str(store / "inbox" / f.name))
                print(f"kiro-sync: inbox draft {d.name}/{f.name} -> repo")

    # 2. git sync
    cmd_sync(argparse.Namespace(quiet=True))

    # 3. mirror push: DERIVED, never authoritative; delete-then-copy so
    # removed/renamed memories don't linger. Paths are constructed here,
    # never taken from input, so the rmtree targets are exactly the mirror.
    for sub in ("memory", "claude"):
        target = mirror / sub
        if target.exists():
            shutil.rmtree(target)
        if (home / sub).is_dir():
            shutil.copytree(home / sub, target)
    if registry_path(home).is_file():
        shutil.copy2(registry_path(home), mirror / "memory-registry.tsv")
    for s in memory_stores(home):
        (mirror / "inbox" / s.name).mkdir(parents=True, exist_ok=True)
    tag = machine_tag()
    if tag:
        (mirror / "machine").write_text(tag + "\n", encoding="utf-8")
    (mirror / "last-sync").write_text(
        datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z") + "\n",
        encoding="utf-8")
    steering = kiro / "steering"
    steering.mkdir(parents=True, exist_ok=True)
    for f in kiro_steering_files(home):
        shutil.copy2(f, steering / f.name)
    return 0


# -------------------------------------------------------------- bootstrap

def _backup(path):
    """Timestamped sibling backup; never nests, never overwrites."""
    b = path.with_name(path.name + ".pre-bootstrap."
                       + datetime.now().strftime("%Y%m%d-%H%M%S"))
    if path.is_dir() and not path.is_symlink():
        shutil.copytree(path, b)
    else:
        shutil.copy2(path, b)
    print(f"  (backed up {path} -> {b})")


def _link_or_copy(src, dst):
    """Symlink dst -> src; where symlinks fail (Windows without
    privileges), copy instead. A differing real file/dir is backed up."""
    if dst.is_symlink():
        if dst.resolve() == src.resolve():
            print(f"ok: {dst} -> {src} (already linked)")
            return
        dst.unlink()
    elif dst.is_dir():
        d = filecmp.dircmp(dst, src)
        if d.diff_files or d.left_only or d.right_only or d.funny_files:
            _backup(dst)
        shutil.rmtree(dst)
    elif dst.exists():
        if not filecmp.cmp(dst, src, shallow=False):
            _backup(dst)
        dst.unlink()
    try:
        os.symlink(src, dst, target_is_directory=src.is_dir())
        print(f"symlinked {dst} -> {src}")
    except OSError:
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        print(f"copied {src} -> {dst} "
              "(symlink unavailable; re-run bootstrap after repo edits)")


def cmd_bootstrap(args):
    home = home_repo()
    print(f"== conspire bootstrap (home repo: {home}) ==")
    CONF_DIR.mkdir(parents=True, exist_ok=True)
    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. machine tag: chosen, not detected; hostname only seeds the
    # default. A legacy ~/.claude/machine-id is migrated, not re-asked.
    idfile = CONF_DIR / "machine"
    legacy = CLAUDE_DIR / "machine-id"
    if idfile.is_file():
        print(f"machine tag: {idfile.read_text(encoding='utf-8').strip()} "
              f"(from {idfile}; delete it to re-choose)")
    elif legacy.is_file():
        shutil.copy2(legacy, idfile)
        print(f"machine tag: {idfile.read_text(encoding='utf-8').strip()} "
              f"(migrated from {legacy}; the old file may be deleted)")
    else:
        default = re.sub(r"[^a-z0-9-]", "-",
                         platform.node().split(".")[0].lower()) or "mymachine"
        tag = input(f"machine tag for this machine [{default}]: ").strip() or default
        if not re.fullmatch(r"[a-z0-9-]+", tag):
            print("error: tag must match [a-z0-9-]+")
            return 1
        idfile.write_text(tag + "\n", encoding="utf-8")
        print(f"machine tag: {tag} -> {idfile}")

    # 2. launcher on PATH
    bin_dir = USER_HOME / ".local" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    _link_or_copy(TOOL / "bin" / "conspire", bin_dir / "conspire")
    if shutil.which("conspire") is None:
        print(f"  NOTE: {bin_dir} is not on PATH; add it in your shell profile")

    # 3. versioned git hooks, served from the tool repo
    r = git("config", "core.hooksPath", str(TOOL / "hooks"), cwd=home)
    if r.returncode != 0:
        print(f"error: git config failed: {git_said(r)}")
        return 1
    print(f"git hooks: core.hooksPath = {TOOL / 'hooks'}")

    # 4. instruction stubs: real one-line @import files, Windows-safe.
    # Any differing existing file is backed up -- including one that
    # contains the stub line plus extra content (e.g. an installer's block).
    for target, imp in instruction_stubs(home):
        desired = f"@{imp}\n"
        if target.is_symlink():
            target.unlink()
        elif target.is_file():
            if target.read_text(encoding="utf-8") == desired:
                print(f"stub: {target} ok")
                continue
            _backup(target)
            target.unlink()
        target.write_text(desired, encoding="utf-8")
        print(f"stub: {target} -> @{imp}")

    # 5. settings.json, output-styles, skills: no import mechanism exists,
    # so symlink (copy where symlinks aren't available). Each only if the
    # home repo has it.
    for name in ("settings.json", "output-styles", "skills"):
        src = home / "claude" / name
        if src.exists():
            _link_or_copy(src, CLAUDE_DIR / name)

    print()
    print("done. Verify with: conspire check")
    print("Register projects by running inside each: conspire register")
    return 0


# ------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(prog="conspire",
                                 description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="point conspire at a home repo")
    p.add_argument("path", help="the home repo (data) directory")
    p.add_argument("--new", action="store_true",
                   help="create it from templates/home and git init")
    p.set_defaults(fn=cmd_init)

    sub.add_parser("bootstrap", help="one-time machine setup").set_defaults(
        fn=cmd_bootstrap)
    sub.add_parser("check", help="verify this machine's wiring").set_defaults(
        fn=cmd_check)

    p = sub.add_parser("sync", help="commit, ff-only pull, push")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(fn=cmd_sync)

    sub.add_parser("register", help="register this project").set_defaults(
        fn=cmd_register)

    p = sub.add_parser("index", help="regenerate MEMORY.md indexes")
    p.add_argument("--check", action="store_true",
                   help="verify freshness and limits; write nothing")
    p.add_argument("stores", nargs="*", help="store dirs (default: memory/*/)")
    p.set_defaults(fn=cmd_index)

    sub.add_parser("session-start", help="sync + status block").set_defaults(
        fn=cmd_session_start)
    sub.add_parser("session-end", help="stamp log (no sync, by design)").set_defaults(
        fn=cmd_session_end)
    sub.add_parser("kiro-sync", help="bridge ~/.kiro (Kiro machines)").set_defaults(
        fn=cmd_kiro_sync)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
