"""Read the exported kit's real vertex and animation data, including sparse morphs."""

import struct
from pathlib import Path

from kit_retarget import gltf_json


def glb_chunks(asset: Path):
    raw = Path(asset).read_bytes()
    length = struct.unpack_from("<I", raw, 12)[0]
    size = struct.unpack_from("<I", raw, 20 + length)[0]
    if len(raw) != struct.unpack_from("<I", raw, 8)[0] or len(raw) < 28 + length + size:
        raise ValueError(f"{asset}: truncated GLB")
    return gltf_json(Path(asset)), raw[28 + length:28 + length + size]


def accessor(document, blob, index):
    item = document["accessors"][index]
    width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[item["type"]]
    formats = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}

    def read(view_index, offset, count, component, columns):
        view = document["bufferViews"][view_index]
        start = view.get("byteOffset", 0) + offset
        fmt = "<" + formats[component] * columns
        stride = view.get("byteStride", struct.calcsize(fmt))
        return [struct.unpack_from(fmt, blob, start + i * stride) for i in range(count)]

    values = read(item["bufferView"], item.get("byteOffset", 0), item["count"], item["componentType"], width) \
        if "bufferView" in item else [(0,) * width for _ in range(item["count"])]
    if "sparse" in item:
        sparse = item["sparse"]
        indices, data = sparse["indices"], sparse["values"]
        rows = read(indices["bufferView"], indices.get("byteOffset", 0), sparse["count"], indices["componentType"], 1)
        patches = read(data["bufferView"], data.get("byteOffset", 0), sparse["count"], item["componentType"], width)
        for (row,), value in zip(rows, patches):
            values[row] = value
    if item.get("normalized", False):
        component = item["componentType"]
        divisor = {5120: 127, 5121: 255, 5122: 32767, 5123: 65535}[component]
        values = [tuple(max(-1.0, value / divisor) for value in row) for row in values]
    return values
