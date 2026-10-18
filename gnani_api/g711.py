"""Vectorised ITU-T G.711 mu-law and A-law codecs (same bit layout as the old ``audioop`` module).

Used to decode Timbre's raw ``container=mulaw``/``alaw`` output (born-narrowband attacks, G3) and by
the mock backend to produce it.
"""

from __future__ import annotations

import numpy as np

_MU_BIAS = 0x84
_MU_CLIP = 32635


def encode_mulaw(pcm16: np.ndarray) -> bytes:
    # Same arithmetic as the reference (Sun g711.c): work on 14-bit values, bias 0x21.
    x = np.asarray(pcm16, dtype=np.int32) >> 2
    sign = np.where(x < 0, 0x80, 0)
    mag = np.minimum(np.abs(x), _MU_CLIP >> 2) + (_MU_BIAS >> 2)
    seg = np.clip(np.floor(np.log2(np.maximum(mag, 1))).astype(np.int32) - 5, 0, 7)
    mant = (mag >> (seg + 1)) & 0x0F
    return (~(sign | (seg << 4) | mant) & 0xFF).astype(np.uint8).tobytes()


def decode_mulaw(data: bytes) -> np.ndarray:
    u = ~np.frombuffer(data, dtype=np.uint8).astype(np.int32) & 0xFF
    seg = (u >> 4) & 0x07
    mag = (((u & 0x0F) << 3) + _MU_BIAS) << seg
    return np.where(u & 0x80, _MU_BIAS - mag, mag - _MU_BIAS).astype(np.int16)


def encode_alaw(pcm16: np.ndarray) -> bytes:
    x = np.asarray(pcm16, dtype=np.int32) >> 3  # A-law works on 13-bit magnitudes
    sign = np.where(x >= 0, 0x80, 0)
    mag = np.where(x >= 0, x, -x - 1)
    mag = np.minimum(mag, 0x0FFF)
    seg = np.where(mag < 32, 0, np.clip(np.floor(np.log2(np.maximum(mag, 1))).astype(np.int32) - 4, 1, 7))
    mant = np.where(seg == 0, mag >> 1, mag >> seg) & 0x0F
    return ((sign | (seg << 4) | mant) ^ 0x55).astype(np.uint8).tobytes()


def decode_alaw(data: bytes) -> np.ndarray:
    a = np.frombuffer(data, dtype=np.uint8).astype(np.int32) ^ 0x55
    seg = (a >> 4) & 0x07
    mant = a & 0x0F
    mag = np.where(seg == 0, (mant << 4) + 8, ((mant << 4) + 0x108) << np.maximum(seg - 1, 0))
    return np.where(a & 0x80, mag, -mag).astype(np.int16)
