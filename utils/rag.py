# rag.py

import json
import os
from pathlib import Path

import streamlit as st

from utils.embeddings import search


# ============================================================
# Configuration
# ============================================================

DEFAULT_TOP_K = 4

GEMINI_MODEL_NAME = "gemini-2.5-flash"

NOT_FOUND_MSG = (
    "المعلومة دي مش موجودة في البيانات الرسمية المتاحة عندي."
)

LOW_CONFIDENCE_MSG = (
    "لم أجد معلومة موثوقة عن هذا السؤال في موازنة المواطن المتاحة."
)


# ============================================================
# Paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

BUDGET_JSON_PATH = BASE_DIR / "data" / "budget.json"


# ============================================================
# Suggested Questions
# ============================================================

SUGGESTED_QUESTIONS = [
    "إيه هي الموازنة العامة؟",
    "ما قيمة المصروفات العامة في موازنة 2026/2027؟",
    "ما هي أولويات موازنة 2026/2027؟",
    "ما حجم الإيرادات العامة؟",
]


# ============================================================
# Gemini API Key
# ============================================================

def get_gemini_api_key():
    """
    Get Gemini API key from Streamlit secrets
    or environment variables.
    """

    # Streamlit Cloud / local secrets
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")

        if api_key:
            return api_key

    except Exception:
        pass

    # Environment variable
    api_key = os.getenv("GEMINI_API_KEY")

    return api_key


# ============================================================
# Gemini Model
# ============================================================

def get_gemini_model():
    """
    Return the Gemini model name.
    """

    return GEMINI_MODEL_NAME


# ============================================================
# LLM Availability
# ============================================================

def is_llm_available():
    """
    Check whether Gemini API key is available.
    """

    api_key = get_gemini_api_key()

    return bool(api_key)


# ============================================================
# Low Confidence Check
# ============================================================

def _is_low_confidence(retrieved):
    """
    The E5 embedding search already applies
    MIN_SIMILARITY filtering.

    If no relevant chunks are returned,
    the retrieval confidence is considered low.
    """

    return not retrieved


# ============================================================
# Retrieve
# ============================================================

def retrieve(question, k=DEFAULT_TOP_K):
    """
    Retrieve the most relevant document chunks
    using multilingual E5 embeddings.
    """

    if not question or not question.strip():
        return []

    question = question.strip()

    return search(
        question,
        k=max(1, k)
    )


# ============================================================
# Build Context
# ============================================================

def build_context(retrieved):
    """
    Build the context sent to Gemini.
    """

    if not retrieved:
        return ""

    context_parts = []

    for item in retrieved:

        page = item.get("page", "غير معروف")
        section = item.get("section", "غير محدد")
        text = item.get("text", "").strip()

        if not text:
            continue

        context_parts.append(
            f"[صفحة {page} - {section}]\n{text}"
        )

    return "\n\n".join(context_parts)


# ============================================================
# Build Sources
# ============================================================

def build_sources(retrieved):
    """
    Build a unique list of sources.
    """

    if not retrieved:
        return []

    sources = []
    seen = set()

    for item in retrieved:

        page = item.get("page")
        section = item.get("section", "غير محدد")

        key = (page, section)

        if key in seen:
            continue

        seen.add(key)

        sources.append(
            {
                "page": page,
                "section": section,
            }
        )

    return sources


# ============================================================
# Build Prompt
# ============================================================

def build_prompt(question, context, level="ببساطة"):
    """
    Build the Gemini prompt.
    """

    level_instructions = {
        "ببساطة": (
            "اشرح الإجابة ببساطة وباختصار، وبأسلوب مناسب للمواطن العادي."
        ),
        "لطالب": (
            "اشرح الإجابة بشكل متوسط، مع توضيح المصطلحات والأرقام المهمة."
        ),
        "بتفصيل": (
            "اشرح الإجابة بتفصيل أكبر مع عرض الأرقام والسياق الموجود في الوثيقة."
        ),
    }

    explanation_style = level_instructions.get(
        level,
        level_instructions["ببساطة"]
    )

    prompt = f"""
أنت مساعد ذكي متخصص في "موازنة المواطن المصرية".

المصدر الرسمي الوحيد للمعلومات هو السياق الموجود بالأسفل.

قواعد مهمة جدًا:
- أجب فقط باستخدام المعلومات الموجودة في السياق.
- لا تستخدم معلومات من خارج السياق.
- لا تخمّن.
- لا تخترع أرقامًا.
- لا تخترع مصادر أو صفحات.
- إذا كانت الإجابة غير موجودة في السياق، قل بوضوح:
  "المعلومة دي مش موجودة في البيانات الرسمية المتاحة عندي."
- حافظ على الأرقام والوحدات كما وردت في المصدر.
- استخدم العربية الواضحة.
- إذا كان السؤال باللهجة المصرية، يمكن الإجابة باللهجة المصرية.
- {explanation_style}

السياق الرسمي:

--------------------
{context}
--------------------

سؤال المستخدم:

{question}

الإجابة:
"""

    return prompt


