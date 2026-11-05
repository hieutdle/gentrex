"""Sample the cases: the whole truth of each report, before any text is written.

Each case holds the record that a perfect `gentrex extract` writes, what a
perfect `gentrex normalize` adds, the distractors that the report prints but
that must not be extracted, and the card that tells the writing model what to
print. The same seed and references give the same cases.
"""

import collections
import dataclasses
import datetime
import random
from typing import Any

import labs
import sources

from gentrex import config

_VERSION = "gentrex-synthetic-1"

_PAGES = {
    "A": (3, 5),
    "B": (5, 8),
    "C": (4, 7),
    "D": (2, 3),
    "E": (3, 5),
    "F": (3, 6),
    "G": (3, 6),
    "H": (2, 4),
}
_PEDIATRIC = (
    "Epilepsy",
    "Noonan Spectrum",
    "Neurodevelopmental",
    "Neuromuscular",
    "Hearing Loss",
)
_RESULT_CATEGORY = {
    "positive": "positive",
    "mixed": "positive",
    "negative": "negative",
    "secondary_finding": "negative",
    "vus_only": "uncertain",
    "carrier": "carrier",
}
_ORIGIN = {
    "de_novo": "De novo",
    "maternal": "Maternally inherited",
    "paternal": "Paternally inherited",
    "both_parents": "Inherited from both parents",
}
_RELATIVES = (
    "mother",
    "father",
    "maternal aunt",
    "paternal uncle",
    "older brother",
    "maternal grandmother",
    "paternal cousin",
)
_AMINO = {
    "Ala": "A",
    "Arg": "R",
    "Asn": "N",
    "Asp": "D",
    "Cys": "C",
    "Gln": "Q",
    "Glu": "E",
    "Gly": "G",
    "His": "H",
    "Ile": "I",
    "Leu": "L",
    "Lys": "K",
    "Met": "M",
    "Phe": "F",
    "Pro": "P",
    "Ser": "S",
    "Thr": "T",
    "Trp": "W",
    "Tyr": "Y",
    "Val": "V",
    "Ter": "*",
    "Sec": "U",
}

# Tags that change the report's layout or add distractors, with the
# instruction for the writing model. Tags that change values (legacy symbols,
# one-letter protein changes, unusual dates, ambiguous specimens, several
# patient IDs, negated features) are realized in the values themselves.
WRITING_TAGS = {
    "table_split_across_pages": "Split the variant table across two pages and "
    "repeat its header row on the second page.",
    "late_page_evidence": "Print the variant table and the patient's features on "
    "page 3 or later, under natural headings. Pages 1 and 2 give the header, the "
    "result and general text only.",
    "provided_phenotype_page": "Print the patient's features only on the last "
    "page, as a list under the heading 'Provided Clinical Phenotype'. Elsewhere, "
    "refer to them as 'the reported features'.",
    "repeated_variant": "Describe each variant a second time in the "
    "interpretation, with the same gene and notation as in the table.",
}
TAGS = (
    *WRITING_TAGS,
    "gene_list_distractor",
    "boilerplate_variant_notation",
    "family_history_distractor",
    "similar_identifiers",
    "trio_columns",
    "multiple_variants",
    "negated_or_uncertain_phenotypes",
    "explicitly_unavailable",
    "missing_optional_fields",
    "multiple_patient_ids",
    "legacy_gene_symbol",
    "nonstandard_hgvs",
    "unusual_date_format",
    "ambiguous_specimen",
)


@dataclasses.dataclass
class _Plan:
    """The choices that the tags depend on."""

    lab: labs.Lab
    kind: str
    scenario: str
    area: labs.Area | None
    pages: int


def _one_letter(protein: str) -> str:
    """Returns a three-letter protein change in one-letter code, as p.R412W."""
    for three, one in _AMINO.items():
        protein = protein.replace(three, one)
    return protein.replace("(", "").replace(")", "")


def _variant_type(variant: sources.Variant) -> str | None:
    """Returns the kind of a variant from its HGVS, as a lab would name it."""
    c, p = variant.hgvs_c or "", variant.hgvs_p or ""
    if variant.hgvs_m:
        return None
    if p.endswith("fs"):
        return "Frameshift"
    if p.endswith("Ter") or p.endswith("*"):
        return "Nonsense"
    if p.endswith("="):
        return "Synonymous"
    if "delins" in c:
        return "Deletion-insertion"
    if "del" in c and p:
        return "In-frame deletion"
    if "dup" in c and p:
        return "In-frame duplication"
    if not p and ("+1" in c or "+2" in c or "-1" in c or "-2" in c):
        return "Splice site"
    if not p:
        return "Intronic"
    return "Missense"


