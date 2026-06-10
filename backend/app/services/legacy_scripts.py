from pathlib import Path

LEGACY_EXAMPLES_DIR = Path(r"G:\Meu Drive\LUMA STORE\AGENT-ECO\EXEMPLOS")

SCRIPT_MAP = {
    "curator": "ai_analyzer.py",
    "makerworld_scraper": "scraper.py",
    "cli_flow": "main.py",
    "shopee_listing": "shopee_analyzer.py",
    "image_generation": "image_generator.py",
    "color_variations": "generate_color_variations.py",
    "shopee_export": "shopee_batch_export.py",
}


def legacy_script_status() -> dict[str, bool]:
    return {
        name: (LEGACY_EXAMPLES_DIR / filename).exists()
        for name, filename in SCRIPT_MAP.items()
    }
