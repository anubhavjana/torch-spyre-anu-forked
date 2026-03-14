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
from typing import List, Optional, Set

import torch
import yaml
from pydantic import BaseModel, field_validator, model_validator

from spyre_test_constants import (
    DEFAULT_UNSUPPORTED_DTYPES,
    MODE_MANDATORY_PASS,
    MODE_XFAIL,
    MODE_XFAIL_STRICT,
    OP_DB_ATTRS,
    REL_PATH_TOKENS,
)
from spyre_test_matching import parse_dtype


# ---------------------------------------------------------------------------
# Valid dtype strings (used in validators)
# ---------------------------------------------------------------------------

_VALID_DTYPE_STRINGS = {
    "float16",
    "float32",
    "float64",
    "bfloat16",
    "int8",
    "int16",
    "int32",
    "int64",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
    "complex32",
    "complex64",
    "complex128",
    "bool",
}

_VALID_MODES = {MODE_MANDATORY_PASS, MODE_XFAIL, MODE_XFAIL_STRICT}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TestEdits(BaseModel):
    extra_allowed_dtypes: List[str] = []
    precision_override: Optional[float] = None
    unsupported_dtypes: Optional[List[str]] = None

    @field_validator("extra_allowed_dtypes", mode="before")
    @classmethod
    def validate_extra_dtypes(cls, v):
        for dt in v or []:
            if dt not in _VALID_DTYPE_STRINGS:
                raise ValueError(
                    f"Unknown dtype {dt!r} in extra_allowed_dtypes. "
                    f"Valid values: {sorted(_VALID_DTYPE_STRINGS)}"
                )
        return v

    @field_validator("unsupported_dtypes", mode="before")
    @classmethod
    def validate_unsupported_dtypes(cls, v):
        for dt in v or []:
            if dt not in _VALID_DTYPE_STRINGS:
                raise ValueError(
                    f"Unknown dtype {dt!r} in unsupported_dtypes. "
                    f"Valid values: {sorted(_VALID_DTYPE_STRINGS)}"
                )
        return v

    # Convenience: resolved torch.dtype sets used by SpyreTestBase
    def resolved_extra_allowed_dtypes(self) -> Set[torch.dtype]:
        return {parse_dtype(dt) for dt in self.extra_allowed_dtypes}

    def resolved_unsupported_dtypes(self) -> Set[torch.dtype]:
        """Return resolved unsupported dtypes. Only call when unsupported_dtypes is not None."""
        assert self.unsupported_dtypes is not None, (
            "resolved_unsupported_dtypes() called but unsupported_dtypes is None. "
            "Check with `entry.edits.unsupported_dtypes is not None` before calling."
        )
        return {parse_dtype(dt) for dt in self.unsupported_dtypes}


class AllowListEntry(BaseModel):
    test: str
    mode: str = MODE_MANDATORY_PASS
    tags: List[str] = []
    edits: TestEdits = TestEdits()

    @field_validator("test")
    @classmethod
    def validate_test_id(cls, v):
        parts = v.split("::")
        if len(parts) != 2 or not all(parts):
            raise ValueError(
                f"Invalid test id {v!r}, expected 'ClassName::method_name'"
            )
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v):
        if v not in _VALID_MODES:
            raise ValueError(
                f"Invalid mode {v!r}. Valid values: {sorted(_VALID_MODES)}"
            )
        return v

    # Convenience
    @property
    def class_name(self) -> str:
        return self.test.split("::")[0]

    @property
    def method_name(self) -> str:
        return self.test.split("::")[1]


class BlockListEntry(BaseModel):
    test: str

    @field_validator("test")
    @classmethod
    def validate_test_id(cls, v):
        parts = v.split("::")
        if len(parts) != 2 or not all(parts):
            raise ValueError(
                f"Invalid test id {v!r}, expected 'ClassName::method_name'"
            )
        return v

    @property
    def class_name(self) -> str:
        return self.test.split("::")[0]

    @property
    def method_name(self) -> str:
        return self.test.split("::")[1]


