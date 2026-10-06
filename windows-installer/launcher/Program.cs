using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace RoleWeaver.RemoteInstaller
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            if (Environment.GetEnvironmentVariable("RW_INSTALLER_ASKPASS") == "1")
            {
                string secret = Environment.GetEnvironmentVariable("RW_INSTALLER_SECRET") ?? "";
                byte[] output = Encoding.UTF8.GetBytes(secret + Environment.NewLine);
                using (Stream stream = Console.OpenStandardOutput())
                    stream.Write(output, 0, output.Length);
                return;
            }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new InstallerForm());
        }
    }

    internal sealed class InstallerForm : Form
    {
        private readonly TextBox host = new TextBox();
        private readonly NumericUpDown sshPort = new NumericUpDown();
        private readonly TextBox username = new TextBox();
        private readonly TextBox archive = new TextBox();
        private readonly TextBox identity = new TextBox();
        private readonly TextBox secret = new TextBox();
        private readonly NumericUpDown setupPort = new NumericUpDown();
        private readonly Button test = new Button();
        private readonly Button start = new Button();
        private readonly Button stop = new Button();
        private readonly TextBox log = new TextBox();
        private readonly Label state = new Label();
        private readonly string diagnosticPath;
        private Process ssh;
        private bool browserOpened;

        public InstallerForm()
        {
            string diagnosticDirectory = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "RoleWeaver",
                "RemoteInstaller"
            );
            diagnosticPath = Path.Combine(diagnosticDirectory, "installer.log");
            try
            {
                Directory.CreateDirectory(diagnosticDirectory);
                File.WriteAllText(
                    diagnosticPath,
                    "Role Weaver Remote Installer diagnostics - " + DateTime.Now.ToString("O") + Environment.NewLine
                );
            }
            catch { }

            Text = "Role Weaver Server Add-on - Remote Setup";
            Width = 850;
            Height = 720;
            MinimumSize = new Size(720, 620);
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Color.FromArgb(17, 16, 24);
            ForeColor = Color.FromArgb(244, 240, 232);
            Font = new Font("Segoe UI", 9.5f);

            Panel heading = new Panel { Dock = DockStyle.Top, Height = 82, BackColor = Color.FromArgb(12, 12, 18) };
            Label title = new Label
            {
                Text = "ROLE WEAVER  ·  REMOTE SERVER SETUP",
                ForeColor = Color.FromArgb(215, 169, 75),
                Font = new Font("Georgia", 17f, FontStyle.Bold),
                AutoSize = true,
                Left = 24,
                Top = 17
            };
            Label subtitle = new Label
            {
                Text = "Upload and configure the Server Add-on on an existing Linux NWN/NWNX host",
                ForeColor = Color.FromArgb(175, 170, 185),
                AutoSize = true,
                Left = 26,
                Top = 50
            };
            heading.Controls.Add(title);
            heading.Controls.Add(subtitle);
            Controls.Add(heading);

            TableLayoutPanel form = new TableLayoutPanel
            {
                Dock = DockStyle.Top,
                Height = 335,
                Padding = new Padding(24, 14, 24, 4),
                ColumnCount = 3,
                RowCount = 8,
                AutoSize = false
            };
            form.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 165));
            form.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            form.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 95));
            for (int i = 0; i < 8; i++) form.RowStyles.Add(new RowStyle(SizeType.Absolute, 38));

            host.Text = "192.168.167.128";
            sshPort.Minimum = 1; sshPort.Maximum = 65535; sshPort.Value = 22;
            username.Text = "roleweaver";
            secret.UseSystemPasswordChar = true;
            setupPort.Minimum = 1024; setupPort.Maximum = 65535; setupPort.Value = 8750;

            AddRow(form, 0, "Linux server address", host, null);
            AddRow(form, 1, "SSH port", sshPort, null);
            AddRow(form, 2, "Linux username", username, null);
            AddRow(form, 3, "Server Add-on archive", archive, BrowseButton("Archive…", SelectArchive));
            AddRow(form, 4, "SSH private key (optional)", identity, BrowseButton("Key…", SelectIdentity));
            AddRow(form, 5, "Password / key phrase", secret, null);
            AddRow(form, 6, "Local setup port", setupPort, null);
            Label note = new Label
            {
                Text = "The password or key phrase is kept in memory only. New SSH host keys are accepted once; changed keys are rejected.",
                ForeColor = Color.FromArgb(175, 170, 185),
                AutoSize = true,
                Dock = DockStyle.Fill,
                Padding = new Padding(0, 7, 0, 0)
            };
            form.Controls.Add(note, 1, 7);
            form.SetColumnSpan(note, 2);
            Controls.Add(form);

            FlowLayoutPanel buttons = new FlowLayoutPanel
            {
                Dock = DockStyle.Top,
                Height = 51,
                Padding = new Padding(24, 5, 24, 5),
                FlowDirection = FlowDirection.LeftToRight
            };
            test.Text = "Test SSH login";
            test.AutoSize = true;
            test.Padding = new Padding(10, 5, 10, 5);
            test.Click += async delegate { await TestConnection(); };
            start.Text = "Connect and open setup";
            start.AutoSize = true;
            start.Padding = new Padding(10, 5, 10, 5);
            start.BackColor = Color.FromArgb(108, 74, 22);
            start.ForeColor = Color.White;
            start.Click += delegate { StartSetup(); };
            stop.Text = "Close connection";
            stop.AutoSize = true;
            stop.Padding = new Padding(10, 5, 10, 5);
            stop.Enabled = false;
            stop.Click += delegate { StopSetup(); };
            state.Text = "Ready";
            state.AutoSize = true;
            state.Padding = new Padding(12, 11, 0, 0);
            buttons.Controls.Add(test);
            buttons.Controls.Add(start);
            buttons.Controls.Add(stop);
            buttons.Controls.Add(state);
            Controls.Add(buttons);

            log.Dock = DockStyle.Fill;
            log.Multiline = true;
            log.ReadOnly = true;
            log.ScrollBars = ScrollBars.Vertical;
            log.BackColor = Color.FromArgb(8, 8, 12);
            log.ForeColor = Color.FromArgb(224, 220, 210);
            log.Font = new Font("Consolas", 9f);
            log.Margin = new Padding(24);
            Controls.Add(log);
            Controls.SetChildIndex(log, 3);
            Controls.SetChildIndex(buttons, 2);
            Controls.SetChildIndex(form, 1);
            Controls.SetChildIndex(heading, 0);

            Append("Ready. Test SSH login before uploading the Server Add-on.");
            Append("Diagnostic log: " + diagnosticPath);

            FormClosing += delegate { StopSetup(); };
        }

        private static void AddRow(TableLayoutPanel panel, int row, string label, Control input, Control button)
        {
            Label caption = new Label { Text = label, AutoSize = true, Anchor = AnchorStyles.Left };
            input.Dock = DockStyle.Fill;
            panel.Controls.Add(caption, 0, row);
            panel.Controls.Add(input, 1, row);
            if (button != null) panel.Controls.Add(button, 2, row);
        }

        private Button BrowseButton(string text, EventHandler handler)
        {
            Button button = new Button { Text = text, Dock = DockStyle.Fill };
            button.Click += handler;
            return button;
        }

        private void SelectArchive(object sender, EventArgs e)
        {
            using (OpenFileDialog dialog = new OpenFileDialog())
            {
                dialog.Title = "Select Role Weaver Server Add-on archive";
                dialog.Filter = "Role Weaver archive (*.tar.gz)|*.tar.gz|All files (*.*)|*.*";
                if (dialog.ShowDialog(this) == DialogResult.OK) archive.Text = dialog.FileName;
            }
        }

        private void SelectIdentity(object sender, EventArgs e)
        {
            using (OpenFileDialog dialog = new OpenFileDialog())
            {
                dialog.Title = "Select SSH private key";
                dialog.Filter = "SSH keys|id_*;*.pem;*.key|All files (*.*)|*.*";
                if (dialog.ShowDialog(this) == DialogResult.OK) identity.Text = dialog.FileName;
            }
        }

        private void StartSetup()
        {
            try
            {
                ValidateInputs();
                string sshExe = FindSsh();

                int localPort = Decimal.ToInt32(setupPort.Value);
                string session = Guid.NewGuid().ToString("N");
                string remote = RemoteCommand(localPort, session);
                string target = Target();

                string[] arguments = BuildArguments(localPort, target, remote);
                ProcessStartInfo info = SshInfo(sshExe, arguments, true);

                log.Clear();
                Append("Connecting to " + target + "…");
                state.Text = "Connecting";
                test.Enabled = false;
                start.Enabled = false;
                stop.Enabled = true;
                browserOpened = false;
                ssh = new Process { StartInfo = info, EnableRaisingEvents = true };
                ssh.OutputDataReceived += delegate(object s, DataReceivedEventArgs e) { if (e.Data != null) RemoteLine(e.Data); };
                ssh.ErrorDataReceived += delegate(object s, DataReceivedEventArgs e) { if (e.Data != null) RemoteLine(e.Data); };
                ssh.Exited += delegate { Finished(); };
                ssh.Start();
                ssh.BeginOutputReadLine();
                ssh.BeginErrorReadLine();

                Process running = ssh;
                string file = archive.Text;
                Task.Run(delegate
                {
                    try
                    {
                        using (FileStream input = File.OpenRead(file))
                            input.CopyTo(running.StandardInput.BaseStream);
                        running.StandardInput.Close();
                    }
                    catch (Exception ex)
                    {
                        RemoteLine("Upload failed: " + ex.Message);
                        try { running.Kill(); } catch { }
                    }
                });
            }
            catch (Exception ex)
            {
                Append("Cannot start setup: " + ex.Message);
                MessageBox.Show(this, ex.Message, "Cannot start setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private async Task TestConnection()
        {
            try
            {
                ValidateConnectionInputs();
                string sshExe = FindSsh();
                string target = Target();
                System.Collections.Generic.List<string> arguments = CommonArguments();
                arguments.Add(target);
                arguments.Add("printf 'ROLEWEAVER_SSH_OK\\n'");

                Append("Testing SSH login to " + target + "…");
                state.Text = "Testing SSH";
                test.Enabled = false;
                start.Enabled = false;

                using (Process process = new Process())
                {
                    process.StartInfo = SshInfo(sshExe, arguments.ToArray(), false);
                    process.Start();
                    Task<string> outputTask = process.StandardOutput.ReadToEndAsync();
                    Task<string> errorTask = process.StandardError.ReadToEndAsync();
                    await Task.Run(delegate { process.WaitForExit(); });
                    string output = await outputTask;
                    string error = await errorTask;

                    foreach (string line in Lines(output)) Append("SSH: " + line);
                    foreach (string line in Lines(error)) Append("SSH: " + line);
                    if (process.ExitCode == 0 && output.Contains("ROLEWEAVER_SSH_OK"))
                    {
                        Append("SSH login succeeded. You can now select the archive and connect.");
                        state.Text = "SSH login succeeded";
                    }
                    else
                    {
                        Append("SSH login failed (exit " + process.ExitCode + "). Check the server address, username, key and password.");
                        state.Text = "SSH login failed";
                    }
                }
            }
            catch (Exception ex)
            {
                Append("SSH test failed: " + ex.Message);
                state.Text = "SSH login failed";
                MessageBox.Show(this, ex.Message, "SSH test failed", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                test.Enabled = true;
                start.Enabled = true;
            }
        }

        private static string[] Lines(string value)
        {
            return value.Split(new[] { "\r\n", "\n" }, StringSplitOptions.RemoveEmptyEntries);
        }

        private static string FindSsh()
        {
            string sshExe = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.Windows),
                "System32",
                "OpenSSH",
                "ssh.exe"
            );
            if (!File.Exists(sshExe))
                throw new InvalidOperationException("Windows OpenSSH Client is not installed. Add it from Windows Optional Features, then try again.");
            return sshExe;
        }

        private string Target()
        {
            string targetHost = host.Text.Trim();
            if (targetHost.Contains(":") && !targetHost.StartsWith("[")) targetHost = "[" + targetHost + "]";
            return username.Text.Trim() + "@" + targetHost;
        }

        private ProcessStartInfo SshInfo(string sshExe, string[] arguments, bool redirectInput)
        {
            ProcessStartInfo info = new ProcessStartInfo
            {
                FileName = sshExe,
                Arguments = String.Join(" ", arguments.Select(QuoteArgument).ToArray()),
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardInput = redirectInput,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };
            if (!String.IsNullOrEmpty(secret.Text))
            {
                info.EnvironmentVariables["SSH_ASKPASS"] = Application.ExecutablePath;
                info.EnvironmentVariables["SSH_ASKPASS_REQUIRE"] = "force";
                info.EnvironmentVariables["DISPLAY"] = "roleweaver-installer";
                info.EnvironmentVariables["RW_INSTALLER_ASKPASS"] = "1";
                info.EnvironmentVariables["RW_INSTALLER_SECRET"] = secret.Text;
            }
            return info;
        }

        private string[] BuildArguments(int localPort, string target, string remote)
        {
            System.Collections.Generic.List<string> args = CommonArguments();
            args.Add("-L"); args.Add(localPort + ":127.0.0.1:" + localPort);
            args.Add("-o"); args.Add("ExitOnForwardFailure=yes");
            args.Add(target);
            args.Add(remote);
            return args.ToArray();
        }

        private System.Collections.Generic.List<string> CommonArguments()
        {
            System.Collections.Generic.List<string> args = new System.Collections.Generic.List<string>();
            args.Add("-T");
            args.Add("-p"); args.Add(Decimal.ToInt32(sshPort.Value).ToString());
            args.Add("-o"); args.Add("StrictHostKeyChecking=accept-new");
            args.Add("-o"); args.Add("ConnectTimeout=15");
            args.Add("-o"); args.Add("ServerAliveInterval=15");
            args.Add("-o"); args.Add("ServerAliveCountMax=3");
            if (!String.IsNullOrWhiteSpace(identity.Text))
            {
                args.Add("-i"); args.Add(identity.Text.Trim());
            }
            if (String.IsNullOrEmpty(secret.Text))
            {
                args.Add("-o"); args.Add("BatchMode=yes");
            }
            else
            {
                args.Add("-o"); args.Add("BatchMode=no");
                args.Add("-o"); args.Add("NumberOfPasswordPrompts=1");
            }
            return args;
        }

        private static string RemoteCommand(int port, string session)
        {
            return "set -eu; umask 077; " +
                "base=\"$HOME/.cache/roleweaver-remote-installer\"; mkdir -p \"$base\"; " +
                "work=\"$base/session-" + session + "\"; mkdir \"$work\"; " +
                "cleanup(){ rm -rf -- \"$work\"; }; trap cleanup EXIT HUP INT TERM; " +
                "tar -xzf - -C \"$work\"; " +
                "setup=$(find \"$work\" -mindepth 1 -maxdepth 3 -type f -name setup.sh -print -quit); " +
                "test -n \"$setup\" || { echo 'The selected archive has no setup.sh' >&2; exit 2; }; " +
                "cd \"$(dirname \"$setup\")\"; " +
                "PYTHONUNBUFFERED=1 bash ./setup.sh gui --port " + port;
        }

        private void ValidateInputs()
        {
            ValidateConnectionInputs();
            if (!File.Exists(archive.Text) || !archive.Text.EndsWith(".tar.gz", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Select the RoleWeaver Server Add-on .tar.gz archive.");
        }

        private void ValidateConnectionInputs()
        {
            if (!Regex.IsMatch(host.Text.Trim(), @"^[A-Za-z0-9.:[\]_-]+$"))
                throw new InvalidOperationException("Enter a hostname or IP address without spaces.");
            if (!Regex.IsMatch(username.Text.Trim(), @"^[A-Za-z0-9._-]+$"))
                throw new InvalidOperationException("Enter a valid Linux username.");
            if (!String.IsNullOrWhiteSpace(identity.Text) && !File.Exists(identity.Text))
                throw new InvalidOperationException("The selected SSH private key was not found.");
        }

        private void RemoteLine(string line)
        {
            if (IsDisposed) return;
            BeginInvoke((MethodInvoker)delegate
            {
                Append(line);
                Match setupUrl = Regex.Match(
                    line,
                    @"http://127\.0\.0\.1:\d+/\?token=[A-Za-z0-9_-]+"
                );
                if (!browserOpened && setupUrl.Success)
                {
                    browserOpened = true;
                    state.Text = "Setup is open";
                    string url = setupUrl.Value;
                    try { Process.Start(url); }
                    catch { Append("Open this address in your browser: " + url); }
                }
            });
        }

        private void Append(string message)
        {
            log.AppendText(message + Environment.NewLine);
            try
            {
                File.AppendAllText(
                    diagnosticPath,
                    "[" + DateTime.Now.ToString("O") + "] " + message + Environment.NewLine
                );
            }
            catch { }
        }

        private void Finished()
        {
            if (IsDisposed) return;
            BeginInvoke((MethodInvoker)delegate
            {
                int code = -1;
                try { code = ssh.ExitCode; } catch { }
                Append("Connection closed (exit " + code + ").");
                state.Text = code == 0 ? "Closed" : "Connection failed";
                test.Enabled = true;
                start.Enabled = true;
                stop.Enabled = false;
                ssh = null;
                secret.Clear();
            });
        }

        private void StopSetup()
        {
            Process process = ssh;
            if (process == null) return;
            try
            {
                if (!process.HasExited) process.Kill();
            }
            catch { }
            ssh = null;
            secret.Clear();
        }

        private static string QuoteArgument(string value)
        {
            if (value.Length > 0 && !value.Any(Char.IsWhiteSpace) && !value.Contains("\"")) return value;
            StringBuilder result = new StringBuilder("\"");
            int slashes = 0;
            foreach (char c in value)
            {
                if (c == '\\') { slashes++; continue; }
                if (c == '"') result.Append('\\', slashes * 2 + 1);
                else result.Append('\\', slashes);
                slashes = 0;
                result.Append(c);
            }
            result.Append('\\', slashes * 2);
            result.Append('"');
            return result.ToString();
        }
    }
}
