#!/usr/bin/env python3
"""
Fetch headlines for the After Hours news board.

Reads news/feeds.json, downloads each RSS or Atom feed, keeps the newest items,
and writes a JSON file in this shape:

  {"updated": "2026-11-20T05:00:00Z",
   "items": [{"source": "EIA", "title": "...", "url": "https://...", "published": "..."}]}

Rules
  - Python standard library only.
  - Headlines and links only. No article text.
  - If every feed fails, the old output file stays unchanged.

Usage: python news/fetch_news.py --out docs/news.json
"""
import argparse
import email.utils
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RSS1 = "{http://purl.org/rss/1.0/}"
DC = "{http://purl.org/dc/elements/1.1/}"
ATOM = "{http://www.w3.org/2005/Atom}"
UA = "KRM-After-Hours/1.0 (+https://kazirafsanmahboob.host.dartmouth.edu/)"


def parse_date(text):
    if not text:
        return None
    text = text.strip()
    try:
        d = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def read_feed(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        root = ET.fromstring(r.read())
    items = []
    for it in root.iter("item"):  # RSS 2.0
        items.append((it.findtext("title"), it.findtext("link"), parse_date(it.findtext("pubDate"))))
    for it in root.iter(RSS1 + "item"):
        items.append((it.findtext(RSS1 + "title"), it.findtext(RSS1 + "link"), parse_date(it.findtext(DC + "date"))))
    for it in root.iter(ATOM + "entry"):  # Atom
        link = it.find(ATOM + "link")
        href = link.get("href") if link is not None else None
        items.append((it.findtext(ATOM + "title"), href, parse_date(it.findtext(ATOM + "updated") or it.findtext(ATOM + "published"))))
    out = []
    for title, link, when in items:
        title = " ".join((title or "").split())
        link = (link or "").strip()
        if title and link.startswith("https://"):
            out.append({"title": title, "url": link, "published": when})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feeds", default=str(HERE / "feeds.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-items", type=int, default=16)
    ap.add_argument("--per-feed", type=int, default=4)
    args = ap.parse_args()

    feeds = json.loads(Path(args.feeds).read_text(encoding="utf-8"))["feeds"]
    collected, ok = [], 0
    for f in feeds:
        if not f.get("enabled", True):
            continue
        try:
            items = read_feed(f["url"])
            if not items:
                raise ValueError("no usable headlines")
            ok += 1
        except Exception as e:  # keep going if one feed fails
            print(f"warning: {f['source']} failed: {e}", file=sys.stderr)
            continue
        items.sort(key=lambda i: i["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        for i in items[: args.per_feed]:
            i["source"] = f["source"]
            i["topic"] = f["topic"]
            collected.append(i)

    if ok == 0:
        print("error: no feed could be read; output not changed", file=sys.stderr)
        return 1

    collected.sort(key=lambda i: i["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    items = [
        {"source": i["source"], "topic": i["topic"], "title": i["title"], "url": i["url"],
         "published": i["published"].strftime("%Y-%m-%dT%H:%M:%SZ") if i["published"] else None}
        for i in collected[: args.max_items]
    ]
    data = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "items": items}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(items)} items from {ok} feeds to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
