const {test} = require("node:test");
const assert = require("node:assert/strict");
const {studyDate} = require("../miniprogram/review.js");
const {scheduleReview} = require("../miniprogram/review.js");
const {
  addStudyTime, applyRating, buildQueue, normalizeState, studyStreak,
} = require("../miniprogram/study.js");
const {masteryFor, recentDays, todayStat} = require("../miniprogram/stats.js");
const {parseBackup, serializeState} = require("../miniprogram/backup.js");
const {sentenceAudioUrl, wordAudioUrl} = require("../miniprogram/audio.js");
const {themeClass} = require("../miniprogram/theme.js");
const {books, cards, cardsFor, unitLabel, words} = require("../miniprogram/catalog.js");

const now = Date.UTC(2026, 10, 17, 12);

test("legacy state is migrated with settings, notes and review history", () => {
  const legacy = {
    goal: 10,
    progress: {a: {stage: 2, correctStreak: 2, nextReviewAt: 123, correctCount: 2, wrongCount: 0}},
    history: {"2026-11-17": {count: 3, newCount: 1}},
    recentEvents: ["event"],
    savedWords: ["bank", "bank"],
  };
  const state = normalizeState(legacy);
  assert.equal(state.goal, 10);
  assert.equal(state.book, "basic_ngsl_1_2");
  assert.equal(state.unitStart, 1);
  assert.equal(state.unitEnd, 9999);
  assert.deepEqual(state.savedWords, ["bank"]);
  assert.deepEqual(state.settings, {accent: "us", autoplay: true, groupSize: 20, theme: "dark"});
  assert.deepEqual(state.notes, {});
  assert.deepEqual(state.savedSentences, []);
  assert.equal(state.history["2026-11-17"].reviewCount, 2);
  assert.equal(state.progress.a.stage, 2);
});

test("theme preference defaults to dark and supports a light mode", () => {
  assert.equal(normalizeState({}).settings.theme, "dark");
  assert.equal(normalizeState({settings: {theme: "light"}}).settings.theme, "light");
  assert.equal(normalizeState({settings: {theme: "sepia"}}).settings.theme, "dark");
  assert.equal(themeClass("dark"), "theme-dark");
  assert.equal(themeClass("light"), "theme-light");
});

test("a card is counted as new once and later as review", () => {
  let state = normalizeState({goal: 20});
  state = applyRating(state, "a", "know", "e1", now);
  const date = studyDate(now);
  assert.equal(state.history[date].newCount, 1);
  assert.equal(state.history[date].reviewCount, 0);
  state = applyRating(state, "a", "know", "e2", now + 1000);
  assert.equal(state.history[date].count, 2);
  assert.equal(state.history[date].newCount, 1);
  assert.equal(state.history[date].reviewCount, 1);
  assert.equal(applyRating(state, "a", "know", "e2", now + 2000), state);
});

test("fuzzy ratings keep progress but return sooner", () => {
  const fuzzy = scheduleReview(undefined, "fuzzy", now);
  assert.equal(fuzzy.stage, 1);
  assert.equal(fuzzy.correctStreak, 0);
  assert.equal(fuzzy.fuzzyCount, 1);
  assert.equal(fuzzy.nextReviewAt - now, 30 * 60_000);
  const known = scheduleReview(fuzzy, "know", now + 1);
  assert.equal(known.stage, 1);
  assert.equal(known.correctStreak, 1);
  assert.equal(known.correctCount, 1);
  assert.equal(known.fuzzyCount, 1);
});

test("session size caps the queue without changing the daily goal", () => {
  const state = normalizeState({goal: 50, settings: {groupSize: 2}});
  assert.deepEqual(buildQueue(["a", "b", "c", "d"], state, now), ["a", "b"]);
  const due = normalizeState({
    goal: 50,
    settings: {groupSize: 3},
    progress: {
      a: {stage: 1, nextReviewAt: now - 2},
      b: {stage: 1, nextReviewAt: now - 1},
      c: {stage: 1, nextReviewAt: now - 3},
      d: {stage: 1, nextReviewAt: now - 4},
    },
  });
  assert.deepEqual(buildQueue(["a", "b", "c", "d"], due, now), ["d", "c", "a"]);
});

test("saved sentences are deduplicated during state migration", () => {
  const state = normalizeState({
    savedSentences: [
      {en: "a happy smile", zh: "一个幸福的微笑", word: "happy", pos: "adj"},
      {en: "a happy smile", word: "happy", pos: "adj"},
      {en: "", word: "happy", pos: "adj"},
    ],
  });
  assert.equal(state.savedSentences.length, 1);
  assert.equal(state.savedSentences[0].zh, "一个幸福的微笑");
});

