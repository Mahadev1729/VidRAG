"""
llm/self_rag.py
===============
Self-RAG and Corrective RAG (CRAG) adaptive retrieval pipeline.

Features:
1. Fast Document Relevance Grading: Evaluates whether initial vector chunks
   contain the information needed to answer the question.
2. Adaptive Query Rewriting: When retrieval is weak or conversational keywords
   don't match video transcripts, rewrites the query into optimal search phrases
   and re-queries FAISS.
3. Grounding & Hallucination Guardrail: Validates that answer claims and
   timestamp citations are directly supported by transcript chunks.
4. Dynamic Few-Shot Memory: Injects verified past high-rated Q&A pairs.
5. Self-Reflection Trace: Returns a detailed telemetry trace for UI rendering.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from config import (
    ENABLE_SELF_RAG,
    GROQ_EVALUATOR_MODEL,
    GROQ_MODEL,
    TOP_K,
)
from llm.feedback_store import get_verified_examples
from llm.groq_client import get_groq_client
from llm.rag import answer_question as baseline_rag


# ── 1. Document Relevance Grading ─────────────────────────────────────────────

def grade_retrieval(question: str, docs: list) -> Dict[str, Any]:
    """
    Fast LLM grading step to evaluate if retrieved transcript chunks contain
    sufficient information to answer the question.
    """
    if not docs:
        return {"is_relevant": False, "score": 0.0, "reason": "No documents retrieved."}

    context_preview = "\n\n".join(
        f"[Chunk {i+1}]: {doc.page_content[:800]}" for i, doc in enumerate(docs)
    )

    system_prompt = (
        "You are an expert retrieval grader. Your job is to assess whether the provided "
        "video transcript excerpts contain relevant information or context to answer the user's question.\n"
        "Be lenient on partial answers or semantic matches (since video speech is conversational).\n"
        "Return ONLY a JSON object with keys:\n"
        '{"is_relevant": true/false, "score": 0.0-1.0, "reason": "brief 1-sentence explanation"}'
    )

    user_prompt = f"""QUESTION: {question}

TRANSCRIPT EXCERPTS:
{context_preview}

GRADE JSON:"""

    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model=GROQ_EVALUATOR_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return {
            "is_relevant": bool(data.get("is_relevant", True)),
            "score": float(data.get("score", 0.8)),
            "reason": str(data.get("reason", "Evaluation complete.")),
        }
    except Exception as e:
        print(f"[SELF_RAG] Document grading error: {e}")
        # Default to True on evaluator failure to avoid blocking generation
        return {"is_relevant": True, "score": 0.75, "reason": "Grading skipped (fallback)."}


# ── 2. Adaptive Query Rewriting ───────────────────────────────────────────────

def rewrite_query(question: str) -> List[str]:
    """
    Reformulate the user's query into 2 alternative search phrases
    tailored to how speakers talk in video transcripts.
    """
    system_prompt = (
        "You are a search query optimizer for YouTube video transcripts.\n"
        "Spoken video transcripts often use conversational phrasing, synonyms, or explanations rather than keyword jargon.\n"
        "Generate 2 diverse alternative search queries that capture the semantic intent of the original question.\n"
        "Return ONLY a JSON object with key:\n"
        '{"queries": ["query 1", "query 2"]}'
    )

    user_prompt = f"ORIGINAL QUESTION: {question}\n\nOPTIMIZED QUERIES JSON:"

    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model=GROQ_EVALUATOR_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        queries = data.get("queries", [])
        if isinstance(queries, list) and queries:
            return [str(q).strip() for q in queries if str(q).strip()][:2]
        return [question]
    except Exception as e:
        print(f"[SELF_RAG] Query rewriting error: {e}")
        return [question]


# ── 3. Grounding & Hallucination Guardrail ────────────────────────────────────

def verify_grounding(question: str, answer: str, docs: list) -> Dict[str, Any]:
    """
    Verify whether the answer and referenced timestamps are grounded
    in the retrieved transcript chunks.
    """
    if not docs or not answer:
        return {"is_grounded": True, "confidence": 1.0, "notes": "No docs to verify against."}

    context = "\n\n".join(doc.page_content for doc in docs[:4])

    system_prompt = (
        "You are a hallucination and factual grounding verifier.\n"
        "Check if the answer is faithful to the transcript context without making up external facts.\n"
        "Return ONLY a JSON object with keys:\n"
        '{"is_grounded": true/false, "confidence": 0.0-1.0, "notes": "brief 1-sentence note"}'
    )

    user_prompt = f"""CONTEXT:
{context}

