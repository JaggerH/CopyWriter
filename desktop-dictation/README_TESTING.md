# HotkeyManager 测试文档

## 概述

本文档说明 `HotkeyManager` 模块的测试策略和使用方法。

## 快速开始

### 安装依赖

```bash
cd desktop-dictation
npm install
```

### 运行测试

```bash
# 运行所有测试
npm test

# 监视模式（自动重新运行）
npm run test:watch

# 生成覆盖率报告
npm run test:coverage
```

## 测试架构

### HotkeyManager 模块设计

`HotkeyManager` 是一个独立的、可测试的快捷键管理器，负责：

1. **按键状态追踪**：使用 Set 跟踪当前按下的所有按键
2. **组合键检测**：识别 Ctrl+Win 组合键（支持左右键）
3. **延迟启动**：按下组合键 0.5 秒后才开始录音（防止误触）
4. **立即停止**：松开任一键立即停止录音
5. **状态超时重置**：3 秒无键盘活动自动重置状态（防止键盘状态卡住）

### 可测试性设计

为了方便单元测试，模块采用依赖注入设计：

```javascript
const manager = new HotkeyManager({
  onRecordStart: () => {},     // 录音开始回调
  onRecordStop: () => {},      // 录音停止回调
  isRecording: () => false,    // 录音状态查询
  keyCodes: { ... },           // 自定义按键码
  recordingDelay: 500,         // 录音延迟（毫秒）
  stateResetTimeout: 3000,     // 状态重置超时（毫秒）
  timers: { ... }              // 计时器接口（测试时可 mock）
});
```

## 测试覆盖范围

### 1. 基础功能测试

- ✅ 按下 Ctrl+Win 延迟 500ms 启动录音
- ✅ 松开任一键立即停止录音
- ✅ 延迟期间松开键取消录音
- ✅ 重复按键不重复触发

### 2. 边界情况测试

- ✅ 只按 Ctrl 或只按 Win（不触发）
- ✅ 左 Ctrl + 右 Win（触发）
- ✅ 右 Ctrl + 左 Win（触发）
- ✅ 同时按左右 Ctrl + Win（触发）
- ✅ 快速按下松开（不触发）
- ✅ 按下其他无关键（Shift、Alt 等）
- ✅ 正在录音时重新按键（不重复启动）
- ✅ 松开所有键后状态完全清空

### 3. 超时重置测试

- ✅ 3 秒后自动重置按键状态
- ✅ 超时时正在录音则停止录音
- ✅ 超时时取消延迟计时器
- ✅ 每次按键重置超时计时器
- ✅ 超时后重新按键可重新开始

### 4. 状态管理测试

- ✅ cleanup 清理所有资源
- ✅ 已在录音时不重复启动
- ✅ getPressedKeys 正确返回按键列表
- ✅ hasCtrlPressed/hasWinPressed 正确识别

### 5. 极端情况测试

- ✅ 按键码为 0、负数、超大数字
- ✅ 重复松开同一个键
- ✅ 未按下直接松开
- ✅ 同时按下 10 个键
- ✅ 延迟/超时为 0

### 6. 复杂按键序列测试

- ✅ Ctrl→Win→Win松开→Win再按下
- ✅ 按下多个无关键后按 Ctrl+Win
- ✅ 录音中按其他键不影响
- ✅ 快速多次按下松开

## 测试策略

### Mock 计时器

测试中使用 mock 计时器来精确控制时间流逝：

```javascript
const mockTimers = {
  setTimeout: jest.fn((callback, delay) => {
    // 记录计时器并返回 ID
    return timerId;
  }),
  clearTimeout: jest.fn((id) => {
    // 标记计时器已清除
  })
};

// 手动触发计时器
function triggerTimersWithDelay(delay) {
  timerCallbacks
    .filter(t => !t.cleared && t.delay === delay)
    .forEach(t => t.callback());
}
```

### 隔离测试

每个测试用例都独立创建 `HotkeyManager` 实例，并在测试后清理：

```javascript
beforeEach(() => {
  manager = new HotkeyManager({ ... });
});

afterEach(() => {
  manager.cleanup();
});
```

## 常见问题

### Q1: 为什么需要 0.5 秒延迟？

**A**: 防止误触。用户可能只是短暂按下组合键，延迟确保是有意的长按操作。

### Q2: 为什么需要 3 秒超时重置？

**A**: 防止键盘状态卡住。某些情况下（如切换窗口、系统快捷键拦截）可能导致松键事件丢失，超时机制确保状态最终会被重置。

### Q3: 如何测试真实的键盘事件？

**A**: 单元测试不需要真实键盘事件。真实集成测试应该在 Electron 应用中手动测试，或使用端到端测试框架（如 Spectron）。

### Q4: 为什么 Win 键码是 3675/3676？

**A**: 这是 uiohook-napi 库定义的 Windows 键的键码。不同键盘库可能使用不同的键码。

## 维护指南

### 添加新测试

1. 在 `src/HotkeyManager.test.js` 中添加新的 `test()` 或 `describe()` 块
2. 使用 mock 计时器控制时间流逝
3. 验证回调函数是否被正确调用
4. 验证内部状态（使用 `getPressedKeys()`）

### 修改延迟/超时配置

如果修改了默认的 500ms 延迟或 3000ms 超时：

1. 更新构造函数的默认值
2. 更新测试中的 `triggerTimersWithDelay()` 调用
3. 更新文档中的时间说明

### 添加新快捷键组合

要支持其他快捷键组合（如 Ctrl+Alt）：

1. 修改 `checkAndTrigger()` 逻辑
2. 添加对应的 `hasXxxPressed()` 方法
3. 添加完整的测试用例（参考现有测试结构）

## 测试覆盖率目标

- **分支覆盖率**: ≥ 80%
- **函数覆盖率**: ≥ 80%
- **行覆盖率**: ≥ 80%
- **语句覆盖率**: ≥ 80%

查看详细覆盖率报告：

```bash
npm run test:coverage
# 打开 coverage/lcov-report/index.html
```

## 参考资料

- [Jest 文档](https://jestjs.io/)
- [uiohook-napi 文档](https://github.com/SnosMe/uiohook-napi)
- [Electron 测试指南](https://www.electronjs.org/docs/latest/tutorial/automated-testing)
