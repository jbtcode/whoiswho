import inspect
import sys


class KeypyError(Exception):
    """Base for every exception raised by keypy."""


# --- configuration / programming errors --------------------------------
class InvalidConfiguration(KeypyError):
    """Config file, env var, or metadata is missing or malformed."""


class InvalidAppImplementation(KeypyError):
    """A subclass failed to honour its contract."""


class InvalidArgumentError(KeypyError, ValueError):
    """Caller passed an invalid argument."""


# --- extraction / loading ----------------------------------------------
class ExtractorError(KeypyError):
    """Base for all extractor and loader failures."""


class ConnectionFailed(ExtractorError):
    """Could not reach the source or target system."""


class AuthenticationFailed(ExtractorError):
    """Credentials rejected by the source or target system."""


class ExtractionFailed(ExtractorError):
    """The system was reachable but the extraction itself failed."""


# --- data quality -------------------------------------------------------
class DQError(KeypyError):
    """Data failed a quality or consistency check."""


def get_custom_error_classes() -> list[str]:
    """Names of every exception class defined by keypy."""
    return sorted(
        name
        for name, obj in inspect.getmembers(sys.modules[__name__], inspect.isclass)
        if issubclass(obj, KeypyError)
    )