QUESTION:
{question}

ANSWER:
{answer}

VERIFICATION JSON:"""

    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model=GROQ_EVALUATOR_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return {
            "is_grounded": bool(data.get("is_grounded", True)),
            "confidence": float(data.get("confidence", 0.9)),
            "notes": str(data.get("notes", "Grounded in context.")),
        }
    except Exception as e:
        print(f"[SELF_RAG] Grounding verification error: {e}")
        return {"is_grounded": True, "confidence": 0.85, "notes": "Grounding verification skipped."}


# ── 4. Main Corrective RAG Pipeline ──────────────────────────────────────────

def self_corrective_rag_answer(
    vector_store,
    question: str,
    video_id: str = "",
    k: int = TOP_K,
) -> Tuple[str, List[Any], Dict[str, Any]]:
    """
    Execute the full Self-RAG & Corrective RAG pipeline.

    Workflow:
    1. Initial retrieval from FAISS
    2. Fast document grading
    3. If relevance is low: Rewrite query -> Re-retrieve -> Merge unique chunks
    4. Inject verified dynamic few-shot examples (from feedback memory)
    5. Generate grounded response with Groq primary model
    6. Verify answer grounding
    7. Return (answer, source_docs, trace_metadata)

    Returns:
        tuple: (answer_text, source_documents, trace_metadata_dict)
    """
    if not ENABLE_SELF_RAG:
        answer, docs = baseline_rag(vector_store, question, k=k)
        return answer, docs, {"self_rag_enabled": False}

    trace: Dict[str, Any] = {
        "self_rag_enabled": True,
        "original_query": question,
        "initial_k": k,
        "query_rewritten": False,
        "rewritten_queries": [],
        "few_shot_count": 0,
        "grounding_corrected": False,
        "fallback_triggered": False,
    }

    # ── Step 1: Initial Retrieval ─────────────────────────────────────────────
    print(f"[SELF_RAG] Initial search for: '{question[:60]}'")
    source_docs = vector_store.similarity_search(question, k=k)
    trace["initial_chunks_count"] = len(source_docs)

    if not source_docs:
        return "I couldn't find the answer in the video.", [], trace

    # ── Step 2: Document Relevance Grading ───────────────────────────────────
    grade_info = grade_retrieval(question, source_docs)
    trace["initial_grade"] = grade_info
    print(f"[SELF_RAG] Retrieval grade: is_relevant={grade_info['is_relevant']}, score={grade_info['score']:.2f}")

    # ── Step 3: Query Rewriting & Re-Retrieval (if needed) ─────────────────────
    if not grade_info["is_relevant"] or grade_info["score"] < 0.5:
        print("[SELF_RAG] Initial chunks scored low. Triggering adaptive query rewriting...")
        new_queries = rewrite_query(question)
        trace["query_rewritten"] = True
        trace["rewritten_queries"] = new_queries

        # Track seen chunk contents to prevent duplicates
        seen_texts = {doc.page_content for doc in source_docs}
        additional_docs = []

        for alt_query in new_queries:
            alt_results = vector_store.similarity_search(alt_query, k=max(2, k // 2))
            for doc in alt_results:
                if doc.page_content not in seen_texts:
                    seen_texts.add(doc.page_content)
                    additional_docs.append(doc)

        if additional_docs:
            source_docs = source_docs + additional_docs
            print(f"[SELF_RAG] Added {len(additional_docs)} new chunks via rewritten queries.")

    trace["final_chunks_count"] = len(source_docs)

    # ── Step 4: Fetch Dynamic Verified Few-Shot Examples ──────────────────────
    few_shot_examples = []
    if video_id:
        few_shot_examples = get_verified_examples(video_id=video_id, question=question, limit=2)
    trace["few_shot_count"] = len(few_shot_examples)

    # ── Step 5: Build Grounded Prompt ─────────────────────────────────────────
    context = "\n\n".join(doc.page_content for doc in source_docs)

    few_shot_section = ""
    if few_shot_examples:
        few_shot_section = "\nVERIFIED HIGH-QUALITY PAST EXAMPLES:\n"
        for ex in few_shot_examples:
            few_shot_section += f"Q: {ex['question']}\nA: {ex['answer']}\n---\n"

    prompt = f"""You are an AI assistant answering questions about a YouTube video.

