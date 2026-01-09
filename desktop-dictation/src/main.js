const { app, BrowserWindow, globalShortcut, ipcMain, Tray, Menu, nativeImage } = require('electron');
const path = require('path');
const AudioRecorder = require('./audioRecorder');
const AsrService = require('./asrService');
const TextInserter = require('./textInserter');
const HotkeyManager = require('./HotkeyManager');
const logger = require('./logger');

// Set unique userData path to avoid cache conflicts
app.setPath('userData', path.join(app.getPath('appData'), 'desktop-dictation'));

// Disable cache to avoid permission errors
app.commandLine.appendSwitch('disable-http-cache');
app.commandLine.appendSwitch('disable-gpu-shader-disk-cache');

// Request single instance lock - only allow one instance to run
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  // Another instance is already running, quit this one
  logger.info('Another instance is already running. Quitting...');
  app.quit();
} else {
  // This is the first instance
  app.on('second-instance', (event, commandLine, workingDirectory) => {
    // Someone tried to run a second instance, focus our window instead
    logger.info('Second instance detected, focusing existing window');
    if (hotwordsWindow && !hotwordsWindow.isDestroyed()) {
      if (hotwordsWindow.isMinimized()) hotwordsWindow.restore();
      hotwordsWindow.focus();
    }
  });
}

let overlayWindow = null;
let hotwordsWindow = null;
let audioRecorder = null;
let asrService = null;
let textInserter = null;
let isRecording = false;
let tray = null;
let recordingStartTime = null;
let hotkeyManager = null;

function createOverlayWindow() {
  logger.debug('Creating overlay window...');

  overlayWindow = new BrowserWindow({
    width: 240,
    height: 120,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    focusable: false,
    show: false,
    opacity: 1.0,
    hasShadow: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      offscreen: false
    }
  });

  const overlayPath = path.join(__dirname, 'overlay.html');
  logger.debug('Loading overlay from:', overlayPath);

  overlayWindow.loadFile(overlayPath);
  overlayWindow.setIgnoreMouseEvents(true);

  // Position at bottom center of the screen where the cursor is
  const { screen } = require('electron');
  const cursorPoint = screen.getCursorScreenPoint();
  const currentDisplay = screen.getDisplayNearestPoint(cursorPoint);

  logger.debug('Cursor position:', cursorPoint);
  logger.debug('Current display:', currentDisplay.bounds);

  const { x: displayX, y: displayY, width, height } = currentDisplay.workArea;
  const x = displayX + Math.floor(width / 2 - 120);  // Center on current display
  const y = displayY + height - 200;                  // Bottom of current display

  logger.debug('Screen size:', width, 'x', height);
  logger.debug('Overlay position:', x, ',', y);

  overlayWindow.setPosition(x, y);

  // Set window level to ensure it's on top
  overlayWindow.setAlwaysOnTop(true, 'screen-saver');

  // Add error handler
  overlayWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    logger.error('Overlay failed to load:', errorCode, errorDescription);
  });

  overlayWindow.webContents.on('did-finish-load', () => {
    logger.debug('Overlay loaded successfully');
  });

  logger.debug('Overlay window created');
}

