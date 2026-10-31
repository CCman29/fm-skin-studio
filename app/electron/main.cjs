// Electron main process: window + the Python core sidecar (JSON-RPC over stdin/stdout).
const { app, BrowserWindow, ipcMain, dialog, shell, Menu } = require("electron");
const { spawn } = require("node:child_process");
const path = require("node:path");
const readline = require("node:readline");

let win = null;
let core = null;
let nextId = 1;
const pending = new Map();

function coreCommand() {
  // Packaged builds ship a frozen sidecar next to the app; development runs the Python package.
  const bundled = path.join(process.resourcesPath || "", "core", process.platform === "win32" ? "fmskin-core.exe" : "fmskin-core");
  if (app.isPackaged) return { cmd: bundled, args: ["rpc"] };
  return { cmd: process.env.FMSKIN_PYTHON || "python", args: ["-m", "fmskin.cli", "rpc"] };
}

function startCore() {
  const { cmd, args } = coreCommand();
  core = spawn(cmd, args, { stdio: ["pipe", "pipe", "pipe"], windowsHide: true });
  readline.createInterface({ input: core.stdout }).on("line", (line) => {
    let msg;
    try { msg = JSON.parse(line); } catch { return; }
    if (msg.event) {
      win?.webContents.send("core:event", msg);
      return;
    }
    const waiter = pending.get(msg.id);
    if (!waiter) return;
    pending.delete(msg.id);
    msg.error ? waiter.reject(msg.error) : waiter.resolve(msg.result);
  });
  core.stderr.on("data", (d) => console.error("[core]", d.toString()));
  core.on("exit", (code) => {
    for (const w of pending.values()) w.reject({ message: `Core stopped (exit ${code})`, type: "CoreExit" });
    pending.clear();
    win?.webContents.send("core:event", { event: "exit", data: { code } });
  });
}

ipcMain.handle("core:call", (_e, method, params) => new Promise((resolve, reject) => {
  if (!core || core.exitCode !== null) return reject({ message: "Core not running", type: "CoreExit" });
  const id = nextId++;
  pending.set(id, { resolve, reject });
  core.stdin.write(JSON.stringify({ id, method, params: params || {} }) + "\n");
}));

ipcMain.handle("dialog:open", async (_e, options) => {
  const r = await dialog.showOpenDialog(win, options || {});
  return r.canceled ? null : r.filePaths;
});
ipcMain.handle("dialog:save", async (_e, options) => {
  const r = await dialog.showSaveDialog(win, options || {});
  return r.canceled ? null : r.filePath;
});
ipcMain.handle("shell:reveal", (_e, p) => shell.showItemInFolder(p));

// Own window frame on Windows/Linux (no menu bar): the app draws its title bar and window buttons.
ipcMain.handle("win:control", (_e, action) => {
  if (!win) return null;
  if (action === "minimize") win.minimize();
  else if (action === "maximize") win.isMaximized() ? win.unmaximize() : win.maximize();
  else if (action === "close") win.close();  // goes through the unsaved-changes check below
  return { maximized: win.isMaximized(), platform: process.platform };
});
// Closing asks the page first when it has unsaved skin changes; the page answers with app:close-now.
let hasUnsaved = false, closeApproved = false;
ipcMain.on("app:set-unsaved", (_e, value) => { hasUnsaved = !!value; });
ipcMain.on("app:close-now", () => { closeApproved = true; win?.close(); });

// ---- updates --------------------------------------------------------------------------------------------------
// Microsoft Store copies: the Store installs updates itself; the button opens its Downloads and updates page.
// Direct downloads: electron-updater reads the releases published on GitHub (see "publish" in package.json).
// macOS: an unsigned app can't replace itself, so a new version is downloaded from the release page instead.
let updater = null;
function getUpdater() {
  if (!updater) {
    updater = require("electron-updater").autoUpdater;
    updater.autoDownload = false;
    updater.autoInstallOnAppQuit = false;
    updater.on("download-progress", (p) => win?.webContents.send("update:event", { type: "progress", percent: Math.round(p.percent) }));
    updater.on("update-downloaded", (i) => win?.webContents.send("update:event", { type: "downloaded", version: i.version }));
    updater.on("error", (e) => win?.webContents.send("update:event", { type: "error", message: String(e?.message || e) }));
  }
  return updater;
}
const RELEASES_URL = "https://github.com/CCman29/fm-skin-studio/releases/latest";
ipcMain.handle("app:info", () => ({ version: app.getVersion(), store: !!process.windowsStore, packaged: app.isPackaged,
  platform: process.platform }));
