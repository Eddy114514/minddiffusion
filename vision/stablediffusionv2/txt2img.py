# Copyright 2022 Huawei Technologies Co., Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================

import os
import time
import sys
import argparse
from PIL import Image
from omegaconf import OmegaConf

import numpy as np
import mindspore as ms

workspace = os.path.dirname(os.path.abspath(__file__))
print("workspace", workspace, flush=True)
sys.path.append(workspace)
from ldm.util import instantiate_from_config
from ldm.models.diffusion.plms import PLMSSampler
from ldm.models.diffusion.dpm_solver import DPMSolverSampler


def seed_everything(seed):
    if seed:
        ms.set_seed(seed)
        np.random.seed(seed)


def numpy_to_pil(images):
    """
    Convert a numpy image or a batch of images to a PIL image.
    """
    if images.ndim == 3:
        images = images[None, ...]
    images = (images * 255).round().astype("uint8")
    pil_images = [Image.fromarray(image) for image in images]

    return pil_images


def load_model_from_config(config, ckpt, verbose=False):
    print(f"Loading model from {ckpt}")
    model = instantiate_from_config(config.model)
    if os.path.exists(ckpt):
        param_dict = ms.load_checkpoint(ckpt)
        if param_dict:
            param_not_load = ms.load_param_into_net(model, param_dict)
            print("param not load:", param_not_load)
    else:
        print(f"!!!Warning!!!: {ckpt} doesn't exist")

    return model


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--data_path",
        type=str,
        nargs="?",
        default="",
        help="the prompt to render"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        nargs="?",
        default="A Van Gogh style oil painting of sunflower",
        help="the prompt to render"
    )
    parser.add_argument(
        "--output_path",
        type=str,
        nargs="?",
        default="output",
        help="dir to write results to"
    )
    parser.add_argument(
        "--skip_grid",
        action='store_true',
        help="do not save a grid, only individual samples. Helpful when evaluating lots of samples",
    )
    parser.add_argument(
        "--skip_save",
        action='store_true',
        help="do not save individual samples. For speed measurements.",
    )
    parser.add_argument(
        "--ddim_steps",
        type=int,
        default=50,
        help="number of ddim sampling steps",
    )
    parser.add_argument(
        "--fixed_code",
        action='store_true',
        help="if enabled, uses the same starting code across samples ",
    )
    parser.add_argument(
        "--ddim_eta",
        type=float,
        default=0.0,
        help="ddim eta (eta=0.0 corresponds to deterministic sampling",
    )
    parser.add_argument(
        "--n_iter",
        type=int,
        default=2,
        help="sample this often",
    )
    parser.add_argument(
        "--H",
        type=int,
        default=512,
        help="image height, in pixel space",
    )
    parser.add_argument(
        "--W",
        type=int,
        default=512,
        help="image width, in pixel space",
    )
    parser.add_argument(
        "--n_samples",
        type=int,
        default=8,
        help="how many samples to produce for each given prompt. A.k.a. batch size",
    )
    parser.add_argument(
        "--dpm_solver",
        action='store_true',
        help="use dpm_solver sampling",
    )
    parser.add_argument(
        "--n_rows",
        type=int,
        default=0,
        help="rows in the grid (default: n_samples)",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=9.0,
        help="unconditional guidance scale: eps = eps(x, empty) + scale * (eps(x, cond) - eps(x, empty))",
    )
    parser.add_argument(
        "--from-file",
        type=str,
        help="if specified, load prompts from this file",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/v2-inference.yaml",
        help="path to config which constructs model",
    )
    parser.add_argument(
        "--ckpt_path",
        type=str,
        default="models",
        help="path to checkpoint of model",
    )
    parser.add_argument(
        "--ckpt_name",
        type=str,
        default="stablediffusionv2_512.ckpt",
        help="path to checkpoint of model",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="the seed (for reproducible sampling)",
    )
    parser.add_argument(
        "--precision",
        type=str,
        help="evaluate at this precision",
        choices=["full", "autocast"],
        default="autocast"
    )
    opt = parser.parse_args()
    work_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"WORK DIR:{work_dir}")
    
    device_id = int(os.getenv("DEVICE_ID", 0))
    ms.context.set_context(
        mode=ms.context.GRAPH_MODE,
        device_target="Ascend",
        device_id=device_id,
        max_device_memory="15GB"
    )
    
    seed_everything(opt.seed)

    if not os.path.isabs(opt.config):
        opt.config = os.path.join(work_dir, opt.config)
    config = OmegaConf.load(f"{opt.config}")
    model = load_model_from_config(config, f"{os.path.join(opt.ckpt_path, opt.ckpt_name)}")

    if opt.dpm_solver:
        sampler = DPMSolverSampler(model)
    else:
        sampler = PLMSSampler(model)
    os.makedirs(opt.output_path, exist_ok=True)
    outpath = opt.output_path

    batch_size = opt.n_samples
    if not opt.data_path:
        prompt = opt.prompt
        assert prompt is not None
        data = [batch_size * [prompt]]
    else:
        opt.prompt = os.path.join(opt.data_path, opt.prompt)
        print(f"reading prompts from {opt.prompt}")
        with open(opt.prompt, "r") as f:
            data = f.read().splitlines()
            data = [batch_size * [prompt for prompt in data]]

    sample_path = os.path.join(outpath, "samples")
    os.makedirs(sample_path, exist_ok=True)
    base_count = len(os.listdir(sample_path))

    start_code = None
    if opt.fixed_code:
        stdnormal = ms.ops.StandardNormal()
        start_code = stdnormal((opt.n_samples, 4, opt.H // 8, opt.W // 8))

    all_samples = list()
    for prompts in data:
        for n in range(opt.n_iter):
            start_time = time.time()

            uc = None
            if opt.scale != 1.0:
                uc = model.get_learned_conditioning(batch_size * [""])
            if isinstance(prompts, tuple):
                prompts = list(prompts)
            c = model.get_learned_conditioning(prompts)

            shape = [4, opt.H // 8, opt.W // 8]
            samples_ddim, _ = sampler.sample(S=opt.ddim_steps,
                                            conditioning=c,
                                            batch_size=opt.n_samples,
                                            shape=shape,
                                            verbose=False,
                                            unconditional_guidance_scale=opt.scale,
                                            unconditional_conditioning=uc,
                                            eta=opt.ddim_eta,
                                            x_T=start_code
                                            )

            x_samples_ddim = model.decode_first_stage(samples_ddim)
            x_samples_ddim = ms.ops.clip_by_value((x_samples_ddim + 1.0) / 2.0,
                                                  clip_value_min=0.0, clip_value_max=1.0)
            x_samples_ddim_numpy = x_samples_ddim.asnumpy()

            if not opt.skip_save:
                for x_sample in x_samples_ddim_numpy:
                    x_sample = 255. * x_sample.transpose(1, 2, 0)
                    img = Image.fromarray(x_sample.astype(np.uint8))
                    img.save(os.path.join(sample_path, f"{base_count:05}.png"))
                    base_count += 1

            if not opt.skip_grid:
                all_samples.append(x_samples_ddim_numpy)

            end_time = time.time()
            print(f"the infer time of a batch is {end_time-start_time}")

        print(f"Your samples are ready and waiting for you here: \n{outpath} \n"
          f" \nEnjoy.")

if __name__ == "__main__":
    main()
