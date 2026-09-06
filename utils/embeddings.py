# utils/embeddings.py

import json
from pathlib import Path

import numpy as np
import streamlit as st
from sentence_transformers import SentenceTransformer


# ============================================================
# Configuration
# ============================================================

MODEL_NAME = "intfloat/multilingual-e5-small"

# Minimum cosine similarity required to consider a chunk relevant.
MIN_SIMILARITY = 0.84

BASE_DIR = Path(__file__).resolve().parent.parent

CHUNKS_PATH = BASE_DIR / "data" / "chunks.json"


# ============================================================
# Load Chunks
# ============================================================

@st.cache_data
def load_chunks():
    """
    Load RAG chunks from chunks.json.
    """

    if not CHUNKS_PATH.exists():
        raise FileNotFoundError(
            f"chunks.json not found at: {CHUNKS_PATH}"
        )

    with open(
        CHUNKS_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        chunks = json.load(f)

    if not isinstance(chunks, list):
        raise ValueError(
            "chunks.json must contain a list of chunks."
        )

    return chunks


# ============================================================
# Load Embedding Model
# ============================================================

@st.cache_resource
def load_embedding_model():
    """
    Load the pretrained multilingual E5 embedding model.

    The model is downloaded automatically from Hugging Face
    on the first run and then cached locally.
    """

    model = SentenceTransformer(
        MODEL_NAME
    )

    return model


# ============================================================
# Build Embedding Index
# ============================================================

@st.cache_resource
def build_index():
    """
    Build embeddings for all document chunks.

    E5 requires:
        query:   for user questions
        passage: for document chunks
    """

    # Load document chunks
    chunks = load_chunks()

    # Load pretrained embedding model
    model = load_embedding_model()

    # Prepare passages for E5
    passages = [
        f"passage: {chunk.get('text', '')}"
        for chunk in chunks
    ]

    # Generate embeddings
    embeddings = model.encode(
        passages,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )

    return {
        "chunks": chunks,
        "embeddings": embeddings,
        "model": model,
    }


# ============================================================
# Semantic Search
# ============================================================

def search(query, k=4):
    """
    Perform semantic search over the document chunks.

    Parameters:
        query : str
            User's question.

        k : int
            Number of top results to return.

    Returns:
        list
            Relevant chunks with similarity scores.
    """

    # Validate query
    if not query or not query.strip():
        return []

    query = query.strip()

    # Load index
    index = build_index()

    model = index["model"]
    chunks = index["chunks"]
    document_embeddings = index["embeddings"]

    # --------------------------------------------------------
    # Encode user query
    # --------------------------------------------------------
    #
    # E5 requires the "query:" prefix for questions.
    #

    query_embedding = model.encode(
        f"query: {query}",
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )

    # --------------------------------------------------------
    # Calculate cosine similarity
    # --------------------------------------------------------
    #
    # Because both query and document embeddings are normalized,
    # dot product = cosine similarity.
    #

    similarities = np.dot(
        document_embeddings,
        query_embedding
    )

    # --------------------------------------------------------
    # Select top-k results
    # --------------------------------------------------------

    k = min(
        max(1, k),
        len(chunks)
    )

    top_indices = np.argsort(
        similarities
    )[::-1][:k]

    # --------------------------------------------------------
    # Build results
    # --------------------------------------------------------

    results = []

    for idx in top_indices:

        similarity = float(
            similarities[idx]
        )

        # Ignore weakly related chunks
        if similarity < MIN_SIMILARITY:
            continue

        # Copy chunk so original data is not modified
        chunk = dict(
            chunks[idx]
        )

        # Add similarity score
        chunk["similarity"] = similarity

        results.append(
            chunk
        )

    return results


# ============================================================
# Debug Search
# ============================================================

def debug_search(query, k=5):
    """
    Debug helper to inspect semantic search results.

    Useful during development/testing.
    """

    results = search(
        query,
        k=k
    )

    print("\n" + "=" * 80)
    print(f"QUERY: {query}")
    print("=" * 80)

    if not results:
        print("No relevant results found.")
        print("=" * 80)
        return []

    for rank, item in enumerate(
        results,
        start=1
    ):

        similarity = item.get(
            "similarity",
            0.0
        )

        page = item.get(
            "page",
            "Unknown"
        )

        section = item.get(
            "section",
            "Unknown"
        )

        text = item.get(
            "text",
            ""
        )

        print(
            f"\n#{rank} "
            f"| similarity={similarity:.4f} "
            f"| page={page} "
            f"| section={section}"
        )

        print("-" * 80)
        print(
            text[:500]
        )

    print("\n" + "=" * 80)

    return results