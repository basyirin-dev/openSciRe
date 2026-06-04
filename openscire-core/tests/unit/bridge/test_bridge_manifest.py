from openscire.bridge.manifest import QueryManifestBuilder


class TestQueryManifest:
    def test_build(self) -> None:
        builder = QueryManifestBuilder()
        manifest = builder.build("test_bridge", "search", query="test", limit=10)
        assert manifest.bridge_name == "test_bridge"
        assert manifest.endpoint == "search"
        assert manifest.query_parameters["query"] == "test"
        assert manifest.query_parameters["limit"] == 10

    def test_parameters_preserved(self) -> None:
        builder = QueryManifestBuilder()
        manifest = builder.build(
            "bio_bridge",
            "get",
            identifier="P12345",
            database="uniprot",
            fields=["sequence", "function"],
        )
        assert manifest.kwargs["identifier"] == "P12345"
        assert manifest.kwargs["database"] == "uniprot"
        assert manifest.kwargs["fields"] == ["sequence", "function"]

    def test_provenance_compatibility(self) -> None:
        builder = QueryManifestBuilder()
        manifest = builder.build("pubmed", "search", query="cancer", max_results=100)
        entry = builder.to_provenance_entry(manifest)
        assert entry["action_type"] == "bridge_query"
        assert "params" in entry
        params = entry["params"]
        assert params["bridge_name"] == "pubmed"
        assert params["endpoint"] == "search"
        assert params["query_parameters"]["query"] == "cancer"
