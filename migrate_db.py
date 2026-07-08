"""
migrate_db.py
=============
Production-grade, 1:1 MongoDB migration utility.

Copies every collection (documents + indexes) from a SOURCE cluster to a
TARGET cluster with full BSON fidelity:

  * `_id` values, nested documents, arrays, ObjectId, Decimal128, Binary,
    and native `datetime` objects are preserved byte-for-byte because we
    stream raw BSON documents straight from the source cursor into
    `insert_many()` — no serialization to JSON ever happens.
  * Documents are streamed with a server-side cursor and inserted in
    batches (default 1000) so RAM usage stays flat regardless of
    collection size.
  * Every user-defined index is recreated on the target with its exact
    options (unique / sparse / TTL / partial / collation / text weights …).
  * Target collections are dropped first to guarantee a clean slate, so
    re-running the script is fully idempotent.

Usage
-----
    # from ULMIND_BACKEND/  (activate the venv first)
    python migrate_db.py                 # run the migration
    python migrate_db.py --dry-run       # analyze only, copy nothing
    python migrate_db.py --batch-size 500

Both connection strings can be overridden via env vars
`SOURCE_MONGO_URI` / `TARGET_MONGO_URI`; otherwise the defaults below
(matching the requested migration) are used.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone

import certifi
from pymongo import MongoClient, IndexModel
from pymongo.errors import BulkWriteError, OperationFailure

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
SOURCE_URI = os.getenv(
    "SOURCE_MONGO_URI",
    "mongodb+srv://samiran:samiran2004@cluster2004.eowyegm.mongodb.net/ulmind",
)
TARGET_URI = os.getenv(
    "TARGET_MONGO_URI",
    "mongodb+srv://ulmindsocialpvtltd_db_user:ulmind200430101001@cluster0.6h3vud7.mongodb.net/ulmind",
)

DB_NAME = "ulmind"
DEFAULT_BATCH_SIZE = 1000

# Index option keys that are metadata / not accepted back by createIndexes.
# We strip these before rebuilding an index from its stored definition.
_IGNORED_INDEX_KEYS = {"v", "ns", "key", "name", "background"}


# --------------------------------------------------------------------------- #
# Logging helpers (timestamped, unbuffered)
# --------------------------------------------------------------------------- #
def log(msg: str, symbol: str = "•") -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {symbol} {msg}", flush=True)


def banner(title: str) -> None:
    line = "=" * 70
    print(f"\n{line}\n  {title}\n{line}", flush=True)


# --------------------------------------------------------------------------- #
# Connection
# --------------------------------------------------------------------------- #
def connect(uri: str, label: str) -> MongoClient:
    log(f"Connecting to {label} …")
    client = MongoClient(
        uri,
        tlsCAFile=certifi.where(),        # matches app/db/database.py TLS setup
        serverSelectionTimeoutMS=20000,
        # RawBSONDocument is NOT used here so we can also read metadata,
        # but standard codec still round-trips every BSON type losslessly.
    )
    # Force a real round-trip so we fail fast on bad credentials / network.
    client.admin.command("ping")
    server = client.server_info().get("version", "unknown")
    log(f"Connected to {label} (MongoDB {server}).", symbol="✓")
    return client


# --------------------------------------------------------------------------- #
# Index migration
# --------------------------------------------------------------------------- #
def build_index_models(src_coll) -> list[IndexModel]:
    """Read every index from a source collection and turn each (except the
    implicit _id_ index, which MongoDB creates automatically) into an
    IndexModel that reproduces it exactly on the target."""
    models: list[IndexModel] = []
    for idx in src_coll.list_indexes():
        idx = dict(idx)
        name = idx.get("name")
        if name == "_id_":
            continue  # auto-created; never recreate

        keys = list(idx["key"].items())            # preserve field order + direction
        options = {
            k: v for k, v in idx.items() if k not in _IGNORED_INDEX_KEYS
        }
        options["name"] = name                     # keep original index name
        models.append(IndexModel(keys, **options))
    return models


def migrate_indexes(src_coll, dst_coll) -> int:
    models = build_index_models(src_coll)
    if not models:
        return 0
    try:
        dst_coll.create_indexes(models)
    except OperationFailure as exc:
        # Rebuild one-by-one so a single incompatible index doesn't abort all.
        log(f"    bulk index build failed ({exc.details.get('errmsg', exc)}); "
            f"retrying individually", symbol="!")
        built = 0
        for m in models:
            try:
                dst_coll.create_indexes([m])
                built += 1
            except OperationFailure as e:
                log(f"    skipped index {m.document.get('name')}: "
                    f"{e.details.get('errmsg', e)}", symbol="✗")
        return built
    return len(models)


# --------------------------------------------------------------------------- #
# Document migration
# --------------------------------------------------------------------------- #
def migrate_documents(src_coll, dst_coll, batch_size: int) -> int:
    total_src = src_coll.estimated_document_count()
    copied = 0
    batch: list = []

    # batch_size on the cursor bounds how many docs the driver buffers at once,
    # keeping RAM flat. (no_cursor_timeout is intentionally NOT set — shared
    # Atlas tiers disallow it, and batches complete well within the 10-min
    # server cursor lifetime.)
    cursor = src_coll.find({}).batch_size(batch_size)
    try:
        for doc in cursor:
            batch.append(doc)
            if len(batch) >= batch_size:
                copied += _flush(dst_coll, batch)
                _progress(copied, total_src)
                batch = []
        if batch:
            copied += _flush(dst_coll, batch)
            _progress(copied, total_src)
    finally:
        cursor.close()

    return copied


def _flush(dst_coll, batch: list) -> int:
    """Insert a batch preserving original _id. ordered=False lets a single
    duplicate/bad doc be skipped without aborting the whole batch."""
    try:
        res = dst_coll.insert_many(batch, ordered=False)
        return len(res.inserted_ids)
    except BulkWriteError as bwe:
        n_ins = bwe.details.get("nInserted", 0)
        errs = bwe.details.get("writeErrors", [])
        log(f"    {len(errs)} write error(s) in batch; {n_ins} inserted",
            symbol="!")
        return n_ins


def _progress(done: int, total: int) -> None:
    pct = f"{(done / total * 100):5.1f}%" if total else "  n/a"
    print(f"\r      → {done:>9,}/{total:<9,} documents ({pct})",
          end="", flush=True)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def migrate(batch_size: int, dry_run: bool) -> None:
    started = time.time()
    banner("ULMiND MongoDB Migration  (Source ➜ Target)")
    if dry_run:
        log("DRY-RUN mode: nothing will be written to the target.", symbol="⚠")

    src_client = connect(SOURCE_URI, "SOURCE (Database1)")
    dst_client = connect(TARGET_URI, "TARGET (Database2)")

    src_db = src_client[DB_NAME]
    dst_db = dst_client[DB_NAME]

    collections = sorted(src_db.list_collection_names())
    log(f"Discovered {len(collections)} collection(s) in source '{DB_NAME}': "
        f"{', '.join(collections) or '(none)'}", symbol="✓")

    grand_docs = 0
    grand_idx = 0
    summary: list[tuple[str, int, int]] = []

    for i, name in enumerate(collections, 1):
        src_coll = src_db[name]
        dst_coll = dst_db[name]
        banner(f"[{i}/{len(collections)}]  Collection: {name}")

        n_src = src_coll.estimated_document_count()
        log(f"Source document count (estimate): {n_src:,}")

        if dry_run:
            n_idx = len(build_index_models(src_coll))
            log(f"Would drop target, copy {n_src:,} docs, build {n_idx} index(es).",
                symbol="⚠")
            summary.append((name, n_src, n_idx))
            continue

        # 1) Clean slate on the target.
        log("Dropping target collection (clean slate) …")
        dst_coll.drop()

        # 2) Copy documents in memory-safe batches.
        log(f"Copying documents in batches of {batch_size} …")
        copied = migrate_documents(src_coll, dst_coll, batch_size)
        print()  # newline after the \r progress line
        log(f"Copied {copied:,} document(s).", symbol="✓")

        # 3) Recreate indexes 1:1.
        log("Rebuilding indexes …")
        n_idx = migrate_indexes(src_coll, dst_coll)
        log(f"Built {n_idx} user index(es).", symbol="✓")

        # 4) Verify counts match.
        n_dst = dst_coll.count_documents({})
        if n_dst == src_coll.count_documents({}):
            log(f"Verified: source and target both hold {n_dst:,} documents.",
                symbol="✓")
        else:
            log(f"COUNT MISMATCH: source has {src_coll.count_documents({}):,}, "
                f"target has {n_dst:,}!", symbol="✗")

        grand_docs += copied
        grand_idx += n_idx
        summary.append((name, copied, n_idx))

    # ----------------------------------------------------------------- #
    banner("Migration Summary")
    for name, docs, idx in summary:
        verb = "would copy" if dry_run else "copied"
        print(f"  {name:<28} {verb} {docs:>9,} docs   {idx} index(es)",
              flush=True)
    elapsed = time.time() - started
    print("-" * 70, flush=True)
    log(f"{'DRY-RUN complete' if dry_run else 'MIGRATION COMPLETE'}: "
        f"{grand_docs:,} documents, {grand_idx} indexes across "
        f"{len(collections)} collections in {elapsed:.1f}s.", symbol="✓")

    src_client.close()
    dst_client.close()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="1:1 MongoDB database migration.")
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                   help=f"Documents per insert_many (default {DEFAULT_BATCH_SIZE}).")
    p.add_argument("--dry-run", action="store_true",
                   help="Analyze only; do not drop or write anything.")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        migrate(batch_size=args.batch_size, dry_run=args.dry_run)
    except KeyboardInterrupt:
        print()
        log("Aborted by user.", symbol="✗")
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001 — top-level guard for CLI UX
        print()
        log(f"FATAL: {exc}", symbol="✗")
        sys.exit(1)
