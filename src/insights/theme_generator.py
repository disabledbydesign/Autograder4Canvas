"""
Theme generation and outlier surfacing for the Insights Engine.

Tier logic for theme generation:
  Lightweight: hierarchical — groups of 10-15 records -> theme sets -> meta-synthesis merge
  Medium: groups of 20-25
  Deep: all records in one call (if context allows, else groups of 30+)

Groups formed by embedding cluster (from Quick Analysis), not arbitrarily.
Contradictions are first-class data, not an afterthought.
"""

import json
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Dict, List, Optional

from insights.llm_backend import BackendConfig, parse_json_response, send_text
from insights.models import (
    Contradiction,
    OutlierRecord,
    OutlierReport,
    QuoteRecord,
    SubmissionCodingRecord,
    Theme,
    ThemeSet,
)
from insights.prompts import (
    ANALYSIS_LENS_PROMPT_FRAGMENT,
    INTEREST_AREAS_FRAGMENT,
    OUTLIER_ANALYSIS_PROMPT,
    SYSTEM_PROMPT,
    THEME_GENERATION_PROMPT,
    THEME_META_SYNTHESIS_PROMPT,
)

log = logging.getLogger(__name__)

# Group size limits by tier
_GROUP_SIZES = {
    "lightweight": 5,   # Tiny groups for 8B — larger batches timeout on 20+ students
    "medium": 10,
    "deep_thinking": 30,
}

# Per-call timeout (seconds). If the LLM hasn't responded in this window,
# we fall back to a non-LLM result so the pipeline doesn't stall.
_LLM_CALL_TIMEOUT = 300       # 5 minutes — per-group theme generation
_META_SYNTH_TIMEOUT = 600     # 10 minutes — meta-synthesis merges all groups
                               # and is inherently heavier on large classes

# Max tokens per stage — tight limits prevent MLX from running away.
# These are well above what a correct response needs; they guard against
# the model looping or generating until context exhaustion.
_MAX_TOKENS_THEME = {
    "lightweight":   1200,  # JSON theme set for 5 students: ~600–900 tokens
    "medium":        2000,
    "deep_thinking": 3000,
}
_MAX_TOKENS_META = {
    "lightweight":   1500,  # Merge 8 theme groups: ~900–1200 tokens
    "medium":        2500,
    "deep_thinking": 4096,
}


def _fallback_theme_set_from_records(
    records: List["SubmissionCodingRecord"],
) -> "ThemeSet":
    """Build a ThemeSet without LLM, from tag frequency in the records.

    Used when an LLM call times out so the pipeline can continue.
    """
    tag_counter: Counter = Counter()
    tag_students: Dict[str, List[str]] = {}
    for r in records:
        for tag in r.theme_tags:
            tag_counter[tag] += 1
            tag_students.setdefault(tag, []).append(r.student_id)

    themes = []
    for tag, count in tag_counter.most_common(10):
        if tag in ("insufficient text for analysis",
                    "file upload — text not extracted",
                    "blank submission"):
            continue  # Skip infrastructure tags
        themes.append(Theme(
            name=tag,
            description=f"Auto-grouped from coding tag '{tag}' (LLM timed out)",
            frequency=count,
            student_ids=tag_students.get(tag, []),
            supporting_quotes=[],
            confidence=0.3,
        ))

    if not themes and records:
        # No tags at all — create a single placeholder theme
        themes.append(Theme(
            name="(theme generation timed out)",
            description=(
                f"LLM theme generation timed out for {len(records)} records. "
                f"Try resuming the run or reducing the number of submissions."
            ),
            frequency=len(records),
            student_ids=[r.student_id for r in records],
            supporting_quotes=[],
            confidence=0.1,
        ))

    return ThemeSet(themes=themes, contradictions=[])


