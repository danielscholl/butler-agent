"""Custom exception classes for Butler Agent."""


class ButlerError(Exception):
    """Base exception for Butler Agent errors."""

    pass


class ClusterNotFoundError(ButlerError):
    """Raised when a cluster cannot be found."""

    pass


class ClusterAlreadyExistsError(ButlerError):
    """Raised when attempting to create a cluster that already exists."""

    pass


class KindCommandError(ButlerError):
    """Raised when a kind CLI command fails."""

    pass


class ConfigurationError(ButlerError):
    """Raised when configuration is invalid or missing."""

    pass
