"""Builds unlogged.json for the Unlogged Texts site from the "<Brand> Unlogged Sessions <pay period>"
Google Docs (one text message per trainer, written for the exception logs).

It reads the docs in the shared "Unlogged Sessions" Drive folder, plus any doc IDs listed in
scripts/extra_docs.txt, through their public "Anyone with the link" views (no credentials). A doc
that isn't shared that way is skipped with a warning. Each trainer's cell number comes from the
ClubReady staff lists in the "Staff List" folder (newest list first, older ones fill gaps).
The output holds trainer names, clubs, trainer cell numbers and client names with session times,
as plain data: anyone with the site's link can read it.

Usage: python scripts/build_unlogged.py [output folder]
Needs: pip install xlrd openpyxl
"""
import html
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

# USAPT Data / Unlogged Sessions and USAPT Data / Staff List
FOLDER = "1I3494fPCOV43SBoOdkzGjQtSz75lYYC_"
STAFF_FOLDER = "1CzSqR5FYD6iz9ZpMldZpZjJTz6JvDwhB"
EXTRA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extra_docs.txt")
UA = {"User-Agent": "Mozilla/5.0 (drive-data)"}
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
TITLE_RE = re.compile(r"\b(GRIP|Elevate|Lighthouse)\b.*?Unlogged Sessions\s*[–—-]?\s*(.+)$", re.I)
HEAD_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<club>[^)]*)\)\s*,?\s*(?P<rest>.*)$")


def get(url, binary=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def list_folder(folder):
    """(id, title, href) for each file in a shared folder (and its subfolders)."""
    out, todo = [], [folder]
    while todo:
        page = get(f"https://drive.google.com/embeddedfolderview?id={todo.pop()}")
        for fid, href, title in re.findall(r'id="entry-([\w-]+)".*?href="([^"]+)".*?flip-entry-title">([^<]*)<', page, re.S):
            href = html.unescape(href)
            if "/drive/folders/" in href:
                todo.append(fid)
            else:
                out.append((fid, html.unescape(title).strip(), href))
    return out


def list_docs():
    return [(fid, title) for fid, title, href in list_folder(FOLDER) if "docs.google.com/document" in href]


# ---------- Trainer phone numbers (ClubReady staff lists) ----------
def words(s):
    return re.sub(r"[^a-z ]", "", re.sub(r"[.\-']", " ", str(s or "").lower())).split()


def phone(v):
    if isinstance(v, float):
        v = str(int(v))
    d = re.sub(r"\D", "", str(v or ""))
    if len(d) == 11 and d[0] == "1":
        d = d[1:]
    return d if len(d) == 10 else ""


def read_rows(fid, title):
    if len(fid) > 40:  # a Google Sheet
        data = get(f"https://docs.google.com/spreadsheets/d/{fid}/export?format=xlsx", binary=True)
    else:
        data = get(f"https://drive.usercontent.google.com/download?id={fid}&export=download", binary=True)
    if data[:2] == b"PK":
        import openpyxl
        ws = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True).worksheets[0]
        return [list(r) for r in ws.iter_rows(values_only=True)]
    if data[:4] == bytes.fromhex("d0cf11e0"):
        import xlrd
        sh = xlrd.open_workbook(file_contents=data).sheet_by_index(0)
        return [sh.row_values(i) for i in range(sh.nrows)]
    raise ValueError(f"{title}: not an Excel file (is it shared 'Anyone with the link'?)")


def staff_rows(rows):
    """ClubReady staff list rows -> [{first, last, club, terminated, phone}]."""
    head = next(i for i, r in enumerate(rows) if "FirstName" in [str(x).strip() for x in r])
    cols = {str(c).strip(): j for j, c in enumerate(rows[head])}
    out = []
    for r in rows[head + 1:]:
        g = lambda c: r[cols[c]] if c in cols and cols[c] < len(r) and r[cols[c]] is not None else ""
        first, last = str(g("FirstName")).strip(), str(g("LastName")).strip()
        if not first and not last:
            continue
        loc = str(g("Location"))
        out.append({"first": first, "last": last, "club": loc.split(" - ", 1)[1].strip() if " - " in loc else loc,
                    "terminated": "terminated" in str(g("Employee Type")).lower(),
                    "phone": phone(g("Cell Phone")) or phone(g("Home Phone"))})
    return out


def list_date(title):
    """'stafflist_11-16GRIP.xls' -> (11, 16); newest lists are tried first."""
    m = re.search(r"(\d{1,2})-(\d{1,2})(?:-(\d{4}))?", title)
    return (int(m.group(3) or 0), int(m.group(1)), int(m.group(2))) if m else (0, 0, 0)


def load_staff():
    """{brand: [staff list rows, newest list first]}"""
    staff = {}
    files = [(fid, t) for fid, t, _ in list_folder(STAFF_FOLDER) if re.search(r"staff", t, re.I)]
    now_year = datetime.now(timezone.utc).year
    files.sort(key=lambda f: (list_date(f[1])[0] or now_year, *list_date(f[1])[1:]), reverse=True)
    for fid, title in files:
        m = re.search(r"GRIP|Elevate|Lighthouse", title, re.I)
        if not m:
            continue
        brand = {"grip": "GRIP", "elevate": "Elevate", "lighthouse": "Lighthouse"}[m.group(0).lower()]
        try:
            rows = staff_rows(read_rows(fid, title))
        except Exception as e:  # noqa: BLE001 - one bad list shouldn't stop the build
            print(f"warning: skipped staff list {title}: {e}", file=sys.stderr)
            continue
        staff.setdefault(brand, []).append(rows)
        print(f"staff list {title}: {len(rows)} people")
    return staff


def find_phone(lists, name, club):
    """The trainer's number from the newest staff list that has one. Matches full name first,
    then first + last name; prefers current staff at the doc's club. Never guesses between two
    different people."""
    n = words(name)
    if not n:
        return ""
    clubs = [words(c) for c in re.split(r",|found under", club) if c.strip()]
    for rows in lists:
        cands = []
        for s in rows:
            f, l = words(s["first"]), words(s["last"])
            if not f or not l or not s["phone"]:
                continue
            if f + l == n or "".join(f + l) == "".join(n):
                rank = 3
            elif f[0] == n[0] and l[-1] == n[-1]:
                rank = 2
            elif f[0] == n[0] and l[0] in n[1:]:
                rank = 1
            else:
                continue
            here = any(set(c) & set(words(s["club"])) for c in clubs)
            cands.append(((rank, not s["terminated"], here), s["phone"]))
        if cands:
            best = max(k for k, _ in cands)
            nums = {p for k, p in cands if k == best}
            if len(nums) == 1:
                return nums.pop()
    return ""


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
    staff = load_staff()
    for d in docs:
        for t in d["trainers"]:
            t["phone"] = find_phone(staff.get(d["brand"], []), t["name"], t["club"])
        print(f"{d['brand']} {d['period']}: numbers for {sum(1 for t in d['trainers'] if t['phone'])} of {len(d['trainers'])} trainers")
    docs.sort(key=lambda d: (d["brand"], -d["sort"]))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "unlogged.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": now.isoformat(timespec="seconds"), "docs": docs, "skipped": skipped}, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
