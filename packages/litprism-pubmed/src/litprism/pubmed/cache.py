"""Optional SQLite cache for fetched articles.

Keyed on (pmid, fetch_date). Entries are valid for TTL_DAYS (7) days — a
cache hit is returned if any entry for the PMID was fetched within that
window, using the most recent fetch. Older entries are removed by
purge_expired().

Usage:
    cache = ArticleCache("~/.litprism/pubmed_cache.db")
    hit = cache.get("12345678")
    if hit is None:
        article = await client.fetch_one("12345678")
        cache.set(article)
    cache.purge_expired()  # call periodically to reclaim space
"""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

from litprism.pubmed.models import Article

TTL_DAYS = 7


class ArticleCache:
    """SQLite-backed cache for Article records.

    Entries expire after TTL_DAYS days. get() and get_many() return the most
    recent entry within the TTL window; purge_expired() deletes stale rows.
    """

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

    def _cutoff_date(self) -> str:
        """ISO date string TTL_DAYS ago — entries older than this are expired."""
        return (date.today() - timedelta(days=TTL_DAYS)).isoformat()

    def get(self, pmid: str) -> Article | None:
        """Return the most recently cached Article within the TTL window, or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM articles WHERE pmid = ? AND fetch_date >= ? "
                "ORDER BY fetch_date DESC LIMIT 1",
                (pmid, self._cutoff_date()),
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
        """Return a dict of pmid → Article for all PMIDs with a hit in the TTL window.

        When multiple entries exist for a PMID (fetched on different days within
        the window), the most recent one is returned.
        """
        cutoff = self._cutoff_date()
        placeholders = ",".join("?" * len(pmids))
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT pmid, data, fetch_date FROM articles "
                f"WHERE pmid IN ({placeholders}) AND fetch_date >= ?",
                (*pmids, cutoff),
            ).fetchall()
        # Keep the most recent entry per pmid
        best: dict[str, tuple[str, str]] = {}  # pmid → (fetch_date, data)
        for pmid, data, fetch_date in rows:
            if pmid not in best or fetch_date > best[pmid][0]:
                best[pmid] = (fetch_date, data)
        return {pmid: Article.model_validate_json(data) for pmid, (_, data) in best.items()}

    def purge_expired(self) -> int:
        """Delete all entries older than TTL_DAYS. Returns the number of rows deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM articles WHERE fetch_date < ?",
                (self._cutoff_date(),),
            )
        return cursor.rowcount
