"""Standard-library guards by default; codec checks explicitly opt in after pinning Pillow."""
import base64
from io import BytesIO
import json
import os
from pathlib import Path
import unittest
from unittest import mock
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("derivatives", ROOT / "scripts/generate_public_derivatives.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def transfer_fixture():
    payloads, records = {}, []
    for _, _, name in module.VARIANTS:
        # Synthetic RIFF envelope tests transfer framing, not image encoding.
        data = b"RIFF" + (21004).to_bytes(4, "little") + b"WEBP" + b"x" * 21000
        payloads[name] = data
        records.append({"artifact": name, "targetPath": module.TARGETS[name], "bytes": len(data),
                        "sha256": module.sha(data), "gitBlob": module.git_blob(data)})
    return payloads, records

class StandardLibraryTests(unittest.TestCase):
    def test_import_needs_no_pillow(self):
        with mock.patch("builtins.__import__", side_effect=lambda name, *a, **k: (
                (_ for _ in ()).throw(AssertionError("Unexpected Pillow import"))
                if name == "PIL" or name.startswith("PIL.") else original_import(name, *a, **k))):
            fresh = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(fresh)

    def test_hash_known_values(self):
        self.assertEqual(module.sha(b"abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        self.assertEqual(module.git_blob(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")

    def test_corrupt_source_rejected_before_optional_decoder(self):
        definition = {"path": "synthetic.png", "bytes": 1, "sha256": module.sha(b"a"),
                      "blob": module.git_blob(b"a")}
        with self.assertRaisesRegex(ValueError, "byte identity"):
            module.validate_source(b"changed", definition)

    def test_wrong_blob_rejected_before_optional_decoder(self):
        definition = {"path": "synthetic.png", "bytes": 1, "sha256": module.sha(b"a"), "blob": "0" * 40}
        with self.assertRaisesRegex(ValueError, "byte identity"):
            module.validate_source(b"a", definition)

    def test_proportional_targets_and_no_upscale(self):
        self.assertEqual(module.target_size((2048, 654), 688), (688, 220))
        self.assertEqual(module.target_size((1012, 1800), 480), (480, 854))
        self.assertEqual(module.target_size((1012, 1800), 768), (768, 1366))
        with self.assertRaises(ValueError):
            module.target_size((16, 8), 17)

    def test_output_outside_artifacts_rejected(self):
        with self.assertRaisesRegex(ValueError, "fixed artifact"):
            module.assert_output_root(ROOT / "public_html")

    def test_transfer_roundtrip_and_bound(self):
        payloads, records = transfer_fixture()
        printed = []
        with mock.patch("builtins.print", side_effect=lambda line, **kwargs: printed.append(line)):
            module.emit_transfer(records, payloads)
        rows = [json.loads(line.split(" ", 1)[1]) for line in printed]
        self.assertTrue(all(len(line) <= 12000 for line in printed))
        for name, data in payloads.items():
            chunks = sorted([row for row in rows if row["artifact"] == name], key=lambda row: row["index"])
            self.assertEqual(len(chunks), chunks[0]["count"])
            self.assertEqual(chunks[0]["path"], module.TARGETS[name])
            self.assertEqual(base64.b64decode("".join(row["base64"] for row in chunks), validate=True), data)

    def test_transfer_rejects_foreign_output(self):
        with self.assertRaisesRegex(ValueError, "allowlist"):
            module.emit_transfer([], {"private.txt": b"never emit"})

    def test_transfer_rejects_missing_or_duplicate_records(self):
        payloads, records = transfer_fixture()
        with self.assertRaisesRegex(ValueError, "allowlist"):
            module.emit_transfer(records[:2], payloads)
        with self.assertRaisesRegex(ValueError, "allowlist"):
            module.emit_transfer([records[0], records[0], records[2]], payloads)

    def test_transfer_rejects_changed_identity_before_any_output(self):
        payloads, records = transfer_fixture()
        records[-1] = {**records[-1], "sha256": "0" * 64}
        with mock.patch("builtins.print") as printer:
            with self.assertRaisesRegex(ValueError, "identity"):
                module.emit_transfer(records, payloads)
            printer.assert_not_called()

    def test_transfer_rejects_wrong_git_blob(self):
        payloads, records = transfer_fixture()
        records[0] = {**records[0], "gitBlob": "0" * 40}
        with self.assertRaisesRegex(ValueError, "identity"):
            module.emit_transfer(records, payloads)

    def test_transfer_rejects_non_webp_even_matching_hash(self):
        payloads, records = transfer_fixture()
        name = records[0]["artifact"]
        data = b"public-only"
        payloads[name] = data
        records[0] = {**records[0], "bytes": len(data), "sha256": module.sha(data), "gitBlob": module.git_blob(data)}
        with self.assertRaisesRegex(ValueError, "container"):
            module.emit_transfer(records, payloads)

original_import = __import__

@unittest.skipUnless(os.environ.get("DERIVATIVE_CODEC_TESTS") == "1", "Artifact CI explicitly opts into pinned Pillow codec checks")
class CodecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import PIL
        from PIL import Image
        if PIL.__version__ != "12.3.0":
            raise RuntimeError("Codec checks require pinned Pillow 12.3.0")
        cls.Image = Image

    def synthetic(self):
        image = self.Image.new("RGB", (16, 8))
        image.putdata([(x * 13 % 256, y * 29 % 256, (x + y) * 7 % 256) for y in range(8) for x in range(16)])
        buffer = BytesIO()
        image.save(buffer, "PNG")
        data = buffer.getvalue()
        definition = {"path": "synthetic-only.png", "bytes": len(data), "sha256": module.sha(data),
                      "blob": module.git_blob(data), "size": image.size, "format": "PNG"}
        return image, data, definition

    def test_wrong_dimensions_rejected(self):
        _, data, definition = self.synthetic()
        with self.assertRaisesRegex(ValueError, "format/dimensions"):
            module.validate_source(data, {**definition, "size": (32, 16)})

    def test_lossless_roundtrip_resample_and_profile(self):
        image, _, _ = self.synthetic()
        profile = b"synthetic-opaque-profile-bytes"
        data, decoded, record = module.encode_variant(image, profile, 8, True)
        reference = image.resize((8, 4), self.Image.Resampling.LANCZOS)
        self.assertEqual(decoded.tobytes(), reference.tobytes())
        self.assertTrue(record["losslessPixelEqualityToResample"])
        self.assertEqual(record["iccSha256"], module.sha(profile))
        with self.Image.open(BytesIO(data)) as reopened:
            self.assertEqual(reopened.info["icc_profile"], profile)

    def test_original_image_not_mutated(self):
        image, _, _ = self.synthetic()
        before = image.tobytes(), image.size
        module.encode_variant(image, b"", 8, True)
        self.assertEqual((image.tobytes(), image.size), before)

    def test_profile_loss_detected(self):
        image, _, _ = self.synthetic()
        original_save = self.Image.Image.save
        def omit_profile(obj, output, *args, **kwargs):
            kwargs.pop("icc_profile", None)
            return original_save(obj, output, *args, **kwargs)
        with mock.patch.object(self.Image.Image, "save", omit_profile):
            with self.assertRaisesRegex(ValueError, "profile"):
                module.encode_variant(image, b"synthetic-opaque-profile-bytes", 8, True)

    def test_lossy_photo_encoding_explicit(self):
        image, _, _ = self.synthetic()
        data, decoded, record = module.encode_variant(image, b"", 8, False)
        self.assertEqual(decoded.size, (8, 4))
        self.assertFalse(record["encoding"]["lossless"])
        self.assertEqual(record["encoding"]["quality"], 90)
        self.assertEqual(record["encoding"]["method"], 6)
        self.assertTrue(data.startswith(b"RIFF"))

if __name__ == "__main__":
    unittest.main()
