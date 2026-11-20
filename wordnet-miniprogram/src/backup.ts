import {normalizeState, type StudyState} from "./study";

export const BACKUP_VERSION = 1;
const MAX_BACKUP_CHARS = 8_000_000;

export type Backup = {
  app: "wordnet-study";
  version: number;
  exportedAt: string;
  state: StudyState;
};

export function serializeState(state: StudyState): string {
  const payload: Backup = {
    app: "wordnet-study",
    version: BACKUP_VERSION,
    exportedAt: new Date().toISOString(),
    state,
  };
  return JSON.stringify(payload, null, 2);
}

export function parseBackup(text: string): StudyState {
  if (typeof text !== "string" || !text.trim()) throw new Error("Backup is empty.");
  if (text.length > MAX_BACKUP_CHARS) throw new Error("Backup is too large.");
  let payload: unknown;
  try {
    payload = JSON.parse(text);
  } catch {
    throw new Error("Backup is not valid JSON.");
  }
  if (!payload || typeof payload !== "object") throw new Error("Backup is not valid.");
  const record = payload as Record<string, unknown>;
  const candidate = record.state && typeof record.state === "object" && !Array.isArray(record.state)
    ? record.state
    : record.progress && typeof record.progress === "object" && !Array.isArray(record.progress)
      ? record
      : null;
  if (!candidate) throw new Error("Backup does not contain study data.");
  if (record.app !== undefined && record.app !== "wordnet-study") {
    throw new Error("This is not a Word Study backup.");
  }
  if (record.version !== undefined && Number(record.version) > BACKUP_VERSION) {
    throw new Error("Backup was created by a newer version.");
  }
  return normalizeState(candidate);
}

function uuid(): string {
  return Math.random().toString(36).slice(2, 10);
}

export function exportToClipboard(state: StudyState): Promise<void> {
  return new Promise((resolve, reject) => {
    wx.setClipboardData({
      data: serializeState(state),
      success: () => resolve(),
      fail: () => reject(new Error("Could not copy the backup.")),
    });
  });
}

export function importFromClipboard(): Promise<StudyState> {
  return new Promise((resolve, reject) => {
    wx.getClipboardData({
      success: result => {
        try { resolve(parseBackup(result.data)); }
        catch (error) { reject(error as Error); }
      },
      fail: () => reject(new Error("Could not read the clipboard.")),
    });
  });
}

export function exportToFile(state: StudyState): Promise<string> {
  return new Promise((resolve, reject) => {
    const env = (wx as unknown as {env?: {USER_DATA_PATH?: string}}).env;
    const fs = (wx as unknown as {getFileSystemManager?: () => {
      writeFileSync(path: string, data: string, encoding?: string): void;
      accessSync(path: string): void;
      mkdirSync(path: string, recursive?: boolean): void;
    }}).getFileSystemManager;
    if (!env?.USER_DATA_PATH || typeof fs !== "function") {
      exportToClipboard(state).then(() => resolve("clipboard")).catch(reject);
      return;
    }
    try {
      const manager = fs();
      const directory = env.USER_DATA_PATH + "/backups";
      try { manager.accessSync(directory); } catch { manager.mkdirSync(directory, true); }
      const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
      const path = directory + "/word-study-" + stamp + "-" + uuid() + ".json";
      manager.writeFileSync(path, serializeState(state), "utf8");
      const share = (wx as unknown as {shareFileMessage?: (options: {
        filePath: string; fileName?: string; success?: () => void; fail?: (error: unknown) => void;
      }) => void}).shareFileMessage;
      if (typeof share === "function") {
        share({
          filePath: path,
          fileName: "word-study-backup.json",
          success: () => resolve(path),
          fail: () => {
            exportToClipboard(state).then(() => resolve("clipboard")).catch(reject);
          },
        });
      } else {
        exportToClipboard(state).then(() => resolve("clipboard")).catch(reject);
      }
    } catch {
      reject(new Error("Could not write the backup file."));
    }
  });
}

export function confirmImport(): Promise<boolean> {
  return new Promise(resolve => {
    wx.showModal({
      title: "Restore backup?",
      content: "This replaces local progress, notes and settings.",
      success: result => resolve(result.confirm),
      fail: () => resolve(false),
    });
  });
}

export function importFromFile(): Promise<StudyState> {
  return new Promise((resolve, reject) => {
    const choose = (wx as unknown as {chooseMessageFile?: (options: {
      count: number; type: string; extension?: string[];
      success: (result: {tempFiles: Array<{path: string}>}) => void;
      fail?: (error: unknown) => void;
    }) => void}).chooseMessageFile;
    const fs = (wx as unknown as {getFileSystemManager?: () => {
      readFileSync(path: string, encoding: string): string;
    }}).getFileSystemManager;
    if (typeof choose !== "function" || typeof fs !== "function") {
      importFromClipboard().then(resolve).catch(reject);
      return;
    }
    choose({
      count: 1,
      type: "file",
      extension: ["json", "txt"],
      success: result => {
        const file = result.tempFiles?.[0];
        if (!file?.path) { reject(new Error("No backup file selected.")); return; }
        try {
          resolve(parseBackup(fs().readFileSync(file.path, "utf8")));
        } catch (error) {
          reject(error as Error);
        }
      },
      fail: () => reject(new Error("Could not open the backup file.")),
    });
  });
}
