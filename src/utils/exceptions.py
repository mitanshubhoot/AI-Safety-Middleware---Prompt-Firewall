"""Custom exceptions for the application."""
from typing import Any, Dict


class AIFirewallException(Exception):
    """Base exception for AI Firewall."""

    def __init__(self, message: str, details: Dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ValidationException(AIFirewallException):
    """Exception raised when prompt validation fails."""

    pass


class DetectionException(AIFirewallException):
    """Exception raised when detection process fails."""

    pass


class PolicyException(AIFirewallException):
    """Exception raised when policy evaluation fails."""

    pass


class CacheException(AIFirewallException):
    """Exception raised when cache operations fail."""

    pass


class DatabaseException(AIFirewallException):
    """Exception raised when database operations fail."""

    pass


class ConfigurationException(AIFirewallException):
    """Exception raised when configuration is invalid."""

    pass


class EmbeddingException(AIFirewallException):
    """Exception raised when embedding generation fails."""

    pass


class RateLimitException(AIFirewallException):
    """Exception raised when rate limit is exceeded."""

    pass
