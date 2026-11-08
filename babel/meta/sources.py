"""External metadata: cover art, synopsis, tags, status.

Sources, tried in the order given:

* ``openlibrary``  — free JSON API, good for published/translated novels. Works without a key.
* ``googlebooks``  — JSON API; set GOOGLE_BOOKS_API_KEY for reliable use (keyless use is throttled).
* ``royalroad`` / ``novelupdates`` — webnovel sites. Both sit behind bot protection and often
  refuse automated requests; when they do, BABEL says so instead of guessing.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; BABEL/2; self-hosted reader)"}
SOURCES = ("openlibrary", "googlebooks", "royalroad", "novelupdates")


class MetadataError(Exception):
    pass


@dataclass
class Metadata:
    source: str
    title: str
    url: str | None = None
    author: str | None = None
    description: str | None = None
    cover_url: str | None = None
    tags: list[str] = field(default_factory=list)
    status: str | None = None


def _client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(headers=UA, timeout=15, follow_redirects=True, transport=transport)


def _blocked(r: httpx.Response) -> bool:
    return r.status_code in (403, 503) or "just a moment" in r.text[:3000].lower()


def _similar(a: str, b: str) -> float:
    ta, tb = set(re.findall(r"\w+", a.lower())), set(re.findall(r"\w+", b.lower()))
    return len(ta & tb) / max(1, len(ta | tb))


def openlibrary(title: str, http: httpx.Client) -> Metadata | None:
    r = http.get("https://openlibrary.org/search.json",
                 params={"title": title, "limit": 5, "fields": "title,author_name,cover_i,key,subject"})
    if r.status_code != 200:
        raise MetadataError(f"openlibrary: HTTP {r.status_code}")
    docs = sorted(r.json().get("docs", []), key=lambda d: -_similar(title, d.get("title", "")))
    if not docs or _similar(title, docs[0].get("title", "")) < 0.3:
        return None
    d = docs[0]
    desc = None
    try:
        w = http.get(f"https://openlibrary.org{d['key']}.json").json()
        desc = w.get("description")
        desc = desc.get("value") if isinstance(desc, dict) else desc
    except (httpx.HTTPError, ValueError, KeyError):
        pass
    return Metadata(
        "openlibrary", d.get("title", title), f"https://openlibrary.org{d.get('key', '')}",
        author=", ".join(dict.fromkeys(d.get("author_name") or [])) or None, description=desc,
        cover_url=f"https://covers.openlibrary.org/b/id/{d['cover_i']}-L.jpg" if d.get("cover_i") else None,
        tags=(d.get("subject") or [])[:12],
    )


def googlebooks(title: str, http: httpx.Client) -> Metadata | None:
    params = {"q": f"intitle:{title}", "maxResults": 5}
    if os.getenv("GOOGLE_BOOKS_API_KEY"):
        params["key"] = os.environ["GOOGLE_BOOKS_API_KEY"]
    r = http.get("https://www.googleapis.com/books/v1/volumes", params=params)
    if r.status_code == 429:
        raise MetadataError("googlebooks: throttled — set GOOGLE_BOOKS_API_KEY")
    if r.status_code != 200:
        raise MetadataError(f"googlebooks: HTTP {r.status_code}")
    items = sorted(r.json().get("items", []), key=lambda i: -_similar(title, i["volumeInfo"].get("title", "")))
    if not items:
        return None
    v = items[0]["volumeInfo"]
    links = v.get("imageLinks") or {}
    cover = links.get("extraLarge") or links.get("large") or links.get("medium") or links.get("thumbnail")
    return Metadata("googlebooks", v.get("title", title), v.get("infoLink"), author=", ".join(v.get("authors") or []) or None,
                    description=v.get("description"), cover_url=cover.replace("http://", "https://") if cover else None,
                    tags=v.get("categories") or [])


def royalroad(title: str, http: httpx.Client) -> Metadata | None:
    r = http.get("https://www.royalroad.com/fictions/search", params={"title": title})
    if _blocked(r):
        raise MetadataError("royalroad: the site refused the request (bot protection)")
    s = BeautifulSoup(r.text, "lxml")
    best = max(s.select(".fiction-list-item h2 a"), key=lambda a: _similar(title, a.get_text()), default=None)
    if best is None:
        return None
    url = "https://www.royalroad.com" + best["href"]
    p = BeautifulSoup(http.get(url).text, "lxml")
    og = p.select_one("meta[property='og:image']")
    desc = p.select_one(".description")
    status = next((lbl.get_text(strip=True).lower() for lbl in p.select(".label")
                   if lbl.get_text(strip=True).upper() in ("ONGOING", "COMPLETED", "HIATUS", "STUB")), None)
    return Metadata("royalroad", best.get_text(strip=True), url,
                    author=(p.select_one(".fic-header h4 a") or p.select_one("h4 a") or BeautifulSoup("", "lxml")).get_text(strip=True) or None,
                    description=desc.get_text("\n", strip=True) if desc else None,
                    cover_url=og.get("content") if og else None,
                    tags=[a.get_text(strip=True) for a in p.select(".tags a")][:15], status=status)


def novelupdates(title: str, http: httpx.Client) -> Metadata | None:
    r = http.get("https://www.novelupdates.com/", params={"s": title, "post_type": "seriesplans"})
    if _blocked(r):
        raise MetadataError("novelupdates: the site refused the request (bot protection)")
    s = BeautifulSoup(r.text, "lxml")
    best = max(s.select(".search_title a"), key=lambda a: _similar(title, a.get_text()), default=None)
    if best is None:
        return None
    p = BeautifulSoup(http.get(best["href"]).text, "lxml")
    img = p.select_one(".seriesimg img")
    desc = p.select_one("#editdescription")
    status = p.select_one("#editstatus")
    return Metadata("novelupdates", (p.select_one(".seriestitlenu") or best).get_text(strip=True), best["href"],
                    author=", ".join(a.get_text(strip=True) for a in p.select("#showauthors a")) or None,
                    description=desc.get_text("\n", strip=True) if desc else None,
                    cover_url=img.get("src") if img else None,
                    tags=[a.get_text(strip=True) for a in p.select("#showtags a")][:15],
                    status=("completed" if status and "complete" in status.get_text().lower() else
                            "ongoing" if status else None))


_FETCHERS = {"openlibrary": openlibrary, "googlebooks": googlebooks, "royalroad": royalroad, "novelupdates": novelupdates}


def fetch(title: str, sources: list[str] | None = None, transport: httpx.BaseTransport | None = None) -> tuple[Metadata | None, list[str]]:
    """Try sources in order; return the first match and the reasons the others failed."""
    notes: list[str] = []
    with _client(transport) as http:
        for name in sources or list(SOURCES):
            fn = _FETCHERS.get(name)
            if fn is None:
                notes.append(f"{name}: unknown source")
                continue
            try:
                meta = fn(title, http)
            except MetadataError as e:
                notes.append(str(e))
                continue
            except httpx.HTTPError as e:
                notes.append(f"{name}: {e}")
                continue
            if meta:
                return meta, notes
            notes.append(f"{name}: no match")
    return None, notes


def download(url: str, transport: httpx.BaseTransport | None = None, limit: int = 8_000_000) -> bytes:
    with _client(transport) as http:
        r = http.get(url)
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
            raise MetadataError(f"cover download failed ({r.status_code})")
        if len(r.content) > limit:
            raise MetadataError("cover image too large")
        return r.content
