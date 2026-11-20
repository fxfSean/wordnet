const {test} = require("node:test");
const assert = require("node:assert/strict");
const {
  bookById, cardByKey, cardsFor, registerBookPackage, words,
} = require("../miniprogram/catalog.js");

test("a downloaded book package merges memberships and new senses", () => {
  const existing = words.find(word => word.senses.some(sense => sense.primary));
  assert.ok(existing);
  const sense = existing.senses.find(item => item.primary);
  const newWord = "zzz-package-test";
  const newSense = {
    id: "wn30:noun:99999999",
    pos: "noun",
    definition: "a test package word",
    primary: true,
    examples: [{en: "This is a package test."}],
    synonyms: [],
  };
  const pkg = {
    version: 1,
    book: {
      id: "test_package",
      title: "Test package",
      subtitle: "Full",
      description: "Package merge test",
      wordCount: 2,
      unitSize: 50,
      unitCount: 1,
      source: {name: "test", version: "1", license: "MIT", url: ""},
    },
    memberships: [
      {word: existing.word, rank: 1, unit: 1},
      {word: newWord, rank: 2, unit: 1},
    ],
    entries: [{word: newWord, rank: 2, unit: 1, senses: [newSense]}],
  };
  registerBookPackage(pkg);
  assert.equal(bookById("test_package").wordCount, 2);
  assert.ok(existing.books.some(ref => ref.book === "test_package" && ref.rank === 1));
  const cards = cardsFor("test_package", 1, 1);
  assert.ok(cards.some(card => card.word === existing.word));
  assert.ok(cards.some(card => card.word === newWord));
  assert.ok(cardByKey(newWord + "|" + newSense.id));
  assert.ok(cardByKey(existing.word + "|" + sense.id));
});
