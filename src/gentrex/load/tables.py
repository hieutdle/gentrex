"""The tables of `gentrex load`, defined once for every database that it supports.

A column whose name ends in _raw holds the report's wording, and the column of
the same name without _raw holds the standard value that `gentrex normalize`
found for it. docs/database-tables.md describes the columns.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.dialects import postgresql

# MySQL compares text case-insensitively by default, so report-01.pdf and
# REPORT-01.pdf would be the same key. The keys compare bytes instead.
_FILE = sa.String(255).with_variant(
    mysql.VARCHAR(255, collation="utf8mb4_bin"), "mysql"
)
_HPO_ID = sa.String(32).with_variant(
    mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"
)
# PostgreSQL's jsonb answers queries faster than its json.
_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

# The version of these tables, kept in schema_version. `gentrex load` never
# changes a table that exists already, so raise the version whenever a column
# changes, and `gentrex load` then refuses a database with the old tables.
SCHEMA_VERSION = 2

metadata = sa.MetaData()

reports = sa.Table(
    "reports",
    metadata,
    sa.Column("file", _FILE, primary_key=True),
    sa.Column("patient_key", sa.Text, nullable=False),
    sa.Column("pages", _JSON, nullable=False),
    sa.Column("error", sa.Text),
    sa.Column("mrn", sa.Text),
    sa.Column("submitter_patient_id", sa.Text),
    sa.Column("lab_accession_number", sa.Text),
    sa.Column("date_of_birth", sa.Date),
    sa.Column("date_of_birth_raw", sa.Text),
    sa.Column("sex", sa.Text),
    sa.Column("specimen_type", sa.Text),
    sa.Column("specimen_type_raw", sa.Text),
    sa.Column("collection_date", sa.Date),
    sa.Column("collection_date_raw", sa.Text),
    sa.Column("received_date", sa.Date),
    sa.Column("received_date_raw", sa.Text),
    sa.Column("test_name", sa.Text),
    sa.Column("test_type", sa.Text),
    sa.Column("test_started_date", sa.Date),
    sa.Column("test_started_date_raw", sa.Text),
    sa.Column("report_date", sa.Date),
    sa.Column("report_date_raw", sa.Text),
    sa.Column("overall_result", sa.Text),
    sa.Column("overall_result_basis", sa.Text),
    sa.Column("overall_result_conflict", sa.Boolean),
    sa.Column("overall_result_raw", sa.Text),
    sa.Column("clinical_indication", sa.Text),
    sa.Column("lab_name", sa.Text),
    sa.Column("record", _JSON, nullable=False),
    sa.Column("normalize_run", sa.Text, nullable=False),
    sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
)

variants = sa.Table(
    "variants",
    metadata,
    sa.Column(
        "file",
        _FILE,
        sa.ForeignKey("reports.file", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("variant_number", sa.Integer, primary_key=True),
    sa.Column("page", sa.Integer),
    sa.Column("gene_symbol", sa.Text),
    sa.Column("gene_symbol_raw", sa.Text),
    sa.Column("hgnc_id", sa.Text),
    sa.Column("gene_status", sa.Text),
    sa.Column("transcript", sa.Text),
    sa.Column("hgvs_c", sa.Text),
    sa.Column("hgvs_p", sa.Text),
    sa.Column("dna_change_raw", sa.Text),
    sa.Column("chromosomal_position", sa.Text),
    sa.Column("classification", sa.Text),
    sa.Column("classification_raw", sa.Text),
    sa.Column("zygosity", sa.Text),
    sa.Column("zygosity_raw", sa.Text),
    sa.Column("parental_origin", sa.Text),
    sa.Column("parental_origin_raw", sa.Text),
    sa.Column("associated_phenotype", sa.Text),
    sa.Column("disease_id", sa.Text),
    sa.Column("disease_label", sa.Text),
    sa.Column("disease_status", sa.Text),
    sa.Column("mode_of_inheritance", sa.Text),
    sa.Column("mode_of_inheritance_raw", sa.Text),
    sa.Column("is_secondary_finding", sa.Boolean),
    sa.Column("variant_type_raw", sa.Text),
)

patient_phenotypes = sa.Table(
    "patient_phenotypes",
    metadata,
    sa.Column(
        "file",
        _FILE,
        sa.ForeignKey("reports.file", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("phenotype_number", sa.Integer, primary_key=True),
    sa.Column("text", sa.Text, nullable=False),
    sa.Column("present", sa.Boolean),
    sa.Column("hpo_id", _HPO_ID),
    sa.Column("hpo_label", sa.Text),
    sa.Column("models_agree", sa.Boolean),
)

phenotype_candidates = sa.Table(
    "phenotype_candidates",
    metadata,
    sa.Column("file", _FILE, primary_key=True),
    sa.Column("phenotype_number", sa.Integer, primary_key=True),
    sa.Column("rank", sa.Integer, primary_key=True),
    sa.Column("hpo_id", _HPO_ID, nullable=False),
    sa.Column("hpo_label", sa.Text, nullable=False),
    sa.Column("models", _JSON, nullable=False),
    sa.ForeignKeyConstraint(
        ["file", "phenotype_number"],
        ["patient_phenotypes.file", "patient_phenotypes.phenotype_number"],
        ondelete="CASCADE",
    ),
)

hpo_terms = sa.Table(
    "hpo_terms",
    metadata,
    sa.Column("hpo_id", _HPO_ID, primary_key=True),
    sa.Column("hpo_label", sa.Text, nullable=False),
)

# One row for each term and each of its ancestors, the term itself included.
hpo_ancestors = sa.Table(
    "hpo_ancestors",
    metadata,
    sa.Column("hpo_id", _HPO_ID, primary_key=True),
    sa.Column("ancestor_id", _HPO_ID, primary_key=True),
)

# The release that hpo_terms and hpo_ancestors hold, so that a run with the
# same release keeps them instead of loading them again.
hpo_release = sa.Table(
    "hpo_release",
    metadata,
    sa.Column("sha256", sa.String(64), primary_key=True),
    sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
)

schema_version = sa.Table(
    "schema_version",
    metadata,
    sa.Column("version", sa.Integer, primary_key=True),
)
