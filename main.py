from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import feedparser
import requests
from dotenv import load_dotenv

from config import (
    ARXIV_CATEGORY,
    DAYS_BACK,
    DEFAULT_LANGUAGE,
    DEFAULT_PROVIDER,
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    GEMINI_MODEL,
    GITHUB_REPO_NAME,
    GITHUB_REPO_OWNER,
    GITHUB_TOKEN,
    KEYWORD_LIST,
    MAX_RESULTS,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
)
from github_issue import create_issue, split_text_into_chunks

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


ARXIV_API_URLS = [
    "https://export.arxiv.org/api/query",
    "https://arxiv.org/api/query",
]
ARXIV_TIMEOUT = 30
UTC = dt.timezone.utc


def log(message: str) -> None:
    now = dt.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {message}", flush=True)


@dataclass
class Paper:
    arxiv_id: str
    title: str
    summary: str
    updated: dt.datetime
    published: dt.datetime
    authors: List[str]
    link: str


class ArxivClient:
    def __init__(self, category: str, user_agent: str = "ChatArxiv/2.0") -> None:
        self.category = category
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def search(self, query: str, max_results: int) -> List[Paper]:
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "lastUpdatedDate",
            "sortOrder": "descending",
        }
        last_exc: Exception | None = None
        parsed = None

        for base_url in ARXIV_API_URLS:
            for attempt in range(1, 4):
                try:
                    log(f"[arxiv] trying {base_url} (attempt {attempt}/3)")
                    started = time.time()
                    resp = self.session.get(base_url, params=params, timeout=ARXIV_TIMEOUT)
                    resp.raise_for_status()
                    parsed = feedparser.parse(resp.text)
                    log(
                        f"[arxiv] success {base_url} (attempt {attempt}/3) "
                        f"in {time.time() - started:.2f}s"
                    )
                    break
                except requests.RequestException as exc:
                    last_exc = exc
                    log(f"[arxiv] failed {base_url} attempt {attempt}/3: {exc}")
                    time.sleep(min(2 * attempt, 5))
            if parsed is not None:
                break

        if parsed is None:
            raise RuntimeError(f"All arXiv endpoints failed. Last error: {last_exc}") from last_exc

        papers: List[Paper] = []
        for entry in parsed.entries:
            papers.append(
                Paper(
                    arxiv_id=_extract_arxiv_id(entry.get("id", "")),
                    title=_normalize_ws(entry.get("title", "")),
                    summary=_normalize_ws(entry.get("summary", "")),
                    updated=_parse_arxiv_time(entry.get("updated", "1970-01-01T00:00:00Z")),
                    published=_parse_arxiv_time(entry.get("published", "1970-01-01T00:00:00Z")),
                    authors=[a.name for a in entry.get("authors", [])],
                    link=entry.get("id", ""),
                )
            )
        log(f"[arxiv] parsed {len(papers)} papers")
        return papers


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_arxiv_id(url: str) -> str:
    if not url:
        return ""
    return url.rstrip("/").split("/")[-1]


def _parse_arxiv_time(value: str) -> dt.datetime:
    return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def keyword_match(paper: Paper, keyword: str) -> bool:
    text = f"{paper.title}\n{paper.summary}".lower()
    return keyword.lower().strip() in text


def filter_recent(papers: Iterable[Paper], days_back: float) -> List[Paper]:
    cutoff = dt.datetime.now(UTC) - dt.timedelta(days=days_back)
    return [p for p in papers if p.updated >= cutoff]


def query_for_keyword(keyword: str, category: str) -> str:
    # category + tokenized all: terms keeps query behavior close to old project.
    terms = " AND ".join(f"all:{token}" for token in keyword.split() if token.strip())
    return f"cat:{category} AND ({terms})" if terms else f"cat:{category}"


def build_prompt(paper: Paper, language: str) -> str:
    return f"""
You are reading a freshly published arXiv paper.

Please answer in {language}. Keep proper nouns in English.

Return Markdown with this exact structure:

**Translated Abstract**
...

**Summary**
1. Research background
2. Prior methods and limitations
3. Main contributions
4. Method overview
5. Task and performance

Paper metadata:
- Title: {paper.title}
- Link: {paper.link}
- Authors: {", ".join(paper.authors)}
- Updated (UTC): {paper.updated.isoformat()}
- Abstract: {paper.summary}
""".strip()


