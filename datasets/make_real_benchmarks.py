"""Build the built-in benchmark datasets from REAL, openly licensed systematic reviews.

Source: ASReview "systematic-review-datasets" (https://github.com/asreview/systematic-review-datasets),
tag `metadata-v1-final`, which holds the full records (title + abstract) and each review's
final inclusion decision. Every record is a real publication; labels are the review authors'.

Each benchmark is a sample: all relevant records (up to 40) plus randomly drawn irrelevant
ones, 150 records in total, with a fixed seed so the file is reproducible. The screening
criteria are each review's own eligibility criteria, copied from the paper's Methods
section and split into separate items.

Usage:
    git clone --depth 1 https://github.com/asreview/systematic-review-datasets /tmp/srd
    git -C /tmp/srd fetch --depth 1 origin metadata-v1-final && git -C /tmp/srd checkout FETCH_HEAD
    python datasets/make_real_benchmarks.py /tmp/srd
"""

import csv
import json
import random
import sys
from pathlib import Path

csv.field_size_limit(10**8)
ROOT = Path(__file__).parent.parent
OUT = ROOT / "apps/litprism-app/backend/services/benchmark_data"
SAMPLES = ROOT / "apps/litprism-app/frontend/public/samples"
SIZE, MAX_REL = 150, 40

DATASETS = [
    {
        "slug": "wilson-disease", "id": "Appenzeller-Herzog_2020", "name": "Wilson disease therapies",
        "topic": "Comparative effectiveness of common therapies for Wilson disease (controlled studies)",
        "citation": "Appenzeller-Herzog C, Mathes T, Heeres MLS, Weiss KH, Houwen RHJ, Ewald H. Comparative effectiveness of common therapies for Wilson disease: a systematic review and meta-analysis of controlled studies. Liver Int 2019;39(11):2136-2152.",
        "doi": "https://doi.org/10.1111/liv.14179", "licence": "CC-BY 4.0",
        "criteria": {
            "inclusion": ["Participants are patients with Wilson disease (any age or disease stage)", "The study drug is D-penicillamine, trientine, tetrathiomolybdate or zinc salts", "The study has a control group (placebo, no treatment, or another treatment that does not include the study drug)", "Prospective or retrospective controlled study (randomised or non-randomised trial, or comparative observational study)"],
            "exclusion": ["Animal study", "Case report, case series, cross-sectional study, before-after study, review or letter"]},
    },
    {
        "slug": "anxiety-cbt", "id": "van_Dis_2020", "name": "CBT for anxiety-related disorders",
        "topic": "Long-term outcomes of cognitive behavioural therapy for anxiety-related disorders",
        "citation": "van Dis EAM, van Veen SC, Hagenaars MA, Batelaan NM, Bockting CLH, van den Heuvel RM, Cuijpers P, Engelhard IM. Long-term outcomes of cognitive behavioral therapy for anxiety-related disorders: a systematic review and meta-analysis. JAMA Psychiatry 2020;77(3):265-273.",
        "doi": "https://doi.org/10.1001/jamapsychiatry.2019.3986", "licence": "CC-BY 4.0",
        "criteria": {
            "inclusion": ["Randomised clinical trial of cognitive behavioural therapy (cognitive restructuring and/or behavioural therapy such as exposure, including third-wave CBT)", "Participants are adults (or mostly adults, with some adolescents aged 16 or older)", "Participants have a diagnosed anxiety-related disorder (generalised anxiety disorder, panic disorder, social anxiety disorder, specific phobia, PTSD or OCD), based on a structured diagnostic interview", "Outcomes are reported at follow-up at least 1 month after treatment completion", "The comparison group is care as usual, relaxation, psychoeducation, pill placebo, supportive therapy or a waiting list"],
            "exclusion": ["Treatment is not CBT (for example EMDR or interpersonal therapy)", "Self-guided therapy without any guidance", "CBT combined with medication or pill placebo", "Participants are inpatients", "Symptoms are not reported separately for each disorder"]},
    },
    {
        "slug": "nudging-healthcare", "id": "Nagtegaal_2019", "name": "Nudging healthcare professionals",
        "topic": "Nudging healthcare professionals towards evidence-based medicine (scoping review)",
        "citation": "Nagtegaal R, Tummers L, Noordegraaf M, Bekkers V. Nudging healthcare professionals towards evidence-based medicine: a systematic scoping review. Journal of Behavioral Public Administration 2019;2(2).",
        "doi": "https://doi.org/10.30636/jbpa.22.71", "licence": "CC0",
        "criteria": {
            "inclusion": ["A nudge (a behavioural intervention that changes choice architecture) is applied to healthcare professionals at the individual level", "The aim is to promote evidence-based medicine, including adherence to guidelines", "The report is an experiment (randomised controlled trial, before-and-after study or interrupted time series)"],
            "exclusion": ["The report is not an experiment", "The intervention is not a nudge", "The target group is not healthcare professionals"]},
    },
    {
        "slug": "virus-metagenomics", "id": "Kwok_2020", "name": "Virus metagenomics in farm animals",
        "topic": "Virus metagenomics in farm animals",
        "citation": "Kwok KTT, Nieuwenhuijse DF, Phan MVT, Koopmans MPG. Virus metagenomics in farm animals: a systematic review. Viruses 2020;12(1):107.",
        "doi": "https://doi.org/10.3390/v12010107", "licence": "CC-BY 4.0",
        "criteria": {
            "inclusion": ["The study performed viral metagenomic sequencing on specimens from farm animals", "The animals are cattle, small ruminants (goats or sheep), poultry or pigs"],
            "exclusion": ["Conference abstract", "Article without original data (review paper, editorial or commentary)"]},
    },
]


