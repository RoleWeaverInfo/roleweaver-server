from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "windows-installer/launcher/Program.cs"
PACKAGER = ROOT / "windows-installer/package.ps1"


@unittest.skipUnless(
    SOURCE.is_file(), "Windows installer source is a separate distribution"
)
class WindowsRemoteInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text()
        cls.packager = PACKAGER.read_text()

    def test_preserves_ssh_host_key_verification(self):
        self.assertIn("StrictHostKeyChecking=accept-new", self.source)
        self.assertNotIn("StrictHostKeyChecking=no", self.source)
        self.assertNotIn("UserKnownHostsFile=/dev/null", self.source)

    def test_password_is_only_passed_to_askpass_memory(self):
        self.assertIn("RW_INSTALLER_SECRET", self.source)
        self.assertNotIn("WriteAllText(diagnosticPath, secret", self.source)
        self.assertNotIn("Append(secret.Text", self.source)
        self.assertNotIn("SaveFileDialog", self.source)

    def test_remote_setup_uses_tunnel_and_opens_tokenized_url(self):
        self.assertIn('args.Add("-L")', self.source)
        self.assertIn("ExitOnForwardFailure=yes", self.source)
        self.assertIn("gui --port", self.source)
        self.assertNotIn("gui --trusted-local", self.source)
        self.assertIn("token=[A-Za-z0-9_-]+", self.source)
        self.assertIn("127.0.0.1:", self.source)

    def test_upload_is_streamed_and_temporary_folder_is_scoped(self):
        self.assertIn("input.CopyTo(running.StandardInput.BaseStream)", self.source)
        self.assertIn("$HOME/.cache/roleweaver-remote-installer", self.source)
        self.assertIn('rm -rf -- \\"$work\\"', self.source)

    def test_remote_setup_uses_top_level_launcher(self):
        self.assertIn("maxdepth 1 -type d", self.source)
        self.assertIn('setup=\\"$root/setup.sh\\"', self.source)
        self.assertIn("$root/tools/setup_gui.py", self.source)
        self.assertNotIn("maxdepth 3 -type f -name setup.sh", self.source)

    def test_window_docking_order_keeps_log_below_controls(self):
        self.assertIn("Controls.SetChildIndex(heading, 0)", self.source)
        self.assertIn("Controls.SetChildIndex(log, 3)", self.source)

    def test_connection_diagnostics_are_visible_and_persisted(self):
        self.assertIn("Test SSH login", self.source)
        self.assertIn("installer.log", self.source)
        self.assertIn("Diagnostic log:", self.source)

    def test_bundled_addon_archive_is_selected_automatically(self):
        self.assertIn("RoleWeaver-Server-Addon-*.tar.gz", self.source)
        self.assertIn("Application.StartupPath", self.source)
        self.assertIn("Using Server Add-on archive:", self.source)

    def test_packager_uses_application_version_and_bundles_checksum(self):
        self.assertIn("roleweaver\\__init__.py", self.packager)
        self.assertIn("$packagedAddon + '.sha256'", self.packager)
        self.assertNotIn("Remote-Installer-1.0.0.zip", self.packager)


if __name__ == "__main__":
    unittest.main()
