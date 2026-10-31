const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("fmskin", {
  call: (method, params) => ipcRenderer.invoke("core:call", method, params),
  onEvent: (fn) => {
    const listener = (_e, msg) => fn(msg);
    ipcRenderer.on("core:event", listener);
    return () => ipcRenderer.removeListener("core:event", listener);
  },
  openFile: (options) => ipcRenderer.invoke("dialog:open", options),
  saveFile: (options) => ipcRenderer.invoke("dialog:save", options),
  reveal: (p) => ipcRenderer.invoke("shell:reveal", p),
  platform: process.platform,
  windowControl: (action) => ipcRenderer.invoke("win:control", action),
  onMaximized: (fn) => {
    const listener = (_e, v) => fn(v);
    ipcRenderer.on("win:maximized", listener);
    return () => ipcRenderer.removeListener("win:maximized", listener);
  },
  setUnsaved: (value) => ipcRenderer.send("app:set-unsaved", value),
  onCloseRequested: (fn) => {
    const listener = () => fn();
    ipcRenderer.on("app:close-requested", listener);
    return () => ipcRenderer.removeListener("app:close-requested", listener);
  },
  closeNow: () => ipcRenderer.send("app:close-now"),
  appInfo: () => ipcRenderer.invoke("app:info"),
  checkForUpdates: () => ipcRenderer.invoke("update:check"),
  downloadUpdate: () => ipcRenderer.invoke("update:download"),
  installUpdate: () => ipcRenderer.send("update:install"),
  onUpdateEvent: (fn) => {
    const listener = (_e, msg) => fn(msg);
    ipcRenderer.on("update:event", listener);
    return () => ipcRenderer.removeListener("update:event", listener);
  },
});
