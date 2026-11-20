import {contentPackageBaseUrl, contentPackageFileId, contentPackageVersion} from "./cloud-config";
import {registerContentPackage, type ContentPackage} from "./catalog";

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

let loaded = false;
let pending: Promise<boolean> | undefined;
let warned = false;

function manager(): FileManager | undefined {
  const factory = (wx as unknown as {getFileSystemManager?: () => FileManager}).getFileSystemManager;
  return typeof factory === "function" ? factory() : undefined;
}

function cachePath(): string | undefined {
  const env = (wx as unknown as {env?: {USER_DATA_PATH?: string}}).env;
  const fs = manager();
  if (!env?.USER_DATA_PATH || !fs) return undefined;
  const directory = env.USER_DATA_PATH + "/content-packages";
  try { fs.accessSync(directory); } catch { fs.mkdirSync(directory, true); }
  return directory + "/content-v" + contentPackageVersion + ".json.gz";
}

function decodePackage(buffer: ArrayBuffer): ContentPackage {
  const bytes = new Uint8Array(buffer);
  return JSON.parse(fflate.strFromU8(fflate.gunzipSync(bytes))) as ContentPackage;
}

function readCached(path: string | undefined): ContentPackage | null {
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

function download(): Promise<string> {
  return new Promise((resolve, reject) => {
    if (contentPackageFileId) {
      const cloud = (wx as unknown as {cloud?: {downloadFile?: (options: {
        fileID: string;
        success: (result: {tempFilePath: string}) => void;
        fail?: (error: unknown) => void;
      }) => void}}).cloud;
      if (!cloud?.downloadFile) { reject(new Error("Cloud storage unavailable")); return; }
      cloud.downloadFile({
        fileID: contentPackageFileId,
        success: result => resolve(result.tempFilePath),
        fail: () => reject(new Error("Could not download the content package")),
      });
      return;
    }
    const downloadFile = (wx as unknown as {downloadFile?: (options: {
      url: string;
      success: (result: {tempFilePath: string; statusCode: number}) => void;
      fail?: (error: unknown) => void;
    }) => void}).downloadFile;
    if (!contentPackageBaseUrl || typeof downloadFile !== "function") {
      reject(new Error("Content package is not configured"));
      return;
    }
    const url = contentPackageBaseUrl.replace(/\/+$/, "") + "/content.json.gz";
    downloadFile({
      url,
      success: result => {
        if (result.statusCode && result.statusCode >= 400) reject(new Error("Could not download the content package"));
        else resolve(result.tempFilePath);
      },
      fail: () => reject(new Error("Could not download the content package")),
    });
  });
}

async function load(): Promise<boolean> {
  const cached = readCached(cachePath());
  if (cached) {
    registerContentPackage(cached);
    loaded = true;
    return true;
  }
  const tempPath = await download();
  const fs = manager();
  if (!fs) return false;
  const buffer = fs.readFileSync(tempPath) as ArrayBuffer;
  const pkg = decodePackage(buffer);
  cacheDownload(tempPath, cachePath());
  registerContentPackage(pkg);
  loaded = true;
  return true;
}

export function isContentPackageLoaded(): boolean {
  return loaded;
}

/**
 * Download (or read from cache) the shared phrase/roots package. Resolves
 * false when it is not configured, unreachable, or the device has no storage.
 */
export function ensureContentPackage(): Promise<boolean> {
  if (loaded) return Promise.resolve(true);
  if (pending) return pending;
  if (!contentPackageFileId && !contentPackageBaseUrl) {
    if (!warned) {
      warned = true;
      console.warn("Content package is not configured; collocations will stay hidden.");
    }
    return Promise.resolve(false);
  }
  const task = load().catch(error => {
    if (!warned) {
      warned = true;
      console.warn("Could not load the content package", error);
    }
    return false;
  }).then(result => {
    pending = undefined;
    return result;
  });
  pending = task;
  return task;
}
