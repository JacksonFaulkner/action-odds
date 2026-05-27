import asyncio
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).parent.parent))

from features.db import DB_PATH, init_db
from features.package_enrichment import enrich_packages


async def main() -> None:
    conn = duckdb.connect(DB_PATH)
    init_db(conn)

    rows = conn.execute("""
        SELECT name, ecosystem
        FROM packages
        WHERE logo_url IS NULL
        AND ecosystem IN ('npm', 'PyPI', 'composer')
    """).fetchall()

    if not rows:
        print("nothing to enrich")
        return

    packages = [(name, ecosystem) for name, ecosystem in rows]
    print(f"enriching {len(packages)} packages...")

    enriched = await enrich_packages(packages)

    updated = 0
    for (name, ecosystem), data in enriched.items():
        try:
            conn.execute("""
                UPDATE packages
                SET weekly_downloads  = ?,
                    cve_ids           = ?,
                    epss_score        = ?,
                    in_cisa_kev       = ?,
                    github_org        = ?,
                    logo_url          = ?,
                    last_enriched_at  = now()
                WHERE name = ? AND ecosystem = ?
            """, [
                data.weekly_downloads,
                data.cve_ids or [],
                data.epss_score,
                data.in_cisa_kev,
                data.github_org,
                data.logo_url,
                name,
                ecosystem,
            ])
            updated += 1
            print(f"  {name:40} downloads={data.weekly_downloads} cves={len(data.cve_ids)} logo={'✓' if data.logo_url else '✗'}")
        except Exception as e:
            print(f"  ERROR {name}: {e}")

    conn.close()
    print(f"\nupdated {updated} packages")


if __name__ == "__main__":
    asyncio.run(main())