def _build_interests_fragment(teacher_interests: list) -> str:
    if not teacher_interests:
        return ""
    summary = ", ".join(f"({i+1}) {interest}" for i, interest in enumerate(teacher_interests[:3]))
    return INTEREST_AREAS_FRAGMENT.format(interests_summary=summary)


def _build_lens_fragment(analysis_lens: Optional[Dict]) -> str:
    if not analysis_lens:
        return ""
    criteria = [f"- {name}: {desc}" for name, desc in analysis_lens.items()]
    if not criteria:
        return ""
    return ANALYSIS_LENS_PROMPT_FRAGMENT.format(lens_criteria="\n".join(criteria))


def _records_to_compact_json(records: List[SubmissionCodingRecord]) -> str:
    """Convert coding records to compact JSON for prompt injection.

    Includes only the fields the theme generator needs, to conserve context.
    Stripped to the minimum viable set: tags, confidence, register, quote.
    readings/concepts/connections removed — they bloat context on 8B models
    and themes are primarily driven by the four retained fields.
    """
    compact = []
    for r in records:
        best_quote = ""
        if r.notable_quotes:
            best_quote = r.notable_quotes[0].text[:200]
        entry = {
            "name": r.student_name,
            "id": r.student_id,
            "tags": r.theme_tags[:5],
            "confidence": {
                t: c for t, c in list(r.theme_confidence.items())[:5]
            } if r.theme_confidence else {},
            "register": r.emotional_register,
            "quote": best_quote,
        }
        compact.append(entry)
    return json.dumps(compact, separators=(",", ":"))


def _group_by_cluster(
    records: List[SubmissionCodingRecord], group_size: int
) -> List[List[SubmissionCodingRecord]]:
    """Group records by embedding cluster, then split into batches of group_size.

    Records without a cluster ID go into an "ungrouped" pool.
    """
    clusters: Dict[int, List[SubmissionCodingRecord]] = {}
    ungrouped: List[SubmissionCodingRecord] = []

    for r in records:
        if r.cluster_id is not None:
            clusters.setdefault(r.cluster_id, []).append(r)
        else:
            ungrouped.append(r)

    # Build groups: keep cluster members together, fill with ungrouped
    groups: List[List[SubmissionCodingRecord]] = []
    current: List[SubmissionCodingRecord] = []

    for cid in sorted(clusters.keys()):
        cluster_records = clusters[cid]
        if len(current) + len(cluster_records) <= group_size:
            current.extend(cluster_records)
        else:
            if current:
                groups.append(current)
            # If cluster is bigger than group_size, split it
            if len(cluster_records) > group_size:
                for i in range(0, len(cluster_records), group_size):
                    groups.append(cluster_records[i: i + group_size])
                current = []
            else:
                current = cluster_records

    # Add ungrouped records
    for r in ungrouped:
        if len(current) >= group_size:
            groups.append(current)
            current = []
        current.append(r)

    if current:
        groups.append(current)

    return groups


def _parse_theme_set(parsed: dict) -> ThemeSet:
    """Convert parsed JSON to a ThemeSet model."""
    themes = []
    for t in parsed.get("themes", []):
        if not isinstance(t, dict):
            continue
        quotes = []
        for q in t.get("supporting_quotes", [])[:4]:
            if isinstance(q, dict) and q.get("text"):
                quotes.append(QuoteRecord(text=q["text"], significance=q.get("significance", "")))
        themes.append(Theme(
            name=t.get("name", ""),
            description=t.get("description", ""),
            frequency=int(t.get("frequency", 0)),
            student_ids=t.get("student_ids", []),
            supporting_quotes=quotes,
            confidence=float(t.get("confidence", 0.5)),
            sub_themes=t.get("sub_themes"),
        ))

    contradictions = []
    for c in parsed.get("contradictions", []):
        if not isinstance(c, dict):
            continue
        contradictions.append(Contradiction(
            description=c.get("description", ""),
            side_a=c.get("side_a", ""),
            side_a_students=c.get("side_a_students", []),
            side_b=c.get("side_b", ""),
            side_b_students=c.get("side_b_students", []),
            pedagogical_significance=c.get("pedagogical_significance", ""),
        ))

    return ThemeSet(themes=themes, contradictions=contradictions)


