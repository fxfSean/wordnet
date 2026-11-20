const {test} = require("node:test");
const assert = require("node:assert/strict");
const {scheduleReview, studyDate} = require("../miniprogram/review.js");
const {applyRating, buildQueue, defaultState} = require("../miniprogram/study.js");
const {cards, words} = require("../miniprogram/catalog.js");

test("review intervals advance, cap at 120 days and reset on a miss", () => {
  const now = Date.UTC(2026, 10, 17);
  let state;
  for (const day of [1, 3, 7, 15, 30, 60, 120, 120]) {
    state = scheduleReview(state, "know", now);
    assert.equal(state.nextReviewAt - now, day * 86400000);
  }
  state = scheduleReview(state, "dont_know", now);
  assert.equal(state.correctCount, 8);
  assert.equal(state.correctStreak, 0);
  assert.equal(state.nextReviewAt - now, 600000);
});

test("due cards precede new cards and a miss returns within the same day", () => {
  const now = Date.UTC(2026, 10, 17);
  const state = applyRating({...defaultState(),goal: 1}, "a", "dont_know", "event-1", now);
  assert.deepEqual(buildQueue(["a","b"], state, now + 599999), []);
  assert.deepEqual(buildQueue(["a","b"], state, now + 600000), ["a"]);
  assert.equal(applyRating(state, "a", "know", "event-1", now), state);
  assert.deepEqual(buildQueue(["a","b"], state, now + 86400000), ["a","b"]);
  assert.deepEqual(buildQueue(["a","b"], state, now + 86400000, true), ["a"]);
  assert.deepEqual(buildQueue(["a","b"], defaultState(), now, true), []);
});

test("local day changes correctly for positive and negative UTC offsets", () => {
  const now = Date.UTC(2026, 10, 17, 16);
  assert.equal(studyDate(now, -480), "2026-11-18");
  assert.equal(studyDate(now, 300), "2026-11-17");
});

test("catalog contains actual words with stable per-lemma sense keys", () => {
  assert.ok(words.length >= 2809);
  assert.equal(new Set(cards.map(card => card.key)).size, cards.length);
  assert.equal(cards.filter(card => card.word === "bank").length, 2);
  assert.equal(cards.some(card => card.word === "the"), false);
});

test("study page reveals and persists precisely one rating", () => {
  let saved;
  let page;
  global.wx = {
    getStorageSync: () => saved,
    setStorageSync: (_, value) => { saved = value; },
  };
  global.Page = options => {
    page = {...options, setData(values) { Object.assign(this.data, values); }};
  };
  try {
    require("../miniprogram/pages/study/index.js");
    page.onShow();
    const initial = page.data.card.key;
    assert.equal(page.data.revealed, false);
    page.know();
    assert.equal(saved, undefined);
    page.reveal();
    assert.equal(page.data.revealed, true);
    page.dontKnow();
    assert.equal(saved.progress[initial].wrongCount, 1);
    assert.equal(page.data.completed, 1);
    assert.match(page.data.feedback, /Review again in 10 min$/);
    assert.equal(page.data.revealed, false);
    page.dontKnow();
    assert.equal(saved.progress[initial].wrongCount, 1);
  } finally {
    page?.onUnload();
    delete global.wx;
    delete global.Page;
  }
});

test("saved words preserve legacy progress and can be removed from the filtered view", () => {
  let saved = {goal: 10, progress: {oldCard: {stage: 2}}};
  let page;
  global.wx = {
    getStorageSync: () => saved,
    setStorageSync: (_, value) => { saved = value; },
  };
  global.Page = options => {
    page = {...options, setData(values) { Object.assign(this.data, values); }};
  };
  try {
    require("../miniprogram/pages/library/index.js");
    page.open({currentTarget: {dataset: {word: "bank"}}});
    page.toggleSaved();
    assert.deepEqual(saved.savedWords, ["bank"]);
    assert.equal(saved.progress.oldCard.stage, 2);
    page.showSaved();
    assert.deepEqual(page.data.entries.map(item => item.word), ["bank"]);
    page.open({currentTarget: {dataset: {word: "bank"}}});
    assert.equal(page.data.saved, true);
    page.toggleSaved();
    assert.deepEqual(page.data.entries, []);
    assert.equal(page.data.emptyMessage, "No saved words yet.");
    page.search({detail: {value: "no-such-saved-word"}});
    assert.equal(page.data.emptyMessage, "No words found.");
  } finally {
    delete global.wx;
    delete global.Page;
  }
});
