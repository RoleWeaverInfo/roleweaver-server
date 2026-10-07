using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace RoleWeaverDemo {
    static class Program {
        [STAThread]
        static int Main(string[] args) {
            Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
            try {
                string root = AppDomain.CurrentDomain.BaseDirectory;
                var runtime = new DemoRuntime(root);
                // Maintainer smoke checks exercise exactly the same runtime as the GUI.
                if (args.Length > 0 && args[0] == "--start-only") { runtime.Start(); return 0; }
                if (args.Length > 0 && args[0] == "--stop") { runtime.Shutdown(); return 0; }
                if (args.Length > 0 && args[0] == "--check") {
                    runtime.Login("roleweaver");
                    File.WriteAllText(Path.Combine(root, "check-result.txt"), "Bridge: " + runtime.BridgeState()); return 0;
                }
                using (var form = new DemoForm(runtime)) {
                    if (args.Length > 1 && args[0] == "--render") {
                        if (args.Length > 2) form.Preview(args[2]);
                        form.Show(); Application.DoEvents();
                        using (var bitmap = new Bitmap(form.Width, form.Height)) {
                            form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, form.Size)); bitmap.Save(args[1]);
                        }
                        return 0;
                    }
                    bool created;
                    string id;
                    using (var sha = System.Security.Cryptography.SHA256.Create())
                        id = BitConverter.ToString(sha.ComputeHash(System.Text.Encoding.UTF8.GetBytes(root.ToLowerInvariant()))).Replace("-", "");
                    using (var mutex = new Mutex(true, "Local\\RoleWeaverDemo-" + id, out created)) {
                        if (!created) { MessageBox.Show("The launcher for this folder is already open.", "Role Weaver"); return 0; }
                        form.AutoStart = args.Length == 0; Application.Run(form); mutex.ReleaseMutex();
                    }
                }
                return 0;
            } catch (Exception e) {
                if (args.Length > 0) {
                    File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "launcher-error.txt"), e.GetType().Name + ": " + e.Message);
                } else MessageBox.Show(e.Message, "Role Weaver Demo", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }
        }
    }

    sealed class DemoForm : Form {
        readonly DemoRuntime runtime;
        readonly Panel body = new Panel();
        readonly Label footer = new Label();
        readonly CancellationTokenSource cancellation = new CancellationTokenSource();
        ComboBox provider, model; TextBox apiKey, endpoint;
        Label modelHelp, endpointLabel;
        Button loadModelsButton, saveSetupButton, advancedSetupButton, backSetupButton;
        ProgressBar modelProgress;
        CancellationTokenSource modelLoading;
        Dictionary<string, object> providerStatus;
        readonly Dictionary<string, string[]> modelLists = new Dictionary<string, string[]>();
        Label status; bool busy, authenticated;
        public bool AutoStart;
        static readonly Color Background = Color.FromArgb(19, 24, 31), Surface = Color.FromArgb(31, 39, 49), Gold = Color.FromArgb(229, 191, 111), Muted = Color.FromArgb(184, 194, 203);
        public DemoForm(DemoRuntime runtime) {
            this.runtime = runtime;
            Text = "Role Weaver — Windows Demo"; ClientSize = new Size(880, 800);
            FormBorderStyle = FormBorderStyle.FixedSingle; MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen; BackColor = Background; ForeColor = Color.White;
            Font = new Font("Segoe UI", 10); AutoScaleMode = AutoScaleMode.Dpi;
            var splash = new PictureBox { Dock = DockStyle.Top, Height = 391, SizeMode = PictureBoxSizeMode.Zoom, BackColor = Color.Black };
            using (var stream = typeof(Program).Assembly.GetManifestResourceStream("RoleWeaver.Splash"))
                splash.Image = new Bitmap(stream);
            footer.SetBounds(28, 763, 820, 30); footer.ForeColor = Muted;
            footer.Text = "Local Windows demo  •  NWN:EE game client required  •  Initial dashboard / DM password: roleweaver";
            body.SetBounds(28, 405, 824, 345); Controls.Add(body); Controls.Add(footer); Controls.Add(splash);
            if (runtime.Settings.SetupComplete) Home(); else Setup(null);
            Shown += async (s, e) => { if (AutoStart && runtime.Settings.SetupComplete) await StartDemo(false); };
            FormClosing += (s, e) => cancellation.Cancel();
        }
        Label LabelAt(string text, int x, int y, int w, int h, bool heading = false) {
            var label = new Label { Text = text, ForeColor = heading ? Gold : Muted, AutoSize = false };
            label.SetBounds(x, y, w, h); if (heading) label.Font = new Font(Font.FontFamily, 16, FontStyle.Bold);
            body.Controls.Add(label); return label;
        }
        Button ButtonAt(string text, int x, int y, int w, Action action, bool primary = false) {
            var button = new Button { Text = text, FlatStyle = FlatStyle.Flat, BackColor = primary ? Gold : Surface, ForeColor = primary ? Background : Color.White, Cursor = Cursors.Hand };
            button.SetBounds(x, y, w, 38); button.FlatAppearance.BorderColor = primary ? Gold : Color.FromArgb(71, 86, 99);
            button.Click += (s, e) => action(); body.Controls.Add(button); return button;
        }
        TextBox TextAt(int x, int y, int w, bool secret = false) {
            var text = new TextBox { BackColor = Surface, ForeColor = Color.White, BorderStyle = BorderStyle.FixedSingle, UseSystemPasswordChar = secret };
            text.SetBounds(x, y, w, 29); body.Controls.Add(text); return text;
        }
        void Clear() { body.Controls.Clear(); }
        public void Preview(string page) {
            // Visual QA only: no server, provider calls or credentials are needed.
            if (page == "passwords") { Passwords(); return; }
            if (page == "ready") { Ready(); return; }
            Setup(null);
            provider.SelectedIndex = page == "lmstudio" ? 3 : 1;
            model.Items.Add("Example model (preview only)"); model.SelectedIndex = 0;
        }
        void Home() {
            Clear(); LabelAt("Your world, ready to explore", 0, 0, 824, 40, true);
            LabelAt("Start the demo, then connect using your NWN:EE game client.\nClosing this launcher leaves the server running. Use Stop demo when you finish.", 0, 48, 810, 55);
            LabelAt("GAME CONNECTION", 0, 120, 360, 25);
            LabelAt(runtime.GameAddress + "\nPlayer password: leave empty\nInitial DM password: roleweaver", 0, 152, 395, 88);
            LabelAt("DASHBOARD", 424, 120, 370, 25);
            LabelAt(runtime.Dashboard + "/\nPassword: roleweaver (unless changed)\nYour settings and saves stay in this folder.", 424, 152, 400, 88);
            ButtonAt("Start demo", 0, 267, 160, async () => await StartDemo(false), true);
            ButtonAt("Advanced settings", 174, 267, 177, Advanced);
            ButtonAt("Read instructions", 365, 267, 177, () => Open(Path.Combine(runtime.Root, "START_HERE.txt")));
        }
        void Setup(Dictionary<string, object> current) {
            providerStatus = current;
            Clear(); LabelAt("Choose your AI service", 0, 0, 824, 40, true);
            LabelAt("Bring your own API key, or configure it later in the dashboard. Provider charges may apply.", 0, 44, 824, 28);
            LabelAt("Provider", 0, 82, 235, 24); LabelAt("Model name", 270, 82, 550, 24);
            provider = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, BackColor = SystemColors.Window, ForeColor = SystemColors.WindowText };
            provider.SetBounds(0, 109, 246, 30); provider.Items.AddRange(new object[] { "Configure later", "OpenAI", "Gemini", "LM Studio" }); body.Controls.Add(provider);
            model = new ComboBox { DropDownStyle = ComboBoxStyle.DropDown, FlatStyle = FlatStyle.Flat, BackColor = Surface, ForeColor = Color.White, AutoCompleteMode = AutoCompleteMode.SuggestAppend, AutoCompleteSource = AutoCompleteSource.ListItems };
            model.SetBounds(270, 109, 386, 30); body.Controls.Add(model);
            loadModelsButton = ButtonAt("Load models", 672, 104, 148, async () => {
                if (modelLoading != null) { loadModelsButton.Enabled = false; modelLoading.Cancel(); }
                else await LoadModels();
            });
            LabelAt("API key (hidden; blank keeps an existing key)", 0, 151, 400, 24);
            apiKey = TextAt(0, 178, 398, true);
            endpointLabel = LabelAt("LM Studio server address", 424, 151, 396, 24);
            endpoint = TextAt(424, 178, 396); endpoint.Text = "http://10.0.2.2:1234/v1";
            modelHelp = LabelAt("Enter your API key, then click Load models to choose from your provider's model list.\nChoose a text/chat model. API keys are saved only inside the demo server.", 0, 217, 824, 54);
            modelProgress = new ProgressBar { Style = ProgressBarStyle.Marquee, MarqueeAnimationSpeed = 25, Visible = false };
            modelProgress.SetBounds(0, 273, 824, 5); body.Controls.Add(modelProgress);
            apiKey.TextChanged += (s, e) => UpdateModelControls();
            provider.SelectedIndexChanged += (s, e) => {
                // A key typed for one service must never be sent to another service.
                apiKey.Clear(); model.Items.Clear(); model.Text = "";
                model.Enabled = provider.SelectedIndex != 0; apiKey.Enabled = provider.SelectedIndex != 0;
                endpoint.Visible = endpointLabel.Visible = provider.SelectedIndex == 3;
                apiKey.Width = provider.SelectedIndex == 3 ? 398 : 820;
                string selected = Service();
                if (modelLists.ContainsKey(selected)) model.Items.AddRange(modelLists[selected]);
                modelHelp.Text = provider.SelectedIndex == 3
                    ? "Start LM Studio and load a model, then click Load models.\n10.0.2.2 reaches LM Studio on this Windows computer."
                    : "Enter your API key, then click Load models to choose from your provider's model list.\nChoose a text/chat model. API keys are saved only inside the demo server.";
                UpdateModelControls();
                if (current == null || provider.SelectedIndex == 0) return;
                string service = Service(); var profiles = (Dictionary<string, object>)current["profiles"];
                if (!profiles.ContainsKey(service)) return;
                var profile = (Dictionary<string, object>)profiles[service];
                model.Text = profile.ContainsKey("model") ? (string)profile["model"] : "";
                if (model.Text.Length > 0 && !model.Items.Contains(model.Text)) model.Items.Add(model.Text);
                if (service == "lmstudio" && profile.ContainsKey("base_url")) endpoint.Text = (string)profile["base_url"];
                if (IsHandleCreated && (service == "lmstudio" || (bool)profile["key_set"]))
                    BeginInvoke(new Action(async () => { if (!busy && !IsDisposed && provider.Parent == body && Service() == service) await LoadModels(); }));
            };
            provider.SelectedIndex = 0;
            if (current != null) {
                string active = (string)current["active"];
                provider.SelectedIndex = active == "openai" ? 1 : active == "gemini" ? 2 : active == "lmstudio" ? 3 : 0;
            }
            saveSetupButton = ButtonAt(authenticated ? "Save settings" : "Save & start demo", 0, 282, 193, async () => await Configure(), true);
            advancedSetupButton = ButtonAt("Advanced settings", 207, 282, 177, Advanced);
            backSetupButton = ButtonAt("Back", 398, 282, 110, () => { if (authenticated) Ready(); else Home(); });
            UpdateModelControls();
        }
        void UpdateModelControls() {
            if (provider == null || provider.SelectedIndex < 0 || loadModelsButton == null) return;
            bool loading = modelLoading != null, selected = Service() != "offline";
            provider.Enabled = !loading; model.Enabled = apiKey.Enabled = selected && !loading;
            endpoint.Enabled = !loading;
            loadModelsButton.Text = loading ? "Cancel" : "Load models";
            loadModelsButton.Enabled = loading || (selected && (Service() == "lmstudio" || apiKey.Text.Trim().Length > 0 || HasSavedKey(Service())));
            modelProgress.Visible = loading;
            foreach (var button in new[] { saveSetupButton, advancedSetupButton, backSetupButton })
                if (button != null) button.Enabled = !loading;
        }
        string Service() { return new[] { "offline", "openai", "gemini", "lmstudio" }[provider.SelectedIndex]; }
        string Endpoint(string service) {
            if (service != "lmstudio") return "";
            Uri uri;
            if (!Uri.TryCreate(endpoint.Text.Trim(), UriKind.Absolute, out uri)) throw new InvalidOperationException("Enter a complete LM Studio URL, including http:// and /v1.");
            if (uri.Host == "localhost" || uri.Host == "127.0.0.1") uri = new UriBuilder(uri) { Host = "10.0.2.2" }.Uri;
            return uri.ToString().TrimEnd('/');
        }
        bool HasSavedKey(string service) {
            if (providerStatus == null) return false;
            var profiles = (Dictionary<string, object>)providerStatus["profiles"];
            return profiles.ContainsKey(service) && (bool)((Dictionary<string, object>)profiles[service])["key_set"];
        }
        async Task LoadModels() {
            if (busy) return;
            string service = Service(), key = apiKey.Text.Trim();
            if (service == "offline") { modelHelp.Text = "Choose an AI provider first."; return; }
            if (service != "lmstudio" && key.Length == 0 && !HasSavedKey(service)) { modelHelp.Text = "Enter your API key, then click Load models."; apiKey.Focus(); return; }
            busy = true;
            modelLoading = CancellationTokenSource.CreateLinkedTokenSource(cancellation.Token);
            var token = modelLoading.Token;
            var elapsed = Stopwatch.StartNew();
            string phase = "Starting the local demo server. First startup can take several minutes.";
            Action refresh = () => { if (!IsDisposed) modelHelp.Text = phase + "\nElapsed: " + elapsed.Elapsed.ToString(@"m\:ss") + ". Cancel stops this request; the demo server stays running."; };
            Action<string> report = message => { phase = message; refresh(); };
            var timer = new System.Windows.Forms.Timer { Interval = 500 };
            timer.Tick += (s, e) => refresh(); timer.Start();
            UpdateModelControls(); refresh();
            try {
                string url = Endpoint(service), previous = model.Text;
                await Boot(token, report);
                report("Retrieving the model list from " + provider.Text + "...");
                var ids = await Task.Run(() => runtime.ListModels(service, key, url, token), token);
                token.ThrowIfCancellationRequested();
                modelLists[service] = ids; model.Items.Clear(); model.Items.AddRange(ids);
                model.Text = previous;
                timer.Stop();
                modelHelp.Text = ids.Length == 0 ? "No models were returned. Load a model in LM Studio, or check your provider account."
                    : ids.Length + " model IDs available. Choose a text/chat model from the dropdown.\nYou can also type an exact model ID. Saving checks that the provider lists it.";
            } catch (OperationCanceledException) {
                timer.Stop();
                if (!IsDisposed) modelHelp.Text = "Model loading cancelled. Your entries are kept; you can retry.\nThe demo server stays running. This did not save or change your AI settings.";
            } catch (Exception e) {
                timer.Stop();
                if (!IsDisposed) modelHelp.Text = e is System.Net.WebException
                    ? "Could not load models. Check the API key or LM Studio address and try again."
                    : e.Message;
            } finally {
                timer.Stop(); timer.Dispose(); key = "";
                modelLoading.Dispose(); modelLoading = null; busy = false;
                if (!IsDisposed) { UpdateModelControls(); if (authenticated) saveSetupButton.Text = "Save settings"; }
            }
        }
        async Task Configure() {
            if (busy) return;
            string service = Service(), selectedModel = model.Text.Trim(), key = apiKey.Text.Trim(), url = endpoint.Text.Trim();
            if (service != "offline" && selectedModel.Length == 0) { MessageBox.Show(this, "Enter the model name to use.", "Choose a model"); model.Focus(); return; }
            if ((service == "openai" || service == "gemini") && key.Length == 0 && !HasSavedKey(service)) {
                MessageBox.Show(this, "Enter your API key, or select Configure later.", "API key"); return;
            }
            try { url = Endpoint(service); } catch (Exception e) { MessageBox.Show(this, e.Message); return; }
            apiKey.Clear();
            await Run(async () => {
                Progress("Preparing your demo", "Starting the local server before saving the AI settings...");
                await Boot();
                if (service != "offline") {
                    status.Text = "Checking the model name with your provider...";
                    var ids = await Task.Run(() => runtime.ListModels(service, key, url));
                    if (Array.IndexOf(ids, selectedModel) < 0) {
                        modelLists[service] = ids;
                        var current = await Task.Run(() => runtime.LlmStatus());
                        Setup(current); provider.SelectedIndex = service == "openai" ? 1 : service == "gemini" ? 2 : 3;
                        apiKey.Text = key; model.Text = selectedModel; endpoint.Text = url;
                        modelHelp.Text = "That model name was not returned by the provider. Choose an available model from the dropdown.";
                        return;
                    }
                }
                await Task.Run(() => runtime.SaveProvider(service, selectedModel, key, url, true));
                key = ""; Ready();
            });
            key = "";
        }
        Task Boot() { return Boot(cancellation.Token, message => { if (!IsDisposed) status.Text = message; }); }
        async Task Boot(CancellationToken token, Action<string> report) {
            await Task.Run(() => runtime.Start(), token);
            await runtime.WaitForDashboard(report, token);
            if (!authenticated) {
                bool needPassword = false;
                report("Signing in to the local dashboard...");
                try { await Task.Run(() => runtime.Login("roleweaver", token), token); }
                catch (System.Net.WebException e) {
                    var response = e.Response as System.Net.HttpWebResponse;
                    if (response == null || response.StatusCode != System.Net.HttpStatusCode.Unauthorized) throw;
                    needPassword = true;
                }
                token.ThrowIfCancellationRequested();
                if (needPassword) {
                    using (var prompt = new Form { Text = "Dashboard password", ClientSize = new Size(380, 135), StartPosition = FormStartPosition.CenterParent, FormBorderStyle = FormBorderStyle.FixedDialog, MaximizeBox = false, MinimizeBox = false }) {
                        var label = new Label { Text = "Enter the dashboard password you set:", Left = 15, Top = 15, Width = 350 };
                        var password = new TextBox { Left = 15, Top = 46, Width = 345, UseSystemPasswordChar = true };
                        var ok = new Button { Text = "Connect", DialogResult = DialogResult.OK, Left = 250, Top = 86, Width = 110 };
                        prompt.Controls.AddRange(new Control[] { label, password, ok }); prompt.AcceptButton = ok;
                        if (prompt.ShowDialog(this) != DialogResult.OK) throw new OperationCanceledException();
                        string value = password.Text; await Task.Run(() => runtime.Login(value, token), token); password.Clear(); value = "";
                    }
                }
                authenticated = true;
            }
        }
        async Task StartDemo(bool unused) {
            await Run(async () => { Progress("Starting your world", "Preparing the local server..."); await Boot(); Ready(); });
        }
        void Progress(string title, string message) {
            Clear(); LabelAt(title, 0, 0, 824, 40, true); status = LabelAt(message, 0, 60, 800, 90);
            var bar = new ProgressBar { Style = ProgressBarStyle.Marquee, MarqueeAnimationSpeed = 25 }; bar.SetBounds(0, 162, 824, 18); body.Controls.Add(bar);
            LabelAt("Please wait. Software emulation can take a few minutes to start.\nYour existing Windows and NWN installations are not changed.", 0, 207, 800, 75);
        }
        void Ready() {
            Clear(); LabelAt("The dashboard is ready", 0, 0, 824, 40, true);
            LabelAt("Connect in NWN:EE using Direct Connect. The game server may need another moment to load.\nPlayer password: leave empty. Use your DM password (initially roleweaver).", 0, 51, 824, 54);
            LabelAt(runtime.GameAddress, 0, 117, 824, 40, true);
            LabelAt("Dashboard: " + runtime.Dashboard + "/\nClosing this window leaves the demo running. Stop it before moving or backing up the folder.", 0, 170, 824, 62);
            ButtonAt("Open dashboard", 0, 260, 187, () => Open(runtime.Dashboard + "/"), true);
            ButtonAt("Configure AI", 201, 260, 148, async () => await Run(async () => { var current = await Task.Run(() => runtime.LlmStatus()); Setup(current); }));
            ButtonAt("Content folder", 363, 260, 153, () => Open(Path.Combine(runtime.Root, "content")));
            ButtonAt("Stop demo", 530, 260, 145, async () => await Run(async () => { Progress("Saving and stopping", "Closing the game server and shutting down Linux safely..."); await Task.Run(() => runtime.Shutdown()); authenticated = false; Home(); }));
            ButtonAt("Instructions", 689, 260, 135, () => Open(Path.Combine(runtime.Root, "START_HERE.txt")));
            ButtonAt("Change passwords", 0, 307, 187, Passwords);
        }
        void Passwords() {
            Clear(); LabelAt("Dashboard and DM passwords", 0, 0, 824, 40, true);
            LabelAt("Current dashboard password (required for either change)", 0, 49, 824, 24);
            var current = TextAt(0, 77, 824, true);
            LabelAt("New dashboard password", 0, 121, 398, 24);
            LabelAt("New DM password", 424, 121, 398, 24);
            var dashboard = TextAt(0, 150, 398, true); var dm = TextAt(424, 150, 398, true);
            LabelAt("Repeat dashboard password", 0, 189, 398, 24);
            LabelAt("Repeat DM password", 424, 189, 398, 24);
            var repeatDashboard = TextAt(0, 215, 398, true); var repeatDM = TextAt(424, 215, 398, true);
            LabelAt("8–256 characters. Other dashboard sessions sign out.", 0, 253, 398, 38);
            LabelAt("8–32 ASCII characters, no spaces. Applies after restart.", 424, 253, 398, 38);
            ButtonAt("Save dashboard", 0, 302, 184, async () => await SavePassword("dashboard", current, dashboard, repeatDashboard), true);
            ButtonAt("Save DM password", 424, 302, 190, async () => await SavePassword("dm", current, dm, repeatDM), true);
            ButtonAt("Back", 702, 302, 122, Ready);
        }
        async Task SavePassword(string kind, TextBox current, TextBox password, TextBox repeat) {
            if (busy) return;
            string old = current.Text, value = password.Text;
            if (old.Length == 0 || value.Length < 8 || value != repeat.Text || value.Length > (kind == "dm" ? 32 : 256)) {
                MessageBox.Show(this, "Enter the current dashboard password and matching new passwords of the stated length.", "Check passwords"); return;
            }
            if (kind == "dm") foreach (char c in value) if (c < 33 || c > 126) { MessageBox.Show(this, "Use ASCII characters without spaces for the DM password."); return; }
            current.Clear(); password.Clear(); repeat.Clear();
            await Run(async () => {
                Progress("Saving password", "Updating the password inside your demo server...");
                await Task.Run(() => runtime.ChangePassword(old, kind, value));
                old = value = "";
                Ready();
                MessageBox.Show(this, kind == "dm" ? "DM password saved. It takes effect the next time you stop and start the demo. Players have not been disconnected."
                    : "Dashboard password changed. Other dashboard sessions must sign in with the new password.", "Password saved");
            });
            old = value = "";
        }
        async Task Run(Func<Task> operation) {
            if (busy) return; busy = true;
            try { await operation(); }
            catch (OperationCanceledException) { if (!IsDisposed) Home(); }
            catch (Exception e) {
                if (IsDisposed) return;
                Clear(); LabelAt("The demo needs attention", 0, 0, 824, 40, true);
                string message = e is System.Net.WebException ? "The server did not accept the request. Check the current password or provider settings. Password controls require the updated demo server files." : e.Message;
                LabelAt(message, 0, 52, 824, 130);
                ButtonAt("Retry / return", 0, 242, 180, () => { if (authenticated) Ready(); else Home(); }, true);
                ButtonAt("Open logs", 194, 242, 150, () => Open(Path.Combine(runtime.UserData, "logs")));
                ButtonAt("Open dashboard", 358, 242, 180, () => Open(runtime.Dashboard + "/"));
            } finally { busy = false; }
        }
        void Advanced() {
            if (runtime.IsRunning()) { MessageBox.Show(this, "Stop the demo before changing its ports or memory.", "Demo is running"); return; }
            Clear(); LabelAt("Local connection settings", 0, 0, 824, 40, true);
            LabelAt("The defaults work for one demo. Change ports only if another local service uses them.", 0, 49, 824, 35);
            string[] names = { "Game UDP port", "Dashboard port", "Linux SSH port", "VM control port" };
            int[] values = { runtime.Settings.GamePort, runtime.Settings.DashboardPort, runtime.Settings.SshPort, runtime.Settings.ControlPort };
            var inputs = new NumericUpDown[4];
            for (int i = 0; i < 4; i++) {
                int x = (i % 2) * 424, y = 103 + (i / 2) * 71; LabelAt(names[i], x, y, 375, 24);
                inputs[i] = new NumericUpDown { Minimum = 1024, Maximum = 65535, Value = values[i], BackColor = Surface, ForeColor = Color.White };
                inputs[i].SetBounds(x, y + 27, 375, 28); body.Controls.Add(inputs[i]);
            }
            ButtonAt("Save settings", 0, 282, 170, () => {
                var distinct = new HashSet<int>(); foreach (var input in inputs) distinct.Add((int)input.Value);
                if (distinct.Count != 4) { MessageBox.Show(this, "Choose four different port numbers."); return; }
                int dashboardPort = (int)inputs[1].Value;
                if (dashboardPort == 5127 || dashboardPort == 6379 || dashboardPort == 8748) { MessageBox.Show(this, "Dashboard ports 5127, 6379 and 8748 are reserved inside the demo. Choose another port."); return; }
                runtime.Settings.GamePort = (int)inputs[0].Value; runtime.Settings.DashboardPort = (int)inputs[1].Value;
                runtime.Settings.SshPort = (int)inputs[2].Value; runtime.Settings.ControlPort = (int)inputs[3].Value;
                runtime.SaveSettings(); if (runtime.Settings.SetupComplete) Home(); else Setup(null);
            }, true);
            ButtonAt("Back", 184, 282, 110, () => { if (runtime.Settings.SetupComplete) Home(); else Setup(null); });
        }
        void Open(string target) {
            try { Process.Start(new ProcessStartInfo(target) { UseShellExecute = true }); }
            catch (Exception e) { MessageBox.Show(this, e.Message, "Could not open"); }
        }
    }
}
