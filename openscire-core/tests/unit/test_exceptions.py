# SPDX-License-Identifier: Apache-2.0

from openscire.constants import ErrorCode
from openscire.exceptions import (
    ConfigError,
    EthicsError,
    ModelProviderError,
    ProvenanceError,
    ValidationError,
    openSciReError,
)


class TestExceptionHierarchy:
    def test_all_are_open_sci_re_error(self) -> None:
        assert issubclass(ProvenanceError, openSciReError)
        assert issubclass(ConfigError, openSciReError)
        assert issubclass(ModelProviderError, openSciReError)
        assert issubclass(EthicsError, openSciReError)
        assert issubclass(ValidationError, openSciReError)
        assert issubclass(openSciReError, Exception)


class TestOpenSciReError:
    def test_default_error_code(self) -> None:
        e = openSciReError()
        assert e.error_code == ErrorCode.ERR_BASE
        assert e.message == ""
        assert e.source == ""

    def test_with_message_and_source(self) -> None:
        e = openSciReError(message="test error", source="test_module")
        assert "[ERR_BASE] test error" in str(e)
        assert e.source == "test_module"

    def test_timestamp_set(self) -> None:
        e = openSciReError()
        assert e.timestamp is not None


class TestProvenanceError:
    def test_default_error_code(self) -> None:
        e = ProvenanceError()
        assert e.error_code == ErrorCode.PROV_CHAIN_BREAK

    def test_override_error_code(self) -> None:
        e = ProvenanceError(
            error_code=ErrorCode.PROV_TAMPER_DETECTED,
            message="tampered",
        )
        assert "[PROV_TAMPER_DETECTED] tampered" in str(e)


class TestConfigError:
    def test_default_error_code(self) -> None:
        e = ConfigError()
        assert e.error_code == ErrorCode.CONFIG_INVALID


class TestModelProviderError:
    def test_default_error_code(self) -> None:
        e = ModelProviderError()
        assert e.error_code == ErrorCode.MODEL_CONNECTION_FAILURE

    def test_auth_failure(self) -> None:
        e = ModelProviderError(
            error_code=ErrorCode.MODEL_AUTH_FAILURE,
            message="invalid API key",
        )
        assert "[MODEL_AUTH_FAILURE] invalid API key" in str(e)


class TestEthicsError:
    def test_default_error_code(self) -> None:
        e = EthicsError()
        assert e.error_code == ErrorCode.ETHICS_DURC_FLAG


class TestValidationError:
    def test_default_error_code(self) -> None:
        e = ValidationError()
        assert e.error_code == ErrorCode.VALIDATION_CLAIM_INVALID

    def test_citation_broken(self) -> None:
        e = ValidationError(
            error_code=ErrorCode.VALIDATION_CITATION_BROKEN,
            message="doi not found",
        )
        assert "doi not found" in str(e)


class TestErrorCodes:
    def test_all_codes_accessible(self) -> None:
        codes = set(ErrorCode)
        assert len(codes) == 41

    def test_general_code(self) -> None:
        assert ErrorCode.ERR_BASE == "ERR_BASE"

    def test_provenance_codes(self) -> None:
        assert ErrorCode.PROV_SIGNING_FAILURE == "PROV_SIGNING_FAILURE"
        assert ErrorCode.PROV_TAMPER_DETECTED == "PROV_TAMPER_DETECTED"

    def test_carbon_budget_code(self) -> None:
        assert ErrorCode.ETHICS_CARBON_BUDGET_EXCEEDED == "ETHICS_CARBON_BUDGET_EXCEEDED"

    def test_uncertainty_code(self) -> None:
        assert ErrorCode.UNCERTAINTY_INSUFFICIENT == "UNCERTAINTY_INSUFFICIENT"

    def test_source_not_found_code(self) -> None:
        assert ErrorCode.VALIDATION_SOURCE_NOT_FOUND == "VALIDATION_SOURCE_NOT_FOUND"

    def test_retracted_source_code(self) -> None:
        assert ErrorCode.VALIDATION_RETRACTED_SOURCE == "VALIDATION_RETRACTED_SOURCE"

    def test_asymmetry_code(self) -> None:
        assert ErrorCode.VALIDATION_ASYMMETRY_DETECTED == "VALIDATION_ASYMMETRY_DETECTED"

    def test_confabulation_code(self) -> None:
        assert ErrorCode.VALIDATION_CONFABULATION_DETECTED == "VALIDATION_CONFABULATION_DETECTED"
