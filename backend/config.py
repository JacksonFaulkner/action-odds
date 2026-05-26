import os
from functools import lru_cache
from pathlib import Path

from exa_py import AsyncExa
from google import genai
from google.genai.types import HttpOptions
from google.oauth2 import service_account
from openai import AsyncOpenAI

MOTHERDUCK_ACCESS_TOKEN = os.getenv("MOTHERDUCK_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EXA_API_KEY = os.getenv("EXA_API_KEY")

GCP_SA_PATH = Path(__file__).parent / "secrets" / "gcp-sa.json"
GCP_PROJECT_ID = "motion-off-the-ocean"
GCP_LOCATION = "us-central1"


@lru_cache(maxsize=1)
def get_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=OPENAI_API_KEY)


@lru_cache(maxsize=1)
def get_exa_client() -> AsyncExa:
    return AsyncExa(api_key=EXA_API_KEY)


@lru_cache(maxsize=1)
def get_gemini_client() -> genai.Client:
    credentials = service_account.Credentials.from_service_account_file(
        str(GCP_SA_PATH),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return genai.Client(
        vertexai=True,
        project=GCP_PROJECT_ID,
        location=GCP_LOCATION,
        credentials=credentials,
        http_options=HttpOptions(api_version="v1beta1"),
    )
