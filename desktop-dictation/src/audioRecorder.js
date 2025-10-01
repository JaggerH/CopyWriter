const { BrowserWindow } = require('electron');
const path = require('path');
const { exec } = require('child_process');
const { promisify } = require('util');
const execAsync = promisify(exec);

class AudioRecorder {
  constructor() {
    this.recorderWindow = null;
    this.previousVolume = null;
    this.callback = null;
    this.createRecorderWindow();
  }

  createRecorderWindow() {
    // Create a hidden window for audio recording
    this.recorderWindow = new BrowserWindow({
      show: false,
      webPreferences: {
        nodeIntegration: true,
        contextIsolation: false
      }
    });

    this.recorderWindow.loadFile(path.join(__dirname, 'recorder.html'));

    // Wait for window to be ready
    this.recorderWindow.webContents.on('did-finish-load', () => {
      console.log('Recorder window loaded successfully');
    });

    // Log console messages from renderer
    this.recorderWindow.webContents.on('console-message', (event, level, message) => {
      console.log(`[Recorder] ${message}`);
    });

    // Handle audio data from renderer
    const { ipcMain } = require('electron');
    ipcMain.on('audio-data', (event, audioBuffer) => {
      console.log(`Received audio data: ${audioBuffer.byteLength} bytes`);
      if (this.callback) {
        this.callback(Buffer.from(audioBuffer));
        this.callback = null;
      }
    });
  }

  muteSystemAudio() {
    console.log('[AudioRecorder] muteSystemAudio() called');
    console.log('[AudioRecorder] Platform:', process.platform);
    try {
      if (process.platform === 'win32') {
        console.log('[AudioRecorder] Attempting to mute system audio on Windows...');
        // Windows: Use uiohook to simulate volume mute key
        const { uIOhook, UiohookKey } = require('uiohook-napi');

        console.log('[AudioRecorder] AudioVolumeMute keycode:', UiohookKey.AudioVolumeMute);
        // Press Volume Mute key (0xAD = 173)
        uIOhook.keyTap(UiohookKey.AudioVolumeMute);
        console.log('[AudioRecorder] ✓ System audio mute key tapped (Windows)');
      } else if (process.platform === 'darwin') {
        // macOS: Use osascript
        execAsync('osascript -e "get volume settings"').then(({ stdout }) => {
          const match = stdout.match(/output volume:(\d+)/);
          if (match) {
            this.previousVolume = parseInt(match[1]);
            execAsync('osascript -e "set volume output volume 0"');
            console.log(`System audio muted (macOS) - previous volume: ${this.previousVolume}`);
          }
        }).catch(() => {
          console.log('Audio mute not available (macOS)');
        });
      } else if (process.platform === 'linux') {
        // Linux: Use amixer
        execAsync('amixer get Master | grep -o "[0-9]*%"').then(({ stdout }) => {
          this.previousVolume = parseInt(stdout);
          execAsync('amixer set Master 0%');
          console.log(`System audio muted (Linux) - previous volume: ${this.previousVolume}`);
        }).catch(() => {
          console.log('Audio mute not available (Linux)');
        });
      }
    } catch (error) {
      console.log('[AudioRecorder] ✗ Error in muteSystemAudio:', error.message);
      console.log('[AudioRecorder] Stack trace:', error.stack);
    }
  }

  restoreSystemAudio() {
    console.log('[AudioRecorder] restoreSystemAudio() called');
    console.log('[AudioRecorder] Platform:', process.platform);
    try {
      if (process.platform === 'win32') {
        console.log('[AudioRecorder] Attempting to restore system audio on Windows...');
        // Windows: Press mute key again to unmute
        const { uIOhook, UiohookKey } = require('uiohook-napi');
        uIOhook.keyTap(UiohookKey.AudioVolumeMute);
        console.log('[AudioRecorder] ✓ System audio mute key tapped again (Windows - should unmute)');
      } else if (this.previousVolume !== null) {
        if (process.platform === 'darwin') {
          execAsync(`osascript -e "set volume output volume ${this.previousVolume}"`).then(() => {
            console.log(`System audio restored (macOS) - volume: ${this.previousVolume}`);
            this.previousVolume = null;
          });
        } else if (process.platform === 'linux') {
          execAsync(`amixer set Master ${this.previousVolume}%`).then(() => {
            console.log(`System audio restored (Linux) - volume: ${this.previousVolume}`);
            this.previousVolume = null;
          });
        }
      }
    } catch (error) {
      console.log('[AudioRecorder] ✗ Error in restoreSystemAudio:', error.message);
      console.log('[AudioRecorder] Stack trace:', error.stack);
    }
  }

  start() {
    // Note: System audio muting disabled - uiohook-napi doesn't support AudioVolumeMute key
    // this.muteSystemAudio();

    // Send start recording message to renderer
    this.recorderWindow.webContents.send('start-recording');

    console.log('Recording started');
  }

  stop(callback) {
    this.callback = callback;

    // Note: System audio restore disabled - uiohook-napi doesn't support AudioVolumeMute key
    // this.restoreSystemAudio();

    // Send stop recording message to renderer
    this.recorderWindow.webContents.send('stop-recording');

    console.log('Recording stopped');
  }
}

module.exports = AudioRecorder;