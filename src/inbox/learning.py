"""
Learning engine: topic tagging, TF-IDF similarity search, edit distance tracking.
Pure Python stdlib only — no scikit-learn, no external NLP libraries.
"""
import re
import math
from collections import Counter
from typing import List, Dict, Optional, Any


# ─── Topic Tagging ────────────────────────────────────────────────────────────

def extract_topic_tags(text: str, topic_keywords: Dict[str, list]) -> List[str]:
    """
    Keyword-based topic tagging. Returns list of matching topics, sorted by
    number of keyword hits (most matches first).
    """
    text_lower = text.lower()
    hits: Dict[str, int] = {}
    for topic, keywords in topic_keywords.items():
        count = sum(1 for kw in keywords if kw.lower() in text_lower)
        if count > 0:
            hits[topic] = count
    if not hits:
        return ["other"]
    return sorted(hits.keys(), key=lambda t: hits[t], reverse=True)


# ─── TF-IDF Similarity ────────────────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _compute_tf(tokens: List[str]) -> Dict[str, float]:
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    return {word: count / total for word, count in counts.items()}


def _compute_idf(documents: List[List[str]]) -> Dict[str, float]:
    """Compute IDF scores across a corpus of tokenized documents."""
    n = len(documents)
    if n == 0:
        return {}
    doc_freq: Dict[str, int] = {}
    for doc in documents:
        for word in set(doc):
            doc_freq[word] = doc_freq.get(word, 0) + 1
    return {word: math.log((1 + n) / (1 + df)) + 1 for word, df in doc_freq.items()}


def _tfidf_vector(tokens: List[str], idf: Dict[str, float]) -> Dict[str, float]:
    tf = _compute_tf(tokens)
    return {word: tf_val * idf.get(word, 1.0) for word, tf_val in tf.items()}


def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a) & set(vec_b)
    if not common:
        return 0.0
    dot = sum(vec_a[w] * vec_b[w] for w in common)
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def find_similar_responses(
    query_text: str,
    past_responses: List[Dict[str, Any]],
    course_family: Optional[str] = None,
    current_semester: Optional[str] = None,
    max_results: int = 5,
    threshold: float = 0.15,
) -> List[Dict[str, Any]]:
    """
    Find past responses similar to the incoming message.

    Ranks by: TF-IDF similarity × temporal decay weight × edit quality bonus.

    Args:
        query_text: The incoming student message text.
        past_responses: List of dicts from db.get_sent_responses().
        course_family: Prefer responses from the same course family.
        current_semester: Tag for scoring semester freshness.
        max_results: Maximum number of results to return.
        threshold: Minimum similarity score (0.0–1.0).

    Returns:
        List of response dicts enriched with 'similarity', 'decay_weight', 'score', 'days_ago'.
    """
    from datetime import datetime

    if not past_responses:
        return []

    # Build corpus: query + all past incoming messages
    all_texts = [query_text] + [r.get("incoming_message", "") for r in past_responses]
    tokenized = [_tokenize(t) for t in all_texts]
    idf = _compute_idf(tokenized)

    query_vec = _tfidf_vector(tokenized[0], idf)

    now = datetime.utcnow()
    scored = []

    for i, resp in enumerate(past_responses):
        if not resp.get("final_sent"):
            continue

        # TF-IDF similarity
        doc_vec = _tfidf_vector(tokenized[i + 1], idf)
        similarity = _cosine_similarity(query_vec, doc_vec)
        if similarity < threshold:
            continue

        # Temporal decay
        days_ago = 999
        sent_at_str = resp.get("sent_at")
        if sent_at_str:
            try:
                sent_dt = datetime.fromisoformat(sent_at_str.split(".")[0])
                days_ago = (now - sent_dt).days
            except (ValueError, AttributeError):
                pass

        decay = _temporal_decay(days_ago, current_semester, resp.get("semester"))

        # Edit quality: low edit_ratio = user barely changed it = good draft
        edit_ratio = resp.get("edit_ratio")
        quality_bonus = 1.0
        if edit_ratio is not None:
            quality_bonus = 1.0 + (1.0 - min(edit_ratio, 1.0)) * 0.3  # up to 1.3x

        # Course family bonus
        family_bonus = 1.2 if (course_family and resp.get("course_family") == course_family) else 1.0

        final_score = similarity * decay * quality_bonus * family_bonus

        scored.append({
            **resp,
            "similarity": round(similarity, 3),
            "decay_weight": round(decay, 2),
            "score": round(final_score, 3),
            "days_ago": days_ago,
        })

    # Sort by final score descending, cap results
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:max_results]


def _temporal_decay(days_ago: int, current_semester: Optional[str], response_semester: Optional[str]) -> float:
    """
    Decay weight based on age. Previous-semester data gets weight 0.1
    regardless of recency within that semester.
    """
    if current_semester and response_semester and response_semester != current_semester:
        return 0.1  # Previous semester

    if days_ago <= 14:
        return 1.0
    elif days_ago <= 28:
        return 0.8
    elif days_ago <= 56:
        return 0.6
    elif days_ago <= 90:
        return 0.3
    else:
        return 0.15


# ─── Edit Distance (Levenshtein) ──────────────────────────────────────────────

def levenshtein_distance(s1: str, s2: str) -> int:
    """Classic Levenshtein edit distance."""
    if s1 == s2:
        return 0
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)

    # Work on words to be faster and more meaningful for text
    w1 = s1.split()
    w2 = s2.split()

    # Cap at 200 words each for performance
    w1 = w1[:200]
    w2 = w2[:200]

    m, n = len(w1), len(w2)
    dp = list(range(n + 1))

    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if w1[i - 1] == w2[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp

    return dp[n]


def compute_edit_ratio(draft: str, final: str) -> float:
    """
    Normalized edit distance: 0.0 = identical, 1.0 = completely different.
    Uses word-level Levenshtein for meaningful comparison.
    """
    if not draft and not final:
        return 0.0
    if not draft or not final:
        return 1.0
    dist = levenshtein_distance(draft, final)
    max_len = max(len(draft.split()), len(final.split()))
    if max_len == 0:
        return 0.0
    return min(dist / max_len, 1.0)
