"""Builds unlogged.json for the Unlogged Texts site from the "<Brand> Unlogged Sessions <pay period>"
Google Docs (one text message per trainer, written for the exception logs).

It reads the docs in the shared "Unlogged Sessions" Drive folder, plus any doc IDs listed in
scripts/extra_docs.txt, through their public "Anyone with the link" views (no credentials). A doc
that isn't shared that way is skipped with a warning. The output holds trainer names, clubs and
client names with session times, as plain data: anyone with the site's link can read it.

Usage: python scripts/build_unlogged.py [output folder]
"""
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

# USAPT Data / Unlogged Sessions
FOLDER = "1I3494fPCOV43SBoOdkzGjQtSz75lYYC_"
EXTRA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extra_docs.txt")
UA = {"User-Agent": "Mozilla/5.0 (drive-data)"}
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
TITLE_RE = re.compile(r"\b(GRIP|Elevate|Lighthouse)\b.*?Unlogged Sessions\s*[–—-]?\s*(.+)$", re.I)
HEAD_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<club>[^)]*)\)\s*,?\s*(?P<rest>.*)$")


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read().decode("utf-8", "replace")


def list_docs():
    """(id, title) for each Google Doc in the folder (and its subfolders)."""
    out, todo = [], [FOLDER]
    while todo:
        page = get(f"https://drive.google.com/embeddedfolderview?id={todo.pop()}")
        for fid, href, title in re.findall(r'id="entry-([\w-]+)".*?href="([^"]+)".*?flip-entry-title">([^<]*)<', page, re.S):
            href = html.unescape(href)
            if "/drive/folders/" in href:
                todo.append(fid)
            elif "docs.google.com/document" in href:
                out.append((fid, html.unescape(title).strip()))
    return out


def extra_docs():
    if not os.path.exists(EXTRA):
        return []
    ids = []
    for line in open(EXTRA, encoding="utf-8"):
        line = line.split("#", 1)[0].strip()
        m = re.search(r"/d/([\w-]{20,})", line) or re.fullmatch(r"([\w-]{20,})", line)
        if m:
            ids.append((m.group(1), ""))
    return ids


def clean(line):
    """One line of an exported doc, without Markdown marks or escapes."""
    line = line.strip().lstrip("#").strip()
    line = line.replace("**", "").replace("__", "")
    line = re.sub(r"\\([\\!_*#.\-()\[\]+`~>|])", r"\1", line)
    return line.strip()


def parse_period(text):
    """'Nov 1–15' -> sort key (month, start day) or None."""
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s*(\d{1,2})", text)
    if not m or m.group(1).lower() not in MONTHS:
        return None
    return MONTHS.index(m.group(1).lower()) + 1, int(m.group(2))


def parse_doc(raw, fallback_title=""):
    raw = raw.replace("﻿", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [l for l in (clean(x) for x in raw.split("\n")) if l]
    if not lines:
        return None
    title = lines[0]
    m = TITLE_RE.search(title) or TITLE_RE.search(fallback_title)
    if not m:
        return None
    brand = {"grip": "GRIP", "elevate": "Elevate", "lighthouse": "Lighthouse"}[m.group(1).lower()]
    period = re.sub(r"\s*-\s*", "–", m.group(2).strip())  # "Nov 1-15" -> "Nov 1–15"

    trainers, needs, intro = [], [], ""
    needs_at = next((i for i, l in enumerate(lines) if re.fullmatch(r"needs a look:?", l, re.I)), len(lines))
    i = 1
    while i < needs_at:
        line = lines[i]
        if not line.startswith("Hi "):
            i += 1
            continue
        heading = lines[i - 1] if i > 1 else ""
        end = next((j for j in range(i + 1, needs_at) if re.match(r"(Did |Thank you)", lines[j])), None)
        if end is None:
            i += 1
            continue
        h = HEAD_RE.match(heading)
        name, club, rest = (h.group("name"), h.group("club"), h.group("rest")) if h else (heading, "", "")
        note = ""
        if " - " in f" {rest} " or rest.endswith("-"):
            rest, _, note = rest.partition("-")
            rest, note = rest.strip(" ,"), note.strip(" -")
        sessions = lines[i + 1:end]
        trainers.append({
            "name": name.strip(),
            "club": club.strip(),
            "label": rest.strip(" ,"),
            "note": note,
            "sessions": len(sessions),
            "message": line + "\n\n" + "\n".join(sessions) + "\n\n" + lines[end],
        })
        i = end + 1
    if trainers:
        first_head = lines.index(next(l for l in lines if l.startswith("Hi "))) - 1
        intro = " ".join(lines[1:first_head])
    needs = lines[needs_at + 1:]
    return {"brand": brand, "period": period, "title": title, "intro": intro, "trainers": trainers, "needsLook": needs}


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    now = datetime.now(timezone.utc)
    docs, seen, skipped = [], set(), []
    for fid, title in list_docs() + extra_docs():
        if fid in seen or (title and not re.search(r"unlogged", title, re.I)):
            continue
        seen.add(fid)
        try:
            raw = get(f"https://docs.google.com/document/d/{fid}/export?format=txt")
        except urllib.error.HTTPError as e:
            print(f"warning: skipped {title or fid}: HTTP {e.code} (is it shared 'Anyone with the link'?)", file=sys.stderr)
            skipped.append(title or fid)
            continue
        if raw.lstrip().startswith("<"):
            print(f"warning: skipped {title or fid}: not readable without sign-in", file=sys.stderr)
            skipped.append(title or fid)
            continue
        doc = parse_doc(raw, title)
        if not doc or not doc["trainers"]:
            print(f"warning: skipped {title or fid}: no trainer messages found", file=sys.stderr)
            skipped.append(title or fid)
            continue
        key = parse_period(doc["period"])
        year = now.year - (1 if key and key[0] > now.month + 1 else 0)
        doc["sort"] = (year * 10000 + key[0] * 100 + key[1]) if key else 0
        doc["id"] = f"{doc['brand']}-{doc['sort']}-{fid[:6]}"
        doc["docUrl"] = f"https://docs.google.com/document/d/{fid}/edit"
        docs.append(doc)
        print(f"{doc['brand']} {doc['period']}: {len(doc['trainers'])} trainers")
    if not docs:
        sys.exit("No unlogged session docs could be read")
    docs.sort(key=lambda d: (d["brand"], -d["sort"]))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "unlogged.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": now.isoformat(timespec="seconds"), "docs": docs, "skipped": skipped}, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
