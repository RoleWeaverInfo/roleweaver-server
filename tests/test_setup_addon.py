"""Import completeness, dependency failures and safe setup configuration."""

import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import setup_addon


class SetupTests(unittest.TestCase):
    def headers(self, directory):
        directory.mkdir()
        for name in setup_addon.HEADERS:
            (directory / ("nwnx_" + name + ".nss")).write_text("// matching build\n")
        (directory / "nwnx_redis.nss").write_text('#include "nwnx_redis_lib"\n')
        (directory / "nwnx_redis_lib.nss").write_text('#include "nwnx_core"\n')

    def test_complete_import_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.headers(root / "headers")
            config = dict(
                world_id="test_world",
                redis_prefix="roleweaver:test_world",
                nwnx_headers=root / "headers",
                output=root / "out",
            )
            manifest = setup_addon.prepare_import(config)
            raw = (root / "out/RoleWeaver-Import.erf").read_bytes()
            self.assertEqual(raw[:8], b"ERF V1.0")
            count, keys, index = struct.unpack_from("<I4xII", raw, 16)
            resources = {}
            for i in range(count):
                name, rid, kind, _ = struct.unpack_from("<16sIHH", raw, keys + 24 * i)
                offset, size = struct.unpack_from("<II", raw, index + 8 * rid)
                resources[name.rstrip(b"\0").decode(), kind] = raw[
                    offset : offset + size
                ]
            self.assertEqual(
                resources["nwnx_redis_lib", 2009],
                (root / "headers/nwnx_redis_lib.nss").read_bytes(),
            )
            self.assertIn(("rw_core", 2009), resources)
            self.assertIn(("rw_shopcore", 2009), resources)
            self.assertIn(("rw_base", 2027), resources)
            self.assertIn(("rw_shop", 2051), resources)
            self.assertIn(("rw_userload", 2009), resources)
            self.assertIn(b"test_world", resources["rw_settings", 2009])
            self.assertFalse(any(kind == 2014 for _, kind in resources))
            for path, digest in manifest["files"].items():
                self.assertEqual(
                    hashlib.sha256((root / "out" / path).read_bytes()).hexdigest(),
                    digest,
                )
            with self.assertRaisesRegex(ValueError, "new output"):
                setup_addon.prepare_import(config)

    def test_missing_transitive_header_creates_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.headers(root / "headers")
            (root / "headers/nwnx_redis_lib.nss").unlink()
            with self.assertRaisesRegex(ValueError, "nwnx_redis_lib"):
                setup_addon.prepare_import(
                    dict(
                        nwnx_headers=root / "headers",
                        output=root / "out",
                        world_id="world",
                        redis_prefix="roleweaver:world",
                    )
                )
            self.assertFalse((root / "out").exists())

    def test_config_rejects_bad_identity_and_ports(self):
        original = json.loads(
            (setup_addon.ROOT / "addon/setup.json").read_text(encoding="utf-8-sig")
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "setup.json"
            for key, value in [
                ("world_id", "bad;command"),
                ("dashboard_port", True),
                ("redis_port", 8743),
            ]:
                p.write_text(json.dumps(dict(original, **{key: value})))
                with self.assertRaises(ValueError):
                    setup_addon.configuration(p)


if __name__ == "__main__":
    unittest.main()
