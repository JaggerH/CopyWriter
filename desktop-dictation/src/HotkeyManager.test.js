/**
 * HotkeyManager 单元测试
 *
 * 测试覆盖：
 * 1. 基础功能：按键监听、延迟启动、立即停止
 * 2. 边界情况：单键、组合键、重复按键、快速操作
 * 3. 超时重置：3 秒自动清理状态
 * 4. 状态管理：防止状态不一致
 */

const HotkeyManager = require('./HotkeyManager');

describe('HotkeyManager', () => {
  let manager;
  let mockCallbacks;
  let mockTimers;
  let timerCallbacks;

  beforeEach(() => {
    // Mock 回调函数
    mockCallbacks = {
      onRecordStart: jest.fn(),
      onRecordStop: jest.fn(),
      isRecording: jest.fn().mockReturnValue(false)
    };

    // Mock 计时器（用于精确控制时间）
    timerCallbacks = [];
    mockTimers = {
      setTimeout: jest.fn((callback, delay) => {
        const id = timerCallbacks.length;
        timerCallbacks.push({ callback, delay, id, cleared: false });
        return id;
      }),
      clearTimeout: jest.fn((id) => {
        if (timerCallbacks[id]) {
          timerCallbacks[id].cleared = true;
        }
      })
    };

    // 创建 manager 实例
    manager = new HotkeyManager({
      ...mockCallbacks,
      timers: mockTimers,
      keyCodes: {
        Ctrl: 29,
        CtrlRight: 3613,
        WinLeft: 3675,
        WinRight: 3676
      }
    });
  });

  afterEach(() => {
    manager.cleanup();
  });

  // ========== 辅助函数 ==========

  /**
   * 触发所有未清除的计时器（按创建顺序）
   */
  function triggerTimers() {
    timerCallbacks.forEach(timer => {
      if (!timer.cleared && timer.callback) {
        timer.callback();
      }
    });
  }

  /**
   * 触发指定延迟的计时器
   */
  function triggerTimersWithDelay(delay) {
    timerCallbacks
      .filter(t => !t.cleared && t.delay === delay)
      .forEach(t => t.callback());
  }

  // ========== 基础功能测试 ==========

  describe('基础功能', () => {
    test('按下 Ctrl+Win 应延迟 500ms 启动录音', () => {
      // 按下 Ctrl
      manager.onKeyDown(29);
      expect(mockCallbacks.onRecordStart).not.toHaveBeenCalled();

      // 按下 Win
      manager.onKeyDown(3675);
      expect(mockCallbacks.onRecordStart).not.toHaveBeenCalled();

      // 触发 500ms 延迟计时器
      triggerTimersWithDelay(500);
      expect(mockCallbacks.onRecordStart).toHaveBeenCalledTimes(1);
    });

    test('松开任一键应立即停止录音', () => {
      // 按下 Ctrl+Win 并启动录音
      manager.onKeyDown(29);
      manager.onKeyDown(3675);
      triggerTimersWithDelay(500);
      mockCallbacks.isRecording.mockReturnValue(true);

      // 松开 Ctrl
      manager.onKeyUp(29);
      expect(mockCallbacks.onRecordStop).toHaveBeenCalledTimes(1);
    });

    test('延迟期间松开键应取消录音', () => {
      // 按下 Ctrl+Win
      manager.onKeyDown(29);
      manager.onKeyDown(3675);
      expect(mockCallbacks.onRecordStart).not.toHaveBeenCalled();

      // 在延迟期间松开 Win
      manager.onKeyUp(3675);

      // 触发延迟计时器（但不应启动录音）
      triggerTimersWithDelay(500);
      expect(mockCallbacks.onRecordStart).not.toHaveBeenCalled();
    });

    test('延迟期间再次按下相同按键不应重复触发', () => {
      // 按下 Ctrl+Win
      manager.onKeyDown(29);
      manager.onKeyDown(3675);

      // 重复按下（模拟按键重复）
      manager.onKeyDown(29);
      manager.onKeyDown(3675);

      // 应该只创建一个 500ms 计时器
      const recordingTimers = timerCallbacks.filter(t => t.delay === 500 && !t.cleared);
      expect(recordingTimers.length).toBeGreaterThan(0);

      // 触发计时器，应该只启动一次录音
      triggerTimersWithDelay(500);
      expect(mockCallbacks.onRecordStart).toHaveBeenCalledTimes(1);
    });
  });

  // ========== 边界情况测试 ==========

  describe('边界情况', () => {
    test('只按 Ctrl 不应触发录音', () => {
      manager.onKeyDown(29);
      triggerTimersWithDelay(500);
      expect(mockCallbacks.onRecordStart).not.toHaveBeenCalled();
    });

    test('只按 Win 不应触发录音', () => {
      manager.onKeyDown(3675);
      triggerTimersWithDelay(500);
      expect(mockCallbacks.onRecordStart).not.toHaveBeenCalled();
    });

    test('左 Ctrl + 右 Win 应触发录音', () => {
      manager.onKeyDown(29);      // 左 Ctrl
      manager.onKeyDown(3676);    // 右 Win
      triggerTimersWithDelay(500);
      expect(mockCallbacks.onRecordStart).toHaveBeenCalledTimes(1);
    });

    test('右 Ctrl + 左 Win 应触发录音', () => {
      manager.onKeyDown(3613);    // 右 Ctrl
      manager.onKeyDown(3675);    // 左 Win
      triggerTimersWithDelay(500);
      expect(mockCallbacks.onRecordStart).toHaveBeenCalledTimes(1);
    });

    test('同时按左右 Ctrl + 左 Win 应触发录音', () => {
      manager.onKeyDown(29);      // 左 Ctrl
      manager.onKeyDown(3613);    // 右 Ctrl
      manager.onKeyDown(3675);    // 左 Win
      triggerTimersWithDelay(500);
      expect(mockCallbacks.onRecordStart).toHaveBeenCalledTimes(1);
    });

    test('快速按下松开不应触发录音', () => {
      manager.onKeyDown(29);
      manager.onKeyDown(3675);
      manager.onKeyUp(29);
      manager.onKeyUp(3675);
      triggerTimersWithDelay(500);
      expect(mockCallbacks.onRecordStart).not.toHaveBeenCalled();
    });

    test('按下 Ctrl+Shift+Win 后松开 Shift 应继续录音', () => {
      // 按下 Ctrl+Shift+Win
      manager.onKeyDown(29);      // Ctrl
      manager.onKeyDown(42);      // Shift
      manager.onKeyDown(3675);    // Win
      triggerTimersWithDelay(500);
      mockCallbacks.isRecording.mockReturnValue(true);

      // 松开 Shift（Ctrl+Win 仍按下）
      manager.onKeyUp(42);
      expect(mockCallbacks.onRecordStop).not.toHaveBeenCalled();
    });

    test('正在录音时松开 Ctrl 后重新按下不应重启录音', () => {
      // 启动录音
      manager.onKeyDown(29);
      manager.onKeyDown(3675);
      triggerTimersWithDelay(500);
      mockCallbacks.isRecording.mockReturnValue(true);

      // 松开 Ctrl（停止录音）
      manager.onKeyUp(29);
      expect(mockCallbacks.onRecordStop).toHaveBeenCalledTimes(1);

      // 重新按下 Ctrl（仍在录音状态）
      mockCallbacks.onRecordStart.mockClear();
      manager.onKeyDown(29);
      triggerTimersWithDelay(500);

      // 不应重新启动录音
      expect(mockCallbacks.onRecordStart).not.toHaveBeenCalled();
    });

    test('松开所有键后状态应完全清空', () => {
      manager.onKeyDown(29);
      manager.onKeyDown(3675);
      manager.onKeyUp(29);
      manager.onKeyUp(3675);
      expect(manager.getPressedKeys()).toEqual([]);
    });
  });

  // ========== 超时重置测试 ==========

  describe('超时重置', () => {
    test('3 秒后应自动重置按键状态', () => {
      manager.onKeyDown(29);
      expect(manager.getPressedKeys()).toContain(29);

      // 触发 3 秒超时
      triggerTimersWithDelay(3000);
      expect(manager.getPressedKeys()).toEqual([]);
    });

    test('超时时正在录音应停止录音', () => {
      manager.onKeyDown(29);
      manager.onKeyDown(3675);
      triggerTimersWithDelay(500);
      mockCallbacks.isRecording.mockReturnValue(true);

      // 触发 3 秒超时
      triggerTimersWithDelay(3000);
      expect(mockCallbacks.onRecordStop).toHaveBeenCalledTimes(1);
    });

    test('超时时有延迟计时器应取消', () => {
      manager.onKeyDown(29);
      manager.onKeyDown(3675);

      // 获取延迟计时器 ID
      const recordingTimer = timerCallbacks.find(t => t.delay === 500);
      expect(recordingTimer).toBeDefined();

      // 触发 3 秒超时
      triggerTimersWithDelay(3000);

      // 验证延迟计时器被清除
      expect(recordingTimer.cleared).toBe(true);
    });

    test('每次按键都应重置超时计时器', () => {
      manager.onKeyDown(29);

      // 第一个 3 秒计时器
      const timer1 = timerCallbacks.filter(t => t.delay === 3000).length;

      manager.onKeyDown(3675);

      // 应该有新的 3 秒计时器
      const timer2 = timerCallbacks.filter(t => t.delay === 3000).length;
      expect(timer2).toBeGreaterThan(timer1);
    });

    test('超时后重新按键应重新开始计时', () => {
      manager.onKeyDown(29);
      triggerTimersWithDelay(3000);
      expect(manager.getPressedKeys()).toEqual([]);

      // 重新按键
      manager.onKeyDown(29);
      expect(manager.getPressedKeys()).toContain(29);
    });
  });

  // ========== 状态管理测试 ==========

  describe('状态管理', () => {
    test('cleanup 应清理所有资源', () => {
      manager.onKeyDown(29);
      manager.onKeyDown(3675);

      manager.cleanup();

      expect(manager.getPressedKeys()).toEqual([]);
      expect(manager.recordingDelayTimer).toBeNull();
      expect(manager.stateResetTimer).toBeNull();
    });

    test('已在录音时再次按 Ctrl+Win 不应重复启动', () => {
      // 启动录音
      manager.onKeyDown(29);
      manager.onKeyDown(3675);
      triggerTimersWithDelay(500);
      mockCallbacks.isRecording.mockReturnValue(true);

      // 清空 mock 并再次按下（模拟重复按键）
      mockCallbacks.onRecordStart.mockClear();
      manager.onKeyDown(29);
      manager.onKeyDown(3675);
      triggerTimersWithDelay(500);

      expect(mockCallbacks.onRecordStart).not.toHaveBeenCalled();
    });

    test('getPressedKeys 应返回当前按下的所有键', () => {
      manager.onKeyDown(29);
      manager.onKeyDown(3675);
      manager.onKeyDown(42);

      const keys = manager.getPressedKeys();
      expect(keys).toContain(29);
      expect(keys).toContain(3675);
      expect(keys).toContain(42);
      expect(keys.length).toBe(3);
    });

    test('hasCtrlPressed 应正确识别 Ctrl 键', () => {
      expect(manager.hasCtrlPressed()).toBe(false);

      manager.onKeyDown(29);
      expect(manager.hasCtrlPressed()).toBe(true);

      manager.onKeyUp(29);
      manager.onKeyDown(3613);
      expect(manager.hasCtrlPressed()).toBe(true);
    });

    test('hasWinPressed 应正确识别 Win 键', () => {
      expect(manager.hasWinPressed()).toBe(false);

      manager.onKeyDown(3675);
      expect(manager.hasWinPressed()).toBe(true);

      manager.onKeyUp(3675);
      manager.onKeyDown(3676);
      expect(manager.hasWinPressed()).toBe(true);
    });
  });

  // ========== 极端情况测试 ==========

  describe('极端情况', () => {
    test('按键码为 0 应正常处理', () => {
      manager.onKeyDown(0);
      expect(manager.getPressedKeys()).toContain(0);
      manager.onKeyUp(0);
      expect(manager.getPressedKeys()).not.toContain(0);
    });

    test('按键码为负数应正常处理', () => {
      manager.onKeyDown(-1);
      expect(manager.getPressedKeys()).toContain(-1);
    });

    test('按键码为超大数字应正常处理', () => {
      manager.onKeyDown(999999);
      expect(manager.getPressedKeys()).toContain(999999);
    });

    test('重复松开同一个键不应报错', () => {
      manager.onKeyDown(29);
      manager.onKeyUp(29);
      manager.onKeyUp(29);  // 重复松开
      expect(manager.getPressedKeys()).toEqual([]);
    });

    test('未按下直接松开不应报错', () => {
      expect(() => manager.onKeyUp(29)).not.toThrow();
    });

    test('同时按下 10 个键应正常处理', () => {
      for (let i = 0; i < 10; i++) {
        manager.onKeyDown(i);
      }
      expect(manager.getPressedKeys().length).toBe(10);
    });

    test('自定义延迟配置应被正确使用', () => {
      // 清理之前的管理器
      manager.cleanup();

      const customDelay = 100;
      const newMockCallbacks = {
        onRecordStart: jest.fn(),
        onRecordStop: jest.fn(),
        isRecording: jest.fn().mockReturnValue(false)
      };

      manager = new HotkeyManager({
        ...newMockCallbacks,
        timers: mockTimers,
        recordingDelay: customDelay
      });

      // 清空之前的调用记录
      mockTimers.setTimeout.mockClear();

      manager.onKeyDown(29);
      manager.onKeyDown(3675);

      // 验证 setTimeout 被调用，且延迟参数正确
      expect(mockTimers.setTimeout).toHaveBeenCalledWith(
        expect.any(Function),
        customDelay
      );
    });

    test('超时为 0 应立即重置', () => {
      // 重置 timerCallbacks
      timerCallbacks = [];

      manager = new HotkeyManager({
        ...mockCallbacks,
        timers: mockTimers,
        stateResetTimeout: 0
      });

      manager.onKeyDown(29);

      // 触发所有计时器（包括超时为 0 的）
      triggerTimers();
      expect(manager.getPressedKeys()).toEqual([]);
    });
  });

  // ========== 按键序列测试 ==========

  describe('复杂按键序列', () => {
    test('序列：Ctrl按下 -> Win按下 -> Win松开 -> Win按下 -> 延迟', () => {
      manager.onKeyDown(29);      // Ctrl 按下
      manager.onKeyDown(3675);    // Win 按下
      manager.onKeyUp(3675);      // Win 松开（取消）
      manager.onKeyDown(3675);    // Win 再次按下
      triggerTimersWithDelay(500);
      expect(mockCallbacks.onRecordStart).toHaveBeenCalledTimes(1);
    });

    test('序列：按下多个无关键后按 Ctrl+Win', () => {
      manager.onKeyDown(65);      // A
      manager.onKeyDown(66);      // B
      manager.onKeyDown(67);      // C
      manager.onKeyDown(29);      // Ctrl
      manager.onKeyDown(3675);    // Win
      triggerTimersWithDelay(500);
      expect(mockCallbacks.onRecordStart).toHaveBeenCalledTimes(1);
    });

    test('序列：录音中按其他键不应影响', () => {
      manager.onKeyDown(29);
      manager.onKeyDown(3675);
      triggerTimersWithDelay(500);
      mockCallbacks.isRecording.mockReturnValue(true);

      // 按其他键
      manager.onKeyDown(65);
      manager.onKeyUp(65);

      expect(mockCallbacks.onRecordStop).not.toHaveBeenCalled();
    });

    test('序列：快速多次按下松开 Ctrl+Win', () => {
      for (let i = 0; i < 5; i++) {
        manager.onKeyDown(29);
        manager.onKeyDown(3675);
        manager.onKeyUp(29);
        manager.onKeyUp(3675);
      }

      // 不应有任何录音触发
      triggerTimersWithDelay(500);
      expect(mockCallbacks.onRecordStart).not.toHaveBeenCalled();
    });
  });
});