test("study time, streaks and recent-day bars use local study dates", () => {
  let state = normalizeState({goal: 20});
  state = applyRating(state, "a", "dont_know", "e1", now);
  state = addStudyTime(state, 65_000, now);
  const date = studyDate(now);
  assert.equal(state.history[date].durationMs, 65_000);
  assert.equal(todayStat(state, now).count, 1);
  assert.equal(studyStreak(state, now), 1);
  assert.equal(studyStreak(state, now + 86_400_000), 1);
  assert.equal(studyStreak(state, now + 2 * 86_400_000), 0);
  const rows = recentDays(state, now, 7);
  assert.equal(rows.length, 7);
  assert.equal(rows[6].date, date);
  assert.equal(rows[6].count, 1);
  assert.ok(rows[6].height > 0);
});

test("mastery buckets can be limited to one book/unit range", () => {
  const state = normalizeState({
    progress: {
      a: {stage: 2, nextReviewAt: now},
      b: {stage: 5, nextReviewAt: now},
      c: {stage: 7, nextReviewAt: now},
    },
  });
  assert.deepEqual(masteryFor(state, ["a", "b", "c"]), {learning: 1, reviewing: 1, mastered: 1});
  assert.deepEqual(masteryFor(state, ["c"]), {learning: 0, reviewing: 0, mastered: 1});
});

test("backup round-trips state and rejects unrelated JSON", () => {
  const state = normalizeState({goal: 30, savedWords: ["bank"], notes: {bank: "river bank"}});
  const restored = parseBackup(serializeState(state));
  assert.deepEqual(restored, state);
  assert.throws(() => parseBackup("not json"), /valid JSON/);
  assert.throws(() => parseBackup(JSON.stringify({app: "other", state})), /not a Word Study backup/);
  assert.throws(() => parseBackup(JSON.stringify({app: "wordnet-study", version: 99, state})), /newer version/);
  const legacy = parseBackup(JSON.stringify({goal: 20, progress: {}}));
  assert.equal(legacy.goal, 20);
});

test("audio URLs switch accent and encode sentences", () => {
  assert.match(wordAudioUrl("bank", "us"), /audio=bank&type=2$/);
  assert.match(wordAudioUrl("bank", "uk"), /audio=bank&type=1$/);
  assert.match(sentenceAudioUrl("a happy smile"), /text=a%20happy%20smile$/);
});

test("catalog carries book, unit and rich sense data", () => {
  assert.ok(words.length >= 2809);
  assert.equal(books.length, 11);
  assert.equal(books[0].id, "basic_ngsl_1_2");
  assert.equal(books[0].unitCount, Math.ceil(2809 / books[0].unitSize));
  assert.ok(books.some(book => book.id === "nawl_1_2"));
  assert.ok(books.some(book => book.id === "tsl_1_2"));
  assert.ok(books.some(book => book.id === "bsl_1_2"));
  assert.ok(books.some(book => book.id === "cet4"));
  assert.ok(books.some(book => book.id === "cet6"));
  assert.ok(books.some(book => book.id === "kaoyan"));
  assert.ok(books.some(book => book.id === "ielts"));
  assert.ok(books.some(book => book.id === "toefl"));
  assert.equal(words[0].rank, 1);
  assert.equal(words[0].unit, 1);
  assert.ok(words[0].books.length >= 1);
  for (const card of cards.slice(0, 50)) {
    assert.equal(card.book, "basic_ngsl_1_2");
    assert.ok(card.unit >= 1);
    assert.ok(card.books.length >= 1);
  }
  const happy = words.find(word => word.word === "happy");
  assert.ok(happy.senses.some(sense => sense.antonyms?.includes("unhappy")));
  assert.ok(happy.senses.some(sense => sense.derivatives?.includes("happiness")));
  assert.ok(happy.senses.some(sense => (sense.examples?.length ?? 0) >= 1));
  const unitCards = cardsFor("basic_ngsl_1_2", 1, 1);
  assert.ok(unitCards.length > 0);
  assert.ok(unitCards.every(card => card.books.some(ref => ref.book === "basic_ngsl_1_2" && ref.unit === 1)));
  const academic = cardsFor("nawl_1_2", 1, 1);
  assert.ok(academic.length > 0);
  assert.ok(academic.every(card => card.books.some(ref => ref.book === "nawl_1_2" && ref.unit === 1)));
  const cet4 = cardsFor("cet4", 1, 1);
  assert.ok(cet4.length > 0);
  assert.ok(cet4.every(card => card.books.some(ref => ref.book === "cet4" && ref.unit === 1)));
  assert.match(unitLabel(books[0], 1), /Unit 1 · 1–50/);
});
