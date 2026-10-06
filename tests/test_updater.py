import importlib.util
from pathlib import Path

import pytest


_SPEC = importlib.util.spec_from_file_location("eco_native_updater", Path(__file__).parents[1] / "deploy/update.py")
updater = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader
_SPEC.loader.exec_module(updater)


def test_release_manifest_is_strict():
    manifest = {
        "schema": 3,
        "tag": "v1.2.3",
        "revision": "a" * 40,
        "image": "eco-native:v1.2.3",
        "architecture": "amd64",
        "asset": updater.ASSET,
        "sha256": "b" * 64,
    }
    assert updater.validate_manifest(manifest, "v1.2.3") == manifest
    with pytest.raises(ValueError):
        updater.validate_manifest({**manifest, "image": "other:v1.2.3"}, "v1.2.3")
    with pytest.raises(ValueError):
        updater.validate_manifest({**manifest, "revision": "main"}, "v1.2.3")


def test_versions_are_numeric_and_environment_keeps_other_settings():
    assert updater.version("v1.10.0") > updater.version("v1.9.9")
    with pytest.raises(ValueError):
        updater.version("latest")
    updated = updater.update_environment("IMAGE=old\nIMAGE_TAG=v1.0.0\nEXTRA=yes\n", "v1.2.3")
    assert updated == "EXTRA=yes\nIMAGE=eco-native\nIMAGE_TAG=v1.2.3\n"


def test_prune_keeps_only_the_running_and_previous_images(monkeypatch):
    calls = []
    monkeypatch.setattr(updater, "run", lambda *args, capture=False: "v1.0.0\nv1.1.0\nv1.2.0\nlatest\n")
    monkeypatch.setattr(updater.subprocess, "run", lambda args, **kwargs: calls.append(args))
    assert updater.image_tag("IMAGE=eco-native\nIMAGE_TAG=v1.1.0\n") == "v1.1.0"
    updater.prune_images({"v1.2.0", updater.image_tag("IMAGE_TAG=v1.1.0\n"), None})
    assert ["docker", "rmi", "eco-native:v1.0.0"] in calls
    assert not any("eco-native:v1.1.0" in call or "eco-native:v1.2.0" in call or "eco-native:latest" in call for call in calls)
    assert ["docker", "builder", "prune", "-f"] in calls


def test_prune_never_fails_an_update(monkeypatch):
    def broken(*args, capture=False):
        raise OSError("docker down")
    monkeypatch.setattr(updater, "run", broken)
    updater.prune_images({"v1.2.0"})
