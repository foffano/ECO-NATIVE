from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from backend.app.db.models import Asset, Listing, Product, Project, StoreProfile
from backend.app.db.store import store
from backend.app.services import mercadolivre as ml

CATEGORY = {
    "id": "MLB1234",
    "name": "Organizadores",
    "path_from_root": [{"id": "MLB1", "name": "Casa"}, {"id": "MLB1234", "name": "Organizadores"}],
    "settings": {"listing_allowed": True, "status": "enabled", "max_title_length": 60},
}
ATTRIBUTES = [
    {"id": "BRAND", "name": "Marca", "tags": {"required": True}, "value_type": "string"},
    {"id": "MODEL", "name": "Modelo", "tags": {"required": True}, "value_type": "string"},
    {"id": "MATERIAL", "name": "Material", "tags": {}, "value_type": "list", "values": [{"id": "10", "name": "Plástico"}]},
    {"id": "COLOR", "name": "Cor", "tags": {"allow_variations": True}, "value_type": "list"},
    {"id": "GTIN", "name": "Código universal", "tags": {"conditional_required": True}},
    {"id": "EMPTY_GTIN_REASON", "name": "Motivo GTIN vazio", "tags": {}, "values": [{"id": "17055160", "name": "O produto não tem código cadastrado"}]},
    {"id": "SELLER_PACKAGE_WEIGHT", "name": "Peso da embalagem", "tags": {}, "value_type": "number_unit"},
    {"id": "INTERNAL", "name": "Interno", "tags": {"read_only": True}},
]


class FakeMercadoLivre:
    def __init__(self, user_product_seller=True):
        self.calls = []
        self.tags = ["normal", "user_product_seller"] if user_product_seller else ["normal"]
        self.created = 0

    def call(self, method, path, *, token=None, headers=None, **kwargs):
        self.calls.append((method, path, kwargs.get("json")))
        if path == "/users/me":
            return {"id": 99, "nickname": "LOJA3D", "tags": self.tags}
        if path.endswith("/domain_discovery/search"):
            return [{"category_id": "MLB1234", "category_name": "Organizadores", "domain_name": "Organizadores",
                     "attributes": [{"id": "BRAND", "value_name": "Sugerida"}]}]
        if path == "/categories/MLB1234":
            return CATEGORY
        if path == "/categories/MLB1234/attributes":
            return ATTRIBUTES
        if path == "/items/validate":
            return None
        if path == "/items":
            self.created += 1
            return {"id": f"MLB90{self.created}", "permalink": f"https://ml/{self.created}", "status": "active"}
        if path.endswith("/description"):
            return {}
        raise AssertionError(f"unexpected call {method} {path}")


def token_response(form):
    return {"access_token": "APP_USR-token", "refresh_token": "TG-refresh", "expires_in": 21600, "user_id": 99}


def setup_product():
    shop = store.upsert_store_profile(StoreProfile(name="Eco Loja"))
    project = store.upsert_project(Project(name="P", store_profile_id=shop.id))
    product = store.upsert_product(Product(
        project_id=project.id,
        name="Organizador de mesa",
        listing=Listing(title="Organizador de Mesa Modular", description="Descrição", category="Casa > Organização",
                        price="39,90", stock=5, weight="0.12", parcel_size="L:20 W:10 H:8"),
        assets=[Asset(product_id="x", kind="cover_image", path="/tmp/cover.jpg"),
                Asset(product_id="x", kind="color_PLA_Blue", path="/tmp/blue.jpg"),
                Asset(product_id="x", kind="color_PLA_Red", path="/tmp/red.jpg")],
        metadata={"sku": "ECO-001"},
    ))
    return shop, product


def client_for(shop):
    from backend.app.main import app
    from backend.app.services.auth import AuthenticatedStore, create_initial_users, create_session
    create_initial_users(("admin", "password123"), [("shop", "password123", shop.id)])
    client = TestClient(app)
    client.cookies.set("eco_native_session", create_session(AuthenticatedStore(shop.id, "shop")))
    return client


