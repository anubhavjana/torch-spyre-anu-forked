"""
Upstream PyTorch decorator patchers for the Spyre test framework.

These patchers modify upstream PyTorch test decorators at instantiation time
to allow Spyre's privateuse1 backend to run tests that would otherwise be
restricted to specific devices or dtypes.

Each patcher follows the same pattern:
  1. Receive the test method as passed to instantiate_test()
  2. Locate the upstream decorator instance (in the closure or on the function)
  3. Mutate its configuration in-place so the decorator allows privateuse1

PyTorch decorators like @onlyOn and @ops read their configuration at call
time, not at decoration time. So mutating the decorator instance after
decoration but before the test runs is sufficient.

PyTorch deepcopies the test method before calling instantiate_test(), so
each call has its own fresh decorator instances. A one-time global patch
would not affect these copies.
"""


class _SpyreOnlyOnPatcher:
    """Patches @onlyOn decorated test methods to also allow privateuse1.

    The already-produced only_fn wrapper closes over the onlyOn instance.
    self.device_type is read at call time, so mutating the instance's
    device_type list after decoration still takes effect.
    """

    _PRIVATEUSE1: str

    # Unwrap bound method to get the underlying function object.
    # Test methods passed to instantiate_test() are bound to their class,
    # so __func__ gives us the raw function whose closure we need to walk.

    def __init__(self, test: object, privateuse1_device_type: str) -> None:
        self._PRIVATEUSE1 = privateuse1_device_type
        self._underlying_fn = (
            test.__func__  # type: ignore[union-attr]
            if hasattr(test, "__func__")
            else test
        )

    def patch(self) -> None:
        """Walk the decorator stack and mutate the onlyOn instance in-place.

        Decorator stacking means @onlyOn may not be the outermost wrapper --
        @suppress_warnings, @skipCUDAIfNotRocm, and @ops are all stacked on
        top of it. We walk the __wrapped__ chain (set by @wraps on each layer)
        until we find a closure cell that holds an onlyOn instance.

        Once found, we append our device name to onlyOn.device_type in-place.
        Because the wrapper reads self.device_type at call time (not at
        decoration time), this update takes effect when the test runs.
        """

        from torch.testing._internal.common_device_type import onlyOn as _onlyOn_cls

        current = self._underlying_fn
        while current is not None:
            # Inspect every cell in this function's closure.
            # Each decorator layer may close over different objects --
            # here we are looking specifically for an onlyOn instance.
            cells = getattr(current, "__closure__", None) or ()
            for cell in cells:
                try:
                    val = cell.cell_contents
                except ValueError:
                    continue

                if not isinstance(val, _onlyOn_cls):
                    # This cell holds something else (e.g. the wrapped function,
                    # a string, or another decorator instance), so continue
                    continue

                # Found the onlyOn instance. Its device_type attribute is what
                # the wrapper checks: `if slf.device_type not in self.device_type`.
                # Update in-place to include our backend name.
                if isinstance(val.device_type, list):
                    if self._PRIVATEUSE1 not in val.device_type:
                        val.device_type.append(self._PRIVATEUSE1)

                # Less common scenario: @onlyOn("cuda") -- single string.
                # Replace with a list containing both the original and ours.
                elif isinstance(val.device_type, str):
                    if val.device_type != self._PRIVATEUSE1:
                        val.device_type = [val.device_type, self._PRIVATEUSE1]
                return

            # This layer had no onlyOn instance in its closure.
            # Move one level deeper via __wrapped__, which @wraps sets
            # to point to the function this decorator wraps.
            current = getattr(current, "__wrapped__", None)

        # If we reach here, that means no @onlyOn was found in the decorator stack.
        # That implies that the test simply did not have @onlyOn.


# ---------------------------------------------------------------------------
# Dtype patcher
# ---------------------------------------------------------------------------


class _SpyreDtypePatcher:
    """Patches @ops allowed_dtypes on a bound test method before instantiation.

    Needed because upstream @ops(..., allowed_dtypes=(...)) restricts which dtype
    variants are generated -- dtypes absent here are never instantiated, so they
    cannot be added to the allow_list. We inject extra dtypes before
    super().instantiate_test() calls _parametrize_test.
    """

    def __init__(self, test, extra_dtypes: set):
        from torch.testing._internal.common_device_type import ops as _ops_cls

        # @ops instance lives at test.__func__.parametrize_fn.__self__
        underlying_fn = test.__func__ if hasattr(test, "__func__") else test
        p = getattr(underlying_fn, "parametrize_fn", None)
        self._ops_instance = (
            p.__self__
            if p is not None
            and hasattr(p, "__self__")
            and isinstance(p.__self__, _ops_cls)
            else None
        )
        self._extra_dtypes = extra_dtypes

    def patch(self) -> None:
        if (
            self._ops_instance is not None
            and self._ops_instance.allowed_dtypes is not None
        ):
            self._ops_instance.allowed_dtypes |= self._extra_dtypes
