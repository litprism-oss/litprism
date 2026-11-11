from typing import Annotated

from db.engine import get_db
from db.models import Project
from dependencies import CurrentUser, OwnedProject
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])

DB = Annotated[AsyncSession, Depends(get_db)]


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
async def list_projects(user: CurrentUser, db: DB) -> list[Project]:
    result = await db.execute(
        select(Project).where(Project.owner_id == user.id).order_by(Project.created_at)
    )
    return list(result.scalars().all())


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project: OwnedProject) -> Project:
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(project: OwnedProject, body: ProjectUpdate, db: DB) -> Project:
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project: OwnedProject, db: DB) -> None:
    await db.delete(project)
    await db.commit()
