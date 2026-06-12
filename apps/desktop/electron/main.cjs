const { app, BrowserWindow, ipcMain } = require("electron");
const { autoUpdater } = require("electron-updater");
const semver = require("semver");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const API_PORT = process.env.ECO_NATIVE_PORT || "8765";
const API_HOST = process.env.ECO_NATIVE_HOST || "127.0.0.1";
const API_URL = `http://${API_HOST}:${API_PORT}`;

let mainWindow = null;
let backendProcess = null;

function backendExecutablePath() {
  const executableName = process.platform === "win32" ? "eco-native-api.exe" : "eco-native-api";
  return path.join(process.resourcesPath, "backend", executableName);
}

function waitForBackend(timeoutMs = 30000) {
  const startedAt = Date.now();

  return new Promise((resolve, reject) => {
    function probe() {
      const request = http.get(`${API_URL}/health`, (response) => {
        response.resume();
        if (response.statusCode && response.statusCode >= 200 && response.statusCode < 300) {
          resolve();
          return;
        }
        retry();
      });

      request.on("error", retry);
      request.setTimeout(1200, () => {
        request.destroy();
        retry();
      });
    }

    function retry() {
      if (Date.now() - startedAt > timeoutMs) {
        reject(new Error("A API local não iniciou dentro do tempo esperado."));
        return;
      }
      setTimeout(probe, 450);
    }

    probe();
  });
}

function startBackend() {
  if (!app.isPackaged || backendProcess) return;

  const userDataPath = app.getPath("userData");
  const env = {
    ...process.env,
    ECO_NATIVE_DATA_DIR: userDataPath,
    ECO_NATIVE_ENV_PATH: path.join(userDataPath, ".env"),
    ECO_NATIVE_HOST: API_HOST,
    ECO_NATIVE_PORT: API_PORT,
    PLAYWRIGHT_BROWSERS_PATH: path.join(process.resourcesPath, "playwright-browsers"),
  };

  backendProcess = spawn(backendExecutablePath(), [], {
    env,
    stdio: "ignore",
    windowsHide: true,
  });

  backendProcess.on("exit", () => {
    backendProcess = null;
  });
}

function sendUpdateEvent(payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("updates:event", payload);
  }
}

function setupAutoUpdater() {
  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = false;

  autoUpdater.on("update-available", (info) => {
    sendUpdateEvent({
      type: "available",
      version: info.version,
      currentVersion: app.getVersion(),
    });
  });

  autoUpdater.on("update-not-available", (info) => {
    sendUpdateEvent({
      type: "not-available",
      version: info.version,
      currentVersion: app.getVersion(),
    });
  });

  autoUpdater.on("download-progress", (progress) => {
    sendUpdateEvent({
      type: "progress",
      percent: progress.percent,
      transferred: progress.transferred,
      total: progress.total,
    });
  });

  autoUpdater.on("update-downloaded", (info) => {
    sendUpdateEvent({
      type: "downloaded",
      version: info.version,
    });
  });

  autoUpdater.on("error", (error) => {
    sendUpdateEvent({
      type: "error",
      message: error instanceof Error ? error.message : "Erro ao atualizar.",
    });
  });
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1040,
    minHeight: 700,
    backgroundColor: "#f6f4ef",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, "preload.cjs"),
    },
  });

  if (app.isPackaged) {
    startBackend();
    await waitForBackend();
    await mainWindow.loadFile(path.join(process.resourcesPath, "frontend", "index.html"));
  } else {
    await mainWindow.loadURL(process.env.ECO_NATIVE_FRONTEND_URL || "http://127.0.0.1:5173");
  }
}

ipcMain.handle("app:info", () => ({
  name: app.getName(),
  version: app.getVersion(),
}));

ipcMain.handle("updates:check", async () => {
  if (!app.isPackaged) {
    return {
      ok: false,
      status: "error",
      message: "Atualizações automáticas só funcionam no aplicativo instalado.",
    };
  }

  try {
    const result = await autoUpdater.checkForUpdates();
    const currentVersion = app.getVersion();
    const latestVersion = result?.updateInfo?.version;
    if (latestVersion && semver.gt(latestVersion, currentVersion)) {
      return {
        ok: true,
        status: "available",
        version: latestVersion,
        currentVersion,
        message: `Nova versão ${latestVersion} disponível.`,
      };
    }
    return {
      ok: true,
      status: "uptodate",
      currentVersion,
      message: `Você já está na versão mais recente (${currentVersion}).`,
    };
  } catch (error) {
    return {
      ok: false,
      status: "error",
      message: error instanceof Error ? error.message : "Não foi possível verificar atualizações.",
    };
  }
});

ipcMain.handle("updates:download", async () => {
  if (!app.isPackaged) {
    return { ok: false, message: "Atualizações automáticas só funcionam no aplicativo instalado." };
  }

  try {
    await autoUpdater.downloadUpdate();
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "Não foi possível baixar a atualização.",
    };
  }
});

ipcMain.handle("updates:install", async () => {
  if (!app.isPackaged) {
    return { ok: false, message: "Atualizações automáticas só funcionam no aplicativo instalado." };
  }

  autoUpdater.quitAndInstall();
  return { ok: true };
});

app.whenReady().then(async () => {
  setupAutoUpdater();
  await createWindow();

  if (app.isPackaged) {
    autoUpdater.checkForUpdates().catch(() => undefined);
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow().catch(() => app.quit());
  });
});

app.on("before-quit", () => {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
