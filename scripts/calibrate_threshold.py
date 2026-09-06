#!/usr/bin/env python3
"""
scripts/calibrate_threshold.py
===============================
Print retrieval distances for a set of sample questions (in Arabic and
English, plus one deliberately unrelated control question) so you can pick
a sensible RAG_DISTANCE_THRESHOLD after switching embedding providers.

Usage:
    export GEMINI_API_KEY=your_api_key_here
    python scripts/calibrate_threshold.py

Read the printed distances: on-topic questions should score noticeably
lower (more similar) than the unrelated control question. Set
RAG_DISTANCE_THRESHOLD (in .env / Streamlit secrets) somewhere between the
two clusters — the default in utils/rag.py (0.55) is only a starting
estimate and has not been validated against live API output.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from utils import embeddings as emb
from utils import rag


SAMPLE_QUESTIONS = list(rag.SUGGESTED_QUESTIONS) + [
    "What is the total expenditure?",
    "What are the main sources of revenue?",
    "ما هي عاصمة اليابان؟",  # Unrelated control question - should score poorly.
]


def main():
    if not emb.get_gemini_api_key():
        print(
            "خطأ: GEMINI_API_KEY غير معرف.\n"
            "صدّره في الطرفية أو ضعه في ملف .env محلي قبل تشغيل هذا السكريبت."
        )
        sys.exit(1)

    if not emb.is_index_ready():
        print(
            "تعذر تجهيز فهرس البحث. شغّل scripts/build_embeddings.py أولًا "
            "أو تأكد من صحة GEMINI_API_KEY."
        )
        sys.exit(1)

    for question in SAMPLE_QUESTIONS:
        results = emb.search(question, k=3)
        print(f"\nسؤال: {question}")

        for result in results:
            preview = result["text"][:60].replace("\n", " ")
            print(
                f"  distance={result['distance']:.4f}  "
                f"page={result['page']}  {preview}..."
            )


if __name__ == "__main__":
    main()
