/**
 * HotkeyManager - 管理全局快捷键监听
 *
 * 职责：
 * 1. 监听 Ctrl+Win 组合键
 * 2. 延迟 0.5 秒后启动录音（防止误触）
 * 3. 松开任一键立即停止录音
 * 4. 3 秒超时自动重置状态（防止键盘状态卡住）
 */
class HotkeyManager {
  /**
   * @param {Object} options 配置选项
   * @param {Function} options.onRecordStart 开始录音的回调
   * @param {Function} options.onRecordStop 停止录音的回调
   * @param {Function} options.isRecording 获取当前录音状态的函数
   * @param {Object} options.keyCodes 按键码映射 { Ctrl, CtrlRight, WinLeft, WinRight }
   * @param {Number} options.recordingDelay 录音延迟时间（毫秒，默认 500）
   * @param {Number} options.stateResetTimeout 状态重置超时时间（毫秒，默认 3000）
   * @param {Object} options.timers 计时器接口（用于测试，默认使用 setTimeout/clearTimeout）
   */
  constructor(options = {}) {
    this.onRecordStart = options.onRecordStart || (() => {});
    this.onRecordStop = options.onRecordStop || (() => {});
    this.isRecording = options.isRecording || (() => false);

    // 按键码映射
    this.keyCodes = options.keyCodes || {
      Ctrl: 29,           // uiohook-napi 的 Ctrl 左键码
      CtrlRight: 3613,    // Ctrl 右键码
      WinLeft: 3675,      // Win 左键码
      WinRight: 3676      // Win 右键码
    };

    // 延迟配置
    this.recordingDelay = options.recordingDelay || 500;  // 0.5 秒
    this.stateResetTimeout = options.stateResetTimeout || 3000;  // 3 秒

    // 计时器接口（便于测试）
    this.timers = options.timers || {
      setTimeout: setTimeout.bind(global),
      clearTimeout: clearTimeout.bind(global)
    };

    // 状态管理
    this.pressedKeys = new Set();
    this.stateResetTimer = null;
    this.recordingDelayTimer = null;
  }

  /**
   * 检查 Ctrl 键是否被按下
   */
  hasCtrlPressed() {
    return this.pressedKeys.has(this.keyCodes.Ctrl) ||
           this.pressedKeys.has(this.keyCodes.CtrlRight);
  }

  /**
   * 检查 Win 键是否被按下
   */
  hasWinPressed() {
    return this.pressedKeys.has(this.keyCodes.WinLeft) ||
           this.pressedKeys.has(this.keyCodes.WinRight);
  }

  /**
   * 检查当前按键状态并触发相应动作
   */
  checkAndTrigger() {
    const hasCtrl = this.hasCtrlPressed();
    const hasWin = this.hasWinPressed();
    const recording = this.isRecording();

    // 情况 1: Ctrl+Win 都按下，且未开始录音 -> 延迟启动录音
    if (hasCtrl && hasWin && !recording) {
      // 取消之前的延迟计时器（如果有）
      if (this.recordingDelayTimer) {
        this.timers.clearTimeout(this.recordingDelayTimer);
      }

      // 延迟 0.5 秒后启动录音
      console.log('Ctrl+Win pressed - waiting before starting recording');
      this.recordingDelayTimer = this.timers.setTimeout(() => {
        // 再次检查按键状态（防止延迟期间松开）
        const stillHasCtrl = this.hasCtrlPressed();
        const stillHasWin = this.hasWinPressed();

        if (stillHasCtrl && stillHasWin && !this.isRecording()) {
          console.log('Delay passed - starting recording');
          this.onRecordStart();
        } else {
          console.log('Keys released during delay - recording cancelled');
        }
        this.recordingDelayTimer = null;
      }, this.recordingDelay);
    }
    // 情况 2: 正在录音，但 Ctrl 或 Win 松开 -> 立即停止录音
    else if (recording && (!hasCtrl || !hasWin)) {
      console.log('Ctrl+Win released - stopping recording immediately');
      this.onRecordStop();
    }
    // 情况 3: 未开始录音，按键松开 -> 取消延迟计时器
    else if (!hasCtrl || !hasWin) {
      if (this.recordingDelayTimer) {
        console.log('Keys released before delay - cancelling recording start');
        this.timers.clearTimeout(this.recordingDelayTimer);
        this.recordingDelayTimer = null;
      }
    }
  }

  /**
   * 重置状态超时（防止键盘状态卡住）
   */
  resetStateAfterDelay() {
    if (this.stateResetTimer) {
      this.timers.clearTimeout(this.stateResetTimer);
    }

    this.stateResetTimer = this.timers.setTimeout(() => {
      if (this.pressedKeys.size > 0) {
        console.warn('Keyboard state timeout - force resetting stuck keys:', Array.from(this.pressedKeys));
        this.pressedKeys.clear();

        if (this.isRecording()) {
          console.warn('Force stopping recording due to stuck keys');
          this.onRecordStop();
        }

        if (this.recordingDelayTimer) {
          this.timers.clearTimeout(this.recordingDelayTimer);
          this.recordingDelayTimer = null;
        }
      }
    }, this.stateResetTimeout);
  }

  /**
   * 处理按键按下事件
   * @param {Number} keycode 按键码
   */
  onKeyDown(keycode) {
    this.pressedKeys.add(keycode);
    this.checkAndTrigger();
    this.resetStateAfterDelay();
  }

  /**
   * 处理按键释放事件
   * @param {Number} keycode 按键码
   */
  onKeyUp(keycode) {
    this.pressedKeys.delete(keycode);
    this.checkAndTrigger();
    this.resetStateAfterDelay();
  }

  /**
   * 注册全局快捷键监听
   * @param {Object} uIOhook uiohook-napi 实例
   */
  register(uIOhook) {
    // 监听按键按下
    uIOhook.on('keydown', (e) => {
      this.onKeyDown(e.keycode);
    });

    // 监听按键释放
    uIOhook.on('keyup', (e) => {
      this.onKeyUp(e.keycode);
    });

    // 启动监听
    uIOhook.start();
    console.log('Global hotkey registered: Hold Ctrl+Win to record');
  }

  /**
   * 清理资源
   */
  cleanup() {
    if (this.recordingDelayTimer) {
      this.timers.clearTimeout(this.recordingDelayTimer);
      this.recordingDelayTimer = null;
    }
    if (this.stateResetTimer) {
      this.timers.clearTimeout(this.stateResetTimer);
      this.stateResetTimer = null;
    }
    this.pressedKeys.clear();
  }

  /**
   * 获取当前按下的键（用于测试）
   */
  getPressedKeys() {
    return Array.from(this.pressedKeys);
  }
}

module.exports = HotkeyManager;
