const { app, BrowserWindow, dialog, ipcMain, Menu } = require("electron");
const { autoUpdater } = require("electron-updater");
const semver = require("semver");
const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");

const API_PORT = process.env.ECO_NATIVE_PORT || "8765";
const API_HOST = process.env.ECO_NATIVE_HOST || "127.0.0.1";
const API_URL = `http://${API_HOST}:${API_PORT}`;
const TITLE_BAR_HEIGHT = 36;
const DEFAULT_TITLE_BAR_COLOR = "#00000000";
const DEFAULT_TITLE_BAR_SYMBOL_COLOR = "#5f7167";
const DEFAULT_WINDOW_BACKGROUND = "#f4f8f0";

let mainWindow = null;
let backendProcess = null;
let backendLogStream = null;

function backendExecutablePath() {
  const executableName = process.platform === "win32" ? "eco-native-api.exe" : "eco-native-api";
  return path.join(process.resourcesPath, "backend", executableName);
}

function backendLogPath() {
  return path.join(app.getPath("userData"), "backend.log");
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
        reject(new Error("A API local nao iniciou dentro do tempo esperado."));
        return;
      }
      setTimeout(probe, 450);
    }

    probe();
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function killOrphanBackendProcesses() {
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/F", "/IM", "eco-native-api.exe", "/T"], {
      stdio: "ignore",
      windowsHide: true,
    });
    return;
  }

  spawnSync("pkill", ["-f", "eco-native-api"], { stdio: "ignore" });
}

function stopManagedBackend() {
  if (backendLogStream) {
    backendLogStream.end();
    backendLogStream = null;
  }
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
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

  backendLogStream = fs.createWriteStream(backendLogPath(), { flags: "a" });
  backendLogStream.write(`\n--- backend start ${new Date().toISOString()} ---\n`);

  backendProcess = spawn(backendExecutablePath(), [], {
    env,
    stdio: ["ignore", backendLogStream, backendLogStream],
    windowsHide: true,
  });

  backendProcess.on("exit", (code, signal) => {
    if (backendLogStream) {
      backendLogStream.write(`--- backend exit code=${code ?? "null"} signal=${signal ?? "null"} ---\n`);
    }
    backendProcess = null;
  });
}

async function prepareBackend() {
  if (!app.isPackaged) return;

  killOrphanBackendProcesses();
  await sleep(700);
  startBackend();
  await waitForBackend(45000);
}

function showStartupError(error) {
  const message = error instanceof Error ? error.message : String(error);
  const logHint = app.isPackaged ? `\n\nLog da API: ${backendLogPath()}` : "";
  dialog.showErrorBox(
    "ECO Native Studio",
    `Nao foi possivel iniciar o aplicativo.\n\n${message}${logHint}`,
  );
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

function applyTitleBarOverlay(window, options = {}) {
  if (process.platform !== "win32" || !window || window.isDestroyed()) return;
  if (typeof window.setTitleBarOverlay !== "function") return;
  window.setTitleBarOverlay({
    color: options.color || DEFAULT_TITLE_BAR_COLOR,
    symbolColor: options.symbolColor || DEFAULT_TITLE_BAR_SYMBOL_COLOR,
    height: TITLE_BAR_HEIGHT,
  });
}

async function createWindow() {
  const isWindows = process.platform === "win32";

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1040,
    minHeight: 700,
    show: false,
    title: "ECO Native Studio",
    backgroundColor: DEFAULT_WINDOW_BACKGROUND,
    autoHideMenuBar: true,
    ...(isWindows
      ? {
          titleBarStyle: "hidden",
          backgroundMaterial: "mica",
          titleBarOverlay: {
            color: DEFAULT_TITLE_BAR_COLOR,
            symbolColor: DEFAULT_TITLE_BAR_SYMBOL_COLOR,
            height: TITLE_BAR_HEIGHT,
          },
        }
      : {}),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, "preload.cjs"),
    },
  });

  mainWindow.setMenuBarVisibility(false);
  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  if (app.isPackaged) {
    await prepareBackend();
    await mainWindow.loadFile(path.join(process.resourcesPath, "frontend", "index.html"));
  } else {
    await mainWindow.loadURL(process.env.ECO_NATIVE_FRONTEND_URL || "http://127.0.0.1:5173");
  }

  if (isWindows) {
    applyTitleBarOverlay(mainWindow);
  }
}

ipcMain.handle("app:info", () => ({
  name: app.getName(),
  version: app.getVersion(),
  platform: process.platform,
  titleBarHeight: process.platform === "win32" ? TITLE_BAR_HEIGHT : 0,
}));

ipcMain.handle("window:set-titlebar-overlay", (_event, options) => {
  if (!mainWindow || mainWindow.isDestroyed()) return { ok: false };
  applyTitleBarOverlay(mainWindow, options);
  return { ok: true };
});

ipcMain.handle("updates:check", async () => {
  if (!app.isPackaged) {
    return {
      ok: false,
      status: "error",
      message: "Atualizacoes automaticas so funcionam no aplicativo instalado.",
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
        message: `Nova versao ${latestVersion} disponivel.`,
      };
    }
    return {
      ok: true,
      status: "uptodate",
      currentVersion,
      message: `Voce ja esta na versao mais recente (${currentVersion}).`,
    };
  } catch (error) {
    return {
      ok: false,
      status: "error",
      message: error instanceof Error ? error.message : "Nao foi possivel verificar atualizacoes.",
    };
  }
});

ipcMain.handle("updates:download", async () => {
  if (!app.isPackaged) {
    return { ok: false, message: "Atualizacoes automaticas so funcionam no aplicativo instalado." };
  }

  try {
    await autoUpdater.downloadUpdate();
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "Nao foi possivel baixar a atualizacao.",
    };
  }
});

ipcMain.handle("updates:install", async () => {
  if (!app.isPackaged) {
    return { ok: false, message: "Atualizacoes automaticas so funcionam no aplicativo instalado." };
  }

  stopManagedBackend();
  killOrphanBackendProcesses();
  autoUpdater.quitAndInstall();
  return { ok: true };
});

async function bootstrap() {
  if (process.platform === "win32") {
    app.setAppUserModelId("com.econative.studio");
  }
  Menu.setApplicationMenu(null);
  setupAutoUpdater();
  await createWindow();

  if (app.isPackaged) {
    autoUpdater.checkForUpdates().catch(() => undefined);
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow().catch((error) => {
        showStartupError(error);
        app.quit();
      });
    }
  });
}

app.whenReady().then(bootstrap).catch((error) => {
  showStartupError(error);
  app.quit();
});

app.on("before-quit", () => {
  stopManagedBackend();
  killOrphanBackendProcesses();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