function createHotwordsWindow() {
  if (hotwordsWindow) {
    hotwordsWindow.focus();
    return;
  }

  hotwordsWindow = new BrowserWindow({
    width: 650,
    height: 700,
    resizable: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  hotwordsWindow.loadFile(path.join(__dirname, 'hotwords.html'));
  hotwordsWindow.setMenuBarVisibility(false);

  hotwordsWindow.on('closed', () => {
    hotwordsWindow = null;
  });
}

function startRecording() {
  if (isRecording) return;

  logger.info('Starting recording...');
  isRecording = true;
  recordingStartTime = Date.now();

  // Check if overlayWindow exists
  if (!overlayWindow) {
    logger.error('overlayWindow is null!');
    return;
  }

  if (overlayWindow.isDestroyed()) {
    logger.error('overlayWindow is destroyed!');
    return;
  }

  logger.debug('Showing overlay window...');
  overlayWindow.show();
  logger.debug('Overlay visibility:', overlayWindow.isVisible());
  logger.debug('Overlay position:', overlayWindow.getBounds());

  audioRecorder.start();
  logger.debug('Audio recorder started');
}

function stopRecording() {
  if (!isRecording) return;

  isRecording = false;
  overlayWindow.hide();

  // Calculate recording duration
  const recordingDuration = (Date.now() - recordingStartTime) / 1000;
  logger.info(`Recording stopped, duration: ${recordingDuration.toFixed(2)}s`);

  audioRecorder.stop(async (audioBuffer) => {
    try {
      // Check minimum duration (1.2 seconds)
      if (recordingDuration < 1.2) {
        logger.warn('Recording too short, skipping ASR');
        return;
      }

      logger.info('Sending audio to ASR service...');
      // Send to ASR service
      const text = await asrService.transcribe(audioBuffer);

      // Insert text at cursor position
      if (text && text.trim()) {
        logger.info(`Transcribed text: "${text.trim()}"`);
        textInserter.insertText(text.trim());
      } else {
        logger.warn('ASR returned empty text');
      }
    } catch (error) {
      logger.error('Transcription error:', error.message);
    }
  });
}

function registerGlobalShortcut() {
  const { uIOhook, UiohookKey } = require('uiohook-napi');

  // 创建 HotkeyManager 实例
  hotkeyManager = new HotkeyManager({
    onRecordStart: startRecording,
    onRecordStop: stopRecording,
    isRecording: () => isRecording,
    keyCodes: {
      Ctrl: UiohookKey.Ctrl,
      CtrlRight: UiohookKey.CtrlRight,
      WinLeft: 3675,
      WinRight: 3676
    }
  });

  // 注册全局快捷键
  hotkeyManager.register(uIOhook);
}

function createTray() {
  // Load icon
  const iconPath = path.join(__dirname, '../assets/icon-32.png');
  const icon = nativeImage.createFromPath(iconPath);

  // Create tray
  tray = new Tray(icon);

  // Create context menu
  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Desktop Dictation',
      enabled: false
    },
    {
      type: 'separator'
    },
    {
      label: '热词管理',
      click: () => {
        createHotwordsWindow();
      }
    },
    {
      type: 'separator'
    },
    {
      label: 'Status: Ready',
      enabled: false
    },
    {
      label: 'Hotkey: Ctrl+Win',
      enabled: false
    },
    {
      type: 'separator'
    },
    {
      label: 'Quit',
      click: () => {
        app.isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setToolTip('Desktop Dictation - Hold Ctrl+Win to record');
  tray.setContextMenu(contextMenu);

  // Update tooltip on recording state change
  tray.on('click', () => {
    tray.popUpContextMenu();
  });
}

app.whenReady().then(() => {
  // Set permission handler for media devices
  const { session } = require('electron');

  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    logger.debug(`Permission request: ${permission}`);
    callback(true); // Allow all permissions for our app
  });

  session.defaultSession.setPermissionCheckHandler((webContents, permission, requestingOrigin, details) => {
    logger.debug(`Permission check: ${permission}`);
    return true; // Allow all permission checks
  });

  // Initialize services
  audioRecorder = new AudioRecorder();
  asrService = new AsrService('http://localhost:8082');
  textInserter = new TextInserter();

  createOverlayWindow();
  createTray();
  registerGlobalShortcut();

  logger.info('Desktop Dictation is ready!');
  logger.info('Hold Ctrl+Win to record');
  logger.info('Log file:', logger.getLogPath());

  // IPC handlers for hotwords management
  ipcMain.handle('get-hotwords', async () => {
    try {
      const response = await fetch('http://localhost:8082/hotwords');
      if (!response.ok) throw new Error('Failed to fetch hotwords');
      return await response.json();
    } catch (error) {
      logger.error('Error fetching hotwords:', error.message);
      throw error;
    }
  });

  ipcMain.handle('add-hotword', async (event, word) => {
    try {
      const response = await fetch(`http://localhost:8082/hotwords/add?word=${encodeURIComponent(word)}`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error('Failed to add hotword');
      return await response.json();
    } catch (error) {
      logger.error('Error adding hotword:', error.message);
      throw error;
    }
  });

  ipcMain.handle('delete-hotword', async (event, word) => {
    try {
      const response = await fetch(`http://localhost:8082/hotwords/${encodeURIComponent(word)}`, {
        method: 'DELETE'
      });
      if (!response.ok) throw new Error('Failed to delete hotword');
      return await response.json();
    } catch (error) {
      logger.error('Error deleting hotword:', error.message);
      throw error;
    }
  });
});

app.on('will-quit', () => {
  const { uIOhook } = require('uiohook-napi');
  uIOhook.stop();
  globalShortcut.unregisterAll();

  // 清理 HotkeyManager 资源
  if (hotkeyManager) {
    hotkeyManager.cleanup();
  }
});

app.on('window-all-closed', () => {
  // Keep app running in background with tray icon
  // Don't quit on macOS either (app runs in tray)
});

// Prevent accidental quit
app.on('before-quit', (e) => {
  if (!app.isQuitting) {
    e.preventDefault();
  }
});