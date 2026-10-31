"""Minimal Electron asar reader/writer (no Node needed).

Layout: [u32 4][u32 hdrPickleSize] [u32 hdrPayload][u32 jsonLen][json + pad to 4] [file data...]
"""
import json
import os
import struct


def read(path):
    """Returns (header, data_offset, file handle)."""
    f = open(path, "rb")
    head = f.read(16)
    json_len = struct.unpack("<I", head[12:16])[0]
    header = json.loads(f.read(json_len))
    base = 16 + (json_len + 3) // 4 * 4
    return header, base, f


def walk(node, prefix=""):
    for name, entry in node.get("files", {}).items():
        path = prefix + "/" + name if prefix else name
        if "files" in entry:
            yield from walk(entry, path)
        else:
            yield path, entry


def extract(asar_path, out_dir):
    """Extracts packed files; entries marked unpacked stay in app.asar.unpacked."""
    header, base, f = read(asar_path)
    count = 0
    with f:
        for path, entry in walk(header):
            if entry.get("unpacked") or "link" in entry:
                continue
            target = os.path.join(out_dir, *path.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            f.seek(base + int(entry["offset"]))
            with open(target, "wb") as out:
                out.write(f.read(entry["size"]))
            count += 1
    with open(os.path.join(out_dir, ".asar-header.json"), "w") as out:
        json.dump(header, out)
    return count


def pack(src_dir, asar_path):
    """Repacks src_dir, keeping the unpacked/link entries of the original header."""
    with open(os.path.join(src_dir, ".asar-header.json")) as fh:
        original = json.load(fh)
    blobs = []
    offset = 0

    def build(node, rel):
        nonlocal offset
        out = {"files": {}}
        for name, entry in node.get("files", {}).items():
            child = rel + "/" + name if rel else name
            if "files" in entry:
                out["files"][name] = build(entry, child)
            elif entry.get("unpacked") or "link" in entry:
                out["files"][name] = entry
            else:
                disk = os.path.join(src_dir, *child.split("/"))
                size = os.path.getsize(disk)
                item = {"size": size, "offset": str(offset)}
                if entry.get("executable"):
                    item["executable"] = True
                out["files"][name] = item
                blobs.append(disk)
                offset += size
        return out

    header = build(original, "")
    # Files the mod adds (not in the original header).
    for extra in _added_files(src_dir, original):
        node = header
        parts = extra.split("/")
        for part in parts[:-1]:
            node = node["files"].setdefault(part, {"files": {}})
        disk = os.path.join(src_dir, *parts)
        size = os.path.getsize(disk)
        node["files"][parts[-1]] = {"size": size, "offset": str(offset)}
        blobs.append(disk)
        offset += size

    raw = json.dumps(header, separators=(",", ":")).encode("utf-8")
    padded = raw + b"\0" * ((4 - len(raw) % 4) % 4)
    payload = struct.pack("<I", len(raw)) + padded
    pickle = struct.pack("<I", len(payload)) + payload
    tmp = asar_path + ".tmp"
    with open(tmp, "wb") as out:
        out.write(struct.pack("<II", 4, len(pickle)))
        out.write(pickle)
        for disk in blobs:
            with open(disk, "rb") as fh:
                while True:
                    chunk = fh.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
    os.replace(tmp, asar_path)


def _added_files(src_dir, header):
    known = {p for p, _ in walk(header)}
    for root, _, files in os.walk(src_dir):
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), src_dir).replace(os.sep, "/")
            if rel != ".asar-header.json" and rel not in known:
                yield rel
