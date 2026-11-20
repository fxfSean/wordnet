import {books, bookById, words, type Word} from "../../catalog";
import {readState, writeState} from "../../local-store";
import {playSentence, playWord} from "../../audio";
import {ensureBookPackage} from "../../book-packages";
import {ensureContentPackage} from "../../content-package";
import {applyChrome, themeClass} from "../../theme";

function allBrowseWords() { return words.filter(item => item.senses.length > 0); }
let pendingWord = "";

function decodeWord(value: string): string {
  try { return decodeURIComponent(value); } catch { return value; }
}

function wordsForBook(bookId: string) {
  return allBrowseWords()
    .filter(item => item.books.some(ref => ref.book === bookId))
    .sort((a, b) => {
      const left = a.books.find(ref => ref.book === bookId)?.rank ?? 0;
      const right = b.books.find(ref => ref.book === bookId)?.rank ?? 0;
      return left - right;
    });
}

type Tab = "definition" | "examples" | "phrases" | "roots" | "derivatives" | "synonyms" | "notes";
type ExampleRow = {key: string; en: string; zh?: string; pos: string};
type TabRow = {id: Tab; label: string; count: number};
type Selected = Word & {
  hasMore: boolean;
  saved: boolean;
  note: string;
  noteDraft: string;
  activeTab: Tab;
  tabs: TabRow[];
  examples: ExampleRow[];
  derivatives: string[];
  synonyms: string[];
  antonyms: string[];
  phrases: Array<{en: string; zh?: string}>;
  roots: Array<{form: string; meaning: string}>;
  unitLabel: string;
  primaryPos: string;
};

function matchingWords(pool: Word[], query: string, savedOnly: boolean,
                       savedWords: string[], limit: number) {
  const saved = new Set(savedWords);
  return pool.filter(item => item.word.startsWith(query) && (!savedOnly || saved.has(item.word)))
    .slice(0, limit + 1);
}

function unique(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))];
}

function tabsFor(selected: Partial<Selected>, more = false): TabRow[] {
  const visibleSenses = selected.senses?.filter(sense => sense.primary || more).length ?? 0;
  return [
    {id: "definition", label: "Definitions", count: visibleSenses},
    {id: "examples", label: "Examples", count: selected.examples?.length ?? 0},
    {id: "phrases", label: "Phrases", count: selected.phrases?.length ?? 0},
    {id: "roots", label: "Roots", count: selected.roots?.length ?? 0},
    {id: "derivatives", label: "Word family", count: selected.derivatives?.length ?? 0},
    {id: "synonyms", label: "Synonyms", count: (selected.synonyms?.length ?? 0) + (selected.antonyms?.length ?? 0)},
    {id: "notes", label: "Notes", count: selected.note ? 1 : 0},
  ];
}

