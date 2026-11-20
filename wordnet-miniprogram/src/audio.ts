import {audioEndpoint, sentenceAudioEndpoint} from "./cloud-config";
import type {Accent} from "./study";

type InnerAudio = {
  src: string;
  volume: number;
  obeyMuteSwitch?: boolean;
  stop(): void;
  play(): void;
  destroy(): void;
  onError?(callback: (error: unknown) => void): void;
};

let audio: InnerAudio | undefined;
let failed = false;

function player(): InnerAudio | undefined {
  if (audio) return audio;
  const factory = (wx as unknown as {createInnerAudioContext?: () => InnerAudio}).createInnerAudioContext;
  if (typeof factory !== "function") return undefined;
  audio = factory();
  audio.volume = 1;
  audio.obeyMuteSwitch = false;
  audio.onError?.(() => {
    if (failed) return;
    failed = true;
    setTimeout(() => { failed = false; }, 5000);
    wx.showToast({title: "Audio unavailable", icon: "none"});
  });
  return audio;
}

export function wordAudioUrl(word: string, accent: Accent): string {
  const type = accent === "uk" ? 1 : 2;
  return audioEndpoint + "?audio=" + encodeURIComponent(word) + "&type=" + type;
}

export function sentenceAudioUrl(sentence: string): string {
  return sentenceAudioEndpoint + "?lan=en&spd=3&source=web&text=" + encodeURIComponent(sentence);
}

export function playUrl(url: string): void {
  if (!url) return;
  const instance = player();
  if (!instance) return;
  try {
    instance.stop();
    instance.src = url;
    instance.play();
  } catch {
    wx.showToast({title: "Audio unavailable", icon: "none"});
  }
}

export function playWord(word: string, accent: Accent): void {
  playUrl(wordAudioUrl(word, accent));
}

export function playSentence(sentence: string): void {
  playUrl(sentenceAudioUrl(sentence));
}

export function stopAudio(): void {
  try {
    audio?.stop();
  } catch {
    // The player may already be released on a previous page.
  }
}
