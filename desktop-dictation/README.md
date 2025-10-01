# Desktop Dictation Tool

跨平台语音转文字桌面工具，支持全局快捷键录音并自动转录到光标位置。

## 功能特性

- ✅ **全局快捷键**: 按住 `Ctrl+Win` 开始录音，松开停止
- ✅ **系统音频静音**: 录音时自动屏蔽后台音频输出（可选）
- ✅ **可视化指示器**: 录音时在屏幕底部中央显示录音图标
- ✅ **ASR 转录**: 自动将录音发送到 ASR 服务进行转录
- ✅ **智能文本插入**: 转录结果自动插入到当前光标位置（通过剪贴板）
- ✅ **跨平台支持**: Windows / macOS / Linux
- ✅ **零外部依赖**: 使用原生 Web Audio API，无需 sox 等工具

## 系统要求

- Node.js 16+
- Python 3.11+ (用于 ASR 服务)
- 运行中的 ASR 服务 (默认 `http://localhost:8082`)

### 平台特定要求

**Windows:**
- Visual Studio Build Tools (用于编译原生模块)

**macOS:**
- Xcode Command Line Tools

**Linux:**
- `alsa-utils` (音频控制)
- `libxtst-dev`, `libpng++-dev` (robotjs 依赖)

```bash
# Ubuntu/Debian
sudo apt-get install alsa-utils libxtst-dev libpng++-dev

# Fedora
sudo dnf install alsa-utils libXtst-devel libpng-devel
```

## 安装

```bash
cd desktop-dictation
npm install
```

## 使用方法

### 开发模式

```bash
npm run dev
```

### 启动应用

```bash
npm start
```

### 使用步骤

1. 启动应用后，它会在后台运行（无窗口）
2. 将光标放在任何可编辑的文本区域
3. **按住** `Ctrl+Win` 开始录音
4. 屏幕底部中央会显示红色录音指示器
5. 系统音频会自动静音（Windows/macOS/Linux）
6. **松开** `Ctrl+Win` 结束录音
7. 录音指示器消失，音频恢复
8. 转录完成后，文字自动通过剪贴板粘贴到光标位置

## 打包构建

### 构建所有平台

```bash
npm run build
```

### 构建特定平台

```bash
# Windows
npm run build:win

# macOS
npm run build:mac

# Linux
npm run build:linux
```

构建产物在 `dist/` 目录。

## 配置

### ASR 服务地址

默认连接到 `http://localhost:8082`。如需修改，编辑 `src/main.js`:

```javascript
asrService = new AsrService('http://your-asr-service:8082');
```

### 快捷键

默认快捷键为 `Ctrl+Alt+Space`。如需修改，编辑 `src/main.js`:

```javascript
globalShortcut.register('CommandOrControl+Alt+Space', () => {
  // ...
});
```

快捷键格式:
- `CommandOrControl`: macOS 上为 Cmd，其他平台为 Ctrl
- `Alt`: Alt 键
- `Shift`: Shift 键
- 字母/数字: 直接使用，如 'A', '1'

## 架构说明

```
desktop-dictation/
├── src/
│   ├── main.js              # Electron 主进程
│   ├── audioRecorder.js     # 音频录制 + 系统静音
│   ├── asrService.js        # ASR 服务集成
│   ├── textInserter.js      # 文本插入（robotjs）
│   └── overlay.html         # 录音指示器 UI
├── assets/                  # 应用图标
├── package.json
└── README.md
```

### 核心技术

- **Electron**: 跨平台桌面应用框架
- **node-record-lpcm16**: 录音
- **loudness**: 系统音量控制
- **robotjs**: 模拟键盘输入
- **axios**: HTTP 客户端

## 故障排除

### robotjs 编译失败

Windows 用户需要安装 Visual Studio Build Tools:
```bash
npm install --global windows-build-tools
```

### Linux 音频控制不工作

确保安装了 `alsa-utils`:
```bash
sudo apt-get install alsa-utils
```

### 文本插入不工作

1. 检查目标应用是否支持键盘输入
2. 尝试给予应用辅助功能权限（macOS）
3. 使用剪贴板方式插入（在 `textInserter.js` 中切换方法）

### ASR 服务连接失败

1. 确认 ASR 服务正在运行: `curl http://localhost:8082/health`
2. 检查防火墙设置
3. 查看应用日志

## 开发调试

启用 Electron DevTools:

```bash
npm run dev
```

查看控制台日志:
- 录音开始/停止
- ASR 请求/响应
- 文本插入操作

## License

MIT