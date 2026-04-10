from __future__ import annotations

import argparse
from pathlib import Path

from .data import load_charter_files, rebuild_collection
from .config import CHARTER_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the citizen charter Chroma collection")
    parser.add_argument(
        "--charter-dir",
        type=Path,
        default=CHARTER_DIR,
        help="Directory containing DNCC and DSCC charter PDFs or text files",
    )
    args = parser.parse_args()
    chunks = load_charter_files(args.charter_dir)
    if not chunks:
        raise SystemExit(f"No charter documents found in {args.charter_dir}")
    count = rebuild_collection(chunks)
    print(f"Indexed {count} charter chunks.")


if __name__ == "__main__":
    main()
