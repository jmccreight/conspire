# Developer notes

## Your memory repo structure, by example

`~/my_claude_memories` after registering two projects and opting out a third:

```
~/my_claude_memories/
  claude/
    CLAUDE.md            # ~/.claude/CLAUDE.md contains only: "@~/my_claude_memories/claude/CLAUDE.md"
    settings.json        # ~/.claude/settings.json symlinks here; carries the session hooks
    output-styles/       # optional; ~/.claude/output-styles symlinks here
    skills/              # optional; each skill linked into ~/.claude/skills/<name>
                         # (never a `synced/` dir: ~/.claude/skills/synced/ is Claude
                         # Code's cache of account skills, not linked, not synced)
  memory/
    project_one/         # project store for every clone of project_one, on every machine
      MEMORY.md          # generated index -- never hand-edited
      highlevel-concerns.md
      conda-envs.md      # names machine tags: "on mymacbook ... on the cluster ..."
    project_two/
      MEMORY.md
      release-plan.md
  memory-registry.tsv    # 3 rows: project_one in, project_two in, scratch-repo out
  prune-limits.tsv       # per-store line/char limits for the memory-prune skill
  README.md
```

## Machine identity

`conspire bootstrap` asks you for a short tag for the machine
(`laptop`, `cluster`, ...), offering the hostname as the default. The
tag is stored in `~/.conspire/machine` and used two ways:

- every commit to the memory repo (a git hook does this) ends with a
  `Machine: <tag>` line, so `git log` shows which machine wrote what;
- a memory that states a fact true only on one machine (a path, a
  conda environment, which clone holds which branch) should say which
  machine in its text, e.g. "on laptop, the clone is `~/usgs/pywatershed`".
  The template `CLAUDE.md` tells the agent to do this.

It is asked for rather than detected because hostnames change, and
because two machines can share one.

## The index, MEMORY.md

Each project store (`memory/<name>/`) has a `MEMORY.md`. It is the only
memory file Claude Code loads at session start: one line per memory
file, giving its name and a one-line description, so the agent can
decide which files are worth opening. Claude Code stops reading it past
200 lines or 25 KB, silently. Those limits are not queryable from Claude
Code; they are `MAX_LINES` and `MAX_BYTES` in `conspire.py`, copied from
the memory page of the Claude Code docs
(https://code.claude.com/docs/en/memory), last checked against Claude
Code 2.1.285 on 2026-10-01. Re-check them when Claude Code upgrades.

conspire generates it. The pre-commit hook rebuilds `MEMORY.md` from
the `name:` and `description:` fields at the top of every memory file
and stages it with the commit, and refuses to commit if the result
would exceed those limits. So never edit `MEMORY.md`; write a good
`description:` instead. Generating it also removes the one merge
conflict this layout would otherwise invite: two machines appending
lines to the same file.

A project store may have an `inbox/` subdirectory, which the index
ignores. It holds drafts written by agents that are not trusted to
write memory unattended -- today, Kiro via `conspire kiro-sync`
(below). Review each draft: promote it to a top-level memory file, or
delete it.

## Trust boundary

Nothing in the memory repo is ever executed. The git hooks it uses run
from this tool repo (`core.hooksPath` points at `hooks/`), which only
you update. A compromised memory repo can therefore corrupt memory and
instructions, but cannot run code.

## Never commit transcripts

The memory repo holds instruction files, settings, and `memory/`
content — nothing else. Claude Code's conversation logs, the `*.jsonl`
files under `~/.claude/projects/`, are not memory and must never leave
the machine. Nothing in conspire copies them; the template
`.gitignore` blocks `*.jsonl` as a backstop. Same for
`~/.claude/skills/synced/`, Claude Code's cache of the skills attached
to your account: conspire never links it, and the template
`.gitignore` blocks `/claude/skills/synced/` in case it ever lands in
the repo (it did once, through the old whole-directory skills link).

## Kiro adapter

Everything attached to git — the store format, index generator, both
git hooks, the registry, machine tags — works wherever git works. Only
the session wiring is Claude-Code-specific. Kiro's sandbox additionally
cannot read the memory repo at all, so `conspire kiro-sync` bridges by
copying: a read-only mirror under `~/.kiro/conspire/` (memory, claude,
the registry, the machine tag), steering from `templates/kiro/steering/`
plus the memory repo's own `kiro/steering/*.md` into `~/.kiro/steering/`,
and drafts flowing back from `~/.kiro/conspire/inbox/<store>/` into
`memory/<store>/inbox/`. It exits quietly where `~/.kiro` is absent.

    conspire kiro-sync                                  # by hand
    */15 * * * * "$HOME/.local/bin/conspire" kiro-sync >> /tmp/kiro-sync.log 2>&1

Steering files must keep their `---` frontmatter as the very first
bytes — Kiro ignores them otherwise.

## Layout of this repo

    bin/conspire            # launcher: find python, exec conspire.py
    bin/find_python.sh      # $CONSPIRE_PYTHON, then python3/python on PATH
    conspire.py             # all the machinery (one subcommand per entry point)
    hooks/                  # git hooks served to the memory repo (core.hooksPath)
      prepare-commit-msg    # appends "Machine: <tag>" trailer
      pre-commit            # regenerates + validates every MEMORY.md
    templates/memory_repo/  # starter memory repo
    templates/kiro/         # steering for the Kiro adapter

Machine-local state, all under `~/.conspire/`: `memory_repo` (path of the
memory repo; `$CONSPIRE_MEMORY_REPO` overrides) and `machine` (this machine's
tag; `$CONSPIRE_MACHINE` overrides).

## Roadmap

- Harden support for Kiro
- Support multiple memory repos, e.g. group projects by "areas" such as "memory_personal", "memory_work", "memory_organization_1".
