"""
Main module of the test project.
Imports and uses functions from other modules.
"""

from utils import public_function, GLOBAL_CONSTANT
from helpers import helper_func


def _main():
    """Main function that uses external functions."""
    result = public_function()
    helper_result = helper_func()
    print(f"Result: {result}, Helper: {helper_result}")
    print(f"Constant: {GLOBAL_CONSTANT}")


if __name__ == "__main__":
    _main()
