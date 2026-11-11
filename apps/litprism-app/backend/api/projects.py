from typing import Annotated

from db.engine import get_db
from db.models import Article, Criteria, Project, ScreeningResult
from dependencies import CurrentUser, OwnedProject
from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])

DB = Annotated[AsyncSession, Depends(get_db)]


async def _with_stats(db: AsyncSession, projects: list[Project]) -> list[ProjectOut]:
    """Attach article/screening counts to projects with a handful of grouped queries."""
    ids = [p.id for p in projects]
    out = [ProjectOut.model_validate(p) for p in projects]
    if not ids:
        return out

    articles = dict(
        (
            await db.execute(
                select(Article.project_id, func.count(Article.id))
                .where(Article.project_id.in_(ids))
                .group_by(Article.project_id)
            )
        ).all()
    )
    with_criteria = set(
        (await db.execute(select(Criteria.project_id).where(Criteria.project_id.in_(ids))))
        .scalars()
        .all()
    )

    # Latest screening result per article; a human decision overrides the model's.
    ranked = (
        select(
            ScreeningResult.project_id.label("project_id"),
            func.coalesce(ScreeningResult.human_decision, ScreeningResult.decision).label("d"),
            func.row_number()
            .over(
                partition_by=ScreeningResult.article_id,
                order_by=ScreeningResult.screened_at.desc(),
            )
            .label("rn"),
        )
        .where(ScreeningResult.project_id.in_(ids))
        .subquery()
    )
    screened: dict[str, int] = {}
    included: dict[str, int] = {}
    for project_id, decision, n in (
        await db.execute(
            select(ranked.c.project_id, ranked.c.d, func.count())
            .where(ranked.c.rn == 1)
            .group_by(ranked.c.project_id, ranked.c.d)
        )
    ).all():
        screened[project_id] = screened.get(project_id, 0) + n
        if decision == "include":
            included[project_id] = n

    for item in out:
        item.article_count = articles.get(item.id, 0)
        item.screened_count = screened.get(item.id, 0)
        item.included_count = included.get(item.id, 0)
        item.has_criteria = item.id in with_criteria
    return out


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectCreate, user: CurrentUser, db: DB) -> Project:
    project = Project(
        name=body.name,
        description=body.description,
        research_question=body.research_question,
        review_type=body.review_type,
        owner_id=user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
async def list_projects(user: CurrentUser, db: DB) -> list[ProjectOut]:
    result = await db.execute(
        select(Project).where(Project.owner_id == user.id).order_by(Project.created_at)
    )
    return await _with_stats(db, list(result.scalars().all()))


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project: OwnedProject, db: DB) -> ProjectOut:
    return (await _with_stats(db, [project]))[0]


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(project: OwnedProject, body: ProjectUpdate, db: DB) -> Project:
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project: OwnedProject, db: DB) -> None:
    # One DELETE: every table references projects with ON DELETE CASCADE, so the database
    # removes the children itself. `db.delete(project)` would first load every article and
    # result into memory (thousands of rows), which timed out at the gateway.
    await db.execute(delete(Project).where(Project.id == project.id))
    await db.commit()
