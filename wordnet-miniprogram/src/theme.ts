import {readState, writeState} from "./local-store";
import type {Theme} from "./study";

/** Class added to each page root so WXSS can switch the palette. */
export function themeClass(theme: Theme): string {
  return theme === "light" ? "theme-light" : "theme-dark";
}

export function themeLabel(theme: Theme): string {
  return theme === "light" ? "Dark" : "Light";
}

/**
 * Keep the native navigation bar in sync with the page. Only the immersive
 * pages (home, study, spelling) use a dark bar; the paper pages stay light.
 */
export function applyChrome(theme: Theme, immersive = false): void {
  const dark = immersive && theme === "dark";
  const backgroundColor = dark ? "#0B1512" : "#F6F3EA";
  wx.setNavigationBarColor?.({
    frontColor: dark ? "#ffffff" : "#000000",
    backgroundColor,
  });
  wx.setBackgroundColor?.({backgroundColor});
}

/** Persist a new theme and update the current page chrome immediately. */
export function setTheme(theme: Theme, immersive = false): void {
  const state = readState();
  if (state.settings.theme !== theme) {
    try {
      writeState({...state, settings: {...state.settings, theme}});
    } catch {
      // The UI still switches; the next launch will fall back to the old theme.
    }
  }
  applyChrome(theme, immersive);
}

export function toggleTheme(theme: Theme, immersive = false): Theme {
  const next: Theme = theme === "dark" ? "light" : "dark";
  setTheme(next, immersive);
  return next;
}
