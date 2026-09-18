from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.db.models import Asset, Product
from backend.app.services import image_generation
from backend.app.services.image_versions import PREVIOUS_VERSIONS_DIR, replace_with_new_version


def product_with_image(tmp_path: Path, kind: str = "generated_studio_classic") -> tuple[Product, Path]:
    current = tmp_path / "SKU_capa_produto_studio_classic.png"
    current.write_bytes(b"old")
    product = Product(project_id="p", name="x")
    product.assets.append(Asset(product_id=product.id, kind=kind, path=str(current), public_url="https://r2/old.png"))
    return product, current


def test_new_version_keeps_the_previous_image(tmp_path):
    product, current = product_with_image(tmp_path)
    replace_with_new_version(product, "generated_studio_classic", current, lambda path: path.write_bytes(b"new"))

    assert current.read_bytes() == b"new"
    [previous] = product.assets
    assert previous.kind == "previous_generated_studio_classic"
    assert previous.public_url is None
    assert Path(previous.path).parent.name == PREVIOUS_VERSIONS_DIR
    assert Path(previous.path).read_bytes() == b"old"
    assert not list(tmp_path.glob(".novo_*"))


def test_failed_render_keeps_the_current_image(tmp_path):
    product, current = product_with_image(tmp_path)

    def fail(path: Path) -> None:
        path.write_bytes(b"partial")
        raise RuntimeError("Kie.ai falhou")

    with pytest.raises(RuntimeError):
        replace_with_new_version(product, "generated_studio_classic", current, fail)
    assert current.read_bytes() == b"old"
    assert [asset.kind for asset in product.assets] == ["generated_studio_classic"]
    assert not list(tmp_path.glob(".novo_*"))


def test_stray_files_are_kept_and_dangling_assets_dropped(tmp_path):
    product = Product(project_id="p", name="x")
    product.assets.append(Asset(product_id=product.id, kind="color_azul", path=str(tmp_path / "gone.png")))
    current = tmp_path / "SKU_cor_azul.png"
    current.write_bytes(b"stray")

    replace_with_new_version(product, "color_azul", current, lambda path: path.write_bytes(b"new"))

    [previous] = product.assets
    assert previous.kind == "previous_color_azul"
    assert Path(previous.path).read_bytes() == b"stray"


def test_regenerate_makes_new_versions_and_resume_reuses(tmp_path, monkeypatch):
    product = Product(project_id="p", name="x", metadata={"sku": "SKU-1"})
    cover = Asset(product_id=product.id, kind="cover_image", path=str(tmp_path / "capa.jpg"))
    product.assets.append(cover)
    rendered = []

    def fake_render(product, source_ref, prompt, output_path, **kwargs):
        rendered.append(prompt)
        output_path.write_bytes(f"version {len(rendered)}".encode())

    monkeypatch.setattr(image_generation, "get_settings", lambda: SimpleNamespace(use_codex_image_gen=False, kie_api_key="key", kie_image_model=None))
    monkeypatch.setattr(image_generation, "ensure_product_cover", lambda product: cover)
    monkeypatch.setattr(image_generation, "resolve_source_ref", lambda product, asset, settings: "https://r2/capa.jpg")
    monkeypatch.setattr(image_generation, "render_image_edit", fake_render)
    monkeypatch.setattr(image_generation, "upload_file_to_r2", lambda path, prefix, force=False: f"https://r2/{Path(path).name}")
    prompts = {"studio_classic": "classic"}

    [first] = image_generation.generate_studio_images(product, image_prompts=prompts)
    product.assets.append(first)
    [resumed] = image_generation.generate_studio_images(product, image_prompts=prompts)
    assert len(rendered) == 1  # An existing image is reused without regenerate.
    assert resumed.path == first.path

    [second] = image_generation.generate_studio_images(product, image_prompts=prompts, regenerate=True)
    product.assets.append(second)
    assert len(rendered) == 2
    assert Path(second.path).read_bytes() == b"version 2"
    assert second.id != first.id
    kinds = sorted(asset.kind for asset in product.assets)
    assert kinds == ["cover_image", "generated_studio_classic", "previous_generated_studio_classic"]
    previous = next(asset for asset in product.assets if asset.kind.startswith("previous_"))
    assert Path(previous.path).read_bytes() == b"version 1"
