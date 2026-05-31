"""Prepare a private Voice Corpus source for bounded reader passes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REGISTER_VALUES = {"calibration", "academic", "personal", "sent_gmail", "admin_proposal"}
DEFAULT_CACHE_ROOT = Path(".codex") / "voice_corpus_cache"
DEFAULT_READER_TASKS = ("voice", "author_method", "facts")


@dataclass(frozen=True)
class Span:
    text: str
    char_start: int
    char_end: int
    byte_start: int
    byte_end: int
    paragraph_start: int
    paragraph_end: int


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-16")


def normalise_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def byte_offsets(text: str) -> list[int]:
    offsets = [0]
    total = 0
    for ch in text:
        total += len(ch.encode("utf-8"))
        offsets.append(total)
    return offsets


def paragraph_spans(text: str, offsets: list[int]) -> list[Span]:
    spans: list[Span] = []
    paragraph_no = 1
    for match in re.finditer(r"\S(?:.*?(?=\n\s*\n|\Z))", text, flags=re.DOTALL):
        para = match.group(0).strip("\n")
        if not para.strip():
            continue
        start = match.start()
        end = match.start() + len(match.group(0).rstrip("\n"))
        spans.append(
            Span(
                text=text[start:end],
                char_start=start,
                char_end=end,
                byte_start=offsets[start],
                byte_end=offsets[end],
                paragraph_start=paragraph_no,
                paragraph_end=paragraph_no,
            )
        )
        paragraph_no += 1
    return spans


def pack_chunks(paragraphs: list[Span], max_chars: int, offsets: list[int], text: str) -> list[Span]:
    if not paragraphs:
        return []

    chunks: list[Span] = []
    current: list[Span] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para.text)
        if current and current_len + para_len + 2 > max_chars:
            chunks.append(join_spans(current, offsets, text))
            current = []
            current_len = 0
        current.append(para)
        current_len += para_len + 2

    if current:
        chunks.append(join_spans(current, offsets, text))
    return chunks


def join_spans(spans: list[Span], offsets: list[int], text: str) -> Span:
    start = spans[0].char_start
    end = spans[-1].char_end
    return Span(
        text=text[start:end],
        char_start=start,
        char_end=end,
        byte_start=offsets[start],
        byte_end=offsets[end],
        paragraph_start=spans[0].paragraph_start,
        paragraph_end=spans[-1].paragraph_end,
    )


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def chunk_id(source_handle: str, chunk: Span) -> str:
    prefix = digest(chunk.text)[:12]
    return f"{source_handle}-P{chunk.paragraph_start:04d}-P{chunk.paragraph_end:04d}-{prefix}"


def build_manifest(
    *,
    source_path: Path,
    source_handle: str,
    register: str,
    source_kind: str,
    salt: str,
    text: str,
    chunks: list[Span],
    chunk_dir: Path,
) -> dict[str, Any]:
    content_hash = digest(text)
    source_id_hash = digest(f"{salt}:{source_handle}:{source_kind}:{content_hash}")
    return {
        "schema_version": "voice-corpus-chunks/0.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "source_handle": source_handle,
            "register": register,
            "source_kind": source_kind,
            "source_path": str(source_path.resolve()),
            "source_id_hash": source_id_hash,
            "content_sha256": content_hash,
            "char_count": len(text),
            "byte_count": len(text.encode("utf-8")),
        },
        "chunks": [
            {
                "chunk_id": chunk_id(source_handle, chunk),
                "chunk_path": str((chunk_dir / f"{chunk_id(source_handle, chunk)}.txt").resolve()),
                "paragraph_start": chunk.paragraph_start,
                "paragraph_end": chunk.paragraph_end,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "byte_start": chunk.byte_start,
                "byte_end": chunk.byte_end,
                "char_count": len(chunk.text),
                "byte_count": len(chunk.text.encode("utf-8")),
                "chunk_sha256": digest(chunk.text),
            }
            for chunk in chunks
        ],
    }


def write_outputs(manifest: dict[str, Any], chunks: list[Span], cache_root: Path, source_handle: str) -> tuple[Path, Path]:
    manifest_dir = cache_root / "manifests"
    chunk_dir = cache_root / "chunks" / source_handle
    manifest_dir.mkdir(parents=True, exist_ok=True)
    chunk_dir.mkdir(parents=True, exist_ok=True)

    for chunk in chunks:
        path = chunk_dir / f"{chunk_id(source_handle, chunk)}.txt"
        path.write_text(chunk.text, encoding="utf-8")

    manifest_path = manifest_dir / f"{source_handle}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest_path, chunk_dir


def parse_reader_tasks(value: str) -> list[str]:
    tasks = [task.strip() for task in value.split(",") if task.strip()]
    invalid = [task for task in tasks if not re.fullmatch(r"[a-z][a-z0-9_]*", task)]
    if invalid:
        raise ValueError(f"invalid reader task(s): {', '.join(invalid)}")
    return tasks


def write_reader_queue(
    manifest: dict[str, Any],
    manifest_path: Path,
    cache_root: Path,
    source_handle: str,
    tasks: list[str],
) -> Path:
    reader_dir = cache_root / "readers" / source_handle
    reader_dir.mkdir(parents=True, exist_ok=True)
    queue_path = reader_dir / "queue.jsonl"

    source = manifest["source"]
    jobs = []
    for chunk in manifest["chunks"]:
        for task in tasks:
            job_id = f"{chunk['chunk_id']}::{task}"
            output_path = reader_dir / f"{chunk['chunk_id']}.{task}.json"
            jobs.append(
                {
                    "schema_version": "voice-reader-queue/0.1",
                    "job_id": job_id,
                    "status": "pending",
                    "reader_task": task,
                    "source_handle": source_handle,
                    "register": source["register"],
                    "source_kind": source["source_kind"],
                    "source_id_hash": source["source_id_hash"],
                    "manifest_path": str(manifest_path.resolve()),
                    "chunk_id": chunk["chunk_id"],
                    "chunk_path": chunk["chunk_path"],
                    "span": {
                        "byte_start": chunk["byte_start"],
                        "byte_end": chunk["byte_end"],
                        "char_start": chunk["char_start"],
                        "char_end": chunk["char_end"],
                        "paragraph_start": chunk["paragraph_start"],
                        "paragraph_end": chunk["paragraph_end"],
                    },
                    "output_path": str(output_path.resolve()),
                    "attempts": 0,
                    "last_error": None,
                }
            )

    queue_path.write_text(
        "".join(json.dumps(job, ensure_ascii=False) + "\n" for job in jobs),
        encoding="utf-8",
    )
    return queue_path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a Voice Corpus source for bounded readers.")
    parser.add_argument("source", help="UTF-8 or UTF-16 text file to chunk.")
    parser.add_argument("--source-handle", required=True, help="Stable source handle, e.g. EPPUR-PRIMARY.")
    parser.add_argument("--register", required=True, choices=sorted(REGISTER_VALUES))
    parser.add_argument("--source-kind", required=True, help="Source kind, e.g. google_doc, latex, gmail.")
    parser.add_argument("--cache-root", default=str(DEFAULT_CACHE_ROOT), help="Ignored cache root.")
    parser.add_argument("--max-chars", type=int, default=120_000, help="Approximate maximum characters per chunk.")
    parser.add_argument("--salt", default=os.environ.get("VOICE_CORPUS_SALT", "voice-corpus-local"))
    parser.add_argument(
        "--reader-queue",
        action="store_true",
        help="Also write a restartable reader job queue. This does not call an LLM.",
    )
    parser.add_argument(
        "--reader-tasks",
        default=",".join(DEFAULT_READER_TASKS),
        help="Comma-separated reader tasks for --reader-queue.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    source = Path(args.source)
    if not source.exists():
        print(f"Error: source not found: {source}", file=sys.stderr)
        return 2
    if args.max_chars < 100:
        print("Error: --max-chars must be at least 100.", file=sys.stderr)
        return 2
    try:
        reader_tasks = parse_reader_tasks(args.reader_tasks)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if args.reader_queue and not reader_tasks:
        print("Error: --reader-tasks must name at least one task when --reader-queue is set.", file=sys.stderr)
        return 2

    text = normalise_newlines(read_text(source))
    offsets = byte_offsets(text)
    paragraphs = paragraph_spans(text, offsets)
    chunks = pack_chunks(paragraphs, args.max_chars, offsets, text)
    cache_root = Path(args.cache_root)
    chunk_dir = cache_root / "chunks" / args.source_handle
    manifest = build_manifest(
        source_path=source,
        source_handle=args.source_handle,
        register=args.register,
        source_kind=args.source_kind,
        salt=args.salt,
        text=text,
        chunks=chunks,
        chunk_dir=chunk_dir,
    )
    manifest_path, chunk_dir = write_outputs(manifest, chunks, cache_root, args.source_handle)
    queue_path = None
    if args.reader_queue:
        queue_path = write_reader_queue(manifest, manifest_path, cache_root, args.source_handle, reader_tasks)

    print("# Voice Corpus Chunking")
    print(f"Source handle: {args.source_handle}")
    print(f"Register: {args.register}")
    print(f"Chunks: {len(chunks)}")
    print(f"Manifest: {manifest_path}")
    print(f"Chunk directory: {chunk_dir}")
    if queue_path:
        print(f"Reader queue: {queue_path}")
        print(f"Reader jobs: {len(chunks) * len(reader_tasks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
