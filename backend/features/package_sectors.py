import re
from typing import Literal

import httpx

PackageSector = Literal[
    "AI / ML",
    "Authentication",
    "Build Tools",
    "CLI / Utilities",
    "Cryptography",
    "Data Science",
    "Database / ORM",
    "Frontend / UI",
    "HTTP Client",
    "Infrastructure",
    "Package Manager",
    "Serialization",
    "Testing",
    "Web Framework",
]

# PyPI Topic:: classifier substrings → sector (evaluated in order, all matches kept)
_PYPI_RULES: list[tuple[str, str]] = [
    ("Security :: Cryptography", "Cryptography"),
    ("Scientific/Engineering :: Artificial Intelligence", "AI / ML"),
    ("Scientific/Engineering :: Machine Learning", "AI / ML"),
    ("Internet :: WWW/HTTP :: WSGI", "Web Framework"),
    ("Internet :: WWW/HTTP :: Dynamic Content", "Web Framework"),
    ("Libraries :: Application Frameworks", "Web Framework"),
    ("Internet :: WWW/HTTP", "HTTP Client"),
    ("System :: Networking", "HTTP Client"),
    ("Database", "Database / ORM"),
    ("Software Development :: Testing", "Testing"),
    ("Software Development :: Quality Assurance", "Build Tools"),
    ("Software Development :: Build Tools", "Build Tools"),
    ("System :: Distributed Computing", "Infrastructure"),
    ("System :: System Shells", "CLI / Utilities"),
    ("Text Processing", "Serialization"),
    ("Scientific/Engineering :: Mathematics", "Data Science"),
    ("Scientific/Engineering :: Visualization", "Data Science"),
    ("Scientific/Engineering", "Data Science"),
    ("Multimedia", "Data Science"),
]

# Any matching keyword from the set triggers the sector
_KEYWORD_RULES: list[tuple[frozenset[str], str]] = [
    (frozenset({"machine-learning", "deep-learning", "neural-network", "llm", "gpt", "nlp",
                "artificial-intelligence", "transformers", "pytorch", "tensorflow",
                "generative-ai", "foundation-model", "embedding", "vector-search"}), "AI / ML"),
    (frozenset({"jwt", "oauth", "saml", "oidc", "authentication", "auth", "identity",
                "login", "sso", "session", "token"}), "Authentication"),
    (frozenset({"bcrypt", "encryption", "decrypt", "cipher", "hmac", "pgp", "aes",
                "rsa", "elliptic", "hashing"}), "Cryptography"),
    (frozenset({"sql", "orm", "mongodb", "postgres", "mysql", "sqlite", "redis", "nosql",
                "database", "query-builder", "migration", "datastore"}), "Database / ORM"),
    (frozenset({"webpack", "rollup", "bundler", "vite", "esbuild", "transpile",
                "compiler", "tree-shaking"}), "Build Tools"),
    (frozenset({"eslint", "linter", "lint", "formatter", "prettier",
                "static-analysis", "code-quality"}), "Build Tools"),
    (frozenset({"test", "testing", "jest", "mocha", "assertion", "spec",
                "mock", "chai", "coverage", "fixture"}), "Testing"),
    (frozenset({"react", "vue", "angular", "svelte", "dom", "component",
                "frontend", "ui-library", "jsx", "tsx"}), "Frontend / UI"),
    (frozenset({"aws", "cloud", "kubernetes", "k8s", "docker", "serverless",
                "devops", "terraform", "ansible", "infrastructure"}), "Infrastructure"),
    (frozenset({"websocket", "grpc", "socket.io", "http", "ajax",
                "fetch", "rest", "xhr", "api-client", "sdk"}), "HTTP Client"),
    (frozenset({"protobuf", "msgpack", "yaml", "toml", "codec",
                "serialize", "deserialize", "marshaling"}), "Serialization"),
    (frozenset({"cli", "command-line", "argument-parser", "argv", "terminal"}), "CLI / Utilities"),
    (frozenset({"routing", "router", "navigation", "spa", "single-page-app"}), "Web Framework"),
    (frozenset({"diagram", "flowchart", "graph-visualization", "chart", "dataviz"}), "Data Science"),
    (frozenset({"workflow", "orchestration", "task-queue", "job-queue", "message-queue", "event-driven"}), "Infrastructure"),
    (frozenset({"telephony", "sms", "voice", "communication", "messaging", "twilio", "vonage"}), "Infrastructure"),
    (frozenset({"data-science", "dataframe", "statistics",
                "visualization", "plotting", "numerical"}), "Data Science"),
    (frozenset({"package-manager", "dependency-management", "semver"}), "Package Manager"),
]

