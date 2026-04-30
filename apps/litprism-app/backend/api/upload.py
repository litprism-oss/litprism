import uuid
from typing import Annotated

from db.engine import get_db
from db.models import Article, Project, UploadArticle, UploadRecord
from fastapi import (  # noqa: F401 (Depends used via Annotated)
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from services.dedup import deduplicate
from services.parsers.bibtex import parse as parse_bib
from services.parsers.csv_xlsx import parse as parse_csv
from services.parsers.exceptions import EmptyFileError, ParseError, PasswordProtectedPDFError
from services.parsers.nbib import parse as parse_nbib
from services.parsers.pdf import parse as parse_pdf
from services.parsers.ris import parse as parse_ris
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from tasks.enrichment import enrich_articles_task

from api.schemas import UploadDryRunOut, UploadRecordOut, UploadResponseOut

DB = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(prefix="/projects", tags=["upload"])

_ALLOWED_EXTENSIONS = {".nbib", ".ris", ".bib", ".csv", ".xlsx", ".pdf", ".txt"}
_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

_PARSERS = {
    ".nbib": parse_nbib,
    ".ris": parse_ris,
    ".bib": parse_bib,
    ".csv": parse_csv,
    ".xlsx": parse_csv,
    ".pdf": parse_pdf,
    ".txt": parse_nbib,  # PubMed MEDLINE export (.txt with CRLF, PMID- prefix)
}

_FORMAT_NAMES = {
    ".nbib": "nbib",
    ".ris": "ris",
    ".bib": "bib",
    ".csv": "csv",
    ".xlsx": "xlsx",
    ".pdf": "pdf",
    ".txt": "medline",
}


def _is_medline_txt(content: bytes) -> bool:
    """Return True if a .txt file looks like a PubMed MEDLINE export."""
    first_line = content.split(b"\n")[0].strip().lstrip(b"\xef\xbb\xbf")  # strip BOM
    return first_line.startswith(b"PMID-")


@router.post("/{project_id}/upload", status_code=201)
async def upload_references(
    project_id: str,
    file: UploadFile,
    db: DB,
    response: Response,
    dry_run: bool = Query(False),
    source_label: str | None = Form(None),
    search_strategy_used: str | None = Form(None),
    limits_applied: str | None = Form(None),
) -> UploadDryRunOut | UploadResponseOut:
    # 1. Load project (404 if not found)
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # 2. Validate file extension
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "unsupported_format",
                "message": f"Unsupported file type '{ext}'. "
                f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
            },
        )

    # 3. Read file content
    content = await file.read()

    # 4. Enforce max file size
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail={"error": "file_too_large", "message": "File exceeds the 50 MB limit."},
        )

    # 5. Validate .txt is MEDLINE format (not an arbitrary text file)
    if ext == ".txt" and not _is_medline_txt(content):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "unsupported_txt_format",
                "message": "Only PubMed MEDLINE .txt exports are supported. "
                "File must begin with 'PMID-'.",
            },
        )

    # 6. Parse
    parser = _PARSERS[ext]
    try:
        parsed = parser(content, filename)
    except PasswordProtectedPDFError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "password_protected_pdf", "message": str(exc)},
        ) from exc
    except EmptyFileError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "empty_or_scanned_pdf", "message": str(exc)},
        ) from exc
    except ParseError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "parse_error", "message": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": "unexpected_parser_error", "message": str(exc)},
        ) from exc

    # 7. Dry-run — return parse preview without any DB writes
    if dry_run:
        response.status_code = 200
        sample = parsed[:3]
        return UploadDryRunOut(
            total_parsed=len(parsed),
            has_title=sum(1 for r in parsed if r.title),
            has_abstract=sum(1 for r in parsed if r.abstract),
            has_authors=sum(1 for r in parsed if r.authors),
            has_doi=sum(1 for r in parsed if r.doi),
            sample_titles=[r.title for r in sample if r.title],
        )

    # 8. Deduplicate against existing articles
    dedup_result = await deduplicate(parsed, project_id, db)

    # 9. Allocate upload_id early so articles can reference it
    upload_id = str(uuid.uuid4())
    fmt = _FORMAT_NAMES[ext]

    # 10. Bulk insert new articles and collect all article IDs for the join table
    new_article_ids: list[str] = []
    if dedup_result.new_articles:
        article_rows = []
        for a in dedup_result.new_articles:
            aid = str(uuid.uuid4())
            new_article_ids.append(aid)
            article_rows.append(
                {
                    "id": aid,
                    "project_id": project_id,
                    "search_run_id": None,
                    "upload_record_id": upload_id,
                    "pmid": a.pmid,
                    "doi": a.doi,
                    "title": a.title,
                    "abstract": a.abstract,
                    "authors": a.authors,
                    "journal": a.journal,
                    "pub_date": a.pub_date,
                    "source": a.source,
                    "upload_format": a.upload_format,
                }
            )
        await db.execute(insert(Article), article_rows)

    # 11. Write upload_article join rows for all articles in this upload
    all_article_ids = new_article_ids + dedup_result.duplicate_article_ids
    if all_article_ids:
        await db.execute(
            insert(UploadArticle),
            [{"upload_record_id": upload_id, "article_id": aid} for aid in all_article_ids],
        )

    # 12. Write UploadRecord
    upload_record = UploadRecord(
        id=upload_id,
        project_id=project_id,
        search_run_id=None,
        filename=filename,
        format=fmt,
        record_count=len(parsed),
        source_label=source_label,
        search_strategy_used=search_strategy_used,
        limits_applied=limits_applied,
    )
    db.add(upload_record)

    await db.commit()

    # Collect IDs needing enrichment:
    # - new articles without an abstract
    # - duplicate articles that are still missing an abstract (stuck or re-upload)
    needs_enrichment = [
        aid
        for aid, a in zip(new_article_ids, dedup_result.new_articles, strict=False)
        if not a.abstract
    ]
    if dedup_result.duplicate_article_ids:
        dup_rows = (
            (
                await db.execute(
                    select(Article.id).where(
                        Article.id.in_(dedup_result.duplicate_article_ids),
                        Article.abstract.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        needs_enrichment.extend(dup_rows)

    if needs_enrichment:
        enrich_articles_task.delay(project_id, needs_enrichment)

    return UploadResponseOut(
        upload_id=upload_id,
        filename=filename,
        format=fmt,
        total_parsed=len(parsed),
        new_articles=len(dedup_result.new_articles),
        duplicates_found=len(dedup_result.duplicates),
        project_id=project_id,
        enrichment_queued=len(needs_enrichment),
    )


@router.get("/{project_id}/uploads", response_model=list[UploadRecordOut])
async def list_uploads(
    project_id: str,
    db: DB,
) -> list[UploadRecordOut]:
    # Verify project exists
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(UploadRecord)
        .where(UploadRecord.project_id == project_id)
        .order_by(UploadRecord.uploaded_at.desc())
    )
    records = result.scalars().all()
    return [UploadRecordOut.model_validate(r) for r in records]
