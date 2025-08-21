import time
import os
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from convert import process_media_to_text, validate_input_file

def wait_for_complete(path, interval=2, checks=3):
    """等待文件写入完成"""
    last_size = -1
    stable_count = 0
    while stable_count < checks:
        try:
            size = os.path.getsize(path)
        except FileNotFoundError:
            time.sleep(interval)
            continue

        if size == last_size:
            stable_count += 1
        else:
            stable_count = 0
            last_size = size
        time.sleep(interval)
    return True


class FileHandler(FileSystemEventHandler):
    def __init__(self, process_func, ignore_patterns=None, only_patterns=None):
        super().__init__()
        self.process_func = process_func
        self.ignore_patterns = [re.compile(p) for p in (ignore_patterns or [])]
        self.only_patterns = [re.compile(p) for p in (only_patterns or [])]

    def should_ignore(self, filename):
        for pattern in self.ignore_patterns:
            if pattern.match(filename):
                return True
        return False

    def handle_file(self, filepath):
        """统一的文件处理入口"""
        filename = os.path.basename(filepath)

        if self.should_ignore(filename):
            print(f"[Watcher] 忽略文件: {filepath}")
            return

        print(f"[Watcher] 检测到文件: {filepath}")
        self.process_func(filepath)

    def on_created(self, event):
        if event.is_directory:
            return
        self.handle_file(event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        # event.dest_path 才是新文件路径
        self.handle_file(event.dest_path)


def process_file(filepath):
    """处理逻辑 (这里示例用打印代替)"""
    print(f"[Processor] 开始处理: {filepath}")
    # 这里可以替换成流程1 / 流程2 的逻辑
    # 比如: asr_processor.process(filepath) 或 decrypt_processor.process(filepath)
    try:
        # 验证输入文件
        validate_input_file(filepath)
        
        # 处理音视频文件
        txt_path = process_media_to_text(filepath)
        print(f"处理完成！文本文件已保存到: {txt_path}")
        
    except FileNotFoundError as e:
        print(f"错误: {e}")
    except ValueError as e:
        print(f"错误: {e}")
    except RuntimeError as e:
        print(f"处理失败: {e}")
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")


def start_watcher(folder, ignore_patterns=None, only_patterns=None):
    event_handler = FileHandler(process_file, ignore_patterns=ignore_patterns, only_patterns=only_patterns)
    observer = Observer()
    observer.schedule(event_handler, folder, recursive=False)
    observer.start()
    print(f"[Watcher] 正在监控文件夹: {folder}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    watch_folder = "./download"

    # 配置忽略规则 (正则表达式列表)
    ignore_patterns = [
        r".*\.txt$",   # 忽略 *.txt
        r"^audio.*\.m4a$",   # 忽略 audio*.m4a
        r".*\.part$",        # 忽略 *.part
        r".*\.tmp$",         # 忽略 *.tmp
    ]

    # 白名单规则（only_patterns）
    only_patterns = [
        r".*\.aac$",
        r".*\.avi$",
        r".*\.flac$",
        r".*\.flv$",
        r".*\.m4a$",
        r".*\.m4v$",
        r".*\.mkv$",
        r".*\.mov$",
        r".*\.mp3$",
        r".*\.mp4$",
        r".*\.ogg$",
        r".*\.wav$",
        r".*\.webm$",
        r".*\.wma$",
        r".*\.wmv$",
    ]

    start_watcher(watch_folder, ignore_patterns=ignore_patterns, only_patterns=only_patterns)
