import hashlib
import json

import pytest

from building_with_rag import ingest


def test_join_lines_keeps_real_hyphens():
    assert ingest.join_lines(["extra-", "territorial offences"]) == "extra-territorial offences"
    assert ingest.join_lines(["a wrapped", "line"]) == "a wrapped line"


def test_split_number_and_paragraphs():
    assert ingest.split_number("304A") == (304, "A")
    text = ingest.build_paragraphs(["(1) first", "part", "(2) second", "Explanation.-note"])
    assert text == "(1) first part\n(2) second\nExplanation.-note"


def test_missing_input_stops_without_output(tmp_path, capsys):
    assert ingest.run(tmp_path, tmp_path / "out", dry_run=False) == 2
    assert "missing input" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


@pytest.mark.skipif(not (ingest.RAW_DIR / ingest.ACTS[0].pdf).is_file(), reason="PDFs absent")
def test_rerun_leaves_files_untouched(tmp_path):
    out = tmp_path / "processed"
    assert ingest.run(ingest.RAW_DIR, out, dry_run=False) == 0
    files = {s.output: (out / s.output).read_bytes() for s in ingest.ACTS}
    first = json.loads(files["bns_sections.jsonl"].splitlines()[0])
    assert first["section_id"] == "bns:1" and first["text"]
    assert ingest.run(ingest.RAW_DIR, out, dry_run=False) == 0
    for name, data in files.items():
        assert hashlib.sha256((out / name).read_bytes()).digest() == hashlib.sha256(data).digest()
        ids = [json.loads(x)["section_id"] for x in data.decode().splitlines()]
        assert len(ids) == len(set(ids))
    assert not list(out.glob("*.tmp"))
