const {test} = require("node:test");
const assert = require("node:assert/strict");
const {
  cardByKey, registerContentPackage, words,
} = require("../miniprogram/catalog.js");

test("a content package merges phrases and roots into words and cards", () => {
  const word = words.find(item =>
    item.senses.some(sense => sense.primary) && !item.phrases?.length && !item.roots?.length);
  assert.ok(word, "expected a word without bundled phrases/roots");
  const sense = word.senses.find(item => item.primary);
  const card = cardByKey(word.word + "|" + sense.id);
  assert.ok(card);

  registerContentPackage({
    version: 1,
    words: {
      [word.word]: {
        phrases: [{en: "content package phrase", zh: "词组测试"}],
        roots: [{form: "test-", meaning: "a test root", kind: "prefix"}],
      },
    },
  });

  assert.equal(word.phrases.length, 1);
  assert.equal(word.phrases[0].en, "content package phrase");
  assert.equal(word.roots[0].form, "test-");
  assert.equal(card.phrases[0].en, "content package phrase");
  assert.equal(card.roots[0].meaning, "a test root");
});

test("bundled content is not overwritten by the content package", () => {
  const word = words.find(item => item.roots?.length && item.senses.some(sense => sense.primary));
  assert.ok(word, "expected a word with bundled roots");
  const original = word.roots[0];
  registerContentPackage({
    version: 1,
    words: {[word.word]: {roots: [{form: "zz-", meaning: "replacement", kind: "prefix"}]}},
  });
  assert.equal(word.roots[0].form, original.form);
});
