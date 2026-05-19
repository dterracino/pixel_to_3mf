"""AI preprocessing step for pixel art images.

Uses Stable Diffusion XL img2img to transform pixel art into smooth flat-color
illustrations before the boundary-smoothing pipeline.  The generative step
turns stairstepped pixel art boundaries (sky bands, wood-grain lines, etc.)
into organic flowing shapes that a downstream vectoriser can trace cleanly.

Usage:
    python ai_preprocess.py samples/input/large/sf2_ryu_level.png
    python ai_preprocess.py samples/input/duckhunt-nes.png --strength 0.78 --seed 42
    python ai_preprocess.py image.png --strength 0.78 --steps 30 --output out.png

The default model (stablediffusionapi/flat-2d-animerge) is an SD 1.5 checkpoint trained
on flat-color cartoon art, so high denoising strengths naturally produce flat-color output.

Requirements:
    pip install -r requirements-gpu.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
from diffusers.pipelines.auto_pipeline import AutoPipelineForImage2Image
from diffusers.utils.pil_utils import make_image_grid
from PIL import Image
from PIL.Image import Resampling


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PROMPT = (
    "anime style, flat color, cel shading, bold clean shapes, "
    "sharp color boundaries, vibrant colors, 2D illustration"
)

NEGATIVE_PROMPT = (
    "photorealistic, 3d, gradients, shading, texture, noise, blur, "
    "pixel art, jagged edges, watercolor, sketch, lineart"
)

# SD 1.5 models work best at 512 native resolution.
# SDXL models work best at 1024.  Adjust this if switching to SDXL.
TARGET_LONG_EDGE = 512


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upscale_for_sdxl(img: Image.Image) -> Image.Image:
    """Scale image so the longer edge = TARGET_LONG_EDGE, using nearest-neighbour.

    Nearest-neighbour preserves the hard pixel boundaries so SDXL still
    receives clear colour information (no LANCZOS blurring across edges).
    Dimensions are rounded to the nearest multiple of 8 as required by SDXL.
    """
    w, h = img.size
    scale = TARGET_LONG_EDGE / max(w, h)
    new_w = round(w * scale / 8) * 8
    new_h = round(h * scale / 8) * 8
    return img.resize((new_w, new_h), Resampling.NEAREST)


def _load_pipeline(model_id: str) -> AutoPipelineForImage2Image:
    """Load img2img pipeline onto GPU in float16.

    Supports both SD 1.5 and SDXL checkpoints via AutoPipeline.  We don't
    request variant='fp16' because most SD 1.5 models don't publish a
    separate fp16 variant — torch_dtype=float16 handles the conversion.
    """
    print(f"Loading model: {model_id}")
    print("  (first run downloads model weights to ~/.cache/huggingface — subsequent runs are instant)")
    pipe = AutoPipelineForImage2Image.from_pretrained(
        model_id,
        torch_dtype=torch.float16,
    )
    pipe = pipe.to("cuda")
    return pipe


# ---------------------------------------------------------------------------
# Main transform
# ---------------------------------------------------------------------------

def ai_preprocess(
    input_path: str | Path,
    output_path: str | Path,
    *,
    model_id: str = "stablediffusionapi/flat-2d-animerge",
    strength: float = 0.78,
    guidance_scale: float = 10.0,
    num_inference_steps: int = 40,
    seed: int | None = None,
    save_comparison: bool = True,
) -> Image.Image:
    """Transform a pixel art image into a smooth flat-color illustration.

    Args:
        input_path: Source pixel art image (any size/format).
        output_path: Where to write the processed image.
        model_id: HuggingFace model repo to use.  Defaults to SDXL base.
        strength: Denoising strength (0–1).  Higher = more creative freedom.
            0.30–0.45: shapes fully preserved, model pushes style toward flat color
            0.50–0.65: shapes mostly preserved, organic edge smoothing
            0.75+:     heavy hallucination, composition may be lost
        guidance_scale: Classifier-free guidance scale.  10+ recommended to
            enforce flat-color prompt against SDXL's photorealism bias.
        num_inference_steps: Diffusion steps (more = higher quality, slower).
        seed: Random seed for reproducibility.  None = random each run.
        save_comparison: If True, also save a side-by-side comparison PNG.

    Returns:
        The processed PIL Image.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    print(f"Input:    {input_path.name}  ({Image.open(input_path).size})")

    src = Image.open(input_path).convert("RGB")
    upscaled = _upscale_for_sdxl(src)
    print(f"Upscaled: {upscaled.size}  (nearest-neighbour to SDXL resolution)")

    pipe = _load_pipeline(model_id)

    generator = torch.Generator(device="cuda")
    if seed is not None:
        generator.manual_seed(seed)
    else:
        seed = generator.seed()
    print(f"Seed: {seed}  (use --seed {seed} to reproduce this result)")

    print(f"Running img2img  strength={strength}  steps={num_inference_steps}  cfg={guidance_scale}")
    result = pipe(  # type: ignore[operator]
        prompt=PROMPT,
        negative_prompt=NEGATIVE_PROMPT,
        image=upscaled,
        strength=strength,
        guidance_scale=guidance_scale,
        num_inference_steps=num_inference_steps,
        generator=generator,
    ).images[0]

    # Downscale result back to the original image dimensions so it can be
    # fed into the existing pipeline (which works in pixel-art pixel units).
    result_original_size = result.resize(src.size, Resampling.LANCZOS)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result_original_size.save(output_path)
    print(f"Saved  → {output_path}")

    if save_comparison:
        cmp_path = output_path.with_stem(output_path.stem + "_comparison")
        comparison = make_image_grid([upscaled, result], rows=1, cols=2)
        comparison.save(cmp_path)
        print(f"Saved  → {cmp_path}  (upscaled input | AI output)")

    return result_original_size


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI pixel-art → flat-color illustration preprocessing",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input", help="Source image path")
    parser.add_argument("--output", help="Output path (default: <input>_ai.png)")
    parser.add_argument(
        "--model",
        default="stablediffusionapi/flat-2d-animerge",
        help="HuggingFace model repo ID (default: flat-2d-animerge, an SD 1.5 flat-color cartoon checkpoint)",
    )
    parser.add_argument(
        "--strength", type=float, default=0.35,
        help="Denoising strength (0.35=preserve layout, 0.50=organic smoothing, 0.75+=hallucination)",
    )
    parser.add_argument("--steps", type=int, default=40, help="Diffusion steps")
    parser.add_argument("--cfg", type=float, default=10.0, help="Classifier-free guidance scale (higher = follow prompt more strictly)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed (omit for random)")
    parser.add_argument(
        "--no-comparison", action="store_true",
        help="Skip saving the side-by-side comparison image",
    )

    args = parser.parse_args()

    if not torch.cuda.is_available():
        print("ERROR: CUDA is not available. Install the CUDA-enabled torch build:")
        print("  pip install -r requirements-gpu.txt")
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)

    output_path = Path(args.output) if args.output else input_path.with_stem(input_path.stem + "_ai")

    ai_preprocess(
        input_path,
        output_path,
        model_id=args.model,
        strength=args.strength,
        guidance_scale=args.cfg,
        num_inference_steps=args.steps,
        seed=args.seed,
        save_comparison=not args.no_comparison,
    )


if __name__ == "__main__":
    main()