def summarize_with_openai(prompt: str, model: str, api_key: str, base_url: str | None) -> str:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed.")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing.")

    client = OpenAI(api_key=api_key, base_url=base_url or None)
    started = time.time()
    log(f"[llm/openai] requesting summary model={model}")
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": "You are a rigorous research assistant."},
            {"role": "user", "content": prompt},
        ],
    )
    log(f"[llm/openai] response received in {time.time() - started:.2f}s")
    text = getattr(resp, "output_text", "")
    if text:
        return text.strip()

    parts: List[str] = []
    for item in getattr(resp, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", "") == "output_text":
                parts.append(getattr(content, "text", ""))
    return "\n".join(parts).strip()


def summarize_with_gemini(prompt: str, model: str, api_key: str, base_url: str | None) -> str:
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing.")

    endpoint_base = (base_url or "https://generativelanguage.googleapis.com").rstrip("/")
    url = f"{endpoint_base}/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }
    started = time.time()
    log(f"[llm/gemini] requesting summary model={model}")
    resp = requests.post(url, params={"key": api_key}, json=payload, timeout=60)
    resp.raise_for_status()
    log(f"[llm/gemini] response received in {time.time() - started:.2f}s")
    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini empty response: {data}")

    texts: List[str] = []
    for part in candidates[0].get("content", {}).get("parts", []):
        text = part.get("text", "")
        if text:
            texts.append(text)
    return "\n".join(texts).strip()


def summarize_paper(paper: Paper, provider: str, model: str, language: str) -> str:
    prompt = build_prompt(paper, language=language)
    if provider == "openai":
        return summarize_with_openai(
            prompt=prompt,
            model=model,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
        )
    if provider == "gemini":
        return summarize_with_gemini(
            prompt=prompt,
            model=model,
            api_key=GEMINI_API_KEY,
            base_url=GEMINI_BASE_URL,
        )
    raise ValueError(f"Unsupported provider: {provider}")


def format_markdown(keyword: str, papers: List[Paper], summaries: Dict[str, str]) -> str:
    lines = [f"# {keyword}"]
    if not papers:
        lines.append("- No matching papers in the selected time range.")
        return "\n".join(lines)

    for p in papers:
        lines.extend(
            [
                f"## {p.title}",
                f"- ArXiv: {p.arxiv_id}",
                f"- Link: {p.link}",
                f"- Updated (UTC): {p.updated.isoformat()}",
                f"- Authors: {', '.join(p.authors)}",
                f"- Abstract: {p.summary}",
                "",
                summaries.get(p.arxiv_id, "(summary failed)"),
                "",
            ]
        )
    return "\n".join(lines)


def write_export(content: str, output_dir: Path, suffix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(UTC).strftime("%Y-%m-%d-%H")
    path = output_dir / f"{ts}.{suffix}"
    path.write_text(content, encoding="utf-8")
    return path


def run(args: argparse.Namespace) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    if not args.model:
        args.model = OPENAI_MODEL if args.provider == "openai" else GEMINI_MODEL
    log(
        f"start mode={args.mode} provider={args.provider} model={args.model} "
        f"keywords={args.keywords} max_results={args.max_results}"
    )

    if args.mode == "create-issue":
        log("stage=create-issue: loading latest markdown")
        newest = sorted(Path(args.output_dir).glob(f"*.{args.file_format}"))
        if not newest:
            raise FileNotFoundError(f"No markdown found in {args.output_dir}")

        body = newest[-1].read_text(encoding="utf-8")
        issue_title = dt.datetime.now(UTC).strftime("%Y-%m-%d-%H")
        chunks = split_text_into_chunks(body, max_chunk_size=args.issue_chunk_size)
        for idx, chunk in enumerate(chunks, start=1):
            title = f"{issue_title}_{idx}" if len(chunks) > 1 else issue_title
            log(f"creating issue chunk {idx}/{len(chunks)} title={title}")
            create_issue(
                title=title,
                body=chunk,
                labels=args.keywords,
                token=GITHUB_TOKEN,
                owner=GITHUB_REPO_OWNER,
                repo=GITHUB_REPO_NAME,
            )
        log(f"[ok] created {len(chunks)} issue(s)")
        return

    arxiv_client = ArxivClient(category=args.category)
    all_sections: List[str] = []

    for kw_idx, keyword in enumerate(args.keywords, start=1):
        log(f"keyword {kw_idx}/{len(args.keywords)}: {keyword}")
        query = query_for_keyword(keyword, args.category)
        log(f"query: {query}")
        papers = arxiv_client.search(query=query, max_results=args.max_results)
        log(f"retrieved={len(papers)} before filters")
        papers = filter_recent(papers, days_back=args.days_back)
        log(f"after time filter={len(papers)}")
        papers = [p for p in papers if keyword_match(p, keyword)]
        log(f"after keyword filter={len(papers)}")

        summaries: Dict[str, str] = {}
        for p_idx, paper in enumerate(papers, start=1):
            try:
                short_title = (paper.title[:80] + "...") if len(paper.title) > 80 else paper.title
                log(f"paper {p_idx}/{len(papers)} summarizing {paper.arxiv_id} | {short_title}")
                started = time.time()
                summaries[paper.arxiv_id] = summarize_paper(
                    paper=paper,
                    provider=args.provider,
                    model=args.model,
                    language=args.language,
                )
                log(
                    f"paper {p_idx}/{len(papers)} summary done in "
                    f"{time.time() - started:.2f}s"
                )
            except Exception as exc:
                log(f"paper {p_idx}/{len(papers)} summary failed: {exc}")
                summaries[paper.arxiv_id] = f"Summary failed: {exc}"

        all_sections.append(format_markdown(keyword=keyword, papers=papers, summaries=summaries))
        log(f"keyword done: {keyword}")

    full_markdown = "\n\n".join(all_sections)
    log(f"markdown assembled, size={len(full_markdown)} chars")

    output_path: Path | None = None
    if args.mode in {"generate", "all"}:
        log(f"writing file to {args.output_dir} as .{args.file_format}")
        output_path = write_export(
            content=full_markdown,
            output_dir=Path(args.output_dir),
            suffix=args.file_format,
        )
        log(f"[ok] markdown generated: {output_path}")

    if args.mode == "all" and not args.dry_run:
        body = full_markdown

        issue_title = dt.datetime.now(UTC).strftime("%Y-%m-%d-%H")
        chunks = split_text_into_chunks(body, max_chunk_size=args.issue_chunk_size)
        for idx, chunk in enumerate(chunks, start=1):
            title = f"{issue_title}_{idx}" if len(chunks) > 1 else issue_title
            log(f"creating issue chunk {idx}/{len(chunks)} title={title}")
            create_issue(
                title=title,
                body=chunk,
                labels=args.keywords,
                token=GITHUB_TOKEN,
                owner=GITHUB_REPO_OWNER,
                repo=GITHUB_REPO_NAME,
            )
        log(f"[ok] created {len(chunks)} issue(s)")


def parse_args() -> argparse.Namespace:
    provider_default = (DEFAULT_PROVIDER or "openai").lower()

    parser = argparse.ArgumentParser(description="ChatArxiv v2")
    parser.add_argument("--provider", choices=["openai", "gemini"], default=provider_default)
    parser.add_argument("--model", default=None)
    parser.add_argument("--keywords", nargs="+", default=KEYWORD_LIST)
    parser.add_argument("--category", default=ARXIV_CATEGORY)
    parser.add_argument("--days-back", type=float, default=DAYS_BACK)
    parser.add_argument("--max-results", type=int, default=MAX_RESULTS)
    parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    parser.add_argument("--mode", choices=["generate", "create-issue", "all"], default="all")
    parser.add_argument("--output-dir", default="export")
    parser.add_argument("--file-format", default="md")
    parser.add_argument("--issue-chunk-size", type=int, default=30000)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    load_dotenv()
    run(parse_args())
