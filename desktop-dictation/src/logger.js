const log = require('electron-log');
const path = require('path');

// Configure log file location
// Windows: %USERPROFILE%\AppData\Roaming\desktop-dictation\logs\
// macOS: ~/Library/Logs/desktop-dictation/
// Linux: ~/.config/desktop-dictation/logs/
log.transports.file.resolvePathFn = () => {
  const { app } = require('electron');
  const logsDir = path.join(app.getPath('userData'), 'logs');
  return path.join(logsDir, 'main.log');
};

// Set max file size to 5MB, keep 3 old files
log.transports.file.maxSize = 5 * 1024 * 1024;

// Log format
log.transports.file.format = '[{y}-{m}-{d} {h}:{i}:{s}.{ms}] [{level}] {text}';
log.transports.console.format = '[{h}:{i}:{s}] [{level}] {text}';

// Enable both console and file logging
log.transports.console.level = 'debug';
log.transports.file.level = 'debug';

// Export logger with same interface as console
module.exports = {
  log: log.info.bind(log),
  info: log.info.bind(log),
  warn: log.warn.bind(log),
  error: log.error.bind(log),
  debug: log.debug.bind(log),

  // Get log file path for debugging
  getLogPath: () => {
    return log.transports.file.getFile().path;
  }
};
