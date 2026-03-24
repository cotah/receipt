"""Patch supabase_auth.types for pydantic >= 2.12 compatibility.

pydantic 2.12+ rejects ``field: None = None`` in BaseModel subclasses
(unevaluable-type-annotation). supabase_auth.types uses this pattern in
AuthOtpResponse. This module rewrites ``None`` annotations to
``Literal[None]`` before the module is imported by the rest of the app.

Import this module BEFORE importing supabase.
"""
import importlib.machinery
import importlib.util
import pathlib
import sys
import types as _builtin_types


def _find_types_path():
    """Locate supabase_auth/types.py without importing the package."""
    # Walk site-packages to find the file directly
    for path_entry in sys.path:
        candidate = pathlib.Path(path_entry) / "supabase_auth" / "types.py"
        if candidate.is_file():
            return candidate
    return None


def _apply_patch():
    if "supabase_auth.types" in sys.modules:
        return  # Already loaded

    types_path = _find_types_path()
    if types_path is None:
        return

    source = types_path.read_text(encoding="utf-8")

    if "user: None = None" not in source:
        return  # Already fixed upstream

    # Add Literal import if missing
    if "from typing import Literal" not in source and "from typing import" in source:
        source = source.replace(
            "from typing import",
            "from typing import Literal,",
            1,
        )
    elif "from typing import Literal" not in source:
        source = "from typing import Literal\n" + source

    # Replace the ambiguous pattern
    source = source.replace("user: None = None", "user: Literal[None] = None")
    source = source.replace("session: None = None", "session: Literal[None] = None")

    # Build a proper spec without triggering parent __init__.py
    loader = importlib.machinery.SourceFileLoader("supabase_auth.types", str(types_path))
    spec = importlib.util.spec_from_loader("supabase_auth.types", loader, origin=str(types_path))

    mod = _builtin_types.ModuleType("supabase_auth.types")
    mod.__file__ = str(types_path)
    mod.__spec__ = spec
    mod.__package__ = "supabase_auth"

    code = compile(source, str(types_path), "exec")
    sys.modules["supabase_auth.types"] = mod
    exec(code, mod.__dict__)


_apply_patch()
