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
  overlayWindow = new BrowserWindow({
    width: 200,
    height: 200,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    focusable: false,
    show: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  overlayWindow.loadFile(path.join(__dirname, 'overlay.html'));
  overlayWindow.setIgnoreMouseEvents(true);

  // Position at bottom center of screen
  const { screen } = require('electron');
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width, height } = primaryDisplay.workAreaSize;
  overlayWindow.setPosition(
    Math.floor(width / 2 - 100),
    Math.floor(height - 250)
  );
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

  isRecording = true;
  overlayWindow.show();
  audioRecorder.start();
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

  let ctrlPressed = false;
  let winPressed = false;

  // Listen for key down events
  uIOhook.on('keydown', (e) => {
    // Check for Ctrl key (left or right)
    if (e.keycode === UiohookKey.Ctrl || e.keycode === UiohookKey.CtrlRight) {
      ctrlPressed = true;
    }
    // Check for Windows key (3675 for left Win, 3676 for right Win on Windows)
    if (e.keycode === 3675 || e.keycode === 3676) {
      winPressed = true;
    }

    // Start recording ONLY when BOTH Ctrl AND Windows are pressed (not Alt!)
    if (ctrlPressed && winPressed && !isRecording) {
      console.log('Ctrl+Win pressed - starting recording');
      startRecording();
    }
  });

  // Listen for key up events
  uIOhook.on('keyup', (e) => {
    // Check for Ctrl key release
    if (e.keycode === UiohookKey.Ctrl || e.keycode === UiohookKey.CtrlRight) {
      ctrlPressed = false;
    }
    // Check for Windows key release
    if (e.keycode === 3675 || e.keycode === 3676) {
      winPressed = false;
    }

    // Stop recording when either key is released
    if (isRecording && (!ctrlPressed || !winPressed)) {
      console.log('Ctrl+Win released - stopping recording');
      stopRecording();
    }
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