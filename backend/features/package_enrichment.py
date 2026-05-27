import asyncio
import re
from dataclasses import dataclass, field

import httpx


@dataclass
class PackageEnrichment:
    weekly_downloads: int | None
    cve_ids: list[str]
    epss_score: float | None
    in_cisa_kev: bool
    github_org: str | None = None
    logo_url: str | None = None


async def _fetch_npm_downloads(client: httpx.AsyncClient, name: str) -> int | None:
    try:
        r = await client.get(f"https://api.npmjs.org/downloads/point/last-week/{name}")
        if r.status_code == 200:
            return r.json().get("downloads")
    except Exception:
        pass
    return None


async def _fetch_pypi_downloads(client: httpx.AsyncClient, name: str) -> int | None:
    try:
        r = await client.get(f"https://pypistats.org/api/packages/{name.lower()}/recent")
        if r.status_code == 200:
            return r.json().get("data", {}).get("last_week")
    except Exception:
        pass
    return None


async def _fetch_cve_ids(client: httpx.AsyncClient, name: str, ecosystem: str) -> list[str]:
    osv_ecosystem = {"npm": "npm", "PyPI": "PyPI", "composer": "Packagist"}.get(ecosystem, ecosystem)
    try:
        r = await client.post(
            "https://api.osv.dev/v1/query",
            json={"package": {"name": name, "ecosystem": osv_ecosystem}},
        )
        if r.status_code == 200:
            vulns = r.json().get("vulns", [])
            return [
                alias
                for v in vulns
                for alias in v.get("aliases", [v.get("id", "")])
                if alias.startswith("CVE-")
            ]
    except Exception:
        pass
    return []


async def _fetch_epss(client: httpx.AsyncClient, cve_ids: list[str]) -> float | None:
    if not cve_ids:
        return None
    try:
        r = await client.get(
            "https://api.first.org/data/v1/epss",
            params={"cve": ",".join(cve_ids[:10])},
        )
        if r.status_code == 200:
            data = r.json().get("data", [])
            scores = [float(d["epss"]) for d in data if "epss" in d]
            return max(scores) if scores else None
    except Exception:
        pass
    return None


async def _fetch_kev_set(client: httpx.AsyncClient) -> set[str]:
    try:
        r = await client.get(
            "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
            timeout=15,
        )
        if r.status_code == 200:
            vulns = r.json().get("vulnerabilities", [])
            return {v["cveID"] for v in vulns}
    except Exception:
        pass
    return set()


async def _fetch_github_org(client: httpx.AsyncClient, name: str, ecosystem: str) -> str | None:
    try:
        if ecosystem == "npm":
            r = await client.get(f"https://registry.npmjs.org/{name}")
            if r.status_code == 200:
                repo = r.json().get("repository", {})
                url = repo.get("url", "") if isinstance(repo, dict) else str(repo)
                m = re.search(r"github\.com[/:]([^/]+)", url)
                return m.group(1) if m else None
        elif ecosystem == "PyPI":
            r = await client.get(f"https://pypi.org/pypi/{name}/json")
            if r.status_code == 200:
                urls = r.json().get("info", {}).get("project_urls") or {}
                for url in urls.values():
                    m = re.search(r"github\.com[/:]([^/]+)", url)
                    if m:
                        return m.group(1)
    except Exception:
        pass
    return None


async def _fetch_github_avatar(client: httpx.AsyncClient, org: str) -> str | None:
    for endpoint in [
        f"https://api.github.com/orgs/{org}",
        f"https://api.github.com/users/{org}",
    ]:
        try:
            r = await client.get(endpoint)
            if r.status_code == 200:
                return r.json().get("avatar_url")
        except Exception:
            pass
    return None


async def _enrich_one(
    client: httpx.AsyncClient,
    name: str,
    ecosystem: str,
) -> PackageEnrichment:
    downloads_coro = (
        _fetch_npm_downloads(client, name) if ecosystem == "npm"
        else _fetch_pypi_downloads(client, name) if ecosystem == "PyPI"
        else asyncio.sleep(0, result=None)
    )

    downloads, cve_ids, github_org = await asyncio.gather(
        downloads_coro,
        _fetch_cve_ids(client, name, ecosystem),
        _fetch_github_org(client, name, ecosystem),
    )

    epss, logo_url = await asyncio.gather(
        _fetch_epss(client, cve_ids),
        _fetch_github_avatar(client, github_org) if github_org else asyncio.sleep(0, result=None),
    )

    return PackageEnrichment(
        weekly_downloads=downloads,
        cve_ids=cve_ids,
        epss_score=epss,
        in_cisa_kev=False,
        github_org=github_org,
        logo_url=logo_url,
    )


async def enrich_packages(
    packages: list[tuple[str, str]],  # (name, ecosystem)
) -> dict[tuple[str, str], PackageEnrichment]:
    async with httpx.AsyncClient(timeout=10) as client:
        kev_set, results = await asyncio.gather(
            _fetch_kev_set(client),
            asyncio.gather(*[_enrich_one(client, name, ecosystem) for name, ecosystem in packages]),
        )

    for result in results:
        result.in_cisa_kev = bool(result.cve_ids and kev_set & set(result.cve_ids))

    return dict(zip(packages, results))