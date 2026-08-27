"""Validate and ingest a city JSONL collection into PostgreSQL."""
from __future__ import annotations

import argparse

from app.knowledge.dataset import DatasetValidationError, load_dataset
from app.knowledge.postgres import PostgresKnowledgeRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest city collection JSONL files")
    parser.add_argument("dataset_dir", help="Directory containing source_manifest.jsonl and collection cards")
    parser.add_argument("--include-draft", action="store_true", help="Import DRAFT records for local integration testing")
    parser.add_argument("--check", action="store_true", help="Validate and show the import plan without writing to PostgreSQL")
    args = parser.parse_args()
    try:
        dataset = load_dataset(args.dataset_dir, include_draft=args.include_draft)
    except DatasetValidationError as exc:
        parser.error(str(exc))

    if args.check:
        print(f"Valid dataset: {len(dataset.documents)} documents planned; {dataset.skipped_drafts} DRAFT records skipped")
        return
    repository = PostgresKnowledgeRepository()
    for document in dataset.documents:
        repository.ingest(document.model_dump())
    print(f"Ingested {len(dataset.documents)} documents; {dataset.skipped_drafts} DRAFT records skipped")


if __name__ == "__main__":
    main()
