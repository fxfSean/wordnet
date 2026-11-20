import {books, bookById, cardsFor, type Card} from "../../catalog";
import {readState} from "../../local-store";
import {playWord, stopAudio} from "../../audio";
import {ensureBookPackage} from "../../book-packages";
import {applyChrome, themeClass, themeLabel, toggleTheme} from "../../theme";
import type {Theme} from "../../study";

function practiceCards(mode: string): Card[] {
  const state = readState();
  const now = Date.now();
  const book = bookById(state.book) ?? books[0];
  if (!book) return [];
  const end = Math.min(state.unitEnd, book.unitCount);
  const pool = cardsFor(book.id, state.unitStart, end);
  const due = pool.filter(card => state.progress[card.key]?.nextReviewAt <= now)
    .sort((a, b) => state.progress[a.key].nextReviewAt - state.progress[b.key].nextReviewAt);
  const rest = pool.filter(card => !due.includes(card));
  return [...due, ...rest].slice(0, 20).map(card => {
    const ref = card.books.find(item => item.book === book.id);
    return ref ? {...card, unit: ref.unit} : card;
  });
}

Page({
  data: {
    mode: "spell" as "spell" | "listen", queue: [] as Card[], index: 0,
    current: null as Card | null, input: "", checked: false, correct: false,
    feedback: "", total: 0, completed: 0, correctCount: 0, progressPercent: 0,
    accent: "us", empty: "No cards in this range.",
    theme: "dark" as Theme, themeClass: "theme-dark", themeLabel: "Light",
  },
  onLoad(options: {mode?: string}) {
    this.setData({mode: options.mode === "listen" ? "listen" : "spell"});
    this.load();
    ensureBookPackage(readState().book).then(loaded => {
      if (loaded) this.load();
    });
  },
  load() {
    const queue = practiceCards(this.data.mode);
    const state = readState();
    this.setData({
      queue,
      index: 0,
      current: queue[0] ?? null,
      input: "",
      checked: false,
      correct: false,
      feedback: "",
      total: queue.length,
      completed: 0,
      correctCount: 0,
      progressPercent: 0,
      accent: state.settings.accent,
      theme: state.settings.theme,
      themeClass: themeClass(state.settings.theme),
      themeLabel: themeLabel(state.settings.theme),
    });
    applyChrome(state.settings.theme, true);
    if (queue[0] && this.data.mode === "listen") this.replay();
  },
  onShow() {
    applyChrome(readState().settings.theme, true);
    if (!this.data.queue.length) this.load();
  },
  onHide() { stopAudio(); },
  onUnload() { stopAudio(); },
  setMode(event: WeChatTapEvent) {
    const mode = event.currentTarget.dataset.mode === "listen" ? "listen" : "spell";
    this.setData({mode});
    this.load();
  },
  input(event: WeChatInputEvent) {
    this.setData({input: event.detail.value});
  },
  replay() {
    const current = this.data.current;
    if (current) playWord(current.word, this.data.accent === "uk" ? "uk" : "us");
  },
  check() {
    const current = this.data.current;
    if (!current || this.data.checked) return;
    const answer = this.data.input.trim().toLowerCase();
    const correct = answer === current.word.toLowerCase();
    this.setData({
      checked: true,
      correct,
      feedback: correct ? "Correct — " + current.word : "Answer: " + current.word,
    });
    if (correct) this.setData({correctCount: this.data.correctCount + 1});
    playWord(current.word, this.data.accent === "uk" ? "uk" : "us");
  },
  skip() {
    const current = this.data.current;
    if (!current) return;
    if (!this.data.checked) {
      this.setData({checked: true, correct: false, feedback: "Answer: " + current.word});
      return;
    }
    this.next();
  },
  next() {
    const nextIndex = this.data.index + 1;
    if (nextIndex >= this.data.queue.length) {
      this.setData({current: null, completed: this.data.total, progressPercent: 100});
      return;
    }
    this.setData({
      index: nextIndex,
      current: this.data.queue[nextIndex],
      input: "",
      checked: false,
      correct: false,
      feedback: "",
      completed: this.data.completed + 1,
      progressPercent: Math.round(nextIndex / this.data.total * 100),
    });
    if (this.data.mode === "listen") this.replay();
  },
  restart() { this.load(); },
  home() { wx.navigateBack(); },
  toggleTheme() {
    const theme = toggleTheme(this.data.theme, true);
    this.setData({theme, themeClass: themeClass(theme), themeLabel: themeLabel(theme)});
  },
});
