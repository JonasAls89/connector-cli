# Guardrails

## Context size

- Instruction and context files (`AGENTS.md`, `.github/copilot-instructions.md`, `.github/instructions/*`, `docs/*.md`) stay under 8000 bytes each.
- Work items fit one agent context window (about 40000 tokens) and one human review (about 400 changed lines).
- `/wayfinder-context` validates context sizes and links. Invoke it after documentation changes, separately from pre-commit checks.

## Grounding

- Statements about the codebase must be traceable to a file. Relative Markdown links must resolve.
- When information is missing, ask or record an open question; do not invent.
- Decisions are recorded as ADRs in `docs/adr/`.

## Review

- One work item per branch or worktree, reviewed by a human before merge.
