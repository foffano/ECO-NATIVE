"""Image models the app knows how to call on Kie.ai.

Every model gets the same request from the app (a prompt and one source image URL), but each
names and validates its inputs differently, so each one maps that request to its own payload.
Adding a model means adding an entry here after checking its page in the Kie.ai docs.
"""
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class ImageModel:
    id: str
    label: str
    description: str
    cost_usd: float  # Estimated price per generated image, shown in the cost dashboard.
    max_prompt_chars: int
    build_input: Callable[[str, str], dict]


def _qwen_image_edit_input(prompt: str, image_url: str) -> dict:
    # https://docs.kie.ai/market/qwen/image-edit
    return {
        "prompt": prompt,
        "image_url": image_url,
        "acceleration": "none",
        "image_size": "square",
        "num_inference_steps": 25,
        "guidance_scale": 4,
        "sync_mode": False,
        "enable_safety_checker": True,
        "output_format": "png",
        "negative_prompt": "blurry, ugly",
    }


def _nano_banana_edit_input(prompt: str, image_url: str) -> dict:
    # https://docs.kie.ai/market/google/nano-banana-edit
    return {
        "prompt": prompt,
        "image_urls": [image_url],
        "aspect_ratio": "1:1",
        "output_format": "png",
    }


DEFAULT_IMAGE_MODEL = "qwen/image-edit"
IMAGE_MODELS = {
    model.id: model
    for model in (
        ImageModel(
            id="qwen/image-edit",
            label="Qwen Image Edit",
            description="Padrão do app e mais barato. Imagem quadrada de 1024 × 1024 px.",
            cost_usd=0.01,
            max_prompt_chars=2000,
            build_input=_qwen_image_edit_input,
        ),
        ImageModel(
            id="google/nano-banana-edit",
            label="Google Nano Banana Edit",
            description="Modelo Gemini do Google. Imagem quadrada de 1024 × 1024 px.",
            cost_usd=0.02,
            max_prompt_chars=5000,
            build_input=_nano_banana_edit_input,
        ),
    )
}


def get_image_model(model_id: str | None) -> ImageModel:
    model = IMAGE_MODELS.get(model_id or DEFAULT_IMAGE_MODEL)
    if model is None:
        raise ValueError(
            f"O modelo de imagem '{model_id}' não é suportado. Escolha um modelo em Ajustes → Integrações."
        )
    return model


def image_model_options() -> list[dict]:
    return [
        {"id": model.id, "label": model.label, "description": model.description, "cost_usd": model.cost_usd}
        for model in IMAGE_MODELS.values()
    ]
