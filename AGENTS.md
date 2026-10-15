# Project Rules & Guidelines for `mdok`

## Development Practices
1. **No Ad-Hoc `python -c` One-Liners**:
   - Never use inline `python -c` commands for testing or exploration.
   - For all tests, diagnostics, and explorations, write proper script files or dedicated pytest test cases.

2. **Test-Driven & Exploratory Unit Tests**:
   - Write exploratory tests in `tests/` and run them via `pytest`.
   - Every core layout feature (centering, column budgeting, alignment, styling) must have automated tests.

3. **Packaging & CLI**:
   - Modern standard `pyproject.toml` structure (`src/mdok`).
   - Clean CLI interface with proper options (`--width`, `--margin`, `--pager`, `--box`, etc.).
   - Installable via `pip install -e .`.


4. **Never Run Git Commands**:
   - Do not invoke `git` commands (status, commit, add, diff, log, etc.). All git operations are managed exclusively by the user.

