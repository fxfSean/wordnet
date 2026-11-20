import {books, bookById, cardsFor, words} from "../../catalog";
import {readState, writeState} from "../../local-store";
import {formatDuration, masteryFor, todayStat} from "../../stats";
import {studyStreak} from "../../study";
import {ensureBookPackage} from "../../book-packages";
import {applyChrome, themeClass, themeLabel, toggleTheme} from "../../theme";
import type {Theme} from "../../study";

const goals = [10, 20, 30];
const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function unitText(start: number, end: number, unitCount: number): string {
  if (start <= 1 && end >= unitCount) return "All units";
  return start === end ? "Unit " + start : "Units " + start + "–" + end;
}

function dateLabel(now: number): string {
  const date = new Date(now);
  return weekdays[date.getDay()] + ", " + months[date.getMonth()] + " " + date.getDate();
}

Page({
  data: {
    due: 0, studied: 0, mastered: 0, today: 0, goal: 20, words: words.length,
    bookTitle: "General English", unitText: "All units",
    streak: 0, todayTime: "0m", todayNew: 0, newRemaining: 0, goalPercent: 0,
    learning: 0, reviewing: 0, dateLabel: "",
    theme: "dark" as Theme, themeClass: "theme-dark", themeLabel: "Light",
  },
  onShow() {
    this.refresh();
    applyChrome(readState().settings.theme, true);
    ensureBookPackage(readState().book).then(loaded => {
      if (loaded) this.refresh();
    });
  },
  refresh() {
    const state = readState();
    const now = Date.now();
    const book = bookById(state.book) ?? books[0];
    const unitEnd = Math.min(state.unitEnd, book?.unitCount ?? 1);
    const active = book ? cardsFor(book.id, state.unitStart, unitEnd) : [];
    const today = todayStat(state, now);
    const buckets = masteryFor(state, active.map(card => card.key));
    const progress = state.progress;
    const newRemaining = Math.max(0, state.goal - today.newCount);
    this.setData({
      due: active.filter(card => progress[card.key]?.nextReviewAt <= now).length,
      studied: active.filter(card => progress[card.key]).length,
      mastered: buckets.mastered,
      learning: buckets.learning,
      reviewing: buckets.reviewing,
      today: today.count,
      todayNew: today.newCount,
      newRemaining,
      goalPercent: Math.min(100, Math.round(today.newCount / Math.max(1, state.goal) * 100)),
      todayTime: formatDuration(today.durationMs),
      streak: studyStreak(state, now),
      goal: state.goal,
      words: book?.wordCount ?? words.length,
      bookTitle: book?.title ?? "General English",
      unitText: book ? unitText(state.unitStart, unitEnd, book.unitCount) : "All units",
      dateLabel: dateLabel(now),
      theme: state.settings.theme,
      themeClass: themeClass(state.settings.theme),
      themeLabel: themeLabel(state.settings.theme),
    });
  },
  toggleTheme() {
    const theme = toggleTheme(this.data.theme, true);
    this.setData({theme, themeClass: themeClass(theme), themeLabel: themeLabel(theme)});
  },
  setGoal(event: WeChatPickerEvent) {
    const goal = goals[Number(event.detail.value)];
    if (goal) {
      try { writeState({...readState(), goal}); this.refresh(); }
      catch { wx.showToast({title: "Could not save the goal", icon: "none"}); }
    }
  },
  plan() { wx.navigateTo({url: "/pages/books/index"}); },
  content() { wx.navigateTo({url: "/pages/content/index"}); },
  stats() { wx.navigateTo({url: "/pages/stats/index"}); },
  study() { wx.navigateTo({url: "/pages/study/index"}); },
  review() { wx.navigateTo({url: "/pages/study/index?mode=review"}); },
  browse() { wx.navigateTo({url: "/pages/library/index"}); },
});
