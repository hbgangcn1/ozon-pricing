"""Proxy module for intra-package function resolution.

All cross-submodule function calls within the db package MUST go through
this proxy so that test patches on db_utils.X (via db/__init__.py) work.
"""


class _DbPackageProxy:
    """Resolves attribute lookups through the db package namespace."""

    def __getattr__(self, name):
        import db

        return getattr(db, name)


_db = _DbPackageProxy()
