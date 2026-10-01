---
name: memory-prune
description: Propose cuts to the current project's memory store -- oversized files, running logs, long descriptions, stale references, duplicates, and Open bullets that git history suggests are done -- and apply only the ones the user approves.
---

Scope: the current project's memory store only -- the directory
named in the system prompt's "persistent file-based memory at"
line. Call it STORE. PROJECT is the repository root of the
working directory. MEMORY_REPO is the path in
`$CONSPIRE_MEMORY_REPO` if set, else in `~/.conspire/memory_repo`.
Skip `MEMORY.md` and `inbox/`.

Start by printing, before any other tool call:

    memory-prune: this run uses read-only git commands
    (git log, git branch) in <PROJECT> and <MEMORY_REPO>.

Limits are per store, in `<MEMORY_REPO>/prune-limits.tsv`
(tab-separated: store, lines, chars, set). The store name is STORE's
directory name; a store with no row uses the `default` row; no file
means default 150 lines, 150 chars. Ask, in these words, then wait
for the answer:

- no row: "No limits for LINES or CHARS have yet been set for pruning
  this project's (<STORE>'s) memory store. Would you like to use the
  defaults of <LINES> for LINES (file length) and <CHARS> for CHARS
  (description: length), or enter your own?"
- row exists: "Limits for pruning this project's (<STORE>'s) memory
  store were set <set note>: <LINES> for LINES (file length) and
  <CHARS> for CHARS (description: length). Use these, or enter your
  own?"

Once answered, write this store's row in `prune-limits.tsv` at once
(creating the file with a header line if needed) with the values
chosen and `set` = `<today> before a run`, unless an existing row
already holds those values. The session-start hook reads this file,
so a run that stops early must not leave the store measured against
the wrong limits.

Then build one report. Change nothing while building it.

0. Every file's creation date and last-change date, from
   `git -C <MEMORY_REPO> log --diff-filter=A --format=%ad --date=short -- <file>`
   and `git -C <MEMORY_REPO> log -1 --format=%ad --date=short -- <file>`.
   Print `file  created  changed  lines`, oldest first. No verdict;
   the user decides.
1. Oversized: files over LINES lines. Print `file  lines`.
2. Running logs: files holding several dated entries where later
   ones supersede earlier ones. Propose the collapsed text: the
   facts that still hold, in present tense, no history.
3. Long descriptions: `description:` over CHARS characters. Propose
   a one-line rewrite that still stands alone as the index line.
4. Stale references: file paths, functions, flags or branch names
   the memory names that no longer exist in PROJECT (search, don't
   guess). Quote the memory line and say what is missing.
5. Duplicates: facts already stated in PROJECT's CLAUDE.md, its
   docs, or another memory file. Name both places.
6. Possibly finished work. For each `**Open:**` bullet and each
   status claim ("branch X, MR pending", "in progress"):
   - SINCE = `git -C <MEMORY_REPO> log -1 --format=%ad --date=short -- <file>`
   - `git -C <PROJECT> log --all --since=<SINCE> --format='%h %ad %s' --date=short`
   - `git -C <PROJECT> branch --all --merged main` (use the
     project's default branch if not main)
   Print each match as `file  bullet  ->  <commit or branch>`.
   These are candidates only; commit subjects mislead both ways.
7. Index warnings: what the pre-commit hook would warn about.
   - `name:` differs from the filename without `.md`. Propose
     renaming the file to match `name:` (the user runs `git mv`),
     unless another memory links `[[the-filename]]`.
   - `description:` wrapped in quotes that also appear inside it
     (`\"`). Propose the line with the outer quotes and
     backslashes removed.
   - No frontmatter, or two files with the same `name:`.

Present the report grouped by check, numbered across the whole
report. Ask which numbers to apply. Apply only those; for a file
deletion, show the file's full text first. After edits, list the
changed files and remind the user to run `conspire sync`.

Finally, ask the user whether LINES and CHARS were about right for
this store. Rewrite the row with the values they settle on and
`set` = `<today> after a run`.
