# Agent Instructions

Repo-specific rules live in CLAUDE.md (if present) - read it first; it wins over this file.

Issue tracking: **bd** (beads). `bd ready` -> `bd update <id> --status in_progress` ->
`bd close <id>` -> `bd sync`.

## Session completion

1. Run the repo's quality gates (tests/lint) if code changed.
2. Update issue status; file follow-ups as beads.
3. Commit your work (scoped, descriptive messages). `bd sync` for beads changes.
4. Pushing: only if this repo allows it - check CLAUDE.md and respect pre-push hooks.
   Never force-push. If a pre-push hook blocks you, the block is intentional:
   STOP and report - do NOT bypass with --no-verify.
5. Leave uncommitted work only with an explicit note (WORKPLAN/anchor/bead).
