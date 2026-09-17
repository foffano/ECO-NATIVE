import json
from zipfile import ZipFile

import pytest

from backend import maintenance


def test_windows_paths_are_remapped_without_touching_urls(tmp_path):
    old = r"C:\Users\User\AppData\Roaming\eco-native-studio"
    value = {"assets": [{"path": old + r"\projects\abc\capa.png"}], "url": "https://example.com/image.png"}
    result = maintenance.remap_paths(value, old, tmp_path)
    assert result["assets"][0]["path"] == str(tmp_path / "projects/abc/capa.png")
    assert result["url"] == value["url"]


def test_operational_backup_roundtrip(tmp_path, monkeypatch):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    monkeypatch.setattr(maintenance, "DATA_DIR", source)
    monkeypatch.setattr(maintenance, "DB_PATH", source / "studio.json")
    monkeypatch.setattr(maintenance, "ENV_PATH", source / ".env")
    (source / "studio.json").write_text(json.dumps({"file": str(source / "projects/a.png")}))
    (source / ".maintenance").touch()
    for name in ("auth.json", ".session-secret", ".env", "browser_data/makerworld/a/Preferences", "projects/a.png"):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("preserved")
    archive = tmp_path / "backup.zip"
    maintenance.backup(archive)
    with ZipFile(archive) as zipfile:
        assert "data/.maintenance" not in zipfile.namelist()
    monkeypatch.setattr(maintenance, "DATA_DIR", target)
    monkeypatch.setattr(maintenance, "DB_PATH", target / "studio.json")
    maintenance.restore(archive)
    assert (target / "auth.json").read_text() == "preserved"
    assert (target / ".session-secret").read_text() == "preserved"
    assert (target / "browser_data/makerworld/a/Preferences").exists()
    assert json.loads((target / "studio.json").read_text())["file"] == str(target / "projects/a.png")
    with pytest.raises(ValueError, match="vazio"):
        maintenance.restore(archive)


def test_restore_rejects_traversal_before_extracting(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    monkeypatch.setattr(maintenance, "DATA_DIR", target)
    archive = tmp_path / "bad.zip"
    with ZipFile(archive, "w") as zipfile:
        zipfile.writestr("manifest.json", json.dumps({"kind": "eco-operational", "version": 1, "data_dir": "/old"}))
        zipfile.writestr("data/studio.json", "{}")
        zipfile.writestr("data/../../escape", "bad")
    with pytest.raises(ValueError):
        maintenance.restore(archive)
    assert not list(target.iterdir())


def test_legacy_full_backup_windows_asset_names(tmp_path, monkeypatch):
    from backend.app.services import store_backup
    from backend.app.db.models import StudioState, Product, Asset, StoreProfile
    projects, logos = tmp_path / "projects", tmp_path / "store_logos"
    file = projects / "p" / "SKU" / "cover.jpg"
    file.parent.mkdir(parents=True)
    file.touch()
    logos.mkdir()
    (logos / "logo.png").touch()
    monkeypatch.setattr(store_backup, "PROJECTS_DIR", projects)
    monkeypatch.setattr(store_backup, "STORE_LOGOS_DIR", logos)
    product = Product(project_id="p", name="P", metadata={"sku": "SKU"}, assets=[Asset(product_id="x", kind="cover_image", path=r"C:\old\projects\p\SKU\cover.jpg")])
    state = StudioState(products=[product], store_profiles=[StoreProfile(name="S", logo_path=r"C:\old\store_logos\logo.png")])
    store_backup.remap_restored_paths(state)
    assert state.products[0].assets[0].path == str(file)
    assert state.store_profiles[0].logo_path == str(logos / "logo.png")
