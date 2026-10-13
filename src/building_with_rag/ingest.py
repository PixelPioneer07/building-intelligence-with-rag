"""Story 2.1: turn the BNS and IPC bare-act PDFs into section-level JSONL files.

Run with ``uv run python -m building_with_rag.ingest``. Extraction only: no database,
embeddings, chunking or retrieval happens here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

PARSER = "pymupdf"
PARSER_VERSION = pymupdf.__version__

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
OUT_DIR = REPO_ROOT / "data" / "processed"
PROVENANCE = "PROVENANCE.md"

REQUIRED_FIELDS = (
    "section_id",
    "act",
    "act_label",
    "status",
    "chapter",
    "chapter_title",
    "section_number",
    "heading",
    "text",
    "source_pdf",
    "source_sha256",
    "parser",
    "parser_version",
    "source_status_version",
    "needs_review",
)
NULLABLE_FIELDS = {
    "act_label",
    "chapter",
    "chapter_title",
    "heading",
    "source_status_version",
}

MIN_TEXT_CHARS = 30
PAGE_CENTRE = 297.6  # BNS pages are A4 (595 pt wide)

CHAPTER_RE = re.compile(r"^CHAPTER\s+([IVXLC]+)(?:[\s-]*([A-Z]))?$")
PARA_START_RE = re.compile(
    r"^(?:\d+\*\[)?(?:\([0-9A-Za-z]{1,5}\)|Explanations?\b|Illustrations?\b|Provided\b"
    r"|Exceptions?\b)"
)
FOOTNOTE_START_RE = re.compile(
    r"^(?:Subs\.|Ins\.|Rep\.|Omitted|Added|The |Clause|Cl\.|Sub-|Paragraph|Re-|Renumbered"
    r"|See |Section|Now |Word|Expl)"
)


@dataclass(frozen=True)
class ActSpec:
    key: str  # "bns" / "ipc"
    act: str
    status: str
    pdf: str
    output: str
    label_pattern: str


ACTS = (
    ActSpec("bns", "BNS_2023", "in_force", "BNS_2023_bare_act.pdf", "bns_sections.jsonl",
            "Bharatiya Nyaya Sanhita, 2023"),
    ActSpec("ipc", "IPC_1860", "repealed", "IPC_1860_bare_act.pdf", "ipc_sections.jsonl",
            "Indian Penal Code, 1860"),
)


@dataclass
class Line:
    text: str
    page: int
    x0: float = 0.0
    x1: float = 0.0
    bold: bool = False
    number: str | None = None  # bold section number prefix (BNS only)


@dataclass
class Section:
    number: str  # "103", "304A"
    heading: str | None
    chapter: str | None
    chapter_title: str | None
    lines: list[str] = field(default_factory=list)
    page_start: int = 0
    page_end: int = 0
    reasons: list[str] = field(default_factory=list)
    body_number: str | None = None


@dataclass
class ParseResult:
    sections: list[Section]
    notes: list[str]  # run-level observations (empty pages, skipped regions)
    empty_pages: list[int]
    skipped_numbers: set[int] = field(default_factory=set)  # printed gaps (repealed runs)


# ---------------------------------------------------------------- text helpers


def clean_text(s: str) -> str:
    s = s.replace("\u00ad", "").replace("\u00a0", " ").replace("\u200b", "")
    return re.sub(r"[ \t]+", " ", s).strip()


def join_lines(lines: list[str]) -> str:
    """Join wrapped lines. A trailing hyphen keeps its hyphen and loses the space, so a
    real hyphenated word ("extra-territorial") is never altered."""
    out = ""
    for line in lines:
        if not out:
            out = line
        elif out.endswith("-"):
            out += line
        else:
            out += " " + line
    return out


def build_paragraphs(lines: list[str]) -> str:
    paras: list[list[str]] = []
    for line in lines:
        if not paras or PARA_START_RE.match(line):
            paras.append([line])
        else:
            paras[-1].append(line)
    return "\n".join(join_lines(p) for p in paras)


def roman_to_int(s: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    for i, ch in enumerate(s):
        v = vals[ch]
        total += -v if i + 1 < len(s) and vals[s[i + 1]] > v else v
    return total


def split_number(num: str) -> tuple[int, str]:
    m = re.fullmatch(r"(\d+)([A-Z]*)", num)
    assert m
    return int(m.group(1)), m.group(2)


# ---------------------------------------------------------------- BNS parsing


def bns_lines(doc: pymupdf.Document) -> tuple[list[Line], list[str], list[int]]:
    """Return body lines of the BNS PDF (index and correspondence table excluded)."""
    start = None
    for i, page in enumerate(doc):
        header = [
            b for b in page.get_text("blocks") if b[1] < 90 and "Chapters and Sections" in b[4]
        ]
        if header and i > 1:
            start = i
            break
    if start is None:
        raise RuntimeError("BNS body start ('Chapters and Sections' header) not found")
    notes = [
        "BNS: skipped PDF pages 1-" + str(start) + " (cover, index and BNS-to-IPC "
        "correspondence table); section text starts at PDF page " + str(start + 1)
    ]
    lines: list[Line] = []
    empty: list[int] = []
    for i in range(start, len(doc)):
        page = doc[i]
        if not page.get_text().strip():
            empty.append(i + 1)
            continue
        for block in page.get_text("dict")["blocks"]:
            for ln in block.get("lines", []):
                if ln["bbox"][1] < 65:  # running header (HomePage link etc.)
                    continue
                spans = [s for s in ln["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = clean_text("".join(s["text"] for s in ln["spans"]))
                if text in {"HomePage", "Chapters and Sections"} or not text:
                    continue
                bold = all("Bold" in s["font"] or s["flags"] & 16 for s in spans)
                number = None
                first = spans[0]
                m = re.match(r"(\d+)\.", text)
                if (first["flags"] & 16 or "Bold" in first["font"]) and m and (
                    first["text"].strip().startswith(m.group(1))
                ):
                    number = m.group(1)
                    text = clean_text(text[m.end():])
                lines.append(Line(text, i + 1, ln["bbox"][0], ln["bbox"][2], bold, number))
    return lines, notes, empty


def parse_bns(doc: pymupdf.Document) -> ParseResult:
    lines, notes, empty = bns_lines(doc)
    sections: list[Section] = []
    chapter = chapter_title = None
    heading_parts: list[str] = []
    sub_heading: str | None = None
    current: Section | None = None
    i = 0
    while i < len(lines):
        ln = lines[i]
        i += 1
        if ln.text.startswith("Note: For Reference only") or set(ln.text) <= set("—-– "):
            continue
        centred = ln.x0 > 120 and abs((ln.x0 + ln.x1) / 2 - PAGE_CENTRE) < 25
        m = CHAPTER_RE.match(ln.text) if ln.bold else None
        if m:
            chapter = m.group(1) + (m.group(2) or "")
            title_parts: list[str] = []
            while i < len(lines) and lines[i].bold and lines[i].x0 > 120 and lines[i].text.isupper():
                title_parts.append(lines[i].text)
                i += 1
            chapter_title = join_lines(title_parts) or None
            heading_parts = []
            sub_heading = None
            continue
        if ln.number is not None:
            heading = join_lines(heading_parts) or sub_heading or None
            current = Section(ln.number, heading, chapter, chapter_title,
                              [ln.text] if ln.text else [], ln.page, ln.page)
            if heading is None:
                current.reasons.append("missing heading")
            sections.append(current)
            heading_parts = []
            sub_heading = None
            continue
        if ln.bold and not centred:
            heading_parts.append(ln.text)
            continue
        if ln.bold and centred:
            sub_heading = ln.text  # sub-chapter heading such as "Of abetment", not section text
            continue
        if current is not None:
            current.lines.append(ln.text)
            current.page_end = ln.page
    return ParseResult(sections, notes, empty)


# ---------------------------------------------------------------- IPC parsing


def ipc_lines(doc: pymupdf.Document) -> tuple[list[Line], list[int]]:
    lines: list[Line] = []
    empty: list[int] = []
    for i, page in enumerate(doc):
        raw = [clean_text(x) for x in page.get_text().splitlines()]
        raw = [x for x in raw if x]
        if not raw:
            empty.append(i + 1)
            continue
        raw = [x for x in raw if not re.fullmatch(r"-{5,}", x) and not re.fullmatch(r"\d{1,3}", x)]
        out: list[str] = []
        j = 0
        while j < len(raw):
            if re.fullmatch(r"\d+\.", raw[j]) and j + 1 < len(raw) and FOOTNOTE_START_RE.match(
                raw[j + 1]
            ):
                # footnote entry: drop marker and wrapped lines up to the sentence end
                j += 1
                while j < len(raw):
                    done = raw[j].endswith((".", '."', ".)", ".]"))
                    if done and j + 1 < len(raw) and raw[j + 1].startswith("The Act "):
                        done = False  # long multi-paragraph note (State amendments)
                    j += 1
                    if done:
                        break
                continue
            out.append(raw[j])
            j += 1
        lines.extend(Line(x, i + 1) for x in out)
    return lines, empty


def parse_ipc(doc: pymupdf.Document) -> ParseResult:
    lines, empty = ipc_lines(doc)
    sections: list[Section] = []
    chapter = chapter_title = None
    current: Section | None = None
    notes: list[str] = []
    skipped: set[int] = set()
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        m = CHAPTER_RE.match(ln.text)
        if m and not re.match(r"^\d", ln.text):
            ch = m.group(1) + (m.group(2) or "")
            j = i + 1
            title: list[str] = []
            while j < n and not CHAPTER_RE.match(lines[j].text) and not re.fullmatch(
                r"\d+[A-Z]?\.", lines[j].text
            ):
                title.append(lines[j].text)
                j += 1
            if j < n and CHAPTER_RE.match(lines[j].text):  # chapter heading printed twice
                if lines[j].text == ln.text:
                    j += len(title) + 1
                else:
                    title = []
                    j = i + 1 + len(title)
            if ch != chapter or title:
                chapter, chapter_title = ch, join_lines(title) or None
            i = j
            if current is not None:
                current.page_end = max(current.page_end, ln.page)
            continue
        rng = re.match(r"^(\d+)[A-Z]? to (\d+)[A-Z]?\.", ln.text)
        if rng:  # one printed note for a repealed run of sections, e.g. "161 to 165A."
            lo, hi = int(rng.group(1)), int(rng.group(2))
            skipped.update(range(lo, hi + 1))
            note = f"IPC: sections {lo}-{hi} are printed as one repeal note; no records written"
            if note not in notes:
                notes.append(note)
            current = None
            i += 1
            continue
        mk = re.fullmatch(r"(\d+[A-Z]?)\.", ln.text)
        if mk:
            num = mk.group(1)
            body_re = re.compile(rf"^(?:\d+\*\[)*\[?{num}\.?\s+\S")
            any_body = re.compile(r"^(?:\d+\*\[)*\[?(\d+[A-Z]?)\.?\s+(\S.*)")
            k = None
            for k2 in range(i + 1, min(i + 30, n)):
                if body_re.match(lines[k2].text) or lines[k2].text == f"{num}.":
                    k = k2
                    break
                ab = any_body.match(lines[k2].text)
                if ab:
                    head = join_lines([x.text for x in lines[i + 1:k2]])
                    if head and norm(ab.group(2)).startswith(norm(head)[:20]):
                        k = k2  # body printed with a different number than the marginal one
                        break
                if re.fullmatch(r"\d+[A-Z]?\.", lines[k2].text) or CHAPTER_RE.match(lines[k2].text):
                    break
            if k is not None:
                heading = join_lines([x.text for x in lines[i + 1:k]]) or None
                current = Section(num, heading, chapter, chapter_title, [], ln.page, lines[k].page)
                if heading is None:
                    current.reasons.append("missing heading")
                printed = re.match(r"^(?:\d+\*\[)*\[?(\d+[A-Z]?)", lines[k].text)
                if printed and printed.group(1) != num:
                    current.reasons.append(f"body prints section number {printed.group(1)}")
                    current.body_number = printed.group(1)
                sections.append(current)
                current.lines.append(lines[k].text)
                i = k + 1
                continue
            nxt = [x.text for x in lines[i + 1:i + 4]]
            if nxt and (nxt[0].startswith("[") or any(re.search(r"\bRep\b|Omitted", t) for t in nxt)):
                # repealed/omitted section: the PDF prints only a bracketed title and a repeal note
                title = re.match(r"^\[(.*?)\]", nxt[0])
                current = Section(num, title.group(1) if title else None, chapter, chapter_title,
                                  [], ln.page, ln.page)
                current.reasons.append("repealed/omitted section: text is the repeal note")
                sections.append(current)
                i += 1
                continue
        nb = re.match(r"^(?:\d+\*\[)*\[?(\d+[A-Z]?)\.\s+\S", ln.text)
        if nb and current is not None and split_number(nb.group(1))[0] == split_number(
            current.number
        )[0] + 1 and not split_number(nb.group(1))[1]:
            # section printed without a marginal heading line: its own title is the heading
            current = Section(nb.group(1), None, chapter, chapter_title, [ln.text], ln.page,
                              ln.page)
            sections.append(current)
            i += 1
            continue
        if current is not None:
            current.lines.append(ln.text)
            current.page_end = ln.page
        i += 1
    for s in sections:
        s.lines = strip_ipc_title(s)
    return ParseResult(sections, notes, empty, skipped)


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.replace("-", "")).strip().lower()


def idx_after(starts: list[int], offset: int) -> int:
    return max(i for i, st in enumerate(starts) if st <= offset) + 1


def strip_ipc_title(s: Section) -> list[str]:
    """Drop the repeated 'N. Heading.--' prefix; the legal text starts after '--'."""
    if any("repealed/omitted" in r for r in s.reasons):
        return s.lines
    head = s.lines[:40]
    joined = ""
    starts: list[int] = []
    for line in head:
        sep = "" if (not joined or joined.endswith("-")) else " "
        joined += sep
        starts.append(len(joined))
        joined += line
    num = s.body_number or s.number
    m = re.match(rf"^(?:\d+\*\[)*\[?{num}\.?\s.{{0,500}}?[.\]\"]\s*-{{1,2}}", joined)
    if not m and s.heading:
        # no "--" printed: drop "N. <heading>" when the body repeats the marginal heading
        m = re.match(rf"^(?:\d+\*\[)*\[?{num}\.?\s+", joined)
        if m and norm(joined[m.end():]).startswith(norm(s.heading)):
            words = len(s.heading.split())
            body = joined[m.end():].split()
            rest = " ".join(body[words:])
            return [rest] + s.lines[idx_after(starts, len(joined) - len(rest)):]
        m = None
    if not m:
        if re.search(r"\bRep\b|Omitted|Repealed", joined[:300]):
            s.reasons.append("repealed/omitted section: text is the repeal note")
        else:
            s.reasons.append("title prefix not found")
        return s.lines
    cut = m.end()
    idx = max(i for i, st in enumerate(starts) if st <= cut)
    rest = joined[cut:starts[idx] + len(head[idx])].strip()
    return ([rest] if rest else []) + s.lines[idx + 1:]


# ---------------------------------------------------------------- provenance


def read_provenance(path: Path) -> dict[str, dict[str, str | None]]:
    out: dict[str, dict[str, str | None]] = {}
    text = path.read_text(encoding="utf-8")
    for spec in ACTS:
        info: dict[str, str | None] = {"sha256": None, "retrieved": None, "label": None,
                                       "status_words": None}
        row = re.search(rf"\|\s*`{re.escape(spec.pdf)}`\s*\|(.*)", text)
        if row:
            cells = [c.strip() for c in row.group(1).split("|")]
            date = next((c for c in cells if re.fullmatch(r"\d{4}-\d{2}-\d{2}", c)), None)
            sha = next((c.strip("`") for c in cells if re.fullmatch(r"`[0-9a-f]{64}`", c)), None)
            info["retrieved"], info["sha256"] = date, sha
        flat = re.sub(r"\s+", " ", text)
        note = re.search(rf"`{re.escape(spec.pdf)}` is the ({re.escape(spec.label_pattern)})", flat)
        if note:
            info["label"] = note.group(1)
            tail = flat[note.end():]
            end = re.search(r"\s-\s|\n- `", tail)
            tail = tail[: end.start()] if end else tail
            st = re.search(
                r"\*\*([^*]+)\*\*((?: as of [^.,;]*?)?)(?= and |\s+is |\.|,|;|$)", tail
            )
            if st:
                info["status_words"] = (st.group(1) + st.group(2)).strip()
        out[spec.key] = info
    return out


def status_version(info: dict[str, str | None]) -> str | None:
    if not info["status_words"] or not info["retrieved"]:
        return None
    return f"{info['status_words']}; retrieved {info['retrieved']} (per {PROVENANCE})"


# ---------------------------------------------------------------- records


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_records(spec: ActSpec, result: ParseResult, sha: str,
                  info: dict[str, str | None]) -> tuple[list[dict], dict[str, list[str]]]:
    label = info["label"]
    sv = status_version(info)
    records: list[dict] = []
    reasons: dict[str, list[str]] = {}
    seen: dict[str, dict] = {}
    prev: tuple[int, str] | None = None
    empty = set(result.empty_pages)
    for s in result.sections:
        why = list(s.reasons)
        num, suffix = split_number(s.number)
        sid = f"{spec.key}:{s.number}"
        if prev is not None:
            pn, ps = prev
            in_seq = (
                (num > pn and not suffix and all(
                    k in result.skipped_numbers for k in range(pn + 1, num)))
                or (num == pn and suffix > ps)
            )
            if not in_seq:
                why.append(f"out of sequence (after {pn}{ps})")
        prev = (num, suffix)
        text = build_paragraphs(s.lines).strip()
        if not text:
            why.append("empty text")
        elif len(text) < MIN_TEXT_CHARS:
            why.append("very short text")
        if any(p in empty for p in range(s.page_start, s.page_end + 1)):
            why.append("page without extractable text")
        if label is None:
            why.append("act_label unknown")
        if sv is None:
            why.append("source_status_version unknown")
        if not s.chapter:
            why.append("chapter unknown")
        if sid in seen:
            if seen[sid]["text"] == text:
                reasons.setdefault(sid, []).append("exact duplicate extraction dropped")
                seen[sid]["needs_review"] = True
                continue
            why.append("duplicate section number with different text")
        rec = {
            "section_id": sid,
            "act": spec.act,
            "act_label": label,
            "status": spec.status,
            "chapter": s.chapter,
            "chapter_title": s.chapter_title,
            "section_number": num,
            "heading": s.heading,
            "text": text,
            "source_pdf": spec.pdf,
            "source_sha256": sha,
            "parser": PARSER,
            "parser_version": PARSER_VERSION,
            "source_status_version": sv,
            "needs_review": bool(why),
            "page_start": s.page_start,
            "page_end": s.page_end,
        }
        if why:
            reasons.setdefault(sid, []).extend(why)
        seen.setdefault(sid, rec)
        records.append(rec)
    for rec in records:
        if rec["section_id"] in reasons:
            rec["needs_review"] = True
    return records, reasons


def check_record(rec: dict, spec: ActSpec) -> list[str]:
    problems = []
    for f in REQUIRED_FIELDS:
        if f not in rec:
            problems.append(f"missing {f}")
        elif rec[f] is None and f not in NULLABLE_FIELDS:
            problems.append(f"{f} is null")
    if problems:
        return problems
    if rec["act"] != spec.act:
        problems.append("bad act")
    if rec["status"] != spec.status:
        problems.append("bad status")
    if not re.fullmatch(rf"{spec.key}:\d+[A-Z]*", str(rec["section_id"])):
        problems.append("bad section_id")
    if not isinstance(rec["section_number"], int) or isinstance(rec["section_number"], bool):
        problems.append("section_number not integer")
    if rec["chapter"] is not None and not isinstance(rec["chapter"], str):
        problems.append("chapter not string")
    if not isinstance(rec["text"], str) or not rec["text"].strip():
        problems.append("empty text")
    if not isinstance(rec["needs_review"], bool):
        problems.append("needs_review not boolean")
    return problems


def load_if_valid(path: Path, spec: ActSpec) -> list[dict] | None:
    if not path.is_file():
        return None
    try:
        records = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError, ValueError):
        return None
    if not records or any(not isinstance(r, dict) or check_record(r, spec) for r in records):
        return None
    ids = [r["section_id"] for r in records]
    return records if len(ids) == len(set(ids)) else None


def write_atomic(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


# ---------------------------------------------------------------- main


def run(raw_dir: Path, out_dir: Path, dry_run: bool) -> int:
    missing = [p for p in [raw_dir / PROVENANCE, *(raw_dir / s.pdf for s in ACTS)]
               if not p.is_file()]
    if missing:
        for p in missing:
            print(f"ERROR: missing input: {p}", file=sys.stderr)
        return 2
    prov = read_provenance(raw_dir / PROVENANCE)
    print(f"Parser: {PARSER} {PARSER_VERSION}")
    exit_code = 0
    for spec in ACTS:
        pdf = raw_dir / spec.pdf
        out = out_dir / spec.output
        info = prov[spec.key]
        sha = sha256_of(pdf)
        print(f"\n== {spec.act} ({spec.pdf}) ==")
        if info["sha256"] is None:
            print("  WARNING: no SHA-256 recorded in PROVENANCE.md for this PDF")
        elif info["sha256"] != sha:
            print(f"  WARNING: SHA-256 MISMATCH. PROVENANCE.md={info['sha256']} computed={sha}")
        else:
            print("  SHA-256 matches PROVENANCE.md")
        existing = None if dry_run else load_if_valid(out, spec)
        if existing is not None and all(r["source_sha256"] == sha for r in existing):
            print(f"  {out.name} is valid and current; left untouched.")
            records, reasons, status = existing, {}, "unchanged"
        else:
            doc = pymupdf.open(pdf)
            result = parse_bns(doc) if spec.key == "bns" else parse_ipc(doc)
            records, reasons = build_records(spec, result, sha, info)
            for note in result.notes:
                print(f"  note: {note}")
            if result.empty_pages:
                print(f"  WARNING: pages with no extractable text (likely scanned): "
                      f"{result.empty_pages}")
            if not records:
                print("  ERROR: no sections extracted; nothing written", file=sys.stderr)
                exit_code = 1
                continue
            if dry_run:
                status = "dry run (nothing written)"
            else:
                write_atomic(out, records)
                status = "written"
        flagged = [r for r in records if r["needs_review"]]
        bad = [(r.get("section_id"), p) for r in records for p in check_record(r, spec)]
        ids = [r["section_id"] for r in records]
        dupes = len(ids) - len(set(ids))
        print(f"  {out.name}: {status}")
        print(f"  records: {len(records)}   needs_review: {len(flagged)}   "
              f"duplicate section_ids: {dupes}")
        print(f"  field check: {'OK' if not bad and not dupes else 'PROBLEMS'}")
        for sid, p in bad[:10]:
            print(f"    {sid}: {p}")
        if flagged:
            print("  flagged records:")
            for r in flagged[:40]:
                why = "; ".join(dict.fromkeys(reasons.get(r["section_id"], []))) or "(see file)"
                print(f"    {r['section_id']}: {why}")
            if len(flagged) > 40:
                print(f"    ... and {len(flagged) - 40} more")
        if bad or dupes:
            exit_code = 1
    return exit_code


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m building_with_rag.ingest",
        description="Extract section-level JSONL corpora from the BNS and IPC PDFs "
        "(data/raw/) into data/processed/bns_sections.jsonl and ipc_sections.jsonl.",
    )
    ap.add_argument("--raw-dir", type=Path, default=RAW_DIR, help="folder with the PDFs and "
                    "PROVENANCE.md (default: data/raw)")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR, help="output folder "
                    "(default: data/processed)")
    ap.add_argument("--dry-run", action="store_true",
                    help="parse and print the summary without writing any file")
    args = ap.parse_args(argv)
    return run(args.raw_dir, args.out_dir, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
