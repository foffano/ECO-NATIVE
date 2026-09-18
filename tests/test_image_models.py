from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.db.models import Product
from backend.app.services import image_generation
from backend.app.services.cost_tracker import add_kie_image_cost, kie_image_cost_usd
from backend.app.services.image_models import get_image_model


@pytest.fixture
def kie_requests(monkeypatch):
    sent = []

    def fake_request(method, url, headers=None, json=None, timeout=None):
        sent.append(json)
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(image_generation, "http_request", fake_request)
    monkeypatch.setattr(image_generation, "read_response_json", lambda response: {"code": 200, "data": {"taskId": "task-1"}})
    return sent


def test_each_model_gets_its_own_request_format(kie_requests):
    url = "https://pub-example.r2.dev/capa.jpg"
    assert image_generation.create_kie_task("prompt", url, "key", "qwen/image-edit") == "task-1"
    image_generation.create_kie_task("prompt", url, "key", "google/nano-banana-edit")

    qwen, nano = kie_requests
    assert qwen["model"] == "qwen/image-edit"
    assert qwen["input"]["image_url"] == url
    assert qwen["input"]["image_size"] == "square"
    assert nano == {
        "model": "google/nano-banana-edit",
        "input": {"prompt": "prompt", "image_urls": [url], "aspect_ratio": "1:1", "output_format": "png"},
    }


def test_unsupported_model_or_long_prompt_fails_before_calling_kie(kie_requests):
    with pytest.raises(ValueError, match="não é suportado"):
        image_generation.create_kie_task("prompt", "https://x/y.jpg", "key", "google/nano-banana-pro")
    with pytest.raises(RuntimeError, match="limite do Qwen Image Edit é 2000"):
        image_generation.create_kie_task("x" * 2001, "https://x/y.jpg", "key", "qwen/image-edit")
    assert kie_requests == []
    assert get_image_model(None).id == "qwen/image-edit"


def test_image_cost_follows_the_model(monkeypatch):
    monkeypatch.delenv("KIE_IMAGE_COST_USD", raising=False)
    assert kie_image_cost_usd("qwen/image-edit") == 0.01
    assert kie_image_cost_usd("google/nano-banana-edit") == 0.02
    event = add_kie_image_cost(Product(project_id="p", name="x"), "Imagem base", model="google/nano-banana-edit")
    assert (event["cost_usd"], event["metadata"]["credits_per_image"]) == (0.02, 4)
    monkeypatch.setenv("KIE_IMAGE_COST_USD", "0.05")
    assert kie_image_cost_usd("google/nano-banana-edit") == 0.05


def test_settings_only_accept_models_the_app_can_call(monkeypatch):
    from backend.app.core.settings import ENV_PATH
    from backend.app.main import app
    from backend.app.services.auth import AuthenticatedStore, create_initial_users, create_session

    monkeypatch.setenv("KIE_IMAGE_MODEL", "qwen/image-edit")
    create_initial_users(("admin", "password123"), [])
    try:
        with TestClient(app) as client:
            client.cookies.set("eco_native_session", create_session(AuthenticatedStore(None, "admin", is_admin=True)))
            assert client.patch("/api/settings", json={"kie_image_model": "google/nano-banana-pro"}).status_code == 422
            response = client.patch("/api/settings", json={"kie_image_model": "google/nano-banana-edit"})
            assert response.status_code == 200
            integrations = response.json()["integrations"]
            assert integrations["kie_image_model"] == "google/nano-banana-edit"
            assert [model["id"] for model in integrations["image_models"]] == ["qwen/image-edit", "google/nano-banana-edit"]
    finally:
        ENV_PATH.unlink(missing_ok=True)


def test_generated_jpeg_is_stored_as_png(tmp_path):
    from PIL import Image

    generated = tmp_path / "SKU_capa_produto_studio_classic.png"
    Image.new("RGB", (8, 8), "red").save(generated, format="JPEG")
    image_generation.save_as_png(generated)
    with Image.open(generated) as image:
        assert image.format == "PNG"
    before = generated.read_bytes()
    image_generation.save_as_png(generated)
    assert generated.read_bytes() == before
