"""ISSUE-016: OpenAPI Contract & Schema Stability Tests.

Prevents breaking API changes across releases by validating route presence,
HTTP method availability, and response schemas against the specification.
"""

from app.main import app

EXPECTED_ROUTES = {
    # Path: set of allowed methods
    "/healthz": {"GET"},
    "/readyz": {"GET"},
    "/api/v1/documents": {"GET"},
    "/api/v1/documents/upload-init": {"POST"},
    "/api/v1/documents/{document_id}/upload-complete": {"POST"},
    "/api/v1/documents/{document_id}": {"GET", "DELETE"},
    "/api/v1/documents/{document_id}/status": {"GET"},
    "/api/v1/documents/{document_id}/process": {"POST"},
    "/api/v1/documents/{document_id}/ask": {"POST"},
    "/api/v1/documents/compare": {"POST"},
    "/api/v1/actions": {"GET"},
    "/api/v1/actions/reminders": {"POST"},
    "/api/v1/actions/{action_id}": {"PATCH"},
    "/api/v1/users/me": {"DELETE"},
}


def test_openapi_schema_contains_all_contract_routes():
    schema = app.openapi()
    assert "paths" in schema
    paths = schema["paths"]

    for expected_path, expected_methods in EXPECTED_ROUTES.items():
        assert expected_path in paths, f"Missing route in OpenAPI contract: {expected_path}"
        actual_methods = {
            m.upper() for m in paths[expected_path].keys() if m.upper() != "PARAMETERS"
        }
        for method in expected_methods:
            assert method in actual_methods, (
                f"Missing method {method} on {expected_path} in OpenAPI contract"
            )


def test_openapi_core_response_schemas_present():
    schema = app.openapi()
    components = schema.get("components", {}).get("schemas", {})

    expected_schemas = [
        "DocumentResponse",
        "DocumentUploadInitRequest",
        "DocumentUploadInitResponse",
        "UploadCompleteRequest",
        "UploadCompleteResponse",
        "AskRequest",
        "AskResponse",
        "CompareRequest",
        "CompareResponse",
        "ActionResponse",
        "ReminderCreateRequest",
        "ActionUpdateRequest",
        "HealthResponse",
    ]

    for expected in expected_schemas:
        assert any(expected in name for name in components.keys()), (
            f"Expected schema '{expected}' missing from OpenAPI components/schemas"
        )
