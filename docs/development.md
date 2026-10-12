# Development

Install the dependencies, including the development tools:

```bash
uv sync
```

Check formatting and lint:

```bash
uv run ruff check . && uv run ruff format --check .
```

To run the lint and format checks automatically on every commit, install the
git hook once:

```bash
uv run pre-commit install
```

Contribution rules are in [AGENTS.md](../AGENTS.md).
