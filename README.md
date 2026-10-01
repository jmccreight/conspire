# conspire

You have multiple projects and/or multiple machines. Conspire brings
together your agent (primarily Claude Code) instruction files, settings, and auto-memory in one place: your private git repo easily synced across machines.

## Benefits

- Your agent memories are valuable: back them up
- Your agent settings, configurations, and memories ensure continuity of experience: share them across machines and projects
- Your single source of memory: give yourself and your agents views across projects

## Why?

Anthropic declined to build cross-machine memory sync
([claude-code#56793](https://github.com/anthropics/claude-code/issues/56793),
closed "not planned").

The conspire approach is simple: your project memories are stored as markdown and synced to your private git repo.

By putting these in one repo, we reap the additional benefits listed above.

Are we reinventing the wheel? Why not collaborate with its inventor? See [free_market.md](free_market.md) for some comparisons.

## How?

Prerequisites: git, python 3.12+ (stdlib only), bash (Git Bash on Windows). Put `~/.local/bin` on PATH if it isn't.

### TL;DR: overview

0. `git clone https://github.com/jmccreight/conspire.git ~/conspire`
1. `~/conspire/bin/conspire init --new ~/my_claude_memories; ~/conspire/bin/conspire bootstrap`
2. Manually reconcile any clashes with existing files under `~/.claude/` resulting from 1.
3. `conspire check`
4. Start an agent in a new project, agent prompts you to run `conspire register`, opt in.
5. Start an agent in an already registered project: session-start sync is triggered.
6. New ritual: tell the agent you are ending the session and to prepare memory, agent prompts you to run `conspire sync`.

## More details

It's not particularly complex. The following introduction is intended to make the system quite transparent to the human user.

Conspire manages local references to your memory repo and remains separate from it. Your memory repo and its contents are known only to you.

Below, let `~/my_claude_memories` stand for wherever you locate your private memory repo; the name and location are yours to choose.

Also note that conspire commands are described below as being run by the human user and not the agent. This choice is premised on the fact that several of the commands create git history and so are best left as a human responsibility. Individual users may green-light agents to run conspire commands if they so choose.

### Install + bootstrap

Place conspire where you want it, e.g. `git clone https://github.com/jmccreight/conspire.git ~/conspire`.

Running

```
~/conspire/bin/conspire init --new ~/my_claude_memories
~/conspire/bin/conspire bootstrap
```

does approximately:

```
Existing files are moved aside, never merged (only if they differ):
  ~/.claude/CLAUDE.md       ---mv-->  ~/.claude/CLAUDE.md.pre-bootstrap.<timestamp>
  ~/.claude/settings.json   ---mv-->  ~/.claude/settings.json.pre-bootstrap.<timestamp>
  ~/.claude/output-styles/  ---mv-->  ~/.claude/output-styles.pre-bootstrap.<timestamp>/
  ~/.claude/skills/         ---mv-->  ~/.claude/skills.pre-bootstrap.<timestamp>/

Instruction files: ~/.claude/CLAUDE.md becomes a one-line file that
tells Claude Code to read the memory repo's copy instead (one per claude/*.md)
  ~/.claude/CLAUDE.md       contains  "@~/my_claude_memories/claude/CLAUDE.md"
  ~/.claude/<other>.md      contains  "@~/my_claude_memories/claude/<other>.md"

Settings, output styles, skills: symlinks (copies on Windows)
  ~/.claude/settings.json   ---symlink-->  ~/my_claude_memories/claude/settings.json
  ~/.claude/output-styles/  ---symlink-->  ~/my_claude_memories/claude/output-styles/
  ~/.claude/skills/         ---symlink-->  ~/my_claude_memories/claude/skills/

Memory: nothing yet -- one project store (memory/<name>/) per project, created on register
  ~/my_claude_memories/memory/     empty
```

### Reconcile files in ~/.claude/

After install, you'll want to reconcile any files which were moved above. You could diff each `*.pre-bootstrap.*` file (listed above) against the memory repo's starter (`claude/CLAUDE.md`, `claude/settings.json`, etc.), copy what you want to keep into the memory repo, then delete the backup. Once you've finished this work, run `conspire check`.

The conspire conventions found in your new `CLAUDE.md` file instruct the agent on how to use and manage conspire. Conspire conventions in the `CLAUDE.md` also describe **how** to write memories. These may evolve. Currently the main convention is to put unfinished work under a line `**Open:**`. This is a convenient way to help collect work still in progress (i.e. todos).

### Register a new project

Start Claude Code in the project as usual. The session-start hook (details in the next section) will see if the current project is registered and print the conspire status block of the following form:

```
  *Session Status:*
    - machine: <tag>
    - project: <path>
    - memory: unregistered
    - sync: no upstream tracking info
```

If the project is not yet registered, the agent will prompt you to run `conspire register`, from the project root directory.

This command will ask you to:

- Set a canonical name for the project (default is project repo name): e.g. `myproj`
- Opt in or out from version-controlled memory

Your answers are stored in the memory repo's registry (`~/my_claude_memories/memory-registry.tsv`), one row per project, keyed on the git remote URL, so every clone on every machine
gets the same answer without asking again. The line for `myproj` opting in would be,
for example,

```
myproj  github.com/user/myproj  in  2026-10-01
```

If you opted in, this clone's Claude Code now writes memory into the
memory repo because `~/path/to/myproj/.claude/settings.local.json` is written to contain `"autoMemoryDirectory": "~/my_claude_memories/memory/myproj"` and the empty project store
`memory/myproj/` is created.

If you opted out, nothing else changes; memory stays in Claude Code's
default place, local to this machine (`~/.claude/projects/<encoded path>/memory/`).

Then you continue as normal.

At the end of the session comes your new ritual: ask the agent to prepare memory for a `conspire sync`, then the agent prompts you to run the sync (additional details below).

### Work on an already registered project: syncing explained

Start Claude Code in the project as usual. At session start, the hook in `settings.json` runs `conspire session-start`, which syncs via

```
git -C ~/my_claude_memories pull --ff-only
```

Then you'll see the conspire status block (shown in previous section). We'll assume the project is opted in below.

You'll work as usual. Claude reads and writes memories to `~/my_claude_memories/memory/myproj/` directly. Edits land in the working tree, uncommitted.

At wrap-up, you perform your new ritual: ask the agent to prepare memory for session end and sync. The agent will prompt you to run `conspire sync` (from anywhere), which performs the following:

```
cd ~/my_claude_memories
git add -A
git commit -m "sync from <machine tag>"    # pre-commit hook regenerates each MEMORY.md
git pull --ff-only
git push
```

### The memory index

Each project store has an index, `MEMORY.md`: the only memory file
Claude Code loads at project session start with one line per memory file. conspire generates it on commit from every memory file's `description:` field, and refuses the commit if it would exceed Claude Code's load limits. Never edit it by hand. More in [DEVELOPER.md](DEVELOPER.md).

## Known caveats

- **Keep the memory repo private.** All memory that lands in the
  memory repo is automatically shared (committed/pushed/pulled) at relatively high frequency via `conspire sync`. Be sure your memory repo is private and under your control. Nothing should be put in the repo that must not reach every machine.
- **`conspire sync` reports "cannot fast-forward"** when two machines
  have committed since they last agreed. In this case, `conspire sync` never merges for you; run `cd ~/my_claude_memories && git pull --rebase`. The design of one file per memory and a generated index make such conflicts rare.
- **A project with no git remote** is registered by its path, so the
  registry row matches only on machines that share that exact path.
- **Installers that rewrite `~/.claude/CLAUDE.md`** (CodeGraph does)
  replace the one-line pointer with a real file. `conspire check`
  reports it. Fix: re-run `conspire bootstrap`, then copy what the
  installer wrote into the memory repo's `claude/CLAUDE.md`.
- **Cowork desktop sessions** ignore the `@` pointer in
  `~/.claude/CLAUDE.md`; a machine using Cowork needs a real file there.

For more details see [DEVELOPER.md](DEVELOPER.md).
