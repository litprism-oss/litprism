"""Built-in benchmark datasets: seeding into the database and scoring a run."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from db.models import BenchmarkDataset, BenchmarkRecord
from litprism.screen.benchmark import compute_metrics
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

DATA_DIR = Path(__file__).parent / "benchmark_data"
CHUNK = 10  # records screened between progress updates


async def seed_datasets(db: AsyncSession) -> int:
    """Insert any bundled dataset that is not in the database yet. Safe to call on every start."""
    existing = set((await db.execute(select(BenchmarkDataset.slug))).scalars())
    added = 0
    for path in sorted(DATA_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["slug"] in existing:
            continue
        records = data["records"]
        ds = BenchmarkDataset(
            slug=data["slug"],
            name=data["name"],
            description=data["description"],
            criteria=data["criteria"],
            record_count=len(records),
            relevant_count=sum(1 for r in records if r["label"]),
        )
        db.add(ds)
        await db.flush()
        db.add_all(
            BenchmarkRecord(
                dataset_id=ds.id,
                title=r["title"],
                abstract=r["abstract"] or None,
                label=bool(r["label"]),
            )
            for r in records
        )
        added += 1
    await db.commit()
    return added


def score(results: list, labels: dict[str, bool], errors: int) -> dict:
    """Metrics as a JSON-friendly dict (see litprism.screen.benchmark.compute_metrics)."""
    m = compute_metrics(results, labels, errors=errors)
    return {
        "n": m.n,
        "relevant": m.relevant,
        "errors": m.errors,
        "recall": m.recall,
        "precision": m.precision,
        "specificity": m.specificity,
        "work_saved": m.work_saved,
        "missed": m.missed,
    }


def as_article(rec: BenchmarkRecord) -> SimpleNamespace:
    return SimpleNamespace(id=rec.id, title=rec.title, abstract=rec.abstract)
