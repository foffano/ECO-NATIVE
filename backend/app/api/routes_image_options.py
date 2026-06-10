from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.services.image_options import read_color_options, save_color_options
from backend.app.services.prompt_library import IMAGE_PROMPTS

router = APIRouter()


class ColorOption(BaseModel):
    id: str
    description: str


class ImageOptionsUpdate(BaseModel):
    colors: list[ColorOption]


@router.get("")
def get_image_options() -> dict[str, list[dict[str, str]]]:
    return {
        "studio_prompts": [{"id": key, "name": key.replace("_", " ").title()} for key in IMAGE_PROMPTS.keys()],
        "colors": read_color_options(),
    }


@router.put("")
def update_image_options(payload: ImageOptionsUpdate) -> dict[str, list[dict[str, str]]]:
    colors = save_color_options([item.model_dump() for item in payload.colors])
    return {
        "studio_prompts": [{"id": key, "name": key.replace("_", " ").title()} for key in IMAGE_PROMPTS.keys()],
        "colors": colors,
    }
