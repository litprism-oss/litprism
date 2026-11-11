from datetime import UTC, datetime, timedelta
from typing import Annotated

from db.engine import get_db
from db.models import BenchmarkDataset, BenchmarkRun
from dependencies import CurrentUser, Member
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tasks.benchmark import run_benchmark

from api.schemas import BenchmarkDatasetOut, BenchmarkRunOut

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])
DB = Annotated[AsyncSession, Depends(get_db)]

# A run that has not finished by now lost its worker; show it as failed instead of "running".
_STALE_AFTER = timedelta(minutes=30)


async def _expire_stale(db: AsyncSession) -> None:
    cutoff = datetime.now(UTC) - _STALE_AFTER
    stale = (
        await db.execute(
            select(BenchmarkRun).where(
                BenchmarkRun.status.in_(("pending", "running")),
                BenchmarkRun.created_at < cutoff,
            )
        )
    ).scalars()
    for run in stale:
        run.status, run.error, run.completed_at = "failed", "Timed out", datetime.now(UTC)
    await db.commit()


@router.get("", response_model=list[BenchmarkDatasetOut])
async def list_benchmarks(_: CurrentUser, db: DB) -> list[BenchmarkDatasetOut]:
    await _expire_stale(db)
    datasets = (
        (await db.execute(select(BenchmarkDataset).order_by(BenchmarkDataset.name))).scalars().all()
    )
    out = []
    for ds in datasets:
        latest = (
            await db.execute(
                select(BenchmarkRun)
                .where(BenchmarkRun.dataset_id == ds.id)
                .order_by(BenchmarkRun.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        out.append(
            BenchmarkDatasetOut(
                slug=ds.slug,
                name=ds.name,
                description=ds.description,
                criteria=ds.criteria,
                record_count=ds.record_count,
                relevant_count=ds.relevant_count,
                latest_run=BenchmarkRunOut.model_validate(latest) if latest else None,
            )
        )
    return out


@router.post("/{slug}/run", response_model=BenchmarkRunOut, status_code=status.HTTP_202_ACCEPTED)
async def start_benchmark(slug: str, user: Member, db: DB) -> BenchmarkRunOut:
    """Screen a built-in dataset with the configured LLM. One run at a time, because it
    spends LLM calls and the free tier rate-limits quickly."""
    await _expire_stale(db)
    ds = (
        await db.execute(select(BenchmarkDataset).where(BenchmarkDataset.slug == slug))
    ).scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    active = (
        await db.execute(
            select(BenchmarkRun.id).where(BenchmarkRun.status.in_(("pending", "running"))).limit(1)
        )
    ).first()
    if active:
        raise HTTPException(
            status_code=409, detail="A benchmark is already running. Wait for it to finish."
        )
    run = BenchmarkRun(dataset_id=ds.id, owner_id=user.id, status="pending", total=ds.record_count)
    db.add(run)
    await db.commit()
    await db.refresh(run)
    run_benchmark.delay(run.id)
    return BenchmarkRunOut.model_validate(run)


@router.get("/runs/{run_id}", response_model=BenchmarkRunOut)
async def get_run(run_id: str, _: CurrentUser, db: DB) -> BenchmarkRunOut:
    await _expire_stale(db)
    run = await db.get(BenchmarkRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return BenchmarkRunOut.model_validate(run)