Use ONLY the context provided below.

Rules:
1. Do not use outside knowledge.
2. Do not make up information or timestamps.
3. Base your answer strictly on the transcript excerpts provided.
4. If the answer is not present in the context, say exactly:
   "I couldn't find the answer in the video."
{few_shot_section}
CONTEXT:
-------------------------
{context}
-------------------------

QUESTION:
{question}

ANSWER:
"""

    # ── Step 6: Primary LLM Generation ────────────────────────────────────────
    print(f"[SELF_RAG] Generating answer with Groq ({GROQ_MODEL})...")
    client = get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": "Answer questions accurately using only the provided video transcript excerpts.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    answer = response.choices[0].message.content or ""

    # ── Step 7: Grounding Verification ────────────────────────────────────────
    grounding_info = verify_grounding(question, answer, source_docs)
    trace["grounding_check"] = grounding_info
    print(f"[SELF_RAG] Grounding check: is_grounded={grounding_info['is_grounded']}, confidence={grounding_info['confidence']:.2f}")

    # ── Step 8: Active Hallucination Self-Correction Guardrail ─────────────────
    if not grounding_info.get("is_grounded", True) or grounding_info.get("confidence", 1.0) < 0.6:
        print("[SELF_RAG] Grounding verification failed or low confidence. Triggering active correction...")
        trace["grounding_corrected"] = True
        trace["original_hallucinated_answer"] = answer
        trace["correction_reason"] = grounding_info.get("notes", "Unsupported claims detected.")

        correction_prompt = f"""You are an AI assistant answering questions about a YouTube video.
Your previous response contained claims or facts not directly supported by the video transcript.

Feedback / Violation Notes:
{grounding_info.get("notes", "Answer contains ungrounded claims.")}

TRANSCRIPT CONTEXT:
-------------------------
{context}
-------------------------

ORIGINAL QUESTION:
{question}

INSTRUCTIONS:
1. Rewrite the answer using ONLY facts directly stated in the transcript context above.
2. Remove any assumptions, external knowledge, or ungrounded claims.
3. If the transcript context does not contain the answer, reply EXACTLY:
   "I couldn't find the answer in the video."

CORRECTED ANSWER:"""

        try:
            corr_response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a strict, grounded AI assistant that strictly adheres to the provided video transcript.",
                    },
                    {"role": "user", "content": correction_prompt},
                ],
                temperature=0.1,
            )
            corrected_answer = corr_response.choices[0].message.content or ""

            # Re-verify the corrected response
            re_check = verify_grounding(question, corrected_answer, source_docs)
            trace["post_correction_check"] = re_check

            if re_check.get("is_grounded", True) or "couldn't find the answer" in corrected_answer.lower():
                answer = corrected_answer
                trace["grounding_check"] = re_check
                print("[SELF_RAG] Active correction succeeded.")
            else:
                # If still failing grounding check, trigger safe fallback
                print("[SELF_RAG] Second grounding check failed. Activating conservative fallback.")
                answer = "I couldn't find the answer in the video."
                trace["fallback_triggered"] = True
        except Exception as e:
            print(f"[SELF_RAG] Active correction error: {e}")

    return answer, source_docs, trace
