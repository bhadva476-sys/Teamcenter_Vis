"""Aspose-backed JT conversion and cache helpers."""

import hashlib
from pathlib import Path

from flask import current_app

CONVERTER_VERSION = "aspose-pbr-v1"
MIMETYPES = {"glb": "model/gltf-binary", "gltf": "model/gltf+json", "zip": "application/zip"}


class NoPreviewDataError(Exception):
    """The JT file has no usable geometry for a browser preview."""


def check_preview_geometry(scene):
    """Raise when a JT scene has no renderable mesh geometry."""
    mesh_count = 0

    def walk(node):
        nonlocal mesh_count
        entity = node.entity
        if entity is not None and hasattr(entity, "control_points"):
            vertices = len(entity.control_points)
            polygons = getattr(entity, "polygon_count", 0)
            if vertices > 0 and polygons > 0:
                mesh_count += 1
        for child in node.child_nodes:
            walk(child)

    walk(scene.root_node)
    if mesh_count == 0:
        raise NoPreviewDataError(
            "This JT file does not contain usable 3D geometry."
        )


def load_aspose():
    """Return (module, None) or (None, readable error). Imported lazily so /health can report problems."""
    try:
        import aspose.threed as a3d
        return a3d, None
    except Exception as e:  # ImportError, missing DLLs, unsupported Python, ...
        return None, f"{type(e).__name__}: {e}"


def _legacy_rgb(old):
    """Pull an RGB triple out of a CAD/legacy material, or None if it has no usable color."""
    for attr in ("diffuse_color", "albedo", "ambient_color", "specular_color"):
        val = getattr(old, attr, None)
        if val is not None and hasattr(val, "x"):
            return val.x, val.y, val.z
    return None


def convert_jt(src: Path, dst: Path) -> dict:
    """
    Convert .jt to .glb/.gltf (format chosen by dst's extension).

    Materials that Aspose read from the JT are converted to glTF PBR materials so the
    color survives in the browser. Colors that Aspose did NOT read cannot be recovered here.
    Returns a small stats dict (also logged).
    """
    a3d, err = load_aspose()
    if a3d is None:
        raise RuntimeError(f"Aspose.3D could not be loaded ({err})")

    scene = a3d.Scene.from_file(str(src))
    check_preview_geometry(scene)
    stats = {"nodes": 0, "with_material": 0, "converted": 0}

    def walk(node):
        stats["nodes"] += 1
        old = node.material  # first material of the node, or None
        if old is not None:
            stats["with_material"] += 1
            already_pbr = isinstance(old, a3d.shading.PbrMaterial)
            rgb = None if already_pbr else _legacy_rgb(old)
            if rgb is not None:
                pbr = a3d.shading.PbrMaterial()
                pbr.albedo = a3d.utilities.Vector3(rgb[0], rgb[1], rgb[2])
                pbr.metallic_factor = 0.1
                pbr.roughness_factor = 0.5
                pbr.name = getattr(old, "name", None) or "MappedMaterial"
                node.material = pbr
                stats["converted"] += 1
        for child in node.child_nodes:
            walk(child)

    walk(scene.root_node)

    if stats["with_material"] == 0:
        current_app.logger.warning(
            "Aspose found NO materials in %s - the .glb will have no color. "
            "A JT reader that supports colors is needed for this file.", src.name
        )
    else:
        current_app.logger.info("JT materials: %s", stats)

    # The format is picked from the file extension (.glb / .gltf)
    scene.save(str(dst))

    if not dst.exists():
        raise RuntimeError("Conversion finished but no output file was produced.")
    return stats

def file_digest(file) -> str:
    """SHA-256 of the uploaded file's contents plus the converter version."""
    h = hashlib.sha256()
    for chunk in iter(lambda: file.stream.read(1024 * 1024), b""):
        h.update(chunk)
    file.stream.seek(0)  # rewind so file.save() still works
    h.update(CONVERTER_VERSION.encode())
    return h.hexdigest()
