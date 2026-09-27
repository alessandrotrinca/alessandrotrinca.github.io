#!/usr/bin/env python3
"""
Regenerate data/publications.js from NASA ADS.

Why a script and not a fetch() in the browser: the ADS API needs a bearer
token on every request and does not send permissive CORS headers. Calling it
from page JavaScript would both fail and leak your token to anyone who views
source. So we call ADS here, write a static file, and the page loads that.

Usage
-----
    export ADS_TOKEN="your-token"          # https://ui.adsabs.harvard.edu/user/settings/token
    python tools/update_publications.py

Options
-------
    --orcid 0000-0002-1899-4360   author ORCID (default below)
    --out   data/publications.js  output path
    --dry   print a summary, write nothing

Anything you want to keep that ADS does not know about — a topic tag, a paper
still in prep — goes in MANUAL_TOPICS or EXTRA below and survives the sync.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

ORCID = "0000-0002-1899-4360"
SURNAME = "Trinca"
API = "https://api.adsabs.harvard.edu/v1/search/query"

FIELDS = ",".join([
    "bibcode", "title", "author", "year", "pub", "volume", "page",
    "citation_count", "doi", "identifier", "doctype", "property", "pubdate",
])

# Research-page tags, keyed by bibcode or arXiv id. ADS has no idea about
# these, so they are re-applied after every sync.
MANUAL_TOPICS = {
    "2022MNRAS.511..616T": ["seeds", "growth"],
    "2023MNRAS.519.4753T": ["seeds", "growth"],
    "2024MNRAS.529.3563T": ["galaxies", "growth"],
    "2412.14248": ["growth"],
    "2602.22305": ["growth"],
    "2605.00092": ["waves"],
}

# Papers ADS does not have yet (in prep, or submitted without a preprint).
EXTRA: list[dict] = []


# --------------------------------------------------------------------- ADS --

def ads_get(token: str, params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:400]
        sys.exit(f"ADS returned {exc.code}: {body}")
    except urllib.error.URLError as exc:
        sys.exit(f"Could not reach ADS: {exc.reason}")


def fetch_all(token: str, orcid: str) -> list[dict]:
    #query = f'orcid:"{orcid}"'
    query = f'author:"Trinca, Alessandro" AND citation_count:[1 TO *]'
    docs, start = [], 0
    while True:
        page = ads_get(token, {
            "q": query,
            "fl": FIELDS,
            "rows": 200,
            "start": start,
            "sort": "date desc",
        })
        batch = page["response"]["docs"]
        docs.extend(batch)
        start += len(batch)
        if start >= page["response"]["numFound"] or not batch:
            break
    return docs


# ---------------------------------------------------------------- shaping --

def short_name(full: str) -> str:
    """ADS gives 'Trinca, Alessandro'; we want 'A. Trinca'."""
    if "," not in full:
        return full.strip()
    last, first = [part.strip() for part in full.split(",", 1)]
    initials = " ".join(f"{tok[0]}." for tok in re.split(r"[\s.\-]+", first) if tok)
    return f"{initials} {last}".strip()


def author_position(authors: list[str]) -> int | str:
    for i, name in enumerate(authors):
        if SURNAME.lower() in name.lower():
            return i + 1 if i < 2 else "n"
    return "n"


def arxiv_id(doc: dict) -> str:
    for ident in doc.get("identifier", []):
        m = re.match(r"^arXiv:(.+)$", ident)
        if m:
            return m.group(1)
    return ""


def journal_ref(doc: dict) -> str:
    pub = (doc.get("pub") or "").replace("Monthly Notices of the Royal Astronomical Society", "MNRAS")
    pub = pub.replace("Astronomy and Astrophysics", "A&A").replace("The Astrophysical Journal", "ApJ")
    if "arXiv" in pub or not pub:
        return ""
    vol = doc.get("volume") or ""
    page = doc.get("page") or [""]
    page = page[0] if isinstance(page, list) else page
    return " ".join(part for part in [pub, f"{vol}," if vol else "", page] if part).strip().rstrip(",")


def status_of(doc: dict) -> str:
    props = doc.get("property", []) or []
    if "REFEREED" in props:
        return "refereed"
    if doc.get("doctype") == "eprint":
        return "preprint"
    return "preprint"


def shape(doc: dict) -> dict:
    authors = [short_name(a) for a in doc.get("author", [])]
    axv = arxiv_id(doc)
    bibcode = doc.get("bibcode", "")
    dois = doc.get("doi") or [""]
    return {
        "year": int(doc.get("year") or 0),
        "title": (doc.get("title") or [""])[0],
        "authors": authors,
        "ref": journal_ref(doc),
        "status": status_of(doc),
        "pos": author_position(authors),
        "cites": int(doc.get("citation_count") or 0),
        "bibcode": bibcode,
        "arxiv": axv,
        "doi": dois[0],
        "topics": MANUAL_TOPICS.get(bibcode) or MANUAL_TOPICS.get(axv) or [],
    }


def h_index(counts: list[int]) -> int:
    h = 0
    for i, c in enumerate(sorted(counts, reverse=True), start=1):
        if c >= i:
            h = i
    return h


# ---------------------------------------------------------------- writing --

HEADER = """\
/* AUTO-GENERATED by tools/update_publications.py on {stamp}.
   Do not hand-edit — your changes will be overwritten on the next sync.
   Add topic tags in MANUAL_TOPICS and unpublished work in EXTRA instead. */

window.SITE_DATA = """


def write(path: str, payload: dict) -> None:
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(HEADER.format(stamp=date.today().isoformat()))
        fh.write(body)
        fh.write(";\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orcid", default=ORCID)
    ap.add_argument("--out", default="data/publications.js")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("ADS_TOKEN")
    if not token:
        sys.exit("Set ADS_TOKEN first — get one at https://ui.adsabs.harvard.edu/user/settings/token")

    docs = fetch_all(token, args.orcid)
    pubs = [shape(d) for d in docs] + EXTRA
    pubs.sort(key=lambda p: (-p["year"], 0 if p["pos"] == 1 else 1, p["title"]))

    refereed = [p for p in pubs if p["status"] == "refereed"]
    payload = {
        "metrics": {
            "updated": date.today().isoformat(),
            "citations": sum(p["cites"] or 0 for p in pubs),
            "hindex": h_index([p["cites"] or 0 for p in pubs]),
        },
        "me": f"A. {SURNAME}",
        "publications": pubs,
    }

    print(f"{len(pubs)} papers · {len(refereed)} refereed · "
          f"{sum(1 for p in pubs if p['pos'] == 1)} first-author · "
          f"{payload['metrics']['citations']} citations · h = {payload['metrics']['hindex']}")

    if args.dry:
        print("--dry: nothing written")
        return

    write(args.out, payload)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
