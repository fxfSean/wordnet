import {books, bookById, cardsFor, unitLabel, type Book} from "../../catalog";
import {readState, writeState} from "../../local-store";
import {ensureBookPackage} from "../../book-packages";
import type {StudyState} from "../../study";
import {applyChrome, setTheme as writeTheme} from "../../theme";

const goals = [10, 20, 30];
const groupSizes = [10, 15, 20, 30];

type CoverRow = {
  id: string; title: string; subtitle: string; wordCount: number;
  studied: number; percent: number; color: string; selected: boolean;
};

function coverRows(state: StudyState, selectedId: string): CoverRow[] {
  return books.map((book, index) => {
    const cards = cardsFor(book.id, 1, Math.max(1, book.unitCount));
    const studied = cards.filter(card => state.progress[card.key]).length;
    return {
      id: book.id,
      title: book.title,
      subtitle: book.subtitle,
      wordCount: book.wordCount,
      studied,
      percent: cards.length ? Math.min(100, Math.round(studied / cards.length * 100)) : 0,
      color: "cover-" + (index % 8),
      selected: book.id === selectedId,
    };
  });
}

function bookIndex(book: Book | undefined): number {
  return book ? Math.max(0, books.findIndex(item => item.id === book.id)) : 0;
}

Page({
  data: {
    bookTitles: [] as string[], bookIndex: 0, bookTitle: "", bookSubtitle: "", bookDescription: "", sourceLabel: "",
    bookCovers: [] as CoverRow[], scrollTarget: "",
    unitLabels: [] as string[], startIndex: 0, endIndex: 0, startLabel: "", endLabel: "",
    goals, goalIndex: 1, goal: 20, accents: ["US", "UK"], accentIndex: 0, accentLabel: "US", autoplay: true,
    groupSizes, groupIndex: 2, groupSize: 20, theme: "dark" as "dark" | "light",
    cardCount: 0, unitCount: 0, summary: "",
  },
  onLoad() {
    this.load();
    ensureBookPackage(readState().book).then(loaded => {
      if (loaded) this.load();
    });
  },
  load() {
    const state = readState();
    applyChrome(state.settings.theme, false);
    const book = bookById(state.book) ?? books[0];
    if (!book) return;
    const index = bookIndex(book);
    const unitLabels = Array.from({length: book.unitCount}, (_, i) => unitLabel(book, i + 1));
    const start = Math.max(1, Math.min(state.unitStart, book.unitCount));
    const end = Math.max(start, Math.min(state.unitEnd, book.unitCount));
    this.setData({
      bookTitles: books.map(item => item.title),
      bookCovers: coverRows(state, book.id),
      scrollTarget: "book-" + book.id,
      bookIndex: index,
      bookTitle: book.title,
      bookSubtitle: book.subtitle,
      bookDescription: book.description ?? "",
      sourceLabel: book.source.name + " " + book.source.version + " · " + book.source.license,
      unitLabels,
      unitCount: book.unitCount,
      startIndex: start - 1,
      endIndex: end - 1,
      startLabel: unitLabels[start - 1],
      endLabel: unitLabels[end - 1],
      goals,
      goalIndex: Math.max(0, goals.indexOf(state.goal)),
      goal: state.goal,
      groupSizes,
      groupIndex: Math.max(0, groupSizes.indexOf(state.settings.groupSize)),
      groupSize: state.settings.groupSize,
      accents: ["US", "UK"],
      accentIndex: state.settings.accent === "uk" ? 1 : 0,
      accentLabel: state.settings.accent === "uk" ? "UK" : "US",
      autoplay: state.settings.autoplay,
      theme: state.settings.theme,
      cardCount: cardsFor(book.id, start, end).length,
      summary: book.wordCount + " words · " + book.unitCount + " units",
    });
  },
  selectBookById(event: WeChatTapEvent) {
    const id = event.currentTarget.dataset.id;
    const index = books.findIndex(book => book.id === id);
    if (index >= 0) this.selectBookAt(index);
  },
  selectBook(event: WeChatPickerEvent) {
    this.selectBookAt(Number(event.detail.value));
  },
  selectBookAt(index: number) {
    const book = books[index];
    if (!book) return;
    const unitLabels = Array.from({length: book.unitCount}, (_, i) => unitLabel(book, i + 1));
    this.setData({
      bookCovers: this.data.bookCovers.map(row => ({...row, selected: row.id === book.id})),
      scrollTarget: "book-" + book.id,
      bookIndex: index,
      bookTitle: book.title,
      bookSubtitle: book.subtitle,
      bookDescription: book.description ?? "",
      sourceLabel: book.source.name + " " + book.source.version + " · " + book.source.license,
      unitLabels,
      unitCount: book.unitCount,
      startIndex: 0,
      endIndex: book.unitCount - 1,
      startLabel: unitLabels[0],
      endLabel: unitLabels[book.unitCount - 1],
      cardCount: cardsFor(book.id, 1, book.unitCount).length,
      summary: book.wordCount + " words · " + book.unitCount + " units",
    });
    ensureBookPackage(book.id).then(loaded => {
      if (!loaded) return;
      const updated = bookById(book.id);
      if (!updated) return;
      const labels = Array.from({length: updated.unitCount}, (_, i) => unitLabel(updated, i + 1));
      this.setData({
        bookCovers: coverRows(readState(), updated.id),
        scrollTarget: "book-" + updated.id,
        bookSubtitle: updated.subtitle,
        bookDescription: updated.description ?? "",
        unitLabels: labels,
        unitCount: updated.unitCount,
        startIndex: 0,
        endIndex: updated.unitCount - 1,
        startLabel: labels[0],
        endLabel: labels[updated.unitCount - 1],
        cardCount: cardsFor(updated.id, 1, updated.unitCount).length,
        summary: updated.wordCount + " words · " + updated.unitCount + " units",
      });
    });
  },
  setStart(event: WeChatPickerEvent) {
    const start = Number(event.detail.value);
    const end = Math.max(start, this.data.endIndex);
    const book = books[this.data.bookIndex] ?? books[0];
    this.setData({
      startIndex: start,
      endIndex: end,
      startLabel: this.data.unitLabels[start],
      endLabel: this.data.unitLabels[end],
      cardCount: book ? cardsFor(book.id, start + 1, end + 1).length : 0,
    });
  },
  setEnd(event: WeChatPickerEvent) {
    const end = Number(event.detail.value);
    const start = Math.min(end, this.data.startIndex);
    const book = books[this.data.bookIndex] ?? books[0];
    this.setData({
      startIndex: start,
      endIndex: end,
      startLabel: this.data.unitLabels[start],
      endLabel: this.data.unitLabels[end],
      cardCount: book ? cardsFor(book.id, start + 1, end + 1).length : 0,
    });
  },
  setGoal(event: WeChatPickerEvent) {
    const goalIndex = Number(event.detail.value);
    this.setData({goalIndex, goal: goals[goalIndex] ?? 20});
  },
  setGroup(event: WeChatPickerEvent) {
    const groupIndex = Number(event.detail.value);
    this.setData({groupIndex, groupSize: groupSizes[groupIndex] ?? 20});
  },
  setAccent(event: WeChatPickerEvent) {
    const accentIndex = Number(event.detail.value);
    this.setData({accentIndex, accentLabel: accentIndex === 1 ? "UK" : "US"});
  },
  toggleAutoplay(event: WeChatSwitchEvent) {
    this.setData({autoplay: event.detail.value});
  },
  selectTheme(event: WeChatTapEvent) {
    const theme = event.currentTarget.dataset.theme === "light" ? "light" : "dark";
    writeTheme(theme, false);
    this.setData({theme});
  },
  save() {
    const state = readState();
    const book = books[this.data.bookIndex] ?? books[0];
    if (!book) return;
    const next = {
      ...state,
      book: book.id,
      unitStart: this.data.startIndex + 1,
      unitEnd: this.data.endIndex + 1,
      goal: goals[this.data.goalIndex] ?? state.goal,
      settings: {
        ...state.settings,
        accent: this.data.accentIndex === 1 ? "uk" as const : "us" as const,
        autoplay: this.data.autoplay,
        groupSize: groupSizes[this.data.groupIndex] ?? state.settings.groupSize,
      },
    };
    try {
      writeState(next);
      wx.showToast({title: "Plan saved", icon: "none"});
      wx.navigateBack();
    } catch {
      wx.showToast({title: "Could not save the plan", icon: "none"});
    }
  },
});