def _validate_theme_quotes(
    theme_set: ThemeSet, records: List[SubmissionCodingRecord]
) -> ThemeSet:
    """Strip theme quotes that don't appear in any student's coding record.

    Prevents fabrication (#ALGORITHMIC_JUSTICE): a teacher reading
    'Amani said X' and acting on it when X is fiction causes direct harm.
    Checks the first 40 characters as a prefix — generous enough to catch
    minor whitespace/punctuation differences while blocking inventions.
    """
    known_prefixes: set = set()
    for r in records:
        for q in r.notable_quotes:
            prefix = q.text[:40].lower().strip()
            if prefix:  # guard against empty quotes becoming universal matches
                known_prefixes.add(prefix)

    if not known_prefixes:
        return theme_set

    validated_themes = []
    for theme in theme_set.themes:
        valid_quotes = []
        for quote in theme.supporting_quotes:
            prefix = quote.text[:40].lower().strip()
            matched = any(
                prefix in known or known in prefix
                for known in known_prefixes
            )
            if matched:
                valid_quotes.append(quote)
            else:
                log.warning(
                    "Stripped fabricated theme quote from '%s': %.60s...",
                    theme.name, quote.text,
                )
        validated_themes.append(theme.model_copy(update={"supporting_quotes": valid_quotes}))

    return theme_set.model_copy(update={"themes": validated_themes})


def _embedding_dedup_themes(theme_set: ThemeSet, threshold: float = 0.85) -> ThemeSet:
    """Merge near-duplicate themes using sentence-transformer embeddings.

    8B models produce 20-30 fragmented themes on larger classes. This pass
    merges themes whose names+descriptions are semantically ≥ threshold similar,
    keeping the higher-frequency theme and merging student_ids and quotes.

    Falls back silently (returns input unchanged) if sentence-transformers
    is unavailable — the dependency is optional.
    """
    if len(theme_set.themes) < 2:
        return theme_set

    try:
        from sentence_transformers import SentenceTransformer, util as st_util
        import torch
    except ImportError:
        log.debug("sentence-transformers not available — skipping embedding dedup")
        return theme_set

    try:
        model = SentenceTransformer("all-MiniLM-L6-v2")
        texts = [f"{t.name}: {t.description}" for t in theme_set.themes]
        embeddings = model.encode(texts, convert_to_tensor=True, show_progress_bar=False)
        cosine_scores = st_util.cos_sim(embeddings, embeddings)

        merged_into: dict = {}  # index → canonical index
        for i in range(len(theme_set.themes)):
            if i in merged_into:
                continue
            for j in range(i + 1, len(theme_set.themes)):
                if j in merged_into:
                    continue
                if cosine_scores[i][j].item() >= threshold:
                    # Keep the higher-frequency theme as canonical
                    canonical = i if theme_set.themes[i].frequency >= theme_set.themes[j].frequency else j
                    duplicate = j if canonical == i else i
                    merged_into[duplicate] = canonical

        if not merged_into:
            return theme_set

        # Build merged themes
        canonical_themes: dict = {}
        for idx, theme in enumerate(theme_set.themes):
            if idx in merged_into:
                continue
            canonical_themes[idx] = theme

        for dup_idx, can_idx in merged_into.items():
            dup = theme_set.themes[dup_idx]
            can = canonical_themes[can_idx]
            merged_ids = list(dict.fromkeys(can.student_ids + dup.student_ids))
            merged_quotes = (can.supporting_quotes + dup.supporting_quotes)[:3]
            canonical_themes[can_idx] = can.model_copy(update={
                "student_ids": merged_ids,
                "frequency": len(merged_ids),
                "supporting_quotes": merged_quotes,
            })

        deduped = list(canonical_themes.values())
        log.info(
            "Embedding dedup: %d themes → %d (threshold=%.2f, merged=%d)",
            len(theme_set.themes), len(deduped), threshold, len(merged_into),
        )
        return theme_set.model_copy(update={"themes": deduped})

    except Exception as exc:
        log.warning("Embedding dedup failed (%s) — returning original theme set", exc)
        return theme_set


