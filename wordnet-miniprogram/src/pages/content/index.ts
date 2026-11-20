import {books, bookById, cards, words} from "../../catalog";
import {readState, writeState} from "../../local-store";
import {playSentence} from "../../audio";
import {studyDate} from "../../review";
import type {SavedSentence} from "../../study";
import {ensureBookPackage} from "../../book-packages";

type ContentTab = "learning" | "saved" | "sentences" | "notes";
type TabRow = {id: ContentTab; label: string; count: number};
type LearningRow = {
  key: string; word: string; pos: string; definition: string;
  stage: number; stageLabel: string; tone: string; due: boolean; last: string;
};
type SavedRow = {word: string; pos: string; definition: string; note: string};
type NoteRow = {word: string; note: string; definition: string};
type SentenceRow = SavedSentence & {key: string};

function stageLabel(stage: number): string {
  if (stage >= 7) return "Mastered";
  if (stage >= 4) return "Reviewing";
  if (stage >= 1) return "Learning";
  return "Relearning";
}

Page({
  data: {
    bookTitle: "", tab: "learning" as ContentTab, tabs: [] as TabRow[],
    learning: [] as LearningRow[], saved: [] as SavedRow[],
    sentences: [] as SentenceRow[], notes: [] as NoteRow[],
    dueCount: 0, empty: "",
  },
  onShow() {
    this.refresh();
    ensureBookPackage(readState().book).then(loaded => {
      if (loaded) this.refresh();
    });
  },
  refresh() {
    const state = readState();
    const now = Date.now();
    const book = bookById(state.book) ?? books[0];
    const byKey = new Map(cards.map(card => [card.key, card]));
    const byWord = new Map(words.map(word => [word.word, word]));

    const learning: LearningRow[] = [];
    for (const [key, row] of Object.entries(state.progress)) {
      const card = byKey.get(key);
      if (!card) continue;
      learning.push({
        key,
        word: card.word,
        pos: card.pos,
        definition: card.definition,
        stage: row.stage,
        stageLabel: stageLabel(row.stage),
        tone: row.stage >= 7 ? "mastered" : row.stage >= 4 ? "reviewing" : "learning",
        due: row.nextReviewAt <= now,
        last: row.lastReviewedAt ? studyDate(row.lastReviewedAt) : "—",
      });
    }
    learning.sort((a, b) => (b.last > a.last ? 1 : b.last < a.last ? -1 : a.word.localeCompare(b.word)));

    const saved: SavedRow[] = [];
    for (const word of state.savedWords) {
      const entry = byWord.get(word);
      if (!entry) continue;
      const sense = entry.senses.find(item => item.primary) ?? entry.senses[0];
      saved.push({
        word,
        pos: sense?.pos ?? "",
        definition: sense?.definition ?? "",
        note: state.notes[word] ?? "",
      });
    }

    const sentences: SentenceRow[] = state.savedSentences.map((row, index) => ({
      ...row, key: row.en + "|" + index,
    }));
    const notes: NoteRow[] = Object.entries(state.notes).map(([word, note]) => {
      const entry = byWord.get(word);
      const sense = entry?.senses.find(item => item.primary) ?? entry?.senses[0];
      return {word, note, definition: sense?.definition ?? ""};
    });

    const tabs: TabRow[] = [
      {id: "learning", label: "Learning", count: learning.length},
      {id: "saved", label: "Saved words", count: saved.length},
      {id: "sentences", label: "Sentences", count: sentences.length},
      {id: "notes", label: "Notes", count: notes.length},
    ];
    const empty = this.data.tab === "learning"
      ? "No cards studied yet."
      : this.data.tab === "saved"
        ? "No saved words yet."
        : this.data.tab === "sentences"
          ? "Save an example while studying to build your sentence bank."
          : "No notes yet.";
    this.setData({
      bookTitle: book ? book.title : "",
      learning, saved, sentences, notes, tabs,
      dueCount: learning.filter(row => row.due).length,
      empty,
    });
  },
  selectTab(event: WeChatTapEvent) {
    const tab = event.currentTarget.dataset.tab as ContentTab;
    if (!tab) return;
    this.setData({tab});
    this.refresh();
  },
  openWord(event: WeChatTapEvent) {
    const word = event.currentTarget.dataset.word;
    if (word) wx.navigateTo({url: "/pages/library/index?word=" + encodeURIComponent(word)});
  },
  playSentence(event: WeChatTapEvent) {
    const index = Number(event.currentTarget.dataset.index ?? 0);
    const sentence = this.data.sentences[index];
    if (sentence) playSentence(sentence.en);
  },
  removeSentence(event: WeChatTapEvent) {
    const index = Number(event.currentTarget.dataset.index ?? 0);
    const sentence = this.data.sentences[index];
    if (!sentence) return;
    const state = readState();
    writeState({...state, savedSentences: state.savedSentences.filter(row => row.en !== sentence.en)});
    this.refresh();
  },
  removeNote(event: WeChatTapEvent) {
    const word = event.currentTarget.dataset.word;
    if (!word) return;
    const state = readState();
    const notes = {...state.notes};
    delete notes[word];
    writeState({...state, notes});
    this.refresh();
  },
  practice() { wx.navigateTo({url: "/pages/spell/index"}); },
});
