import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from pydantic import AnyHttpUrl, BaseModel
from sqlalchemy import create_engine, select
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import Chunk, Document
from app.ingestion.chunking import chunk_filing_text
from app.ingestion.embedder import InferenceRequestError, embed_texts
from app.ingestion.parser import parse_filing_html

COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
}


class ManifestFiling(BaseModel):
    ticker: str
    form: str
    filing_date: date
    report_date: date | None = None
    accession_number: str
    source_url: AnyHttpUrl
    local_path: Path


class FilingManifest(BaseModel):
    filings: list[ManifestFiling]


def _database_url() -> URL:
    url = make_url(settings.database_url)
    if url.drivername in {"postgres", "postgresql"}:
        return url.set(drivername="postgresql+psycopg")
    if url.drivername != "postgresql+psycopg":
        raise ValueError("Ingestion requires a PostgreSQL DATABASE_URL")
    return url


def load_manifest(manifest_path: Path) -> tuple[Path, FilingManifest]:
    manifest_path = manifest_path.resolve(strict=True)
    try:
        raw: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid filing manifest: {manifest_path}") from exc
    return manifest_path.parent, FilingManifest.model_validate(raw)


async def ingest_manifest(manifest_path: Path) -> int:
    corpus_root, manifest = load_manifest(manifest_path)
    engine = create_engine(_database_url(), pool_pre_ping=True)
    ingested_count = 0
    try:
        async with httpx.AsyncClient(
            base_url="https://generativelanguage.googleapis.com",
            headers={"x-goog-api-key": settings.gemini_api_key},
            timeout=60,
        ) as client:
            for filing in manifest.filings:
                with Session(engine) as session:
                    existing_document = session.scalar(
                        select(Document.id).where(
                            Document.accession_number == filing.accession_number
                        )
                    )
                if existing_document is not None:
                    print(f"Already ingested {filing.accession_number}; skipping")
                    continue

                source_path = (corpus_root / filing.local_path).resolve(strict=True)
                source_path.relative_to(corpus_root)
                ticker = filing.ticker.upper()
                try:
                    company_name = COMPANY_NAMES[ticker]
                except KeyError:
                    raise ValueError(
                        f"Unsupported filing ticker: {filing.ticker}"
                    ) from None

                text = parse_filing_html(source_path)
                chunks = chunk_filing_text(text)
                if not chunks:
                    raise ValueError(f"No text extracted from filing: {source_path}")

                embeddings = await embed_texts(
                    client,
                    [chunk.content for chunk in chunks],
                    model=settings.gemini_embedding_model,
                    dimensions=settings.gemini_embedding_dimensions,
                    task_type="RETRIEVAL_DOCUMENT",
                )

                with Session(engine) as session, session.begin():
                    document = Document(
                        ticker=ticker,
                        company_name=company_name,
                        form_type=filing.form,
                        fiscal_year=(filing.report_date or filing.filing_date).year,
                        filed_at=filing.filing_date,
                        accession_number=filing.accession_number,
                        source_url=str(filing.source_url),
                        source_path=filing.local_path.as_posix(),
                    )
                    session.add(document)

                    session.flush()
                    session.add_all(
                        [
                            Chunk(
                                document_id=document.id,
                                chunk_index=chunk.chunk_index,
                                section_title=chunk.section_title,
                                content=chunk.content,
                                embedding=embedding,
                            )
                            for chunk, embedding in zip(
                                chunks, embeddings, strict=True
                            )
                        ]
                    )
                ingested_count += 1

                print(
                    f"Ingested {ticker} {filing.form} {filing.accession_number}: "
                    f"{len(chunks)} chunks"
                )
    finally:
        engine.dispose()

    return ingested_count


def main() -> None:
    default_manifest = (
        Path(__file__).resolve().parents[3] / "data" / "downloads" / "manifest.json"
    )
    try:
        count = asyncio.run(ingest_manifest(default_manifest))
    except InferenceRequestError as exc:
        raise SystemExit(
            f"Ingestion stopped: {exc} Re-run after the issue clears."
        ) from exc
    print(f"Created {count} filing(s) and their chunks")


if __name__ == "__main__":
    main()
