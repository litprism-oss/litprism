import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    search_runs: Mapped[list["SearchRun"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    upload_records: Mapped[list["UploadRecord"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    articles: Mapped[list["Article"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    deduplication_logs: Mapped[list["DeduplicationLog"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    criteria: Mapped[list["Criteria"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    screening_results: Mapped[list["ScreeningResult"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    screening_runs: Mapped[list["ScreeningRun"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class SearchRun(Base):
    __tablename__ = "search_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    review_type: Mapped[str] = mapped_column(String, nullable=False)
    query_natural: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_generated: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_final: Mapped[str | None] = mapped_column(Text, nullable=True)
    filters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    locked_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="search_runs")
    source_queries: Mapped[list["SourceQuery"]] = relationship(
        back_populates="search_run", cascade="all, delete-orphan"
    )
    upload_records: Mapped[list["UploadRecord"]] = relationship(
        back_populates="search_run", cascade="all, delete-orphan"
    )
    articles: Mapped[list["Article"]] = relationship(back_populates="search_run")


class SourceQuery(Base):
    __tablename__ = "source_queries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    search_run_id: Mapped[str] = mapped_column(
        String, ForeignKey("search_runs.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    interface: Mapped[str] = mapped_column(String, nullable=False)
    query_string: Mapped[str] = mapped_column(Text, nullable=False)
    filters_applied: Mapped[dict] = mapped_column(JSON, nullable=False)
    filters_human_readable: Mapped[str] = mapped_column(Text, nullable=False)
    searched_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)

    search_run: Mapped["SearchRun"] = relationship(back_populates="source_queries")


class UploadRecord(Base):
    __tablename__ = "upload_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    search_run_id: Mapped[str] = mapped_column(
        String, ForeignKey("search_runs.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    format: Mapped[str] = mapped_column(String, nullable=False)
    uploaded_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="upload_records")
    search_run: Mapped["SearchRun"] = relationship(back_populates="upload_records")


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    search_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("search_runs.id"), nullable=True
    )
    pmid: Mapped[str | None] = mapped_column(String, nullable=True)
    doi: Mapped[str | None] = mapped_column(String, nullable=True)
    europepmc_id: Mapped[str | None] = mapped_column(String, nullable=True)
    semantic_scholar_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    authors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    journal: Mapped[str | None] = mapped_column(String, nullable=True)
    pub_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    upload_format: Mapped[str | None] = mapped_column(String, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="articles")
    search_run: Mapped["SearchRun | None"] = relationship(back_populates="articles")
    screening_results: Mapped[list["ScreeningResult"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )


class DeduplicationLog(Base):
    __tablename__ = "deduplication_log"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    kept_article_id: Mapped[str] = mapped_column(String, ForeignKey("articles.id"), nullable=False)
    duplicate_article_id: Mapped[str] = mapped_column(
        String, ForeignKey("articles.id"), nullable=False
    )
    match_type: Mapped[str] = mapped_column(String, nullable=False)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="deduplication_logs")
    kept_article: Mapped["Article"] = relationship(foreign_keys=[kept_article_id])
    duplicate_article: Mapped["Article"] = relationship(foreign_keys=[duplicate_article_id])


class Criteria(Base):
    __tablename__ = "criteria"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_criteria_project_version"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    inclusion: Mapped[list] = mapped_column(JSON, nullable=False)
    exclusion: Mapped[list] = mapped_column(JSON, nullable=False)
    uncertain_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.90)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    superseded_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="criteria")
    screening_results: Mapped[list["ScreeningResult"]] = relationship(back_populates="criteria")
    screening_runs: Mapped[list["ScreeningRun"]] = relationship(back_populates="criteria")


class ScreeningResult(Base):
    __tablename__ = "screening_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    article_id: Mapped[str] = mapped_column(
        String, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    criteria_id: Mapped[str] = mapped_column(String, ForeignKey("criteria.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    criteria_hits: Mapped[list] = mapped_column(JSON, nullable=False)
    model_used: Mapped[str] = mapped_column(String, nullable=False)
    llm_provider: Mapped[str] = mapped_column(String, nullable=False)
    human_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    human_decision: Mapped[str | None] = mapped_column(String, nullable=True)
    human_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    screened_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    overridden_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)

    article: Mapped["Article"] = relationship(back_populates="screening_results")
    project: Mapped["Project"] = relationship(back_populates="screening_results")
    criteria: Mapped["Criteria"] = relationship(back_populates="screening_results")


class ScreeningRun(Base):
    __tablename__ = "screening_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    criteria_id: Mapped[str] = mapped_column(String, ForeignKey("criteria.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    total_articles: Mapped[int] = mapped_column(Integer, nullable=False)
    screened_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resumed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="screening_runs")
    criteria: Mapped["Criteria"] = relationship(back_populates="screening_runs")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="chat_messages")
