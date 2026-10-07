import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.package_release import package
from tools.verify_release import verify_addon, verify_installer


class ReleaseVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addon = self.root / "RoleWeaver-Server-Addon-1.0.1.tar.gz"
        package(self.addon, "addon")
        self.installer = self.root / "RoleWeaver-Remote-Installer-1.0.1.zip"
        with zipfile.ZipFile(self.installer, "w") as archive:
            archive.writestr("Role Weaver Remote Installer.exe", b"MZtest")
            archive.writestr("README.txt", b"test")
            archive.write(self.addon, self.addon.name)
            archive.write(
                self.addon.with_name(self.addon.name + ".sha256"),
                self.addon.name + ".sha256",
            )
        checksum = hashlib.sha256(self.installer.read_bytes()).hexdigest()
        self.installer.with_name(self.installer.name + ".sha256").write_text(
            f"{checksum}  {self.installer.name}\n", encoding="ascii"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_coordinated_addon_and_installer_pass(self):
        version = verify_addon(self.addon)
        self.assertEqual(version, "1.0.1")
        verify_installer(self.installer, self.addon, version)

    def test_different_bundled_addon_is_rejected(self):
        with zipfile.ZipFile(self.installer, "w") as archive:
            archive.writestr("Role Weaver Remote Installer.exe", b"MZtest")
            archive.writestr("README.txt", b"test")
            archive.writestr(self.addon.name, b"different")
            archive.write(
                self.addon.with_name(self.addon.name + ".sha256"),
                self.addon.name + ".sha256",
            )
        checksum = hashlib.sha256(self.installer.read_bytes()).hexdigest()
        self.installer.with_name(self.installer.name + ".sha256").write_text(
            f"{checksum}  {self.installer.name}\n", encoding="ascii"
        )
        with self.assertRaisesRegex(ValueError, "different Server Add-on"):
            verify_installer(self.installer, self.addon, "1.0.1")


if __name__ == "__main__":
    unittest.main()
