import uuid
from typing import Annotated

from db.engine import get_db
from db.models import Article, Project, UploadRecord
from fastapi import (  # noqa: F401 (Depends used via Annotated)
    APIRouter,
    Depends,
    Form,
    HTTPException,
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

from api.schemas import UploadRecordOut, UploadResponseOut

DB = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(prefix="/projects", tags=["upload"])

_ALLOWED_EXTENSIONS = {".nbib", ".ris", ".bib", ".csv", ".xlsx", ".pdf"}
_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

_PARSERS = {
    ".nbib": parse_nbib,
    ".ris": parse_ris,
    ".bib": parse_bib,
    ".csv": parse_csv,
    ".xlsx": parse_csv,
    ".pdf": parse_pdf,
}

_FORMAT_NAMES = {
    ".nbib": "nbib",
    ".ris": "ris",
    ".bib": "bib",
    ".csv": "csv",
    ".xlsx": "xlsx",
    ".pdf": "pdf",
}


@router.post("/{project_id}/upload", status_code=201, response_model=UploadResponseOut)
async def upload_references(
    project_id: str,
    file: UploadFile,
    db: DB,
    source_label: str | None = Form(None),
    search_strategy_used: str | None = Form(None),
    limits_applied: str | None = Form(None),
) -> UploadResponseOut:
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

    # 5. Parse
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

    # 6. Deduplicate against existing articles
    dedup_result = await deduplicate(parsed, project_id, db)

    # 7. Bulk insert new articles
    if dedup_result.new_articles:
        article_rows = [
            {
                "id": str(uuid.uuid4()),
                "project_id": project_id,
                "search_run_id": None,
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
            for a in dedup_result.new_articles
        ]
        await db.execute(insert(Article), article_rows)

    # 8. Write UploadRecord
    upload_id = str(uuid.uuid4())
    fmt = _FORMAT_NAMES[ext]
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

    return UploadResponseOut(
        upload_id=upload_id,
        filename=filename,
        format=fmt,
        total_parsed=len(parsed),
        new_articles=len(dedup_result.new_articles),
        duplicates_found=len(dedup_result.duplicates),
        project_id=project_id,
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
