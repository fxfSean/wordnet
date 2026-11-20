import {scheduleReview, studyDate, type Rating, type ReviewState} from "./review";

export type DayStat = {
  count: number;
  newCount: number;
  reviewCount: number;
  durationMs: number;
};
export type Accent = "us" | "uk";
export type Theme = "dark" | "light";
export type Settings = {accent: Accent; autoplay: boolean; groupSize: number; theme: Theme};
export type SavedSentence = {en: string; zh?: string; word: string; pos: string};
export type StudyState = {
  progress: Record<string, ReviewState>;
  history: Record<string, DayStat>;
  recentEvents: string[];
  goal: number;
  savedWords: string[];
  notes: Record<string, string>;
  savedSentences: SavedSentence[];
  settings: Settings;
  book: string;
  unitStart: number;
  unitEnd: number;
};

export const DEFAULT_BOOK = "basic_ngsl_1_2";
export const MAX_UNIT = 9999;

export function defaultState(): StudyState {
  return {
    progress: {},
    history: {},
    recentEvents: [],
    goal: 20,
    savedWords: [],
    notes: {},
    savedSentences: [],
    settings: {accent: "us", autoplay: true, groupSize: 20, theme: "dark"},
    book: DEFAULT_BOOK,
    unitStart: 1,
    unitEnd: MAX_UNIT,
  };
}

