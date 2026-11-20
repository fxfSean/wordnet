import {books, bookById, cardByKey, cards, cardsFor, type Card, type Example} from "../../catalog";
import {readState, writeState} from "../../local-store";
import {applyRating, addStudyTime, buildQueue, type StudyState, type Theme} from "../../study";
import type {Rating} from "../../review";
import {playSentence, playWord, stopAudio} from "../../audio";
import {ensureBookPackage} from "../../book-packages";
import {ensureContentPackage} from "../../content-package";
import {applyChrome, themeClass, themeLabel, toggleTheme} from "../../theme";

type Root = {form: string; meaning: string; kind?: string};

let timer: ReturnType<typeof setInterval> | undefined;
let activeEvent = "";
let activeSince = 0;
let lastFlush = 0;
let lastAutoKey = "";

function activeKeys(state: StudyState): string[] {
  const book = bookById(state.book) ?? books[0];
  if (!book) return cards.map(card => card.key);
  const end = Math.min(state.unitEnd, book.unitCount);
  return cardsFor(book.id, state.unitStart, end).map(card => card.key);
}

function examplesOf(card: Card): Example[] {
  return card.examples ?? [];
}

Page({
  data: {
    card: null as Card | null, revealed: false, remaining: 0, completed: 0, waiting: "",
    dueOnly: false, feedback: "", examples: [] as Example[], note: "", accent: "us",
    autoplay: true, progressPercent: 0, total: 0, accentLabel: "US", cardUnit: 0,
    phrases: [] as Example[], roots: [] as Root[],
    theme: "dark" as Theme, themeClass: "theme-dark", themeLabel: "Light",
  },
  onLoad(options: {mode?: string}) {
    this.setData({dueOnly: options.mode === "review"});
  },
  onShow() {
    this.refresh();
    applyChrome(readState().settings.theme, true);
    ensureBookPackage(readState().book).then(loaded => {
      if (loaded) this.refresh();
    });
    ensureContentPackage().then(loaded => {
      if (loaded) this.refresh();
    });
    activeSince = Date.now();
    lastFlush = activeSince;
    if (timer !== undefined) clearInterval(timer);
    timer = setInterval(() => {
      if (Date.now() - lastFlush >= 60_000) this.flushTime();
      if (!this.data.card) this.refresh();
    }, 5000);
  },
  onHide() { this.flushTime(); this.stopTimer(); stopAudio(); },
  onUnload() { this.flushTime(); this.stopTimer(); stopAudio(); },
  stopTimer() { if (timer !== undefined) clearInterval(timer); timer = undefined; },
  flushTime() {
    if (!activeSince) return;
    const now = Date.now();
    const elapsed = now - activeSince;
    activeSince = now;
    lastFlush = now;
    if (elapsed <= 0) return;
    try { writeState(addStudyTime(readState(), elapsed, now)); }
    catch { /* progress writes surface their own errors */ }
  },
  refresh() {
    const now = Date.now();
    const state = readState();
    const keys = activeKeys(state);
    const queue = buildQueue(keys, state, now, this.data.dueOnly);
    const card = queue[0] ? cardByKey(queue[0]) ?? null : null;
    const currentBook = bookById(state.book) ?? books[0];
    const reviews = keys
      .map(key => state.progress[key]?.nextReviewAt)
      .filter((value): value is number => typeof value === "number");
    const nextReview = reviews.length ? Math.min(...reviews) : Infinity;
    const wait = Math.max(1, Math.ceil((nextReview - now) / 60000));
    activeEvent = card ? card.key + "|" + now : "";
    const membership = card?.books.find(ref => ref.book === currentBook?.id) ?? card?.books[0];
    const total = this.data.completed + queue.length;
    const sameCard = card !== null && this.data.card?.key === card.key;
    this.setData({
      card, revealed: sameCard ? this.data.revealed : false, remaining: queue.length,
      examples: card ? examplesOf(card) : [],
      phrases: card?.phrases ?? [],
      roots: card?.roots ?? [],
      waiting: !card && Number.isFinite(wait) && wait <= 10 ? "Next review in " + wait + " min" : "",
      note: card ? (state.notes[card.word] ?? "") : "",
      accent: state.settings.accent,
      accentLabel: state.settings.accent === "uk" ? "UK" : "US",
      autoplay: state.settings.autoplay,
      cardUnit: membership?.unit ?? 0,
      total,
      progressPercent: total ? Math.round(this.data.completed / total * 100) : 0,
      theme: state.settings.theme,
      themeClass: themeClass(state.settings.theme),
      themeLabel: themeLabel(state.settings.theme),
    });
    if (!card) {
      lastAutoKey = "";
    } else if (state.settings.autoplay && card.key !== lastAutoKey) {
      lastAutoKey = card.key;
      playWord(card.word, state.settings.accent === "uk" ? "uk" : "us");
    }
  },
  reveal() {
    if (!this.data.card) return;
    this.setData({revealed: true});
  },
  speakWord() {
    if (this.data.card) playWord(this.data.card.word, this.data.accent === "uk" ? "uk" : "us");
  },
  speakExample(event: WeChatTapEvent) {
    const index = Number(event.currentTarget.dataset.index ?? 0);
    const example = this.data.examples[index];
    if (example) playSentence(example.en);
  },
  saveSentence(event: WeChatTapEvent) {
    const card = this.data.card;
    const example = this.data.examples[Number(event.currentTarget.dataset.index ?? 0)];
    if (!card || !example) return;
    const state = readState();
    if (state.savedSentences.some(row => row.en === example.en)) {
      wx.showToast({title: "Already in sentence bank", icon: "none"});
      return;
    }
    try {
      writeState({...state, savedSentences: [...state.savedSentences, {
        en: example.en, zh: example.zh, word: card.word, pos: card.pos,
      }].slice(-500)});
      wx.showToast({title: "Sentence saved", icon: "none"});
    } catch {
      wx.showToast({title: "Could not save the sentence", icon: "none"});
    }
  },
  editNote() {
    const card = this.data.card;
    if (!card) return;
    wx.showModal({
      title: "Note · " + card.word,
      editable: true,
      content: this.data.note,
      placeholderText: "Add a memory hook, translation or usage note",
      success: result => {
        if (!result.confirm) return;
        const state = readState();
        const notes = {...state.notes};
        const value = (result.content ?? "").trim();
        if (value) notes[card.word] = value;
        else delete notes[card.word];
        try {
          writeState({...state, notes});
          this.setData({note: value});
        } catch {
          wx.showToast({title: "Could not save the note", icon: "none"});
        }
      },
    });
  },
  know() { this.rate("know"); },
  fuzzy() { this.rate("fuzzy"); },
  dontKnow() { this.rate("dont_know"); },
  openDetail() {
    const card = this.data.card;
    if (card) wx.navigateTo({url: "/pages/library/index?word=" + encodeURIComponent(card.word)});
  },
  rate(rating: Rating) {
    const card = this.data.card;
    if (!card || !this.data.revealed || !activeEvent) return;
    const eventId = activeEvent;
    activeEvent = "";
    const now = Date.now();
    const next = applyRating(readState(), card.key, rating, eventId, now);
    try {
      writeState(next);
    } catch {
      activeEvent = eventId;
      wx.showToast({title: "Could not save. Try again.", icon: "none"});
      return;
    }
    const days = Math.round((next.progress[card.key].nextReviewAt - now) / 86_400_000);
    const interval = rating === "dont_know"
      ? "10 min"
      : rating === "fuzzy"
        ? "30 min"
        : days + (days === 1 ? " day" : " days");
    this.setData({completed: this.data.completed + 1, feedback: card.word + " · Review again in " + interval});
    this.refresh();
  },
  home() { wx.navigateBack(); },
  toggleTheme() {
    const theme = toggleTheme(this.data.theme, true);
    this.setData({theme, themeClass: themeClass(theme), themeLabel: themeLabel(theme)});
  },
});
