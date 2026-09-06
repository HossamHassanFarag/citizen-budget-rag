#!/usr/bin/env python3
"""
scripts/build_embeddings.py
============================
Offline utility to (re)generate the precomputed embedding index for the
official Citizen Budget chunks, using the Google Gemini embedding API.

Usage:
    export GEMINI_API_KEY=your_api_key_here   # or put it in a local .env
    python scripts/build_embeddings.py            # build only if missing/stale
    python scripts/build_embeddings.py --force     # always rebuild

The result is written to data/embeddings/embeddings.npz and
data/embeddings/metadata.json. These files are small (a few hundred KB for
~181 chunks) and are meant to be committed to the repository so that
Streamlit Community Cloud never needs to call the embedding API on
startup — see utils/embeddings.py for the full caching strategy.

data/chunks.json remains the single source of truth: this script only
derives an index from it and never modifies it.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from utils.data import load_chunks
from utils import embeddings as emb


def main():
    parser = argparse.ArgumentParser(
        description="Build/refresh the precomputed budget embedding index.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even if a valid, up-to-date cache already exists.",
    )
    parser.add_argument(
        "--output-dir",
        default=emb.STATIC_EMBEDDINGS_DIR,
        help="Directory to write embeddings.npz/metadata.json into "
        "(default: data/embeddings).",
    )
    args = parser.parse_args()

    if not emb.get_gemini_api_key():
        print(
            "خطأ: GEMINI_API_KEY غير معرف.\n"
            "صدّره في الطرفية أو ضعه في ملف .env محلي قبل تشغيل هذا السكريبت."
        )
        sys.exit(1)

    chunks = load_chunks()

    if not chunks:
        print("خطأ: لا توجد بيانات في data/chunks.json.")
        sys.exit(1)

    chunks_hash = emb.compute_chunks_hash(chunks)
    expected_metadata = emb._expected_metadata(chunks_hash, len(chunks))

    embeddings_path = os.path.join(args.output_dir, "embeddings.npz")
    metadata_path = os.path.join(args.output_dir, "metadata.json")

    if not args.force:
        existing_matrix, existing_metadata = emb._load_npz(
            embeddings_path, metadata_path
        )

        if existing_matrix is not None and emb._metadata_matches(
            existing_metadata, expected_metadata
        ):
            print("الفهرس الحالي محدث بالفعل — لا حاجة لإعادة البناء.")
            print("استخدم --force إذا كنت تريد إعادة البناء رغم ذلك.")
            print(json.dumps(existing_metadata, ensure_ascii=False, indent=2))
            return

    print(f"جاري توليد embeddings لعدد {len(chunks)} جزء عبر Gemini API...")
    print(f"  النموذج: {expected_metadata['model']}")
    print(f"  الأبعاد: {expected_metadata['dimension']}")

    def progress(done, total):
        print(f"  ... {done}/{total}")

    texts = [chunk.get("text", "") for chunk in chunks]
    matrix = emb.embed_documents(texts, progress_callback=progress)

    emb._save_npz(embeddings_path, metadata_path, matrix, expected_metadata)

    print("\nتم الانتهاء بنجاح.")
    print(f"  المزوّد: {expected_metadata['provider']}")
    print(f"  النموذج: {expected_metadata['model']}")
    print(f"  عدد الأجزاء: {expected_metadata['chunk_count']}")
    print(f"  الأبعاد: {expected_metadata['dimension']}")
    print(f"  بصمة البيانات (hash): {expected_metadata['chunks_hash'][:16]}...")
    print(f"  الملفات المُنشأة:\n    {embeddings_path}\n    {metadata_path}")
    print(
        "\nلا تنسَ الالتزام (commit) بهذين الملفين في git حتى لا يحتاج التطبيق "
        "لاستدعاء واجهة برمجة التطبيقات عند كل تشغيل على Streamlit Cloud."
    )


if __name__ == "__main__":
    main()
