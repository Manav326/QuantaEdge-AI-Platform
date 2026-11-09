#!/usr/bin/env python3
"""Validate a QuantaEdge class-wise GHCR textbook image export before it is saved."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # pragma: no cover - exercised by the PowerShell preflight
    raise SystemExit(
        'PyMuPDF is required. Run the downloader; it installs '
        '"PyMuPDF>=1.24,<2" in the selected Python environment.'
    ) from exc

BOOK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,239}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(index_path: Path, books_dir: Path, image: str) -> dict[str, Any]:
    if not index_path.is_file():
        raise ValueError(f"Registry index is missing: {index_path}")
    if not books_dir.is_dir():
        raise ValueError(f"Registry books directory is missing: {books_dir}")

    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not parse registry index: {exc}") from exc

    if not isinstance(index, dict) or not isinstance(index.get("books"), list):
        raise ValueError("GHCR index.json must contain a books array.")
    if index.get("schema_version") not in (1, "1"):
        raise ValueError(f"Unsupported registry schema_version: {index.get('schema_version')!r}")

    image_match = re.fullmatch(
        r"ghcr\.io/([a-z0-9][a-z0-9-]*)/quantaedge-textbooks-class-(6|7|8|9|10|11|12)-(hindi|english):latest",
        image.casefold(),
    )
    if not image_match:
        raise ValueError(f"Unexpected QuantaEdge textbook image reference: {image}")
    expected_class = int(image_match.group(2))
    expected_language = image_match.group(3)
    if index.get("registry") not in (None, image):
        raise ValueError("GHCR index registry does not match the requested image.")
    if index.get("class_no") is not None and int(index["class_no"]) != expected_class:
        raise ValueError("GHCR index class_no does not match the requested image.")
    if index.get("language") is not None and str(index["language"]).casefold() != expected_language:
        raise ValueError("GHCR index language does not match the requested image.")

    books = index["books"]
    if not books:
        raise ValueError(f"The GHCR image contains no indexed books: {image}")

    seen_ids: set[str] = set()
    verified: list[dict[str, Any]] = []
    total_bytes = 0
    total_pages = 0

    for position, item in enumerate(books, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Book entry #{position} is not a JSON object.")

        book_id = str(item.get("book_id") or "")
        if not BOOK_ID_RE.fullmatch(book_id):
            raise ValueError(f"Book entry #{position} has an unsafe or missing book_id: {book_id!r}")
        if book_id in seen_ids:
            raise ValueError(f"Duplicate book_id in GHCR index: {book_id}")
        seen_ids.add(book_id)

        relative = PurePosixPath(str(item.get("file") or ""))
        expected_relative = PurePosixPath("books") / f"{book_id}.pdf"
        if relative != expected_relative or relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Book {book_id} has a non-canonical whole-book path: {relative}")

        expected_hash = str(item.get("sha256") or "").lower()
        if not SHA256_RE.fullmatch(expected_hash):
            raise ValueError(f"Book {book_id} has a missing or invalid SHA-256 in the index.")

        pdf_path = books_dir / f"{book_id}.pdf"
        if not pdf_path.is_file():
            raise ValueError(f"Indexed PDF is missing: {pdf_path}")
        if pdf_path.stat().st_size <= 0:
            raise ValueError(f"Indexed PDF is empty: {pdf_path}")

        with pdf_path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise ValueError(f"Indexed file is not a PDF: {pdf_path}")

        actual_hash = sha256_file(pdf_path)
        if actual_hash != expected_hash:
            raise ValueError(
                f"SHA-256 mismatch for {book_id}: expected {expected_hash}, got {actual_hash}"
            )

        try:
            with fitz.open(pdf_path) as document:
                if document.is_encrypted:
                    raise ValueError(f"PDF is encrypted and cannot be validated: {book_id}")
                page_count = document.page_count
                if page_count < 1:
                    raise ValueError(f"PDF has no pages: {book_id}")
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError(f"PyMuPDF could not open {book_id}: {exc}") from exc

        indexed_page_count = item.get("page_count")
        if indexed_page_count is not None:
            try:
                expected_pages = int(indexed_page_count)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Book {book_id} has an invalid indexed page_count.") from exc
            if expected_pages < 1 or page_count != expected_pages:
                raise ValueError(
                    f"Page-count mismatch for {book_id}: index says {expected_pages}, PDF has {page_count}"
                )

        size_bytes = pdf_path.stat().st_size
        total_bytes += size_bytes
        total_pages += page_count
        verified.append(
            {
                "book_id": book_id,
                "title": str(item.get("title") or book_id),
                "file": relative.as_posix(),
                "size_bytes": size_bytes,
                "page_count": page_count,
                "sha256": actual_hash,
                "source_url": item.get("source_url") or item.get("catalog_entry_url"),
                "edition": item.get("edition"),
            }
        )

    return {
        "status": "VERIFIED",
        "image": image,
        "book_count": len(verified),
        "total_pdf_bytes": total_bytes,
        "total_pdf_pages": total_pages,
        "books": verified,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--books-dir", required=True, type=Path)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    try:
        result = validate(args.index, args.books_dir, args.image)
    except Exception as exc:
        print(f"TEXTBOOK_CACHE_VALIDATION_FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
