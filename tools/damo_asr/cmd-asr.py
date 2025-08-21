# -*- coding:utf-8 -*-

import sys, os, traceback

import torch

from funasr import AutoModel

dir = sys.argv[1]
if dir[-1] == "/":
    dir = dir[:-1]
# opt_name=dir.split("\\")[-1].split("/")[-1]
opt_name = os.path.basename(dir)

path_asr    = 'tools/damo_asr/models/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch'
path_vad    = 'tools/damo_asr/models/speech_fsmn_vad_zh-cn-16k-common-pytorch'
path_punc   = 'tools/damo_asr/models/punc_ct-transformer_zh-cn-common-vocab272727-pytorch'
path_asr    = path_asr if os.path.exists(path_asr)else "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
path_vad    = path_vad if os.path.exists(path_vad)else "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
path_punc   = path_punc if os.path.exists(path_punc)else "iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch"

model = AutoModel(model=path_asr, model_revision="v2.0.4",
                  vad_model=path_vad,
                  vad_model_revision="v2.0.4",
                  punc_model=path_punc,
                  punc_model_revision="v2.0.4",
                  )

opt_dir = "output/asr_opt"
os.makedirs(opt_dir, exist_ok=True)

file_names = os.listdir(dir)
file_names.sort()
for file_name in file_names: 
    # file_name is like audio.mp3
    name, extension = os.path.splitext(os.path.basename(file_name))
    try:
        output_path = f"{opt_dir}/{name}.txt"
        if not os.path.exists(output_path):
            text = model.generate(input=f"{dir}/{file_name}")[0]["text"]
            print(text)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)
    except:
        print(traceback.format_exc())



