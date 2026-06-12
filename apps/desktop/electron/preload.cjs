const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("ecoNative", {
  checkForUpdates: () => ipcRenderer.invoke("updates:check"),
  getAppInfo: () => ipcRenderer.invoke("app:info"),
});
