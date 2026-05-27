"""
Seed packages table with top 500 PyPI + npm packages.
No LLM enrichment — downloads, CVEs, EPSS, KEV only.

Flow:
  1. Fetch package name candidates (PyPI list is pre-sorted; npm candidates are re-ranked)
  2. Fetch actual weekly download counts for all candidates
  3. Re-sort npm by downloads, trim to top 500
  4. Batch-fetch CVE IDs via OSV querybatch (via build_cve_history)
  5. Bulk-fetch EPSS scores for all found CVEs
  6. Fetch CISA KEV set
  7. Compute risk_score = weekly_downloads * epss_score
  8. Upsert into packages table
"""
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

import duckdb
import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from features.cve_history import build_cve_history, fetch_top_npm, fetch_top_pypi
from features.db import DB_PATH, init_db
from features.package_enrichment import _fetch_kev_set

_TOP_N = 500
_DL_CONCURRENCY = 40
_EPSS_CHUNK = 100


# --- Download fetchers ---

async def _npm_downloads(client: httpx.AsyncClient, sem: asyncio.Semaphore, name: str) -> int:
    async with sem:
        try:
            r = await client.get(
                f"https://api.npmjs.org/downloads/point/last-week/{name}",
                timeout=10,
            )
            if r.status_code == 200:
                return r.json().get("downloads") or 0
        except Exception:
            pass
    return 0


async def _pypi_downloads(client: httpx.AsyncClient, sem: asyncio.Semaphore, name: str) -> int:
    async with sem:
        try:
            r = await client.get(
                f"https://pypistats.org/api/packages/{name.lower()}/recent",
                timeout=10,
            )
            if r.status_code == 200:
                return r.json().get("data", {}).get("last_week") or 0
        except Exception:
            pass
    return 0


async def fetch_downloads(
    packages: list[tuple[str, str]],
) -> dict[tuple[str, str], int]:
    sem = asyncio.Semaphore(_DL_CONCURRENCY)
    async with httpx.AsyncClient(timeout=10) as client:
        tasks = [
            _npm_downloads(client, sem, name) if eco == "npm"
            else _pypi_downloads(client, sem, name)
            for name, eco in packages
        ]
        results = await asyncio.gather(*tasks)
    return dict(zip(packages, results))


# --- EPSS bulk fetcher ---

async def bulk_epss(cve_ids: list[str]) -> dict[str, float]:
    """Returns {cve_id: epss_score} for all queried CVEs."""
    scores: dict[str, float] = {}
    async with httpx.AsyncClient(timeout=15) as client:
        for i in range(0, len(cve_ids), _EPSS_CHUNK):
            chunk = cve_ids[i : i + _EPSS_CHUNK]
            try:
                r = await client.get(
                    "https://api.first.org/data/v1/epss",
                    params={"cve": ",".join(chunk)},
                )
                if r.status_code == 200:
                    for entry in r.json().get("data", []):
                        scores[entry["cve"]] = float(entry["epss"])
            except Exception:
                pass
    return scores


# --- Main ---