def _zygosity(inheritance: str, sex: str, diagnostic: bool) -> str:
    if inheritance == "mitochondrial":
        return "heteroplasmic"
    if inheritance.startswith("x_linked") and sex == "Male":
        return "hemizygous"
    if inheritance == "autosomal_recessive" and diagnostic:
        return "homozygous"
    return "heterozygous"


class _Sampler:
    """Samples one case after another from one random stream."""

    def __init__(self, refs: sources.References, seed: str) -> None:
        self._refs = refs
        self._rng = random.Random(seed)
        self._tag_counts: collections.Counter[str] = collections.Counter()
        self._fields = list(config.load_schema()["properties"])
        schema = config.load_schema()["properties"]["variants"]["items"]
        self._variant_fields = list(schema["properties"])

    def _pick_variant(
        self,
        genes: list[str],
        classes: set[str],
        modes: set[str] | None = None,
        exclude: set[str] = frozenset(),  # pyright: ignore[reportArgumentType]
    ) -> sources.Variant | None:
        rng = self._rng
        candidates = [
            v
            for gene in genes
            if gene not in exclude
            for v in self._refs.variants.get(gene, [])
            if v.classification in classes
            and (modes is None or v.disease.inheritance in modes)
            and (v.hgvs_m is None) == (not gene.startswith("MT-"))
        ]
        if not candidates:
            return None
        gene = rng.choice(sorted({v.gene for v in candidates}))
        return rng.choice([v for v in candidates if v.gene == gene])

    def _plan(self, split: str) -> _Plan:
        rng = self._rng
        lab = rng.choice(
            [lab for lab in labs.LABS if split == "test" or not lab.held_out]
        )
        kind = rng.choices(
            ["panel", "exome", "single_gene", "carrier", "mito"],
            weights=[45, 25, 12, 12, 6],
        )[0]
        scenario = rng.choice(
            {
                "panel": ["positive", "positive", "negative", "vus_only", "mixed"],
                "exome": [
                    "positive",
                    "positive",
                    "negative",
                    "vus_only",
                    "mixed",
                    "secondary_finding",
                ],
                "single_gene": ["positive", "negative", "vus_only"],
                "carrier": ["carrier", "carrier", "negative"],
                "mito": ["positive", "negative"],
            }[kind]
        )
        area = None
        if kind == "exome":
            area = rng.choice([a for a in labs.AREAS if a.name in _PEDIATRIC])
        elif kind in ("panel", "single_gene"):
            area = rng.choice(labs.AREAS)
        return _Plan(lab, kind, scenario, area, rng.randint(*_PAGES[lab.key]))

    def _tags(self, plan: _Plan, has_variants: bool, has_features: bool) -> list[str]:
        rng = self._rng
        allowed = set(TAGS)
        if plan.kind != "panel":
            allowed.discard("gene_list_distractor")
        if plan.kind != "exome" or plan.lab.key in ("D",):
            allowed.discard("trio_columns")
        if plan.scenario not in ("positive", "vus_only"):
            allowed.discard("multiple_variants")
        if not has_variants:
            allowed -= {
                "table_split_across_pages",
                "repeated_variant",
                "legacy_gene_symbol",
                "nonstandard_hgvs",
            }
        if not has_features:
            allowed -= {"negated_or_uncertain_phenotypes", "provided_phenotype_page"}
        if plan.pages < 3:
            allowed -= {"table_split_across_pages", "late_page_evidence"}
        if "submitter_patient_id" not in plan.lab.ids(random.Random(0)):
            allowed.discard("multiple_patient_ids")
        if "provided_phenotype_page" in allowed and "late_page_evidence" in allowed:
            allowed.discard(
                rng.choice(["provided_phenotype_page", "late_page_evidence"])
            )
        count = rng.choice([1, 2, 2, 3])
        # Sorted first, because a set's order changes from process to process.
        ranked = sorted(
            sorted(allowed), key=lambda t: (self._tag_counts[t], rng.random())
        )
        chosen = ranked[:count]
        if "table_split_across_pages" in chosen and "multiple_variants" in allowed:
            chosen.append("multiple_variants")
        self._tag_counts.update(chosen)
        return sorted(set(chosen))

    def _variants(
        self, plan: _Plan, tags: set[str]
    ) -> list[tuple[sources.Variant, bool]]:
        """Returns the variants of the case, each with whether it is secondary."""
        pathogenic = {"pathogenic", "likely_pathogenic"}
        vus = {"uncertain_significance"}
        genes: list[str]
        if plan.kind == "mito":
            genes = list(labs.MITO_GENES)
        elif plan.kind == "carrier":
            genes = list(labs.CARRIER_GENES)
        else:
            assert plan.area is not None
            genes = list(plan.area.genes)
            if plan.kind == "single_gene":
                genes = [
                    self._rng.choice([g for g in genes if g in self._refs.variants])
                ]
        picks: list[tuple[sources.Variant | None, bool]] = []
        if plan.scenario == "positive":
            picks.append((self._pick_variant(genes, pathogenic), False))
            if "multiple_variants" in tags:
                used = {p.gene for p, _ in picks if p}
                picks.append((self._pick_variant(genes, vus, exclude=used), False))
        elif plan.scenario == "mixed":
            first = self._pick_variant(genes, pathogenic)
            used = {first.gene} if first else set()
            picks += [
                (first, False),
                (self._pick_variant(genes, vus, exclude=used), False),
            ]
        elif plan.scenario == "vus_only":
            picks.append((self._pick_variant(genes, vus), False))
            if "multiple_variants" in tags:
                used = {p.gene for p, _ in picks if p}
                picks.append((self._pick_variant(genes, vus, exclude=used), False))
        elif plan.scenario == "carrier":
            picks.append(
                (self._pick_variant(genes, pathogenic, {"autosomal_recessive"}), False)
            )
        elif plan.scenario == "secondary_finding":
            picks.append(
                (
                    self._pick_variant(
                        list(labs.SECONDARY_GENES), pathogenic, {"autosomal_dominant"}
                    ),
                    True,
                )
            )
        return [(v, secondary) for v, secondary in picks if v is not None]

    def _features(
        self, disease: sources.Disease | None, negated: bool
    ) -> list[tuple[str, str, bool | None]]:
        """Returns (HPO ID, printed text, present) for each of the patient's features.

        Returns:
            The features, none of whose text contains another's.
        """
        if disease is None:
            return []
        rng = self._rng
        ids = list(disease.phenotypes)
        rng.shuffle(ids)
        features: list[tuple[str, str, bool | None]] = []
        for hpo_id in ids:
            term = self._refs.terms[hpo_id]
            names = [term.label, *[s for s in term.synonyms if len(s) < 40]]
            text = rng.choice(names[:4])
            texts = [t.casefold() for _, t, _ in features]
            if any(text.casefold() in t or t in text.casefold() for t in texts):
                continue
            features.append((hpo_id, text, True))
            if len(features) == rng.randint(2, 5):
                break
        if negated and len(features) >= 2:
            hpo_id, text, _ = features[-1]
            features[-1] = (hpo_id, text, rng.choice([False, None]))
        return features

    def _dates(self, plan: _Plan, age: int, lab_prints_started: bool) -> dict[str, Any]:
        rng = self._rng
        report = datetime.date(2019, 1, 1) + datetime.timedelta(rng.randint(0, 2800))
        turnaround = (
            rng.randint(42, 120) if plan.kind == "exome" else rng.randint(14, 70)
        )
        received = report - datetime.timedelta(turnaround)
        collected = received - datetime.timedelta(rng.randint(1, 10))
        started = received + datetime.timedelta(rng.randint(0, 5))
        birth = collected - datetime.timedelta(365 * age + rng.randint(30, 360))
        dates = {
            "date_of_birth": birth,
            "collection_date": collected,
            "received_date": received,
            "report_date": report,
        }
        if lab_prints_started:
            dates["test_started_date"] = started
        return dates

    def case(self, number: int, split: str) -> dict[str, Any]:
        """Returns one case: its plan, truth, distractors and card."""
        rng = self._rng
        plan = self._plan(split)
        lab, area = plan.lab, plan.area
        case_id = f"SYN-{number:04d}"
        provisional = self._variants(plan, {"multiple_variants"})
        primary = [v for v, secondary in provisional if not secondary]
        disease = primary[0].disease if primary else None
        if disease is None and area is not None:
            fallback = self._pick_variant(list(area.genes), {"pathogenic"})
            disease = fallback.disease if fallback else None
        if plan.kind == "mito" and disease is None:
            fallback = self._pick_variant(list(labs.MITO_GENES), {"pathogenic"})
            disease = fallback.disease if fallback else None
        has_features = plan.kind != "carrier" and disease is not None
        tags = set(self._tags(plan, bool(provisional), has_features))
        found = provisional
        if "multiple_variants" not in tags and plan.scenario in (
            "positive",
            "vus_only",
        ):
            found = provisional[:1]
        if plan.scenario != "negative" and not found:
            return self.case(number, split)

        needs_male = any(
            v.disease.inheritance.startswith("x_linked") and not secondary
            for v, secondary in found
        )
        sex = "Male" if needs_male else rng.choice(["Female", "Male"])
        if area is not None:
            age = rng.randint(*area.age)
        elif plan.kind == "carrier":
            age = rng.randint(20, 40)
        else:
            age = rng.randint(4, 40)
        trio = "trio_columns" in tags
        if trio:
            age = min(age, 12)

        ids = lab.ids(rng)
        record: dict[str, Any] = dict.fromkeys(self._fields)
        record.update(ids)
        if "multiple_patient_ids" in tags:
            record["submitter_patient_id"] += (
                f", {labs.LABS[0].ids(rng)['submitter_patient_id']}"
            )
        dates = self._dates(
            plan, age, "Test Started" in lab.layout or "Started" in lab.layout
        )
        if "unusual_date_format" in tags:
            date_format = rng.choice(list(labs.UNUSUAL_DATE_FORMATS.values()))
        else:
            date_format = labs.DATE_FORMATS[lab.date_format]
        for field, value in dates.items():
            record[field] = date_format(value)
        record["sex"] = sex if lab.prints_sex else None
        specimens = (
            labs.AMBIGUOUS_SPECIMENS if "ambiguous_specimen" in tags else labs.SPECIMENS
        )
        specimen, specimen_category = rng.choice(specimens)
        record["specimen_type"] = specimen

        if plan.kind == "exome":
            record["test_name"] = lab.exome_name[1 if trio else 0]
            record["test_type"] = "exome"
        elif plan.kind == "panel":
            assert area is not None
            record["test_name"] = lab.panel_name(area.name)
            record["test_type"] = "panel"
        elif plan.kind == "single_gene":
            gene = found[0][0].gene if found else rng.choice(area.genes)  # pyright: ignore[reportOptionalMemberAccess]
            record["test_name"] = (
                f"{gene} Gene Sequencing and Deletion/Duplication Analysis"
            )
            record["test_type"] = "single_gene"
        elif plan.kind == "carrier":
            record["test_name"] = rng.choice(
                ["Expanded Carrier Screen", "Carrier Screening Panel"]
            )
            record["test_type"] = "panel"
        else:
            record["test_name"] = "Mitochondrial Genome Sequencing"
            record["test_type"] = "other"
        record["overall_result_raw"] = lab.result[plan.scenario]
        if area is not None:
            record["clinical_indication"] = rng.choice(area.indication)
        elif plan.kind == "carrier":
            record["clinical_indication"] = "Reproductive carrier screening"
        else:
            record["clinical_indication"] = "Suspected mitochondrial disorder"
        record["lab_name"] = lab.name

        features = self._features(
            disease if has_features else None, "negated_or_uncertain_phenotypes" in tags
        )
        record["patient_phenotypes"] = [
            {"text": text, "present": present} for _, text, present in features
        ]

        variants, normalized_variants = [], []
        for variant, secondary in found:
            zygosity = _zygosity(
                variant.disease.inheritance,
                sex,
                diagnostic=not secondary
                and plan.scenario != "carrier"
                and variant.classification != "uncertain_significance",
            )
            printed_gene = variant.gene
            previous = self._refs.previous_symbols.get(variant.gene, [])
            if "legacy_gene_symbol" in tags and previous:
                printed_gene = rng.choice(previous)
            protein = variant.hgvs_p
            if protein and "nonstandard_hgvs" in tags:
                protein = _one_letter(protein)
            elif protein and lab.protein_parentheses:
                protein = f"p.({protein[2:]})"
            zygosity_raw = lab.zygosity[zygosity]
            if zygosity == "heteroplasmic":
                zygosity_raw = f"{zygosity_raw} ({rng.randint(15, 85)}%)"
            origin = None
            if trio:
                if (
                    variant.classification != "uncertain_significance"
                    and zygosity == "heterozygous"
                ):
                    origin = "de_novo"
                elif zygosity == "hemizygous":
                    origin = "maternal"
                elif zygosity == "homozygous":
                    origin = "both_parents"
                else:
                    origin = rng.choice(["maternal", "paternal"])
            item: dict[str, Any] = dict.fromkeys(self._variant_fields)
            item.update(
                gene_symbol=printed_gene,
                transcript=variant.transcript,
                hgvs_c=variant.hgvs_c,
                hgvs_p=protein,
                dna_change_raw=variant.hgvs_m,
                classification_raw=lab.classification[variant.classification],
                classification=variant.classification,
                zygosity_raw=zygosity_raw,
                zygosity=zygosity,
                parental_origin_raw=_ORIGIN[origin] if origin else None,
                parental_origin=origin,
                associated_phenotype=variant.disease.label,
                mode_of_inheritance_raw=lab.inheritance[variant.disease.inheritance],
                mode_of_inheritance=variant.disease.inheritance,
                is_secondary_finding=secondary,
                variant_type_raw=_variant_type(variant),
            )
            variants.append(item)
            normalized_variants.append(
                {
                    "gene_symbol": variant.gene,
                    "hgnc_id": variant.hgnc_id,
                    "disease_id": variant.disease.mondo_id,
                    "clinvar_variation_id": variant.variation_id,
                }
            )
        record["variants"] = variants

        distractors: list[dict[str, str]] = []
        instructions = [WRITING_TAGS[t] for t in sorted(tags) if t in WRITING_TAGS]
        if "gene_list_distractor" in tags and area is not None:
            genes = [
                g for g in area.genes if g not in {v["gene_symbol"] for v in variants}
            ]
            distractors += [{"kind": "gene_list", "text": g} for g in genes]
            instructions.append(
                "Print the genes analyzed as a list or table, in this order: "
                f"{', '.join(genes)}. None of them has a finding."
            )
        if "boilerplate_variant_notation" in tags:
            example = (
                f"c.{rng.randint(100, 3000)}{rng.choice('ACGT')}>{rng.choice('ACGT')}"
            )
            distractors.append({"kind": "boilerplate_hgvs", "text": example})
            instructions.append(
                f"In Methods or Limitations, quote '{example}' as an example of "
                "HGVS notation. It is not a finding in this patient."
            )
        if "family_history_distractor" in tags:
            mine = {hpo_id for hpo_id, _, _ in features}
            pool = [t for t in (disease.phenotypes if disease else ()) if t not in mine]
            if pool:
                relative = rng.choice(_RELATIVES)
                text = self._refs.terms[rng.choice(pool)].label
                distractors.append({"kind": "relative_feature", "text": text})
                instructions.append(
                    f"In a family history passage, state that the patient's "
                    f"{relative} has {text}. Keep it clearly about the relative, "
                    "outside the patient's features."
                )
        if "similar_identifiers" in tags:
            for label in rng.sample(
                ["Specimen #", "Requisition #", "Order #", "Client ID"], 2
            ):
                value = f"{rng.randint(10, 99)}{rng.randint(100000, 999999)}"
                distractors.append({"kind": "identifier", "text": value})
                instructions.append(
                    f"Print '{label}' with the value {value} near the accession number."
                )
        if trio:
            instructions.append(
                "Add MOTHER and FATHER columns to the variant table with each "
                "parent's genotype, consistent with the origin of each variant."
            )
        unavailable = None
        if "explicitly_unavailable" in tags:
            present = [
                f
                for f in ("mrn", "submitter_patient_id", "collection_date")
                if record[f] is not None
            ]
            unavailable = rng.choice(present)
            record[unavailable] = None
            instructions.append(
                f"Print the label for the {_LABELS[unavailable]} with the value "
                "'Not provided'."
            )
        omitted = []
        if "missing_optional_fields" in tags:
            optional = [
                f
                for f in (
                    "test_started_date",
                    "received_date",
                    "submitter_patient_id",
                    "specimen_type",
                )
                if record[f] is not None
            ]
            omitted = rng.sample(optional, min(len(optional), rng.randint(1, 2)))
            for field in omitted:
                record[field] = None

        normalized = {
            field: (dates[field].isoformat() if record[field] is not None else None)
            if field in dates
            else None
            for field in (
                "date_of_birth",
                "collection_date",
                "received_date",
                "test_started_date",
                "report_date",
            )
        }
        normalized.update(
            specimen_type=specimen_category if record["specimen_type"] else None,
            overall_result=_RESULT_CATEGORY[plan.scenario],
            variants=normalized_variants,
            patient_phenotypes=[{"hpo_id": hpo_id} for hpo_id, _, _ in features],
        )

        first_name = rng.choice(labs.FIRST_NAMES[sex])
        card = {
            "case_id": case_id,
            "laboratory": {"name": lab.name, "layout": lab.layout},
            "page_count": plan.pages,
            "patient": {
                "name": f"{first_name} {rng.choice(labs.LAST_NAMES)}",
                "age_years": age,
                "sex": sex,
                "sex_may_be_revealed": lab.prints_sex,
            },
            "values": {_LABELS[f]: record[f] for f in _LABELS if record[f] is not None},
            "result_meaning": _MEANING[plan.scenario],
            "variants": [_card_variant(v) for v in variants],
            "patient_features": [
                {
                    "text": f["text"],
                    "status": {True: "present", False: "absent", None: "uncertain"}[
                        f["present"]
                    ],
                }
                for f in record["patient_phenotypes"]
            ],
            "leave_out": [_LABELS[f] for f in omitted],
            "instructions": instructions,
        }
        return {
            "case_id": case_id,
            "split": split,
            "generator": _VERSION,
            "lab": lab.key,
            "kind": plan.kind,
            "scenario": plan.scenario,
            "tags": sorted(tags),
            "record": record,
            "normalized": normalized,
            "distractors": distractors,
            "unavailable": unavailable,
            "card": card,
        }


