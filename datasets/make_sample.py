"""Generate the synthetic sample review in datasets/probiotics-crohns/.

All records are INVENTED for testing the tool (they are not real publications). Re-run:
    python datasets/make_sample.py
Produces records.csv (title, abstract, label), labels.csv (title, label), records.ris,
and criteria.json.
"""

import csv
import json
import random
from pathlib import Path

OUT = Path(__file__).parent / "probiotics-crohns"
rng = random.Random(7)

STRAINS = ["Lactobacillus rhamnosus GG", "Saccharomyces boulardii", "Bifidobacterium longum",
           "VSL#3", "Escherichia coli Nissle 1917", "Lactobacillus casei", "Bifidobacterium infantis",
           "Lactobacillus plantarum", "Streptococcus thermophilus", "a multi-strain probiotic"]
OUTCOMES = ["clinical remission (CDAI < 150)", "endoscopic recurrence", "faecal calprotectin",
            "quality of life (IBDQ)", "relapse rate at 12 months", "C-reactive protein"]
CITIES = ["Leuven", "Zurich", "Toronto", "Melbourne", "Osaka", "Sao Paulo", "Aarhus", "Pune",
          "Boston", "Lyon"]

rel, irr = [], []

# 20 relevant: randomised controlled trials of probiotics in adults with Crohn's disease
for i in range(20):
    s, o, c = STRAINS[i % 10], OUTCOMES[i % 6], CITIES[i % 10]
    n = rng.randint(40, 220)
    weeks = rng.choice([8, 12, 24, 52])
    title = f"{s} for {['maintaining remission', 'active disease', 'postoperative recurrence'][i % 3]} in adults with Crohn's disease: a randomised placebo-controlled trial ({c} cohort {i + 1})"
    abstract = (f"Background: Evidence for probiotics in Crohn's disease is limited. Methods: In this "
                f"double-blind trial, {n} adults (aged 18-70) with confirmed Crohn's disease were randomised "
                f"to {s} or placebo for {weeks} weeks. The primary outcome was {o}. Results: The "
                f"intervention group showed {rng.choice(['a modest improvement', 'no significant difference', 'a significant improvement'])} "
                f"in {o} (p = {rng.choice(['0.03', '0.21', '0.008', '0.47'])}). Conclusion: "
                f"{rng.choice(['Larger trials are needed.', 'Results support further study.', 'Benefit was limited to a subgroup.'])}")
    rel.append((title, abstract))

# 40 not relevant, in several realistic ways
for i in range(10):  # animal / in vitro
    s, c = STRAINS[i % 10], CITIES[i % 10]
    irr.append((f"{s} in a murine model of colitis: effects on mucosal inflammation ({c} {i + 1})",
                f"We investigated {s} in DSS-induced colitis in mice. Forty C57BL/6 mice were given "
                f"{s} or vehicle for 14 days and inflammation was scored histologically."))
for i in range(10):  # other condition
    cond = ["irritable bowel syndrome", "antibiotic-associated diarrhoea", "ulcerative colitis",
            "eczema in infants", "Clostridioides difficile infection", "bacterial vaginosis",
            "type 2 diabetes", "depression", "necrotising enterocolitis", "acne"][i]
    s = STRAINS[(i + 3) % 10]
    irr.append((f"{s} in {cond}: a randomised controlled trial ({i + 1})",
                f"We randomised {rng.randint(50, 300)} participants with {cond} to {s} or placebo. "
                f"The primary outcome was symptom score at {rng.choice([4, 8, 12])} weeks."))
for i in range(8):  # not a trial / wrong design
    irr.append((f"Dietary patterns and risk of Crohn's disease: a retrospective cohort study ({i + 1})",
                f"This retrospective cohort study used registry data on {rng.randint(2000, 90000)} adults "
                f"to relate diet quality to incident Crohn's disease. No intervention was assigned."))
for i in range(6):  # paediatric
    irr.append((f"{STRAINS[i]} in children with Crohn's disease: a pilot randomised trial ({i + 1})",
                f"We randomised {rng.randint(20, 60)} children aged 6-17 with Crohn's disease to "
                f"{STRAINS[i]} or placebo for 12 weeks. The primary outcome was PCDAI."))
for i in range(6):  # unrelated
    irr.append((f"Machine learning for retinal image grading: external validation ({i + 1})",
                "We trained a convolutional network on fundus photographs and report sensitivity and "
                "specificity on an external test set."))

# 5 relevant records with NO abstract: the AI can only mark these uncertain (kept for full text)
noabs = [(f"Probiotic supplementation in Crohn's disease patients: a randomised trial (record without abstract {i + 1})", "")
         for i in range(5)]

records = [(t, a, 1) for t, a in rel] + [(t, a, 0) for t, a in irr] + [(t, a, 1) for t, a in noabs]
rng.shuffle(records)
OUT.mkdir(exist_ok=True)

with (OUT / "records.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["title", "abstract", "label"])
    w.writerows(records)
with (OUT / "labels.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["title", "label"])
    w.writerows((t, l) for t, _, l in records)
with (OUT / "records.ris").open("w", encoding="utf-8") as f:
    for i, (t, a, _) in enumerate(records):
        f.write(f"TY  - JOUR\nTI  - {t}\n")
        if a:
            f.write(f"AB  - {a}\n")
        f.write(f"PY  - {2015 + i % 10}\nJO  - Synthetic Test Journal\nID  - sample{i}\nER  - \n\n")
(OUT / "criteria.json").write_text(json.dumps({
    "inclusion": ["Randomised controlled trial", "Adult participants (18 years or older)",
                  "Participants have Crohn's disease", "Intervention is a probiotic"],
    "exclusion": ["Animal or in vitro study", "Participants are children"],
}, indent=2) + "\n")
print(len(records), "records,", sum(r[2] for r in records), "relevant")
