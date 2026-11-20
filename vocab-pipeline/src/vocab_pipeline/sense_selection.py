from .models import CandidateSense


def recommend_senses(
    candidates: list[CandidateSense], limit: int, min_tags: int
) -> bool:
    """Recommend distinct high-evidence senses and return whether review is needed."""
    has_exact = any(sense.match_method == "exact" for sense in candidates)
    ranked = []
    for sense in candidates:
        sense.ranking_score = sense.tag_count
        sense.is_recommended = False
        if (
            (not has_exact or sense.match_method == "exact")
            and sense.tag_count is not None
            and sense.tag_count >= min_tags
        ):
            ranked.append(sense)
    ranked.sort(key=lambda sense: -sense.ranking_score)
    boundary = ranked[limit].ranking_score if len(ranked) > limit else None
    for sense in ranked[:limit]:
        sense.is_recommended = sense.ranking_score != boundary
    tied = boundary is not None and ranked[limit - 1].ranking_score == boundary
    uncertain = not has_exact and any(
        sense.match_confidence == "low" for sense in candidates
    )
    return bool(candidates) and (not ranked or tied or uncertain)
