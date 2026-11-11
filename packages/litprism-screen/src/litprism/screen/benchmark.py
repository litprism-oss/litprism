"""Benchmark LLM screening against labelled records (recall, precision, work saved).

Every published screening tool reports recall and precision on public datasets. Use this
to produce the same numbers for LitPrism on your own review or a public dataset.

Input CSV columns: ``id`` (optional), ``title``, ``abstract``, ``label`` (1 = relevant,
0 = not). Criteria JSON: ``{"inclusion": [...], "exclusion": [...]}``.

    python -m litprism.screen.benchmark data.csv criteria.json --limit 200

Uses the same environment variables as the app (GEMINI_API_KEY, OPENAI_API_KEY, LLM_MODEL...).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path

from litprism.screen.criteria import Criteria
from litprism.screen.models import ScreeningResult
from litprism.screen.screener import Screener


@dataclass
class _Record:
    id: str
    title: str
    abstract: str | None
    label: bool


@dataclass(frozen=True)
class Metrics:
    n: int
    relevant: int
    errors: int
    recall: float | None  # share of truly relevant records the screen kept
    precision: float | None  # share of kept records that are truly relevant
    specificity: float | None
    work_saved: float  # share of records the screen excluded (workload avoided)
    missed: int  # relevant records the screen excluded

    def summary(self) -> str:
        def pct(v: float | None) -> str:
            return "n/a" if v is None else f"{v * 100:.1f}%"

        return (
            f"records={self.n} relevant={self.relevant} errors={self.errors}\n"
            f"recall={pct(self.recall)} precision={pct(self.precision)} "
            f"specificity={pct(self.specificity)}\n"
            f"work saved={pct(self.work_saved)} missed relevant={self.missed}"
        )


def compute_metrics(
    results: list[ScreeningResult], labels: dict[str, bool], errors: int = 0
) -> Metrics:
    """Score screening results. 'include' and 'uncertain' both count as kept for review,
    because LitPrism routes uncertain records to full text rather than excluding them."""
    tp = fp = tn = fn = 0
    for r in results:
        kept = r.decision != "exclude"
        relevant = labels[r.article_id]
        if kept and relevant:
            tp += 1
        elif kept:
            fp += 1
        elif relevant:
            fn += 1
        else:
            tn += 1
    n = tp + fp + tn + fn
    return Metrics(
        n=n,
        relevant=tp + fn,
        errors=errors,
        recall=tp / (tp + fn) if tp + fn else None,
        precision=tp / (tp + fp) if tp + fp else None,
        specificity=tn / (tn + fp) if tn + fp else None,
        work_saved=(tn + fn) / n if n else 0.0,
        missed=fn,
    )


_LABEL_COLUMNS = ("label", "label_included", "included", "include", "relevant")


def load_records(path: Path) -> list[_Record]:
    """Read a labelled CSV. Accepts the ASReview dataset layout (``label_included``) too."""
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError("CSV is empty")
    cols = {c.strip().lower(): c for c in rows[0]}
    label_col = next((cols[c] for c in _LABEL_COLUMNS if c in cols), None)
    if "title" not in cols or label_col is None:
        raise ValueError(
            "CSV needs a 'title' column and a label column "
            f"(one of: {', '.join(_LABEL_COLUMNS)}); found: {', '.join(rows[0])}"
        )
    title_col, abstract_col = cols["title"], cols.get("abstract")
    id_col = cols.get("id")
    return [
        _Record(
            id=(row.get(id_col) if id_col else "") or str(i),
            title=row[title_col],
            abstract=((row.get(abstract_col) or "").strip() or None) if abstract_col else None,
            label=(row[label_col] or "").strip().lower()
            in {"1", "1.0", "true", "yes", "include", "included"},
        )
        for i, row in enumerate(rows)
    ]


async def run_benchmark(records: list[_Record], criteria: Criteria, screener: Screener) -> Metrics:
    results, errors = await screener.ascreen_batch(records, criteria, stage="abstract")
    return compute_metrics(results, {r.id: r.label for r in records}, errors=len(errors))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("csv", type=Path)
    ap.add_argument("criteria", type=Path, help="JSON with 'inclusion' and 'exclusion' lists")
    ap.add_argument("--limit", type=int, help="screen a random sample of N records (cheaper)")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    records = load_records(args.csv)
    if args.limit and args.limit < len(records):
        # Keep all relevant records and sample the rest, so recall stays measurable.
        rng = random.Random(args.seed)
        rel = [r for r in records if r.label]
        rest = [r for r in records if not r.label]
        rng.shuffle(rest)
        records = rel + rest[: max(args.limit - len(rel), 0)]
    criteria = Criteria(**json.loads(args.criteria.read_text()))
    metrics = asyncio.run(run_benchmark(records, criteria, Screener.from_env()))
    print(metrics.summary())


if __name__ == "__main__":
    main()
