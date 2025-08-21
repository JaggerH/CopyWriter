import sys, os, traceback
import subprocess
from funasr import AutoModel

from tqdm import tqdm

def convert_to_mp3(input_file, output_file):
    try:
        # 使用subprocess.run并捕获输出
        result = subprocess.run(
            ['ffmpeg', '-i', input_file, '-vn', '-acodec', 'libmp3lame', '-q:a', '4', output_file],
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg 转换失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False
    except FileNotFoundError:
        print("错误: 未找到 FFmpeg，请确保已安装 FFmpeg 并添加到系统路径")
        return False
    except Exception as e:
        print(f"转换过程中发生未知错误: {e}")
        return False

def process_audio(input_file):
    path_asr    = 'tools/damo_asr/models/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch'
    path_vad    = 'tools/damo_asr/models/speech_fsmn_vad_zh-cn-16k-common-pytorch'
    path_punc   = 'tools/damo_asr/models/punc_ct-transformer_zh-cn-common-vocab272727-pytorch'

    model = AutoModel(model=path_asr, model_revision="v2.0.4",
                    vad_model=path_vad,
                    vad_model_revision="v2.0.4",
                    punc_model=path_punc,
                    punc_model_revision="v2.0.4",
                    )

    text = model.generate(input=input_file)[0]["text"]
    return text

def process_media_to_text(input_file):
    """
    将音视频文件转换为文本
    """
    # 支持的音视频格式
    VIDEO_FORMATS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
    AUDIO_FORMATS = {'.m4a', '.wav', '.flac', '.aac', '.ogg', '.wma', '.mp3'}
    ALL_SUPPORTED_FORMATS = VIDEO_FORMATS | AUDIO_FORMATS
    
    # 获取文件扩展名
    _, extension = os.path.splitext(input_file)
    extension_lower = extension.lower()
    
    # 检查文件格式是否支持
    if extension_lower not in ALL_SUPPORTED_FORMATS:
        raise ValueError(f"不支持的文件格式 '{extension}'，支持的格式: {', '.join(sorted(ALL_SUPPORTED_FORMATS))}")
    
    # 创建临时文件夹
    import tempfile
    temp_dir = tempfile.mkdtemp(prefix="convert_")
    mp3_path = None
    
    try:
        # 生成输出文件路径
        base_name = os.path.splitext(input_file)[0]
        txt_path = base_name + '.txt'
        
        # 处理视频文件 - 转换为MP3
        if extension_lower in VIDEO_FORMATS:
            temp_mp3_name = os.path.basename(base_name) + '.mp3'
            mp3_path = os.path.join(temp_dir, temp_mp3_name)
            print(f"正在将视频文件转换为MP3...")
            if not convert_to_mp3(input_file, mp3_path):
                raise RuntimeError("视频转MP3失败")
            print("视频转MP3完成")
        
        # 处理音频文件
        elif extension_lower in AUDIO_FORMATS:
            if extension_lower in ['.mp3', ".m4a"]:
                # MP3文件直接使用
                mp3_path = input_file
                print(f"{extension_lower[1:]}无需转换")
            else:
                # 其他音频格式转换为MP3
                temp_mp3_name = os.path.basename(base_name) + '.mp3'
                mp3_path = os.path.join(temp_dir, temp_mp3_name)
                print(f"正在将音频文件转换为MP3...")
                if not convert_to_mp3(input_file, mp3_path):
                    raise RuntimeError("音频转MP3失败")
                print("音频转MP3完成")
        
        # 进行语音识别
        print("正在进行语音识别...")
        text = process_audio(mp3_path)
        
        # 保存识别结果
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)
        
        print(f"语音识别完成，结果已保存到: {txt_path}")
        return txt_path
        
    finally:
        # 清理临时文件和文件夹
        if mp3_path and mp3_path != input_file and os.path.exists(mp3_path):
            os.remove(mp3_path)
        
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)

def validate_input_file(input_file):
    """
    验证输入文件
    """
    # 检查文件是否存在
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"文件 '{input_file}' 不存在")
    
    # 检查文件格式是否支持
    VIDEO_FORMATS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
    AUDIO_FORMATS = {'.m4a', '.wav', '.flac', '.aac', '.ogg', '.wma', '.mp3'}
    ALL_SUPPORTED_FORMATS = VIDEO_FORMATS | AUDIO_FORMATS
    
    _, extension = os.path.splitext(input_file)
    extension_lower = extension.lower()
    
    if extension_lower not in ALL_SUPPORTED_FORMATS:
        raise ValueError(f"不支持的文件格式 '{extension}'，支持的格式: {', '.join(sorted(ALL_SUPPORTED_FORMATS))}")

def main():
    # 检查命令行参数
    if len(sys.argv) != 2:
        print("用法: python convert.py <输入文件>")
        print("支持的格式: .mp4, .avi, .mov, .mkv, .wmv, .flv, .webm, .m4v, .m4a, .wav, .flac, .aac, .ogg, .wma, .mp3")
        return
    
    input_file = sys.argv[1]
    
    try:
        # 验证输入文件
        validate_input_file(input_file)
        
        # 处理音视频文件
        txt_path = process_media_to_text(input_file)
        print(f"处理完成！文本文件已保存到: {txt_path}")
        
    except FileNotFoundError as e:
        print(f"错误: {e}")
    except ValueError as e:
        print(f"错误: {e}")
    except RuntimeError as e:
        print(f"处理失败: {e}")
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        print(f"详细错误信息: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