Page({
  data: {
    query: "", entries: wordsForBook(books[0]?.id ?? "").slice(0, 30), selected: null as Selected | null,
    more: false, savedOnly: false, limit: 30, moreWords: true, emptyMessage: "No words found.", saved: false,
    bookTitle: "General English", themeClass: "theme-dark",
  },
  onLoad(options: {word?: string}) {
    if (options.word) pendingWord = decodeWord(options.word);
  },
  onShow() {
    this.refreshList();
    applyChrome(readState().settings.theme, false);
    const previous = this.data.selected;
    const previousTab = previous?.activeTab;
    Promise.all([ensureBookPackage(readState().book), ensureContentPackage()]).then(([bookLoaded, contentLoaded]) => {
      this.refreshList();
      if (previous && (bookLoaded || contentLoaded)) {
        this.openWord(previous.word);
        const updated = this.data.selected;
        if (updated && previousTab && previousTab !== "definition") {
          this.setData({selected: {...updated, activeTab: previousTab}});
        }
      }
      this.openPending();
    });
  },
  openPending() {
    if (!pendingWord) return;
    const word = pendingWord;
    pendingWord = "";
    this.openWord(word);
  },
  refreshList() {
    const state = readState();
    const book = bookById(state.book) ?? books[0];
    const pool = this.data.savedOnly ? allBrowseWords() : wordsForBook(book?.id ?? "");
    const matches = matchingWords(pool, this.data.query, this.data.savedOnly, state.savedWords, this.data.limit);
    this.setData({
      entries: matches.slice(0, this.data.limit),
      moreWords: matches.length > this.data.limit,
      bookTitle: book ? book.title : "General English",
      themeClass: themeClass(state.settings.theme),
      emptyMessage: this.data.savedOnly && !this.data.query
        ? "No saved words yet."
        : "No words found.",
    });
  },
  search(event: WeChatInputEvent) {
    const query = event.detail.value.trim().toLowerCase();
    this.setData({query, selected: null, more: false, limit: 30});
    this.refreshList();
  },
  showSaved() {
    this.setData({savedOnly: !this.data.savedOnly, selected: null, more: false, limit: 30});
    this.refreshList();
  },
  loadMoreWords() {
    this.setData({limit: this.data.limit + 30});
    this.refreshList();
  },
  open(event: WeChatTapEvent) {
    this.openWord(event.currentTarget.dataset.word);
  },
  openWord(name: string) {
    const word = words.find(item => item.word === name);
    if (!word) return;
    const state = readState();
    const examples: ExampleRow[] = [];
    const derivatives: string[] = [];
    const synonyms: string[] = [];
    const antonyms: string[] = [];
    const phrases: Selected["phrases"] = [];
    const roots: Selected["roots"] = [];
    phrases.push(...(word.phrases ?? []));
    roots.push(...(word.roots ?? []));
    for (const sense of word.senses) {
      for (const example of sense.examples ?? []) {
        examples.push({...example, key: sense.id + "|" + examples.length, pos: sense.pos});
      }
      derivatives.push(...(sense.derivatives ?? []));
      synonyms.push(...(sense.synonyms ?? []));
      antonyms.push(...(sense.antonyms ?? []));
      phrases.push(...(sense.phrases ?? []));
      roots.push(...(sense.roots ?? []));
    }
    const phraseRows = [...new Map(phrases.map(row => [row.en, row])).values()];
    const rootRows = [...new Map(roots.map(row => [row.form, row])).values()];
    const book = bookById(state.book) ?? books[0];
    const membership = word.books.find(ref => ref.book === book?.id) ?? word.books[0];
    const note = state.notes[word.word] ?? "";
    const primary = word.senses.find(sense => sense.primary) ?? word.senses[0];
    const selected: Selected = {
      ...word,
      hasMore: word.senses.some(sense => !sense.primary),
      saved: state.savedWords.includes(word.word),
      note,
      noteDraft: note,
      activeTab: "definition",
      tabs: [],
      examples,
      derivatives: unique(derivatives),
      synonyms: unique(synonyms),
      antonyms: unique(antonyms),
      phrases: phraseRows,
      roots: rootRows,
      unitLabel: membership ? "Unit " + membership.unit + " · Rank " + membership.rank : "Word",
      primaryPos: primary?.pos ?? "word",
    };
    selected.tabs = tabsFor(selected, false);
    this.setData({selected, more: false, saved: selected.saved});
  },
  selectTab(event: WeChatTapEvent) {
    const tab = event.currentTarget.dataset.tab as Tab;
    const selected = this.data.selected;
    if (!selected || !tab) return;
    this.setData({selected: {...selected, activeTab: tab}});
  },
  speakWord() {
    const selected = this.data.selected;
    if (!selected) return;
    playWord(selected.word, readState().settings.accent === "uk" ? "uk" : "us");
  },
  speakExample(event: WeChatTapEvent) {
    const selected = this.data.selected;
    if (!selected) return;
    const example = selected.examples[Number(event.currentTarget.dataset.index ?? 0)];
    if (example) playSentence(example.en);
  },
  saveSentence(event: WeChatTapEvent) {
    const selected = this.data.selected;
    const example = selected?.examples[Number(event.currentTarget.dataset.index ?? 0)];
    if (!selected || !example) return;
    const state = readState();
    if (state.savedSentences.some(row => row.en === example.en)) {
      wx.showToast({title: "Already in sentence bank", icon: "none"});
      return;
    }
    try {
      writeState({...state, savedSentences: [...state.savedSentences, {
        en: example.en, zh: example.zh, word: selected.word, pos: example.pos,
      }].slice(-500)});
      wx.showToast({title: "Sentence saved", icon: "none"});
    } catch {
      wx.showToast({title: "Could not save the sentence", icon: "none"});
    }
  },
  noteInput(event: WeChatInputEvent) {
    const selected = this.data.selected;
    if (selected) this.setData({selected: {...selected, noteDraft: event.detail.value}});
  },
  saveNote() {
    const selected = this.data.selected;
    if (!selected) return;
    const state = readState();
    const notes = {...state.notes};
    const value = selected.noteDraft.trim();
    if (value) notes[selected.word] = value;
    else delete notes[selected.word];
    try {
      writeState({...state, notes});
      const updated = {...selected, note: value};
      updated.tabs = tabsFor(updated, this.data.more);
      this.setData({selected: updated});
      wx.showToast({title: "Note saved", icon: "none"});
    } catch {
      wx.showToast({title: "Could not save the note", icon: "none"});
    }
  },
  toggleSaved() {
    const selected = this.data.selected;
    if (!selected) return;
    const state = readState();
    const saved = !state.savedWords.includes(selected.word);
    const savedWords = saved
      ? [...state.savedWords, selected.word]
      : state.savedWords.filter(item => item !== selected.word);
    try {
      writeState({...state, savedWords});
      this.setData({selected: {...selected, saved}, saved});
      this.refreshList();
    } catch {
      wx.showToast({title: "Could not update saved words", icon: "none"});
    }
  },
  toggle() {
    const more = !this.data.more;
    const selected = this.data.selected;
    if (!selected) { this.setData({more}); return; }
    const updated = {...selected, tabs: tabsFor(selected, more)};
    this.setData({more, selected: updated});
  },
  back() { this.setData({selected: null}); },
  shelf() { wx.navigateTo({url: "/pages/books/index"}); },
});
