import asyncio
from dataclasses import dataclass

import httpx

_OSV_ECOSYSTEMS = {"npm": "npm", "PyPI": "PyPI", "composer": "Packagist"}
_SEVERITY_MAP = {"CRITICAL": "critical", "HIGH": "high", "MODERATE": "medium", "LOW": "low"}
_OSV_BATCH = 500
_FETCH_CONCURRENCY = 50


@dataclass
class CveRecord:
    osv_id: str
    cve_id: str | None
    name: str
    ecosystem: str
    published_date: str | None
    modified_date: str | None
    severity: str | None
    cvss_vector: str | None


async def fetch_top_npm(n: int = 500) -> list[str]:
    """
    Fetch top npm package names weighted purely by download-based popularity.
    Returns n+250 candidates so the seed script can re-rank by actual download
    counts and trim to true top-n (parallel to how hugovk works for PyPI).
    """
    seen: set[str] = set()
    names: list[str] = []
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for page in range(4):  # 4 × 250 = 1000 candidates max
            if len(names) >= n + 250:
                break
            r = await client.get(
                "https://registry.npmjs.org/-/v1/search",
                params={
                    "text": "not:unstable",
                    "size": 250,
                    "from": page * 250,
                    "popularity": "1.0",
                    "quality": "0.0",
                    "maintenance": "0.0",
                },
            )
            if r.status_code != 200:
                break
            objects = r.json().get("objects", [])
            if not objects:
                break
            for obj in objects:
                pkg = obj["package"]["name"]
                if pkg not in seen:
                    seen.add(pkg)
                    names.append(pkg)
    return names  # caller trims after download-based re-sort


async def fetch_top_pypi(n: int = 500) -> list[str]:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        r = await client.get(
            "https://hugovk.github.io/top-pypi-packages/top-pypi-packages-30-days.min.json"
        )
        if r.status_code == 200:
            return [row["project"] for row in r.json().get("rows", [])[:n]]
    return []


async def _fetch_osv_ids(
    client: httpx.AsyncClient,
    packages: list[tuple[str, str]],
) -> dict[tuple[str, str], list[str]]:
    queries = [
        {"package": {"name": name, "ecosystem": _OSV_ECOSYSTEMS.get(eco, eco)}}
        for name, eco in packages
    ]
    r = await client.post(
        "https://api.osv.dev/v1/querybatch",
        json={"queries": queries},
        timeout=30,
    )
    results = r.json().get("results", [])
    return {
        pkg: [v["id"] for v in result.get("vulns", [])]
        for pkg, result in zip(packages, results)
    }


async def _fetch_vuln(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    osv_id: str,
) -> dict:
    async with sem:
        try:
            r = await client.get(f"https://api.osv.dev/v1/vulns/{osv_id}", timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
    return {"id": osv_id}


def _parse_vuln(vuln: dict) -> tuple[str | None, str | None, str | None]:
    cve_id = next((a for a in vuln.get("aliases", []) if a.startswith("CVE-")), None)

    db = vuln.get("database_specific", {})
    raw_sev = (db.get("severity") or "").upper()
    severity = _SEVERITY_MAP.get(raw_sev)

    cvss_vector = None
    for sev in vuln.get("severity", []):
        if sev.get("type") in ("CVSS_V3", "CVSS_V2", "CVSS_V4"):
            cvss_vector = sev.get("score")
            break

    return cve_id, severity, cvss_vector


async def build_cve_history(
    packages: list[tuple[str, str]],
    progress: bool = True,
) -> list[CveRecord]:
    sem = asyncio.Semaphore(_FETCH_CONCURRENCY)

    async with httpx.AsyncClient(timeout=30) as client:
        # Querybatch in chunks to get vuln IDs per package
        pkg_ids: dict[tuple[str, str], list[str]] = {}
        for i in range(0, len(packages), _OSV_BATCH):
            batch = packages[i : i + _OSV_BATCH]
            chunk = await _fetch_osv_ids(client, batch)
            pkg_ids.update(chunk)
            if progress:
                print(f"  osv ids: {min(i + _OSV_BATCH, len(packages))}/{len(packages)}")

        unique_ids = list({osv_id for ids in pkg_ids.values() for osv_id in ids})
        if progress:
            print(f"  fetching {len(unique_ids)} unique vulns in parallel...")

        # Fetch full vuln details in parallel
        tasks = [_fetch_vuln(client, sem, osv_id) for osv_id in unique_ids]
        raw_vulns = await asyncio.gather(*tasks)
        vulns_by_id = {v.get("id", ""): v for v in raw_vulns}

    records: list[CveRecord] = []
    for (name, ecosystem), osv_ids in pkg_ids.items():
        for osv_id in osv_ids:
            vuln = vulns_by_id.get(osv_id, {"id": osv_id})
            cve_id, severity, cvss_vector = _parse_vuln(vuln)
            records.append(CveRecord(
                osv_id=osv_id,
                cve_id=cve_id,
                name=name,
                ecosystem=ecosystem,
                published_date=vuln.get("published"),
                modified_date=vuln.get("modified"),
                severity=severity,
                cvss_vector=cvss_vector,
            ))

    return records
