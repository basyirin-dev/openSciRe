from openscire.curation.ratio_enforcer import ExternalSourceRatioEnforcer


class TestExternalSourceRatioEnforcer:
    def test_default_ratio(self) -> None:
        enforcer = ExternalSourceRatioEnforcer()
        assert enforcer.min_external_ratio == 0.5

    def test_passes_when_above_threshold(self) -> None:
        enforcer = ExternalSourceRatioEnforcer({"min_external_ratio": 0.5})
        passed, ratio = enforcer.check_ratio(1, 3)
        assert passed is True
        assert ratio == 0.75

    def test_fails_when_below_threshold(self) -> None:
        enforcer = ExternalSourceRatioEnforcer({"min_external_ratio": 0.5})
        passed, ratio = enforcer.check_ratio(3, 1)
        assert passed is False
        assert ratio == 0.25

    def test_all_external_passes(self) -> None:
        enforcer = ExternalSourceRatioEnforcer({"min_external_ratio": 0.3})
        passed, ratio = enforcer.check_ratio(0, 5)
        assert passed is True
        assert ratio == 1.0

    def test_all_user_fails(self) -> None:
        enforcer = ExternalSourceRatioEnforcer({"min_external_ratio": 0.1})
        passed, ratio = enforcer.check_ratio(5, 0)
        assert passed is False
        assert ratio == 0.0

    def test_zero_total_passes(self) -> None:
        enforcer = ExternalSourceRatioEnforcer()
        passed, ratio = enforcer.check_ratio(0, 0)
        assert passed is True
        assert ratio == 0.0

    def test_get_insufficient_sources_above_ratio(self) -> None:
        enforcer = ExternalSourceRatioEnforcer({"min_external_ratio": 0.5})
        result = enforcer.get_insufficient_sources(["u1"], ["e1", "e2"])
        assert result == []

    def test_get_insufficient_sources_below_ratio(self) -> None:
        enforcer = ExternalSourceRatioEnforcer({"min_external_ratio": 0.5})
        result = enforcer.get_insufficient_sources(["u1", "u2", "u3"], ["e1"])
        assert len(result) >= 1

    def test_get_insufficient_sources_empty(self) -> None:
        enforcer = ExternalSourceRatioEnforcer()
        result = enforcer.get_insufficient_sources([], [])
        assert result == []
