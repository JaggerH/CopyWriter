# 安装
## 创建 Conda 环境
```
conda create -n copywriter python=3.11
conda activate copywriter

# index-url中的版本根据`nvidia-smi`运行后的结果自行判断
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu129
pip install -r requirement.txt
pip install -r Bili23-Downloader/requirements.txt
```

## 运行脚本示例

### 手动转换单个文件
```
python convert.py C:\Users\Jagger\Downloads\cc256f5c69796d125ea0109e07e5b1c9.mp4
```
