"""Catalog hygiene: example templates promote into production manifests."""

from fastapi.testclient import TestClient

from eda_platform.api import manifest_loader
from eda_platform.api.main import app
from eda_platform.api.manifest_loader import clear_manifest_cache, load_all_manifests
from tests.data.mock_data import mock_manifests

client = TestClient(app)


def _write_example(directory, component_id: str, *, name: str | None = None) -> None:
    manifest = mock_manifests()["sens_ina219"].model_copy(
        update={
            "component_id": component_id,
            "name": name or component_id,
        }
    )
    (directory / f"{component_id}.example.json").write_text(manifest.model_dump_json())


def test_loader_ignores_example_files(tmp_path, monkeypatch):
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    (manifests_dir / "mcu_rp2040.json").write_text(
        mock_manifests()["mcu_rp2040"].model_dump_json()
    )
    _write_example(manifests_dir, "sens_bme280", name="BME280")

    monkeypatch.setattr(manifest_loader, "_MANIFESTS_DIR", manifests_dir)
    clear_manifest_cache()

    assert set(load_all_manifests()) == {"mcu_rp2040"}
    clear_manifest_cache()


def test_promote_example_then_reject_duplicate_and_missing(tmp_path, monkeypatch):
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    _write_example(manifests_dir, "sens_only", name="Only Sensor")
    (manifests_dir / "broken.example.json").write_text("{not json")
    mismatched = mock_manifests()["mcu_rp2040"].model_dump_json()
    (manifests_dir / "not_the_id.example.json").write_text(mismatched)

    monkeypatch.setattr(manifest_loader, "_MANIFESTS_DIR", manifests_dir)
    clear_manifest_cache()

    listed = client.get("/api/v1/manifests/examples")
    assert listed.status_code == 200
    ids = {item["component_id"] for item in listed.json()["examples"]}
    assert ids == {"sens_only"}
    assert listed.json()["examples"][0]["promoted"] is False

    promoted = client.post("/api/v1/manifests/sens_only/promote")
    assert promoted.status_code == 200
    assert promoted.json()["manifest"]["component_id"] == "sens_only"
    assert (manifests_dir / "sens_only.json").read_bytes() == (
        manifests_dir / "sens_only.example.json"
    ).read_bytes()
    assert "sens_only" in load_all_manifests()

    again = client.get("/api/v1/manifests/examples")
    assert again.json()["examples"][0]["promoted"] is True

    duplicate = client.post("/api/v1/manifests/sens_only/promote")
    assert duplicate.status_code == 409

    missing = client.post("/api/v1/manifests/does_not_exist/promote")
    assert missing.status_code == 404

    invalid = client.post("/api/v1/manifests/not_the_id/promote")
    assert invalid.status_code == 400

    clear_manifest_cache()


def test_shipped_catalog_keeps_examples_out_until_promoted():
    clear_manifest_cache()
    catalog = client.get("/api/v1/manifests")
    assert catalog.status_code == 200
    ids = {item["component_id"] for item in catalog.json()["manifests"]}
    assert {"mcu_rp2040", "sens_ina219"} <= ids
    assert "sens_bme280" not in ids
    assert "mcu_rpi4" not in ids

    examples = client.get("/api/v1/manifests/examples")
    assert examples.status_code == 200
    by_id = {item["component_id"]: item for item in examples.json()["examples"]}
    assert by_id["mcu_rp2040"]["promoted"] is True
    assert by_id["sens_ina219"]["promoted"] is True
    assert by_id["sens_bme280"]["promoted"] is False
    assert by_id["mcu_rpi4"]["promoted"] is False
    clear_manifest_cache()
