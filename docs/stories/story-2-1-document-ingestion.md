# Story 2.1: Document Ingestion

## Purpose

Build a script that turns the supplied BNS and IPC PDFs into a small, inspectable, section-level corpus: one JSON record per legal section, written to two JSONL files when the user runs it. Later stories (chunking, MongoDB import, embeddings, retrieval) read these files. This story does only the extraction.

Do not implement MongoDB, embeddings, vector indexes, retrieval, or answer generation here. They belong to later stories.

## Prerequisites

- Story 1.1 is complete. Reuse its application (`src/building_with_rag/`), its documents (`docs/architecture.md`, `README.md`), and the existing `.env.example`. Do not add, rename, or remove any setting.
- Project path: `docs/config.yaml` did not exist when this story was written, so use the repository root. If it exists when you start, use the project path it configures.
- Inputs (read-only):
  - `data/raw/BNS_2023_bare_act.pdf`
  - `data/raw/IPC_1860_bare_act.pdf`
  - `data/raw/PROVENANCE.md`
- Preserve the original PDFs and `PROVENANCE.md` byte for byte. Do not edit, move, or delete them. If any input is missing, stop and report exactly which one. Do not substitute another source.
- Preserve all existing work in the repository, including any valid file already in `data/processed/`.

## Out of scope

MongoDB, embeddings, vector indexes, chunking, retrieval, answer generation, OCR pipelines, a comprehensive corpus-validation framework, a reference-difference report, broad security tests, and synthetic permission records.

## Work to do

1. **Read first.** Read `docs/architecture.md`, Story 1.1, the existing code, `data/raw/PROVENANCE.md`, and skim both PDFs. Note that the BNS PDF also contains an index and a BNS-to-IPC correspondence table. These are not section text and must not become records.
2. **Choose a parser.** Pick a suitable PDF text-extraction library and add it with UV (`uv add <package>`). Keep the choice small and justified in one or two sentences. Record its name and version; these become the `parser` and `parser_version` values.
3. **Write the extraction.** Add a small module (for example `src/building_with_rag/ingest.py`) with a command-line entry point, run as `uv run python -m building_with_rag.ingest`. It reads each PDF and extracts sections without rewriting their meaning.
   - Keep the legal wording as printed. Only normalise obvious layout noise: repeated page headers and footers, page numbers, hyphenation at line breaks, and extra spaces or blank lines.
   - Join sections that run across pages into one record. Do not split a section at a page break.
   - Handle obvious duplicate extraction (the same section text produced twice) conservatively: keep one copy, and set `needs_review` to true on that record if you are not sure.
   - Flag uncertain content rather than repairing it silently. Examples: a section number that does not follow the sequence, a missing heading, very short text, or pages with no extractable text (likely scanned). Set `needs_review` to true and mention the case in the run summary.
   - Do not invent unknown provenance. If a value cannot be taken from the PDF, `PROVENANCE.md`, or the parser, leave it `null` and set `needs_review` to true.
4. **Record format.** Write one JSON object per line, UTF-8, with these fields exactly:

   | Field | Value |
   |---|---|
   | `section_id` | `bns:<number>` or `ipc:<number>` |
   | `act` | `BNS_2023` or `IPC_1860` |
   | `act_label` | the act's readable name from the PDF or `PROVENANCE.md` (for example "Bharatiya Nyaya Sanhita, 2023") |
   | `status` | `in_force` (BNS) or `repealed` (IPC) |
   | `chapter` | string, for example `I` |
   | `chapter_title` | the chapter heading text |
   | `section_number` | integer |
   | `heading` | the section's marginal heading |
   | `text` | the full section text, never empty |
   | `source_pdf` | the PDF file name |
   | `source_sha256` | SHA-256 of that PDF, computed at run time |
   | `parser` | parser library name |
   | `parser_version` | parser library version |
   | `source_status_version` | the status/version of the source as stated in `PROVENANCE.md` (use its recorded retrieval date and status wording; do not guess) |
   | `needs_review` | boolean |

   Page references (for example `page_start`, `page_end`) may be added as extra fields, but they do not replace any field above. Keep BNS and IPC records separate even where section numbers match (`bns:103` and `ipc:103` are different records).
5. **Output.** Write `data/processed/bns_sections.jsonl` and `data/processed/ipc_sections.jsonl`.
   - Verify each PDF's SHA-256 against `PROVENANCE.md`. Report a mismatch, and still record the computed hash in `source_sha256`.
   - If an output file already exists, is valid, and its records all carry the current `source_sha256`, leave it untouched.
   - If the source hash differs from the one in the existing output, regenerate that file as one complete replacement: write to a temporary file in the same folder, then rename it over the old file. Never append, and never mix records from different source versions.
   - Re-running must not append duplicate records.
6. **Document it.** Add a short section to `docs/architecture.md` recording the parser choice, the output format and field list, the exact command, and the known limitations (for example scanned or uncertain pages, the index and correspondence table being skipped). Update `README.md` with the command. Extend additively; do not rewrite existing content.

## Run policy

The implementer builds the extraction script and makes it available in the project. The implementer does **not** run the extraction, and does not create or modify anything in `data/processed/`. The user runs the command themselves. If the implementer needs to try the parser on a few pages while building, it may read the PDFs, but it must write no output into `data/processed/` and must not leave generated corpus files behind.

## Completion checks

Keep these small and direct.

**The implementer runs (code checks only):**

