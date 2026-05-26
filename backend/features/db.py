import duckdb
from fastapi import Request

# Switch to "md:action_odds" for MotherDuck
DB_PATH = "action_odds.duckdb"


def get_db(request: Request) -> duckdb.DuckDBPyConnection:
    return request.app.state.db


def init_db(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id      VARCHAR PRIMARY KEY,
            title   VARCHAR NOT NULL,
            logo    VARCHAR,
            grade   VARCHAR NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            id          VARCHAR PRIMARY KEY,
            company_id  VARCHAR NOT NULL REFERENCES companies(id),
            title       VARCHAR NOT NULL,
            description VARCHAR NOT NULL,
            grade       VARCHAR NOT NULL,
            price       INTEGER NOT NULL,
            payout      INTEGER NOT NULL,
            end_date    TIMESTAMP NOT NULL,
            status      VARCHAR NOT NULL DEFAULT 'open'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         VARCHAR PRIMARY KEY,
            username   VARCHAR NOT NULL,
            schmeckles INTEGER NOT NULL DEFAULT 1000
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            id         VARCHAR PRIMARY KEY,
            user_id    VARCHAR NOT NULL REFERENCES users(id),
            market_id  VARCHAR NOT NULL REFERENCES markets(id),
            placed_at  TIMESTAMP NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id               VARCHAR PRIMARY KEY,
            title            VARCHAR NOT NULL,
            description      VARCHAR,
            published_date   TIMESTAMPTZ,
            source_url       VARCHAR NOT NULL,
            threat_actor     VARCHAR,
            exploit_status   VARCHAR,
            severity         VARCHAR,
            company_labels   VARCHAR[],
            sector_labels    VARCHAR[],
            embed_title      FLOAT[3072],
            embed_description FLOAT[3072],
            embed_source     FLOAT[3072],
            ingested_at      TIMESTAMPTZ DEFAULT now()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS news_packages (
            news_id          VARCHAR NOT NULL REFERENCES news(id),
            name             VARCHAR NOT NULL,
            ecosystem        VARCHAR NOT NULL,
            weekly_downloads INTEGER,
            cve_ids          VARCHAR[],
            epss_score       FLOAT,
            in_cisa_kev      BOOLEAN NOT NULL DEFAULT false,
            PRIMARY KEY (news_id, name)
        )
    """)


_CDN = "https://cdn.simpleicons.org"

COMPANIES = [
    # Grade A — massive security orgs, slow to adopt unvetted deps
    {"id": "google", "title": "Google", "logo": f"{_CDN}/google", "grade": "A"},
    {"id": "microsoft", "title": "Microsoft", "logo": "https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg", "grade": "A"},
    # Grade B — strong security, but broader open-source surface
    {"id": "stripe", "title": "Stripe", "logo": f"{_CDN}/stripe", "grade": "B"},
    {"id": "cloudflare", "title": "Cloudflare", "logo": f"{_CDN}/cloudflare", "grade": "B"},
    {"id": "github", "title": "GitHub", "logo": f"{_CDN}/github", "grade": "B"},
    # Grade C — medium exposure, real third-party integration risk
    {"id": "shopify", "title": "Shopify", "logo": f"{_CDN}/shopify", "grade": "C"},
    {"id": "twilio", "title": "Twilio", "logo": f"{_CDN}/twilio", "grade": "C"},
    {"id": "okta", "title": "Okta", "logo": f"{_CDN}/okta", "grade": "C"},
    # Grade D — high npm/pip dependency count, fast-moving teams
    {"id": "robinhood", "title": "Robinhood", "logo": f"{_CDN}/robinhood", "grade": "D"},
    {"id": "coinbase", "title": "Coinbase", "logo": f"{_CDN}/coinbase", "grade": "D"},
    # Grade F — open source everything, huge transitive dep surface
    {"id": "vercel", "title": "Vercel", "logo": f"{_CDN}/vercel", "grade": "F"},
    {"id": "huggingface", "title": "Hugging Face", "logo": f"{_CDN}/huggingface", "grade": "F"},
    {"id": "replit", "title": "Replit", "logo": f"{_CDN}/replit", "grade": "F"},
]


def seed_companies(conn: duckdb.DuckDBPyConnection) -> None:
    conn.executemany(
        """
        INSERT INTO companies (id, title, logo, grade) VALUES (?, ?, ?, ?)
        ON CONFLICT (id) DO UPDATE SET title = excluded.title, logo = excluded.logo, grade = excluded.grade
        """,
        [(c["id"], c["title"], c["logo"], c["grade"]) for c in COMPANIES],
    )
    print(f"Seeded {len(COMPANIES)} companies.")


if __name__ == "__main__":
    conn = duckdb.connect(DB_PATH)
    init_db(conn)
    seed_companies(conn)
    conn.close()