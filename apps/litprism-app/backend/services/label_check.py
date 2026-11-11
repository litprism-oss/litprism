"""Compare the AI's screening decisions with a reviewer's own labels (no LLM calls)."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from types import SimpleNamespace

from litprism.screen.benchmark import Metrics, compute_metrics

LABEL_COLUMNS = ("label", "label_included", "included", "include", "decision", "relevant")
_POSITIVE = {"1", "1.0", "true", "yes", "y", "include", "included"}
MAX_ROWS = 50_000


@dataclass(frozen=True)
class LabelRow:
    title: str
    doi: str | None
    label: bool


def norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()


def norm_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip().casefold())
    return d or None


def parse_labels(raw: bytes) -> list[LabelRow]:
    """Read a CSV with a title (and/or doi) column and a label column."""
    text = raw.decode("utf-8-sig", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise ValueError("The file has no rows.")
    if len(rows) > MAX_ROWS:
        raise ValueError(f"The file has more than {MAX_ROWS:,} rows.")
    cols = {c.strip().lower(): c for c in rows[0] if c}
    label_col = next((cols[c] for c in LABEL_COLUMNS if c in cols), None)
    title_col, doi_col = cols.get("title"), cols.get("doi")
    if label_col is None or (title_col is None and doi_col is None):
        raise ValueError(
            "Need a 'title' (or 'doi') column and a label column named one of: "
            + ", ".join(LABEL_COLUMNS)
            + ". Use 1/yes/include for relevant records and 0/no/exclude for the rest."
        )
    out: list[LabelRow] = []
    for row in rows:
        title = (row.get(title_col) or "").strip() if title_col else ""
        doi = norm_doi(row.get(doi_col)) if doi_col else None
        if not title and not doi:
            continue
        out.append(LabelRow(title, doi, (row.get(label_col) or "").strip().lower() in _POSITIVE))
    return out


@dataclass(frozen=True)
class LabelCheck:
    uploaded: int
    matched: int  # rows matched to a screened article in this project
    unmatched: int
    metrics: Metrics | None
    missed_titles: list[str]  # relevant per the reviewer, excluded by the AI
    missed_total: int


def compare(
    rows: list[LabelRow],
    articles: list[tuple[str, str, str | None, str]],  # (id, title, doi, ai_decision)
) -> LabelCheck:
    by_doi = {norm_doi(a[2]): a for a in articles if norm_doi(a[2])}
    by_title = {norm_title(a[1]): a for a in articles}
    labels: dict[str, bool] = {}
    results: list[SimpleNamespace] = []
    titles: dict[str, str] = {}
    unmatched = 0
    for row in rows:
        art = (by_doi.get(row.doi) if row.doi else None) or by_title.get(norm_title(row.title))
        if art is None or art[0] in labels:
            if art is None:
                unmatched += 1
            continue
        labels[art[0]] = row.label
        titles[art[0]] = art[1]
        results.append(SimpleNamespace(article_id=art[0], decision=art[3]))
    metrics = compute_metrics(results, labels) if results else None  # type: ignore[arg-type]
    missed = [r.article_id for r in results if labels[r.article_id] and r.decision == "exclude"]
    return LabelCheck(
        uploaded=len(rows),
        matched=len(results),
        unmatched=unmatched,
        metrics=metrics,
        missed_titles=[titles[i] for i in missed[:20]],
        missed_total=len(missed),
    )
