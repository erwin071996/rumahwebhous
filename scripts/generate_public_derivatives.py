"""Artifact-only derivatives of two pinned public originals. No website writes."""
from __future__ import annotations
import argparse
import base64
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime, timezone

SOURCE_SHA = "ab9335cb8a80039eb710c0231167c6d490d66e37"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "public-derivatives"
SOURCES = {
    "logo": {"path": "public_html/assets/branding/logo-3dkan-original.jpg",
             "bytes": 191744, "sha256": "2072e61fb6c1391a8c893dd9f37dcb95846220c6d9a4118d4b72ec83b84405d0",
             "blob": "4a9becc3852f3ee595c921ab5acf6af6b08b3500", "size": (2048, 654), "format": "JPEG"},
    "cimb": {"path": "public_html/assets/portfolio-real/clean/cimb-niaga-signage-atm.webp",
             "bytes": 612162, "sha256": "501e6f982db106e44c739b40dcf9416ae31692651c277a00980b3d0b80edf476",
             "blob": "013fe16bf49cd75352382ece665f1ca7d129e8c4", "size": (1012, 1800), "format": "WEBP"},
}
VARIANTS = (("logo", 688, "logo-3dkan-688.webp"),
            ("cimb", 480, "cimb-niaga-signage-atm-480.webp"),
            ("cimb", 768, "cimb-niaga-signage-atm-768.webp"))
TARGETS = {
    "logo-3dkan-688.webp": "public_html/assets/branding/logo-3dkan-688.webp",
    "cimb-niaga-signage-atm-480.webp": "public_html/assets/portfolio-real/responsive/cimb-niaga-signage-atm-480.webp",
    "cimb-niaga-signage-atm-768.webp": "public_html/assets/portfolio-real/responsive/cimb-niaga-signage-atm-768.webp",
}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()

def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=30, check=False)
    if result.returncode:
        raise RuntimeError("Pinned Git source read failed")
    return result.stdout

def validate_source(data, spec):
    if len(data) != spec["bytes"] or sha(data) != spec["sha256"] or git_blob(data) != spec["blob"]:
        raise ValueError("Original source byte identity failed: " + spec["path"])
    if len(data) > 2_000_000:
        raise ValueError("Original source exceeds fixed byte cap")
    from PIL import Image
    with Image.open(BytesIO(data)) as image:
        if image.format != spec["format"] or image.size != tuple(spec["size"]):
            raise ValueError("Original source format/dimensions failed")
        if image.mode != "RGB" or getattr(image, "n_frames", 1) != 1:
            raise ValueError("Only one-frame RGB originals are allowed; no color conversion")
        if image.getexif().get(274, 1) != 1:
            raise ValueError("Unexpected source orientation; no automatic rotation")
        profile = image.info.get("icc_profile", b"")
        if profile and (not isinstance(profile, bytes) or len(profile) > 1_000_000):
            raise ValueError("Invalid source profile")
        image.load()
        decoded = image.copy()
    return decoded, profile or b""

def read_source(spec):
    reference = SOURCE_SHA + ":" + spec["path"]
    if git("rev-parse", reference).decode("ascii").strip() != spec["blob"]:
        raise ValueError("Pinned source Git blob changed")
    if int(git("cat-file", "-s", spec["blob"]).decode("ascii")) != spec["bytes"]:
        raise ValueError("Pinned source Git size changed")
    data = git("show", reference)
    image, profile = validate_source(data, spec)
    return data, image, profile

def target_size(size, width):
    if not isinstance(width, int) or width <= 0 or width > size[0]:
        raise ValueError("Target width must be positive and cannot upscale")
    return width, round(size[1] * width / size[0])