def generate_themes(
    coding_records: List[SubmissionCodingRecord],
    *,
    tier: str,
    backend: BackendConfig,
    assignment_name: str = "",
    analysis_lens: Optional[Dict] = None,
    teacher_interests: Optional[list] = None,
    profile_fragment: str = "",
) -> ThemeSet:
    """Generate themes from coding records.

    Returns a ThemeSet with themes and contradictions.
    """
    if not coding_records:
        return ThemeSet()

    group_size = _GROUP_SIZES.get(tier, 12)
    interests_text = _build_interests_fragment(teacher_interests)
    lens_fragment = _build_lens_fragment(analysis_lens)

    # If all records fit in one group, single call
    if len(coding_records) <= group_size:
        result = _generate_single(
            coding_records, assignment_name, interests_text, lens_fragment,
            backend, profile_fragment, tier=tier,
        )
        result = _validate_theme_quotes(result, coding_records)
        return _embedding_dedup_themes(result)

    # Hierarchical: group -> theme sets -> meta-synthesis
    groups = _group_by_cluster(coding_records, group_size)
    log.info("Theme generation: %d records in %d groups (tier=%s, group_size=%d)",
             len(coding_records), len(groups), tier, group_size)

    group_theme_sets = []
    for i, group in enumerate(groups):
        log.info("  Generating themes for group %d/%d (%d records)", i + 1, len(groups), len(group))
        ts = _generate_single(
            group, assignment_name, interests_text, lens_fragment,
            backend, profile_fragment, tier=tier,
        )
        group_theme_sets.append(ts)

    if len(group_theme_sets) == 1:
        result = _validate_theme_quotes(group_theme_sets[0], coding_records)
        return _embedding_dedup_themes(result)

    # Meta-synthesis: merge group theme sets
    result = _meta_synthesize(
        group_theme_sets, assignment_name, interests_text, backend,
        profile_fragment, tier=tier,
    )
    result = _validate_theme_quotes(result, coding_records)
    return _embedding_dedup_themes(result)


def _generate_single(
    records: List[SubmissionCodingRecord],
    assignment_name: str,
    interests_text: str,
    lens_fragment: str,
    backend: BackendConfig,
    profile_fragment: str = "",
    tier: str = "lightweight",
) -> ThemeSet:
    """Generate themes from a single group of records.

    Wrapped with a timeout — if the LLM call exceeds _LLM_CALL_TIMEOUT
    seconds, returns a fallback ThemeSet built from tag frequencies so the
    pipeline doesn't stall on slow 8B models.
    """
    _max_tok = _MAX_TOKENS_THEME.get(tier, 1200)

    def _inner() -> ThemeSet:
        prompt = THEME_GENERATION_PROMPT.format(
            n_records=len(records),
            assignment_name=assignment_name,
            teacher_interests=interests_text,
            records_json=_records_to_compact_json(records),
            lens_fragment=lens_fragment,
            profile_fragment=profile_fragment,
        )

        raw = send_text(backend, prompt, SYSTEM_PROMPT, max_tokens=_max_tok)
        parsed = parse_json_response(raw)

        if "_parse_error" in parsed:
            log.warning("Theme generation JSON parse failed, retrying")
            from insights.prompts import JSON_REPAIR_PROMPT
            repair = JSON_REPAIR_PROMPT.format(
                raw_response=raw[:2000],
                expected_format='{"themes": [...], "contradictions": [...]}',
            )
            raw2 = send_text(backend, repair, SYSTEM_PROMPT, max_tokens=_max_tok)
            parsed2 = parse_json_response(raw2)
            return _parse_theme_set(parsed2)

        return _parse_theme_set(parsed)

    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(_inner)
        return future.result(timeout=_LLM_CALL_TIMEOUT)
    except FuturesTimeoutError:
        log.warning(
            "Theme generation timed out after %ds for %d records — "
            "falling back to tag-frequency themes",
            _LLM_CALL_TIMEOUT, len(records),
        )
        # Don't wait for the orphaned thread — let it finish on its own
        pool.shutdown(wait=False, cancel_futures=True)
        return _fallback_theme_set_from_records(records)
    except Exception as exc:
        log.warning(
            "Theme generation failed (%s) for %d records — "
            "falling back to tag-frequency themes",
            exc, len(records),
        )
        return _fallback_theme_set_from_records(records)
    finally:
        pool.shutdown(wait=False)