# ============================================================
# Call Gemini
# ============================================================

def call_llm(prompt):
    """
    Send the prompt to Gemini and return the generated answer.
    """

    api_key = get_gemini_api_key()

    if not api_key:
        return None

    try:

        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=60000
            )
        )

        response = client.models.generate_content(
            model=get_gemini_model(),
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2
            )
        )

        if response is None:
            return None

        text = getattr(
            response,
            "text",
            None
        )

        if text:
            return text.strip()

        return None

    except Exception as e:

        print(
            f"[Gemini Error] {type(e).__name__}: {e}"
        )

        return None


# ============================================================
# Fallback Answer
# ============================================================

def build_fallback_answer(retrieved):
    """
    Return retrieved document snippets when
    Gemini is unavailable.
    """

    if not retrieved:
        return NOT_FOUND_MSG

    answers = []

    for item in retrieved:

        text = item.get(
            "text",
            ""
        ).strip()

        if not text:
            continue

        page = item.get(
            "page",
            "غير معروف"
        )

        answers.append(
            f"من الصفحة {page}:\n{text}"
        )

    if not answers:
        return NOT_FOUND_MSG

    return "\n\n".join(answers)


# ============================================================
# Main RAG Answer Function
# ============================================================

def answer_question(
    question,
    level="ببساطة",
    top_k=DEFAULT_TOP_K
):
    """
    Complete RAG pipeline:

    1. Retrieve chunks using E5.
    2. Check retrieval confidence.
    3. Build context.
    4. Send context to Gemini.
    5. Return answer and sources.
    """

    # --------------------------------------------------------
    # Validate question
    # --------------------------------------------------------

    if not question or not question.strip():

        return {
            "answer": "من فضلك اكتب سؤالك أولًا.",
            "sources": [],
            "retrieved": [],
            "confidence": 0.0,
        }

    question = question.strip()

    # --------------------------------------------------------
    # Retrieval
    # --------------------------------------------------------

    retrieved = retrieve(
        question,
        k=top_k
    )

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    if _is_low_confidence(retrieved):

        return {
            "answer": LOW_CONFIDENCE_MSG,
            "sources": [],
            "retrieved": [],
            "confidence": 0.0,
        }

    # --------------------------------------------------------
    # Best similarity
    # --------------------------------------------------------

    similarities = [
        float(
            item.get(
                "similarity",
                0.0
            )
        )
        for item in retrieved
    ]

    best_similarity = (
        max(similarities)
        if similarities
        else 0.0
    )

    # --------------------------------------------------------
    # Build context
    # --------------------------------------------------------

    context = build_context(
        retrieved
    )

    # --------------------------------------------------------
    # Build prompt
    # --------------------------------------------------------

    prompt = build_prompt(
        question,
        context,
        level=level
    )

    # --------------------------------------------------------
    # Gemini
    # --------------------------------------------------------

    answer = call_llm(
        prompt
    )

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    if not answer:

        answer = build_fallback_answer(
            retrieved
        )

    # --------------------------------------------------------
    # Sources
    # --------------------------------------------------------

    sources = build_sources(
        retrieved
    )

    # --------------------------------------------------------
    # Return
    # --------------------------------------------------------

    return {
        "answer": answer,
        "sources": sources,
        "retrieved": retrieved,
        "confidence": best_similarity,
    }


# ============================================================
# Load Structured Budget Data
# ============================================================

def load_budget_data():
    """
    Load structured budget data from budget.json.
    """

    if not BUDGET_JSON_PATH.exists():
        return None

    try:

        with open(
            BUDGET_JSON_PATH,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception as e:

        print(
            f"[Budget JSON Error] {type(e).__name__}: {e}"
        )

        return None


# ============================================================
# Structured Data Calculations
# ============================================================

def calculate_from_structured_data(
    question,
    budget=None
):
    """
    Handle deterministic questions using structured data.

    This function is intentionally conservative.

    If no safe deterministic calculation can be made,
    return None so that the normal RAG pipeline handles
    the question.
    """

    if not question:
        return None

    # --------------------------------------------------------
    # Use budget passed from app.py
    # --------------------------------------------------------

    if budget is None:
        budget = load_budget_data()

    if not budget:
        return None

    # --------------------------------------------------------
    # No deterministic calculation implemented yet.
    #
    # Returning None is intentional:
    # the question will continue to the RAG pipeline.
    # --------------------------------------------------------

    return None