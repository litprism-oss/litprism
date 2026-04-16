import csv
import io
import json
import zipfile
from datetime import date, datetime

import rispy
from db.models import (
    Article,
    Criteria,
    DeduplicationLog,
    Project,
    ScreeningResult,
    SearchRun,
    SourceQuery,
    UploadRecord,
)
from docx import Document
from docx.shared import Pt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

_EXPORT_FORMATS = {"ris", "nbib", "csv", "json", "asreview", "prisma-s"}


async def export_articles(
    project_id: str,
    db: AsyncSession,
    decision: str | None = None,
    fmt: str = "ris",
) -> tuple[bytes, str]:
    """
    Returns (file_bytes, suggested_filename).
    Loads articles with their latest screening_result under active criteria.
    """
    # Load active criteria for the project
    criteria_result = await db.execute(
        select(Criteria)
        .where(Criteria.project_id == project_id, Criteria.superseded_at.is_(None))
        .order_by(Criteria.version.desc())
        .limit(1)
    )
    active_criteria = criteria_result.scalar_one_or_none()
    active_criteria_id = active_criteria.id if active_criteria else None

    # Load articles, optionally joined to their screening decision
    if decision and active_criteria_id:
        # Only articles with a matching decision under active criteria
        result = await db.execute(
            select(Article, ScreeningResult)
            .join(
                ScreeningResult,
                (ScreeningResult.article_id == Article.id)
                & (ScreeningResult.criteria_id == active_criteria_id),
            )
            .where(Article.project_id == project_id, ScreeningResult.decision == decision)
        )
        rows = result.all()
        articles = [r[0] for r in rows]
        decisions = {r[0].id: r[1].decision for r in rows}
    else:
        # All articles; attach decisions where available
        result = await db.execute(select(Article).where(Article.project_id == project_id))
        articles = list(result.scalars().all())
        if active_criteria_id:
            sr_result = await db.execute(
                select(ScreeningResult).where(
                    ScreeningResult.project_id == project_id,
                    ScreeningResult.criteria_id == active_criteria_id,
                )
            )
            decisions = {sr.article_id: sr.decision for sr in sr_result.scalars()}
        else:
            decisions = {}

    # Attach decision to each article as a transient attribute for formatters
    articles_with_decisions = [(a, decisions.get(a.id)) for a in articles]

    now_str = datetime.now().strftime("%Y%m%d")
    slug = project_id[:8]

    if fmt == "ris":
        return _to_ris(articles), f"litprism_{slug}_{now_str}.ris"
    if fmt == "nbib":
        return _to_nbib(articles), f"litprism_{slug}_{now_str}.nbib"
    if fmt == "csv":
        return _to_csv(articles_with_decisions), f"litprism_{slug}_{now_str}.csv"
    if fmt == "json":
        return _to_json(articles_with_decisions), f"litprism_{slug}_{now_str}.json"
    if fmt == "asreview":
        return _to_asreview(articles_with_decisions), f"litprism_{slug}_{now_str}.asreview"
    if fmt == "prisma-s":
        content = await _to_prisma_s(project_id, db)
        return content, f"litprism_{slug}_prisma_s_{now_str}.docx"

    raise ValueError(f"Unknown format: {fmt}")


# ---------------------------------------------------------------------------
# RIS
# ---------------------------------------------------------------------------


def _to_ris(articles: list) -> bytes:
    entries = []
    for a in articles:
        entry = {
            "type_of_reference": "JOUR",
            "title": a.title,
            "abstract": a.abstract or "",
            "doi": a.doi or "",
            "authors": [
                f"{au.get('last_name', '')}, {au.get('fore_name', '')}".strip(", ")
                for au in (a.authors or [])
            ],
            "journal_name": a.journal or "",
            "year": str(a.pub_date.year) if a.pub_date else "",
        }
        if a.pmid:
            entry["pmid"] = a.pmid
        entries.append(entry)
    return rispy.dumps(entries).encode("utf-8")


# ---------------------------------------------------------------------------
# NBIB
# ---------------------------------------------------------------------------