def _meta_synthesize(
    theme_sets: List[ThemeSet],
    assignment_name: str,
    interests_text: str,
    backend: BackendConfig,
    profile_fragment: str = "",
    tier: str = "lightweight",
) -> ThemeSet:
    """Merge multiple ThemeSets into one via meta-synthesis LLM call.

    Wrapped with a timeout — falls back to _manual_merge if the LLM
    exceeds _META_SYNTH_TIMEOUT seconds (longer than per-group timeout
    because meta-synthesis prompts are larger for big classes).
    """
    _max_tok = _MAX_TOKENS_META.get(tier, 1500)

    def _inner() -> ThemeSet:
        sets_json = []
        for i, ts in enumerate(theme_sets):
            sets_json.append({
                "group": i + 1,
                "themes": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "frequency": t.frequency,
                        "student_ids": t.student_ids,
                        "confidence": t.confidence,
                        "supporting_quotes": [
                            {"text": q.text, "significance": q.significance}
                            for q in t.supporting_quotes[:2]
                        ],
                    }
                    for t in ts.themes
                ],
                "contradictions": [
                    {
                        "description": c.description,
                        "side_a": c.side_a,
                        "side_a_students": c.side_a_students,
                        "side_b": c.side_b,
                        "side_b_students": c.side_b_students,
                    }
                    for c in ts.contradictions
                ],
            })

        prompt = THEME_META_SYNTHESIS_PROMPT.format(
            n_groups=len(theme_sets),
            assignment_name=assignment_name,
            teacher_interests=interests_text,
            theme_sets_json=json.dumps(sets_json, indent=1),
            profile_fragment=profile_fragment,
        )

        raw = send_text(backend, prompt, SYSTEM_PROMPT, max_tokens=_max_tok)
        parsed = parse_json_response(raw)

        if "_parse_error" in parsed:
            # Retry once with stripped-down input (names + frequencies only,
            # no quotes, no student_ids) to reduce token pressure that causes
            # truncated JSON.  student_ids can be long arrays with 20+ students;
            # dropping them cuts the input by ~30% on large classes.
            log.warning("Meta-synthesis parse failed — retrying with compact input")
            compact_sets = []
            for i, ts in enumerate(theme_sets):
                compact_sets.append({
                    "group": i + 1,
                    "themes": [
                        {"name": t.name, "frequency": t.frequency}
                        for t in ts.themes
                    ],
                })
            retry_prompt = THEME_META_SYNTHESIS_PROMPT.format(
                n_groups=len(theme_sets),
                assignment_name=assignment_name,
                teacher_interests=interests_text,
                theme_sets_json=json.dumps(compact_sets, indent=1),
                profile_fragment=profile_fragment,
            )
            raw2 = send_text(backend, retry_prompt, SYSTEM_PROMPT, max_tokens=_max_tok)
            parsed = parse_json_response(raw2)
            if "_parse_error" in parsed:
                log.warning("Meta-synthesis retry also failed — combining theme sets manually")
                return _manual_merge(theme_sets)

        return _parse_theme_set(parsed)

    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(_inner)
        return future.result(timeout=_META_SYNTH_TIMEOUT)
    except FuturesTimeoutError:
        log.warning(
            "Meta-synthesis timed out after %ds for %d theme sets — "
            "falling back to manual merge",
            _META_SYNTH_TIMEOUT, len(theme_sets),
        )
        pool.shutdown(wait=False, cancel_futures=True)
        return _manual_merge(theme_sets)
    finally:
        pool.shutdown(wait=False)


