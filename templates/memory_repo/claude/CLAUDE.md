# Global instructions (all projects, all machines)

This file is loaded on every machine through the one-line stub
`~/.claude/CLAUDE.md` that `conspire bootstrap` writes. Add your own
sections below the conspire ones.

## Session startup

A SessionStart hook (`conspire session-start`) injects a status block:
machine tag, project, and the project's memory state. Surface that
block at the top of your first reply, in exactly this form -- same
lines, same order, only the values after each colon change:

    *conspire session status:*
    - machine: <tag>
    - project: <path>
    - memory: version controlled -> <store path>
    - sync: in sync with origin

The four values come from the hook's `machine:`, `project:`, `memory:`
and `sync:` lines -- same words, only lowercased. Add nothing else to
the block.

If the memory line says UNREGISTERED, ask me -- version-controlled
memory or opt out? -- and on my answer run `conspire register` inside
the project (it prompts for a name and in/out). If the hook says the
store is over its prune limits, suggest `/memory-prune` once, in your
first reply, after the block.

## Memory conventions

My memory stores live in a git repo managed by conspire. Session start
syncs automatically; session end does not -- when I wrap up a session
by asking whether memory is up to date, remind me to run
`conspire sync`.

- Facts tied to a machine (paths, environment names, which clone holds
  which branch) must name the machine tag. Machine-neutral facts need
  no tag.
- The `description:` frontmatter field IS the index line: MEMORY.md is
  generated from frontmatter by a pre-commit hook, never hand-edited.
  Write descriptions to stand alone; after writing a memory file, do
  NOT append to MEMORY.md.
- Ignore `inbox/` subdirectories in memory stores when recalling; they
  hold unreviewed drafts from other harnesses. When asked to review an
  inbox, promote each draft to a proper top-level memory (correct
  frontmatter, machine tag) or delete it.
- Unfinished work goes under a line reading exactly `**Open:**`, one
  action per bullet, imperative, with enough context to stand alone.
