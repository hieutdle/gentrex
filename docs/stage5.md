# Stage 5: Load report data into a database

Stage 5 loads the records of a stage 4 run into a database, so that you can
answer questions about all your reports with SQL, the query language of
databases. For example, this query counts the patients with a
neurodevelopmental delay of any kind:

```sql
SELECT count(DISTINCT r.patient_key) AS patients
FROM patient_phenotypes p
JOIN hpo_ancestors a ON a.hpo_id = p.hpo_id
JOIN reports r ON r.file = p.file
WHERE a.ancestor_id = 'HP:0012758' AND p.present;
```

Stage 5 reads `normalized.jsonl` from a stage 4 run. It writes one row per
report, per variant and per clinical feature into tables of the database. It
also loads the terms of the Human Phenotype Ontology (HPO) with their
hierarchy, so that a query on a term like Neurodevelopmental delay finds the
features matched to the terms under it. Stage 5 needs no model server and no
GPU, and it loads a few hundred reports in a few seconds.

The database is a [SQLite](../README.md#terms) file, which needs no server,
or a PostgreSQL or MySQL [database server](../README.md#terms). You choose in
step 1, and the rest of this page is the same for all three.
[Supported databases](#supported-databases) says what that means.

## Before you start

You need:

- Gentrex installed, as in [stage 1, step 1](stage1.md#step-1-install).
- A finished stage 4 run, in `results/normalize/`.
- The HPO release `data/ontology/hp-base.json`, which
  [stage 4, step 2](stage4.md#step-2-build-the-hpo-index) downloads. Stage 5
  needs it even if you ran stage 4 with `--no-hpo`.
- A machine approved for patient data, because the database holds the
  records of every report.
- [Docker](https://docs.docker.com/get-started/get-docker/), if you choose
  PostgreSQL or MySQL in step 1. It runs the server in a
  [container](../README.md#terms), which takes 1 to 2 GB of disk with the
  database. SQLite needs neither.

On Minerva, run stage 5 with SQLite in the interactive session of stage 4, as
[Running on Minerva](minerva.md#stage-5-load-report-data-into-a-database)
shows.

## Step 1: Choose a database

| Database | Choose it when | What it needs |
| --- | --- | --- |
| SQLite | You query the records yourself, from the machine that runs Gentrex. This fits most projects, and Minerva. | Nothing. The database is one file, which stage 5 creates. |
| PostgreSQL 18 | Several people or programs query the database at once, or your group runs a PostgreSQL server already. | A server. The command below starts one in Docker. |
| MySQL 8.4 | The same as PostgreSQL, when your group runs MySQL. | A server. The command below starts one in Docker. |

### SQLite

There is nothing to start and nothing to install. SQLite keeps the whole
database in one file, `results/load/gentrex.db`, which Python reads and
writes without a server. Stage 5 creates the file on the first run. Go on to
step 2.

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

- `-d` runs the container in the background, so the server keeps running
  after the command returns.
- `--name gentrex-postgres` names the container. The commands below use this
  name.
- `-e POSTGRES_USER=gentrex` and `-e POSTGRES_PASSWORD=gentrex` create the
  database user `gentrex` with the password `gentrex`. The image also creates
  a database named after the user. If other people can log in to the
  machine, choose your own password, and use it in step 2 too.
- `-p 127.0.0.1:5432:5432` makes the server reachable at port 5432, the usual
  port of PostgreSQL. The address 127.0.0.1 stands for this machine only, so
  other machines can't reach the patient data in the database.
- `-v gentrex-postgres:/var/lib/postgresql` keeps the database in a Docker
  volume named `gentrex-postgres`. A volume is storage that Docker manages on
  the machine's disk, so the database stays when the container stops or is
  removed.
- `postgres:18` is the image of PostgreSQL 18. The first run downloads it,
  about 700 MB.

The server is ready when this command prints
`127.0.0.1:5432 - accepting connections`:

```bash
docker exec gentrex-postgres pg_isready -h 127.0.0.1 -U gentrex
```

`docker exec` runs a command inside the container, and `pg_isready` asks the
server whether it accepts connections at port 5432. The first start takes a
few seconds longer, because the server sets up the database first.

The server runs until you stop it with `docker stop gentrex-postgres`. Start
it again with `docker start gentrex-postgres`. The database stays in the
volume in between.

Gentrex talks to PostgreSQL through a driver, the Python package psycopg. It
is not installed with Gentrex, because stages 1 to 4 don't need it. In step
3, you run stage 5 with `--extra postgresql`, which installs it the first
time.

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

- `-d`, `--name`, `-p` and `-v` work as for PostgreSQL. 3306 is the usual
  port of MySQL, and the volume `gentrex-mysql` keeps the database.
- `-e MYSQL_DATABASE=gentrex`, `-e MYSQL_USER=gentrex` and
  `-e MYSQL_PASSWORD=gentrex` create the database `gentrex` and the user
  `gentrex` with the password `gentrex`, who may use that database.
- `-e MYSQL_ROOT_PASSWORD=gentrex` sets the password of `root`, the user who
  may do anything on the server. Gentrex doesn't use `root`, but the image
  refuses to start without a password for it. If other people can log in to
  the machine, choose your own passwords.
- `mysql:8.4` is the image of MySQL 8.4, the current long-term release. The
  first run downloads it, about 1.1 GB.

The server is ready when this command prints `mysqld is alive`:

```bash
docker exec gentrex-mysql mysqladmin ping -h 127.0.0.1 -u gentrex -pgentrex
```

`mysqladmin ping` asks the server whether it is up. It also prints a warning
about the password on the command line, which you can ignore on your own
machine. The first start takes about ten seconds longer, because the server
sets up the database first.

The server runs until you stop it with `docker stop gentrex-mysql`. Start it
again with `docker start gentrex-mysql`.

Gentrex talks to MySQL through the driver PyMySQL, which `--extra mysql` in
step 3 installs the first time.

## Step 2: Point Gentrex at the database

Stage 5 reads the database's address from `GENTREX_DATABASE_URL` in `.env`.
If you have no `.env` file yet, create it from the example file:

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

A SQLite address is `sqlite:///` followed by the path of the file. A relative
path counts from the folder you run Gentrex in, so the example file goes to
`results/load/`, which Git ignores too. For an absolute path, write four
slashes, as in `sqlite:////data/gentrex/gentrex.db`.

## Step 3: Run

With SQLite:

```bash
uv run --env-file .env gentrex stage5
```

With a server, add the extra that installs its driver, `--extra postgresql`
or `--extra mysql`:

```bash
uv run --env-file .env --extra postgresql gentrex stage5
```

This reads the newest finished stage 4 run, `results/normalize/latest`, and
loads it into the database. It also writes a new folder named after the time
the run started, such as `results/load/20261021-122822/`. To load another
stage 4 run:

```bash
uv run --env-file .env gentrex stage5 --input results/normalize/20261019-030000
```

Gentrex prints the database it loads into, as in
`loading into sqlite+pysqlite:///results/load/gentrex.db`. The part before
`://` names the database and, after `+`, its driver. A server's password is
shown as `***`. The first run into a database then prints
`loaded 19894 HPO terms with 223079 ancestor rows`, which takes a few
seconds. Later runs print `kept the HPO terms, which are from the same
release` instead. Then Gentrex prints one line per report, such as
`loaded report-01.pdf`. The last line counts the reports that were loaded, as
in `loaded 300 of 300 reports in 1 s`.

## Check the result

The run folder holds two files:

| File | Contents |
| --- | --- |
| `run.yaml` | The command, the stage 4 run that was loaded, the settings and `hpo_sha256`, the checksum of the HPO release. |
| `log.txt` | What Gentrex printed during the run. |

The records themselves are in the database. `results/load/latest` points to
the newest finished run. [Runs and results](../README.md#runs-and-results)
explains run folders and `latest`.

### Open the database

Each database comes with a command-line client, a program in which you type
queries. A query ends with `;`.

| Database | Open the client | List the tables | Show a table's columns | Quit |
| --- | --- | --- | --- | --- |
| SQLite | `sqlite3 results/load/gentrex.db` | `.tables` | `.schema reports` | `.quit` |
| PostgreSQL | `docker exec -it gentrex-postgres psql -U gentrex` | `\dt` | `\d reports` | `\q` |
| MySQL | `docker exec -it gentrex-mysql mysql -u gentrex -pgentrex gentrex` | `SHOW TABLES;` | `DESCRIBE reports;` | `quit` |

`sqlite3` comes with macOS and most Linux systems. In it, `.headers on` and
`.mode column` print the results of a query as a table with column names.
For the servers, `docker exec -it` connects your terminal to the client
inside the container.

### See what each table holds

| Table | One row per |
| --- | --- |
| `reports` | Report, with its report-level fields from stage 3 and their standard values from stage 4. |
| `variants` | Variant of a report. |
| `patient_phenotypes` | Clinical feature of a report, with its HPO term. |
| `phenotype_candidates` | Candidate HPO term of a clinical feature, 5 per feature by default (`normalize.hpo.top_k` in settings.yaml). |
| `hpo_terms` | Current HPO term, with its label. |
| `hpo_ancestors` | HPO term and one of its ancestors. |
| `hpo_release` | The HPO release that `hpo_terms` and `hpo_ancestors` were loaded from. It has one row. |

[`tables.py`](../src/gentrex/load/tables.py) defines the tables.
[`schema.yaml`](../src/gentrex/defaults/schema.yaml) says what each field of
stage 3 holds, and [stage 4](stage4.md#check-the-result) explains the standard
values.

Most columns have the name of a field of the stage 4 record. Where stage 4
found a standard value for a field, the column of the field's name holds the
standard value, and the column with `_raw` added holds the report's wording.
For a report with the date of birth `29-JUN-1984`:

| Column | Holds | Example |
| --- | --- | --- |
| `date_of_birth` | The date from `normalized.date_of_birth`, of the SQL type `date`. | 1984-06-29 |
| `date_of_birth_raw` | The printed date from `data.date_of_birth`, as text. | 29-JUN-1984 |

The same goes for `collection_date`, `received_date`, `test_started_date`,
`report_date`, `specimen_type` and the `gene_symbol` of each variant. The
other `_raw` columns, such as `classification_raw`, keep their names from
stage 3, because the field without `_raw` is already the category.

`reports` has these columns besides the fields of the record:

| Column | Meaning |
| --- | --- |
| `file` | Name of the PDF. It identifies the report in every table. |
| `patient_key` | The key that links the reports of one patient, such as `mrn:SYN-MRN-0001`. [Link reports to patients](#link-reports-to-patients) explains it. |
| `pages` | The pages that stage 3 sent to the model, as a JSON list such as `[1, 2]`. |
| `error` | The error from stage 3 or 4, or null. [Stage 4](stage4.md#when-something-goes-wrong) explains the errors. |
| `record` | The whole line of `normalized.jsonl`, as JSON. It also holds the fields that have no column, such as a field you added to `schema.yaml`. |
| `normalize_run` | The stage 4 run folder that the report was loaded from. |
| `loaded_at` | When stage 5 loaded the report, in UTC. |

The other tables have these columns:

| Table | Column | Meaning |
| --- | --- | --- |
| `variants` | `variant_number` | The variant's place in the report's list of variants, from 1. |
| `variants` | `gene_symbol`, `hgnc_id`, `gene_status` | The approved HGNC symbol, the HGNC ID and how the symbol matched, from stage 4. `gene_symbol_raw` holds the symbol as printed. |
| `patient_phenotypes` | `phenotype_number` | The feature's place in the report's list of features, from 1. |
| `patient_phenotypes` | `text`, `present` | The feature, and whether the patient has it, from stage 3. `present` is false when the report says the patient doesn't have the feature, and null when the report is unsure. |
| `patient_phenotypes` | `hpo_id`, `hpo_label`, `models_agree` | The matched HPO term, and whether the models agree, from stage 4. They are null if stage 4 ran with `--no-hpo`. |
| `phenotype_candidates` | `rank` | 1 for the match, then 2 to 5 for the alternatives. |
| `phenotype_candidates` | `models` | For each model, the label or synonym of the term that came closest (`name`) and its cosine similarity, as JSON. |
| `hpo_ancestors` | `hpo_id`, `ancestor_id` | A term, and the term itself or a term above it. [Find a term together with the terms under it](#find-a-term-together-with-the-terms-under-it) explains them. |
| `hpo_release` | `sha256` | The checksum of the release file, the same as `hpo_sha256` in `run.yaml`. |

A feature that the patient doesn't have has a row too, with `present` false.
When you count the patients with a feature, add `p.present` to the `WHERE`
clause, as the queries on this page do. Otherwise "no hearing impairment"
counts as hearing impairment.

To read a value inside a JSON column, such as a field of `record` that has
no column of its own, each database has a syntax of its own. These queries
print the laboratory's name from the record:

| Database | Query |
| --- | --- |
| PostgreSQL | `SELECT file, record->'data'->>'lab_name' FROM reports;` |
| MySQL and SQLite | `SELECT file, record->>'$.data.lab_name' FROM reports;` |

SQLite reads `->>` from version 3.38 on, which `sqlite3 --version` shows.

### Query the tables

The queries on this page give the same result on all three databases. To
count the reports per result category:

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

`count(DISTINCT r.patient_key)` counts each patient once, even a patient with
several reports or several variants in the gene.

To list the clinical features whose match the two models disagree on, each
with its candidates:

```sql
SELECT p.file, p.text, c.rank, c.hpo_id, c.hpo_label
FROM patient_phenotypes p
JOIN phenotype_candidates c USING (file, phenotype_number)
WHERE NOT p.models_agree
ORDER BY p.file, p.phenotype_number, c.rank;
```

Check these matches first, because they are more often wrong
([stage 4](stage4.md#check-the-result)).

To read a table in Python with pandas:

```python
import os

import pandas as pd

from gentrex.load import run

engine = run.make_engine(os.environ["GENTREX_DATABASE_URL"])
variants = pd.read_sql("SELECT * FROM variants", engine)
```

`run.make_engine` opens the database that `GENTREX_DATABASE_URL` names, in
the same way as stage 5, so the same address works for all three databases.
In Gentrex's environment, `uv run --env-file .env --with pandas python`
starts Python with pandas and with the address set. With a server, add its
extra, as in step 3.

## How it works

### Turn records into rows

Each line of `normalized.jsonl` becomes one row in `reports`. Each item of
`data.variants` becomes a row in `variants`, and each item of
`data.patient_phenotypes` a row in `patient_phenotypes`, with its candidates
in `phenotype_candidates`. A report without data, from a failed stage 3
request, gets no rows, so that it can't count as a patient. Stage 5 lists it
among the failed files.

### Link reports to patients

Research questions are about patients, but the database is filled from
reports. One patient can have several reports, for example a panel and later
an exome. If you count reports, that patient counts twice. So stage 5 gives
each report a `patient_key`, and reports with the same key count as the same
patient.

The reports have no patient ID in common, only what each laboratory printed.
So the key comes from the first of these that the report has:

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

Reports 01 and 02 count as one patient, because they share the MRN. Report 03
counts as a second patient, although report 02 shows that SYN-SUB-0002 is the
same person. Stage 5 doesn't follow such links. This query lists the
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

There is no table of patients. Each report keeps the date of birth and the
sex it printed, so a disagreement between the reports of one patient stays
visible. Suppose stage 3 misread the date of birth on the second of two
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

Stage 4 gives each clinical feature the most specific HPO term that fits.
Suppose three reports say this:

| file | Feature in the report | Term from stage 4 |
| --- | --- | --- |
| report-01.pdf | intellectual disability | HP:0001249 Intellectual disability |
| report-02.pdf | mild intellectual disability | HP:0001256 Mild intellectual disability |
| report-03.pdf | severe intellectual disability | HP:0010864 Severe intellectual disability |

All three patients have intellectual disability. A query for
`hpo_id = 'HP:0001249'` counts only one of them, because to the database the
three IDs are unrelated. You would have to know every kind of intellectual
disability and list all their IDs in the query. For intellectual disability,
there are 6 IDs. For seizures, there are 347, Seizure itself and 346 kinds of
seizure.

HPO records which term is a kind of which, such as "Mild intellectual
disability is a kind of Intellectual disability". A term can have several
parents:

```
HP:0002384 Focal impaired awareness seizure
  is a HP:0007359 Focal-onset seizure
    is a HP:0001250 Seizure
  is a HP:0011146 Dialeptic seizure
    is a HP:0001250 Seizure
```

Stage 5 copies this hierarchy into `hpo_ancestors`. For each term, the table
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
this page works the same way. For 12 synthetic reports, it finds 3 patients
with Neurodevelopmental delay (HP:0012758), while a query for that exact ID
finds none. Their features were matched to Global developmental delay,
Delayed speech and language development and Delayed ability to walk, which
all lie under Neurodevelopmental delay.

The hierarchy gives you three things:

- **Counts at the level of the research question.** You can count
  intellectual disability, seizures or developmental delay without lists of
  IDs.
- **Counts that don't depend on how specific a match is.** Stage 4 matched
  "seizures since infancy" to Neonatal seizure, which is too specific. The
  feature still counts as a seizure.
- **Counts per body system.** With HP:0000707, Abnormality of the nervous
  system, the query counts the patients with any of the 2,831 terms under it.

Stage 5 reads the hierarchy from the HPO release that `load.hpo_release` in
settings.yaml names. It keeps the same terms as the HPO index of stage 4 and
follows their `is_a` links. For the release of 1 September 2026, that is
19,894 terms and 223,079 rows in `hpo_ancestors`.

### Load a run again

Stage 5 replaces the rows of each report that it loads, and keeps the reports
of other files. So you can load the runs of several batches of PDFs into one
database. You can also load a report again after running stages 1 to 4 for it
once more. A report replaces any earlier report with the same file name, so
keep file names unique across batches.

Each report is loaded in one [transaction](../README.md#terms), a group of
changes that the database makes all together or not at all. If loading a
report fails, its rows from an earlier run stay as they were, and the other
reports are still loaded.

The HPO tables are loaded once per release. Stage 5 keeps the checksum of the
release file in `hpo_release`. A run with the same release keeps the terms,
which saves the few seconds that the 223,079 rows take. A run with another
release replaces them, in one transaction.

Stage 5 creates the tables at the start of a run if they don't exist yet. To
start again with an empty database, delete it and do step 1 again. This
deletes every loaded report:

| Database | Delete the database |
| --- | --- |
| SQLite | `rm results/load/gentrex.db` |
| PostgreSQL | `docker rm -f gentrex-postgres`, then `docker volume rm gentrex-postgres` |
| MySQL | `docker rm -f gentrex-mysql`, then `docker volume rm gentrex-mysql` |

### Supported databases

Stage 5 supports SQLite, PostgreSQL 18 and MySQL 8.4. Supported means three
things:

- Gentrex's tests load reports into each of them on every change to the
  code. SQLite needs no server, so the tests always run on it. PostgreSQL
  and MySQL run as servers in Gentrex's continuous integration, and
  [Development](development.md) shows how to run the tests on them yourself.
- The queries on this page were run on each of them.
- The ways in which they behave differently are handled in the code, so that
  a report loads the same way everywhere.

Gentrex talks to all three through SQLAlchemy, a Python package that writes
the SQL of each database from one description of the tables, which is
[`tables.py`](../src/gentrex/load/tables.py). The description uses only
types that all three have: text, dates, booleans, integers and JSON.
SQLAlchemy quotes names, sends the rows in batches and begins and ends
transactions as each database expects.

Three differences needed handling of their own:

- SQLite ignores the rule that deleting a report deletes its variants and
  features, unless each connection switches the rule on. Gentrex does.
  Without it, loading a report again would leave its old variants in place.
- MySQL compares text without regard to case by default, so the files
  `report-01.pdf` and `REPORT-01.pdf` would be one report. The key columns
  `file`, `hpo_id` and `ancestor_id` compare exactly instead. The other text
  columns keep MySQL's default, so on MySQL `WHERE classification =
  'Pathogenic'` matches `pathogenic`, and on the others it doesn't.
- Sorting puts null first on SQLite and MySQL, and last on PostgreSQL. In
  the query per gene above, a variant without a gene symbol comes first or
  last for that reason.

Other databases that SQLAlchemy knows, such as MariaDB, are not supported,
and stage 5 refuses their addresses. To add one, add its name and driver to
`DRIVERS` in [`run.py`](../src/gentrex/load/run.py), add the driver as an
extra of that name in `pyproject.toml`, list a server for it in
`GENTREX_TEST_DATABASE_URLS` in `.github/workflows/ci.yml`, and run the
queries on this page against it.

## Settings

The setting of stage 5 is in
[`src/gentrex/defaults/settings.yaml`](../src/gentrex/defaults/settings.yaml),
under `load`:

| Setting | Default | What it does |
| --- | --- | --- |
| `hpo_release` | `data/ontology/hp-base.json` | The HPO release that `hpo_terms` and `hpo_ancestors` come from. Use the release that built the HPO index of stage 4, so that every matched term is in it. |

The address of the database is `GENTREX_DATABASE_URL` in `.env`, as in
step 2.

## When something goes wrong

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every report was loaded, and none has an error. | Nothing. |
| 1 | A file is missing, the database can't be used, some reports have an error or weren't loaded, or the run stopped with a traceback. The end of the output says which. | See below. |
| 2 | `GENTREX_DATABASE_URL` is not set. | Do step 2. |

If something is missing, stage 5 stops before it loads anything:

| Message | What to do |
| --- | --- |
| `results/normalize/latest/normalized.jsonl not found` | Run stage 4 first, or name a stage 4 run with `--input`. |
| `data/ontology/hp-base.json not found` | Download the HPO release as in [stage 4, step 2](stage4.md#step-2-build-the-hpo-index). |
| `GENTREX_DATABASE_URL: not a database URL` | Write the address in the form of step 2. |
| `GENTREX_DATABASE_URL: mariadb is not a supported database` | Use SQLite, PostgreSQL or MySQL, as in step 1. |
| `GENTREX_DATABASE_URL: No module named 'psycopg'; its driver comes with uv run --extra postgresql` | Run stage 5 with the extra that the message names, as in step 3. |
| `can't connect to the database: ... Connection refused` | The server isn't running. Start it as in step 1, or with `docker start gentrex-postgres` or `docker start gentrex-mysql`. |
| `can't connect to the database: ... password authentication failed` or `... Access denied for user` | The password in `GENTREX_DATABASE_URL` differs from the one in step 1. Correct it in `.env`. |
| `can't connect to the database: unable to open database file` | Gentrex can't write the SQLite file. Check the path after `sqlite:///` in `.env`, and that you may write there. |

While it loads, stage 5 prints a line for each report that it doesn't load:

- `skipped report-13.pdf, which has no data: APITimeoutError: Request timed out.`
  means that stage 3 got no data for the report. Run stage 3 again for it, and
  then stages 4 and 5.
- `failed report-07.pdf:` followed by a reason means that loading the report
  failed. Its rows from an earlier run stay.

A report with an error from stage 3 or 4 is still loaded, but it is listed
among the failed files at the end, as in stages 3 and 4.

The warning `matched HPO terms missing from the HPO release` means that
`hp-base.json` is another release than the one that built the HPO index.
Queries through `hpo_ancestors` miss the features matched to the terms it
lists. Download the release that built the index, and run stage 5 again.

If `docker run` in step 1 fails with `Bind for 127.0.0.1:5432 failed: port is
already allocated`, or the same for port 3306, another program uses the port,
often a database server installed on the machine. Docker still created the
container, so remove it with `docker rm gentrex-postgres` or
`docker rm gentrex-mysql`. Then run step 1 with `-p 127.0.0.1:5433:5432`, or
`-p 127.0.0.1:3307:3306` for MySQL, and use that port in
`GENTREX_DATABASE_URL`.