1. `uv sync` succeeds, `uv run ruff check .` passes, and the existing `uv run pytest` still passes.
2. `uv run python -m building_with_rag.ingest --help` runs and shows the command's usage.
3. The PDFs and `PROVENANCE.md` are unchanged and no secrets were added.

**The user runs (after handover), and the story lists these as instructions:**

4. `uv run python -m building_with_rag.ingest`. Both JSONL files appear in `data/processed/`. The run prints record counts and `needs_review` counts for each act.
5. Check required fields on every record (exact allowed values for `act`, `status`, `section_id`, `section_number` as integer, `chapter` as string) and that no record has empty `text`.
6. Inspect representative records against each PDF: a first, a middle and a last section, and one section that spans pages if present.
7. Run the command a second time. The files must be unchanged (same line count and hash) with no duplicate `section_id` values.

Write the instructions for steps 4-7 in the README section so the user can follow them. The script's end-of-run summary should make steps 4 and 5 easy (counts, flagged records, field check).

## Handover

When finished, add a completion record to this story containing:

- **Inputs:** the three input files named above.
- **Output:** the two JSONL paths the script will write. State clearly that they have not been generated yet.
- **Files created or changed:** the actual list.
- **Commands actually run** and their results (checks 1-3 only). Do not claim a check passed unless it was run. State any skipped check and why.
- **How to run it:** the exact command and the user checks 4-7 above.
- **Known limitations:** cases the script flags for review (scanned or uncertain pages, skipped index and correspondence table), and any missing input.
- **How later chunking keeps the parent section and source information:** every chunk must carry its parent `section_id`, `act`, `act_label`, `status`, `chapter`, `chapter_title`, `section_number`, `heading`, `source_pdf`, `source_sha256`, `parser`, `parser_version`, `source_status_version` and `needs_review` unchanged from the section record, plus its position in the section. Chunks are cut from a section's `text` only, never across sections or acts, so every retrieved chunk can be traced to one parent section record and one source PDF.
- **Notes for Story 2.2:** anything the importer and embedding story must know.

---

## Completion record

**Inputs (read-only, unchanged):** `data/raw/BNS_2023_bare_act.pdf`, `data/raw/IPC_1860_bare_act.pdf`, `data/raw/PROVENANCE.md`. Both PDF hashes matched `PROVENANCE.md` when the parser was tried in dry-run mode.

**Output (NOT generated yet):** `data/processed/bns_sections.jsonl` and `data/processed/ipc_sections.jsonl`. `data/processed/` is still empty; the user runs the command.

**Files created or changed:**
- Created `src/building_with_rag/ingest.py` (extraction and CLI)
- Created `tests/test_ingest.py`
- Changed `pyproject.toml` and `uv.lock` (added `pymupdf`)
- Extended `docs/architecture.md` and `README.md` (additive sections)
- Added this completion record

**Commands actually run (checks 1-3):**
1. `uv sync`: succeeded. `uv run ruff check .`: all checks passed. `uv run pytest`: 11 passed (the 7 existing tests plus 4 new ones). One new test writes to a pytest temp folder, runs the ingest twice and checks that the files are unchanged; it never touches `data/processed/`.
2. `uv run python -m building_with_rag.ingest --help`: shows usage.
3. Both PDFs' SHA-256 equal the values in `PROVENANCE.md`; `data/processed/` is empty. No secrets added.
Besides these, I ran `--dry-run` (nothing written) to develop the parser. In that mode it found 358 BNS records (1 flagged) and 547 IPC records (about 17 flagged).

**How to run it:** `uv run python -m building_with_rag.ingest`, then steps 4-7 in the README section "Build the section corpus (Story 2.1)". I did not run steps 4-7.

**Known limitations:**
- The BNS index and BNS-to-IPC correspondence table (PDF pages 1-73) are skipped.
- No page lacked extractable text, so no scanned pages are expected, but the script would report them.
- BNS 287 is flagged because its heading is not bold in the PDF.
- IPC repealed/omitted sections keep only the printed repeal note as text and are flagged.
- IPC 330 is flagged because the PDF body prints "320".
- IPC 213 is flagged because the body title is shorter than the marginal heading.
- IPC 161-165A and 478-489 are single printed repeal-note ranges. No per-section records are written for those ranges, and a few numbers inside them (for example 479) have no record.
- IPC footnotes and chapter headings are removed by heuristics. Inline amendment markers (`1*[...]`) stay in the text.
- IPC sections with a letter (for example 304A) use `section_id` `ipc:304A` and `section_number` 304.
- No input was missing.

**How later chunking keeps the parent section and source information:** every chunk must carry its parent `section_id`, `act`, `act_label`, `status`, `chapter`, `chapter_title`, `section_number`, `heading`, `source_pdf`, `source_sha256`, `parser`, `parser_version`, `source_status_version` and `needs_review` unchanged from the section record, plus its position in the section. Chunks are cut from a section's `text` only, never across sections or acts, so every retrieved chunk can be traced to one parent section record and one source PDF.

**Notes for Story 2.2:**
- Key records by `section_id` (unique per file, and act-qualified). `bns:103` and `ipc:103` are different records.
- `section_number` is an integer, so `ipc:304A` and `ipc:304` share 304. Do not key on it alone.
- `chapter`, `chapter_title`, `heading`, `act_label` and `source_status_version` can be `null` in principle. Right now only `heading` is null (BNS 287 and some repealed IPC sections).
- `text` uses `\n` between clauses, explanations and illustrations. `page_start` and `page_end` are extra fields.
- Decide how to treat `needs_review` records and IPC repeal-note records before embedding them.
- `status` is `repealed` for all IPC records; never present them as current law.
