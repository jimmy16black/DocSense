"""BE-2 (Settings validation) + BE-4 (error-code catalog) regression tests."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _prod_kwargs(**overrides):
    base = {
        "APP_ENV": "production",
        "SECRET_KEY": "x" * 48,
        "ALLOWED_ORIGINS": "https://app.example.com",
        "SUPABASE_URL": "https://proj.supabase.co",
        "SUPABASE_JWT_SECRET": "y" * 40,
        "SUPABASE_SERVICE_ROLE_KEY": "real-service-key",
        "OPENAI_API_KEY": "sk-real",
    }
    base.update(overrides)
    return base


class TestSettingsValidation:
    def test_unknown_env_var_rejected(self):
        # extra="forbid": typos like REDIS_URL must fail loudly at startup.
        with pytest.raises(ValidationError, match="extra_forbidden"):
            Settings(REDIS_URL="redis://typo")

    def test_invalid_app_env_rejected(self):
        with pytest.raises(ValidationError, match="APP_ENV must be one of"):
            Settings(APP_ENV="prod")  # typo of "production"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"MAX_PAGE_COUNT": 0},
            {"MAX_UPLOAD_SIZE_BYTES": -1},
            {"R2_PRESIGNED_EXPIRATION_SECONDS": 10},
            {"APP_PORT": 70000},
            {"EMBEDDING_DIMENSION": 0},
        ],
    )
    def test_numeric_bounds_enforced(self, kwargs):
        with pytest.raises(ValidationError):
            Settings(**kwargs)

    def test_production_with_defaults_fails_aggregated(self):
        with pytest.raises(ValidationError) as excinfo:
            Settings(APP_ENV="production")
        msg = str(excinfo.value)
        for expected in ("SECRET_KEY", "ALLOWED_ORIGINS", "SUPABASE_SERVICE_ROLE_KEY", "https"):
            assert expected in msg

    def test_valid_production_configuration_passes(self):
        s = Settings(**_prod_kwargs())
        assert s.is_production

    def test_production_requires_ai_key(self):
        kw = _prod_kwargs()
        kw.pop("OPENAI_API_KEY")
        with pytest.raises(ValidationError, match="AI gateway key"):
            Settings(**kw)

    def test_development_unaffected_by_hardening(self):
        s = Settings(APP_ENV="development")  # defaults are fine outside prod
        assert not s.is_production


class TestErrorCodeCatalog:
    """BE-4: every user-visible failure carries a stable machine code.

    Note: the `client` fixture already overrides get_current_user with a mock
    identity (see conftest), so no Authorization header is needed here.
    """

    async def test_failed_document_exposes_friendly_retry_message(self, client):
        # Upload verification failure -> FAILED row stores a user-safe message
        # (mobile shows its own friendly copy keyed by error code; the stored
        # message must never contain stack traces or internal paths).
        from app.models.document import Document  # noqa: F401  (schema sanity)

        init = await client.post(
            "/api/v1/documents/upload-init",
            json={"fileName": "a.pdf", "fileSizeBytes": 1234, "mimeType": "application/pdf"},
        )
        assert init.status_code == 200
        doc_id = init.json()["data"]["documentId"]

        # Complete without uploading bytes -> server-side verification fails.
        res = await client.post(f"/api/v1/documents/{doc_id}/upload-complete")
        assert res.status_code == 422
        body = res.json()
        assert body["success"] is False
        err = body["error"]
        assert err["code"] == "VALIDATION_ERROR"
        assert err["classification"] == "USER_ACTION_REQUIRED"
        assert "correlationId" in err
        # No internal leakage:
        for leak in ("Traceback", ".py", "sqlite", "postgresql", "/app/"):
            assert leak not in err["message"]

    async def test_validation_handler_emits_stable_code(self, client):
        res = await client.post(
            "/api/v1/documents/upload-init",
            json={"fileName": "x"},  # missing required fields
        )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_unknown_route_is_structured_404(self, client):
        res = await client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000")
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
