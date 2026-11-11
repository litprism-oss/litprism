"""Generate the built-in benchmark datasets as JSON for the app database.

All records are INVENTED (not real publications). Output goes to
apps/litprism-app/backend/services/benchmark_data/<slug>.json and is loaded into the
database at API start-up. Re-run:  python datasets/make_benchmarks.py
"""

import csv
import json
import random
from pathlib import Path

OUT = Path(__file__).parent.parent / "apps/litprism-app/backend/services/benchmark_data"
OUT.mkdir(parents=True, exist_ok=True)
CITIES = ["Leuven", "Zurich", "Toronto", "Melbourne", "Osaka", "Sao Paulo", "Aarhus", "Pune",
          "Boston", "Lyon"]


def topic_dataset(slug, name, description, spec, seed):
    rng = random.Random(seed)
    s = spec
    recs = []
    for i in range(20):  # relevant: RCTs in adults with the condition
        iv, oc, c = s["interventions"][i % len(s["interventions"])], s["outcomes"][i % len(s["outcomes"])], CITIES[i % 10]
        n, wk = rng.randint(40, 400), rng.choice([8, 12, 24, 52])
        title = f"{iv} in adults with {s['condition']}: a randomised controlled trial ({c} cohort {i + 1})"
        abstract = (f"Background: Evidence for {iv} in {s['condition']} is limited. Methods: In this "
                    f"double-blind trial, {n} adults (aged 18-80) with {s['condition']} were randomised to "
                    f"{iv} or {s['control']} for {wk} weeks. The primary outcome was {oc}. Results: "
                    f"{rng.choice(['A modest improvement', 'No significant difference', 'A significant improvement'])} "
                    f"in {oc} was observed (p = {rng.choice(['0.03', '0.21', '0.008', '0.47'])}). "
                    f"Conclusion: {rng.choice(['Larger trials are needed.', 'Results support further study.', 'Benefit was limited to a subgroup.'])}")
        recs.append((title, abstract, 1))
    for i in range(10):  # animal / in vitro
        iv, c = s["interventions"][i % len(s["interventions"])], CITIES[i % 10]
        recs.append((f"{iv} in a rodent model of {s['condition']}: mechanistic findings ({c} {i + 1})",
                     f"We studied {iv} in {s['animal']}. Forty animals received {iv} or vehicle for "
                     f"14 days and tissue markers were measured.", 0))
    for i in range(10):  # other condition
        cond = s["other_conditions"][i % len(s["other_conditions"])]
        iv = s["interventions"][(i + 2) % len(s["interventions"])]
        recs.append((f"{iv} in {cond}: a randomised controlled trial ({i + 1})",
                     f"We randomised {rng.randint(50, 400)} participants with {cond} to {iv} or "
                     f"{s['control']}. The primary outcome was symptom score at {rng.choice([4, 8, 12])} weeks.", 0))
    for i in range(8):  # wrong design
        recs.append((f"{s['condition'].capitalize()} and health outcomes: a retrospective cohort study ({i + 1})",
                     f"This retrospective cohort study used registry data on {rng.randint(2000, 90000)} "
                     f"adults with {s['condition']}. No intervention was assigned by investigators.", 0))
    for i in range(6):  # children
        iv = s["interventions"][i % len(s["interventions"])]
        recs.append((f"{iv} in children with {s['condition']}: a pilot randomised trial ({i + 1})",
                     f"We randomised {rng.randint(20, 60)} children aged 6-17 with {s['condition']} to "
                     f"{iv} or {s['control']} for 12 weeks.", 0))
    for i in range(6):  # unrelated
        recs.append((f"Machine learning for retinal image grading: external validation ({i + 1})",
                     "We trained a convolutional network on fundus photographs and report sensitivity "
                     "and specificity on an external test set.", 0))
    for i in range(5):  # relevant, no abstract
        iv = s["interventions"][i % len(s["interventions"])]
        recs.append((f"{iv} in {s['condition']}: a randomised trial (record without abstract {i + 1})", "", 1))
    rng.shuffle(recs)
    return {
        "slug": slug, "name": name, "description": description,
        "criteria": {"inclusion": ["Randomised controlled trial", "Adult participants (18 years or older)",
                                   f"Participants have {s['condition']}", f"Intervention is {s['iv_phrase']}"],
                     "exclusion": ["Animal or in vitro study", "Participants are children"]},
        "records": [{"title": t, "abstract": a, "label": bool(l)} for t, a, l in recs],
    }


def probiotics():
    rows = list(csv.DictReader((Path(__file__).parent / "probiotics-crohns/records.csv").open(encoding="utf-8")))
    crit = json.loads((Path(__file__).parent / "probiotics-crohns/criteria.json").read_text())
    return {"slug": "probiotics-crohns", "name": "Probiotics in Crohn's disease",
            "description": "Randomised trials of probiotics in adults with Crohn's disease. Includes 5 relevant records with no abstract.",
            "criteria": crit,
            "records": [{"title": r["title"], "abstract": r["abstract"], "label": r["label"] == "1"} for r in rows]}


DATASETS = [
    probiotics(),
    topic_dataset(
        "sglt2-heart-failure", "SGLT2 inhibitors in heart failure",
        "Randomised trials of SGLT2 inhibitors in adults with heart failure. Decoys include diabetes-only and animal studies.",
        {"condition": "heart failure", "control": "placebo", "iv_phrase": "an SGLT2 inhibitor",
         "interventions": ["Dapagliflozin", "Empagliflozin", "Canagliflozin", "Sotagliflozin", "Ertugliflozin"],
         "outcomes": ["cardiovascular death or hospitalisation", "NT-proBNP", "KCCQ score", "6-minute walk distance"],
         "other_conditions": ["type 2 diabetes", "chronic kidney disease", "hypertension", "obesity", "atrial fibrillation"],
         "animal": "a rat model of myocardial infarction"}, 11),
    topic_dataset(
        "mindfulness-depression", "Mindfulness for depression",
        "Randomised trials of mindfulness-based interventions in adults with depression. Decoys include anxiety-only and adolescent studies.",
        {"condition": "major depressive disorder", "control": "a waitlist control", "iv_phrase": "a mindfulness-based intervention",
         "interventions": ["Mindfulness-based cognitive therapy", "Mindfulness-based stress reduction", "An 8-week mindfulness programme",
                           "Online mindfulness training", "Mindfulness-based relapse prevention"],
         "outcomes": ["PHQ-9 score", "relapse at 12 months", "HAM-D score", "remission rate"],
         "other_conditions": ["generalised anxiety disorder", "chronic pain", "insomnia", "PTSD", "bipolar disorder"],
         "animal": "a chronic stress model in mice"}, 23),
]
for d in DATASETS:
    (OUT / f"{d['slug']}.json").write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(d["slug"], len(d["records"]), sum(r["label"] for r in d["records"]), "relevant")
