# Copyright 2025 The Torch-Spyre Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import torch
import torch_spyre.fallbacks  # noqa: F401
from typing import Union


@torch.library.register_kernel("aten::mm", ["spyre"])
def spyre__mm(self: torch.Tensor, mat2: torch.Tensor) -> torch.Tensor:
    compiled_mm = torch.compile(torch.mm, dynamic=False)
    return compiled_mm(self, mat2)


@torch.library.register_kernel("aten::mm.out", ["spyre"])
def spyre__mm_out(
    self: torch.Tensor, mat2: torch.Tensor, out: torch.Tensor
) -> torch.Tensor:
    compiled_mm = torch.compile(torch.mm, dynamic=False)
    return compiled_mm(self, mat2, out=out)


@torch.library.register_kernel("aten::fill_.Scalar", ["spyre"])
def spyre__fill_scalar(
    self: torch.Tensor, other: Union[int, float, bool, complex]
) -> torch.Tensor:
    tmp = torch.ones(self.size(), dtype=self.dtype) * other
    self.copy_(tmp)
    return self




# INSERT_CODEGEN_HERE

@torch.library.register_kernel("aten::abs", ["spyre"])
def spyre__abs_default(self: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_abs = torch.compile(torch.abs, dynamic=False)
    return compiled_abs(self)


@torch.library.register_kernel("aten::abs.out", ["spyre"])
def spyre__abs_out(self: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_abs = torch.compile(torch.abs, dynamic=False)
    return compiled_abs(self, out=out)


@torch.library.register_kernel("aten::add.Tensor", ["spyre"])
def spyre__add_Tensor(self: torch.Tensor, other: torch.Tensor, alpha: Union[int, float, bool, complex] = 1) -> torch.Tensor:
    # Standard variant
    compiled_add = torch.compile(torch.add, dynamic=False)
    return compiled_add(self, other, alpha=alpha)


@torch.library.register_kernel("aten::add.out", ["spyre"])
def spyre__add_out(self: torch.Tensor, other: torch.Tensor, alpha: Union[int, float, bool, complex] = 1, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_add = torch.compile(torch.add, dynamic=False)
    return compiled_add(self, other, alpha=alpha, out=out)


@torch.library.register_kernel("aten::add.Scalar", ["spyre"])
def spyre__add_Scalar(self: torch.Tensor, other: Union[int, float, bool, complex], alpha: Union[int, float, bool, complex] = 1) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    other_scaTensor = None
    other_scaTensor = torch.tensor([other], device="spyre")
    # Standard variant
    compiled_add = torch.compile(torch.add, dynamic=False)
    return compiled_add(self, other_scaTensor, alpha)


@torch.library.register_kernel("aten::bitwise_not", ["spyre"])
def spyre__bitwise_not_default(self: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_bitwise_not = torch.compile(torch.bitwise_not, dynamic=False)
    return compiled_bitwise_not(self)


@torch.library.register_kernel("aten::bitwise_not.out", ["spyre"])
def spyre__bitwise_not_out(self: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_bitwise_not = torch.compile(torch.bitwise_not, dynamic=False)
    return compiled_bitwise_not(self, out=out)


@torch.library.register_kernel("aten::logical_not", ["spyre"])
def spyre__logical_not_default(self: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_logical_not = torch.compile(torch.logical_not, dynamic=False)
    return compiled_logical_not(self)


@torch.library.register_kernel("aten::logical_not.out", ["spyre"])
def spyre__logical_not_out(self: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_logical_not = torch.compile(torch.logical_not, dynamic=False)
    return compiled_logical_not(self, out=out)


@torch.library.register_kernel("aten::cat", ["spyre"])
def spyre__cat_default(tensors: list[torch.Tensor], dim: int = 0) -> torch.Tensor:
    # Standard variant
    compiled_cat = torch.compile(torch.cat, dynamic=False)
    return compiled_cat(tensors, dim)


@torch.library.register_kernel("aten::cat.out", ["spyre"])
def spyre__cat_out(tensors: list[torch.Tensor], dim: int = 0, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_cat = torch.compile(torch.cat, dynamic=False)
    return compiled_cat(tensors, dim, out=out)


@torch.library.register_kernel("aten::cat.names", ["spyre"])
def spyre__cat_names(tensors: list[torch.Tensor], dim: str) -> torch.Tensor:
    # Standard variant
    compiled_cat = torch.compile(torch.cat, dynamic=False)
    return compiled_cat(tensors, dim)


@torch.library.register_kernel("aten::cat.names_out", ["spyre"])
def spyre__cat_names_out(tensors: list[torch.Tensor], dim: str, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_cat = torch.compile(torch.cat, dynamic=False)
    return compiled_cat(tensors, dim, out=out)


@torch.library.register_kernel("aten::cumsum", ["spyre"])
def spyre__cumsum_default(self: torch.Tensor, dim: int, dtype: None = None) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::cumsum", "CPU")
    return kernel.call_boxed(torch._C._dispatch_keys(self), self, dim, dtype=dtype)


@torch.library.register_kernel("aten::cumsum.out", ["spyre"])
def spyre__cumsum_out(self: torch.Tensor, dim: int, dtype: None = None, out: torch.Tensor = None) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::cumsum.out", "CPU")
    out = kernel.call_boxed(torch._C._dispatch_keys(self), self, dim, dtype=dtype)
    return out


@torch.library.register_kernel("aten::cumsum.dimname", ["spyre"])
def spyre__cumsum_dimname(self: torch.Tensor, dim: str, dtype: None = None) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::cumsum.dimname", "CPU")
    return kernel.call_boxed(torch._C._dispatch_keys(self), self, dim, dtype=dtype)


@torch.library.register_kernel("aten::cumsum.dimname_out", ["spyre"])
def spyre__cumsum_dimname_out(self: torch.Tensor, dim: str, dtype: None = None, out: torch.Tensor = None) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::cumsum.dimname_out", "CPU")
    out = kernel.call_boxed(torch._C._dispatch_keys(self), self, dim, dtype=dtype)
    return out


@torch.library.register_kernel("aten::div.Tensor", ["spyre"])
def spyre__div_Tensor(self: torch.Tensor, other: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_div = torch.compile(torch.div, dynamic=False)
    return compiled_div(self, other)


@torch.library.register_kernel("aten::div.out", ["spyre"])
def spyre__div_out(self: torch.Tensor, other: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_div = torch.compile(torch.div, dynamic=False)
    return compiled_div(self, other, out=out)


@torch.library.register_kernel("aten::div.Tensor_mode", ["spyre"])
def spyre__div_Tensor_mode(self: torch.Tensor, other: torch.Tensor, rounding_mode: None) -> torch.Tensor:
    # Standard variant
    compiled_div = torch.compile(torch.div, dynamic=False)
    return compiled_div(self, other, rounding_mode=rounding_mode)


@torch.library.register_kernel("aten::div.out_mode", ["spyre"])
def spyre__div_out_mode(self: torch.Tensor, other: torch.Tensor, rounding_mode: None, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_div = torch.compile(torch.div, dynamic=False)
    return compiled_div(self, other, rounding_mode=rounding_mode, out=out)


@torch.library.register_kernel("aten::div.Scalar", ["spyre"])
def spyre__div_Scalar(self: torch.Tensor, other: Union[int, float, bool, complex]) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    other_scaTensor = None
    other_scaTensor = torch.tensor([other], device="spyre")
    # Standard variant
    compiled_div = torch.compile(torch.div, dynamic=False)
    return compiled_div(self, other_scaTensor)


@torch.library.register_kernel("aten::div.Scalar_mode", ["spyre"])
def spyre__div_Scalar_mode(self: torch.Tensor, other: Union[int, float, bool, complex], rounding_mode: None) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    other_scaTensor = None
    other_scaTensor = torch.tensor([other], device="spyre")
    # Standard variant
    compiled_div = torch.compile(torch.div, dynamic=False)
    return compiled_div(self, other_scaTensor, rounding_mode=rounding_mode)


@torch.library.register_kernel("aten::embedding", ["spyre"])
def spyre__embedding_default(weight: torch.Tensor, indices: torch.Tensor, padding_idx: int = -1, scale_grad_by_freq: bool = False, sparse: bool = False) -> torch.Tensor:
    # Standard variant
    compiled_embedding = torch.compile(torch.nn.functional.embedding, dynamic=False)
    return compiled_embedding(weight, indices, padding_idx, scale_grad_by_freq, sparse)


@torch.library.register_kernel("aten::exp", ["spyre"])
def spyre__exp_default(self: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_exp = torch.compile(torch.exp, dynamic=False)
    return compiled_exp(self)


@torch.library.register_kernel("aten::exp.out", ["spyre"])
def spyre__exp_out(self: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_exp = torch.compile(torch.exp, dynamic=False)
    return compiled_exp(self, out=out)


@torch.library.register_kernel("aten::expand", ["spyre"])
def spyre__expand_default(self: torch.Tensor, size: list[int], implicit: bool = False) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::expand", "CPU")
    return kernel.call_boxed(torch._C._dispatch_keys(self), self, size, implicit)


@torch.library.register_kernel("aten::log", ["spyre"])
def spyre__log_default(self: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_log = torch.compile(torch.log, dynamic=False)
    return compiled_log(self)


@torch.library.register_kernel("aten::log.out", ["spyre"])
def spyre__log_out(self: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_log = torch.compile(torch.log, dynamic=False)
    return compiled_log(self, out=out)


@torch.library.register_kernel("aten::mul.Tensor", ["spyre"])
def spyre__mul_Tensor(self: torch.Tensor, other: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_mul = torch.compile(torch.mul, dynamic=False)
    return compiled_mul(self, other)


@torch.library.register_kernel("aten::mul.out", ["spyre"])
def spyre__mul_out(self: torch.Tensor, other: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_mul = torch.compile(torch.mul, dynamic=False)
    return compiled_mul(self, other, out=out)


@torch.library.register_kernel("aten::mul.Scalar", ["spyre"])
def spyre__mul_Scalar(self: torch.Tensor, other: Union[int, float, bool, complex]) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    other_scaTensor = None
    other_scaTensor = torch.tensor([other], device="spyre")
    # Standard variant
    compiled_mul = torch.compile(torch.mul, dynamic=False)
    return compiled_mul(self, other_scaTensor)


@torch.library.register_kernel("aten::permute", ["spyre"])
def spyre__permute_default(self: torch.Tensor, dims: list[int]) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::permute", "CPU")
    return kernel.call_boxed(torch._C._dispatch_keys(self), self, dims)


@torch.library.register_kernel("aten::reciprocal", ["spyre"])
def spyre__reciprocal_default(self: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_reciprocal = torch.compile(torch.reciprocal, dynamic=False)
    return compiled_reciprocal(self)


@torch.library.register_kernel("aten::reciprocal.out", ["spyre"])
def spyre__reciprocal_out(self: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_reciprocal = torch.compile(torch.reciprocal, dynamic=False)
    return compiled_reciprocal(self, out=out)


@torch.library.register_kernel("aten::neg", ["spyre"])
def spyre__neg_default(self: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_neg = torch.compile(torch.neg, dynamic=False)
    return compiled_neg(self)


@torch.library.register_kernel("aten::neg.out", ["spyre"])
def spyre__neg_out(self: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_neg = torch.compile(torch.neg, dynamic=False)
    return compiled_neg(self, out=out)


@torch.library.register_kernel("aten::repeat", ["spyre"])
def spyre__repeat_default(self: torch.Tensor, repeats: list[int]) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::repeat", "CPU")
    return kernel.call_boxed(torch._C._dispatch_keys(self), self, repeats)


@torch.library.register_kernel("aten::relu", ["spyre"])
def spyre__relu_default(self: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_relu = torch.compile(torch.relu, dynamic=False)
    return compiled_relu(self)


@torch.library.register_kernel("aten::gelu.out", ["spyre"])
def spyre__gelu_out(self: torch.Tensor, approximate: str = "none", out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_gelu = torch.compile(torch.nn.functional.gelu, dynamic=False)
    return compiled_gelu(self, approximate=approximate, out=out)


@torch.library.register_kernel("aten::gelu", ["spyre"])
def spyre__gelu_default(self: torch.Tensor, approximate: str = "none") -> torch.Tensor:
    # Standard variant
    compiled_gelu = torch.compile(torch.nn.functional.gelu, dynamic=False)
    return compiled_gelu(self, approximate=approximate)


@torch.library.register_kernel("aten::rsqrt", ["spyre"])
def spyre__rsqrt_default(self: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_rsqrt = torch.compile(torch.rsqrt, dynamic=False)
    return compiled_rsqrt(self)


@torch.library.register_kernel("aten::rsqrt.out", ["spyre"])
def spyre__rsqrt_out(self: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_rsqrt = torch.compile(torch.rsqrt, dynamic=False)
    return compiled_rsqrt(self, out=out)


@torch.library.register_kernel("aten::silu", ["spyre"])
def spyre__silu_default(self: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_silu = torch.compile(torch.nn.functional.silu, dynamic=False)
    return compiled_silu(self)


@torch.library.register_kernel("aten::silu.out", ["spyre"])
def spyre__silu_out(self: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_silu = torch.compile(torch.nn.functional.silu, dynamic=False)
    return compiled_silu(self, out=out)


@torch.library.register_kernel("aten::mish", ["spyre"])
def spyre__mish_default(self: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_mish = torch.compile(torch.nn.functional.mish, dynamic=False)
    return compiled_mish(self)


@torch.library.register_kernel("aten::mish.out", ["spyre"])
def spyre__mish_out(self: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_mish = torch.compile(torch.nn.functional.mish, dynamic=False)
    return compiled_mish(self, out=out)


@torch.library.register_kernel("aten::sigmoid", ["spyre"])
def spyre__sigmoid_default(self: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_sigmoid = torch.compile(torch.ops.aten.sigmoid, dynamic=False)
    return compiled_sigmoid(self)


@torch.library.register_kernel("aten::sigmoid.out", ["spyre"])
def spyre__sigmoid_out(self: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_sigmoid = torch.compile(torch.ops.aten.sigmoid, dynamic=False)
    return compiled_sigmoid(self, out=out)


@torch.library.register_kernel("aten::_softmax", ["spyre"])
def spyre___softmax_default(self: torch.Tensor, dim: int, half_to_float: bool) -> torch.Tensor:
    # Standard variant
    compiled__softmax = torch.compile(torch.ops.aten._softmax, dynamic=False)
    return compiled__softmax(self, dim, half_to_float)


@torch.library.register_kernel("aten::_softmax.out", ["spyre"])
def spyre___softmax_out(self: torch.Tensor, dim: int, half_to_float: bool, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled__softmax = torch.compile(torch.ops.aten._softmax, dynamic=False)
    return compiled__softmax(self, dim, half_to_float, out=out)


@torch.library.register_kernel("aten::squeeze", ["spyre"])
def spyre__squeeze_default(self: torch.Tensor) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::squeeze", "CPU")
    return kernel.call_boxed(torch._C._dispatch_keys(self), self)


@torch.library.register_kernel("aten::squeeze.dim", ["spyre"])
def spyre__squeeze_dim(self: torch.Tensor, dim: int) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::squeeze.dim", "CPU")
    return kernel.call_boxed(torch._C._dispatch_keys(self), self, dim)


@torch.library.register_kernel("aten::squeeze.dimname", ["spyre"])
def spyre__squeeze_dimname(self: torch.Tensor, dim: str) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::squeeze.dimname", "CPU")
    return kernel.call_boxed(torch._C._dispatch_keys(self), self, dim)


@torch.library.register_kernel("aten::squeeze.dims", ["spyre"])
def spyre__squeeze_dims(self: torch.Tensor, dim: list[int]) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::squeeze.dims", "CPU")
    return kernel.call_boxed(torch._C._dispatch_keys(self), self, dim)


@torch.library.register_kernel("aten::stack", ["spyre"])
def spyre__stack_default(tensors: list[torch.Tensor], dim: int = 0) -> torch.Tensor:
    # Standard variant
    compiled_stack = torch.compile(torch.stack, dynamic=False)
    return compiled_stack(tensors, dim)


@torch.library.register_kernel("aten::stack.out", ["spyre"])
def spyre__stack_out(tensors: list[torch.Tensor], dim: int = 0, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_stack = torch.compile(torch.stack, dynamic=False)
    return compiled_stack(tensors, dim, out=out)


@torch.library.register_kernel("aten::sum", ["spyre"])
def spyre__sum_default(self: torch.Tensor, dtype: None = None) -> torch.Tensor:
    # Standard variant
    compiled_sum = torch.compile(torch.sum, dynamic=False)
    return compiled_sum(self, dtype=dtype)


@torch.library.register_kernel("aten::sum.dim_IntList", ["spyre"])
def spyre__sum_dim_IntList(self: torch.Tensor, dim: None, keepdim: bool = False, dtype: None = None) -> torch.Tensor:
    # Standard variant
    compiled_sum = torch.compile(torch.sum, dynamic=False)
    return compiled_sum(self, dim, keepdim, dtype=dtype)


@torch.library.register_kernel("aten::sum.dim_DimnameList", ["spyre"])
def spyre__sum_dim_DimnameList(self: torch.Tensor, dim: list[str], keepdim: bool = False, dtype: None = None) -> torch.Tensor:
    # Standard variant
    compiled_sum = torch.compile(torch.sum, dynamic=False)
    return compiled_sum(self, dim, keepdim, dtype=dtype)


@torch.library.register_kernel("aten::sum.IntList_out", ["spyre"])
def spyre__sum_IntList_out(self: torch.Tensor, dim: None, keepdim: bool = False, dtype: None = None, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_sum = torch.compile(torch.sum, dynamic=False)
    return compiled_sum(self, dim, keepdim, dtype=dtype, out=out)


@torch.library.register_kernel("aten::sum.DimnameList_out", ["spyre"])
def spyre__sum_DimnameList_out(self: torch.Tensor, dim: list[str], keepdim: bool = False, dtype: None = None, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_sum = torch.compile(torch.sum, dynamic=False)
    return compiled_sum(self, dim, keepdim, dtype=dtype, out=out)


@torch.library.register_kernel("aten::sqrt", ["spyre"])
def spyre__sqrt_default(self: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_sqrt = torch.compile(torch.sqrt, dynamic=False)
    return compiled_sqrt(self)


@torch.library.register_kernel("aten::sqrt.out", ["spyre"])
def spyre__sqrt_out(self: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_sqrt = torch.compile(torch.sqrt, dynamic=False)
    return compiled_sqrt(self, out=out)


@torch.library.register_kernel("aten::t", ["spyre"])
def spyre__t_default(self: torch.Tensor) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::t", "CPU")
    return kernel.call_boxed(torch._C._dispatch_keys(self), self)


@torch.library.register_kernel("aten::tanh", ["spyre"])
def spyre__tanh_default(self: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_tanh = torch.compile(torch.tanh, dynamic=False)
    return compiled_tanh(self)


@torch.library.register_kernel("aten::tanh.out", ["spyre"])
def spyre__tanh_out(self: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_tanh = torch.compile(torch.tanh, dynamic=False)
    return compiled_tanh(self, out=out)


@torch.library.register_kernel("aten::transpose.int", ["spyre"])
def spyre__transpose_int(self: torch.Tensor, dim0: int, dim1: int) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::transpose.int", "CPU")
    return kernel.call_boxed(torch._C._dispatch_keys(self), self, dim0, dim1)


@torch.library.register_kernel("aten::transpose.Dimname", ["spyre"])
def spyre__transpose_Dimname(self: torch.Tensor, dim0: str, dim1: str) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::transpose.Dimname", "CPU")
    return kernel.call_boxed(torch._C._dispatch_keys(self), self, dim0, dim1)


@torch.library.register_kernel("aten::_unsafe_view", ["spyre"])
def spyre___unsafe_view_default(self: torch.Tensor, size: list[int]) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::_unsafe_view", "CPU")
    return kernel.call_boxed(torch._C._dispatch_keys(self), self, size)


@torch.library.register_kernel("aten::unsqueeze", ["spyre"])
def spyre__unsqueeze_default(self: torch.Tensor, dim: int) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::unsqueeze", "CPU")
    return kernel.call_boxed(torch._C._dispatch_keys(self), self, dim)


@torch.library.register_kernel("aten::sub.out", ["spyre"])
def spyre__sub_out(self: torch.Tensor, other: torch.Tensor, alpha: Union[int, float, bool, complex] = 1, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_sub = torch.compile(torch.sub, dynamic=False)
    return compiled_sub(self, other, alpha=alpha, out=out)


@torch.library.register_kernel("aten::sub.Tensor", ["spyre"])
def spyre__sub_Tensor(self: torch.Tensor, other: torch.Tensor, alpha: Union[int, float, bool, complex] = 1) -> torch.Tensor:
    # Standard variant
    compiled_sub = torch.compile(torch.sub, dynamic=False)
    return compiled_sub(self, other, alpha=alpha)


@torch.library.register_kernel("aten::sub.Scalar", ["spyre"])
def spyre__sub_Scalar(self: torch.Tensor, other: Union[int, float, bool, complex], alpha: Union[int, float, bool, complex] = 1) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    other_scaTensor = None
    other_scaTensor = torch.tensor([other], device="spyre")
    # Standard variant
    compiled_sub = torch.compile(torch.sub, dynamic=False)
    return compiled_sub(self, other_scaTensor, alpha)


@torch.library.register_kernel("aten::view", ["spyre"])
def spyre__view_default(self: torch.Tensor, size: list[int]) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::view", "CPU")
    return kernel.call_boxed(torch._C._dispatch_keys(self), self, size)


@torch.library.register_kernel("aten::tril.out", ["spyre"])
def spyre__tril_out(self: torch.Tensor, diagonal: int = 0, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_tril = torch.compile(torch.tril, dynamic=False)
    return compiled_tril(self, diagonal, out=out)


@torch.library.register_kernel("aten::tril", ["spyre"])
def spyre__tril_default(self: torch.Tensor, diagonal: int = 0) -> torch.Tensor:
    # Standard variant
    compiled_tril = torch.compile(torch.tril, dynamic=False)
    return compiled_tril(self, diagonal)


@torch.library.register_kernel("aten::eq.Scalar_out", ["spyre"])
def spyre__eq_Scalar_out(self: torch.Tensor, other: Union[int, float, bool, complex], out: torch.Tensor = None) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    other_scaTensor = None
    other_scaTensor = torch.tensor([other], device="spyre")
    # Out variant
    compiled_eq = torch.compile(torch.eq, dynamic=False)
    return compiled_eq(self, other_scaTensor, out=out)


@torch.library.register_kernel("aten::eq.Scalar", ["spyre"])
def spyre__eq_Scalar(self: torch.Tensor, other: Union[int, float, bool, complex]) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    other_scaTensor = None
    other_scaTensor = torch.tensor([other], device="spyre")
    # Standard variant
    compiled_eq = torch.compile(torch.eq, dynamic=False)
    return compiled_eq(self, other_scaTensor)


@torch.library.register_kernel("aten::eq.Tensor_out", ["spyre"])
def spyre__eq_Tensor_out(self: torch.Tensor, other: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_eq = torch.compile(torch.eq, dynamic=False)
    return compiled_eq(self, other, out=out)


@torch.library.register_kernel("aten::eq.Tensor", ["spyre"])
def spyre__eq_Tensor(self: torch.Tensor, other: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_eq = torch.compile(torch.eq, dynamic=False)
    return compiled_eq(self, other)


@torch.library.register_kernel("aten::ge.Scalar_out", ["spyre"])
def spyre__ge_Scalar_out(self: torch.Tensor, other: Union[int, float, bool, complex], out: torch.Tensor = None) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    other_scaTensor = None
    other_scaTensor = torch.tensor([other], device="spyre")
    # Out variant
    compiled_ge = torch.compile(torch.ge, dynamic=False)
    return compiled_ge(self, other_scaTensor, out=out)


@torch.library.register_kernel("aten::ge.Scalar", ["spyre"])
def spyre__ge_Scalar(self: torch.Tensor, other: Union[int, float, bool, complex]) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    other_scaTensor = None
    other_scaTensor = torch.tensor([other], device="spyre")
    # Standard variant
    compiled_ge = torch.compile(torch.ge, dynamic=False)
    return compiled_ge(self, other_scaTensor)


@torch.library.register_kernel("aten::ge.Tensor_out", ["spyre"])
def spyre__ge_Tensor_out(self: torch.Tensor, other: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_ge = torch.compile(torch.ge, dynamic=False)
    return compiled_ge(self, other, out=out)


@torch.library.register_kernel("aten::ge.Tensor", ["spyre"])
def spyre__ge_Tensor(self: torch.Tensor, other: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_ge = torch.compile(torch.ge, dynamic=False)
    return compiled_ge(self, other)


@torch.library.register_kernel("aten::lt.Scalar_out", ["spyre"])
def spyre__lt_Scalar_out(self: torch.Tensor, other: Union[int, float, bool, complex], out: torch.Tensor = None) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    other_scaTensor = None
    other_scaTensor = torch.tensor([other], device="spyre")
    # Out variant
    compiled_lt = torch.compile(torch.lt, dynamic=False)
    return compiled_lt(self, other_scaTensor, out=out)


@torch.library.register_kernel("aten::lt.Scalar", ["spyre"])
def spyre__lt_Scalar(self: torch.Tensor, other: Union[int, float, bool, complex]) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    other_scaTensor = None
    other_scaTensor = torch.tensor([other], device="spyre")
    # Standard variant
    compiled_lt = torch.compile(torch.lt, dynamic=False)
    return compiled_lt(self, other_scaTensor)


@torch.library.register_kernel("aten::lt.Tensor_out", ["spyre"])
def spyre__lt_Tensor_out(self: torch.Tensor, other: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_lt = torch.compile(torch.lt, dynamic=False)
    return compiled_lt(self, other, out=out)


@torch.library.register_kernel("aten::lt.Tensor", ["spyre"])
def spyre__lt_Tensor(self: torch.Tensor, other: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_lt = torch.compile(torch.lt, dynamic=False)
    return compiled_lt(self, other)


@torch.library.register_kernel("aten::maximum", ["spyre"])
def spyre__maximum_default(self: torch.Tensor, other: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_maximum = torch.compile(torch.maximum, dynamic=False)
    return compiled_maximum(self, other)


@torch.library.register_kernel("aten::maximum.out", ["spyre"])
def spyre__maximum_out(self: torch.Tensor, other: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_maximum = torch.compile(torch.maximum, dynamic=False)
    return compiled_maximum(self, other, out=out)


@torch.library.register_kernel("aten::pow.Tensor_Tensor_out", ["spyre"])
def spyre__pow_Tensor_Tensor_out(self: torch.Tensor, exponent: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_pow = torch.compile(torch.pow, dynamic=False)
    return compiled_pow(self, exponent, out=out)


@torch.library.register_kernel("aten::pow.Tensor_Tensor", ["spyre"])
def spyre__pow_Tensor_Tensor(self: torch.Tensor, exponent: torch.Tensor) -> torch.Tensor:
    # Standard variant
    compiled_pow = torch.compile(torch.pow, dynamic=False)
    return compiled_pow(self, exponent)


@torch.library.register_kernel("aten::pow.Tensor_Scalar_out", ["spyre"])
def spyre__pow_Tensor_Scalar_out(self: torch.Tensor, exponent: Union[int, float, bool, complex], out: torch.Tensor = None) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    exponent_scaTensor = None
    exponent_scaTensor = torch.tensor([exponent], device="spyre")
    # Out variant
    compiled_pow = torch.compile(torch.pow, dynamic=False)
    return compiled_pow(self, exponent_scaTensor, out=out)


@torch.library.register_kernel("aten::pow.Tensor_Scalar", ["spyre"])
def spyre__pow_Tensor_Scalar(self: torch.Tensor, exponent: Union[int, float, bool, complex]) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    exponent_scaTensor = None
    exponent_scaTensor = torch.tensor([exponent], device="spyre")
    # Standard variant
    compiled_pow = torch.compile(torch.pow, dynamic=False)
    return compiled_pow(self, exponent_scaTensor)


@torch.library.register_kernel("aten::linalg_vector_norm", ["spyre"])
def spyre__linalg_vector_norm_default(self: torch.Tensor, ord: Union[int, float, bool, complex] = 2, dim: None = None, keepdim: bool = False, dtype: None = None) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    ord_scaTensor = None
    ord_scaTensor = torch.tensor([ord], device="spyre")
    # Standard variant
    compiled_linalg_vector_norm = torch.compile(torch.linalg.vector_norm, dynamic=False)
    return compiled_linalg_vector_norm(self, ord_scaTensor, dim, keepdim, dtype=dtype)


@torch.library.register_kernel("aten::linalg_vector_norm.out", ["spyre"])
def spyre__linalg_vector_norm_out(self: torch.Tensor, ord: Union[int, float, bool, complex] = 2, dim: None = None, keepdim: bool = False, dtype: None = None, out: torch.Tensor = None) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    ord_scaTensor = None
    ord_scaTensor = torch.tensor([ord], device="spyre")
    # Out variant
    compiled_linalg_vector_norm = torch.compile(torch.linalg.vector_norm, dynamic=False)
    return compiled_linalg_vector_norm(self, ord_scaTensor, dim, keepdim, dtype=dtype, out=out)


@torch.library.register_kernel("aten::add.Scalar_out", ["spyre"])
def spyre__add_Scalar_out(self: torch.Tensor, other: Union[int, float, bool, complex], alpha: Union[int, float, bool, complex] = 1, out: torch.Tensor = None) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    other_scaTensor = None
    other_scaTensor = torch.tensor([other], device="spyre")
    # Out variant
    compiled_add = torch.compile(torch.add, dynamic=False)
    return compiled_add(self, other_scaTensor, alpha, out=out)


@torch.library.register_kernel("aten::div.Scalar_out", ["spyre"])
def spyre__div_Scalar_out(self: torch.Tensor, other: Union[int, float, bool, complex], out: torch.Tensor = None) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    other_scaTensor = None
    other_scaTensor = torch.tensor([other], device="spyre")
    # Out variant
    compiled_div = torch.compile(torch.div, dynamic=False)
    return compiled_div(self, other_scaTensor, out=out)


@torch.library.register_kernel("aten::div.Scalar_mode_out", ["spyre"])
def spyre__div_Scalar_mode_out(self: torch.Tensor, other: Union[int, float, bool, complex], rounding_mode: None, out: torch.Tensor = None) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    other_scaTensor = None
    other_scaTensor = torch.tensor([other], device="spyre")
    # Out variant
    compiled_div = torch.compile(torch.div, dynamic=False)
    return compiled_div(self, other_scaTensor, rounding_mode=rounding_mode, out=out)


@torch.library.register_kernel("aten::embedding.out", ["spyre"])
def spyre__embedding_out(weight: torch.Tensor, indices: torch.Tensor, padding_idx: int = -1, scale_grad_by_freq: bool = False, sparse: bool = False, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_embedding = torch.compile(torch.nn.functional.embedding, dynamic=False)
    return compiled_embedding(weight, indices, padding_idx, scale_grad_by_freq, sparse, out=out)


@torch.library.register_kernel("aten::mul.Scalar_out", ["spyre"])
def spyre__mul_Scalar_out(self: torch.Tensor, other: Union[int, float, bool, complex], out: torch.Tensor = None) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    other_scaTensor = None
    other_scaTensor = torch.tensor([other], device="spyre")
    # Out variant
    compiled_mul = torch.compile(torch.mul, dynamic=False)
    return compiled_mul(self, other_scaTensor, out=out)


@torch.library.register_kernel("aten::repeat.out", ["spyre"])
def spyre__repeat_out(self: torch.Tensor, repeats: list[int], out: torch.Tensor = None) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::repeat.out", "CPU")
    out = kernel.call_boxed(torch._C._dispatch_keys(self), self, repeats)
    return out


@torch.library.register_kernel("aten::relu.out", ["spyre"])
def spyre__relu_out(self: torch.Tensor, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_relu = torch.compile(torch.relu, dynamic=False)
    return compiled_relu(self, out=out)


@torch.library.register_kernel("aten::sum.out", ["spyre"])
def spyre__sum_out(self: torch.Tensor, dtype: None = None, out: torch.Tensor = None) -> torch.Tensor:
    # Out variant
    compiled_sum = torch.compile(torch.sum, dynamic=False)
    return compiled_sum(self, dtype=dtype, out=out)


@torch.library.register_kernel("aten::_unsafe_view.out", ["spyre"])
def spyre___unsafe_view_out(self: torch.Tensor, size: list[int], out: torch.Tensor = None) -> torch.Tensor:
    kernel = torch.library.get_kernel("aten::_unsafe_view.out", "CPU")
    out = kernel.call_boxed(torch._C._dispatch_keys(self), self, size)
    return out


@torch.library.register_kernel("aten::sub.Scalar_out", ["spyre"])
def spyre__sub_Scalar_out(self: torch.Tensor, other: Union[int, float, bool, complex], alpha: Union[int, float, bool, complex] = 1, out: torch.Tensor = None) -> torch.Tensor:
    # Convert scalar arguments to tensors on Spyre device
    other_scaTensor = None
    other_scaTensor = torch.tensor([other], device="spyre")
    # Out variant
    compiled_sub = torch.compile(torch.sub, dynamic=False)
    return compiled_sub(self, other_scaTensor, alpha, out=out)

# -------------------------------------------------
# This section is auto generated by codegen/gen.py.

