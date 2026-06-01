# SPDX-License-Identifier: Apache-2.0

from openscire.models import (
    FalsificationConfig,
    KnowledgeBoundaryFlag,
    ProvenanceEntry,
    ResearchContext,
    ScientificClaim,
)
from openscire.serialization import (
    CURRENT_SERIALIZATION_VERSION,
    SchemaVersionMismatchError,
    SerializationError,
    Serializer,
    UnknownFormatError,
)


class TestSerializerFormats:
    def test_json(self, sample_claim: ScientificClaim) -> None:
        ser = Serializer.dumps(sample_claim, format="json")
        assert isinstance(ser, str)
        restored = Serializer.loads(ser, ScientificClaim, format="json")
        assert restored.field == sample_claim.field

    def test_yaml(self, sample_claim: ScientificClaim) -> None:
        ser = Serializer.dumps(sample_claim, format="yaml")
        assert isinstance(ser, str)
        restored = Serializer.loads(ser, ScientificClaim, format="yaml")
        assert restored.field == sample_claim.field

    def test_msgpack(self, sample_claim: ScientificClaim) -> None:
        ser = Serializer.dumps(sample_claim, format="msgpack")
        assert isinstance(ser, bytes)
        restored = Serializer.loads(ser, ScientificClaim, format="msgpack")
        assert restored.field == sample_claim.field

    def test_all_model_types(
        self,
        sample_claim: ScientificClaim,
        sample_entry: ProvenanceEntry,
        sample_context: ResearchContext,
    ) -> None:
        for model in (sample_claim, sample_entry, sample_context, FalsificationConfig()):
            for fmt in ("json", "yaml", "msgpack"):
                ser = Serializer.dumps(model, format=fmt)
                restored = Serializer.loads(ser, type(model), format=fmt)
                assert type(restored) is type(model)


class TestSerializerFileRoundTrip:
    def test_json_file(self, tmp_path: object, sample_claim: ScientificClaim) -> None:
        p = tmp_path / "test.json"
        Serializer.dump(sample_claim, p)
        loaded = Serializer.load(p, ScientificClaim)
        assert loaded.field == sample_claim.field

    def test_yaml_file(self, tmp_path: object, sample_entry: ProvenanceEntry) -> None:
        p = tmp_path / "test.yaml"
        Serializer.dump(sample_entry, p)
        loaded = Serializer.load(p, ProvenanceEntry)
        assert loaded.action_id == sample_entry.action_id

    def test_msgpack_file(self, tmp_path: object) -> None:
        p = tmp_path / "test.mpk"
        fc = FalsificationConfig()
        Serializer.dump(fc, p)
        loaded = Serializer.load(p, FalsificationConfig)
        assert loaded.enabled == fc.enabled

    def test_auto_detect_format(self, tmp_path: object) -> None:
        p = tmp_path / "data.json"
        skbf = KnowledgeBoundaryFlag(category="outside_corpus", query="test?", confidence=0.1)
        Serializer.dump(skbf, p)
        loaded = Serializer.load(p, KnowledgeBoundaryFlag)
        assert loaded.query == "test?"

    def test_unsupported_extension(self, tmp_path: object) -> None:
        p = tmp_path / "data.xyz"
        try:
            Serializer.dump(FalsificationConfig(), p)
            assert False
        except UnknownFormatError:
            pass


class TestSerializerErrors:
    def test_unsupported_format(self) -> None:
        try:
            Serializer.dumps(FalsificationConfig(), format="xml")
            assert False
        except UnknownFormatError:
            pass

    def test_wrong_model(self, sample_claim: ScientificClaim) -> None:
        ser = Serializer.dumps(sample_claim)
        try:
            Serializer.loads(ser, ProvenanceEntry)
            assert False
        except SchemaVersionMismatchError:
            pass

    def test_too_new_version(self, sample_claim: ScientificClaim) -> None:
        import json

        ser = json.loads(Serializer.dumps(sample_claim))
        ser["serialization_version"] = "99"
        try:
            Serializer.loads(json.dumps(ser), ScientificClaim)
            assert False
        except SchemaVersionMismatchError:
            pass

    def test_corrupt_json(self) -> None:
        try:
            Serializer.loads("not json", ScientificClaim)
            assert False
        except SerializationError:
            pass

    def test_corrupt_yaml(self) -> None:
        try:
            Serializer.loads("not: yaml: [[[", ScientificClaim, format="yaml")
            assert False
        except SerializationError:
            pass

    def test_current_version_constant(self) -> None:
        assert CURRENT_SERIALIZATION_VERSION == "1"


class TestSerializerEdgeCases:
    def test_empty_data_json(self) -> None:
        try:
            Serializer.loads("{}", ScientificClaim)
            assert False
        except SerializationError:
            pass

    def test_yml_extension(self, tmp_path: object) -> None:
        p = tmp_path / "config.yml"
        fc = FalsificationConfig()
        Serializer.dump(fc, p)
        loaded = Serializer.load(p, FalsificationConfig)
        assert loaded.enabled == fc.enabled
