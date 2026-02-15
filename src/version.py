"""
Version information for radioToolsAutomation.
"""

__version__ = "2.6.10"
__version_info__ = (2, 6, 10)
__release_date__ = "February 14, 2026"

# Version metadata
VERSION_NAME = "radioToolsAutomation"
VERSION_STRING = f"{VERSION_NAME} v{__version__}"
FULL_VERSION = f"{VERSION_STRING} ({__release_date__})"

# Compatibility info
MINIMUM_PYTHON_VERSION = "3.8"
TESTED_PYTHON_VERSION = "3.12.3"

def get_version():
    """Return the version string."""
    return __version__

def get_version_info():
    """Return version as tuple (major, minor, patch)."""
    return __version_info__

def get_full_version():
    """Return full version string with release date."""
    return FULL_VERSION

if __name__ == "__main__":
    print(FULL_VERSION)
    print(f"Minimum Python version: {MINIMUM_PYTHON_VERSION}")
    print(f"Tested on Python: {TESTED_PYTHON_VERSION}")