def _to_nbib(articles: list) -> bytes:
    lines = []
    for a in articles:
        if a.pmid:
            lines.append(f"PMID- {a.pmid}")
        lines.append(f"TI  - {a.title}")
        if a.abstract:
            lines.append(f"AB  - {a.abstract}")
        if a.doi:
            lines.append(f"AID - {a.doi} [doi]")
        for au in a.authors or []:
            name = au.get("last_name", "")
            if au.get("fore_name"):
                name += f", {au['fore_name']}"
            lines.append(f"AU  - {name}")
        if a.journal:
            lines.append(f"TA  - {a.journal}")
        if a.pub_date:
            lines.append(f"DP  - {a.pub_date.year}")
        lines.append("")  # blank line between records
    return "\n".join(lines).encode("utf-8")


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def _to_csv(articles_with_decisions: list[tuple]) -> bytes:
    buf = io.StringIO()
    fieldnames = [
        "Title",
        "Abstract",
        "Authors",
        "Source title",
        "Year",
        "DOI",
        "PubMed ID",
        "Decision",
        "Confidence",
        "Reasoning",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for a, dec in articles_with_decisions:
        authors_str = "; ".join(
            f"{au.get('last_name', '')}, {au.get('fore_name', '')}".strip(", ")
            for au in (a.authors or [])
        )
        writer.writerow(
            {
                "Title": a.title,
                "Abstract": a.abstract or "",
                "Authors": authors_str,
                "Source title": a.journal or "",
                "Year": a.pub_date.year if a.pub_date else "",
                "DOI": a.doi or "",
                "PubMed ID": a.pmid or "",
                "Decision": dec or "",
                "Confidence": "",
                "Reasoning": "",
            }
        )
    return buf.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def _to_json(articles_with_decisions: list[tuple]) -> bytes:
    records = []
    for a, dec in articles_with_decisions:
        records.append(
            {
                "id": a.id,
                "title": a.title,
                "abstract": a.abstract,
                "authors": a.authors,
                "journal": a.journal,
                "pub_date": a.pub_date.isoformat() if isinstance(a.pub_date, date) else a.pub_date,
                "doi": a.doi,
                "pmid": a.pmid,
                "source": a.source,
                "decision": dec,
            }
        )
    return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")


# ---------------------------------------------------------------------------
# ASReview
# ---------------------------------------------------------------------------


def _to_asreview(articles_with_decisions: list[tuple]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        csv_buf = io.StringIO()
        writer = csv.DictWriter(
            csv_buf, fieldnames=["title", "abstract", "authors", "doi", "included"]
        )
        writer.writeheader()
        for a, dec in articles_with_decisions:
            included = {"include": 1, "exclude": 0}.get(dec or "", -1)
            writer.writerow(
                {
                    "title": a.title,
                    "abstract": a.abstract or "",
                    "authors": "; ".join(au.get("last_name", "") for au in (a.authors or [])),
                    "doi": a.doi or "",
                    "included": included,
                }
            )
        zf.writestr("data.csv", csv_buf.getvalue())
        zf.writestr(
            "metadata.json",
            json.dumps({"version": "1.0", "software": "LitPrism"}),
        )
    return buf.getvalue()


# ---------------------------------------------------------------------------
# PRISMA-S
# ---------------------------------------------------------------------------


async def _to_prisma_s(project_id: str, db: AsyncSession) -> bytes:
    # Load project
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    project_name = project.name if project else project_id

    # Load completed search runs with their source queries
    runs_result = await db.execute(
        select(SearchRun).where(SearchRun.project_id == project_id).order_by(SearchRun.created_at)
    )
    search_runs = list(runs_result.scalars())

    # Load source queries for each run
    run_ids = [r.id for r in search_runs]
    source_queries: list = []
    if run_ids:
        sq_result = await db.execute(
            select(SourceQuery)
            .where(SourceQuery.search_run_id.in_(run_ids))
            .order_by(SourceQuery.searched_at)
        )
        source_queries = list(sq_result.scalars())

    # Load upload records
    ur_result = await db.execute(
        select(UploadRecord)
        .where(UploadRecord.project_id == project_id)
        .order_by(UploadRecord.uploaded_at)
    )
    upload_records = list(ur_result.scalars())

    # Aggregate counts
    total_articles_result = await db.execute(
        select(func.count()).where(Article.project_id == project_id)
    )
    total_articles: int = total_articles_result.scalar_one() or 0

    dedup_result = await db.execute(
        select(func.count()).where(DeduplicationLog.project_id == project_id)
    )
    duplicates_removed: int = dedup_result.scalar_one() or 0
    after_dedup = total_articles  # articles already deduplicated before insert

    # Screening counts
    active_criteria_result = await db.execute(
        select(Criteria)
        .where(Criteria.project_id == project_id, Criteria.superseded_at.is_(None))
        .order_by(Criteria.version.desc())
        .limit(1)
    )
    active_criteria = active_criteria_result.scalar_one_or_none()

    screened = included = excluded = uncertain = 0
    if active_criteria:
        sr_counts = await db.execute(
            select(ScreeningResult.decision, func.count())
            .where(
                ScreeningResult.project_id == project_id,
                ScreeningResult.criteria_id == active_criteria.id,
            )
            .group_by(ScreeningResult.decision)
        )
        for dec, cnt in sr_counts:
            screened += cnt
            if dec == "include":
                included += cnt
            elif dec == "exclude":
                excluded += cnt
            elif dec == "uncertain":
                uncertain += cnt

    # Build document
    doc = Document()
    doc.add_heading(f"Search Record (PRISMA-S) — {project_name}", level=1)

    # --- Search source sections ---
    if source_queries:
        doc.add_heading("Database Searches", level=2)
        # Group source queries by search_run
        sq_by_run: dict[str, list] = {}
        for sq in source_queries:
            sq_by_run.setdefault(sq.search_run_id, []).append(sq)

        for run in search_runs:
            queries = sq_by_run.get(run.id, [])
            if not queries:
                continue
            for sq in queries:
                tbl = doc.add_table(rows=2, cols=4)
                tbl.style = "Table Grid"
                hdr = tbl.rows[0].cells
                hdr[0].text = "Source"
                hdr[1].text = "Interface"
                hdr[2].text = "Date searched"
                hdr[3].text = "Results"
                for cell in hdr:
                    for para in cell.paragraphs:
                        for run_obj in para.runs:
                            run_obj.bold = True

                searched_at = sq.searched_at
                date_str = (
                    searched_at.strftime("%d %b %Y")
                    if hasattr(searched_at, "strftime")
                    else str(searched_at)[:10]
                )
                data = tbl.rows[1].cells
                data[0].text = sq.source
                data[1].text = sq.interface
                data[2].text = date_str
                data[3].text = str(sq.result_count)

                doc.add_paragraph(f"Query: {sq.query_string}")
                if sq.filters_human_readable:
                    doc.add_paragraph(f"Filters: {sq.filters_human_readable}")
                doc.add_paragraph("")

    # --- Upload record sections ---
    if upload_records:
        doc.add_heading("File Uploads", level=2)
        tbl = doc.add_table(rows=1 + len(upload_records), cols=3)
        tbl.style = "Table Grid"
        hdr = tbl.rows[0].cells
        hdr[0].text = "Filename"
        hdr[1].text = "Format"
        hdr[2].text = "Records"
        for cell in hdr:
            for para in cell.paragraphs:
                for run_obj in para.runs:
                    run_obj.bold = True
        for i, ur in enumerate(upload_records, start=1):
            row = tbl.rows[i].cells
            row[0].text = ur.filename
            row[1].text = ur.format
            row[2].text = str(ur.record_count)
        doc.add_paragraph("")

    # --- Totals section ---
    doc.add_heading("Summary Counts", level=2)
    totals = [
        ("Total identified", total_articles + duplicates_removed),
        ("Duplicates removed", duplicates_removed),
        ("After deduplication", after_dedup),
        ("Screened (abstract)", screened),
        ("Included", included),
        ("Excluded", excluded),
        ("Uncertain", uncertain),
    ]
    tbl = doc.add_table(rows=len(totals), cols=2)
    tbl.style = "Table Grid"
    for i, (label, count) in enumerate(totals):
        row = tbl.rows[i].cells
        row[0].text = label
        # Bold the label
        for para in row[0].paragraphs:
            for run_obj in para.runs:
                run_obj.bold = True
        row[1].text = f"{count:,}"

    # Add PRISMA-S note
    doc.add_paragraph("")
    note = doc.add_paragraph(
        "Generated by LitPrism. "
        "Cite search strategies per PRISMA-S guidelines "
        "(Rethlefsen et al., 2021, Syst Rev 10:39)."
    )
    note.runs[0].font.size = Pt(9)
    note.runs[0].italic = True

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
