import {bookPackageBaseUrl, bookPackageFileIds, bookPackageVersion} from "./cloud-config";
import {registerBookPackage, type BookPackage} from "./catalog";

type FileManager = {
  accessSync(path: string): void;
  mkdirSync(path: string, recursive?: boolean): void;
  readFileSync(path: string, encoding?: string): any;
  copyFileSync(srcPath: string, destPath: string): void;
  unlinkSync(path: string): void;
};

const fflate = require("./lib/fflate.js") as {
  gunzipSync(data: Uint8Array): Uint8Array;
  strFromU8(data: Uint8Array): string;
};

const loaded = new Set<string>();
const pending = new Map<string, Promise<boolean>>();

function manager(): FileManager | undefined {
  const factory = (wx as unknown as {getFileSystemManager?: () => FileManager}).getFileSystemManager;
  return typeof factory === "function" ? factory() : undefined;
}

function cachePath(bookId: string): string | undefined {
  const env = (wx as unknown as {env?: {USER_DATA_PATH?: string}}).env;
  const fs = manager();
  if (!env?.USER_DATA_PATH || !fs) return undefined;
  const directory = env.USER_DATA_PATH + "/book-packages";
  try { fs.accessSync(directory); } catch { fs.mkdirSync(directory, true); }
  return directory + "/" + bookId + "-v" + bookPackageVersion + ".json.gz";
}

function decodePackage(buffer: ArrayBuffer): BookPackage {
  const bytes = new Uint8Array(buffer);
  return JSON.parse(fflate.strFromU8(fflate.gunzipSync(bytes))) as BookPackage;
}

function readCached(path: string | undefined): BookPackage | null {
  if (!path) return null;
  const fs = manager();
  if (!fs) return null;
  try {
    return decodePackage(fs.readFileSync(path) as ArrayBuffer);
  } catch {
    return null;
  }
}

function cacheDownload(tempPath: string, path: string | undefined): void {
  if (!path) return;
  const fs = manager();
  if (!fs) return;
  try {
    try { fs.unlinkSync(path); } catch { /* no previous cache */ }
    fs.copyFileSync(tempPath, path);
  } catch {
    // A missing cache only makes the next load download again.
  }
}

function packageUrl(bookId: string): string {
  if (!bookPackageBaseUrl) return "";
  return bookPackageBaseUrl.replace(/\/+$/, "") + "/" + bookId + ".json.gz";
}

function download(bookId: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const fileID = bookPackageFileIds[bookId];
    if (fileID) {
      const cloud = (wx as unknown as {cloud?: {downloadFile?: (options: {
        fileID: string;
        success: (result: {tempFilePath: string}) => void;
        fail?: (error: unknown) => void;
      }) => void}}).cloud;
      if (!cloud?.downloadFile) { reject(new Error("Cloud storage unavailable")); return; }
      cloud.downloadFile({
        fileID,
        success: result => resolve(result.tempFilePath),
        fail: () => reject(new Error("Could not download the book package")),
      });
      return;
    }
    const url = packageUrl(bookId);
    const downloadFile = (wx as unknown as {downloadFile?: (options: {
      url: string;
      success: (result: {tempFilePath: string; statusCode: number}) => void;
      fail?: (error: unknown) => void;
    }) => void}).downloadFile;
    if (!url || typeof downloadFile !== "function") {
      reject(new Error("Book package is not configured"));
      return;
    }
    downloadFile({
      url,
      success: result => {
        if (result.statusCode && result.statusCode >= 400) reject(new Error("Could not download the book package"));
        else resolve(result.tempFilePath);
      },
      fail: () => reject(new Error("Could not download the book package")),
    });
  });
}

async function load(bookId: string): Promise<boolean> {
  const cached = readCached(cachePath(bookId));
  if (cached) {
    registerBookPackage(cached);
    loaded.add(bookId);
    return true;
  }
  const tempPath = await download(bookId);
  const fs = manager();
  if (!fs) return false;
  const buffer = fs.readFileSync(tempPath) as ArrayBuffer;
  const pkg = decodePackage(buffer);
  cacheDownload(tempPath, cachePath(bookId));
  registerBookPackage(pkg);
  loaded.add(bookId);
  return true;
}

export function isBookPackageLoaded(bookId: string): boolean {
  return loaded.has(bookId);
}

/** Download (or read from cache) a full book package. Resolves false when unavailable. */
export function ensureBookPackage(bookId: string): Promise<boolean> {
  if (loaded.has(bookId)) return Promise.resolve(true);
  const existing = pending.get(bookId);
  if (existing) return existing;
  const task = load(bookId).catch(() => false).then(result => {
    pending.delete(bookId);
    return result;
  });
  pending.set(bookId, task);
  return task;
}
