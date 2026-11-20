# Contributing to Heurisma

Thank you for your interest in improving **Heurisma**!

Because Heurisma is a discipline-enforcing agent skill, we treat skill authoring as **Test-Driven Development (TDD) applied to process documentation** (`RED → GREEN → REFACTOR`).

## How to Contribute

### 1. Proposing a New Discipline Protocol or Rule
Before editing `skills/heurisma/SKILL.md` or `skills/heurisma/references/*.md`:
1. **RED (Baseline):** Add or reference a pressure scenario in `evals/scenarios/` and run it *without* your proposed change. Document the exact failure or rationalization observed.
2. **GREEN (Minimal Change):** Add the smallest, clearest rule or reference entry that fixes the observed failure.
3. **REFACTOR (Verify):** Re-run the scenario *with* your change to confirm compliance and check for new loopholes.

### 2. Contributing to Scripts or Tests
- `skills/heurisma/scripts/validate_report.py` must remain **zero-dependency** (Python 3 standard library only).
- Write failing unit tests in `tests/` before implementing changes.
- Run the full local test suite before opening a PR:
  ```bash
  python3 -m unittest discover -s tests -v
  ```

### 3. Skill Style Guidelines
- All files in this repository must be written in clear, concise **English**.
- Keep `SKILL.md` lean; place heavy domain references in `skills/heurisma/references/`.
- Never summarize the workflow inside the YAML `description` field — keep `description` strictly to triggering conditions (`"Use when..."`).

## Pull Requests
Fill out the PR template, link any relevant issue or evaluation scenario, and make sure GitHub Actions CI passes cleanly.
