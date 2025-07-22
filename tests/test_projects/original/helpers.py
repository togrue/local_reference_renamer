"""
Helper functions module.
Contains both public and private functions.
"""

# Public global variable
HELPER_VERSION = "1.0.0"

# Private global variable
_cache = {}


def helper_func():
    """Public helper function used externally."""
    return "helper result"


def cache_helper():
    """Private helper function only used locally."""
    return _cache.get("key", "default")


def process_data():
    """Public function that uses private elements."""
    cached = cache_helper()
    return f"processed: {cached}"


# Tuple assignment example
a, b = 1, 2
c, d = 3, 4


def tuple_example():
    """Function that uses tuple variables."""
    return a + b + c + d
