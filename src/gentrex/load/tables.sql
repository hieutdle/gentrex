-- The tables of stage 5. Every run creates those that don't exist yet, and
-- docs/stage5.md describes their columns. A column whose name ends in _raw
-- holds the report's wording, and the column of the same name without _raw
-- holds the standard value that stage 4 found for it.

CREATE TABLE IF NOT EXISTS reports (
    file text PRIMARY KEY,
    patient_key text NOT NULL,
    pages integer[] NOT NULL,
    error text,
    mrn text,
    submitter_patient_id text,
    lab_accession_number text,
    date_of_birth date,
    date_of_birth_raw text,
    sex text,
    specimen_type text,
    specimen_type_raw text,
    collection_date date,
    collection_date_raw text,
    received_date date,
    received_date_raw text,
    test_name text,
    test_type text,
    test_started_date date,
    test_started_date_raw text,
    report_date date,
    report_date_raw text,
    overall_result text,
    overall_result_basis text,
    overall_result_conflict boolean,
    overall_result_raw text,
    clinical_indication text,
    lab_name text,
    record jsonb NOT NULL,
    normalize_run text NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS variants (
    file text NOT NULL REFERENCES reports ON DELETE CASCADE,
    variant_number integer NOT NULL,
    page integer,
    gene_symbol text,
    gene_symbol_raw text,
    hgnc_id text,
    gene_status text,
    transcript text,
    hgvs_c text,
    hgvs_p text,
    dna_change_raw text,
    chromosomal_position text,
    classification text,
    classification_raw text,
    zygosity text,
    zygosity_raw text,
    parental_origin text,
    parental_origin_raw text,
    associated_phenotype text,
    mode_of_inheritance text,
    mode_of_inheritance_raw text,
    is_secondary_finding boolean,
    variant_type_raw text,
    PRIMARY KEY (file, variant_number)
);

CREATE TABLE IF NOT EXISTS patient_phenotypes (
    file text NOT NULL REFERENCES reports ON DELETE CASCADE,
    phenotype_number integer NOT NULL,
    text text NOT NULL,
    present boolean,
    hpo_id text,
    hpo_label text,
    models_agree boolean,
    PRIMARY KEY (file, phenotype_number)
);

CREATE TABLE IF NOT EXISTS phenotype_candidates (
    file text NOT NULL,
    phenotype_number integer NOT NULL,
    rank integer NOT NULL,
    hpo_id text NOT NULL,
    hpo_label text NOT NULL,
    models jsonb NOT NULL,
    PRIMARY KEY (file, phenotype_number, rank),
    FOREIGN KEY (file, phenotype_number)
        REFERENCES patient_phenotypes ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS hpo_terms (
    hpo_id text PRIMARY KEY,
    hpo_label text NOT NULL
);

-- One row for each term and each of its ancestors, the term itself included.
CREATE TABLE IF NOT EXISTS hpo_ancestors (
    hpo_id text NOT NULL,
    ancestor_id text NOT NULL,
    PRIMARY KEY (hpo_id, ancestor_id)
);
