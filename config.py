from __future__ import annotations

import os

# ---------- Provider switch ----------
# openai | gemini
DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()

# OpenAI (gpt-5-nano)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", os.getenv("OPENAI_API_KEYS", ""))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-nano")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")

# Gemini (gemini-3-pro-preview)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "")

# ---------- GitHub ----------
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", os.getenv("TOKEN", ""))
GITHUB_REPO_OWNER = os.getenv("GITHUB_REPO_OWNER", "lxr-astro")
GITHUB_REPO_NAME = os.getenv("GITHUB_REPO_NAME", "ChatArxiv")

# ---------- arXiv ----------
ARXIV_CATEGORY = os.getenv("ARXIV_CATEGORY", "astro-ph.GA")
DAYS_BACK = float(os.getenv("DAYS_BACK", "2"))
MAX_RESULTS = int(os.getenv("MAX_RESULTS", "99"))

# ---------- Pipeline ----------
DEFAULT_LANGUAGE = os.getenv("LANGUAGE", "zh")
DEFAULT_KEYWORD_LIST = "AGN, blazar, BL Lac"
_keyword_raw = os.getenv("KEYWORD_LIST")
if _keyword_raw is None or not _keyword_raw.strip():
    _keyword_raw = DEFAULT_KEYWORD_LIST

KEYWORD_LIST = [x.strip() for x in _keyword_raw.split(",") if x.strip()]
