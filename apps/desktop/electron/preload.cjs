const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("ecoNative", {
  getAppInfo: () => ipcRenderer.invoke("app:info"),
  checkForUpdates: () => ipcRenderer.invoke("updates:check"),
  downloadUpdate: () => ipcRenderer.invoke("updates:download"),
  installUpdate: () => ipcRenderer.invoke("updates:install"),
  onUpdateEvent: (callback) => {
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on("updates:event", listener);
    return () => ipcRenderer.removeListener("updates:event", listener);
  },
});
