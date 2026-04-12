"""Optional SQLite cache for fetched articles.

Keyed on (pmid, fetch_date) so re-fetching on a different day bypasses
the cache and picks up any PubMed record updates.

Usage:
    cache = ArticleCache("~/.litprism/pubmed_cache.db")
    hit = cache.get("12345678")
    if hit is None:
        article = await client.fetch_one("12345678")
        cache.set(article)
"""

import sqlite3
from datetime import date
from pathlib import Path

from litprism.pubmed.models import Article


class ArticleCache:
    """SQLite-backed cache for Article records."""

    def __init__(self, db_path: str | Path = "~/.litprism/pubmed_cache.db") -> None:
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    pmid        TEXT NOT NULL,
                    fetch_date  TEXT NOT NULL,
                    data        TEXT NOT NULL,
                    PRIMARY KEY (pmid, fetch_date)
                )
            """)

    def _today(self) -> str:
        return date.today().isoformat()

    def get(self, pmid: str) -> Article | None:
        """Return cached Article for today, or None if not cached."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM articles WHERE pmid = ? AND fetch_date = ?",
                (pmid, self._today()),
            ).fetchone()
        if row is None:
            return None
        return Article.model_validate_json(row[0])

    def set(self, article: Article) -> None:
        """Cache an Article keyed on its PMID and today's date."""
        if article.pmid is None:
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO articles (pmid, fetch_date, data)
                VALUES (?, ?, ?)
                """,
                (article.pmid, self._today(), article.model_dump_json()),
            )

    def set_many(self, articles: list[Article]) -> None:
        """Cache multiple articles in a single transaction."""
        today = self._today()
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO articles (pmid, fetch_date, data) VALUES (?, ?, ?)",
                [(a.pmid, today, a.model_dump_json()) for a in articles if a.pmid is not None],
            )

    def get_many(self, pmids: list[str]) -> dict[str, Article]:
        """Return a dict of pmid → Article for all cached PMIDs."""
        today = self._today()
        placeholders = ",".join("?" * len(pmids))
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT pmid, data FROM articles WHERE pmid IN ({placeholders}) "
                f"AND fetch_date = ?",
                (*pmids, today),
            ).fetchall()
        return {pmid: Article.model_validate_json(data) for pmid, data in rows}