def _manual_merge(theme_sets: List[ThemeSet]) -> ThemeSet:
    """Fallback: combine theme sets with token-overlap deduplication.

    When LLM meta-synthesis times out, each cluster group independently
    generated themes — producing near-identical names like "concern for
    public safety" (freq 3) and "concern about public safety" (freq 4)
    side by side.  This non-LLM pass collapses near-duplicates by token
    overlap so the fallback produces coherent output without adding LLM
    latency.

    Two themes are treated as duplicates when their content-word Jaccard
    similarity is ≥ 0.5.  The merged theme keeps the higher-frequency
    name and combines student_ids.
    """
    import re as _re

    def _name_tokens(name: str) -> set:
        # Skip function words that add noise — prepositions, articles, aux verbs
        stop = {"a", "an", "the", "of", "and", "or", "in", "for", "to",
                "with", "on", "by", "at", "is", "are", "its", "their",
                "about", "from", "that", "this", "which", "against"}
        return {t for t in _re.findall(r"[a-z]{3,}", name.lower()) if t not in stop}

    def _are_duplicates(a_name: str, b_name: str) -> bool:
        a_toks = _name_tokens(a_name)
        b_toks = _name_tokens(b_name)
        if not a_toks or not b_toks:
            return False
        # Jaccard similarity: symmetric, avoids false merges when a short
        # theme shares incidental terms with a longer, distinct theme.
        overlap = len(a_toks & b_toks)
        union = len(a_toks | b_toks)
        return overlap / union >= 0.5

    # Collect all themes from all groups
    all_raw = []
    all_contradictions = []
    for ts in theme_sets:
        all_raw.extend(ts.themes)
        all_contradictions.extend(ts.contradictions)

    # Greedy dedup: iterate and merge near-duplicates into a representative
    merged: List = []
    for theme in all_raw:
        matched = False
        for rep in merged:
            if _are_duplicates(rep.name, theme.name):
                # Keep the higher-frequency name; union student_ids
                if theme.frequency > rep.frequency:
                    rep.name = theme.name
                    rep.description = theme.description
                rep.frequency += theme.frequency
                existing_ids = set(rep.student_ids)
                rep.student_ids = rep.student_ids + [
                    sid for sid in theme.student_ids if sid not in existing_ids
                ]
                matched = True
                break
        if not matched:
            merged.append(theme)

    # Sort by frequency descending so teachers see the most common themes first
    merged.sort(key=lambda t: t.frequency, reverse=True)

    return ThemeSet(themes=merged, contradictions=all_contradictions)


# ---------------------------------------------------------------------------
# Outlier surfacing
# ---------------------------------------------------------------------------

