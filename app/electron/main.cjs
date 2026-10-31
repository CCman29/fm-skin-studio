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
// Only our own pages open in the browser from the app (support page, releases).
const OPENABLE = ["https://ko-fi.com/ccman29", "https://github.com/CCman29/fm-skin-studio"];
ipcMain.handle("shell:open", (_e, url) => {
  if (typeof url === "string" && OPENABLE.some((u) => url === u || url.startsWith(u + "/"))) shell.openExternal(url);
});

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
// Every update closes the app, installs the new version and reopens it.
//   Windows: electron-updater downloads the new installer from the GitHub release and runs it silently, then relaunches.
//   macOS: Apple's updater only accepts signed apps, so the app updates itself: it downloads the release's .zip for this
//          Mac's chip, and after quitting a small script swaps the new .app into place and reopens it.
//   Microsoft Store copies: the Store installs updates itself; the button opens its Downloads and updates page.
let updater = null;
const send = (msg) => win?.webContents.send("update:event", msg);
function getUpdater() {
  if (!updater) {
    updater = require("electron-updater").autoUpdater;
    updater.autoDownload = false;
    updater.autoInstallOnAppQuit = false;
    updater.on("download-progress", (p) => send({ type: "progress", percent: Math.round(p.percent) }));
    updater.on("update-downloaded", (i) => send({ type: "downloaded", version: i.version }));
    updater.on("error", (e) => send({ type: "error", message: String(e?.message || e) }));
  }
  return updater;
}
const RELEASES_URL = "https://github.com/CCman29/fm-skin-studio/releases/latest";
const fs = require("node:fs");
const os = require("node:os");
let latestVersion = null;
let macDownloaded = null;  // { app: path of the new .app }

// macOS: the .app bundle this copy runs from, and whether it can be replaced without admin rights
function macBundle() { return path.resolve(process.execPath, "..", "..", ".."); }
function macCanReplace() {
  try { fs.accessSync(path.dirname(macBundle()), fs.constants.W_OK); return macBundle().endsWith(".app"); } catch { return false; }
}
function download(url, file, onProgress) {
  return new Promise((resolve, reject) => {
    const https = require("node:https");
    const get = (u, hops) => https.get(u, { headers: { "User-Agent": "FM-Skin-Studio" } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location && hops < 6) { res.resume(); return get(res.headers.location, hops + 1); }
      if (res.statusCode !== 200) { res.resume(); return reject(new Error(`Download failed (${res.statusCode})`)); }
      const total = Number(res.headers["content-length"] || 0); let got = 0;
      const out = fs.createWriteStream(file);
      res.on("data", (c) => { got += c.length; if (total) onProgress(Math.round((got / total) * 100)); });
      res.pipe(out); out.on("finish", () => out.close(resolve)); out.on("error", reject);
    }).on("error", reject);
    get(url, 0);
  });
}
async function macDownload(version) {
  const name = `FM-Skin-Studio-${version}-${process.arch === "arm64" ? "arm64" : "x64"}.zip`;
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "fmskin-update-"));
  const zip = path.join(dir, name);
  await download(`https://github.com/CCman29/fm-skin-studio/releases/download/v${version}/${name}`, zip, (p) => send({ type: "progress", percent: p }));
  await new Promise((resolve, reject) => spawn("/usr/bin/ditto", ["-x", "-k", zip, dir]).on("exit", (c) => c === 0 ? resolve() : reject(new Error("Couldn't unpack the update"))));
  const appDir = fs.readdirSync(dir).find((f) => f.endsWith(".app"));
  if (!appDir) throw new Error("The update didn't contain the app");
  macDownloaded = { app: path.join(dir, appDir) };
  send({ type: "downloaded", version });
}
function macInstallAndRelaunch() {
  // after this process exits: replace the bundle, clear the download flag, reopen
  const target = macBundle(), source = macDownloaded.app;
  const script = path.join(path.dirname(source), "install.sh");
  fs.writeFileSync(script, [
    "#!/bin/sh",
    `while kill -0 ${process.pid} 2>/dev/null; do sleep 0.5; done`,
    `rm -rf "${target}.old" && mv "${target}" "${target}.old" && /usr/bin/ditto "${source}" "${target}" && rm -rf "${target}.old" || { rm -rf "${target}"; mv "${target}.old" "${target}"; }`,
    `/usr/bin/xattr -dr com.apple.quarantine "${target}" 2>/dev/null`,
    `/usr/bin/open "${target}"`,
  ].join("\n"), { mode: 0o755 });
  spawn("/bin/sh", [script], { detached: true, stdio: "ignore" }).unref();
  closeApproved = true;
  app.quit();
}

ipcMain.handle("app:info", () => ({ version: app.getVersion(), store: !!process.windowsStore, packaged: app.isPackaged,
  platform: process.platform }));
ipcMain.handle("update:check", async () => {
  if (process.windowsStore) {
    shell.openExternal("ms-windows-store://downloadsandupdates");
    return { state: "store" };
  }
  if (!app.isPackaged) return { state: "dev", current: app.getVersion() };
  const r = await getUpdater().checkForUpdates();
  latestVersion = r?.updateInfo?.version ?? null;
  const available = !!latestVersion && r.isUpdateAvailable !== false && latestVersion !== app.getVersion();
  return { state: available ? "available" : "current", current: app.getVersion(), latest: latestVersion,
    canInstall: process.platform === "win32" || (process.platform === "darwin" && macCanReplace()), releaseUrl: RELEASES_URL };
});
ipcMain.handle("update:download", async () => {
  if (process.platform === "darwin") {
    if (!macCanReplace()) { shell.openExternal(RELEASES_URL); return { opened: true }; }
    macDownload(latestVersion).catch((e) => send({ type: "error", message: String(e?.message || e) }));
    return { downloading: true };
  }
  if (process.platform !== "win32") { shell.openExternal(RELEASES_URL); return { opened: true }; }
  await getUpdater().downloadUpdate();
  return { downloading: true };
});
ipcMain.on("update:install", () => {
  closeApproved = true;
  if (process.platform === "darwin" && macDownloaded) return macInstallAndRelaunch();
  getUpdater().quitAndInstall(true, true);  // silent install, then reopen the app
});

// Test and support hook: run the app with --update-now to check, download and install an update without the UI.
async function updateNowFromCommandLine() {
  if (!app.isPackaged || !process.argv.includes("--update-now")) return;
  const u = getUpdater();
  const r = await u.checkForUpdates();
  const v = r?.updateInfo?.version;
  if (!v || v === app.getVersion()) return;
  if (process.platform === "darwin") {
    if (!macCanReplace()) return;
    await macDownload(v);
    return macInstallAndRelaunch();
  }
  await u.downloadUpdate();
  closeApproved = true;
  u.quitAndInstall(true, true);
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
