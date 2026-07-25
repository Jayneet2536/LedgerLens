import math
import os
import re
from typing import Iterable

from langchain_core.documents import Document


MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "6000"))
CHARS_PER_TOKEN = 4
MIN_RERANKED_DOCUMENTS = int(os.getenv("MIN_RERANKED_DOCUMENTS", "3"))
MAX_RERANKED_DOCUMENTS = int(os.getenv("MAX_RERANKED_DOCUMENTS", "5"))

STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "company",
    "did",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "into",
    "its",
    "management",
    "much",
    "our",
    "the",
    "their",
    "this",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "with",
    "year",
}


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / CHARS_PER_TOKEN))


def _truncate_to_budget(text: str, token_budget: int) -> str:
    char_budget = max(1, token_budget * CHARS_PER_TOKEN)
    if len(text) <= char_budget:
        return text

    candidate = text[:char_budget].rstrip()
    sentence_end = max(candidate.rfind("."), candidate.rfind("?"), candidate.rfind("!"))
    if sentence_end > char_budget // 2:
        return candidate[: sentence_end + 1].strip()
    return candidate.strip()


def build_capped_context(
    documents: Iterable[Document],
    token_budget: int = MAX_CONTEXT_TOKENS,
) -> tuple[str, list[Document]]:
    remaining_tokens = token_budget
    used_documents: list[Document] = []
    context_blocks: list[str] = []

    for document in documents:
        content = document.page_content.strip()
        if not content:
            continue

        document_tokens = estimate_tokens(content)
        if document_tokens <= remaining_tokens:
            used_documents.append(document)
            context_blocks.append(content)
            remaining_tokens -= document_tokens
            continue

        if not used_documents:
            truncated_content = _truncate_to_budget(content, remaining_tokens)
            truncated_document = Document(
                page_content=truncated_content,
                metadata=document.metadata,
            )
            used_documents.append(truncated_document)
            context_blocks.append(truncated_content)
        break

    return "\n\n".join(context_blocks), used_documents


def rerank_documents_for_question(
    question: str,
    documents: Iterable[Document],
    min_documents: int = MIN_RERANKED_DOCUMENTS,
    max_documents: int = MAX_RERANKED_DOCUMENTS,
) -> list[Document]:
    candidates = list(documents)
    if len(candidates) <= min_documents:
        return candidates

    query_terms = _important_terms(question)
    query_phrases = _query_phrases(question, query_terms)
    if not query_terms:
        return candidates[:max_documents]

    scored = [
        (_document_relevance_score(document.page_content, query_terms, query_phrases), index, document)
        for index, document in enumerate(candidates)
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))

    positive_matches = [item for item in scored if item[0] > 0]
    selected = positive_matches[:max_documents]

    if len(selected) < min_documents:
        seen_indexes = {index for _, index, _ in selected}
        for item in scored:
            if item[1] in seen_indexes:
                continue
            selected.append(item)
            seen_indexes.add(item[1])
            if len(selected) >= min_documents:
                break

    return [document for _, _, document in selected]


def _important_terms(text: str) -> list[str]:
    terms = re.findall(r"[a-z0-9]+", text.lower())
    return [
        term
        for term in dict.fromkeys(terms)
        if len(term) >= 3 and term not in STOPWORDS
    ]


def _query_phrases(question: str, query_terms: list[str]) -> list[str]:
    normalized_question = " ".join(re.findall(r"[a-z0-9]+", question.lower()))
    phrases = []

    for phrase_size in (3, 2):
        for start in range(0, len(query_terms) - phrase_size + 1):
            phrase = " ".join(query_terms[start : start + phrase_size])
            if phrase in normalized_question:
                phrases.append(phrase)

    return phrases


def _document_relevance_score(content: str, query_terms: list[str], query_phrases: list[str]) -> float:
    normalized_content = " ".join(re.findall(r"[a-z0-9]+", content.lower()))
    content_terms = set(normalized_content.split())
    score = 0.0

    for term in query_terms:
        if term not in content_terms:
            continue
        if term.isdigit():
            score += 2.0
        else:
            score += 1.0

    for phrase in query_phrases:
        if phrase in normalized_content:
            score += 4.0

    return score
