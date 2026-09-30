# Free market check

Is anyone selling what conspire does, but better? Surveyed 2026-09-30
from READMEs only. Answer: no.

## What conspire is for

- Memory is plain Markdown in a private git repo you own. Readable,
  diffable, greppable, prunable by hand.
- Synced across machines by git. No machine is special.
- One store per project. Written on purpose by the assistant, one
  fact per file, indexed from frontmatter, kept lean.
- Carries the assistant config too: instructions, settings, skills,
  output styles, session hooks.
- Python standard library. Nothing runs in the background.

## The market

| | files in git | machine sync | who writes | pruning | must run | maturity | verdict |
|---|---|---|---|---|---|---|---|
| **conspire** | yes | git | assistant, on purpose | by hand | nothing | small, in daily use | keep |
| [agentcairn](https://github.com/ccf/agentcairn) | yes, Markdown vault | none | transcript scraping | keeps everything, marks it superseded | nothing | docs, benchmarks | grows forever |
| [rill.md](https://github.com/rillmd/rill) | yes | none stated | you, then "AI thinks" | none | a Mac app | v0.1.2 | a journal app; "AI remembers. Rill thinks." |
| [memmy-agent](https://github.com/MemTensor/memmy-agent) | not stated | not stated | automatic | not stated | two systemd services and an HTTP port | 2,000 stars | wants to be your "identity layer"; won't say where it keeps the data |
| [mcp-memory](https://github.com/fellowgeek/mcp-memory) | yes, Markdown plus SQLite index | none | assistant, on purpose | `stale_after` field nobody reads | nothing | 218 stars, 16 commits | star-farmed; guessing an expiry date up front is not pruning |
| [memloom](https://github.com/memloom/memloom) | no, PostgreSQL | none (Notion) | both | flags contradictions, keeps them | a daemon | 15 stars | "fused in SQL" |
| [AliceMemory](https://github.com/samrusani/AliceMemory) | no, SQLite/Postgres | "one operator, one machine" | assistant proposes, policy decides | none | an MCP server, or Docker plus two ports | 4 stars, one maintainer, alpha, mostly AI-written | honest; refuses transcript scraping, which is right |
| [agentic-memory](https://github.com/agentralabs/agentic-memory) | no, one binary `.amem` | copy the file | assistant, optional automatic | never deletes, 20-year "immortal" plan | nothing | 26 stars, "peer-reviewed papers included" | a binary graph that hoards; opposite of lean |

## Pattern

- Two of seven keep plain files. Zero sync through git. Zero prune.
- What they sell instead: search, daemons, databases, graphs, vectors.
  Not asked for.
- The louder the README, the less it says about where the bytes live.