async def main() -> None:
    print("=== seed_top_packages ===")

    # 1. Fetch name candidates
    print("\n[1/5] fetching package name lists...")
    pypi_names, npm_candidates = await asyncio.gather(
        fetch_top_pypi(_TOP_N),
        fetch_top_npm(_TOP_N),  # returns up to 1000 candidates for re-sort
    )
    print(f"  pypi candidates={len(pypi_names)}  npm candidates={len(npm_candidates)}")

    # 2. Fetch downloads for all candidates
    print("\n[2/5] fetching weekly download counts...")
    all_candidates = (
        [(n, "PyPI") for n in pypi_names]
        + [(n, "npm") for n in npm_candidates]
    )
    downloads = await fetch_downloads(all_candidates)

    # 3. Re-sort npm by actual downloads, trim to _TOP_N
    npm_ranked = sorted(
        [(n, "npm") for n in npm_candidates],
        key=lambda p: downloads.get(p, 0),
        reverse=True,
    )[:_TOP_N]

    # PyPI list is already sorted by hugovk (30-day download rank); keep order
    pypi_final = [(n, "PyPI") for n in pypi_names[:_TOP_N]]

    packages = pypi_final + npm_ranked
    print(f"  final: pypi={len(pypi_final)} npm={len(npm_ranked)} total={len(packages)}")
    top5_pypi = sorted(pypi_final, key=lambda p: downloads.get(p, 0), reverse=True)[:5]
    top5_npm  = sorted(npm_ranked,  key=lambda p: downloads.get(p, 0), reverse=True)[:5]
    print(f"  top PyPI: {[n for n,_ in top5_pypi]}")
    print(f"  top npm:  {[n for n,_ in top5_npm]}")

    # 4. CVE history via OSV
    print(f"\n[3/5] fetching CVE history ({len(packages)} packages via OSV)...")
    records = await build_cve_history(packages, progress=True)

    cve_ids_by_pkg: dict[tuple[str, str], list[str]] = defaultdict(list)
    for r in records:
        if r.cve_id:
            cve_ids_by_pkg[(r.name, r.ecosystem)].append(r.cve_id)

    all_cves = list({cve for cves in cve_ids_by_pkg.values() for cve in cves})
    print(f"  {len(records)} vuln records, {len(all_cves)} unique CVEs across {len(cve_ids_by_pkg)} packages")

    # 5. EPSS + KEV
    print("\n[4/5] fetching EPSS scores + CISA KEV...")
    async with httpx.AsyncClient(timeout=15) as client:
        epss_scores, kev_set = await asyncio.gather(
            bulk_epss(all_cves),
            _fetch_kev_set(client),
        )
    print(f"  EPSS scores fetched={len(epss_scores)}  KEV entries={len(kev_set)}")

    # 6. Upsert
    print("\n[5/5] upserting to DB...")
    conn = duckdb.connect(DB_PATH)
    init_db(conn)

    inserted = updated = 0
    for pkg in packages:
        name, ecosystem = pkg
        weekly_dl = downloads.get(pkg, 0) or 0
        cve_ids   = cve_ids_by_pkg.get(pkg, [])
        pkg_epss  = max((epss_scores.get(c, 0.0) for c in cve_ids), default=None) if cve_ids else None
        in_kev    = bool(cve_ids and kev_set & set(cve_ids))
        risk      = weekly_dl * (pkg_epss or 0.0)

        existing = conn.execute(
            "SELECT 1 FROM packages WHERE name = ? AND ecosystem = ?",
            [name, ecosystem],
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE packages
                SET weekly_downloads  = ?,
                    cve_ids           = ?,
                    epss_score        = ?,
                    in_cisa_kev       = ?,
                    risk_score        = ?,
                    last_enriched_at  = now()
                WHERE name = ? AND ecosystem = ?
                """,
                [weekly_dl, cve_ids, pkg_epss, in_kev, risk, name, ecosystem],
            )
            updated += 1
        else:
            conn.execute(
                """
                INSERT INTO packages
                    (name, ecosystem, weekly_downloads, cve_ids, epss_score, in_cisa_kev, risk_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [name, ecosystem, weekly_dl, cve_ids, pkg_epss, in_kev, risk],
            )
            inserted += 1

    conn.close()

    print(f"\ndone. inserted={inserted} updated={updated}")
    print(f"top risk packages:")
    top_risk = sorted(
        packages,
        key=lambda p: downloads.get(p, 0) * (
            max((epss_scores.get(c, 0.0) for c in cve_ids_by_pkg.get(p, [])), default=0.0)
        ),
        reverse=True,
    )[:10]
    for pkg in top_risk:
        name, eco = pkg
        dl = downloads.get(pkg, 0)
        epss = max((epss_scores.get(c, 0.0) for c in cve_ids_by_pkg.get(pkg, [])), default=0.0)
        print(f"  {eco:6} {name:40} dl={dl:>12,}  epss={epss:.4f}  risk={dl*epss:,.0f}")


if __name__ == "__main__":
    asyncio.run(main())
