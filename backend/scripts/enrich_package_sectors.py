import asyncio
import sys
from pathlib import Path

import duckdb
import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from features.db import DB_PATH, init_db
from features.package_sectors import fetch_package_sectors

_CONCURRENCY = 30


async def main() -> None:
    conn = duckdb.connect(DB_PATH)
    init_db(conn)

    rows = conn.execute("""
        SELECT name, ecosystem FROM packages
        WHERE sectors IS NULL AND ecosystem IN ('npm', 'PyPI')
    """).fetchall()

    if not rows:
        print("nothing to enrich")
        return

    print(f"enriching {len(rows)} packages...")

    sem = asyncio.Semaphore(_CONCURRENCY)

    async def enrich_one(
        client: httpx.AsyncClient, name: str, ecosystem: str
    ) -> tuple[str, str, list[str]]:
        async with sem:
            sectors = await fetch_package_sectors(client, name, ecosystem)
            return name, ecosystem, sectors

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        results = await asyncio.gather(
            *[enrich_one(client, name, eco) for name, eco in rows]
        )

    updated = 0
    no_match = 0
    for name, ecosystem, sectors in sorted(results, key=lambda r: (not r[2], r[0])):
        if sectors:
            conn.execute(
                "UPDATE packages SET sectors = ? WHERE name = ? AND ecosystem = ?",
                [sectors, name, ecosystem],
            )
            updated += 1
            print(f"  {name[:40]:40} {ecosystem:6} {sectors}")
        else:
            no_match += 1

    conn.close()
    print(f"\nupdated {updated}, no match {no_match}/{len(rows)}")


if __name__ == "__main__":
    asyncio.run(main())
