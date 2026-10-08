import json

import pytest

from app.ingestion.ingest import load_manifest


def test_load_manifest_resolves_filing_paths_from_manifest_directory(tmp_path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "filings": [
                    {
                        "ticker": "AAPL",
                        "form": "10-K",
                        "filing_date": "2025-10-31",
                        "report_date": "2025-09-27",
                        "accession_number": "0000320193-25-000079",
                        "source_url": "https://www.sec.gov/filing.html",
                        "local_path": "2025/filing.html",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    corpus_root, manifest = load_manifest(manifest_path)

    assert corpus_root == tmp_path
    assert manifest.filings[0].ticker == "AAPL"
    assert manifest.filings[0].local_path.as_posix() == "2025/filing.html"


def test_load_manifest_rejects_malformed_json(tmp_path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid filing manifest"):
        load_manifest(manifest_path)
