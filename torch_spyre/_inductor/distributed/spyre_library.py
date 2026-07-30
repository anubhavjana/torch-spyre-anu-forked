import torch

# This provides:
# 1. Proper schema registration
# 2. Automatic fake kernel registration
# 3. Better integration with torch.compile
# 4. C++ implementation via TORCH_LIBRARY_IMPL in spyre_distributed.cpp
# This file only registers the abstract (fake/meta) kernels needed by torch.compile
# for shape inference during tracing.

# The op schema is defined here in Python -- NOT via a C++ TORCH_LIBRARY(spyre,
# ...) def -- so it exists as soon as torch_spyre is imported. torch_spyre._C
# (which holds the real PrivateUse1 kernels registered via
# TORCH_LIBRARY_IMPL(spyre, PrivateUse1, ...) in spyre_distributed.cpp) is
# loaded lazily on first real device use (see _SpyreImpl._lazy_init in
# torch_spyre/__init__.py). register_fake() below requires the schema to
# already exist, and this module is imported eagerly at autoload time -- so
# defining the schema via C++ TORCH_LIBRARY would require _C to be loaded
# before autoload finishes, breaking that lazy-load contract and making
# `import torch` raise "operator spyre::broadcast_async does not exist".
# "FRAGMENT" (rather than "DEF") avoids conflicting with other Library
# handles that may also touch the "spyre" namespace (e.g. the
# torch.library.custom_op declarations in customops.py).
#
# Module-level Library handle, kept alive for the lifetime of the process:
# torch.library.Library uses weakref.finalize to call m.reset() on GC, which
# would silently unregister the schema from the dispatcher.
_spyre_distributed_lib = torch.library.Library("spyre", "FRAGMENT")
_spyre_distributed_lib.define(
    "broadcast_async(Tensor input, int src_rank, str group_name) -> Tensor"
)
_spyre_distributed_lib.define("wait_work(Tensor(a!) tensor) -> Tensor(a)")


@torch.library.register_fake("spyre::broadcast_async")
def _(x: torch.Tensor, src_rank: int = 0, group_name: str = "default") -> torch.Tensor:
    """Fake implementation for shape inference during compilation.

    Broadcast preserves shape, dtype, and stride.
    """
    return torch.empty_strided(x.shape, x.stride(), dtype=x.dtype, device=x.device)


@torch.library.register_fake("spyre::wait_work")
def _(x: torch.Tensor) -> torch.Tensor:
    """Fake implementation — pass through the tensor."""
    return x