def build(src: Path) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SAMPLES.mkdir(parents=True, exist_ok=True)
    for spec in DATASETS:
        path = src / "datasets" / spec["id"] / "output" / f"{spec['id']}.csv"
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        rows = [r for r in rows if (r.get("title") or "").strip()]
        rng = random.Random(2026)
        rel = [r for r in rows if r["label_included"] == "1"]
        irr = [r for r in rows if r["label_included"] != "1"]
        rng.shuffle(rel)
        rng.shuffle(irr)
        rel = rel[:MAX_REL]
        picked = rel + irr[: SIZE - len(rel)]
        rng.shuffle(picked)
        records = [
            {"title": " ".join(r["title"].split()), "abstract": " ".join((r.get("abstract") or "").split()),
             "label": r["label_included"] == "1", "doi": (r.get("doi") or "").strip(), "year": (r.get("year") or "").strip()}
            for r in picked
        ]
        source = (f"Real records sampled from the review's open dataset. {spec['citation']} {spec['doi']} "
                  f"Dataset licence: {spec['licence']} (via ASReview systematic-review-datasets). "
                  f"Labels are the review authors' final inclusion decisions. The criteria are the review's own eligibility "
                  f"criteria from its Methods section, split into separate items (language and publication-year "
                  f"rules are left out). Some are full-text rules, so an abstract may not settle them and the AI "
                  f"will then answer uncertain. Sample: all relevant records (up to {MAX_REL}) plus random "
                  f"irrelevant ones.")
        data = {
            "slug": spec["slug"], "name": spec["name"], "description": spec["topic"],
            "source": source, "criteria": spec["criteria"], "records": records,
        }
        (OUT / f"{spec['slug']}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(spec["slug"], len(records), sum(r["label"] for r in records), "relevant,",
              sum(1 for r in records if r["label"] and not r["abstract"]), "relevant without abstract")
        if spec["slug"] == "wilson-disease":  # downloadable practice files for the in-app flow
            with (SAMPLES / "records.ris").open("w", encoding="utf-8") as f:
                for i, r in enumerate(records):
                    f.write(f"TY  - JOUR\nTI  - {r['title']}\n")
                    if r["abstract"]:
                        f.write(f"AB  - {r['abstract']}\n")
                    if r["year"]:
                        f.write(f"PY  - {r['year'][:4]}\n")
                    if r["doi"]:
                        f.write(f"DO  - {r['doi']}\n")
                    f.write(f"ID  - wilson{i}\nER  - \n\n")
            for name, cols in (("labels.csv", ("title", "doi", "label")), ("records.csv", ("title", "abstract", "label"))):
                with (SAMPLES / name).open("w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(cols)
                    for r in records:
                        w.writerow([int(r["label"]) if c == "label" else r[c] for c in cols])
            (SAMPLES / "criteria.json").write_text(json.dumps(spec["criteria"], indent=2) + "\n")
            (SAMPLES / "SOURCE.txt").write_text(source + "\n")


if __name__ == "__main__":
    build(Path(sys.argv[1]))
