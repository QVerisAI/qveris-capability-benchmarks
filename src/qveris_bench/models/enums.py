from enum import StrEnum


class SourceType(StrEnum):
    EXTERNAL_REPOSITORY = "external_repository"
    PUBLIC_BENCHMARK = "public_benchmark"
    CUSTOMER_QUESTION = "customer_question"
    DEVELOPER_QUERY = "developer_query"
    PROVIDER_SUBMISSION = "provider_submission"
    SEARCH_DEMAND = "search_demand"
    QVERIS_ORIGINAL = "qveris_original"


class AccessPathType(StrEnum):
    NATIVE_MCP = "native_mcp"
    OFFICIAL_OPENAPI = "official_openapi"
    OFFICIAL_API = "official_api"
    OFFICIAL_SDK = "official_sdk"
    BENCHMARK_WRAPPER = "benchmark_wrapper"
    QVERIS_CONNECTOR = "qveris_connector"


class AccessProtocol(StrEnum):
    HTTPS_REST = "https_rest"
    MCP_STREAMABLE_HTTP = "mcp_streamable_http"
    MCP_SSE = "mcp_sse"
    FIX_44 = "fix_44"
    SDK = "sdk"


class QualificationDisposition(StrEnum):
    INCLUDED = "included"
    EXCLUDED = "excluded"


class ReleaseFactType(StrEnum):
    OUTCOME = "outcome"
    EVIDENCE = "evidence"
    LIMITATION = "limitation"
    ACCESS_PATH = "access_path"
    PROVIDER_FEEDBACK = "provider_feedback"


class DimensionState(StrEnum):
    MEASURED = "measured"
    DECLARED = "declared"
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"


class RunMode(StrEnum):
    DIRECT = "direct"
    AGENT_TRIAL = "agent_trial"


class CellState(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    PROVIDER_NEGATIVE = "provider_negative"
    INFRA_BLOCKED = "infra_blocked"
    NOT_APPLICABLE = "not_applicable"
    EXCLUDED = "excluded"


class OutcomeStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class FailureAttribution(StrEnum):
    INVALID_PARAMETERS = "invalid_parameters"
    PROVIDER_VALIDATION_ERROR = "provider_validation_error"
    PROVIDER_RUNTIME_ERROR = "provider_runtime_error"
    AUTH_OR_ENTITLEMENT = "auth_or_entitlement"
    RATE_LIMITED = "rate_limited"
    NETWORK_OR_TIMEOUT = "network_or_timeout"
    EMPTY_OR_PARTIAL_DATA = "empty_or_partial_data"
    TRUNCATED_OR_UNPAGED = "truncated_or_unpaged"
    RESPONSE_INTERPRETATION_ERROR = "response_interpretation_error"
    AGENT_OUTPUT_ERROR = "agent_output_error"
    BENCHMARK_SYSTEM_ERROR = "benchmark_system_error"
    UNKNOWN = "unknown"


class RedactionStatus(StrEnum):
    PENDING = "pending"
    SANITIZED = "sanitized"
    NOT_PUBLISHABLE = "not_publishable"


class DisclosureLevel(StrEnum):
    PRIVATE = "private"
    SUMMARY_ONLY = "summary_only"
    SANITIZED_PUBLIC = "sanitized_public"


class LicenseStatus(StrEnum):
    PENDING = "pending"
    CLEARED = "cleared"
    RESTRICTED = "restricted"
