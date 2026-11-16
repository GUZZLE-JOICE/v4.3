"""Resilient, key-free public research for JARVIS.

This module deliberately uses documented public APIs and feeds instead of
driving search-result pages.  That avoids CAPTCHA loops without attempting to
solve, hide, or bypass a site's bot checks.  Every source is optional: one
failing provider never prevents the remaining providers from returning useful
material.
"""

from __future__ import annotations

import concurrent.futures
import html
import json
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable


MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_QUERY_CHARS = 240
MAX_EXCERPT_CHARS = 1_100
CACHE_SECONDS = 30 * 60


def _one_line(value: Any, limit: int = MAX_EXCERPT_CHARS) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _query(value: Any) -> str:
    text = re.sub(r"\bsite:[^\s]+", " ", str(value or ""), flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_QUERY_CHARS] or "useful practical knowledge"


def _url(base: str, params: dict[str, Any]) -> str:
    return base + ("&" if "?" in base else "?") + urllib.parse.urlencode(params, doseq=True)


class ResearchEngine:
    """Aggregate low-volume research from public, no-key sources."""

    def __init__(self, data_dir: str | Path, *, timeout: float = 7.0) -> None:
        self.data_dir = Path(data_dir)
        self.timeout = max(2.0, min(15.0, float(timeout)))
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._health: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._network_slots = threading.BoundedSemaphore(12)
        self._brave_key = ""
        self._providers: tuple[tuple[str, Callable[[str], list[dict[str, str]]]], ...] = (
            ("DuckDuckGo", self._duckduckgo),
            ("Wikipedia", self._wikipedia),
            ("Hacker News", self._hacker_news),
            ("Stack Exchange", self._stack_exchange),
            ("Crossref", self._crossref),
            ("arXiv", self._arxiv),
            ("Open Library", self._open_library),
            ("GitHub", self._github),
            ("npm", self._npm),
        )

    # General web engines are listed first in results; reference sources follow.
    WEB_ENGINES = ("Brave Search", "DuckDuckGo")

    def set_brave_key(self, key: Any) -> None:
        """Enable the official Brave Search API when the user supplies a key."""
        clean = re.sub(r"\s+", "", str(key or ""))[:200]
        with self._lock:
            if clean != self._brave_key:
                self._brave_key = clean
                self._cache.clear()

    @property
    def brave_configured(self) -> bool:
        return bool(self._brave_key)

    def _active_providers(self) -> tuple[tuple[str, Callable[[str], list[dict[str, str]]]], ...]:
        if self._brave_key:
            return (("Brave Search", self._brave),) + tuple(self._providers)
        return tuple(self._providers)

    @property
    def source_names(self) -> list[str]:
        return [name for name, _ in self._active_providers()]

    def _duckduckgo(self, query: str) -> list[dict[str, str]]:
        """DuckDuckGo Instant Answer API: documented, key-free, never a CAPTCHA page."""
        data = self._json(_url(
            "https://api.duckduckgo.com/",
            {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1, "no_redirect": 1, "t": "jarvis"},
        ))
        results: list[dict[str, str]] = []
        heading = data.get("Heading") or query
        answer = data.get("Answer") if isinstance(data.get("Answer"), str) else ""
        summary = answer or data.get("AbstractText") or data.get("Definition") or ""
        if summary:
            item = self._item("DuckDuckGo", heading, summary, data.get("AbstractURL") or data.get("DefinitionURL") or "")
            if item:
                results.append(item)

        def add_topic(topic: Any) -> None:
            if not isinstance(topic, dict):
                return
            if isinstance(topic.get("Topics"), list):
                for child in topic["Topics"]:
                    add_topic(child)
                return
            text = str(topic.get("Text") or "")
            item = self._item("DuckDuckGo", text.split(" - ")[0][:120], text, topic.get("FirstURL"))
            if item:
                results.append(item)

        for row in (data.get("Results") or []) + (data.get("RelatedTopics") or []):
            add_topic(row)
        return results[:5]

    def _brave(self, query: str) -> list[dict[str, str]]:
        """Official Brave Search API (built for assistants, so it is never bot-blocked)."""
        request = urllib.request.Request(
            _url("https://api.search.brave.com/res/v1/web/search", {"q": query, "count": 6}),
            headers={"Accept": "application/json", "X-Subscription-Token": self._brave_key},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read(MAX_RESPONSE_BYTES).decode("utf-8", errors="replace") or "{}")
        results: list[dict[str, str]] = []
        for row in ((data.get("web") or {}).get("results") or []) if isinstance(data, dict) else []:
            if not isinstance(row, dict):
                continue
            item = self._item("Brave Search", row.get("title"), row.get("description"), row.get("url"))
            if item:
                results.append(item)
        return results

    def top_web_result(self, query: Any) -> str:
        """Best http(s) link from the API engines; used when a results page is blocked."""
        clean = _query(query)
        for name, provider in self._active_providers():
            if name not in self.WEB_ENGINES and name != "Wikipedia":
                continue
            try:
                for item in provider(clean):
                    target = str(item.get("url") or "")
                    if re.match(r"^https?://", target, re.I) and "duckduckgo.com" not in target:
                        return target
            except Exception:
                continue
        return ""

    def health(self) -> dict[str, Any]:
        with self._lock:
            sources = {name: dict(self._health.get(name, {"status": "not_checked"})) for name in self.source_names}
        return {"ok": True, "source_count": len(sources), "sources": sources, "brave_configured": self.brave_configured}

    def _fetch(self, url: str, *, accept: str = "application/json") -> bytes:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "JARVIS/4.3 (personal research workspace; key-free public APIs)",
                "Accept": accept,
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            if int(getattr(response, "status", 200)) != 200:
                raise RuntimeError(f"HTTP {getattr(response, 'status', 'error')}")
            return response.read(MAX_RESPONSE_BYTES)

    def _json(self, url: str) -> dict[str, Any]:
        value = json.loads(self._fetch(url).decode("utf-8", errors="replace") or "{}")
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _item(source: str, title: Any, excerpt: Any, url: Any) -> dict[str, str] | None:
        clean_title = _one_line(title, 240)
        clean_excerpt = _one_line(excerpt)
        clean_url = str(url or "").strip()
        if not clean_title or not (clean_excerpt or clean_url):
            return None
        return {"source": source, "title": clean_title, "excerpt": clean_excerpt, "url": clean_url}

    def _wikipedia(self, query: str) -> list[dict[str, str]]:
        endpoint = _url(
            "https://en.wikipedia.org/w/api.php",
            {
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrlimit": 5,
                "prop": "extracts|info",
                "exintro": 1,
                "explaintext": 1,
                "exsentences": 4,
                "inprop": "url",
                "format": "json",
                "formatversion": 2,
                "origin": "*",
            },
        )
        pages = ((self._json(endpoint).get("query") or {}).get("pages") or [])
        results: list[dict[str, str]] = []
        for page in pages if isinstance(pages, list) else []:
            if not isinstance(page, dict):
                continue
            item = self._item("Wikipedia", page.get("title"), page.get("extract"), page.get("fullurl"))
            if item:
                results.append(item)
        return results

    def _hacker_news(self, query: str) -> list[dict[str, str]]:
        data = self._json(_url("https://hn.algolia.com/api/v1/search", {"query": query, "tags": "story", "hitsPerPage": 5}))
        results: list[dict[str, str]] = []
        for hit in data.get("hits") or []:
            if not isinstance(hit, dict):
                continue
            object_id = hit.get("objectID")
            target = hit.get("url") or (f"https://news.ycombinator.com/item?id={object_id}" if object_id else "")
            excerpt = f"{hit.get('points') or 0} points · {hit.get('num_comments') or 0} comments · {hit.get('created_at') or ''}"
            item = self._item("Hacker News", hit.get("title") or hit.get("story_title"), excerpt, target)
            if item:
                results.append(item)
        return results

    def _stack_exchange(self, query: str) -> list[dict[str, str]]:
        endpoint = _url(
            "https://api.stackexchange.com/2.3/search/advanced",
            {"q": query, "site": "stackoverflow", "order": "desc", "sort": "relevance", "pagesize": 5, "filter": "withbody"},
        )
        results: list[dict[str, str]] = []
        for row in self._json(endpoint).get("items") or []:
            if not isinstance(row, dict):
                continue
            excerpt = row.get("body") or f"Score {row.get('score') or 0} · {row.get('answer_count') or 0} answers"
            item = self._item("Stack Exchange", row.get("title"), excerpt, row.get("link"))
            if item:
                results.append(item)
        return results

    def _crossref(self, query: str) -> list[dict[str, str]]:
        endpoint = _url(
            "https://api.crossref.org/works",
            {"query": query, "rows": 5, "select": "DOI,title,abstract,URL,published,author,container-title"},
        )
        rows = ((self._json(endpoint).get("message") or {}).get("items") or [])
        results: list[dict[str, str]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = (row.get("title") or [""])[0]
            authors = []
            for author in (row.get("author") or [])[:4]:
                if isinstance(author, dict):
                    authors.append(" ".join(filter(None, [str(author.get("given") or ""), str(author.get("family") or "")])).strip())
            excerpt = row.get("abstract") or ("Authors: " + ", ".join(filter(None, authors)))
            item = self._item("Crossref", title, excerpt, row.get("URL"))
            if item:
                results.append(item)
        return results

    def _arxiv(self, query: str) -> list[dict[str, str]]:
        endpoint = _url(
            "https://export.arxiv.org/api/query",
            {"search_query": "all:" + query, "start": 0, "max_results": 5, "sortBy": "relevance", "sortOrder": "descending"},
        )
        root = ET.fromstring(self._fetch(endpoint, accept="application/atom+xml"))
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        results: list[dict[str, str]] = []
        for entry in root.findall("atom:entry", namespace):
            item = self._item(
                "arXiv",
                entry.findtext("atom:title", default="", namespaces=namespace),
                entry.findtext("atom:summary", default="", namespaces=namespace),
                entry.findtext("atom:id", default="", namespaces=namespace),
            )
            if item:
                results.append(item)
        return results

    def _open_library(self, query: str) -> list[dict[str, str]]:
        endpoint = _url(
            "https://openlibrary.org/search.json",
            {"q": query, "limit": 5, "fields": "key,title,author_name,first_publish_year,subject"},
        )
        results: list[dict[str, str]] = []
        for row in self._json(endpoint).get("docs") or []:
            if not isinstance(row, dict):
                continue
            authors = ", ".join(str(x) for x in (row.get("author_name") or [])[:4])
            subjects = ", ".join(str(x) for x in (row.get("subject") or [])[:6])
            excerpt = " · ".join(filter(None, [authors, str(row.get("first_publish_year") or ""), subjects]))
            key = str(row.get("key") or "")
            item = self._item("Open Library", row.get("title"), excerpt, "https://openlibrary.org" + key if key.startswith("/") else "")
            if item:
                results.append(item)
        return results

    def _github(self, query: str) -> list[dict[str, str]]:
        endpoint = _url("https://api.github.com/search/repositories", {"q": query, "sort": "stars", "order": "desc", "per_page": 5})
        results: list[dict[str, str]] = []
        for row in self._json(endpoint).get("items") or []:
            if not isinstance(row, dict):
                continue
            excerpt = f"{row.get('description') or ''} · {row.get('stargazers_count') or 0} stars · {row.get('language') or 'mixed'}"
            item = self._item("GitHub", row.get("full_name"), excerpt, row.get("html_url"))
            if item:
                results.append(item)
        return results

    def _npm(self, query: str) -> list[dict[str, str]]:
        endpoint = _url("https://registry.npmjs.org/-/v1/search", {"text": query, "size": 5})
        results: list[dict[str, str]] = []
        for row in self._json(endpoint).get("objects") or []:
            package = row.get("package") if isinstance(row, dict) else None
            if not isinstance(package, dict):
                continue
            links = package.get("links") if isinstance(package.get("links"), dict) else {}
            item = self._item("npm", package.get("name"), package.get("description"), links.get("npm"))
            if item:
                results.append(item)
        return results

    def research(self, query: Any, label: Any = "", *, force: bool = False) -> dict[str, Any]:
        clean = _query(query)
        cache_key = clean.casefold()
        now = time.time()
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached and not force and now - cached[0] < CACHE_SECONDS:
                result = dict(cached[1])
                result["cached"] = True
                return result

        collected: list[dict[str, str]] = []
        failures: list[dict[str, str]] = []

        def run_provider(name: str, provider: Callable[[str], list[dict[str, str]]]) -> tuple[str, list[dict[str, str]], str]:
            started = time.monotonic()
            try:
                with self._network_slots:
                    rows = provider(clean)
                elapsed = round((time.monotonic() - started) * 1000)
                with self._lock:
                    self._health[name] = {"status": "ready", "last_success": int(time.time()), "elapsed_ms": elapsed, "results": len(rows)}
                return name, rows, ""
            except Exception as exc:  # A provider failure is intentionally isolated.
                message = _one_line(exc, 260) or "Source unavailable"
                with self._lock:
                    self._health[name] = {"status": "unavailable", "last_error": message, "checked": int(time.time())}
                return name, [], message

        with concurrent.futures.ThreadPoolExecutor(max_workers=10, thread_name_prefix="jarvis-research") as pool:
            futures = [pool.submit(run_provider, name, provider) for name, provider in self._active_providers()]
            for future in concurrent.futures.as_completed(futures):
                name, rows, error = future.result()
                if error:
                    failures.append({"source": name, "error": error})
                else:
                    collected.extend(rows[:5])

        # Real web-search engines lead; the stable sort keeps the rest in arrival order.
        collected.sort(key=lambda row: 0 if row.get("source") in self.WEB_ENGINES else 1)
        unique: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in collected:
            marker = re.sub(r"[^a-z0-9]", "", item.get("title", "").casefold())[:120]
            if not marker or marker in seen:
                continue
            seen.add(marker)
            unique.append(item)

        if not unique:
            message = "No public source returned a readable result. Check the internet connection and try a more specific topic."
            return {"ok": False, "error": message, "query": clean, "failures": failures, "source_health": self.health()["sources"]}

        chosen = unique[:18]
        source_names = list(dict.fromkeys(item["source"] for item in chosen))
        lines = [f"Research topic: {clean}", f"Sources reached: {', '.join(source_names)}", ""]
        for item in chosen:
            lines.append(f"[{item['source']}] {item['title']}")
            if item.get("excerpt"):
                lines.append(item["excerpt"])
            if item.get("url"):
                lines.append(item["url"])
            lines.append("")
        result = {
            "ok": True,
            "query": clean,
            "label": _one_line(label, 160),
            "title": f"Multi-source research · {clean}",
            "text": "\n".join(lines).strip(),
            "url": chosen[0].get("url", ""),
            "source": "MULTI-SOURCE PUBLIC RESEARCH",
            "sources": chosen,
            "source_names": source_names,
            "source_count": len(source_names),
            "result_count": len(chosen),
            "failures": failures,
            "cached": False,
            "finished_at": int(time.time()),
        }
        with self._lock:
            self._cache[cache_key] = (now, dict(result))
            if len(self._cache) > 80:
                oldest = sorted(self._cache.items(), key=lambda item: item[1][0])[:20]
                for key, _ in oldest:
                    self._cache.pop(key, None)
        return result
