const { app, BrowserWindow, ipcMain } = require("electron");
const { autoUpdater } = require("electron-updater");
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

ipcMain.handle("updates:check", async () => {
  if (!app.isPackaged) {
    return { ok: false, message: "Atualizações automáticas só funcionam no aplicativo instalado." };
  }

  try {
    const result = await autoUpdater.checkForUpdatesAndNotify();
    return {
      ok: true,
      message: result?.updateInfo?.version
        ? `Atualização ${result.updateInfo.version} verificada.`
        : "Nenhuma atualização nova encontrada.",
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "Não foi possível verificar atualizações.",
    };
  }
});

app.whenReady().then(async () => {
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;

  await createWindow();

  if (app.isPackaged) {
    autoUpdater.checkForUpdatesAndNotify().catch(() => undefined);
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
