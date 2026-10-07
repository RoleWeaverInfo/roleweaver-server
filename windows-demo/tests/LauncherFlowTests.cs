// Exercises the real WinForms message loop and real cancellable HTTP requests.
// The fake backend is loopback-only; it never contacts an AI provider or a VM.
using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace RoleWeaverDemo {
    sealed class TestRuntime : DemoRuntime {
        public TestRuntime(string root) : base(root) { }
        public override void Start() { }
        public override bool IsRunning() { return true; }
    }
    sealed class FakeDashboard : IDisposable {
        readonly TcpListener listener = new TcpListener(IPAddress.Loopback, 0);
        public readonly ManualResetEventSlim Release = new ManualResetEventSlim(false);
        public volatile bool HoldLogin, HoldModels, FailModels;
        public int ModelRequests;
        public int Port { get { return ((IPEndPoint)listener.LocalEndpoint).Port; } }
        bool stopped;
        public FakeDashboard() {
            listener.Start();
            Task.Run(async () => {
                while (!stopped) {
                    TcpClient client;
                    try { client = await listener.AcceptTcpClientAsync(); } catch (ObjectDisposedException) { return; } catch (SocketException) { return; }
                    Task.Run(() => Handle(client));
                }
            });
        }
        void Handle(TcpClient client) {
            using (client) try {
                var stream = client.GetStream(); stream.ReadTimeout = 10000;
                var reader = new StreamReader(stream, Encoding.UTF8);
                string first = reader.ReadLine(), line; int length = 0;
                while (!String.IsNullOrEmpty(line = reader.ReadLine()))
                    if (line.StartsWith("Content-Length:", StringComparison.OrdinalIgnoreCase)) length = Int32.Parse(line.Substring(15).Trim());
                var body = new char[length]; int read = 0;
                while (read < length) { int size = reader.Read(body, read, length - read); if (size == 0) break; read += size; }
                bool models = first.Contains(" /api/llm-models ");
                if (models) Interlocked.Increment(ref ModelRequests);
                if ((models && HoldModels) || (first.Contains(" /login ") && HoldLogin)) Release.Wait(10000);
                string json = models ? "{\"models\":[\"fixture-chat-one\",\"fixture-chat-two\"]}" : "{\"ok\":true}";
                byte[] payload = Encoding.UTF8.GetBytes(json);
                string status = models && FailModels ? "503 Unavailable" : "200 OK";
                byte[] header = Encoding.ASCII.GetBytes("HTTP/1.1 " + status + "\r\nContent-Type: application/json\r\nContent-Length: " + payload.Length + "\r\nConnection: close\r\n\r\n");
                stream.Write(header, 0, header.Length); stream.Write(payload, 0, payload.Length);
            } catch (IOException) { } catch (ObjectDisposedException) { }
        }
        public void Dispose() { stopped = true; Release.Set(); listener.Stop(); }
    }
    static class LauncherFlowTests {
        static T Field<T>(object obj, string name) { return (T)obj.GetType().GetField(name, BindingFlags.Instance | BindingFlags.NonPublic).GetValue(obj); }
        static void Require(bool value, string message) { if (!value) throw new Exception(message); }
        static async Task Until(Func<bool> done) {
            var end = DateTime.UtcNow.AddSeconds(5);
            while (!done()) { if (DateTime.UtcNow >= end) throw new Exception("UI operation did not finish"); await Task.Delay(25); }
        }
        [STAThread]
        static int Main(string[] args) {
            Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
            string outcome = "FAIL: no completion"; int exitCode = 1;
            using (var backend = new FakeDashboard()) {
                var runtime = new TestRuntime(Path.GetTempPath()); runtime.Settings.DashboardPort = backend.Port;
                using (var form = new DemoForm(runtime)) {
                    form.Preview("cloud");
                    form.Shown += async (s, e) => {
                        try {
                            var load = Field<Button>(form, "loadModelsButton");
                            var key = Field<TextBox>(form, "apiKey");
                            var panel = Field<Panel>(form, "body");
                            Require(!load.Enabled, "Load models must explain/disable a missing API key");
                            key.Text = "test-only-not-a-real-key";
                            Require(load.Enabled, "Entering a key should enable model loading");
                            backend.HoldLogin = true; load.PerformClick();
                            await Task.Delay(700);
                            Require(panel.Enabled && load.Enabled && load.Text == "Cancel", "Startup must leave Cancel available");
                            Require(Field<Label>(form, "modelHelp").Text.Contains("Elapsed:"), "Startup progress is missing");
                            load.PerformClick();
                            await Until(() => Field<CancellationTokenSource>(form, "modelLoading") == null);
                            Require(key.Enabled && key.Text == "test-only-not-a-real-key", "Cancel lost the API entry");
                            backend.HoldLogin = false; backend.Release.Set();

                            backend.HoldModels = true; backend.Release.Reset(); load.PerformClick();
                            await Until(() => backend.ModelRequests > 0);
                            Require(panel.Enabled && load.Enabled, "Model request froze the controls");
                            load.PerformClick();
                            await Until(() => Field<CancellationTokenSource>(form, "modelLoading") == null);
                            backend.HoldModels = false; backend.Release.Set();
                            load.PerformClick();
                            await Until(() => Field<CancellationTokenSource>(form, "modelLoading") == null);
                            Require(Field<ComboBox>(form, "model").Items.Count == 2, "Retry did not populate model IDs");

                            backend.FailModels = true; load.PerformClick();
                            await Until(() => Field<CancellationTokenSource>(form, "modelLoading") == null);
                            Require(load.Enabled && key.Enabled && Field<Label>(form, "modelHelp").Text.Contains("Could not load"), "Provider error did not recover the form");
                            backend.FailModels = false;
                            Field<ComboBox>(form, "provider").SelectedIndex = 2;
                            Require(key.Text == "" && !load.Enabled, "Provider switch must not forward another provider's key");
                            key.Text = "test-only-not-a-real-key";
                            backend.HoldModels = true; backend.Release.Reset();
                            int prior = backend.ModelRequests; load.PerformClick();
                            await Until(() => backend.ModelRequests > prior);
                            form.Close();
                            outcome = "PASS: empty-key feedback; responsive startup/model wait; cancellation; retained input; retry/model list; error recovery; provider key isolation; close during lookup.";
                            exitCode = 0;
                        } catch (Exception ex) { outcome = "FAIL: " + ex.Message; }
                        finally { form.Close(); }
                    };
                    Application.Run(form);
                }
            }
            File.WriteAllText(args[0], outcome);
            return exitCode;
        }
    }
}
