import {books, bookById, cardsFor} from "../../catalog";
import {readState, writeState} from "../../local-store";
import {confirmImport, exportToFile, importFromFile} from "../../backup";
import {formatDuration, masteryFor, monthCalendar, recentDays, todayStat, totalStudyTime, type CalendarMonth, type DayRow} from "../../stats";
import {studyStreak, type DayStat} from "../../study";
import {ensureBookPackage} from "../../book-packages";
import {applyChrome, themeClass} from "../../theme";

function sum(rows: DayStat[]): DayStat {
  return rows.reduce<DayStat>((total, row) => ({
    count: total.count + row.count,
    newCount: total.newCount + row.newCount,
    reviewCount: total.reviewCount + row.reviewCount,
    durationMs: total.durationMs + row.durationMs,
  }), {count: 0, newCount: 0, reviewCount: 0, durationMs: 0});
}

Page({
  data: {
    todayCount: 0, todayNew: 0, todayReview: 0, todayTime: "0m",
    weekCount: 0, weekTime: "0m", monthCount: 0, monthTime: "0m",
    streak: 0, totalStudied: 0, due: 0, learning: 0, reviewing: 0, mastered: 0,
    totalTime: "0m", bars: [] as DayRow[], recent: [] as DayRow[], bookTitle: "",
    masteryRows: [] as Array<{label: string; value: number; percent: number; tone: string}>,
    calendar: {title: "", weekdays: [], cells: [], checkInDays: 0} as CalendarMonth,
    themeClass: "theme-dark",
  },
  onShow() {
    this.refresh();
    applyChrome(readState().settings.theme, false);
    ensureBookPackage(readState().book).then(loaded => {
      if (loaded) this.refresh();
    });
  },
  refresh() {
    const state = readState();
    const now = Date.now();
    const book = bookById(state.book) ?? books[0];
    const end = book ? Math.min(state.unitEnd, book.unitCount) : 1;
    const active = book ? cardsFor(book.id, state.unitStart, end) : [];
    const keys = active.map(card => card.key);
    const buckets = masteryFor(state, keys);
    const today = todayStat(state, now);
    const month = recentDays(state, now, 30);
    const week = recentDays(state, now, 7);
    const weekStats = sum(week);
    const monthStats = sum(month);
    const masteryTotal = Math.max(1, buckets.learning + buckets.reviewing + buckets.mastered);
    const masteryRows = [
      {label: "Learning", value: buckets.learning, percent: Math.round(buckets.learning / masteryTotal * 100), tone: "learning"},
      {label: "Reviewing", value: buckets.reviewing, percent: Math.round(buckets.reviewing / masteryTotal * 100), tone: "reviewing"},
      {label: "Mastered", value: buckets.mastered, percent: Math.round(buckets.mastered / masteryTotal * 100), tone: "mastered"},
    ];
    this.setData({
      todayCount: today.count,
      todayNew: today.newCount,
      todayReview: today.reviewCount,
      todayTime: formatDuration(today.durationMs),
      weekCount: weekStats.count,
      weekTime: formatDuration(weekStats.durationMs),
      monthCount: monthStats.count,
      monthTime: formatDuration(monthStats.durationMs),
      streak: studyStreak(state, now),
      totalStudied: keys.filter(key => state.progress[key]).length,
      due: active.filter(card => state.progress[card.key]?.nextReviewAt <= now).length,
      learning: buckets.learning,
      reviewing: buckets.reviewing,
      mastered: buckets.mastered,
      masteryRows,
      totalTime: formatDuration(totalStudyTime(state)),
      bars: recentDays(state, now, 14),
      recent: month.slice(-7).reverse(),
      bookTitle: book ? book.title : "",
      calendar: monthCalendar(state, now),
      themeClass: themeClass(state.settings.theme),
    });
  },
  async exportBackup() {
    try {
      const result = await exportToFile(readState());
      wx.showToast({title: result === "clipboard" ? "Backup copied" : "Backup ready", icon: "none"});
    } catch (error) {
      wx.showToast({title: (error as Error).message || "Export failed", icon: "none"});
    }
  },
  async importBackup() {
    if (!(await confirmImport())) return;
    try {
      const state = await importFromFile();
      writeState(state);
      this.refresh();
      wx.showToast({title: "Backup restored", icon: "none"});
    } catch (error) {
      wx.showToast({title: (error as Error).message || "Import failed", icon: "none"});
    }
  },
});
