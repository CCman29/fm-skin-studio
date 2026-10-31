// Bridge to the Python core: Electron IPC in the desktop app, or the dev HTTP server in a plain browser.

export interface CoreError { message: string; type: string; trace?: string }

interface Bridge {
  call(method: string, params?: object): Promise<unknown>;
  onEvent(fn: (msg: { event: string; data: unknown }) => void): () => void;
  openFile(options?: object): Promise<string[] | null>;
  saveFile(options?: object): Promise<string | null>;
  reveal(path: string): Promise<void>;
  platform?: string;
  windowControl?(action: "minimize" | "maximize" | "close" | "state"): Promise<{ maximized: boolean; platform: string } | null>;
  onMaximized?(fn: (maximized: boolean) => void): () => void;
  setUnsaved?(value: boolean): void;
  onCloseRequested?(fn: () => void): () => void;
  closeNow?(): void;
  appInfo?(): Promise<{ version: string; store: boolean; packaged: boolean; platform: string }>;
  checkForUpdates?(): Promise<UpdateCheck>;
  downloadUpdate?(): Promise<{ downloading?: boolean; opened?: boolean }>;
  installUpdate?(): void;
  onUpdateEvent?(fn: (e: { type: "progress" | "downloaded" | "error"; percent?: number; version?: string; message?: string }) => void): () => void;
}
export interface UpdateCheck { state: "store" | "dev" | "available" | "current"; current?: string; latest?: string; canInstall?: boolean;
  releaseUrl?: string }

declare global {
  interface Window { fmskin?: Bridge }
}

const DEV_URL = "http://127.0.0.1:8765";

export const isDesktop = typeof window !== "undefined" && !!window.fmskin;

export async function call<T>(method: string, params: object = {}): Promise<T> {
  if (window.fmskin) return (await window.fmskin.call(method, params)) as T;
  const res = await fetch(DEV_URL, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ method, params }) });
  const body = await res.json();
  if (body.error) throw body.error as CoreError;
  return body.result as T;
}

export function onCoreEvent(fn: (msg: { event: string; data: unknown }) => void): () => void {
  return window.fmskin ? window.fmskin.onEvent(fn) : () => {};
}

export async function pickFiles(filters: { name: string; extensions: string[] }[]): Promise<string | null> {
  if (window.fmskin) return (await window.fmskin.openFile({ properties: ["openFile"], filters }))?.[0] ?? null;
  return window.prompt("Full path of the file (browser preview mode):");
}

export async function pickFolder(title: string): Promise<string | null> {
  if (window.fmskin) return (await window.fmskin.openFile({ title, properties: ["openDirectory", "createDirectory"] }))?.[0] ?? null;
  return window.prompt(`${title} (full folder path, browser preview mode):`);
}

export async function pickSavePath(defaultPath: string,
  filters: { name: string; extensions: string[] }[] = [{ name: "Skin pack", extensions: ["fmskin"] }]): Promise<string | null> {
  if (window.fmskin) return window.fmskin.saveFile({ defaultPath, filters });
  return window.prompt("Save to (full path):", defaultPath);
}

export function reveal(path: string) { window.fmskin?.reveal(path); }

// ---- shapes returned by the core -----------------------------------------------------------------
export interface Paths {
  platform: string; game_root: string | null; bundles: string | null; user_docs: string | null;
  persistent: string | null; player_log: string | null; skins_root: string | null; layouts_dir: string | null;
  game_build: string | null; problems: string[];
}
export interface IndexStatus { ready: boolean; manifest: null | { tokens: number; sheets: number; compositions: number; screens: number; build: string } }
export interface SkinRow { id: string; name: string; path: string; managed: boolean; sheets: string[] }
export interface Pack { id: string; name: string; path: string; managed: boolean; sheets: string[];
  tokens: Record<string, string>; layouts: string[]; info: Record<string, unknown> }
export interface Token { name: string; default: string; resolved: string | null; kind: string; group: string;
  selector: string; useCount: number; uses: Record<string, number>; referencedBy: string[]; key: string | null;
  override: string | null; label: string; description: string; usedFor: string; technical: boolean }
export interface Problem { severity: "error" | "warning" | "info"; file: string; line: number; message: string }
export interface ScreenRow { name: string; screen: string; area: string; breakpoint: string; inMatch: boolean;
  editable: boolean; columns: number; panels: number }
export interface Panel { id: string; x: number; y: number; w: number; h: number; minW: number; minH: number;
  maxW: number; maxH: number; locked: boolean; optional: boolean }
export interface PlacedPanel { id: string; x: number; y: number; w: number; h: number; sizes: number[][]; locked: boolean }
export interface ScreenDetail extends Omit<ScreenRow, "panels"> { panels: Panel[]; layout: PlacedPanel[];
  layoutSource: "pack" | "player" | null; catalogue: { id: string; sizes: number[][] }[] }
export interface BarSetting { mode: "club" | "solid" | "gradient" | "image"; colours?: string[]; angle?: string;
  stripes?: boolean; stripeColour?: string; source?: string; label?: string }
export interface FontCatalog { fontFilesWork: boolean; defaults: Record<string, string>;
  fonts: { id: string; family: string; role: string; widthVsDefault: number; lineHeightVsDefault: number; license: string }[];
  builtin: { id: string; family: string; token: string; note: string }[] }
export interface LogEvent { kind: string; skin: string | null; detail: string; offset: number }
