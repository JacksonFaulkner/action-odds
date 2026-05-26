import duckdb

from models.models import PackageRisk, RecentNews

_SIMILARITY_THRESHOLD = 0.92


def _exists(conn: duckdb.DuckDBPyConnection, news_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM news WHERE id = ?", [news_id]).fetchone()
    return row is not None


def _is_semantic_duplicate(
    conn: duckdb.DuckDBPyConnection,
    embedding: list[float],
) -> bool:
    row = conn.execute(
        """
        SELECT max(list_cosine_similarity(embed_description, ?::FLOAT[3072])) AS score
        FROM news
        """,
        [embedding],
    ).fetchone()
    return row is not None and row[0] is not None and row[0] >= _SIMILARITY_THRESHOLD


def _insert_news(conn: duckdb.DuckDBPyConnection, article: RecentNews) -> None:
    conn.execute(
        """
        INSERT INTO news (
            id, title, description, published_date, source_url,
            threat_actor, exploit_status, severity,
            company_labels, sector_labels,
            embed_title, embed_description, embed_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            article.id,
            article.title,
            article.description,
            article.published_date,
            article.source_url,
            article.analysis.threat_actor,
            article.analysis.exploit_status,
            article.analysis.severity,
            article.analysis.company_labels,
            article.analysis.sector_labels,
            article.embeddings.title,
            article.embeddings.description,
            article.embeddings.source,
        ],
    )


def _insert_packages(
    conn: duckdb.DuckDBPyConnection,
    news_id: str,
    packages: list[PackageRisk],
) -> None:
    if not packages:
        return
    conn.executemany(
        """
        INSERT INTO news_packages (news_id, name, ecosystem, weekly_downloads, cve_ids, epss_score, in_cisa_kev)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (news_id, name) DO NOTHING
        """,
        [
            (news_id, p.name, p.ecosystem, p.weekly_downloads, p.cve_ids, p.epss_score, p.in_cisa_kev)
            for p in packages
        ],
    )


def ingest(conn: duckdb.DuckDBPyConnection, article: RecentNews) -> str:
    """Insert article if not already stored. Returns 'inserted', 'url_duplicate', or 'semantic_duplicate'."""
    if _exists(conn, article.id):
        return "url_duplicate"

    if _is_semantic_duplicate(conn, article.embeddings.description):
        return "semantic_duplicate"

    _insert_news(conn, article)
    _insert_packages(conn, article.id, article.analysis.affected_packages)
    return "inserted"


def ingest_many(conn: duckdb.DuckDBPyConnection, articles: list[RecentNews]) -> dict[str, int]:
    counts: dict[str, int] = {"inserted": 0, "url_duplicate": 0, "semantic_duplicate": 0}
    for article in articles:
        result = ingest(conn, article)
        counts[result] += 1
    return counts