def surface_outliers(
    theme_set: ThemeSet,
    coding_records: List[SubmissionCodingRecord],
    embedding_outlier_ids: List[str],
    *,
    tier: str,
    backend: BackendConfig,
    assignment_name: str = "",
) -> OutlierReport:
    """Identify and explain outlier submissions.

    Outliers = records whose theme tags don't match any generated theme
    + records flagged as unique by embedding clustering.
    """
    if not theme_set.themes:
        return OutlierReport()

    theme_names = {t.name.lower() for t in theme_set.themes}
    theme_student_ids = set()
    for t in theme_set.themes:
        theme_student_ids.update(t.student_ids)

    # Find coding-based outliers: records with no theme tag matching a generated theme
    coding_outliers = []
    for r in coding_records:
        if r.student_id in theme_student_ids:
            continue
        # Also check if their tags match any theme name
        matched = any(tag.lower() in theme_names for tag in r.theme_tags)
        if not matched:
            coding_outliers.append(r)

    # Combine with embedding outliers
    outlier_ids = set(r.student_id for r in coding_outliers)
    outlier_ids.update(embedding_outlier_ids)

    outlier_records = [r for r in coding_records if r.student_id in outlier_ids]

    if not outlier_records:
        return OutlierReport()

    # Build themes summary for the prompt
    themes_summary = "\n".join(
        f"- {t.name} ({t.frequency} students): {t.description[:100]}"
        for t in theme_set.themes
    )

    # Build outlier data for the prompt
    outliers_data = []
    for r in outlier_records:
        quotes = [{"text": q.text, "significance": q.significance} for q in r.notable_quotes[:2]]
        outliers_data.append({
            "student_id": r.student_id,
            "student_name": r.student_name,
            "theme_tags": r.theme_tags,
            "emotional_register": r.emotional_register,
            "notable_quotes": quotes,
            "in_embedding_outliers": r.student_id in embedding_outlier_ids,
        })

    prompt = OUTLIER_ANALYSIS_PROMPT.format(
        assignment_name=assignment_name,
        themes_summary=themes_summary,
        outliers_json=json.dumps(outliers_data, indent=1),
    )

    try:
        raw = send_text(backend, prompt, SYSTEM_PROMPT)
        parsed = parse_json_response(raw)
    except Exception as exc:
        log.warning("Outlier analysis LLM call failed (%s) — using minimal report", exc)
        return _minimal_outlier_report(outlier_records, embedding_outlier_ids)

    if "_parse_error" in parsed:
        log.warning("Outlier analysis parse failed — using minimal report")
        return _minimal_outlier_report(outlier_records, embedding_outlier_ids)

    # Build OutlierReport
    outliers = []
    for item in parsed.get("outliers", []):
        if not isinstance(item, dict):
            continue
        quote_data = item.get("notable_quote")
        quote = None
        if isinstance(quote_data, dict) and quote_data.get("text"):
            quote = QuoteRecord(
                text=quote_data["text"],
                significance=quote_data.get("significance", ""),
            )
        outliers.append(OutlierRecord(
            student_id=item.get("student_id", ""),
            student_name=item.get("student_name", ""),
            why_notable=item.get("why_notable", ""),
            relationship_to_themes=item.get("relationship_to_themes", ""),
            notable_quote=quote,
            teacher_recommendation=item.get("teacher_recommendation", ""),
        ))

    # Cross-check: mark high confidence if both LLM and embedding agree
    for o in outliers:
        if o.student_id in embedding_outlier_ids:
            if not o.why_notable.endswith(" [confirmed by embedding analysis]"):
                o.why_notable += " [confirmed by embedding analysis]"

    return OutlierReport(outliers=outliers)


def _minimal_outlier_report(
    records: List[SubmissionCodingRecord],
    embedding_outlier_ids: List[str],
) -> OutlierReport:
    """Fallback outlier report when LLM parse fails."""
    outliers = []
    for r in records:
        quote = r.notable_quotes[0] if r.notable_quotes else None
        is_embedding = r.student_id in embedding_outlier_ids
        outliers.append(OutlierRecord(
            student_id=r.student_id,
            student_name=r.student_name,
            why_notable=f"Did not match identified themes. Tags: {', '.join(r.theme_tags)}"
                        + (" [also flagged by embedding analysis]" if is_embedding else ""),
            relationship_to_themes="Could not be determined (LLM analysis unavailable)",
            notable_quote=quote,
            teacher_recommendation="Review this submission — it may contain a unique perspective.",
        ))
    return OutlierReport(outliers=outliers)
