const { app, BrowserWindow, globalShortcut, ipcMain, Tray, Menu, nativeImage } = require('electron');
const path = require('path');
const AudioRecorder = require('./audioRecorder');
const AsrService = require('./asrService');
const TextInserter = require('./textInserter');

// Set unique userData path to avoid cache conflicts
app.setPath('userData', path.join(app.getPath('appData'), 'desktop-dictation'));

// Disable cache to avoid permission errors
app.commandLine.appendSwitch('disable-http-cache');
app.commandLine.appendSwitch('disable-gpu-shader-disk-cache');

// Request single instance lock - only allow one instance to run
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  // Another instance is already running, quit this one
  console.log('Another instance is already running. Quitting...');
  app.quit();
} else {
  // This is the first instance
  app.on('second-instance', (event, commandLine, workingDirectory) => {
    // Someone tried to run a second instance, focus our window instead
    console.log('Second instance detected, focusing existing window');
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

function createOverlayWindow() {
  console.log('[DEBUG] Creating overlay window...');

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
  console.log('[DEBUG] Loading overlay from:', overlayPath);

  overlayWindow.loadFile(overlayPath);
  overlayWindow.setIgnoreMouseEvents(true);

  // Position at bottom center of the screen where the cursor is
  const { screen } = require('electron');
  const cursorPoint = screen.getCursorScreenPoint();
  const currentDisplay = screen.getDisplayNearestPoint(cursorPoint);

  console.log('[DEBUG] Cursor position:', cursorPoint);
  console.log('[DEBUG] Current display:', currentDisplay.bounds);

  const { x: displayX, y: displayY, width, height } = currentDisplay.workArea;
  const x = displayX + Math.floor(width / 2 - 120);  // Center on current display
  const y = displayY + height - 200;                  // Bottom of current display

  console.log('[DEBUG] Screen size:', width, 'x', height);
  console.log('[DEBUG] Overlay position:', x, ',', y);

  overlayWindow.setPosition(x, y);

  // Set window level to ensure it's on top
  overlayWindow.setAlwaysOnTop(true, 'screen-saver');

  // Add error handler
  overlayWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error('[ERROR] Overlay failed to load:', errorCode, errorDescription);
  });

  overlayWindow.webContents.on('did-finish-load', () => {
    console.log('[DEBUG] Overlay loaded successfully');
  });

  console.log('[DEBUG] Overlay window created');
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

  console.log('[DEBUG] Starting recording...');
  isRecording = true;

  // Check if overlayWindow exists
  if (!overlayWindow) {
    console.error('[ERROR] overlayWindow is null!');
    return;
  }

  if (overlayWindow.isDestroyed()) {
    console.error('[ERROR] overlayWindow is destroyed!');
    return;
  }

  console.log('[DEBUG] Showing overlay window...');
  overlayWindow.show();
  console.log('[DEBUG] Overlay visibility:', overlayWindow.isVisible());
  console.log('[DEBUG] Overlay position:', overlayWindow.getBounds());

  audioRecorder.start();
  console.log('[DEBUG] Audio recorder started');
}

function stopRecording() {
  if (!isRecording) return;

  isRecording = false;
  overlayWindow.hide();

  audioRecorder.stop(async (audioBuffer) => {
    try {
      // Send to ASR service
      const text = await asrService.transcribe(audioBuffer);

      // Insert text at cursor position
      if (text && text.trim()) {
        textInserter.insertText(text.trim());
      }
    } catch (error) {
      console.error('Transcription error:', error);
    }
  });
}

function registerGlobalShortcut() {
  const { uIOhook, UiohookKey } = require('uiohook-napi');

  // Use Set to track currently pressed keys (avoids state desync issues)
  const pressedKeys = new Set();
  let stateResetTimer = null;

  // Check current key state and trigger/stop recording accordingly
  function checkAndTrigger() {
    const hasCtrl = pressedKeys.has(UiohookKey.Ctrl) ||
                    pressedKeys.has(UiohookKey.CtrlRight);
    const hasWin = pressedKeys.has(3675) || pressedKeys.has(3676);

    if (hasCtrl && hasWin && !isRecording) {
      console.log('Ctrl+Win pressed - starting recording');
      startRecording();
    } else if (isRecording && (!hasCtrl || !hasWin)) {
      console.log('Ctrl+Win released - stopping recording');
      stopRecording();
    }
  }

  // Auto-reset state after 3 seconds of no keyboard activity (fixes stuck keys)
  function resetStateAfterDelay() {
    if (stateResetTimer) clearTimeout(stateResetTimer);

    stateResetTimer = setTimeout(() => {
      if (pressedKeys.size > 0) {
        console.warn('Keyboard state timeout - force resetting stuck keys:', Array.from(pressedKeys));
        pressedKeys.clear();
        if (isRecording) {
          console.warn('Force stopping recording due to stuck keys');
          stopRecording();
        }
      }
    }, 3000); // 3 seconds timeout
  }

  // Listen for key down events
  uIOhook.on('keydown', (e) => {
    pressedKeys.add(e.keycode);
    checkAndTrigger();
    resetStateAfterDelay();
  });

  // Listen for key up events
  uIOhook.on('keyup', (e) => {
    pressedKeys.delete(e.keycode);
    checkAndTrigger();
    resetStateAfterDelay();
  });

  // Start the hook
  uIOhook.start();
  console.log('Global hotkey registered: Hold Ctrl+Win to record');
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
    console.log(`Permission request: ${permission}`);
    callback(true); // Allow all permissions for our app
  });

  session.defaultSession.setPermissionCheckHandler((webContents, permission, requestingOrigin, details) => {
    console.log(`Permission check: ${permission}`);
    return true; // Allow all permission checks
  });

  // Initialize services
  audioRecorder = new AudioRecorder();
  asrService = new AsrService('http://localhost:8082');
  textInserter = new TextInserter();

  createOverlayWindow();
  createTray();
  registerGlobalShortcut();

  console.log('Desktop Dictation is ready!');
  console.log('Hold Ctrl+Win to record');

  // IPC handlers for hotwords management
  ipcMain.handle('get-hotwords', async () => {
    try {
      const response = await fetch('http://localhost:8082/hotwords');
      if (!response.ok) throw new Error('Failed to fetch hotwords');
      return await response.json();
    } catch (error) {
      console.error('Error fetching hotwords:', error);
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
      console.error('Error adding hotword:', error);
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
      console.error('Error deleting hotword:', error);
      throw error;
    }
  });
});

app.on('will-quit', () => {
  const { uIOhook } = require('uiohook-napi');
  uIOhook.stop();
  globalShortcut.unregisterAll();
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