"""Safe provider metadata for diagnosis; omit exception bodies and supplied values."""

import re


def provider_error_fields(error: Exception) -> dict:
    code = getattr(error, "code", None)
    status = getattr(error, "status_code", None)
    return {
        "error_type": type(error).__name__,
        "http_status": status if type(status) is int and 100 <= status <= 599 else None,
        "provider_code": code
        if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", code)
        else None,
    }
