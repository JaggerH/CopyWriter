# CopyWriter - 音视频转文本工具

一个自动化的音视频转文本工具，支持监控文件夹中的新文件并自动进行语音识别转换。

## 功能特性

- 🎥 支持多种音视频格式：MP4, AVI, MOV, MKV, WMV, FLV, WebM, M4V, M4A, WAV, FLAC, AAC, OGG, WMA, MP3
- 🔄 自动文件监控：监控指定文件夹，自动处理新下载的文件
- 🎯 智能过滤：自动忽略特定格式的文件（如 audio*.m4a）
- 📝 语音识别：使用 FunASR 进行高精度中文语音识别
- 🧹 自动清理：处理完成后自动清理临时文件

## 项目入口

### 主要入口：自动监控模式
```bash
python auto.py
```
启动后会自动监控 `./download` 文件夹，检测到新的音视频文件时自动进行转换。

### 手动转换模式
```bash
python convert.py <输入文件路径>
```
手动转换单个音视频文件为文本。

## 安装

### 创建 Conda 环境
```bash
conda create -n copywriter python=3.11
conda activate copywriter

# index-url中的版本根据`nvidia-smi`运行后的结果自行判断
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu129
pip install -r requirement.txt
pip install -r Bili23-Downloader/requirements.txt
```

## 使用说明

### 1. 启动自动监控
```bash
python auto.py
```
- 自动启动 Bili23-Downloader GUI（如果未运行）
- 监控 `./download` 文件夹
- 自动处理新下载的音视频文件

### 2. 手动转换文件
```bash
python convert.py C:\Users\Jagger\Downloads\video.mp4
```

### 3. 支持的格式
- **视频格式**: MP4, AVI, MOV, MKV, WMV, FLV, WebM, M4V
- **音频格式**: M4A, WAV, FLAC, AAC, OGG, WMA, MP3

## 项目结构

```
CopyWriter/
├── auto.py              # 主入口文件（自动监控模式）
├── convert.py           # 手动转换工具
├── download/            # 监控文件夹
├── output/              # 输出文件夹
├── Bili23-Downloader/   # 下载器子模块
└── tools/               # 工具文件夹
```

## 依赖项目

- **Bili23-Downloader**: 作为 Git 子模块集成，用于视频下载功能

## 注意事项

- 确保已安装 FFmpeg 并添加到系统路径
- 首次运行会自动下载语音识别模型
- 处理大文件时请耐心等待
- 临时文件会自动清理，无需手动删除
