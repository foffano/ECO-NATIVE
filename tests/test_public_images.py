from fastapi.testclient import TestClient

from backend.app.core.paths import PROJECTS_DIR
from backend.app.db.models import Asset, Product
from backend.app.db.store import store
from backend.app.services import public_images


def image_file(name="ECO-001_capa_produto.jpg"):
    path = PROJECTS_DIR / "project" / "ECO-001" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xd8jpeg")
    return path


def test_public_link_serves_only_that_image_without_login(monkeypatch):
    from backend.app.main import app
    monkeypatch.setenv("PUBLIC_APP_URL", "https://eco.example.com/")
    path = image_file()
    url = public_images.public_image_url(path)
    assert url.startswith("https://eco.example.com/i/") and url.endswith("/project/ECO-001/ECO-001_capa_produto.jpg")

    client = TestClient(app)  # no session cookie
    link = url.removeprefix("https://eco.example.com")
    response = client.get(link)
    assert response.status_code == 200 and response.content == b"\xff\xd8jpeg"

    signature = link.split("/")[2]
    other = image_file("ECO-001_outra.jpg")
    assert client.get(f"/i/{signature}/project/ECO-001/{other.name}").status_code == 404  # signature is per file
    assert client.get(link.replace(signature, "x" * len(signature))).status_code == 404
    assert client.get(f"/i/{signature}/../.env").status_code == 404
    path.unlink()
    assert client.get(link).status_code == 404  # deleted image, dead link


def test_link_needs_the_public_address(monkeypatch):
    monkeypatch.setenv("PUBLIC_APP_URL", "")
    try:
        public_images.public_image_url(image_file())
    except public_images.PublicUrlMissing as exc:
        assert "endereço público" in str(exc)
    else:
        raise AssertionError("expected PublicUrlMissing")


def test_old_r2_links_are_forgotten():
    store.upsert_product(Product(
        project_id="p", name="x", metadata={"image_url": "https://makerworld.bblmw.com/capa.jpg"},
        assets=[
            Asset(product_id="x", kind="cover_image", path="/c.jpg", public_url="https://pub-1.r2.dev/c.jpg"),
            Asset(product_id="x", kind="generated_studio", path="/g.png", public_url="https://pub-1.r2.dev/g.png"),
        ],
    ))
    assert public_images.forget_r2_links() == 2
    cover, generated = store.load().products[0].assets
    assert cover.public_url == "https://makerworld.bblmw.com/capa.jpg"
    assert generated.public_url is None
    assert public_images.forget_r2_links() == 0
