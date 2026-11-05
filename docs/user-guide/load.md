# Load report data into a database

`gentrex load` puts the records from `gentrex normalize` into the tables of a
database, so you can ask questions about all your reports in SQL. This query
counts the patients with a neurodevelopmental delay of any kind:

```sql
SELECT count(DISTINCT r.patient_key) AS patients
FROM patient_phenotypes p
JOIN hpo_ancestors a ON a.hpo_id = p.hpo_id
JOIN reports r ON r.file = p.file
WHERE a.ancestor_id = 'HP:0012758' AND p.present;
```

This works because the command also loads the Human Phenotype Ontology (HPO)
with its hierarchy. A query for Neurodevelopmental delay then finds the
features matched to the terms under it, too. A few hundred reports take a few
seconds to load.

The database can be a SQLite file, which needs no server, or a PostgreSQL
or MySQL server. These are the [supported databases](#supported-databases). You
choose in step 1, and the rest of the page is the same for all three.

## Before you start

You need:

- Gentrex installed ([Transcribe PDF pages](transcribe.md#step-1-install)).
- A finished run of `gentrex normalize` in `results/normalize/`.
- The HPO release `data/ontology/hp-base.json` from step 2 of
  [Normalize report data](normalize.md#step-2-build-the-hpo-index), even if
  you ran `gentrex normalize` with `--no-hpo`.
- A machine approved for patient data, because the database contains the
  records of every report.
- [Docker](https://docs.docker.com/get-started/get-docker/) for PostgreSQL or
  MySQL. It runs the server in a container, a package of the server with
  everything it needs. The container takes 1 to 2 GB of disk with the
  database.

On Minerva, use SQLite in the
[interactive session](../minerva/minerva.md#load-report-data-into-a-database)
where you ran `gentrex normalize`.

## Step 1: Choose a database

| Database | Choose it when | What it needs |
| --- | --- | --- |
| SQLite | You query the records yourself, from the machine that runs Gentrex. This fits most projects, and Minerva. | Nothing. The database is one file. |
| PostgreSQL 18 | Several people or programs query the database at once, or your group already runs a PostgreSQL server. | A server. The command below starts one in Docker. |
| MySQL 8.4 | The same as PostgreSQL, when your group runs MySQL. | A server. The command below starts one in Docker. |

### SQLite

There is nothing to start or install. Gentrex creates the database file,
`results/load/gentrex.db`, on the first run. Go on to step 2.

### PostgreSQL

Start PostgreSQL 18 from its official Docker image:

```bash
docker run -d --name gentrex-postgres \
  -e POSTGRES_USER=gentrex \
  -e POSTGRES_PASSWORD=gentrex \
  -p 127.0.0.1:5432:5432 \
  -v gentrex-postgres:/var/lib/postgresql \
  postgres:18
```

This creates the database user `gentrex` with the password `gentrex`, and a
database of the same name. If other people can log in to the machine, choose
your own password, and use it in step 2 too.

`-p 127.0.0.1:5432:5432` opens port 5432 to this machine only, so other
machines can't reach the patient data in the database. With `-v`, the
database lives in `gentrex-postgres`, a Docker volume on the machine's disk,
and stays there when the container is removed. The first run downloads the
image, about 700 MB.

The server is ready when this command prints
`127.0.0.1:5432 - accepting connections`:

```bash
docker exec gentrex-postgres pg_isready -h 127.0.0.1 -U gentrex
```

The first start takes a few seconds longer, while the server sets up the
database. The server runs until you stop it with
`docker stop gentrex-postgres`. `docker start gentrex-postgres` starts it
again, with the database as you left it.

### MySQL

Start MySQL 8.4 from its official Docker image:

```bash
docker run -d --name gentrex-mysql \
  -e MYSQL_ROOT_PASSWORD=gentrex \
  -e MYSQL_DATABASE=gentrex \
  -e MYSQL_USER=gentrex \
  -e MYSQL_PASSWORD=gentrex \
  -p 127.0.0.1:3306:3306 \
  -v gentrex-mysql:/var/lib/mysql \
  mysql:8.4
```

This creates the database `gentrex` and the database user `gentrex` with the
password `gentrex`. The image won't start without a password for `root`, so
`MYSQL_ROOT_PASSWORD` sets one, although Gentrex doesn't use `root`. If other
people can log in to the machine, choose your own passwords.

`-p` and `-v` work as for PostgreSQL, with port 3306 and the volume
`gentrex-mysql`. MySQL 8.4 is a long-term support release. The first run
downloads it, about 1.1 GB.

The server is ready when this command prints `mysqld is alive`:

```bash
docker exec gentrex-mysql mysqladmin ping -h 127.0.0.1 -u gentrex -pgentrex
```

It also warns about the password on the command line, which you can ignore
on your own machine. The first start takes about ten seconds longer, while
the server sets up the database. Stop the server with
`docker stop gentrex-mysql`, and start it again with
`docker start gentrex-mysql`.

## Step 2: Point Gentrex at the database

The database's address goes in `GENTREX_DATABASE_URL` in `.env`. If you have
no `.env` file yet, copy the example file:

```bash
cp .env.example .env
```

The example value is the SQLite file:

```
GENTREX_DATABASE_URL=sqlite:///results/load/gentrex.db
```

For a server, replace it with the address of the server from step 1:

| Database | Address |
| --- | --- |
| SQLite | `sqlite:///results/load/gentrex.db` |
| PostgreSQL | `postgresql://gentrex:gentrex@127.0.0.1:5432/gentrex` |
| MySQL | `mysql://gentrex:gentrex@127.0.0.1:3306/gentrex` |

A server's address has the form `database://user:password@host:port/name`.
If you chose your own password in step 1, put it in place of the second
`gentrex`. Git ignores `.env`, so the password stays out of the repository.

For SQLite, a relative path after `sqlite:///` counts from the folder you
run Gentrex in. The example file goes to `results/load/`, which Git ignores
too. For an absolute path, write four slashes, as in
`sqlite:////data/gentrex/gentrex.db`.

## Step 3: Run

With SQLite:

```bash
uv run --env-file .env gentrex load
```

With a server, add `--extra postgresql` or `--extra mysql`. This installs the
server's driver, the Python package that lets Gentrex connect to it:

```bash
uv run --env-file .env --extra postgresql gentrex load
```

Either command loads `results/normalize/latest`, the newest finished run of
`gentrex normalize`, and writes a run folder like
`results/load/20261021-122822/`. To load another run:

```bash
uv run --env-file .env gentrex load --input results/normalize/20261019-030000
```

Gentrex prints the database it loads into, with the driver after `+`, as in
`loading into sqlite+pysqlite:///results/load/gentrex.db`. A server's
password shows as `***`. On the first run into a database, loading the HPO
terms takes a few seconds and prints
`loaded 19894 HPO terms with 223079 ancestor rows`. Later runs print
`kept the HPO terms, which are from the same release` instead. Then it
prints a line per report, such as `loaded report-01.pdf`, and the count, as
in `loaded 300 of 300 reports in 1 s`.

## Check the result

The records are in the database. The run folder has two files:

| File | Contents |
| --- | --- |
| `run.yaml` | The command, the run of `gentrex normalize` that was loaded, the settings and `hpo_sha256`, the checksum of the HPO release. |
| `log.txt` | What Gentrex printed during the run. |

`results/load/latest` points to the newest finished run
([Runs and results](runs-and-results.md#run-folders)).

### Open the database

Each database has a command-line client for typing queries. End each query
with `;`.

| Database | Open the client | List the tables | Show a table's columns | Quit |
| --- | --- | --- | --- | --- |
| SQLite | `sqlite3 results/load/gentrex.db` | `.tables` | `.schema reports` | `.quit` |
| PostgreSQL | `docker exec -it gentrex-postgres psql -U gentrex` | `\dt` | `\d reports` | `\q` |
| MySQL | `docker exec -it gentrex-mysql mysql -u gentrex -pgentrex gentrex` | `SHOW TABLES;` | `DESCRIBE reports;` | `quit` |

`sqlite3` comes with macOS and most Linux systems. Type `.headers on` and
`.mode column` in it to print query results as a table with column names.
For the servers, `docker exec -it` connects your terminal to the client
inside the container.

### See what each table holds

| Table | One row per |
| --- | --- |
| `reports` | Report, with its report-level fields from `gentrex extract` and their standard values from `gentrex normalize`. |
| `variants` | Variant of a report. |
| `patient_phenotypes` | Clinical feature of a report, with its HPO term. |
| `phenotype_candidates` | Candidate HPO term of a clinical feature, 5 per feature by default (`normalize.hpo.top_k` in settings.yaml). |
| `hpo_terms` | Current HPO term, with its label. |
| `hpo_ancestors` | HPO term and one of its ancestors. |
| `hpo_release` | The HPO release that `hpo_terms` and `hpo_ancestors` were loaded from. It has one row. |
| `schema_version` | The version of the tables. It has one row. |

[Database tables](database-tables.md) lists every column with its type and
contents. The tables are defined in
[`tables.py`](../../src/gentrex/load/tables.py).

Most columns are named after a field of the record. Where
`gentrex normalize` found a standard value for a field, the column of that
name has the standard value, and the column with `_raw` added has the
report's wording. For a report with the date of birth `29-JUN-1984`:

| Column | Holds | Example |
| --- | --- | --- |
| `date_of_birth` | The date from `normalized.date_of_birth`, of the SQL type `date`. | 1984-06-29 |
| `date_of_birth_raw` | The printed date from `data.date_of_birth`, as text. | 29-JUN-1984 |

The same goes for `collection_date`, `received_date`, `test_started_date`,
`report_date`, `specimen_type` and the `gene_symbol` of each variant. Other
`_raw` columns, such as `classification_raw`, keep their names from
`gentrex extract`, because the field without `_raw` is already the category.

A feature that the patient doesn't have gets a row too, with `present` false.
To count the patients with a feature, add `p.present` to the `WHERE` clause,
as the queries on this page do. Otherwise "no hearing impairment" counts as
hearing impairment.

Each database has its own syntax for reading a value inside a JSON column.
You need it for a field that you add to schema.yaml, because only the fields
that Gentrex knows get a column of their own. These queries read `lab_name`
from `record`, to show the syntax:

| Database | Query |
| --- | --- |
| PostgreSQL | `SELECT file, record->'data'->>'lab_name' FROM reports;` |
| MySQL and SQLite | `SELECT file, record->>'$.data.lab_name' FROM reports;` |

SQLite reads `->>` from version 3.38 on. `sqlite3 --version` shows yours.

### Query the tables

The queries on this page run unchanged on all three databases.
[Supported databases](#supported-databases) lists where their results can
differ. To count the reports per result category:

```sql
SELECT overall_result, count(*) AS reports
FROM reports
GROUP BY overall_result
ORDER BY reports DESC, overall_result;
```

For 12 synthetic reports, psql prints:

```
 overall_result | reports
----------------+---------
 positive       |       5
 negative       |       3
 uncertain      |       2
 carrier        |       1
 inconclusive   |       1
(5 rows)
```

To count the patients with a pathogenic or likely pathogenic variant, per
gene:

```sql
SELECT v.gene_symbol, count(DISTINCT r.patient_key) AS patients
FROM variants v
JOIN reports r ON r.file = v.file
WHERE v.classification IN ('pathogenic', 'likely_pathogenic')
GROUP BY v.gene_symbol
ORDER BY patients DESC, v.gene_symbol;
```

`count(DISTINCT r.patient_key)` counts each patient once, even one with
several reports or several variants in the gene.

To list the clinical features whose match the two models disagree on, with
their candidates:

```sql
SELECT p.file, p.text, c.rank, c.hpo_id, c.hpo_label
FROM patient_phenotypes p
JOIN phenotype_candidates c USING (file, phenotype_number)
WHERE NOT p.models_agree
ORDER BY p.file, p.phenotype_number, c.rank;
```

These matches are wrong more often, so check them first
([Normalize report data](normalize.md#check-the-result)).

To read a table in Python with pandas:

```python
import os

import pandas as pd

from gentrex.load import run

engine = run.make_engine(os.environ["GENTREX_DATABASE_URL"])
variants = pd.read_sql("SELECT * FROM variants", engine)
```

`run.make_engine` opens the database in `GENTREX_DATABASE_URL` the same way
`gentrex load` does, so one address works for all three databases.
`uv run --env-file .env --with pandas python` starts Python with pandas and
the address set. With a server, add its extra as in step 3.

## How it works

### Turn records into rows

Each line of `normalized.jsonl` becomes one row in `reports`. Each item of
`data.variants` becomes a row in `variants`, and each item of
`data.patient_phenotypes` a row in `patient_phenotypes`, with its candidates
in `phenotype_candidates`. A report without data, from a failed request in
`gentrex extract`, gets no rows, so it can't count as a patient. It is listed
among the failed files instead.

### Link reports to patients

One patient can have several reports, for example a panel and later an exome.
If you count reports, that patient counts twice. So each report gets a
`patient_key`, and reports with the same key count as one patient.

The reports share no patient ID, only what each laboratory printed. The key
comes from the first of these that the report has:

1. Its MRN, as in `mrn:SYN-MRN-0001`.
2. Its submitter patient ID, as in `submitter:SYN-SUB-0002`.
3. Its file name, as in `file:report-04.pdf`. The report then counts as a
   patient of its own.

Four reports get these keys:

| file | mrn | submitter_patient_id | patient_key |
| --- | --- | --- | --- |
| report-01.pdf | SYN-MRN-0001 | | `mrn:SYN-MRN-0001` |
| report-02.pdf | SYN-MRN-0001 | SYN-SUB-0002 | `mrn:SYN-MRN-0001` |
| report-03.pdf | | SYN-SUB-0002 | `submitter:SYN-SUB-0002` |
| report-04.pdf | | | `file:report-04.pdf` |

Reports 01 and 02 share the MRN, so they count as one patient. Report 03
counts as a second patient, although report 02 shows that SYN-SUB-0002 is the
same person. Gentrex doesn't follow such links. This query lists the
submitter IDs that appear with more than one key, and the keys:

```sql
SELECT DISTINCT submitter_patient_id, patient_key
FROM reports
WHERE submitter_patient_id IN (
    SELECT submitter_patient_id
    FROM reports
    WHERE submitter_patient_id IS NOT NULL
    GROUP BY submitter_patient_id
    HAVING count(DISTINCT patient_key) > 1)
ORDER BY submitter_patient_id, patient_key;
```

There is no table of patients. Each report keeps the date of birth and sex
that it printed, so you can see when the reports of one patient disagree.
Suppose `gentrex extract` misread the date of birth on the second of two
reports. Both dates remain:

| file | patient_key | date_of_birth | sex |
| --- | --- | --- | --- |
| report-01.pdf | mrn:SYN-MRN-0001 | 2018-05-14 | Female |
| report-02.pdf | mrn:SYN-MRN-0001 | 2016-05-14 | Female |

This query lists the patients whose reports give different dates of birth,
and the dates:

```sql
SELECT DISTINCT patient_key, date_of_birth
FROM reports
WHERE patient_key IN (
    SELECT patient_key
    FROM reports
    GROUP BY patient_key
    HAVING count(DISTINCT date_of_birth) > 1)
ORDER BY patient_key, date_of_birth;
```

### Find a term together with the terms under it

`gentrex normalize` gives each clinical feature the most specific HPO term
that fits. Suppose three reports say this:

| file | Feature in the report | Term from `gentrex normalize` |
| --- | --- | --- |
| report-01.pdf | intellectual disability | HP:0001249 Intellectual disability |
| report-02.pdf | mild intellectual disability | HP:0001256 Mild intellectual disability |
| report-03.pdf | severe intellectual disability | HP:0010864 Severe intellectual disability |

All three patients have intellectual disability, but a query for
`hpo_id = 'HP:0001249'` counts only one of them. To the database, the three
IDs are unrelated. You would have to list every kind of intellectual
disability in the query, which is 6 IDs. For seizures, it is 347, Seizure
itself and 346 kinds of seizure.

HPO says which term is a kind of which. A term can have several parents:

```
HP:0002384 Focal impaired awareness seizure
  is a HP:0007359 Focal-onset seizure
    is a HP:0001250 Seizure
  is a HP:0011146 Dialeptic seizure
    is a HP:0001250 Seizure
```

Gentrex copies this hierarchy into `hpo_ancestors`. For each term, the table
lists the term itself and every term above it, each once. HP:0002384 has 8
rows:

| hpo_id | ancestor_id |
| --- | --- |
| HP:0002384 | HP:0002384 |
| HP:0002384 | HP:0007359 |
| HP:0002384 | HP:0011146 |
| HP:0002384 | HP:0001250 |
| HP:0002384 | HP:0012638 |
| HP:0002384 | HP:0000707 |
| HP:0002384 | HP:0000118 |
| HP:0002384 | HP:0000001 |

The last four are the terms above Seizure, from Abnormal nervous system
physiology up to All, the root of HPO.

The question "which patients have intellectual disability?" then becomes
"which patients have a feature whose term has HP:0001249 among its
ancestors?":

```sql
SELECT count(DISTINCT r.patient_key) AS patients
FROM patient_phenotypes p
JOIN hpo_ancestors a ON a.hpo_id = p.hpo_id
JOIN reports r ON r.file = p.file
WHERE a.ancestor_id = 'HP:0001249' AND p.present;
```

For the three reports above, it counts 3 patients. The query at the top of
the page works the same way. For 12 synthetic reports, it finds 3 patients
with Neurodevelopmental delay (HP:0012758), while a query for that exact ID
finds none. Their features were matched to Global developmental delay,
Delayed speech and language development and Delayed ability to walk, which
all lie under Neurodevelopmental delay.

The hierarchy also helps when a match is too specific. `gentrex normalize`
matched "seizures since infancy" to Neonatal seizure, and the feature still
counts as a seizure. You can count per body system, too. With HP:0000707,
Abnormality of the nervous system, the query counts the patients with any of
the 2,831 terms under it.

The hierarchy comes from the HPO release that `load.hpo_release` in
settings.yaml points to. Gentrex keeps the same terms as the HPO index of
`gentrex normalize` and follows their `is_a` links. For the release of
1 September 2026, that is 19,894 terms and 223,079 rows in `hpo_ancestors`.

### Load a run again

Loading a report replaces its rows and leaves the other reports alone. So
you can load several batches of PDFs into one database, or load a report
again after running `gentrex transcribe`, `gentrex select`, `gentrex extract`
and `gentrex normalize` for it once more. A report replaces any earlier
report with the same file name, so keep file names unique across batches.

Each report is loaded in one transaction, a group of changes that the
database makes all together or not at all. If a report fails to load, its
rows from an earlier run stay as they were, and the other reports still
load.

The HPO tables are loaded once per release. `hpo_release` stores the
checksum of the release file, and a run with the same release keeps the
terms. A run with another release replaces them, in one transaction.

Gentrex creates the tables at the start of a run if they don't exist yet,
and it never changes a table that exists. So when a new version of Gentrex
changes the tables, `gentrex load` stops on a database from an older version
with `the database holds version 1 of the Gentrex tables, but this Gentrex
writes version 2`. Then delete the database as below, do step 1 again and
load each run of `gentrex normalize` again.

To start again with an empty database, delete it and do step 1 again. This
deletes every loaded report:

| Database | Delete the database |
| --- | --- |
| SQLite | `rm results/load/gentrex.db` |
| PostgreSQL | `docker rm -f gentrex-postgres`, then `docker volume rm gentrex-postgres` |
| MySQL | `docker rm -f gentrex-mysql`, then `docker volume rm gentrex-mysql` |

### Supported databases

`gentrex load` supports SQLite, PostgreSQL 18 and MySQL 8.4. Gentrex's tests
load reports into each of them on every change to the code, with PostgreSQL
and MySQL as servers in continuous integration. To run the tests on them
yourself, see [Development](../development/development.md). The queries on
this page were run on all three, and the code handles the ways in which they
differ, so a report loads the same way everywhere.

Gentrex talks to all three through SQLAlchemy, a Python package that writes
each database's SQL from one description of the tables,
[`tables.py`](../../src/gentrex/load/tables.py). It uses only types that all
three have: text, dates, booleans, integers and JSON.

Three differences needed handling of their own:

- SQLite ignores the rule that deleting a report deletes its variants and
  features, unless each connection switches the rule on. Gentrex does,
  because otherwise loading a report again would leave its old variants in
  place.
- MySQL compares text without regard to case by default, so `report-01.pdf`
  and `REPORT-01.pdf` would be one report. The key columns `file`, `hpo_id`
  and `ancestor_id` compare exactly instead. The other text columns keep
  MySQL's default, so on MySQL `WHERE classification = 'Pathogenic'` matches
  `pathogenic`, and on the others it doesn't.
- Sorting puts null first on SQLite and MySQL, and last on PostgreSQL. In
  the query per gene above, a variant without a gene symbol comes first or
  last for that reason.

Other databases that SQLAlchemy knows, such as MariaDB, are not supported,
and Gentrex refuses their addresses. To add one, add its name and driver to
`DRIVERS` in [`run.py`](../../src/gentrex/load/run.py), and the driver as an
extra of that name in `pyproject.toml`. In `.github/workflows/ci.yml`, add a
server for it under `services`, its address to `GENTREX_TEST_DATABASE_URLS`
and its extra to the `uv sync` line. Then run the queries on this page
against it.

## Settings

`gentrex load` has one setting, under `load` in
[`src/gentrex/defaults/settings.yaml`](../../src/gentrex/defaults/settings.yaml):

| Setting | Default | What it does |
| --- | --- | --- |
| `hpo_release` | `data/ontology/hp-base.json` | The HPO release that `hpo_terms` and `hpo_ancestors` come from. Use the release that built the HPO index of `gentrex normalize`, so every matched term is in it. |

The database's address is set in `GENTREX_DATABASE_URL` in `.env` (step 2).

## When something goes wrong

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every report was loaded, and none has an error. | Nothing. |
| 1 | A file is missing, the database can't be used, some reports have an error or weren't loaded, or the run stopped with a traceback. The end of the output says which. | See below. |
| 2 | `GENTREX_DATABASE_URL` is not set. | Do step 2. |

If something is missing, Gentrex stops before it loads anything:

| Message | What to do |
| --- | --- |
| `results/normalize/latest/normalized.jsonl not found` | Run `gentrex normalize` first, or name one of its runs with `--input`. |
| `data/ontology/hp-base.json not found` | Download the HPO release in step 2 of [Normalize report data](normalize.md#step-2-build-the-hpo-index). |
| `GENTREX_DATABASE_URL: not a database URL` | Write the address in the form shown in step 2. |
| `GENTREX_DATABASE_URL: mariadb is not a supported database` | Use SQLite, PostgreSQL or MySQL. |
| `GENTREX_DATABASE_URL: No module named 'psycopg'; its driver comes with uv run --extra postgresql` | Run `gentrex load` with the extra that the message names. |
| `can't connect to the database: ... Connection refused` | The server isn't running. Start it with `docker start gentrex-postgres` or `docker start gentrex-mysql`, or create it in step 1. |
| `can't connect to the database: ... password authentication failed` or `... Access denied for user` | The password in `GENTREX_DATABASE_URL` differs from the one in step 1. Correct it in `.env`. |
| `can't connect to the database: unable to open database file` | Gentrex can't write the SQLite file. Check the path after `sqlite:///` in `.env`, and that you may write there. |
| `the database holds version 1 of the Gentrex tables, but this Gentrex writes version 2` | The database was made by an older version of Gentrex. Delete it and load the runs of `gentrex normalize` again ([Load a run again](#load-a-run-again)). |

While loading, Gentrex prints a line for each report it doesn't load:

- `skipped report-13.pdf, which has no data: APITimeoutError: Request timed out.`
  means that `gentrex extract` got no data for the report. Run
  `gentrex extract` again for it, then `gentrex normalize` and
  `gentrex load`.
- `failed report-07.pdf:` followed by a reason means that loading the report
  failed. Its rows from an earlier run stay.

A report with an error from `gentrex extract` or `gentrex normalize` is still
loaded, but it is listed among the failed files at the end, as in the output
of those two commands.

The warning `matched HPO terms missing from the HPO release` means that
`hp-base.json` is a different release from the one that built the HPO index.
Queries through `hpo_ancestors` then miss the features matched to the terms
it lists. Download the release that built the index, and run `gentrex load`
again.

If `docker run` in step 1 fails with `Bind for 127.0.0.1:5432 failed: port is
already allocated`, or the same for port 3306, another program uses the port.
Often it's a database server installed on the machine. Docker still created
the container, so remove it with `docker rm gentrex-postgres` or
`docker rm gentrex-mysql`. Then run step 1 with `-p 127.0.0.1:5433:5432`, or
`-p 127.0.0.1:3307:3306` for MySQL, and use that port in
`GENTREX_DATABASE_URL`.
