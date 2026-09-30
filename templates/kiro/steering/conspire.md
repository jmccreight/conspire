---
inclusion: always
---

# conspire bridge: the user's cross-machine instructions and memory

The user works across machines and harnesses; their durable
instructions and memory live in a git repo your sandbox cannot see.
This machine's `~/.kiro/conspire/` is a read-only mirror of it,
refreshed by cron; `~/.kiro/conspire/last-sync` holds the refresh
time -- read it and state the mirror's age in your status block.
Everything under it except `inbox/` is DERIVED: never edit it -- your
edits would be silently overwritten.

## Ground rules

Read `~/.kiro/conspire/claude/CLAUDE.md` -- the user's global ground
rules and working preferences. They apply in full here; translate
Claude-Code-specific mechanisms (session hooks, `/context`, slash
skills) to their Kiro equivalents rather than skipping them.

## Memory: read

Before any substantial task, find this workspace's memory store: take
the workspace's git remote URL, reduce it to `host/owner/repo`
(lowercase, no scheme, user, port, or `.git`), and look it up in the
`remotes` column of `~/.kiro/conspire/memory-registry.tsv`. The row's
`name` is the store: read `~/.kiro/conspire/memory/<name>/MEMORY.md`,
then open the topic files relevant to the task. A row whose
`decision` is `out`, or no row at all, means no store: say so and
proceed without memory.

Ignore `inbox/` subdirectories when recalling: they are unreviewed
drafts. Memories may state facts tied to a specific machine (paths,
environments, clones) -- check the named machine tag against this
machine's, in `~/.kiro/conspire/machine`, before acting on them.

## Memory: write (drafts only)

You do not write to the store. When something durable emerges -- a
correction from the user, a confirmed approach, project state not
derivable from the code -- write a DRAFT to
`~/.kiro/conspire/inbox/<name>/<kebab-slug>.md`:

    ---
    name: <kebab-slug>
    description: <one line that can stand alone in an index>
    metadata:
      type: user | feedback | project | reference
    ---

    <the fact. For feedback/project add **Why:** and **How to apply:**
    lines. Name the machine tag for any machine-specific fact.>

A Claude Code session later reviews the inbox: promotes drafts into the
store or deletes them. Write drafts sparingly and factually -- they are
proposals, not records. Do not create or update any other notes files.
