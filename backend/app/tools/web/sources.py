"""Live information from the web: search results, news headlines and readable page text.

Everything returned here is untrusted text from the internet. Callers quote it to
the model as data to read, never as instructions, and only ever show or speak it.
"""
import asyncio
import html
import ipaddress
import re
import urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
_MAX_PAGE_BYTES = 1_500_000

_RESULT = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=<a[^>]+class="result__a"|$)', re.S
)
_SNIPPET = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.S)
_ITEM = re.compile(r"<item>(.*?)</item>", re.S)
_DROP_BLOCKS = re.compile(
    r"<(script|style|noscript|svg|nav|header|footer|aside|form|figure)\b.*?</\1>", re.S | re.I
)
_PARAGRAPH = re.compile(r"<(p|h1|h2|h3|li)\b[^>]*>(.*?)</\1>", re.S | re.I)


def _client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def plain(fragment: str) -> str:
    """HTML fragment -> single-line plain text."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment or ""))).strip()


def site_name(url: str) -> str:
    host = urllib.parse.urlparse(url).hostname or url
    return host[4:] if host.startswith("www.") else host


def is_public_url(url: str) -> bool:
    """Only fetch ordinary public web pages, never this computer or the local network."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""
    if parsed.scheme not in ("http", "https") or not host or host == "localhost" or host.endswith(".local"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return address.is_global


async def search(query: str, limit: int = 8) -> List[Dict[str, str]]:
    """DuckDuckGo results as {url, title, snippet}; empty when offline."""
    try:
        async with _client(8.0) as client:
            page = await client.post("https://html.duckduckgo.com/html/", data={"q": query})
    except Exception:
        return []
    results = []
    for href, title, rest in _RESULT.findall(page.text):
        url = _real_url(html.unescape(href))
        if not url.startswith(("http://", "https://")) or "duckduckgo.com/y.js" in url:
            continue  # ads
        snippet = _SNIPPET.search(rest)
        results.append({"url": url, "title": plain(title), "snippet": plain(snippet.group(1)) if snippet else ""})
        if len(results) >= limit:
            break
    return results


def _real_url(href: str) -> str:
    # DuckDuckGo wraps results as //duckduckgo.com/l/?uddg=<encoded target>
    parsed = urllib.parse.urlparse(href if "://" in href else f"https:{href}")
    target = urllib.parse.parse_qs(parsed.query).get("uddg")
    return target[0] if target else href


async def news(query: Optional[str] = None, country: str = "US", limit: int = 6) -> List[Dict[str, str]]:
    """Recent headlines (newest first) from Google News, for a topic or the top stories."""
    country = (country or "US").upper()
    params = {"hl": f"en-{country}", "gl": country, "ceid": f"{country}:en"}
    url = "https://news.google.com/rss"
    if query:
        url, params["q"] = "https://news.google.com/rss/search", query
    try:
        async with _client(8.0) as client:
            feed = (await client.get(url, params=params)).text
    except Exception:
        return []
    return parse_news(feed, limit)


def parse_news(feed: str, limit: int = 6) -> List[Dict[str, str]]:
    items = []
    for raw in _ITEM.findall(feed):
        title = _tag(raw, "title")
        source = _tag(raw, "source")
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        published = _parse_date(_tag(raw, "pubDate"))
        items.append({"title": title, "source": source, "url": _tag(raw, "link"),
                      "published": published.isoformat() if published else ""})
    items.sort(key=lambda item: item["published"], reverse=True)
    return items[:limit]


def _tag(raw: str, name: str) -> str:
    match = re.search(rf"<{name}\b[^>]*>(.*?)</{name}>", raw, re.S)
    if not match:
        return ""
    value = match.group(1).replace("<![CDATA[", "").replace("]]>", "")
    return plain(value)


def _parse_date(value: str) -> Optional[datetime]:
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


async def page_text(url: str, max_chars: int = 1500) -> str:
    """The readable paragraphs of a web page, trimmed; '' if it can't be fetched."""
    if not is_public_url(url):
        return ""
    try:
        async with _client(6.0) as client:
            async with client.stream("GET", url) as response:
                if response.status_code != 200 or "html" not in response.headers.get("content-type", ""):
                    return ""
                if not is_public_url(str(response.url)):
                    return ""  # redirected somewhere private
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > _MAX_PAGE_BYTES:
                        break
                text = body.decode(response.encoding or "utf-8", errors="replace")
    except Exception:
        return ""
    return readable_text(text, max_chars)


def readable_text(document: str, max_chars: int = 1500) -> str:
    body = _DROP_BLOCKS.sub(" ", document)
    parts: List[str] = []
    total = 0
    for _, fragment in _PARAGRAPH.findall(body):
        text = plain(fragment)
        if len(text) < 50 or text in parts:
            continue
        parts.append(text)
        total += len(text) + 1
        if total >= max_chars:
            break
    return "\n".join(parts)[:max_chars]


async def pages_text(urls: List[str], max_chars: int = 1500) -> List[str]:
    return list(await asyncio.gather(*(page_text(url, max_chars) for url in urls)))


def _terms(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


def relevant_passages(text: str, question: str, max_chars: int = 500) -> str:
    """The sentences of a page that share the most words with the question, in page order."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n", text) if len(s.strip()) > 30]
    wanted = _terms(question)
    scored = sorted(range(len(sentences)), key=lambda i: -len(wanted & _terms(sentences[i])))
    chosen, total = [], 0
    for i in scored:
        if total + len(sentences[i]) > max_chars or not wanted & _terms(sentences[i]):
            continue
        chosen.append(i)
        total += len(sentences[i]) + 1
    return " ".join(sentences[i] for i in sorted(chosen))