# Lowercase package name substring → sector
_NAME_RULES: list[tuple[str, str]] = [
    # AI / ML
    ("torch", "AI / ML"), ("tensorflow", "AI / ML"), ("langchain", "AI / ML"),
    ("transformers", "AI / ML"), ("diffusers", "AI / ML"), ("litellm", "AI / ML"),
    ("openai", "AI / ML"), ("anthropic", "AI / ML"), ("huggingface", "AI / ML"),
    ("sentence-transformer", "AI / ML"), ("llamaindex", "AI / ML"), ("llama-index", "AI / ML"),
    ("mistralai", "AI / ML"), ("cohere", "AI / ML"), ("replicate", "AI / ML"),
    ("google-generativeai", "AI / ML"), ("google-genai", "AI / ML"),
    ("vertexai", "AI / ML"), ("vertex-ai", "AI / ML"), ("xinference", "AI / ML"),
    ("instructor", "AI / ML"), ("dspy", "AI / ML"), ("guidance", "AI / ML"),
    # Web frameworks
    ("django", "Web Framework"), ("flask", "Web Framework"), ("fastapi", "Web Framework"),
    ("starlette", "Web Framework"), ("tornado", "Web Framework"), ("falcon", "Web Framework"),
    ("express", "Web Framework"), ("nestjs", "Web Framework"), ("hono", "Web Framework"),
    ("koa", "Web Framework"), ("sanic", "Web Framework"), ("litestar", "Web Framework"),
    # HTTP clients
    ("requests", "HTTP Client"), ("httpx", "HTTP Client"), ("urllib3", "HTTP Client"),
    ("aiohttp", "HTTP Client"), ("axios", "HTTP Client"), ("got", "HTTP Client"),
    ("node-fetch", "HTTP Client"),
    # Auth
    ("pyjwt", "Authentication"), ("python-jose", "Authentication"), ("authlib", "Authentication"),
    ("pyotp", "Authentication"), ("passlib", "Authentication"),
    # Cryptography
    ("cryptography", "Cryptography"), ("pyopenssl", "Cryptography"), ("bcrypt", "Cryptography"),
    ("pynacl", "Cryptography"), ("paramiko", "Cryptography"),
    # Database
    ("sqlalchemy", "Database / ORM"), ("alembic", "Database / ORM"), ("pymongo", "Database / ORM"),
    ("motor", "Database / ORM"), ("aioredis", "Database / ORM"), ("psycopg", "Database / ORM"),
    ("typeorm", "Database / ORM"), ("prisma", "Database / ORM"), ("mongoose", "Database / ORM"),
    ("sequelize", "Database / ORM"), ("tortoise-orm", "Database / ORM"), ("peewee", "Database / ORM"),
    # Data Science
    ("numpy", "Data Science"), ("pandas", "Data Science"), ("scipy", "Data Science"),
    ("matplotlib", "Data Science"), ("scikit", "Data Science"), ("pillow", "Data Science"),
    ("opencv", "Data Science"), ("seaborn", "Data Science"), ("plotly", "Data Science"),
    ("statsmodels", "Data Science"),
    # Build tools / linters
    ("webpack", "Build Tools"), ("babel", "Build Tools"), ("eslint", "Build Tools"),
    ("prettier", "Build Tools"), ("rollup", "Build Tools"), ("vite", "Build Tools"),
    ("esbuild", "Build Tools"), ("mypy", "Build Tools"), ("ruff", "Build Tools"),
    ("black", "Build Tools"), ("flake8", "Build Tools"), ("pylint", "Build Tools"),
    ("isort", "Build Tools"), ("pyright", "Build Tools"), ("bandit", "Build Tools"),
    # CLI
    ("click", "CLI / Utilities"), ("typer", "CLI / Utilities"), ("rich", "CLI / Utilities"),
    ("tqdm", "CLI / Utilities"), ("colorama", "CLI / Utilities"), ("commander", "CLI / Utilities"),
    ("yargs", "CLI / Utilities"), ("inquirer", "CLI / Utilities"), ("chalk", "CLI / Utilities"),
    # Testing
    ("pytest", "Testing"), ("hypothesis", "Testing"), ("factory-boy", "Testing"),
    ("responses", "Testing"), ("faker", "Testing"),
    # Frontend / UI
    ("tailwind", "Frontend / UI"), ("nextjs", "Frontend / UI"), ("nuxt", "Frontend / UI"),
    ("vueuse", "Frontend / UI"), ("shadcn", "Frontend / UI"), ("radix-ui", "Frontend / UI"),
    ("antv", "Data Science"), ("echarts", "Data Science"), ("d3", "Data Science"),
    # tanstack family — router/start → Web Framework, everything else → Frontend / UI
    ("tanstack/router", "Web Framework"), ("tanstack/start", "Web Framework"),
    ("tanstack/query", "HTTP Client"), ("tanstack/form", "Frontend / UI"),
    ("tanstack/table", "Frontend / UI"), ("tanstack/virtual", "Frontend / UI"),
    ("tanstack/", "Frontend / UI"),  # catch-all for remaining @tanstack/* packages
    # security tooling and misc
    ("trivy", "Infrastructure"), ("grype", "Infrastructure"), ("syft", "Infrastructure"),
    ("guardrails", "AI / ML"), ("promptfoo", "AI / ML"),
    ("cap-js", "Database / ORM"), ("cap-js/db", "Database / ORM"),
    ("tiledesk", "Infrastructure"), ("telnyx", "Infrastructure"),
    ("uipath", "Infrastructure"), ("automagik", "AI / ML"),
    # Infrastructure
    ("boto", "Infrastructure"), ("aws-cdk", "Infrastructure"), ("azure-", "Infrastructure"),
    ("kubernetes", "Infrastructure"), ("celery", "Infrastructure"), ("kafka", "Infrastructure"),
    ("ansible", "Infrastructure"), ("terraform", "Infrastructure"), ("pulumi", "Infrastructure"),
    ("fabric", "Infrastructure"), ("invoke", "Infrastructure"), ("supervisor", "Infrastructure"),
    ("gunicorn", "Infrastructure"), ("uvicorn", "Infrastructure"), ("nginx", "Infrastructure"),
    # Serialization
    ("pyyaml", "Serialization"), ("ruamel", "Serialization"), ("toml", "Serialization"),
    ("protobuf", "Serialization"), ("msgpack", "Serialization"), ("orjson", "Serialization"),
    ("ujson", "Serialization"), ("marshmallow", "Serialization"), ("pydantic", "Serialization"),
    # Package managers
    ("poetry", "Package Manager"), ("pipenv", "Package Manager"), ("setuptools", "Package Manager"),
    ("twine", "Package Manager"), ("build", "Package Manager"), ("hatch", "Package Manager"),
    ("flit", "Package Manager"),
]