_LABELS = {
    "lab_name": "laboratory name (letterhead)",
    "mrn": "medical record number (MRN)",
    "submitter_patient_id": "submitter's patient ID",
    "lab_accession_number": "laboratory accession number",
    "date_of_birth": "date of birth",
    "sex": "sex",
    "specimen_type": "specimen",
    "collection_date": "collection date",
    "received_date": "date received",
    "test_started_date": "date testing started",
    "report_date": "report date",
    "test_name": "test name",
    "clinical_indication": "reason for testing",
    "overall_result_raw": "headline result",
}
_MEANING = {
    "positive": "A pathogenic or likely pathogenic variant explains the patient's "
    "features.",
    "mixed": "A pathogenic or likely pathogenic variant was found, and a variant of "
    "uncertain significance.",
    "negative": "No reportable variant was found.",
    "vus_only": "Only variants of uncertain significance were found.",
    "carrier": "The patient carries one pathogenic variant for a recessive "
    "condition and is not affected.",
    "secondary_finding": "The primary result is negative. A pathogenic variant was "
    "found in a gene of the ACMG secondary-findings list and is reported under "
    "Secondary Findings.",
}


def _card_variant(variant: dict[str, Any]) -> dict[str, Any]:
    names = {
        "gene_symbol": "gene",
        "transcript": "transcript",
        "hgvs_c": "c. change",
        "hgvs_p": "p. change",
        "dna_change_raw": "mtDNA change",
        "zygosity_raw": "zygosity",
        "classification_raw": "classification",
        "associated_phenotype": "condition",
        "mode_of_inheritance_raw": "inheritance",
        "parental_origin_raw": "origin",
        "variant_type_raw": "variant type",
    }
    card = {name: variant[field] for field, name in names.items() if variant[field]}
    card["finding"] = "secondary" if variant["is_secondary_finding"] else "primary"
    return card


def sample(refs: sources.References, seed: str, dev: int, test: int) -> list[dict]:
    """Returns `dev` dev cases and then `test` test cases, numbered from 1."""
    sampler = _Sampler(refs, seed)
    cases = []
    for split, count in (("dev", dev), ("test", test)):
        sampler._tag_counts.clear()
        for _ in range(count):
            cases.append(sampler.case(len(cases) + 1, split))
    return cases
