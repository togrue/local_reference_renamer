"""
Utility functions module.
Contains both public and private functions/variables.
"""

# Public global variable - used externally
GLOBAL_CONSTANT = 42

# Private global variable - only used locally
local_config = {"debug": True, "timeout": 30}


def public_function():
    """Public function that is used externally."""
    return "public result"


def private_function():
    """Private function that is only used locally."""
    return "private result"


def internal_helper():
    """Helper function used only within this module."""
    return private_function() + " with config: " + str(local_config)


# This function uses the private function and variable
def another_public_function():
    """Another public function that uses private elements."""
    return internal_helper()
