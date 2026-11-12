# How the benchmark generator works

The benchmark generator makes fictional genetic test reports for testing
Gentrex. Each report comes with a truth file that holds what a perfect run of
`gentrex extract` and `gentrex normalize` would write for it. Gentrex's output
can then be compared with the truth, value by value. Real reports can't be
shared for this, because they hold patient data.

You give the generator a seed and a number of cases. For each case you get
the report as five PDFs and one truth file.
[Generate benchmark reports](generate-benchmark-reports.md) shows how to run
it.

## An example report

Here is page 1 of one generated report, a neurodevelopmental panel with one
variant of uncertain significance. The colors show where each piece of text
comes from:

- **Yellow** text is a value of the truth, printed by code.
- **Red** text is a distractor, a value that looks like something to extract
  but isn't. Here, two IDs look like the lab number.
- **Blue** text was written by a language model.
- Text without color is the template's own labels, headings and fixed
  sentences, or a detail made up for the case, such as the patient's name.

![Page 1 of a synthetic report from Indigo Genetic Testing. Yellow marks the values of the truth: the lab name, date of birth, sex, sample type and dates, report date, lab number, reason for testing, clinical features, test name, the result "RESULT: UNCERTAIN", the variant table with MECP2, c.1101C>A, p.Ser367Arg, Heterozygous and Uncertain Significance, and the condition, transcript and inheritance. The MRN reads "Not provided". Red marks two distractor IDs below the lab number. Blue marks the model's text: the summary, "About this result", the next steps and the clinical summary.](../images/benchmark-report-sources.png)

The colors are only in this picture. A generated report has none. The MRN
reads "Not provided", so the truth has no MRN.

The truth file holds the variant as `gentrex extract` should write it, here
without its empty fields:

```json
{
  "page": 1,
  "gene_symbol": "MECP2",
  "transcript": "NM_001110792.2",
  "hgvs_c": "c.1101C>A",
  "hgvs_p": "p.Ser367Arg",
  "classification_raw": "Uncertain Significance",
  "classification": "uncertain_significance",
  "zygosity_raw": "Heterozygous",
  "zygosity": "heterozygous",
  "associated_phenotype": "Rett syndrome",
  "mode_of_inheritance_raw": "X-linked dominant",
  "mode_of_inheritance": "x_linked_dominant",
  "is_secondary_finding": false
}
```

A field that ends in `_raw` holds the text as the report prints it. The field
without `_raw` holds the category that Gentrex should choose. The truth file
also holds what `gentrex normalize` should add, such as HGNC:6990 for MECP2
and MONDO:0010726 for the condition.

## The truth comes first

The generator never asks a language model what a report says. Code decides
every value first, from public databases. Only then is the report made around
those values. A model that wrote the values itself could contradict itself,
with a protein change that doesn't follow from the DNA change, or a table and
a paragraph that give different zygosities.

A report is made in five steps:

![The five steps of the generator. Code and a seed sample the case, with one of the report templates, and write the truth file. An LLM writes the report's free text, code fills the template's HTML with the truth and that text, and Chrome renders it as a PDF. check.py compares the PDF text with the truth file, and a case that fails is written again. The PDFs that pass are scanned at two levels with Pillow and copied as clean images, so each report comes as a native, scan, fax, mixed or image PDF, all with one truth file.](../images/benchmark-generator.svg)

## Step 1: Sample the case

Code draws each case from a random stream that starts from a seed, the text
in `sample.seed` of `settings.yaml`. The same seed and the same reference
files always give the same cases, so anyone can rebuild the benchmark.

First comes the test, and with it the possible results:

| Test | Share of cases | Results |
| --- | --- | --- |
| Multigene panel | 20% | positive, negative, VUS only, positive with a VUS. Three templates can also report an indeterminate result, a pathogenic variant and a VUS in the same recessive gene. |
| Exome or genome | 17% | the same, or negative with a secondary finding. A genome can also find a uniparental disomy. |
| Carrier screen | 16% | carrier, negative |
| Chromosomal microarray | 12% | a pathogenic or likely pathogenic copy-number change, one of uncertain significance, negative |
| Single gene | 9% | positive, negative, VUS only, and indeterminate as for panels |
| One known variant | 7% | positive, negative |
| Repeat expansion of FMR1, HTT or C9orf72 | 5% | FMR1: a premutation carrier, a full mutation, normal. HTT and C9orf72: an expanded allele, normal. |
| Chromosome analysis | 5% | an abnormal karyotype, a balanced translocation, a normal karyotype |
| Mitochondrial genome | 4% | positive, negative |
| SMN1 copy number, for spinal muscular atrophy | 3% | a carrier, affected, normal |
| Methylation of 15q11.2q13, for Prader-Willi and Angelman syndromes | 2% | positive, with no variant to extract, or normal |

The dev and test cases each have these shares, rounded to whole cases.

Panels, exomes, single-gene tests and tests of one known variant belong to
one of nine clinical areas, such as epilepsy, cardiomyopathy or hereditary
cancer. The area gives the genes, the patient's age range and the reason for
testing. Carrier screens use ten recessive genes, among them CFTR and HEXA,
and the UK-style carrier test looks at CFTR only.

The variants come from ClinVar's release of November 2026, in the genes of
the test. A variant qualifies when ClinVar classifies it as pathogenic,
likely pathogenic or of uncertain significance, with a review status of
"criteria provided" or higher and without conflicts. Its condition must have
a MONDO ID, a mode of inheritance and features in HPO's annotations. A
condition that fewer than a tenth of the gene's variants have is left out,
because it is often outside the clinical area that tests the gene. So the
HGVS, classification, condition and IDs of every variant are real. Deletions
and duplications of whole exons qualify too, written as ClinVar writes them,
as c.(?_5299)_(5572_?)del.

The copy-number changes of microarrays come from ClinVar as well. A change
qualifies when it is a gain or loss of 50 kb to 15 Mb with the same review
status, and ClinVar gives its positions on both GRCh37 and GRCh38. Two array
templates print positions on GRCh37 and one on GRCh38. Karyotypes,
uniparental disomies, repeat sizes, SMN1 copy numbers and methylation results
come from short lists and rules in `sample.py`, each with the MONDO ID and
HPO features of its syndrome.

The patient follows from the findings. An X-linked recessive finding makes
the patient male, and an X-linked dominant one female. A karyotype or a
copy-number change of a sex chromosome fixes the sex too. The zygosity
follows from the inheritance and the sex. A male with an X-linked variant is
hemizygous, and a patient diagnosed with a recessive condition is homozygous.
The patient's features are two to five of the condition's most frequent
features in HPO, leaving out features of the other sex. A copy-number change
without such a condition gets features of children who are sent for a
microarray, such as developmental delay or seizures.

Each case gets one of the 21 report templates that report its kind of test.
Before any case is drawn, the cases of each kind are spread over its
templates. The kinds that the fewest templates report come first, and then
cases move from fuller to emptier templates. A case can only move to a
template of its kind, so a move may pass through a template in between,
which takes a case of one kind and gives up a case of another. So every
template gets about the same share, at least 8 of the 200 test cases.

The templates can't all get the same number of cases, because the shares of
the tests are fixed first. The `karyotype` template is the only one that
reports chromosome analysis, and it reports nothing else. It therefore gets
that test's 5% of the cases, which is 10 of the 200 test cases. The four
templates that report only carrier screens share the 32 carrier cases and
get 8 each. A template that reports several tests may get cases of only
some of them, because its other tests go to templates that would otherwise
have too few cases. The table under [Templates](#templates) gives every
template's count.

The case also gets the IDs and dates in its template's formats, and one to
three challenge tags, which the section [Challenge tags](#challenge-tags)
below describes.

## Step 2: Write the report

A language model writes only the report's free text. It gets a short card
with the test, the patient's age and sex, the meaning of the result and the
variants. For the example report, the card says, in short:

```json
{
  "test": "Comprehensive Neurodevelopmental Panel",
  "reason_for_testing": "Global developmental delay",
  "patient": {"age_years": 11, "sex": "Female"},
  "result": "Only variants of uncertain significance were found.",
  "variants": [
    {
      "gene": "MECP2",
      "change": "c.1101C>A",
      "zygosity": "heterozygous",
      "classification": "variant of uncertain significance",
      "condition": "Rett syndrome",
      "inheritance": "X-linked dominant"
    }
  ]
}
```

The model answers in JSON with six parts: a summary, an interpretation, the
evidence for each variant, a description of the condition, next steps and a
summary for the patient. That is about 1,500 tokens, the pieces of words that
language models read and write. The instructions in `gentrex-bench/generator/prompt.md` keep
the model from writing IDs, dates, names, the patient's features,
karyotypes, array results and genomic positions, because code prints those.
It writes a DNA change only when the `repeated_variant` tag asks for it.

Code then fills the report's template with the case's values, its
distractors and the model's text. Every value is printed where the layout
puts it, exactly as the truth has it. Details outside the truth, such as the
ordering clinician, addresses and order numbers, are made up from a random
stream seeded with the case ID.

The model can be any model on a server that accepts requests in OpenAI's
format, on your own GPUs or hosted, except a Gemma model. Gentrex extracts
with Gemma, and it would then read text that its own model family wrote. The
default is Meta's Muse Glimmer 30B.

## Step 3: Render the PDF

Gentrex reads PDFs, so the filled HTML is printed to PDF by Google Chrome,
which runs in the background without a window. Every page gets a footer that
marks the report as synthetic:

```text
SYNTHETIC TEST REPORT - fictional patient and laboratory - not for clinical use | SYN-0065 | Page 1 of 2
```

## Step 4: Check against the truth

`check.py` reads the PDF's text with pdfplumber, as `gentrex transcribe`
does. The report passes when:

- every page has the synthetic footer,
- every value of the truth and every distractor is in the text,
- the text names the genome build of the truth and no other, and
- the text names no DNA change (c. or m.), array result or karyotype other
  than those of the truth and the distractors.

The last rule catches a model that copies a variant wrongly. A report that
fails gets its text written again, up to three times. A report that passes
gets its truth file, with the text of every page and the page of each
variant. Nobody edits a truth file by hand.

## Step 5: Scan

Each report comes in five versions, so that Gentrex can also be tested on
scanned pages:

| Version | What it looks like |
| --- | --- |
| `native` | The PDF as Chrome printed it, with a text layer |
| `scan` | Page images with a slight skew, blur, noise and JPEG compression, as from an office scanner |
| `fax` | Page images at half the vertical resolution, with a larger skew, in black and white, with speckles and streaks |
| `mixed` | The native PDF with about a third of its pages scanned |
| `image` | Clean page images whose only text is a short document code, as some labs' PDFs come |

The damage is drawn from a random stream seeded with the case ID, so a
report always gets the same copies. All five versions share one truth file.
Every report gets all five, and none is drawn at a rate.
[Benchmark design](benchmark.md#benchmark-set) gives the reason.

## Templates

Each template follows one layout family of the sample reports that genetics
labs publish on their websites.
[Public sample reports](benchmark.md#public-sample-reports) lists the sample
reports behind each template. The lab names are invented. Each is a colour
that starts with the same letter as the real lab, as Indigo for Invitae, and
templates that follow the same real lab share it.

| Template | Fictional lab | Follows | Tests | Dev cases | Test cases |
| --- | --- | --- | --- | --- | --- |
| `graybar-panel` | Aqua Genetics | Ambry | panel, single gene | 6 | 12 |
| `exome-box` | Aqua Genetics | Ambry | exome | 6 | 8 |
| `genome-card` | Aqua Genetics | Ambry | genome, with uniparental disomy | 0 | 8 |
| `snp-array` | Aqua Genetics | Ambry | chromosomal microarray, on GRCh38 | 5 | 11 |
| `chart` | Apricot Reference Laboratories | ARUP | one known variant | 7 | 8 |
| `lis-printout` | Apricot Reference Laboratories | ARUP | single gene, one known variant | 0 | 8 |
| `findings-grid` | Bronze Clinical Genomics | Blueprint | panel, mitochondrial genome | 6 | 12 |
| `screen-badge` | Bronze Clinical Genomics | Blueprint | carrier screen | 5 | 8 |
| `results-statement` | Bronze Clinical Genomics | Blueprint | panel | 6 | 12 |
| `exome-findings` | Bronze Clinical Genomics | Blueprint | exome | 5 | 9 |
| `dx-banner` | Indigo Genetic Testing | Invitae | panel, single gene | 6 | 11 |
| `carrier-grid` | Indigo Genetic Testing | Invitae | carrier screen | 0 | 8 |
| `teal-banner` | Lilac Molecular Laboratory | Labcorp | single gene, carrier screen | 5 | 8 |
| `enterprise` | Lilac Molecular Laboratory | Labcorp | carrier screen, single gene, FMR1 repeats, SMN1 copy number | 5 | 11 |
| `carrier-banner` | Lilac Molecular Laboratory | Labcorp | carrier screen | 5 | 8 |
| `microarray-printout` | Lilac Molecular Laboratory | Labcorp | chromosomal microarray, on GRCh37 | 6 | 11 |
| `karyotype` | Lilac Molecular Laboratory | Labcorp | chromosome analysis | 5 | 10 |
| `patient-page` | Navy Genomic Laboratory | NHS | carrier test of CFTR, in UK style | 5 | 8 |
| `one-page` | Navy Genomic Laboratory | NHS | single gene, carrier test of CFTR, in UK style | 5 | 8 |
| `summary-line` | Plum Genetics | PreventionGenetics | panel, single gene, chromosomal microarray on GRCh37, HTT and C9orf72 repeats, methylation | 6 | 12 |
| `summary-sidebar` | Plum Genetics | PreventionGenetics | exome | 6 | 9 |

The counts are those of the default settings, with 100 dev cases, 200 test
cases and the seed `gentrex-synthetic-1`. `genome-card`, `carrier-grid` and
`lis-printout` appear only in the test cases. They show how Gentrex does on
layouts that it wasn't tuned on.

A template fixes everything that stays the same between a lab's reports:

- the header fields and their labels,
- how the result and the variants are shown,
- the sections, the fonts and the colors,
- the lab's fixed text, such as its methods and limitations, with the genome
  build that the methods name, and
- the wording of values, for example "HET" for heterozygous, "Pathogenic
  Mutation", or a headline that names the variant.

The layout is the HTML file `gentrex-bench/generator/templates/<template>.html`.
Each lab's look is in a CSS file, such as `templates/aqua.css`. The
wording, the formats of IDs and dates, and the tests a template reports are
in `gentrex-bench/generator/labs.py`.

## Challenge tags

Each case gets one to three challenge tags. A tag makes the report harder in
one known way, and the truth file lists the case's tags, so results can be
split by tag. Each tag appears in 11 to 24 of the 200 test cases. A tag that
can't change a report, such as `legacy_gene_symbol` for a gene without a
previous symbol, is dropped from it.

| Tag | What it changes in the report |
| --- | --- |
| `multiple_variants` | A second variant, of uncertain significance in another gene |
| `table_split_across_pages` | The variant table breaks across two pages |
| `late_page_evidence` | A cover sheet and a page about the report come first, so the variants are on page 3 or later |
| `provided_phenotype_page` | The patient's features appear only on a page of their own at the end |
| `repeated_variant` | The model's text names each variant again, with its DNA change |
| `trio_columns` | An exome of a child and both parents, with the parents' genotypes and the variant's origin |
| `negated_or_uncertain_phenotypes` | One feature is absent or uncertain, as "no seizures" or "possible seizures" |
| `family_history_distractor` | A relative's feature, as "Family history is notable for a maternal aunt with Hyperreflexia." |
| `gene_list_distractor` | The panel's genes are listed, most of them without a finding |
| `boilerplate_variant_notation` | The methods give an example DNA change that isn't the patient's |
| `similar_identifiers` | Two more IDs that look like the lab number |
| `multiple_patient_ids` | The submitter's patient ID field holds two IDs |
| `explicitly_unavailable` | The MRN, submitter's patient ID or collection date reads "Not provided" |
| `missing_optional_fields` | One or two fields are left out with their labels, such as the date received |
| `legacy_gene_symbol` | The gene appears under a previous HGNC symbol |
| `nonstandard_hgvs` | The protein change is in one-letter code, as p.R412W |
| `unusual_date_format` | Dates in a format that `gentrex normalize` doesn't read, as 6.12.2019 |
| `ambiguous_specimen` | A specimen without a clear category, as "Saliva/Buccal" |

Some templates add distractors of their own, as real reports do. The
Bronze templates cite another variant of the same gene from the
literature, the larger carrier screens list normal FMR1 and SMN1 results
under "Results to note", and a negative test of one known variant names the
variant that wasn't found. A normal microarray prints its normal result in
ISCN, which isn't a karyotype. A normal repeat test prints the repeat sizes,
and an SMA test prints the SMN2 copy number, and for a normal result the SMN1
copy number too. The one-line summary template prints the ClinVar ID of each
variant. The two Navy templates name the partner whose result led to a
carrier test, with the partner's variant and date of birth.

## Where the code is

The generator is in `gentrex-bench/generator/`:

| File | What it does |
| --- | --- |
| `generate.py` | The two commands, `sample` and `build` |
| `settings.yaml` | The settings of both commands |
| `sources.py` | Reads ClinVar, HPO, MONDO and HGNC |
| `sample.py` | Samples each case, with its truth, distractors, tags and the model's card |
| `labs.py` | The templates' wording, IDs, date formats and tests, and the clinical areas |
| `templates/` | The templates' HTML, and each lab's CSS and shared pieces |
| `write.py`, `prompt.md` | Ask the model for a report's text |
| `fill.py` | Fills a template with a case and the model's text |
| `render.py` | Prints HTML to PDF with Chrome |
| `check.py` | Checks a PDF against its case and writes the truth file |
| `scan.py` | Makes the scan, fax, mixed and image copies |
