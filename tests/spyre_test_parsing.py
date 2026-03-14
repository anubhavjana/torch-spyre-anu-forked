"""
YAML config parsing and op_db filtering for the Spyre PyTorch test framework.

Responsibilities:
  - load_yaml_config: read YAML and return validated SpyreTestConfig
  - resolve_rel_path: expand ${PYTORCH} / ${TORCH_SPYRE} tokens
  - resolve_current_file: match a YAML file entry against cwd
  - filter_op_db: monkey-patch pytorch op_db lists to supported_ops subset
"""

import os
import warnings
from pathlib import Path
from typing import Optional, Set

import yaml

from spyre_test_constants import OP_DB_ATTRS, REL_PATH_TOKENS
from spyre_test_config_models import FileEntry, SpyreTestConfig


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


def load_yaml_config(path: str) -> SpyreTestConfig:
    """Load YAML and return a validated SpyreTestConfig.

    Pydantic validates structure, field types, dtype strings, mode values,
    and test id format automatically.

    Raises:
        FileNotFoundError: if the YAML file does not exist.
        pydantic.ValidationError: if the YAML structure is invalid.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Spyre config file not found: {config_path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    return SpyreTestConfig.model_validate(raw)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_rel_path(rel_path: str) -> str:
    """Expand ${PYTORCH} and ${TORCH_SPYRE} tokens using env vars."""
    for token, env_var in REL_PATH_TOKENS:
        if token in rel_path:
            root = os.environ.get(env_var)
            if not root:
                raise EnvironmentError(
                    f"rel_path contains {token!r} but ${env_var} is not set."
                )
            rel_path = rel_path.replace(token, root)
    return rel_path


# ---------------------------------------------------------------------------
# Debug helper
# ---------------------------------------------------------------------------


def _debug(msg: str) -> None:
    os.write(2, f"[DEBUG] resolve_current_file: {msg}\n".encode())


# ---------------------------------------------------------------------------
# Current file resolution
# ---------------------------------------------------------------------------


def resolve_current_file(config: SpyreTestConfig, config_path: str) -> FileEntry:
    """Match a YAML file entry against the file pytest is currently running.

    Searches sys.argv[1:] (skipping the pytest runner at argv[0]) for a .py
    file argument, then finds the FileEntry whose resolved rel_path matches it.

    Raises EnvironmentError if no match is found.
    """
    import sys

    cwd = Path(os.getcwd()).resolve()

    # sys.argv[0] is the pytest runner itself (e.g. pytest/__main__.py) -- skip it.
    # The test file is one of the remaining args, e.g. 'test_ops.py'.
    current_test_file: Optional[str] = None
    for arg in sys.argv[1:]:
        candidate = Path(arg)
        if candidate.suffix == ".py":
            candidate_resolved = (
                (cwd / candidate).resolve()
                if not candidate.is_absolute()
                else candidate.resolve()
            )
            if candidate_resolved.exists():
                current_test_file = str(candidate_resolved)
                break

    _debug(f"current_test_file: {current_test_file!r}")
    _debug(f"cwd: {cwd!r}")

    if current_test_file is None:
        raise EnvironmentError(
            f"Could not determine the test file being run from sys.argv[1:]={sys.argv[1:]!r}.\n"
            f"Make sure you invoke pytest with an explicit test file, "
            f"e.g. `pytest test_ops.py`."
        )

    for file_entry in config.files:
        entry_resolved = str(Path(resolve_rel_path(file_entry.rel_path)).resolve())
        _debug(
            f"entry: {file_entry.rel_path!r} -> {entry_resolved!r} match={entry_resolved == current_test_file}"
        )
        if entry_resolved == current_test_file:
            return file_entry

    raise EnvironmentError(
        f"No rel_path in {config_path!r} matches the test file being run "
        f"({current_test_file!r}).\n"
        f"sys.argv={sys.argv!r}\n"
        f"Available entries:\n"
        + "\n".join(f"  {resolve_rel_path(f.rel_path)}" for f in config.files)
    )


# ---------------------------------------------------------------------------
# op_db monkey-patching
# ---------------------------------------------------------------------------


def filter_op_db(supported_ops: Set[str]) -> None:
    """Restrict pytorch op_db lists to *supported_ops* in-place.

    Handles list attrs (mutated in-place) and tuple attrs (reassigned).
    Unknown types emit a warning and are skipped.

    Args:
        supported_ops: set of op name strings, e.g. {'add', 'mul'}.
                       If empty, raises ValueError.
    """
    import torch.testing._internal.common_methods_invocations as _cmi  # lazy import

    if not supported_ops:
        raise ValueError(
            "supported_ops is empty -- this would skip all ops. "
            "Remove the key from the YAML to run all ops, or add at least one op name."
        )

    for attr in OP_DB_ATTRS:
        obj = getattr(_cmi, attr, None)
        if obj is None:
            continue

        filtered = [op for op in obj if op.name in supported_ops]

        if isinstance(obj, list):
            obj[:] = filtered
        elif isinstance(obj, tuple):
            setattr(_cmi, attr, tuple(filtered))
        else:
            warnings.warn(
                f"spyre filter_op_db: pytorch's {attr!r} is neither a list nor a "
                f"tuple (got {type(obj)}) -- skipping. Op filtering may be incomplete. "
                f"This likely means a pytorch refactor needs revisiting in OP_DB_ATTRS.",
                stacklevel=2,
            )