function numberOr(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function dayStat(value: unknown): DayStat {
  const row = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const count = Math.max(0, Math.floor(numberOr(row.count, 0)));
  const newCount = Math.max(0, Math.min(count, Math.floor(numberOr(row.newCount, 0))));
  const reviewCount = row.reviewCount === undefined
    ? Math.max(0, count - newCount)
    : Math.max(0, Math.min(count - newCount, Math.floor(numberOr(row.reviewCount, 0))));
  return {
    count,
    newCount,
    reviewCount,
    durationMs: Math.max(0, Math.floor(numberOr(row.durationMs, 0))),
  };
}

function reviewState(value: unknown): ReviewState {
  const row = value && typeof value === "object" ? value as Record<string, unknown> : {};
  return {
    stage: Math.max(0, Math.min(7, Math.floor(numberOr(row.stage, 0)))),
    correctStreak: Math.max(0, Math.floor(numberOr(row.correctStreak, 0))),
    nextReviewAt: numberOr(row.nextReviewAt, 0),
    correctCount: Math.max(0, Math.floor(numberOr(row.correctCount, 0))),
    wrongCount: Math.max(0, Math.floor(numberOr(row.wrongCount, 0))),
    fuzzyCount: Math.max(0, Math.floor(numberOr(row.fuzzyCount, 0))),
    lastReviewedAt: Math.max(0, numberOr(row.lastReviewedAt, 0)),
  };
}

/** Merge persisted state with current defaults, including old app versions. */
export function normalizeState(value: unknown): StudyState {
  const fallback = defaultState();
  const state = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const progress: Record<string, ReviewState> = {};
  if (state.progress && typeof state.progress === "object") {
    for (const [key, row] of Object.entries(state.progress as Record<string, unknown>)) {
      progress[key] = reviewState(row);
    }
  }
  const history: Record<string, DayStat> = {};
  if (state.history && typeof state.history === "object") {
    for (const [date, row] of Object.entries(state.history as Record<string, unknown>)) {
      history[date] = dayStat(row);
    }
  }
  const recentEvents = Array.isArray(state.recentEvents)
    ? state.recentEvents.filter((item): item is string => typeof item === "string").slice(-500)
    : [];
  const savedWords = Array.isArray(state.savedWords)
    ? [...new Set(state.savedWords.filter((item): item is string => typeof item === "string"))]
    : [];
  const notes: Record<string, string> = {};
  if (state.notes && typeof state.notes === "object") {
    for (const [word, note] of Object.entries(state.notes as Record<string, unknown>)) {
      if (typeof note === "string" && note.trim()) notes[word] = note;
    }
  }
  const savedSentences: SavedSentence[] = [];
  const seenSentences = new Set<string>();
  if (Array.isArray(state.savedSentences)) {
    for (const row of state.savedSentences) {
      if (!row || typeof row !== "object") continue;
      const item = row as Record<string, unknown>;
      if (typeof item.en !== "string" || !item.en.trim()) continue;
      if (typeof item.word !== "string" || !item.word.trim()) continue;
      if (seenSentences.has(item.en)) continue;
      seenSentences.add(item.en);
      savedSentences.push({
        en: item.en,
        zh: typeof item.zh === "string" ? item.zh : undefined,
        word: item.word,
        pos: typeof item.pos === "string" ? item.pos : "",
      });
    }
  }
  const rawSettings = state.settings && typeof state.settings === "object"
    ? state.settings as Record<string, unknown>
    : {};
  const accent: Accent = rawSettings.accent === "uk" ? "uk" : "us";
  const theme: Theme = rawSettings.theme === "light" ? "light" : "dark";
  let unitStart = Math.max(1, Math.floor(numberOr(state.unitStart, fallback.unitStart)));
  let unitEnd = Math.max(1, Math.floor(numberOr(state.unitEnd, fallback.unitEnd)));
  if (unitStart > unitEnd) [unitStart, unitEnd] = [unitEnd, unitStart];
  return {
    progress,
    history,
    recentEvents,
    goal: Math.max(1, Math.min(100, Math.floor(numberOr(state.goal, fallback.goal)))),
    savedWords,
    notes,
    savedSentences,
    settings: {
      accent,
      autoplay: typeof rawSettings.autoplay === "boolean" ? rawSettings.autoplay : fallback.settings.autoplay,
      groupSize: Math.max(1, Math.min(100, Math.floor(numberOr(rawSettings.groupSize, fallback.settings.groupSize)))),
      theme,
    },
    book: typeof state.book === "string" && state.book ? state.book : fallback.book,
    unitStart,
    unitEnd,
  };
}

export function buildQueue(keys: string[], state: StudyState, now: number, dueOnly = false): string[] {
  const due = keys.filter(key => state.progress[key]?.nextReviewAt <= now)
    .sort((a, b) => state.progress[a].nextReviewAt - state.progress[b].nextReviewAt);
  const groupSize = Math.max(1, state.settings.groupSize);
  if (dueOnly) return due.slice(0, groupSize);
  const remaining = Math.max(0, state.goal - (state.history[studyDate(now)]?.newCount ?? 0));
  const dueCards = due.slice(0, groupSize);
  const newCards = keys.filter(key => !state.progress[key])
    .slice(0, Math.min(remaining, Math.max(0, groupSize - dueCards.length)));
  return [...dueCards, ...newCards];
}

export function applyRating(state: StudyState, key: string, rating: Rating, eventId: string,
                            now: number): StudyState {
  if (state.recentEvents.includes(eventId)) return state;
  const previous = state.progress[key];
  const date = studyDate(now);
  const today = state.history[date] ?? {count: 0, newCount: 0, reviewCount: 0, durationMs: 0};
  return {
    ...state,
    progress: {...state.progress, [key]: scheduleReview(previous, rating, now)},
    history: {...state.history, [date]: {
      ...today,
      count: today.count + 1,
      newCount: (today.newCount ?? 0) + Number(!previous),
      reviewCount: (today.reviewCount ?? 0) + Number(!!previous),
    }},
    recentEvents: [...state.recentEvents.slice(-499), eventId],
  };
}

/** Add active study time to the local day, capped to avoid an idle page inflating totals. */
export function addStudyTime(state: StudyState, milliseconds: number, now: number): StudyState {
  const elapsed = Math.min(6 * 3_600_000, Math.floor(Math.max(0, milliseconds)));
  if (elapsed <= 0) return state;
  const date = studyDate(now);
  const today = state.history[date] ?? {count: 0, newCount: 0, reviewCount: 0, durationMs: 0};
  return {
    ...state,
    history: {...state.history, [date]: {...today, durationMs: today.durationMs + elapsed}},
  };
}

function shiftDate(date: string, days: number): string {
  const value = new Date(date + "T00:00:00Z");
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}

/** Consecutive study days, counting yesterday when today has no activity yet. */
export function studyStreak(state: StudyState, now: number): number {
  let date = studyDate(now);
  if (!(state.history[date]?.count > 0)) date = shiftDate(date, -1);
  let days = 0;
  while (state.history[date]?.count > 0 && days < 3650) {
    days += 1;
    date = shiftDate(date, -1);
  }
  return days;
}
