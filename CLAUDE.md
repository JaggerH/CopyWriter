# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CopyWriter is an automated audio/video transcription tool that monitors folders for new media files and converts them to text using Chinese ASR (Automatic Speech Recognition). The project integrates with Bili23-Downloader for video downloading capabilities.

## Architecture

### Core Components
- **auto.py**: Main entry point that starts file monitoring and automatic processing
- **convert.py**: Manual conversion utility for single files
- **Bili23-Downloader/**: Git submodule for video downloading (wxPython-based GUI application)
- **tools/**: ASR models and processing utilities
  - `tools/asr/`: ASR processing modules (FunASR, FasterWhisper)
  - `tools/damo_asr/`: DAMO ASR models and configurations

### Processing Flow
1. File monitoring via watchdog detects new media files in `./download`
2. Files are validated against supported formats
3. Video files are converted to MP3 using FFmpeg
4. Audio undergoes Chinese ASR processing using FunASR models
5. Transcribed text is saved as .txt files with same base name
6. Temporary files are automatically cleaned up

## Development Commands

### Environment Setup

**CRITICAL: Always activate the conda environment before running any commands or tests:**
```bash
conda activate copywriter
```

Initial setup:
```bash
conda create -n copywriter python=3.11
conda activate copywriter
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu129
pip install -r requirement.txt
pip install -r Bili23-Downloader/requirements.txt
```

### Running the Application
```bash
# Automatic monitoring mode (main entry point)
python auto.py

# Manual conversion of single file  
python convert.py <input_file_path>
```

### Dependencies
- **FFmpeg**: Must be installed and in PATH for media conversion
- **FunASR**: Chinese ASR processing
- **psutil**: Process management for GUI detection
- **watchdog**: File system monitoring
- **tqdm**: Progress bars

## File Structure

### Key Configuration Files
- `config.json`: Bili23-Downloader configuration (download paths, quality settings, CDN options)
- `requirement.txt`: Python dependencies (note: encoding issues detected)
- `tools/damo_asr/models/`: Pre-trained ASR model files

### Supported Media Formats
- **Video**: MP4, AVI, MOV, MKV, WMV, FLV, WebM, M4V
- **Audio**: M4A, WAV, FLAC, AAC, OGG, WMA, MP3

### Directory Usage
- `./download/`: Monitored folder for new files
- `./output/`: Output directory for processed files
- `./audio/`: Sample audio files
- Temporary files created in system temp directory during processing

## Important Notes

### File Filtering
The monitoring system ignores:
- `*.txt` files
- Files matching `audio*.m4a` pattern
- Partial downloads (`*.part`, `*.tmp`)

### ASR Models
- Uses DAMO ASR models for Chinese speech recognition
- Models fallback to online versions if local files missing
- Local models stored in `tools/damo_asr/models/`

### Process Management
- `auto.py` automatically launches Bili23-Downloader GUI if not running
- Uses psutil to detect existing GUI processes
- File processing waits for complete downloads before processing

### Error Handling
- Comprehensive exception handling in both auto and manual modes
- FFmpeg conversion errors are caught and reported
- ASR processing failures are logged with tracebacks

## Telegram Bot Integration

### Project Location
- **Path**: `telegram_bot/`
- **Documentation**: `telegram_bot/README.md`
- **Environment**: Use `conda activate copywriter` for development

### Architecture
The Telegram Bot uses a Redis queue-based architecture for scalable video downloads:
- **Main Bot Process**: Receives Telegram messages, validates URLs, queues tasks
- **Worker Process**: Processes download tasks from Redis queue
- **Queue Manager**: Handles task distribution, progress tracking, and status management
- **Downloaders**: Modular downloader classes for different platforms (currently Bilibili)

### Key Components
- `src/utils.py`: URL validation, filename sanitization, task serialization
- `src/queue_manager.py`: Redis-based task queue management with progress tracking
- `src/downloaders/base.py`: Abstract base class for platform downloaders
- `src/downloaders/bilibili.py`: Bilibili downloader using Bili23-Downloader core
- `tests/`: Comprehensive unit tests with 90%+ coverage

### Testing
```bash
cd telegram_bot
python -m pytest                    # Run all tests
python -m pytest -v --cov=src      # Run with coverage report
python -m pytest tests/test_utils.py -v  # Run specific module tests
```

### Dependencies
- Redis server for queue management
- python-telegram-bot for Telegram API
- All Bili23-Downloader dependencies for video processing
- See `telegram_bot/requirements.txt` for full list

### Usage Pattern
1. Bot receives Bilibili URL from user
2. URL validation and task creation
3. Task queued in Redis with unique ID
4. Worker process picks up task
5. Downloads video using integrated Bili23-Downloader
6. Progress updates sent back to user
7. Completion notification with file info

## Microservices Architecture

### Project Location
- **Path**: Root directory (services/, shared/)
- **Documentation**: `README_microservices.md`

### Architecture Overview
The project includes a full microservices version with GPU acceleration:
- **video-service** (8080): Video parsing and download using Douyin_TikTok_Download_API
- **asr-service** (8082): GPU-accelerated ASR using NVIDIA containers
- **orchestrator-service** (8081): API Gateway with FFmpeg conversion
- **redis** (6379): Task queue and caching layer

### Microservices Commands
```bash
# Build and start all services (requires NVIDIA GPU)
docker-compose up --build

# Start specific services
docker-compose up video-service redis

# View service logs
docker-compose logs -f orchestrator-service

# Clean rebuild
docker-compose down && docker-compose up --build
```

### Service URLs
- **Main API**: http://localhost:8081/api/process-video
- **Video Service**: http://localhost:8080
- **ASR Service**: http://localhost:8082
- **Redis**: localhost:6379

### Multi-Platform Support

The project now supports multiple video platforms through the microservices architecture:

#### Telegram Bot Extensions
- **Path**: `telegram_bot/src/parsers/` and `telegram_bot/src/downloaders/`
- **Multi-platform bot**: `telegram_bot/src/multi_platform_bot_integration.py`
- **Platform adapters**: Bilibili, Douyin/TikTok support
- **Factory pattern**: `telegram_bot/src/downloaders/downloader_factory.py`

#### Running Multi-Platform Bot
```bash
cd telegram_bot
# Install multi-platform dependencies
pip install -r requirements_multi_platform.txt

# Run combined bot and worker
python run_all.py

# Run components separately  
python run_bot.py    # Bot only
python run_worker.py # Worker only
```

#### Platform-Specific Testing
```bash
cd telegram_bot
# Test specific platform integration
python test_callback_integration.py
python test_asr_fix.py
```

## Utility Scripts

### Queue Management
- **clear_queue.py**: Interactive Redis queue cleaner for Telegram bot tasks
- **Usage**: `python clear_queue.py` - provides menu to clear specific or all queues

### Testing Framework
The project uses comprehensive testing with pytest:
```bash
cd telegram_bot
python -m pytest                    # Run all tests
python -m pytest -v --cov=src      # Run with coverage report  
python -m pytest tests/test_utils.py -v # Run specific module
python -m pytest -m "not slow"     # Skip slow integration tests
```

Test configuration in `telegram_bot/pytest.ini` includes:
- Coverage reporting with HTML output
- Test markers for slow/integration tests
- Strict marker enforcement