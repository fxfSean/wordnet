export type Rating = "know" | "fuzzy" | "dont_know";
export type ReviewState = {
  stage: number;
  correctStreak: number;
  nextReviewAt: number;
  correctCount: number;
  wrongCount: number;
  fuzzyCount: number;
  lastReviewedAt: number;
};
const intervals = [1, 3, 7, 15, 30, 60, 120];
const dayMs = 86_400_000;
const fuzzyMs = 30 * 60_000;
const forgotMs = 10 * 60_000;

export function scheduleReview(current: ReviewState | undefined, rating: Rating, now: number): ReviewState {
  const base = current ?? {
    stage: 0,
    correctStreak: 0,
    nextReviewAt: now,
    correctCount: 0,
    wrongCount: 0,
    fuzzyCount: 0,
    lastReviewedAt: 0,
  };
  if (rating === "fuzzy") {
    return {
      ...base,
      stage: Math.max(1, Math.min(base.stage || 1, 3)),
      nextReviewAt: now + fuzzyMs,
      fuzzyCount: (base.fuzzyCount ?? 0) + 1,
      lastReviewedAt: now,
    };
  }
  const streak = rating === "know" ? (base.correctStreak ?? 0) + 1 : 0;
  const stage = Math.min(streak, intervals.length);
  return {
    ...base,
    stage,
    correctStreak: streak,
    nextReviewAt: now + (stage ? intervals[stage - 1] * dayMs : forgotMs),
    correctCount: (base.correctCount ?? 0) + Number(rating === "know"),
    wrongCount: (base.wrongCount ?? 0) + Number(rating === "dont_know"),
    fuzzyCount: base.fuzzyCount ?? 0,
    lastReviewedAt: now,
  };
}

export function studyDate(now: number, offsetMinutes = new Date(now).getTimezoneOffset()): string {
  return new Date(now - offsetMinutes * 60_000).toISOString().slice(0, 10);
}
