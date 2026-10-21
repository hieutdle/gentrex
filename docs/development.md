# Development

Install the dependencies, including the development tools:

```bash
uv sync
```

Check formatting and lint:

```bash
uv run ruff check . && uv run ruff format --check .
```

Run the tests:

```bash
uv run pytest
```

The tests of stage 5 need a PostgreSQL server, and pytest skips them without
one. To run them, start the server of
[stage 5, step 1](stage5.md#step-1-start-the-postgresql-server), and name it
in `GENTREX_TEST_DATABASE_URL`:

```bash
GENTREX_TEST_DATABASE_URL=postgresql://gentrex:gentrex@127.0.0.1:5432/gentrex uv run pytest
```

Each test creates its tables in a new schema and drops the schema afterwards,
so the tests leave the loaded reports alone.

To run the lint and format checks automatically on every commit, install the
git hook once:

```bash
uv run pre-commit install
```

Contribution rules are in [AGENTS.md](../AGENTS.md).
