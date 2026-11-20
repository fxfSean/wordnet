export type Example = {en: string; zh?: string};
export type BookRef = {book: string; rank: number; unit: number};
export type Sense = {
  id: string;
  pos: string;
  definition: string;
  definitionZh?: string;
  examples?: Example[];
  primary: boolean;
  synonyms?: string[];
  antonyms?: string[];
  derivatives?: string[];
  phrases?: Example[];
  roots?: Array<{form: string; meaning: string}>;
};
export type Word = {
  word: string;
  book: string;
  rank: number;
  unit: number;
  books: BookRef[];
  senses: Sense[];
  phrases?: Example[];
  roots?: Array<{form: string; meaning: string; kind?: string}>;
};
export type Card = Sense & {
  word: string;
  key: string;
  book: string;
  rank: number;
  unit: number;
  books: BookRef[];
  phrases?: Example[];
  roots?: Array<{form: string; meaning: string; kind?: string}>;
};
export type Book = {
  id: string;
  title: string;
  subtitle: string;
  description?: string;
  wordCount: number;
  unitSize: number;
  unitCount: number;
  source: {name: string; version: string; license: string; url: string; authors?: string};
};
export type BookPackageEntry = {
  word: string; rank: number; unit: number; senses: Sense[];
  phrases?: Example[]; roots?: Array<{form: string; meaning: string; kind?: string}>;
};
export type BookPackage = {
  version: number;
  book: Book;
  memberships: Array<{word: string; rank: number; unit: number}>;
  entries: BookPackageEntry[];
};
export type ContentPackage = {
  version: number;
  words: Record<string, {
    phrases?: Example[];
    roots?: Array<{form: string; meaning: string; kind?: string}>;
  }>;
};
type CatalogPayload = {words: Word[]; books: Book[]};

const fflate = require("./lib/fflate.js") as {
  gunzipSync(data: Uint8Array): Uint8Array;
  strFromU8(data: Uint8Array): string;
};

const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
const base64Lookup = new Int16Array(128).fill(-1);
for (let index = 0; index < alphabet.length; index += 1) {
  base64Lookup[alphabet.charCodeAt(index)] = index;
}

/** Decode the base64 payload without relying on Node's Buffer or wx APIs. */
function decodeBase64(input: string): Uint8Array {
  const clean = input.replace(/=+$/, "");
  const output = new Uint8Array(Math.floor(clean.length * 3 / 4));
  let buffer = 0;
  let bits = 0;
  let index = 0;
  for (let cursor = 0; cursor < clean.length; cursor += 1) {
    const code = clean.charCodeAt(cursor);
    const value = code < 128 ? base64Lookup[code] : -1;
    if (value < 0) continue;
    buffer = (buffer << 6) | value;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      output[index++] = (buffer >> bits) & 0xff;
    }
  }
  return output.subarray(0, index);
}

const encoded = require("./data/catalog.gz.js") as string;
const payload = JSON.parse(fflate.strFromU8(fflate.gunzipSync(decodeBase64(encoded)))) as CatalogPayload;

export const words = payload.words;
export const books = payload.books;

export const cards: Card[] = words.flatMap(entry =>
  entry.senses.filter(sense => sense.primary).map(sense => ({
    ...sense,
    word: entry.word,
    key: entry.word + "|" + sense.id,
    book: entry.book,
    rank: entry.rank,
    unit: entry.unit,
    books: entry.books,
    phrases: entry.phrases,
    roots: entry.roots,
  }))
);

export function bookById(id: string): Book | undefined {
  return books.find(book => book.id === id);
}

const wordIndex = new Map(words.map(word => [word.word, word]));
const cardIndex = new Map(cards.map(card => [card.key, card]));
const cardsByWord = new Map<string, Card[]>();
for (const card of cards) {
  const list = cardsByWord.get(card.word) ?? [];
  list.push(card);
  cardsByWord.set(card.word, list);
}

export function cardByKey(key: string): Card | undefined {
  return cardIndex.get(key);
}

