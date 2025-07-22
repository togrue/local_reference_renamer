"""
Helper functions module.
Contains both public and private functions.
"""

# Public global variable
_HELPER_VERSION = "1.0.0"

# Private global variable
_cache = {}


def helper_func():
    """Public helper function used externally."""
    return "helper result"


def _cache_helper():
    """Private helper function only used locally."""
    return _cache.get("key", "default")


def _process_data():
    """Public function that uses private elements."""
    cached = _cache_helper()
    return f"processed: {cached}"


# Tuple assignment example
_a, _b = 1, 2
_c, _d = 3, 4


def _tuple_example():
    """Function that uses tuple variables."""
    return _a + _b + _c + _d