class FileEntry(BaseModel):
    rel_path: str
    allow_list: List[AllowListEntry] = []
    block_list: List[BlockListEntry] = []

    @field_validator("rel_path")
    @classmethod
    def validate_rel_path(cls, v):
        known_tokens = {token for token, _ in REL_PATH_TOKENS}
        has_token = any(token in v for token in known_tokens)
        if not has_token and not Path(v).is_absolute():
            warnings.warn(
                f"rel_path {v!r} contains no known token "
                f"({sorted(known_tokens)}) and is not absolute. "
                "Make sure the path is resolvable at runtime.",
                stacklevel=2,
            )
        return v


class GlobalConfig(BaseModel):
    unsupported_dtypes: List[str] = []
    supported_ops: Optional[List[str]] = None

    @field_validator("unsupported_dtypes", mode="before")
    @classmethod
    def validate_unsupported_dtypes(cls, v):
        for dt in v or []:
            if dt not in _VALID_DTYPE_STRINGS:
                raise ValueError(
                    f"Unknown dtype {dt!r} in global.unsupported_dtypes. "
                    f"Valid values: {sorted(_VALID_DTYPE_STRINGS)}"
                )
        return v

    # Convenience
    def resolved_unsupported_dtypes(self) -> Set[torch.dtype]:
        if not self.unsupported_dtypes:
            return DEFAULT_UNSUPPORTED_DTYPES.copy()
        return {parse_dtype(dt) for dt in self.unsupported_dtypes}

    def resolved_supported_ops(self) -> Optional[Set[str]]:
        if self.supported_ops is None:
            return None
        return set(self.supported_ops)


class TestsBlock(BaseModel):
    files: List[FileEntry]
    global_config: GlobalConfig = GlobalConfig()

    # pydantic reads "global" from YAML but "global" is a Python keyword
    # so we alias it
    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def rename_global(cls, values):
        if "global" in values:
            values["global_config"] = values.pop("global")
        return values


class SpyreTestConfig(BaseModel):
    tests: TestsBlock

    @property
    def files(self) -> List[FileEntry]:
        return self.tests.files

    @property
    def global_config(self) -> GlobalConfig:
        return self.tests.global_config


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

    # pydantic raises ValidationError with clear field-level messages if invalid
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


# def resolve_current_file(config: SpyreTestConfig, config_path: str) -> FileEntry:
#     """Match a YAML FileEntry against the current working directory.

#     Returns:
#         The matching FileEntry.

#     Raises:
#         EnvironmentError: if no entry matches cwd.
#     """
#     cwd = os.path.abspath(os.getcwd())
#     for file_entry in config.files:
#         resolved = os.path.abspath(resolve_rel_path(file_entry.rel_path))
#         if os.path.dirname(resolved) == cwd:
#             return file_entry
#     raise EnvironmentError(
#         f"No rel_path in {config_path!r} matches the current working directory "
#         f"{cwd!r}.\n"
#         f"Make sure you are running pytest from the pytorch/test/ directory and "
#         f"that the YAML has an entry for the test file you are running."
#     )


def resolve_current_file(config: SpyreTestConfig, config_path: str) -> FileEntry:
    """Match a YAML file entry against the file pytest is currently running.

    Iterates sys.argv to find the test file path passed to pytest, then
    finds the FileEntry whose resolved rel_path matches it exactly.

    Raises EnvironmentError if no match is found.
    """
    import sys

    # Find the test file pytest was invoked with from sys.argv
    # e.g. pytest test_ops.py -v  ->  sys.argv = ['pytest', 'test_ops.py', '-v']
    current_test_file = None
    for arg in sys.argv:
        candidate = Path(arg)
        if candidate.suffix == ".py" and candidate.exists():
            current_test_file = str(candidate.resolve())
            break

    if current_test_file is None:
        raise EnvironmentError(
            f"Could not determine the test file being run from sys.argv={sys.argv!r}.\n"
            f"Make sure you invoke pytest with an explicit test file, "
            f"e.g. `pytest test_ops.py`."
        )

    for file_entry in config.files:
        resolved = str(Path(resolve_rel_path(file_entry.rel_path)).resolve())
        if resolved == current_test_file:
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
