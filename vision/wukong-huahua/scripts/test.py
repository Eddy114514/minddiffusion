python txt2img.py --prompt dog --ckpt_path /root/wukong/minddiffusion/vision/wukong-huahua/models --ckpt_name wukong-huahua-ms.ckpt --H 512 --W 512 --output_path /root/wukong/minddiffusion/vision/wukong-huahua/samples --n_samples 1

python txt2img.py --prompt dog --ckpt_path /root/wukong/minddiffusion/vision/stablediffusionv2/models --ckpt_name stablediffusionv2_512.ckpt --H 512 --W 512 --output_path /root/wukong/minddiffusion/vision/stablediffusionv2/samples --n_samples 1



conda config--set show channel urls yesconda config
--add channels https://mirrors.tuna.tsinghuaedu.cn/anaconda/pkgs/free

pip install https://ms-release.obs.cn-north-4.myhuaweicloud.com/1.9.0/MindSpore/unified/aarch64/mindspore-1.9.0-cp39-cp39-linux_aarch64.whl --trusted-host ms-release.obs.cn-north-4.myhuaweicloud.com -i https://pypi.tuna.tsinghua.edu.cn/simple

conda install mindspore=1.9.0 -c mindspore -c conda-forge

