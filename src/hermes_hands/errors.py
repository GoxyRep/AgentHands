"""Custom exception hierarchy for hermes-hands."""


class HermesHandsError(Exception):
    """Base exception for all hermes-hands errors."""


class ConfigError(HermesHandsError):
    """Configuration is missing or invalid."""


class PolicyDeniedError(HermesHandsError):
    """An action was denied by the policy gate.

    Attributes:
        action: The action that was denied.
        reason: Human-readable explanation.
    """

    def __init__(self, action: str, reason: str) -> None:
        self.action = action
        self.reason = reason
        super().__init__(f"Policy denied '{action}': {reason}")


class AuthError(HermesHandsError):
    """Authentication or authorization failed."""


class ApiError(HermesHandsError):
    """The PiKVM API returned an error.

    Attributes:
        status_code: HTTP status code.
        body: Response body (truncated).
    """

    def __init__(self, message: str, status_code: int = 0, body: str = "") -> None:
        self.status_code = status_code
        self.body = body[:500]
        super().__init__(f"{message} (HTTP {status_code}): {self.body}")


class SnapshotError(HermesHandsError):
    """Snapshot retrieval or validation failed."""
