# SPDX-License-Identifier: Apache-2.0

"""Quantization detection and resource estimation for model providers.

Provides pattern-based quantization format detection from model identifiers,
hardware resource introspection, and heuristic memory estimation.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class QuantizationResult:
    """Result of quantization detection from a model identifier."""

    format: str
    level: str
    bits: float


_GGUF_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"q2_k", re.I), "Q2_K", 2.0),
    (re.compile(r"q3_k_s", re.I), "Q3_K_S", 3.35),
    (re.compile(r"q3_k_m", re.I), "Q3_K_M", 3.5),
    (re.compile(r"q3_k_l", re.I), "Q3_K_L", 3.85),
    (re.compile(r"q4_k_s", re.I), "Q4_K_S", 4.0),
    (re.compile(r"q4_k_m", re.I), "Q4_K_M", 4.5),
    (re.compile(r"q4_0"), "Q4_0", 4.0),
    (re.compile(r"q4_1"), "Q4_1", 4.5),
    (re.compile(r"q5_k_s", re.I), "Q5_K_S", 5.0),
    (re.compile(r"q5_k_m", re.I), "Q5_K_M", 5.5),
    (re.compile(r"q5_0"), "Q5_0", 5.0),
    (re.compile(r"q5_1"), "Q5_1", 5.5),
    (re.compile(r"q6_k", re.I), "Q6_K", 6.0),
    (re.compile(r"q8_0"), "Q8_0", 8.0),
    (re.compile(r"f16"), "F16", 16.0),
    (re.compile(r"f32"), "F32", 32.0),
]

_AWQ_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"(?:^|\b)awq(?:$|\b)", re.I), "AWQ", 4.0),
    (re.compile(r"w4a16", re.I), "W4A16", 4.0),
]

_GPTQ_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"gptq", re.I), "GPTQ", 4.0),
    (re.compile(r"3bit", re.I), "GPTQ-3bit", 3.0),
]

_BITSANDBYTES_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"nf4", re.I), "NF4", 4.0),
    (re.compile(r"fp4", re.I), "FP4", 4.0),
    (re.compile(r"8bit", re.I), "8-bit", 8.0),
]


def detect_from_name(model_id: str) -> QuantizationResult | None:
    """Detect quantization from a model identifier string.

    Tries each quantization format group in priority order:
    bitsandbytes, AWQ, EXL2, GPTQ, GGUF.
    """
    for pat, level, bits in _BITSANDBYTES_PATTERNS:
        if pat.search(model_id):
            return QuantizationResult(format="bitsandbytes", level=level, bits=bits)

    for pat, level, bits in _AWQ_PATTERNS:
        if pat.search(model_id):
            return QuantizationResult(format="awq", level=level, bits=bits)

    exl2 = _detect_exl2(model_id)
    if exl2:
        return exl2

    for pat, level, bits in _GPTQ_PATTERNS:
        if pat.search(model_id):
            return QuantizationResult(format="gptq", level=level, bits=bits)

    for pat, level, bits in _GGUF_PATTERNS:
        if pat.search(model_id):
            return QuantizationResult(format="gguf", level=level, bits=bits)

    # Catch-all generic bit patterns
    if re.search(r"4bit", model_id, re.I):
        return QuantizationResult(format="gptq", level="GPTQ-4bit", bits=4.0)

    return None


def detect_from_ollama_details(details: dict[str, Any]) -> QuantizationResult | None:
    """Detect quantization from an Ollama model details dict.

    Olama returns ``quantization_level`` as a string like ``"Q4_0"``,
    ``"Q4_K_M"``, ``"F16"``, etc.
    """
    q_level = details.get("quantization_level")
    if not q_level:
        return None
    bits = _bits_for_quant_level(q_level)
    return QuantizationResult(format="gguf", level=q_level, bits=bits)


def _detect_exl2(model_id: str) -> QuantizationResult | None:
    m = re.search(r"(\d+(?:\.\d+)?)bpw", model_id, re.I)
    if m:
        bits = float(m.group(1))
        return QuantizationResult(format="exl2", level=f"EXL2-{bits}bpw", bits=bits)
    return None


@dataclass
class SystemResources:
    """Available system hardware resources."""

    total_ram_gb: float
    available_ram_gb: float
    vram_gb: float | None
    cpu_count: int


def get_system_resources() -> SystemResources:
    """Detect available system resources with optional psutil and nvidia-smi."""
    try:
        import psutil

        mem = psutil.virtual_memory()
        total_ram = mem.total / (1024**3)
        available_ram = mem.available / (1024**3)
    except ImportError:
        total_ram = 0.0
        available_ram = 0.0

    return SystemResources(
        total_ram_gb=round(total_ram, 1),
        available_ram_gb=round(available_ram, 1),
        vram_gb=_get_vram_gb(),
        cpu_count=os.cpu_count() or 0,
    )


def _get_vram_gb() -> float | None:
    try:
        import subprocess

        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            total = sum(
                int(line.strip()) for line in result.stdout.strip().split("\n") if line.strip()
            )
            return round(total / 1024, 1)
    except Exception:
        pass
    return None


_KNOWN_PARAM_SIZES: list[tuple[str, float]] = [
    ("405b", 405.0),
    ("180b", 180.0),
    ("175b", 175.0),
    ("120b", 120.0),
    ("70b", 70.0),
    ("34b", 34.0),
    ("30b", 30.0),
    ("20b", 20.0),
    ("13b", 13.0),
    ("12b", 12.0),
    ("8b", 8.0),
    ("7b", 7.0),
    ("6b", 6.0),
    ("3b", 3.0),
    ("2b", 2.0),
    ("1b", 1.0),
]


def _extract_param_count(model_id: str) -> float:
    lower = model_id.lower()
    for size, count in _KNOWN_PARAM_SIZES:
        if size in lower:
            return count
    return 7.0


def _bits_for_quant_level(level: str) -> float:
    upper = level.upper()
    mapping: dict[str, float] = {
        "Q2_K": 2.0,
        "Q3_K_S": 3.35,
        "Q3_K_M": 3.5,
        "Q3_K_L": 3.85,
        "Q4_0": 4.0,
        "Q4_1": 4.5,
        "Q4_K_S": 4.0,
        "Q4_K_M": 4.5,
        "Q5_0": 5.0,
        "Q5_1": 5.5,
        "Q5_K_S": 5.0,
        "Q5_K_M": 5.5,
        "Q6_K": 6.0,
        "Q8_0": 8.0,
        "F16": 16.0,
        "F32": 32.0,
    }
    return mapping.get(upper, 0.0)


def estimate_model_memory_gb(model_id: str, quantization: str | None = None) -> float:
    """Estimate model memory usage in GB from model id and optional quantization level.

    Uses heuristic: params_b * bytes_per_param * 1.1 (10% KV cache overhead).
    Assumes FP16 (2 bytes/param) for unquantized models.
    """
    params_b = _extract_param_count(model_id)

    if quantization:
        upper = quantization.upper()
        if upper == "F32":
            bytes_per_param = 4.0
        elif upper == "F16":
            bytes_per_param = 2.0
        else:
            bits = _bits_for_quant_level(quantization)
            bytes_per_param = bits / 8.0 if bits > 0 else 2.0
    else:
        bytes_per_param = 2.0

    model_gb = params_b * bytes_per_param * 1.1
    return round(model_gb, 1)


def is_unquantized(quantization: str | None) -> bool:
    """Return True if the model is unquantized (no quantization marker found)."""
    return quantization is None


def check_resource_warning(model_id: str, quantization: str | None) -> str | None:
    """Return a warning string if the model may exceed available memory.

    Only warns for unquantized or FP16/FP32 models when estimated memory
    exceeds 80% of available RAM/VRAM.
    """
    if quantization:
        upper = quantization.upper()
        if upper not in ("F16", "F32"):
            return None

    resources = get_system_resources()
    estimated = estimate_model_memory_gb(model_id, quantization)
    available = resources.vram_gb or resources.available_ram_gb

    if available > 0 and estimated > available * 0.8:
        return (
            f"Model {model_id} may be too large for available memory. "
            f"Estimated: {estimated} GB, Available: {available} GB. "
            "Consider using a quantized version (e.g., GGUF Q4_K_M)."
        )
    return None
