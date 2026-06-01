# SPDX-License-Identifier: Apache-2.0

"""Integration test: ReproducibilityBundle export from config + environment."""

from openscire.config import Config
from openscire.models import ReproducibilityBundle


def test_reproducibility_bundle_export() -> None:
    cfg = Config()
    cfg.model.model_name = "test-model"
    cfg.model.temperature = 0.5

    bundle = cfg.to_reproducibility_bundle()
    assert isinstance(bundle, ReproducibilityBundle)
    assert "pydantic" in bundle.dependency_tree
    assert bundle.config_snapshot["model"]["model_name"] == "test-model"
    assert bundle.config_snapshot["model"]["temperature"] == 0.5
    assert "python" in bundle.hardware_profile
    assert "system" in bundle.hardware_profile


def test_reproducibility_bundle_round_trip(tmp_path: object) -> None:
    from openscire.serialization import Serializer

    cfg = Config()
    bundle = cfg.to_reproducibility_bundle()

    file_path = tmp_path / "bundle.json"
    Serializer.dump(bundle, file_path)
    loaded = Serializer.load(file_path, ReproducibilityBundle)

    assert loaded.dependency_tree == bundle.dependency_tree
    assert loaded.config_snapshot == bundle.config_snapshot
    assert loaded.hardware_profile == bundle.hardware_profile
    assert loaded.environment_lockfile == bundle.environment_lockfile
