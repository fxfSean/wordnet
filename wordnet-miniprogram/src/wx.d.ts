declare const wx: {
  cloud?: {
    init(options: {env: string}): void;
    downloadFile?(options: {
      fileID: string;
      success: (result: {tempFilePath: string}) => void;
      fail?: (error: unknown) => void;
    }): void;
  };
  getStorageSync(key: string): unknown;
  setStorageSync(key: string, data: unknown): void;
  navigateTo(options: {url: string}): void;
  navigateBack(): void;
  showToast(options: {title: string; icon: 'none' | 'success' | 'error'}): void;
  showModal(options: {
    title?: string;
    content?: string;
    editable?: boolean;
    placeholderText?: string;
    success?: (result: {confirm: boolean; content?: string}) => void;
    fail?: (error: unknown) => void;
  }): void;
  setClipboardData(options: {data: string; success?: () => void; fail?: (error: unknown) => void}): void;
  getClipboardData(options: {success: (result: {data: string}) => void; fail?: (error: unknown) => void}): void;
  showLoading(options: {title: string}): void;
  hideLoading(): void;
  setNavigationBarColor?: (options: {frontColor: string; backgroundColor: string}) => void;
  setBackgroundColor?: (options: {backgroundColor: string}) => void;
  env?: {USER_DATA_PATH?: string};
  createInnerAudioContext?: () => {
    src: string;
    volume: number;
    obeyMuteSwitch?: boolean;
    stop(): void;
    play(): void;
    destroy(): void;
    onError?(callback: (error: unknown) => void): void;
  };
  getFileSystemManager?: () => {
    accessSync(path: string): void;
    mkdirSync(path: string, recursive?: boolean): void;
    writeFileSync(path: string, data: string, encoding?: string): void;
    readFileSync(path: string, encoding?: string): any;
    copyFileSync(srcPath: string, destPath: string): void;
    unlinkSync(path: string): void;
  };
  downloadFile?: (options: {
    url: string;
    success: (result: {tempFilePath: string; statusCode: number}) => void;
    fail?: (error: unknown) => void;
  }) => void;
  shareFileMessage?: (options: {
    filePath: string;
    fileName?: string;
    success?: () => void;
    fail?: (error: unknown) => void;
  }) => void;
  chooseMessageFile?: (options: {
    count: number;
    type: string;
    extension?: string[];
    success: (result: {tempFiles: Array<{path: string; name?: string; size?: number}>}) => void;
    fail?: (error: unknown) => void;
  }) => void;
};
declare function App(options: object): void;
declare function Page<T extends {data: object}>(options: T & ThisType<T & {
  setData(data: Partial<T['data']>): void;
}>): void;
declare function require(path: string): unknown;
type WeChatInputEvent = {detail: {value: string}};
type WeChatSwitchEvent = {detail: {value: boolean}};
type WeChatPickerEvent = {detail: {value: string}};
type WeChatTapEvent = {currentTarget: {dataset: Record<string, string>}};
