# Example reports

This folder holds one synthetic report for each of the 21 templates of
gentrex-bench, each with its truth file. `carrier-banner.pdf` also comes in
the four other copies that every benchmark report gets. Open a PDF to see what
Gentrex reads, and the JSON file of the same name to see what a perfect run of
`gentrex extract` and `gentrex normalize` would write for it.

These reports are not part of the benchmark. Their cases come from their own
seed, `gentrex-examples-1`, so none of them is one of the 300 cases of v1,
and scores never include them. Claude Haiku 5.5 wrote their free text, where
the benchmark uses the model in `build.model` of
`gentrex-bench/generator/settings.yaml`. Everything else is made as for the
benchmark, and every PDF passed the generator's check against its truth.

## Templates

| File | Lab | Test | Result |
| --- | --- | --- | --- |
| `carrier-banner` | Lilac Molecular Laboratory | Expanded Carrier Panel | carrier |
| `carrier-grid` | Indigo Genetic Testing | Comprehensive Carrier Screen | carrier |
| `chart` | Apricot Reference Laboratories | COL6A1 c.1611+1G>A Variant Analysis | negative |
| `dx-banner` | Indigo Genetic Testing | Comprehensive Noonan Spectrum Panel | positive |
| `enterprise` | Lilac Molecular Laboratory | Fragile X Carrier Screening | carrier |
| `exome-box` | Aqua Genetics | ExomeScan-Trio | secondary finding |
| `exome-findings` | Bronze Clinical Genomics | Exome Plus | positive |
| `findings-grid` | Bronze Clinical Genomics | Neurodevelopmental Panel | positive |
| `genome-card` | Aqua Genetics | Genome Sequencing | uniparental disomy |
| `graybar-panel` | Aqua Genetics | HearingScan | positive, with a VUS |
| `karyotype` | Lilac Molecular Laboratory | Chromosome Analysis, Blood | negative |
| `lis-printout` | Apricot Reference Laboratories | TECTA N1474fs Variant Analysis | negative |
| `microarray-printout` | Lilac Molecular Laboratory | Chromosomal Microarray, Pediatric | positive |
| `one-page` | Navy Genomic Laboratory | APC Gene Sequencing and Deletion/Duplication Analysis | negative |
| `patient-page` | Navy Genomic Laboratory | Cystic Fibrosis Carrier Test | carrier |
| `results-statement` | Bronze Clinical Genomics | Hereditary Cancer Panel | positive |
| `screen-badge` | Bronze Clinical Genomics | Comprehensive Carrier Screen | carrier |
| `snp-array` | Aqua Genetics | SNP Microarray | positive |
| `summary-line` | Plum Genetics | Prader-Willi/Angelman Syndrome Analysis via MS-MLPA | negative |
| `summary-sidebar` | Plum Genetics | Whole Exome Test, Trio Analysis | VUS only |
| `teal-banner` | Lilac Molecular Laboratory | SYNGAP1 Gene Sequencing and Deletion/Duplication Analysis | VUS only |

The labs are fictional. Each one's templates follow the public sample reports
of a real lab, which
[Templates](../../docs/development/benchmark-generator.md#templates) lists.

## The five copies

| File | What it looks like |
| --- | --- |
| `carrier-banner.pdf` | The PDF as Chrome printed it, with a text layer |
| `carrier-banner-scan.pdf` | Page images with a slight skew, blur, noise and JPEG compression, as from an office scanner |
| `carrier-banner-fax.pdf` | Page images at half the vertical resolution, with a larger skew, in black and white, with speckles and streaks |
| `carrier-banner-mixed.pdf` | The native PDF with about a third of its pages scanned |
| `carrier-banner-image.pdf` | Clean page images whose only text is a short document code |

All five share the truth file `carrier-banner.json`.
[How the benchmark generator works](../../docs/development/benchmark-generator.md)
explains the truth files, the challenge tags and the copies.