def encode_variant(image, profile, width, lossless):
    from PIL import Image, ImageChops, ImageStat
    size = target_size(image.size, width)
    resized = image.resize(size, Image.Resampling.LANCZOS)
    settings = {"lossless": lossless, "quality": 100 if lossless else 90,
                "method": 6, "exact": True}
    buffer = BytesIO()
    resized.save(buffer, format="WEBP", icc_profile=profile, **settings)
    data = buffer.getvalue()
    if len(data) > 1_500_000 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("Derivative WebP container/size failed")
    with Image.open(BytesIO(data)) as decoded:
        decoded.load()
        if decoded.size != size or decoded.mode != "RGB":
            raise ValueError("Derivative dimensions/mode failed")
        if (decoded.info.get("icc_profile", b"") or b"") != profile:
            raise ValueError("Derivative profile was not preserved byte-for-byte")
        pixels = decoded.copy()
    difference = ImageChops.difference(resized, pixels)
    exact_pixels = resized.tobytes() == pixels.tobytes()
    if lossless and not exact_pixels:
        raise ValueError("Lossless logo round-trip changed resized pixels")
    delta = ImageStat.Stat(difference)
    return data, pixels, {"dimensions": list(size), "bytes": len(data), "sha256": sha(data),
                          "gitBlob": git_blob(data), "encoding": settings,
                          "iccBytes": len(profile), "iccSha256": sha(profile) if profile else None,
                          "losslessPixelEqualityToResample": exact_pixels,
                          "meanAbsoluteChannelDifference": delta.mean,
                          "maxChannelDifference": [bounds[1] for bounds in difference.getextrema()]}

def assert_output_root(output=OUTPUT):
    if not output.is_absolute() or output != ROOT / "artifacts" / "public-derivatives":
        raise ValueError("Only the fixed artifact directory is allowed")
    if not output.resolve().is_relative_to((ROOT / "artifacts").resolve()):
        raise ValueError("Artifact output escaped root")
    for parent in (ROOT / "artifacts", output):
        if parent.is_symlink():
            raise ValueError("Artifact path cannot be a symlink")

def write_new(name, data):
    if Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError("Artifact filename must be one component")
    target = OUTPUT / name
    if target.exists() or target.is_symlink():
        raise ValueError("Artifact already exists; nothing will be overwritten")
    with target.open("xb") as stream:
        stream.write(data)
    if sha(target.read_bytes()) != sha(data):
        raise ValueError("Written artifact digest differs")

def comparison_sheet(images, labels, width, profile):
    from PIL import Image, ImageDraw
    height = round(images[0].height * width / images[0].width)
    canvas = Image.new("RGB", (len(images) * (width + 24) + 24, height + 72), "white")
    draw = ImageDraw.Draw(canvas)
    for index, (image, label) in enumerate(zip(images, labels)):
        frame = image.resize((width, height), Image.Resampling.LANCZOS)
        left = 24 + index * (width + 24)
        draw.text((left, 16), label, fill="black")
        canvas.paste(frame, (left, 48))
    buffer = BytesIO()
    canvas.save(buffer, format="PNG", icc_profile=profile)
    return buffer.getvalue()

def emit_transfer(records, payloads):
    allowed = {name for _, _, name in VARIANTS}
    if (set(payloads) != allowed or len(records) != len(allowed)
            or {record.get("artifact") for record in records} != allowed):
        raise ValueError("Public transfer allowlist mismatch")
    # Validate every public record before any byte is emitted.
    for record in records:
        name = record["artifact"]
        data = payloads[name]
        if (record.get("targetPath") != TARGETS[name] or sha(data) != record["sha256"]
                or len(data) != record["bytes"] or git_blob(data) != record["gitBlob"]):
            raise ValueError("Public transfer output identity failed")
        if (data[:4] != b"RIFF" or data[8:12] != b"WEBP"
                or int.from_bytes(data[4:8], "little") != len(data) - 8):
            raise ValueError("Public transfer WebP container failed")
    for record in records:
        name = record["artifact"]
        data = payloads[name]
        encoded = base64.b64encode(data).decode("ascii")
        chunks = [encoded[index:index + 10000] for index in range(0, len(encoded), 10000)]
        for index, chunk in enumerate(chunks):
            line = "DERIVATIVE_TRANSFER " + json.dumps({"schemaVersion": 1, "sourceCommit": SOURCE_SHA,
                    "path": TARGETS[name], "artifact": name, "index": index, "count": len(chunks), "bytes": len(data),
                    "sha256": record["sha256"], "gitBlob": record["gitBlob"], "base64": chunk},
                    separators=(",", ":"))
            if len(line) > 12000:
                raise ValueError("Public transfer line exceeds bound")
            print(line, flush=True)

