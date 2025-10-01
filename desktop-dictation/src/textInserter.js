const { clipboard, globalShortcut } = require('electron');
const { uIOhook, UiohookKey } = require('uiohook-napi');

class TextInserter {
  constructor() {
    this.previousClipboard = '';
  }

  insertText(text) {
    try {
      // Save current clipboard content
      this.previousClipboard = clipboard.readText();

      // Set new clipboard content
      clipboard.writeText(text);

      // Small delay to ensure clipboard is set
      setTimeout(() => {
        // Simulate Ctrl+V (paste)
        this.simulatePaste();

        // Restore previous clipboard after a delay
        setTimeout(() => {
          clipboard.writeText(this.previousClipboard);
        }, 500);

        console.log('Text inserted via clipboard:', text);
      }, 100);
    } catch (error) {
      console.error('Failed to insert text:', error);
    }
  }

  simulatePaste() {
    // Use uiohook to simulate Ctrl+V
    const isWindows = process.platform === 'win32';
    const isMac = process.platform === 'darwin';

    if (isMac) {
      // Cmd+V on macOS
      uIOhook.keyToggle(UiohookKey.Cmd, 'down');
      uIOhook.keyToggle(UiohookKey.V, 'down');
      uIOhook.keyToggle(UiohookKey.V, 'up');
      uIOhook.keyToggle(UiohookKey.Cmd, 'up');
    } else {
      // Ctrl+V on Windows/Linux
      uIOhook.keyToggle(UiohookKey.Ctrl, 'down');
      uIOhook.keyToggle(UiohookKey.V, 'down');
      uIOhook.keyToggle(UiohookKey.V, 'up');
      uIOhook.keyToggle(UiohookKey.Ctrl, 'up');
    }
  }
}

module.exports = TextInserter;