def _infer_sectors(name: str, classifiers: list[str], keywords: list[str]) -> list[str]:
    sectors: set[str] = set()
    name_lower = name.lower()
    kw_set = {k.lower() for k in keywords}

    for pattern, sector in _PYPI_RULES:
        if any(pattern in c for c in classifiers):
            sectors.add(sector)

    for trigger_kws, sector in _KEYWORD_RULES:
        if kw_set & trigger_kws:
            sectors.add(sector)

    for substr, sector in _NAME_RULES:
        if substr in name_lower:
            sectors.add(sector)

    return sorted(sectors)


async def _fetch_pypi_meta(
    client: httpx.AsyncClient, name: str
) -> tuple[list[str], list[str]]:
    try:
        r = await client.get(f"https://pypi.org/pypi/{name}/json", timeout=10)
        if r.status_code == 200:
            info = r.json().get("info", {})
            classifiers = info.get("classifiers") or []
            kw_raw = info.get("keywords") or ""
            keywords = [k.strip() for k in re.split(r"[,\s]+", kw_raw) if k.strip()]
            return classifiers, keywords
    except Exception:
        pass
    return [], []


async def _fetch_npm_keywords(client: httpx.AsyncClient, name: str) -> list[str]:
    try:
        r = await client.get(f"https://registry.npmjs.org/{name}", timeout=10)
        if r.status_code == 200:
            kw = r.json().get("keywords") or []
            return [k for k in kw if isinstance(k, str)]
    except Exception:
        pass
    return []


async def fetch_package_description(
    client: httpx.AsyncClient, name: str, ecosystem: str
) -> tuple[str, list[str]]:
    """Returns (description_text, keywords) for LLM classification."""
    if ecosystem == "PyPI":
        try:
            r = await client.get(f"https://pypi.org/pypi/{name}/json", timeout=10)
            if r.status_code == 200:
                info = r.json().get("info", {})
                desc = (info.get("description") or "")[:2000]
                kw_raw = info.get("keywords") or ""
                kw = [k.strip() for k in re.split(r"[,\s]+", kw_raw) if k.strip()]
                return desc, kw
        except Exception:
            pass
    elif ecosystem == "npm":
        try:
            r = await client.get(f"https://registry.npmjs.org/{name}/latest", timeout=10)
            if r.status_code == 200:
                data = r.json()
                desc = data.get("description") or ""
                kw = [k for k in (data.get("keywords") or []) if isinstance(k, str)]
                return desc, kw
        except Exception:
            pass
    return "", []


async def fetch_package_sectors(
    client: httpx.AsyncClient, name: str, ecosystem: str
) -> list[str]:
    if ecosystem == "PyPI":
        classifiers, keywords = await _fetch_pypi_meta(client, name)
    elif ecosystem == "npm":
        keywords = await _fetch_npm_keywords(client, name)
        classifiers = []
    else:
        classifiers, keywords = [], []

    return _infer_sectors(name, classifiers, keywords)