def main(emit_public_transfer=False):
    import PIL
    from PIL import features
    if PIL.__version__ != "12.3.0" or sys.version_info < (3, 10):
        raise RuntimeError("Pinned Pillow 12.3.0 and Python >=3.10 required")
    if not features.check("webp"):
        raise RuntimeError("This pinned Pillow wheel lacks WebP support")
    assert_output_root()
    git("cat-file", "-e", SOURCE_SHA + "^{commit}")
    inputs = {key: read_source(spec) for key, spec in SOURCES.items()}
    payloads, outputs, decoded = {}, [], {}
    for kind, width, name in VARIANTS:
        original, image, profile = inputs[kind]
        data, pixels, record = encode_variant(image, profile, width, kind == "logo")
        record.update({"artifact": name, "targetPath": TARGETS[name], "sourceKind": kind, "sourcePath": SOURCES[kind]["path"],
                       "sourceBytes": len(original), "sourceSha256": sha(original),
                       "sourceDimensions": list(image.size),
                       "savedBytes": len(original) - len(data),
                       "savedPercent": 100 * (1 - len(data) / len(original))})
        payloads[name], decoded[name] = data, pixels
        outputs.append(record)
    sheets = {
        "logo-comparison.png": comparison_sheet(
            [inputs["logo"][1], decoded["logo-3dkan-688.webp"]],
            ["Original whole lockup (display resample)", "688px lossless WebP"],
            688, inputs["logo"][2]),
        "cimb-comparison.png": comparison_sheet(
            [inputs["cimb"][1], decoded["cimb-niaga-signage-atm-480.webp"], decoded["cimb-niaga-signage-atm-768.webp"]],
            ["Original whole photo (display resample)", "480px WebP quality 90", "768px WebP quality 90"],
            480, inputs["cimb"][2]),
    }
    for key, spec in SOURCES.items():
        if git("show", SOURCE_SHA + ":" + spec["path"]) != inputs[key][0]:
            raise ValueError("Original Git source unexpectedly changed")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, data in {**payloads, **sheets}.items():
        write_new(name, data)
    report = {
        "sourceCommit": SOURCE_SHA, "generatorCommit": git("rev-parse", "HEAD").decode("ascii").strip(),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "runtime": {"python": sys.version, "pillow": PIL.__version__, "libwebp": features.version("webp"),
                    "platform": platform.platform(), "machine": platform.machine(),
                    "imageOS": os.environ.get("ImageOS"), "imageVersion": os.environ.get("ImageVersion")},
        "sources": SOURCES, "outputs": outputs,
        "sheets": [{"artifact": name, "bytes": len(data), "sha256": sha(data)} for name, data in sheets.items()],
        "transform": "Full frame LANCZOS resize with rounded integer height; specified WebP encoding. No crop, rotation, redraw or intentional palette/color transform. ICC preserved byte-for-byte when present.",
        "limitations": ["Logo lossless equality is to the resized RGB reference, not original dimensions.",
                        "Photo quality90 is lossy; channel differences are measured against the resized RGB reference.",
                        "Comparison sheet scales complete frames for display; it is not a substitute for native UI/print pixel review.",
                        "No HTML references, website files or original Git blobs are written."]
    }
    write_new("derivative-report.json", (json.dumps(report, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"status": "PASS", "sourceCommit": SOURCE_SHA, "outputs": outputs,
                      "artifactDirectory": str(OUTPUT.relative_to(ROOT)), "visualReview": "PENDING"}, indent=2))
    if emit_public_transfer:
        emit_transfer(outputs, payloads)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emit-public-transfer", action="store_true",
                        help="Emit only the three verified public WebP outputs as bounded base64 log records.")
    main(parser.parse_args().emit_public_transfer)
