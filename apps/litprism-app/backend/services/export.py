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
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt
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


def generate_prisma_s_docx(
    project: Project,
    source_queries: list[SourceQuery],
    upload_records: list[UploadRecord],
    prisma_counts: dict,
) -> bytes:
    """
    Generate a PRISMA-S supplementary search strategy document.
    Returns bytes suitable for streaming as a file download.

    prisma_counts keys: db_records, other_records, duplicates_removed, records_screened
    """
    doc = Document()

    # Document title
    title = doc.add_heading("PRISMA-S Supplementary Search Strategy", level=1)
    title.runs[0].font.size = Pt(14)
    title.runs[0].font.bold = True

    # Metadata block
    meta = doc.add_paragraph()
    meta.add_run("Review title: ").bold = True
    meta.add_run(project.name)
    doc.add_paragraph(f"Date of document: {date.today().strftime('%d %B %Y')}")
    doc.add_paragraph()

    # Table S1 heading
    doc.add_heading("Table S1. Search strategies for all databases searched", level=2)

    # Source queries (API searches)
    for sq in source_queries:
        _add_source_query_section(doc, sq)

    # Upload records (manual searches)
    for upload in upload_records:
        _add_upload_section(doc, upload)

    # Summary counts
    doc.add_paragraph()
    doc.add_heading("Summary", level=2)

    total = prisma_counts["db_records"] + prisma_counts["other_records"]
    dups = prisma_counts["duplicates_removed"]
    summary_tbl = doc.add_table(rows=4, cols=2)
    summary_tbl.style = "Table Grid"
    rows_data = [
        ("Total records identified", f"{total:,}"),
        ("Duplicate records removed", f"{dups:,}"),
        ("Records after deduplication", f"{total - dups:,}"),
        ("Records screened", f"{prisma_counts['records_screened']:,}"),
    ]
    for i, (label, value) in enumerate(rows_data):
        summary_tbl.rows[i].cells[0].text = label
        summary_tbl.rows[i].cells[1].text = value
        summary_tbl.rows[i].cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # Reference
    doc.add_paragraph()
    ref = doc.add_paragraph()
    ref.add_run("Reference: ").bold = True
    ref.add_run(
        "Rethlefsen ML, Kirtley S, Waffenschmidt S, et al. "
        "PRISMA-S: an extension to the PRISMA Statement for "
        "Reporting Literature Searches in Systematic Reviews. "
        "Systematic Reviews. 2021;10(1):39."
    )

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _add_source_query_section(doc: Document, sq: SourceQuery) -> None:
    """Add one API source query as a formatted section."""
    searched_at = sq.searched_at
    date_str = (
        searched_at.strftime("%d %B %Y")
        if hasattr(searched_at, "strftime")
        else str(searched_at)[:10]
    )
    result_count = sq.result_count or 0

    header = doc.add_paragraph()
    header.add_run(_source_display_name(sq.source)).bold = True
    header.add_run(f"  |  {sq.interface}  |  {date_str}  |  {result_count:,} records")

    doc.add_paragraph("Query:")
    query_para = doc.add_paragraph()
    query_run = query_para.add_run(sq.query_string or "")
    # Set font AFTER adding text — python-docx requires this order
    query_run.font.name = "Courier New"
    query_run.font.size = Pt(9)
    query_para.paragraph_format.left_indent = Inches(0.5)

    if sq.filters_human_readable and sq.filters_human_readable not in ("None", ""):
        doc.add_paragraph(f"Filters: {sq.filters_human_readable}")

    doc.add_paragraph()  # spacer


def _add_upload_section(doc: Document, upload: UploadRecord) -> None:
    """Add one uploaded file as a formatted section."""
    source_label = getattr(upload, "source_label", None) or "Manual search / other source"
    uploaded_at = upload.uploaded_at
    date_str = (
        uploaded_at.strftime("%d %B %Y")
        if hasattr(uploaded_at, "strftime")
        else str(uploaded_at)[:10]
    )
    record_count = upload.record_count or 0

    header = doc.add_paragraph()
    header.add_run(source_label).bold = True
    header.add_run(f"  |  Web interface  |  {date_str}  |  {record_count:,} records")
    header.add_run(f"  (uploaded file: {upload.filename})").italic = True

    search_strategy = getattr(upload, "search_strategy_used", None)
    if search_strategy:
        doc.add_paragraph("Query:")
        q_para = doc.add_paragraph()
        q_run = q_para.add_run(search_strategy)
        q_run.font.name = "Courier New"
        q_run.font.size = Pt(9)
        q_para.paragraph_format.left_indent = Inches(0.5)

    limits = getattr(upload, "limits_applied", None)
    if limits:
        doc.add_paragraph(f"Limits: {limits}")

    doc.add_paragraph()


def _source_display_name(source: str) -> str:
    return {
        "pubmed": "MEDLINE",
        "europepmc": "Europe PMC",
        "semanticscholar": "Semantic Scholar",
    }.get(source, source.title())


async def _to_prisma_s(project_id: str, db: AsyncSession) -> bytes:
    # Load project
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if project is None:
        # Fallback: build a minimal Project-like object
        project = type("_P", (), {"name": project_id, "id": project_id})()

    # Load source queries across all search runs for this project
    runs_result = await db.execute(
        select(SearchRun).where(SearchRun.project_id == project_id).order_by(SearchRun.created_at)
    )
    search_runs = list(runs_result.scalars())
    run_ids = [r.id for r in search_runs]
    source_queries: list[SourceQuery] = []
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

    # Counts
    dedup_result = await db.execute(
        select(func.count()).where(DeduplicationLog.project_id == project_id)
    )
    duplicates_removed: int = dedup_result.scalar_one() or 0

    db_records = sum(sq.result_count or 0 for sq in source_queries)
    other_records = sum(ur.record_count or 0 for ur in upload_records)

    active_criteria_result = await db.execute(
        select(Criteria)
        .where(Criteria.project_id == project_id, Criteria.superseded_at.is_(None))
        .order_by(Criteria.version.desc())
        .limit(1)
    )
    active_criteria = active_criteria_result.scalar_one_or_none()
    records_screened = 0
    if active_criteria:
        sr_count_result = await db.execute(
            select(func.count()).where(
                ScreeningResult.project_id == project_id,
                ScreeningResult.criteria_id == active_criteria.id,
            )
        )
        records_screened = sr_count_result.scalar_one() or 0

    prisma_counts = {
        "db_records": db_records,
        "other_records": other_records,
        "duplicates_removed": duplicates_removed,
        "records_screened": records_screened,
    }

    return generate_prisma_s_docx(project, source_queries, upload_records, prisma_counts)