function addCard(word: Word, sense: Sense): void {
  const key = word.word + "|" + sense.id;
  const existing = cardIndex.get(key);
  if (existing) {
    for (const ref of word.books) {
      if (!existing.books.some(item => item.book === ref.book && item.rank === ref.rank)) {
        existing.books.push(ref);
      }
    }
    return;
  }
  const card: Card = {
    ...sense,
    word: word.word,
    key,
    book: word.book,
    rank: word.rank,
    unit: word.unit,
    books: word.books,
    phrases: word.phrases,
    roots: word.roots,
  };
  cards.push(card);
  cardIndex.set(key, card);
  const list = cardsByWord.get(word.word) ?? [];
  list.push(card);
  cardsByWord.set(word.word, list);
}

/** Merge a downloaded full-book package into the in-memory catalog. */
export function registerBookPackage(pkg: BookPackage): void {
  const book = books.find(item => item.id === pkg.book.id);
  if (book) Object.assign(book, pkg.book);
  else books.push(pkg.book);

  for (const entry of pkg.entries) {
    let word = wordIndex.get(entry.word);
    if (!word) {
      word = {
        word: entry.word,
        book: pkg.book.id,
        rank: entry.rank,
        unit: entry.unit,
        books: [],
        senses: [],
      };
      words.push(word);
      wordIndex.set(word.word, word);
      cardsByWord.set(word.word, []);
    }
    for (const sense of entry.senses) {
      if (!word.senses.some(item => item.id === sense.id)) word.senses.push(sense);
      if (sense.primary) addCard(word, sense);
    }
    if (entry.phrases?.length && !word.phrases?.length) word.phrases = entry.phrases;
    if (entry.roots?.length && !word.roots?.length) word.roots = entry.roots;
    applyContent(word);
    for (const card of cardsByWord.get(word.word) ?? []) {
      if (entry.phrases?.length && !card.phrases?.length) card.phrases = entry.phrases;
      if (entry.roots?.length && !card.roots?.length) card.roots = entry.roots;
    }
  }

  for (const membership of pkg.memberships) {
    const word = wordIndex.get(membership.word);
    if (!word) continue;
    const ref = {book: pkg.book.id, rank: membership.rank, unit: membership.unit};
    if (!word.books.some(item => item.book === ref.book && item.rank === ref.rank)) {
      word.books.push(ref);
    }
    for (const card of cardsByWord.get(word.word) ?? []) {
      if (!card.books.some(item => item.book === ref.book && item.rank === ref.rank)) {
        card.books.push(ref);
      }
    }
  }
}

const contentIndex = new Map<string, {
  phrases?: Example[];
  roots?: Array<{form: string; meaning: string; kind?: string}>;
}>();

function applyContent(word: Word): void {
  const content = contentIndex.get(word.word);
  if (!content) return;
  if (content.phrases?.length && !word.phrases?.length) word.phrases = content.phrases;
  if (content.roots?.length && !word.roots?.length) word.roots = content.roots;
  for (const card of cardsByWord.get(word.word) ?? []) {
    if (content.phrases?.length && !card.phrases?.length) card.phrases = content.phrases;
    if (content.roots?.length && !card.roots?.length) card.roots = content.roots;
  }
}

/** Merge a downloaded phrase/roots package into the in-memory catalog. */
export function registerContentPackage(pkg: ContentPackage): void {
  for (const [word, content] of Object.entries(pkg.words)) {
    contentIndex.set(word, content);
  }
  for (const word of words) applyContent(word);
}

export function cardsFor(book: string, unitStart: number, unitEnd: number): Card[] {
  return cards
    .filter(card => card.books.some(ref => ref.book === book && ref.unit >= unitStart && ref.unit <= unitEnd))
    .sort((a, b) => {
      const left = a.books.find(ref => ref.book === book)?.rank ?? 0;
      const right = b.books.find(ref => ref.book === book)?.rank ?? 0;
      return left - right;
    });
}

export function unitLabel(book: Book, unit: number): string {
  const first = (unit - 1) * book.unitSize + 1;
  const last = Math.min(unit * book.unitSize, book.wordCount);
  return "Unit " + unit + " · " + first + "–" + last;
}
