"""
Data utilities for the "موازنتي" project.

This module is responsible for:
- Extracting text from the official Citizen Budget PDF
- Cleaning extracted text
- Splitting text into overlapping chunks
- Assigning sections to PDF pages
- Loading structured budget data
"""

import json
import os
import re

import fitz
import streamlit as st


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data")
PDF_PATH = os.path.join(DATA_DIR, "budget.pdf")
BUDGET_JSON_PATH = os.path.join(DATA_DIR, "budget.json")
CHUNKS_JSON_PATH = os.path.join(DATA_DIR, "chunks.json")


SOURCE_LABEL = "موازنة المواطن 2026/2027 - وزارة المالية المصرية"


# Page ranges are used to provide useful section labels for retrieved sources.
SECTION_MAP = {
    (1, 8): "نظرة عامة",
    (9, 13): "الإطار الاقتصادي والموازنة",
    (14, 20): "الإيرادات والمصروفات",
    (21, 25): "الحماية الاجتماعية",
    (26, 28): "الصحة",
    (29, 31): "التعليم",
    (32, 36): "دعم الأنشطة الاقتصادية",
    (37, 43): "الإصلاحات والسياسات المالية",
    (44, 50): "الدين والعجز",
    (51, 60): "برامج ومبادرات الموازنة",
    (61, 70): "بيانات ومعلومات إضافية",
}


def _clean_text(text: str) -> str:
    """
    Normalize whitespace while preserving meaningful paragraph breaks.
    """
    if not text:
        return ""

    text = text.replace("\u00a0", " ")
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Remove repeated spaces and tabs inside lines.
    text = re.sub(r"[ \t]+", " ", text)

    # Normalize excessive blank lines.
    text = re.sub(r"\n[ \t]*\n+", "\n\n", text)

    return text.strip()


def _split_into_chunks(
    text: str,
    max_chars: int = 900,
    overlap_chars: int = 150,
) -> list:
    """
    Split text into overlapping chunks.

    Paragraph boundaries are preferred so important sentences are less likely
    to be separated from the surrounding context.
    """
    text = _clean_text(text)

    if not text:
        return []

    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero.")

    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError(
            "overlap_chars must be >= 0 and smaller than max_chars."
        )

    paragraphs = [
        paragraph.strip()
        for paragraph in text.split("\n\n")
        if paragraph.strip()
    ]

    chunks = []
    current = ""

    for paragraph in paragraphs:
        if not current:
            current = paragraph
            continue

        candidate = f"{current}\n\n{paragraph}"

        if len(candidate) <= max_chars:
            current = candidate
            continue

        chunks.append(current)

        overlap = current[-overlap_chars:] if overlap_chars else ""

        if overlap:
            # Avoid starting the next chunk in the middle of a word.
            overlap_start = overlap.find(" ")

            if overlap_start != -1:
                overlap = overlap[overlap_start + 1 :]

        current = f"{overlap}\n\n{paragraph}".strip()

        # A very long paragraph may still exceed the chunk limit.
        if len(current) > max_chars:
            while len(current) > max_chars:
                chunks.append(current[:max_chars].strip())

                remaining = current[max_chars - overlap_chars :].strip()
                current = remaining

    if current:
        chunks.append(current)

    return [
        chunk.strip()
        for chunk in chunks
        if chunk.strip()
    ]


def _section_for_page(page_number: int) -> str:
    """Return the logical section assigned to a PDF page."""
    for (start_page, end_page), section in SECTION_MAP.items():
        if start_page <= page_number <= end_page:
            return section

    return "غير محدد"


def build_chunks_from_pdf():
    """
    Extract the official PDF and rebuild chunks.json.

    The PDF remains the source of truth. Generated chunks are only an
    intermediate representation used by the RAG pipeline.
    """
    if not os.path.exists(PDF_PATH):
        raise FileNotFoundError(
            f"Official budget PDF was not found: {PDF_PATH}"
        )

    os.makedirs(DATA_DIR, exist_ok=True)

    chunks = []

    with fitz.open(PDF_PATH) as document:
        for page_index, page in enumerate(document):
            page_number = page_index + 1

            raw_text = page.get_text("text")
            text = _clean_text(raw_text)

            if not text:
                continue

            section = _section_for_page(page_number)

            page_chunks = _split_into_chunks(
                text,
                max_chars=900,
                overlap_chars=150,
            )

            for chunk_index, chunk_text in enumerate(page_chunks):
                chunk_id = f"page_{page_number}_chunk_{chunk_index}"

                chunks.append(
                    {
                        "id": chunk_id,
                        "text": chunk_text,
                        "page": page_number,
                        "section": section,
                        "source": SOURCE_LABEL,
                    }
                )

    with open(
        CHUNKS_JSON_PATH,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            chunks,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return chunks


@st.cache_data
def load_budget_data():
    """Load manually verified structured budget data."""
    if not os.path.exists(BUDGET_JSON_PATH):
        raise FileNotFoundError(
            f"Structured budget data was not found: {BUDGET_JSON_PATH}"
        )

    with open(
        BUDGET_JSON_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


@st.cache_data
def load_chunks():
    """
    Load generated PDF chunks.

    If chunks.json does not exist, rebuild it directly from the official PDF.
    """
    if not os.path.exists(CHUNKS_JSON_PATH):
        return build_chunks_from_pdf()

    with open(
        CHUNKS_JSON_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        chunks = json.load(file)

    if not isinstance(chunks, list):
        raise ValueError("chunks.json must contain a list of chunks.")

    return chunks


def rebuild_chunks():
    """
    Force a fresh chunk extraction from the official PDF.

    This is useful after changing chunking settings or replacing the PDF.
    """
    load_chunks.clear()

    if os.path.exists(CHUNKS_JSON_PATH):
        os.remove(CHUNKS_JSON_PATH)

    return build_chunks_from_pdf()


if __name__ == "__main__":
    generated_chunks = build_chunks_from_pdf()

    print(f"PDF: {PDF_PATH}")
    print(f"Generated chunks: {len(generated_chunks)}")
    print(f"Output: {CHUNKS_JSON_PATH}")