def test_oauth_draft_and_publish_one_item_per_color(monkeypatch):
    monkeypatch.setenv("MERCADOLIVRE_APP_ID", "123")
    monkeypatch.setenv("MERCADOLIVRE_CLIENT_SECRET", "secret")
    shop, product = setup_product()
    fake = FakeMercadoLivre()
    client = client_for(shop)
    with patch.object(ml, "_call", side_effect=fake.call), patch.object(ml, "_oauth_token", side_effect=token_response), \
         patch("backend.app.api.routes_mercadolivre.r2_configured", return_value=True), \
         patch("backend.app.api.routes_mercadolivre.gallery_image_urls", return_value=["https://cdn/cover.jpg"]), \
         patch("backend.app.api.routes_mercadolivre.color_image_map",
               return_value={"PLA_Blue": "https://cdn/blue.jpg", "PLA_Red": "https://cdn/red.jpg"}):
        connect = client.post("/api/integrations/mercado-livre/connect", headers={"host": "eco.example.com", "x-forwarded-proto": "https"})
        query = parse_qs(urlparse(connect.json()["url"]).query)
        assert query["redirect_uri"] == ["https://eco.example.com/api/auth/mercado-livre/callback"]
        # Callback arrives without the session cookie (cross-site redirect).
        callback = TestClient(client.app).get(f"/api/auth/mercado-livre/callback?code=TG-code&state={query['state'][0]}", follow_redirects=False)
        assert callback.headers["location"] == "/?mercadolivre=connected"
        assert client.get("/api/integrations/mercado-livre/status").json()["nickname"] == "LOJA3D"

        draft = client.get(f"/api/integrations/mercado-livre/products/{product.id}/draft").json()
        assert draft["category"]["path"] == "Casa > Organizadores"
        assert {a["id"] for a in draft["category"]["attributes"]} == {"BRAND", "MODEL", "MATERIAL", "EMPTY_GTIN_REASON", "SELLER_PACKAGE_WEIGHT"}
        assert draft["values"]["BRAND"] == "Sugerida"
        assert draft["values"]["MATERIAL"] == "Plástico"
        assert draft["values"]["SELLER_PACKAGE_WEIGHT"] == "120 g"
        assert draft["missing_required"] == []
        assert draft["colors"] == ["Azul", "Vermelho"]

        response = client.post(f"/api/integrations/mercado-livre/products/{product.id}/publish", json={
            "category_id": "MLB1234", "family_name": draft["family_name"], "price": "39,90", "quantity": 5,
            "attributes": draft["values"],
        })
        assert response.status_code == 200, response.text
        assert [item["color"] for item in response.json()["items"]] == ["Azul", "Vermelho"]

    posts = [(path, body) for method, path, body in fake.calls if method == "POST"]
    assert [path for path, _ in posts][:2] == ["/items/validate", "/items/validate"]
    item_body = next(body for path, body in posts if path == "/items")
    assert item_body["family_name"] == "Organizador de Mesa Modular" and "title" not in item_body
    assert item_body["price"] == 39.9
    assert {"id": "COLOR", "value_name": "Azul"} in item_body["attributes"]
    assert {"id": "MATERIAL", "value_id": "10"} in item_body["attributes"]
    assert item_body["pictures"][0] == {"source": "https://cdn/blue.jpg"}

    saved = next(p for p in store.load().products if p.id == product.id)
    assert saved.metadata["listed"] is True
    assert len(saved.metadata["mercado_livre"]["items"]) == 2
    assert ml.remembered_category(shop.id, "casa  > organização")["category_id"] == "MLB1234"

    with patch.object(ml, "_call", side_effect=fake.call):
        again = client.post(f"/api/integrations/mercado-livre/products/{product.id}/publish", json={
            "category_id": "MLB1234", "family_name": "x", "price": "10", "attributes": {}})
    assert again.status_code == 409


def test_other_store_cannot_publish_product():
    shop, product = setup_product()
    other = store.upsert_store_profile(StoreProfile(name="Outra"))
    client = client_for(shop)
    from backend.app.services.auth import AuthenticatedStore, create_session, create_user
    create_user("other", "password123", other.id)
    client.cookies.set("eco_native_session", create_session(AuthenticatedStore(other.id, "other")))
    assert client.get(f"/api/integrations/mercado-livre/products/{product.id}/draft").status_code == 404


def test_legacy_seller_uses_title_and_variations():
    fake = FakeMercadoLivre(user_product_seller=False)
    with patch.object(ml, "_call", side_effect=fake.call):
        details = ml.category_details("t", "MLB1234")
    items = ml.build_items(
        details=details, values={"BRAND": "Eco", "GTIN": "", "EMPTY_GTIN_REASON": "O produto não tem código cadastrado"},
        name="Organizador", price=10.0, quantity=3, listing_type_id="gold_special", warranty_time="90 dias",
        gallery=["https://cdn/a.jpg"], sku="ECO-1",
        variants=[{"color": "Azul", "image": "https://cdn/b.jpg", "sku": "ECO-1-AZ"}], user_product_seller=False,
    )
    assert len(items) == 1
    assert items[0]["title"] == "Organizador"
    assert items[0]["variations"][0]["attribute_combinations"] == [{"id": "COLOR", "value_name": "Azul"}]
    assert items[0]["variations"][0]["picture_ids"] == ["https://cdn/b.jpg"]
    assert {"id": "EMPTY_GTIN_REASON", "value_id": "17055160"} in items[0]["attributes"]


def test_missing_required_and_parsers():
    fake = FakeMercadoLivre()
    with patch.object(ml, "_call", side_effect=fake.call):
        details = ml.category_details("t", "MLB1234")
    assert ml.missing_required(details, {"BRAND": "Eco"}) == ["Modelo"]
    assert ml.parse_price("R$ 1.234,50") == 1234.5
    assert ml.parse_price("39.90") == 39.9
    assert ml.parse_price("") is None
    assert ml.parse_parcel("20x10x8") == {"length": 20.0, "width": 10.0, "height": 8.0}
