"""
Pydantic models for the Spyre PyTorch test framework YAML config.

Used by spyre_test_parsing.py to validate and parse the YAML config.
"""

import warnings
from pathlib import Path
from typing import List, Optional, Set

import torch
from pydantic import BaseModel, field_validator, model_validator

from spyre_test_constants import (
    DEFAULT_UNSUPPORTED_DTYPES,
    MODE_MANDATORY_PASS,
    MODE_XFAIL,
    MODE_XFAIL_STRICT,
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
# Models
# ---------------------------------------------------------------------------


class TestEdits(BaseModel):
    extra_allowed_dtypes: List[str] = []
    precision_override: Optional[float] = None
    # None means "use global"; an explicit list overrides global completely
    unsupported_dtypes: Optional[List[str]] = None

    @field_validator("extra_allowed_dtypes", mode="before")
    @classmethod
    def validate_extra_dtypes(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        for dt in v or []:
            if dt not in _VALID_DTYPE_STRINGS:
                raise ValueError(
                    f"Unknown dtype {dt!r} in extra_allowed_dtypes. "
                    f"Valid values: {sorted(_VALID_DTYPE_STRINGS)}"
                )
        return v

    @field_validator("unsupported_dtypes", mode="before")
    @classmethod
    def validate_unsupported_dtypes(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        for dt in v or []:
            if dt not in _VALID_DTYPE_STRINGS:
                raise ValueError(
                    f"Unknown dtype {dt!r} in unsupported_dtypes. "
                    f"Valid values: {sorted(_VALID_DTYPE_STRINGS)}"
                )
        return v

    def resolved_extra_allowed_dtypes(self) -> Set[torch.dtype]:
        """Return extra_allowed_dtypes as a set of torch.dtype."""
        return {parse_dtype(dt) for dt in self.extra_allowed_dtypes}

    def resolved_unsupported_dtypes(self) -> Set[torch.dtype]:
        """Return unsupported_dtypes as a set of torch.dtype.

        Only call when unsupported_dtypes is not None.
        """
        assert self.unsupported_dtypes is not None, (
            "resolved_unsupported_dtypes() called but unsupported_dtypes is None. "
            "Guard with `entry.edits.unsupported_dtypes is not None` before calling."
        )
        return {parse_dtype(dt) for dt in self.unsupported_dtypes}


class AllowListEntry(BaseModel):
    test: str
    mode: str = MODE_MANDATORY_PASS
    tags: List[str] = []
    edits: TestEdits = TestEdits()

    @field_validator("test")
    @classmethod
    def validate_test_id(cls, v: str) -> str:
        parts = v.split("::")
        if len(parts) != 2 or not all(parts):
            raise ValueError(
                f"Invalid test id {v!r}, expected 'ClassName::method_name'"
            )
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in _VALID_MODES:
            raise ValueError(
                f"Invalid mode {v!r}. Valid values: {sorted(_VALID_MODES)}"
            )
        return v

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
    def validate_test_id(cls, v: str) -> str:
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
    def validate_rel_path(cls, v: str) -> str:
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
    def validate_unsupported_dtypes(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        for dt in v or []:
            if dt not in _VALID_DTYPE_STRINGS:
                raise ValueError(
                    f"Unknown dtype {dt!r} in global.unsupported_dtypes. "
                    f"Valid values: {sorted(_VALID_DTYPE_STRINGS)}"
                )
        return v

    def resolved_unsupported_dtypes(self) -> Set[torch.dtype]:
        """Return unsupported_dtypes as a set of torch.dtype.

        Falls back to DEFAULT_UNSUPPORTED_DTYPES if the field is empty.
        """
        if not self.unsupported_dtypes:
            return DEFAULT_UNSUPPORTED_DTYPES.copy()
        return {parse_dtype(dt) for dt in self.unsupported_dtypes}

    def resolved_supported_ops(self) -> Optional[Set[str]]:
        """Return supported_ops as a set of strings, or None if not set."""
        if self.supported_ops is None:
            return None
        return set(self.supported_ops)


class TestsBlock(BaseModel):
    files: List[FileEntry]
    global_config: GlobalConfig = GlobalConfig()

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def rename_global(cls, values: object) -> object:
        # "global" is a Python keyword so we alias it to "global_config"
        if isinstance(values, dict) and "global" in values:
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
