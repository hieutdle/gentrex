# Development

Install the dependencies, including the development tools:

```bash
uv sync
```

Check formatting and lint:

```bash
uv run ruff check . && uv run ruff format --check .
```

Check the types with basedpyright, which reads its settings from
`[tool.basedpyright]` in pyproject.toml:

```bash
uv run basedpyright
```

Run the tests:

```bash
uv run pytest
```

The database tests of `gentrex load` and `gentrex export omop` run on SQLite.
To run them on PostgreSQL and MySQL too, start the servers from step 1 of
[Load report data into a database](../user-guide/load.md#step-1-choose-a-database).
List their addresses in `GENTREX_TEST_DATABASE_URLS`, separated by spaces,
and add the extras that install their drivers:

```bash
GENTREX_TEST_DATABASE_URLS="postgresql://gentrex:gentrex@127.0.0.1:5432/gentrex mysql://root:gentrex@127.0.0.1:3306/mysql" uv run --extra postgresql --extra mysql pytest
```

Each test creates its own database on the server and drops it afterwards, so
the tests leave your loaded reports alone. The user in the address must be
allowed to create databases. On the servers from step 1, that is `gentrex` on
PostgreSQL and `root` on MySQL.

CI runs these checks and the tests for every push to `master` and every pull
request, on Python 3.12, 3.13 and 3.14.

To run the lint and format checks on every commit, install the git hook once:

```bash
uv run pre-commit install
```

Contribution rules are in [AGENTS.md](../../AGENTS.md).
