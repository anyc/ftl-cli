"""
Low-level binary primitives used by FTL's ae_prof.sav format.

Mirrors net.blerf.ftl.parser.Parser from the Java FTL Profile Editor:
- 32-bit little-endian ints
- booleans stored as 0/1 ints
- strings stored as (int length-in-bytes)(raw bytes), windows-1252
  before FTL 1.6.1, UTF-8 from FTL 1.6.1 onward.
"""

from __future__ import annotations

import struct
from typing import BinaryIO


class ProfileFormatError(ValueError):
	"""Raised when the profile data doesn't match the expected binary layout."""


def read_int(f: BinaryIO) -> int:
	data = f.read(4)
	if len(data) < 4:
		raise ProfileFormatError("End of stream reached before reading enough bytes for an int")
	return struct.unpack("<i", data)[0]


def write_int(f: BinaryIO, value: int) -> None:
	f.write(struct.pack("<i", value))


def read_bool(f: BinaryIO) -> bool:
	i = read_int(f)
	if i not in (0, 1):
		raise ProfileFormatError(f"Not a bool: {i}")
	return i == 1


def write_bool(f: BinaryIO, value: bool) -> None:
	write_int(f, 1 if value else 0)


def read_string(f: BinaryIO, unicode_strings: bool) -> str:
	length = read_int(f)
	if length < 0:
		raise ProfileFormatError(f"Negative string length: {length}")
	data = f.read(length)
	if len(data) < length:
		raise ProfileFormatError(
			f"End of stream reached before reading enough bytes for string of length {length}"
		)
	encoding = "utf-8" if unicode_strings else "windows-1252"
	return data.decode(encoding)


def write_string(f: BinaryIO, value: str, unicode_strings: bool) -> None:
	encoding = "utf-8" if unicode_strings else "windows-1252"
	data = value.encode(encoding)
	write_int(f, len(data))
	f.write(data)
