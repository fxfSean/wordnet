import {studyDate} from "./review";
import type {DayStat, StudyState} from "./study";

export type DayRow = DayStat & {date: string; label: string; height: number};
export type Mastery = {learning: number; reviewing: number; mastered: number};
export type CalendarCell = {
  key: string; date: string; day: number; count: number;
  level: number; today: boolean; inMonth: boolean;
};
export type CalendarMonth = {
  title: string; weekdays: string[]; cells: CalendarCell[]; checkInDays: number;
};

const monthNames = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];
const weekdayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function emptyDay(): DayStat {
  return {count: 0, newCount: 0, reviewCount: 0, durationMs: 0};
}

export function formatDuration(milliseconds: number): string {
  const minutes = Math.floor(Math.max(0, milliseconds) / 60_000);
  if (minutes < 60) return minutes + "m";
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? hours + "h " + rest + "m" : hours + "h";
}

export function todayStat(state: StudyState, now: number): DayStat {
  return state.history[studyDate(now)] ?? emptyDay();
}

export function recentDays(state: StudyState, now: number, days: number): DayRow[] {
  const rows: DayRow[] = [];
  const cursor = new Date(studyDate(now) + "T00:00:00Z");
  for (let index = days - 1; index >= 0; index -= 1) {
    const date = new Date(cursor);
    date.setUTCDate(date.getUTCDate() - index);
    const key = date.toISOString().slice(0, 10);
    const stat = state.history[key] ?? emptyDay();
    rows.push({
      ...stat,
      date: key,
      label: key.slice(5),
      height: 0,
    });
  }
  const max = Math.max(1, ...rows.map(row => row.count));
  for (const row of rows) {
    row.height = row.count ? Math.max(6, Math.round(row.count / max * 100)) : 0;
  }
  return rows;
}

export function mastery(state: StudyState): Mastery {
  return masteryFor(state, Object.keys(state.progress));
}

export function masteryFor(state: StudyState, keys: string[]): Mastery {
  const result = {learning: 0, reviewing: 0, mastered: 0};
  for (const key of keys) {
    const row = state.progress[key];
    if (!row) continue;
    if (row.stage >= 7) result.mastered += 1;
    else if (row.stage >= 4) result.reviewing += 1;
    else result.learning += 1;
  }
  return result;
}

export function totalStudyTime(state: StudyState): number {
  return Object.values(state.history).reduce((total, row) => total + row.durationMs, 0);
}

export function monthCalendar(state: StudyState, now: number): CalendarMonth {
  const today = studyDate(now);
  const [year, month] = today.split("-").map(Number);
  const first = new Date(Date.UTC(year, month - 1, 1));
  const days = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const leading = (first.getUTCDay() + 6) % 7;
  const cells: CalendarCell[] = [];
  const total = Math.ceil((leading + days) / 7) * 7;
  for (let index = 0; index < total; index += 1) {
    const day = index - leading + 1;
    if (day < 1 || day > days) {
      cells.push({key: "blank-" + index, date: "", day: 0, count: 0, level: 0, today: false, inMonth: false});
      continue;
    }
    const date = year + "-" + String(month).padStart(2, "0") + "-" + String(day).padStart(2, "0");
    const count = state.history[date]?.count ?? 0;
    const level = count === 0 ? 0 : count < 10 ? 1 : count < 20 ? 2 : count < 40 ? 3 : 4;
    cells.push({key: date, date, day, count, level, today: date === today, inMonth: true});
  }
  const checkInDays = Object.values(state.history).filter(row => row.count > 0).length;
  return {
    title: monthNames[month - 1] + " " + year,
    weekdays: weekdayNames,
    cells,
    checkInDays,
  };
}
