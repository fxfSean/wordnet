import {normalizeState, type StudyState} from "./study";

const key = "word-study-v1";

export function readState(): StudyState {
  const state = wx.getStorageSync(key);
  return state && typeof state === "object"
    ? normalizeState(state)
    : normalizeState(undefined);
}

export function writeState(state: StudyState): void {
  wx.setStorageSync(key, state);
}
