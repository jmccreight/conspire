# My conspire memory repo

Claude Code instruction files, settings, and memory stores, synced
across machines by [conspire](https://github.com/jmccreight/conspire).

    claude/
      CLAUDE.md           global instructions (stubbed into ~/.claude/CLAUDE.md)
      settings.json       Claude Code user settings incl. the session hooks
      output-styles/      optional; linked to ~/.claude/output-styles
      skills/             optional; linked to ~/.claude/skills
    memory/<name>/        one auto-memory store per project family
    memory-registry.tsv   which projects are in (version-controlled) or out
    kiro/steering/        optional; extra Kiro steering files (see conspire README)

Every other `claude/*.md` file also gets a one-line stub in `~/.claude/`,
so a project's CLAUDE.md can import it as `@~/.claude/<name>.md`.

Daily use: nothing -- session start syncs. At wrap-up: `conspire sync`.
New machine: clone this repo, then

    git clone <conspire> ~/conspire
    ~/conspire/bin/conspire init <this repo>
    conspire bootstrap
    conspire check
