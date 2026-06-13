const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("ecoNative", {
  platform: process.platform,
  titleBarHeight: process.platform === "win32" ? 36 : 0,
  getAppInfo: () => ipcRenderer.invoke("app:info"),
  setTitleBarOverlay: (options) => ipcRenderer.invoke("window:set-titlebar-overlay", options),
  checkForUpdates: () => ipcRenderer.invoke("updates:check"),
  downloadUpdate: () => ipcRenderer.invoke("updates:download"),
  installUpdate: () => ipcRenderer.invoke("updates:install"),
  onUpdateEvent: (callback) => {
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on("updates:event", listener);
    return () => ipcRenderer.removeListener("updates:event", listener);
  },
});
