"""Typed verifier failures used for stable result classification."""


class VerifyError(Exception):
    """Base verifier error."""


class ExactRevisionError(VerifyError):
    """Requested revision cannot be resolved or does not match the tested checkout."""


class SuiteValidationError(VerifyError):
    """Suite/config/report data failed schema validation."""


class AdapterError(VerifyError):
    """Project adapter failed before a product assertion could be evaluated."""
