from __future__ import annotations

from typing import List

import requests


def split_text_into_chunks(text: str, max_chunk_size: int = 30000) -> List[str]:
    if max_chunk_size <= 0:
        raise ValueError("max_chunk_size must be positive")

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chunk_size, len(text))
        if end < len(text):
            newline = text.rfind("\n", start, end)
            if newline > start:
                end = newline
        chunks.append(text[start:end])
        start = end
    return chunks


def create_issue(
    title: str,
    body: str,
    labels: List[str],
    token: str,
    owner: str,
    repo: str,
) -> dict:
    if not token:
        raise RuntimeError("GITHUB_TOKEN (or TOKEN) is missing.")

    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "title": title,
        "body": body,
        "labels": labels,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code != 201:
        raise RuntimeError(f"Failed to create issue: {resp.status_code} {resp.text}")

    data = resp.json()
    print(f"[ok] issue created: #{data.get('number')} {data.get('html_url')}")
    return data