ipcMain.handle("update:check", async () => {
  if (process.windowsStore) {
    shell.openExternal("ms-windows-store://downloadsandupdates");
    return { state: "store" };
  }
  if (!app.isPackaged) return { state: "dev", current: app.getVersion() };
  const r = await getUpdater().checkForUpdates();
  const latest = r?.updateInfo?.version;
  const available = !!latest && r.isUpdateAvailable !== false && latest !== app.getVersion();
  return { state: available ? "available" : "current", current: app.getVersion(), latest,
    canInstall: process.platform === "win32", releaseUrl: RELEASES_URL };
});
ipcMain.handle("update:download", async () => {
  if (process.platform !== "win32") { shell.openExternal(RELEASES_URL); return { opened: true }; }
  await getUpdater().downloadUpdate();
  return { downloading: true };
});
ipcMain.on("update:install", () => { closeApproved = true; getUpdater().quitAndInstall(false, true); });

// Test and support hook: "FM Skin Studio.exe --update-now" checks, downloads and installs an update without the UI.
async function updateNowFromCommandLine() {
  if (!app.isPackaged || process.platform !== "win32" || !process.argv.includes("--update-now")) return;
  const u = getUpdater();
  const r = await u.checkForUpdates();
  if (r?.updateInfo?.version && r.updateInfo.version !== app.getVersion()) {
    await u.downloadUpdate();
    closeApproved = true;
    u.quitAndInstall(true, true);
  }
}

const DESIGN_WIDTH = 1440;
let userScale = 1;
function fitZoom() {
  if (!win || win.isDestroyed()) return;
  const { width, height } = win.getContentBounds();
  const fit = Math.min(width / DESIGN_WIDTH, height / 820);  // keep whole screens visible on very wide or short windows
  win.webContents.setZoomFactor(Math.min(2.2, Math.max(0.75, fit)) * userScale);
}

function createWindow() {
  win = new BrowserWindow({
    width: 1440, height: 900, minWidth: 1100, minHeight: 700, backgroundColor: "#0b0f17",
    title: "FM Skin Studio",
    ...(process.platform === "darwin" ? { titleBarStyle: "hiddenInset" } : { frame: false }),
    icon: path.join(__dirname, "..", "build", process.platform === "win32" ? "icon.ico" : "icon.png"),
    webPreferences: { preload: path.join(__dirname, "preload.cjs"), contextIsolation: true, sandbox: true },
  });
  win.on("close", (e) => {
    if (closeApproved || !hasUnsaved) return;
    e.preventDefault();
    win.webContents.send("app:close-requested");
  });
  const sendMax = () => win?.webContents.send("win:maximized", win.isMaximized());
  win.on("maximize", sendMax); win.on("unmaximize", sendMax);
  // Responsive scaling: the UI is designed at 1440 px wide and zoomed to fit the window, so it fills a large monitor and
  // shrinks on a small one (Windows and macOS; the OS already handles high-DPI screens). Ctrl/Cmd + = / - / 0 adjust on top.
  win.on("resize", fitZoom);
  win.webContents.on("did-finish-load", fitZoom);
  win.webContents.on("before-input-event", (e, input) => {
    if (input.type !== "keyDown" || !(input.control || input.meta)) return;
    if (input.key === "=" || input.key === "+") userScale = Math.min(1.6, userScale + 0.1);
    else if (input.key === "-") userScale = Math.max(0.6, userScale - 0.1);
    else if (input.key === "0") userScale = 1;
    else return;
    e.preventDefault();
    fitZoom();
  });
  const devUrl = process.env.FMSKIN_DEV_URL;
  if (devUrl) win.loadURL(devUrl);
  else win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
}

app.whenReady().then(() => {
  // Windows/Linux: no menu bar at all (copy, paste and the zoom keys still work). macOS keeps its standard app menu.
  if (process.platform !== "darwin") Menu.setApplicationMenu(null);
  startCore(); createWindow();
  updateNowFromCommandLine().catch((e) => console.error("[update]", e));
});
app.on("window-all-closed", () => {
  if (core && core.exitCode === null) core.stdin.write(JSON.stringify({ id: 0, method: "shutdown" }) + "\n");
  app.quit();
});
