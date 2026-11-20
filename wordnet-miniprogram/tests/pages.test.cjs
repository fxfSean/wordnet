const {test} = require("node:test");
const assert = require("node:assert/strict");
const {normalizeState} = require("../miniprogram/study.js");

function mount(modulePath, saved) {
  let page;
  global.wx = {
    getStorageSync: () => saved.value,
    setStorageSync: (_key, value) => { saved.value = value; },
    navigateTo: () => {},
    navigateBack: () => {},
    showToast: () => {},
  };
  global.Page = options => {
    page = {...options, setData(values) { Object.assign(this.data, values); }};
  };
  try {
    require(modulePath);
  } finally {
    delete global.Page;
  }
  return page;
}

test("home page renders the active plan and saves a new goal", () => {
  const saved = {value: normalizeState({goal: 20})};
  const page = mount("../miniprogram/pages/home/index.js", saved);
  page.onShow();
  assert.equal(page.data.bookTitle, "General English");
  assert.equal(page.data.words, 2809);
  assert.equal(page.data.unitText, "All units");
  assert.equal(page.data.goal, 20);
  page.setGoal({detail: {value: "2"}});
  assert.equal(saved.value.goal, 30);
  assert.equal(page.data.goal, 30);
  delete global.wx;
});

test("books page loads units and saves a range", () => {
  const saved = {value: normalizeState({goal: 20})};
  const page = mount("../miniprogram/pages/books/index.js", saved);
  page.onLoad();
  assert.equal(page.data.unitCount, Math.ceil(2809 / 50));
  assert.equal(page.data.bookTitles.length, 11);
  assert.ok(page.data.bookTitles.includes("Academic English"));
  assert.ok(page.data.bookTitles.includes("CET-4"));
  assert.equal(page.data.bookCovers.length, 11);
  assert.ok(page.data.bookCovers.some(row => row.selected));
  assert.ok(page.data.cardCount > 0);
  page.setStart({detail: {value: "2"}});
  page.setEnd({detail: {value: "3"}});
  page.setGoal({detail: {value: "2"}});
  page.save();
  assert.equal(saved.value.unitStart, 3);
  assert.equal(saved.value.unitEnd, 4);
  assert.equal(saved.value.goal, 30);
  assert.equal(saved.value.settings.groupSize, 20);
  delete global.wx;
});

test("content page groups learning, saved words, sentences and notes", () => {
  const now = Date.now();
  const {cards} = require("../miniprogram/catalog.js");
  const card = cards[0];
  const saved = {
    value: normalizeState({
      progress: {[card.key]: {stage: 2, nextReviewAt: 0, lastReviewedAt: now}},
      savedWords: [card.word],
      notes: {[card.word]: "my note"},
      savedSentences: [{en: "a happy smile", zh: "一个幸福的微笑", word: card.word, pos: card.pos}],
    }),
  };
  const page = mount("../miniprogram/pages/content/index.js", saved);
  page.onShow();
  assert.ok(page.data.tabs.length === 4);
  assert.equal(page.data.learning.length, 1);
  assert.equal(page.data.saved.length, 1);
  assert.equal(page.data.sentences.length, 1);
  assert.equal(page.data.notes.length, 1);
  assert.equal(page.data.notes[0].note, "my note");
  delete global.wx;
});

test("spelling practice checks answers and advances", () => {
  const saved = {value: normalizeState({goal: 20})};
  const page = mount("../miniprogram/pages/spell/index.js", saved);
  page.onLoad({mode: "spell"});
  assert.ok(page.data.current);
  const word = page.data.current.word;
  page.input({detail: {value: word}});
  page.check();
  assert.equal(page.data.checked, true);
  assert.equal(page.data.correct, true);
  assert.equal(page.data.correctCount, 1);
  page.next();
  assert.ok(page.data.index === 1 || page.data.current === null);
  delete global.wx;
});

test("stats page builds recent rows and mastery buckets", () => {
  const {cards} = require("../miniprogram/catalog.js");
  const [first, second] = cards;
  const state = normalizeState({
    history: {
      [require("../miniprogram/review.js").studyDate(Date.now())]: {
        count: 4, newCount: 2, reviewCount: 2, durationMs: 120000,
      },
    },
    progress: {
      [first.key]: {stage: 2, nextReviewAt: 0},
      [second.key]: {stage: 7, nextReviewAt: 0},
    },
  });
  const saved = {value: state};
  const page = mount("../miniprogram/pages/stats/index.js", saved);
  page.onShow();
  assert.equal(page.data.bars.length, 14);
  assert.equal(page.data.recent.length, 7);
  assert.equal(page.data.todayCount, 4);
  assert.equal(page.data.mastered, 1);
  assert.equal(page.data.learning, 1);
  assert.ok(page.data.calendar.cells.length >= 28);
  assert.ok(page.data.calendar.cells.length % 7 === 0);
  assert.ok(page.data.calendar.title.length > 0);
  delete global.wx;
});
