// Portable runtime management. No provider key is written on the Windows host.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Runtime.InteropServices;
using System.ComponentModel;

namespace RoleWeaverDemo {
    public class LocalSettings {
        public int GamePort = 5127, DashboardPort = 8747, SshPort = 12222, ControlPort = 18747;
        public int MemoryMB = 2048;
        public bool SetupComplete;
        public string Instance = Guid.NewGuid().ToString("N");
    }
    public class VmRecord { public int Pid; public long Started; }
    public class DemoRuntime {
        public readonly string Root, UserData;
        public LocalSettings Settings;
        static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
        CookieContainer cookies = new CookieContainer();
        public string Dashboard { get { return "http://127.0.0.1:" + Settings.DashboardPort; } }
        public string GameAddress { get { return "127.0.0.1:" + Settings.GamePort; } }
        public string Qemu { get { return Path.Combine(Root, "runtime", "qemu", "qemu-system-x86_64.exe"); } }
        public DemoRuntime(string root) {
            Root = Path.GetFullPath(root); UserData = Path.Combine(Root, "userdata");
            Settings = File.Exists(Path.Combine(UserData, "launcher.json"))
                ? Json.Deserialize<LocalSettings>(File.ReadAllText(Path.Combine(UserData, "launcher.json"))) : new LocalSettings();
            ValidateSettings();
        }
        public void ValidateSettings() {
            int[] ports = { Settings.GamePort, Settings.DashboardPort, Settings.SshPort, Settings.ControlPort };
            if (ports.Any(p => p < 1024 || p > 65535) || ports.Distinct().Count() != 4 ||
                new[] { 5127, 6379, 8748 }.Contains(Settings.DashboardPort) ||
                (Settings.MemoryMB != 2048 && Settings.MemoryMB != 4096))
                throw new InvalidOperationException("Invalid local ports or memory setting in userdata/launcher.json.");
        }
        public void SaveSettings() { WriteJson(Path.Combine(UserData, "launcher.json"), Settings); }
        static void WriteJson(string file, object value) {
            Directory.CreateDirectory(Path.GetDirectoryName(file));
            string temp = file + ".new";
            File.WriteAllText(temp, Json.Serialize(value), new UTF8Encoding(false));
            if (File.Exists(file)) File.Replace(temp, file, null); else File.Move(temp, file);
        }
        public static string Quote(string value) {
            // Windows CreateProcess argument quoting, including trailing backslashes.
            var b = new StringBuilder("\""); int slashes = 0;
            foreach (char c in value) {
                if (c == '\\') { slashes++; continue; }
                if (c == '"') b.Append('\\', slashes * 2 + 1).Append(c);
                else b.Append('\\', slashes).Append(c);
                slashes = 0;
            }
            return b.Append('\\', slashes * 2).Append('"').ToString();
        }
        static string Arguments(IEnumerable<string> values) { return string.Join(" ", values.Select(Quote)); }
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        struct StartupInfo {
            public int Size; public string Reserved, Desktop, Title;
            public int X, Y, XSize, YSize, XChars, YChars, Fill, Flags;
            public short Show, ReservedSize; public IntPtr ReservedData, Input, Output, Error;
        }
        [StructLayout(LayoutKind.Sequential)]
        struct ProcessInfo { public IntPtr Process, Thread; public int Pid, Tid; }
        [StructLayout(LayoutKind.Sequential)]
        struct SecurityAttributes { public int Length; public IntPtr Descriptor; public int Inherit; }
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern IntPtr CreateFile(string name, uint access, uint share, ref SecurityAttributes security, uint creation, uint flags, IntPtr template);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern bool CreateProcess(string application, StringBuilder command, IntPtr processAttributes, IntPtr threadAttributes,
            bool inherit, uint flags, IntPtr environment, string directory, ref StartupInfo startup, out ProcessInfo process);
        [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
        [DllImport("kernel32.dll")] static extern uint SetFilePointer(IntPtr file, int distance, IntPtr high, uint method);
        Process LaunchDetached(string executable, string arguments) {
            // Real inherited file handles outlive this GUI. Anonymous stderr pipes
            // would break when the launcher closes while the VM keeps running.
            var security = new SecurityAttributes { Length = Marshal.SizeOf(typeof(SecurityAttributes)), Inherit = 1 };
            IntPtr output = CreateFile(Path.Combine(UserData, "logs/qemu.log"), 0x40000000, 3, ref security, 4, 0x80, IntPtr.Zero);
            IntPtr input = CreateFile("NUL", 0x80000000, 3, ref security, 3, 0x80, IntPtr.Zero);
            try {
                if (output == new IntPtr(-1) || input == new IntPtr(-1)) throw new Win32Exception(Marshal.GetLastWin32Error());
                SetFilePointer(output, 0, IntPtr.Zero, 2);
                var startup = new StartupInfo { Size = Marshal.SizeOf(typeof(StartupInfo)), Flags = 0x101, Show = 0, Input = input, Output = output, Error = output };
                ProcessInfo process;
                if (!CreateProcess(executable, new StringBuilder(Quote(executable) + " " + arguments), IntPtr.Zero, IntPtr.Zero,
                    true, 0x08000000, IntPtr.Zero, Root, ref startup, out process)) throw new Win32Exception(Marshal.GetLastWin32Error());
                CloseHandle(process.Thread); CloseHandle(process.Process);
                return Process.GetProcessById(process.Pid);
            } finally { if (output != new IntPtr(-1)) CloseHandle(output); if (input != new IntPtr(-1)) CloseHandle(input); }
        }
        static void PrivateDirectory(string path) {
            Directory.CreateDirectory(path);
            var acl = new DirectorySecurity(); acl.SetAccessRuleProtection(true, false);
            foreach (var sid in new[] { WindowsIdentity.GetCurrent().User,
                new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null),
                new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null) })
                acl.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.FullControl,
                    InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
                    PropagationFlags.None, AccessControlType.Allow));
            Directory.SetAccessControl(path, acl);
        }
        static byte[] Join(params byte[][] arrays) { return arrays.SelectMany(a => a).ToArray(); }
        static byte[] Length(int size) {
            if (size < 128) return new[] { (byte)size };
            var bytes = new List<byte>(); for (int n = size; n > 0; n >>= 8) bytes.Insert(0, (byte)n);
            bytes.Insert(0, (byte)(128 | bytes.Count)); return bytes.ToArray();
        }
        static byte[] Positive(byte[] value) {
            int start = 0; while (start < value.Length - 1 && value[start] == 0) start++;
            byte[] result = value.Skip(start).ToArray();
            return (result[0] & 128) != 0 ? Join(new byte[] { 0 }, result) : result;
        }
        static byte[] Integer(byte[] value) { value = Positive(value); return Join(new byte[] { 2 }, Length(value.Length), value); }
        static byte[] SshField(byte[] value) {
            int n = value.Length; return Join(new[] { (byte)(n >> 24), (byte)(n >> 16), (byte)(n >> 8), (byte)n }, value);
        }
        public static void CreateSshIdentity(string directory) {
            // Optional Linux terminal access; generating keys does not require OpenSSH.
            PrivateDirectory(directory);
            string key = Path.Combine(directory, "admin-key");
            if (File.Exists(key) && File.Exists(key + ".pub")) return;
            if (File.Exists(key) || File.Exists(key + ".pub")) throw new IOException("Incomplete Linux access key pair in userdata. Restore both files from your folder backup.");
            using (var rsa = new RSACryptoServiceProvider(3072)) {
                rsa.PersistKeyInCsp = false; var p = rsa.ExportParameters(true);
                byte[] sequence = Join(Integer(new byte[] { 0 }), Integer(p.Modulus), Integer(p.Exponent),
                    Integer(p.D), Integer(p.P), Integer(p.Q), Integer(p.DP), Integer(p.DQ), Integer(p.InverseQ));
                string body = Convert.ToBase64String(Join(new byte[] { 48 }, Length(sequence.Length), sequence));
                var pem = new StringBuilder("-----BEGIN RSA PRIVATE KEY-----\n");
                for (int i = 0; i < body.Length; i += 64) pem.AppendLine(body.Substring(i, Math.Min(64, body.Length - i)));
                pem.AppendLine("-----END RSA PRIVATE KEY-----");
                File.WriteAllText(key, pem.ToString(), new UTF8Encoding(false));
                string pub = "ssh-rsa " + Convert.ToBase64String(Join(SshField(Encoding.ASCII.GetBytes("ssh-rsa")),
                    SshField(Positive(p.Exponent)), SshField(Positive(p.Modulus)))) + " roleweaver-local-demo";
                File.WriteAllText(key + ".pub", pub + "\n", new UTF8Encoding(false));
            }
        }
        public Process ManagedProcess() {
            string state = Path.Combine(UserData, "vm-state.json");
            if (!File.Exists(state)) return null;
            VmRecord record = Json.Deserialize<VmRecord>(File.ReadAllText(state));
            Process process;
            try { process = Process.GetProcessById(record.Pid); } catch (ArgumentException) { return null; }
            try {
                if (process.HasExited) return null;
                if (!string.Equals(Path.GetFullPath(process.MainModule.FileName), Qemu, StringComparison.OrdinalIgnoreCase) ||
                    process.StartTime.ToUniversalTime().Ticks != record.Started)
                    throw new InvalidOperationException("The saved process belongs to a different application. This launcher will not control it.");
                return process;
            } catch { process.Dispose(); throw; }
        }
        public virtual bool IsRunning() { using (var p = ManagedProcess()) return p != null; }
        public void Prepare() {
            foreach (string relative in new[] { "runtime/qemu/qemu-system-x86_64.exe", "runtime/qemu/qemu-img.exe", "runtime/base.qcow2", "runtime/vmlinuz" })
                if (!File.Exists(Path.Combine(Root, relative))) throw new FileNotFoundException("Missing " + relative + ". Extract the complete ZIP into a writable folder before starting.");
            PrivateDirectory(UserData);
            Directory.CreateDirectory(Path.Combine(UserData, "logs"));
            Directory.CreateDirectory(Path.Combine(UserData, "boot"));
            CreateSshIdentity(UserData);
            SaveSettings();
            WriteJson(Path.Combine(UserData, "boot", "instance.json"), new {
                version = 1, instance = Settings.Instance, dashboard_port = Settings.DashboardPort,
                ssh_public_key = File.ReadAllText(Path.Combine(UserData, "admin-key.pub")).Trim() });
            string disk = Path.Combine(UserData, "demo.qcow2");
            if (!File.Exists(disk)) {
                var info = new ProcessStartInfo(Path.Combine(Root, "runtime/qemu/qemu-img.exe"),
                    Arguments(new[] { "create", "-f", "qcow2", "-F", "qcow2", "-b", "../runtime/base.qcow2", "userdata/demo.qcow2" })) {
                    WorkingDirectory = Root, UseShellExecute = false, CreateNoWindow = true,
                    RedirectStandardError = true, RedirectStandardOutput = true };
                using (var p = Process.Start(info)) {
                    string error = p.StandardError.ReadToEnd(); p.StandardOutput.ReadToEnd(); p.WaitForExit();
                    if (p.ExitCode != 0) throw new IOException("Could not create the demo disk. " + error);
                }
            }
        }
        void CheckPorts() {
            foreach (int port in new[] { Settings.DashboardPort, Settings.SshPort, Settings.ControlPort }) {
                var listener = new TcpListener(IPAddress.Loopback, port);
                try { listener.Start(); } catch (SocketException) { throw new IOException("Port " + port + " is already in use. Stop the other demo first, or choose different ports under Advanced settings."); }
                finally { listener.Stop(); }
            }
            using (var socket = new UdpClient()) {
                socket.ExclusiveAddressUse = true;
                try { socket.Client.Bind(new IPEndPoint(IPAddress.Loopback, Settings.GamePort)); }
                catch (SocketException) { throw new IOException("Game port " + Settings.GamePort + " is already in use. Stop the other demo or change the game port."); }
            }
        }
        public virtual void Start() {
            if (IsRunning()) return;
            Prepare(); CheckPorts();
            var args = new[] { "-name", "Role Weaver Demo", "-L", "runtime/qemu/share", "-machine", "q35,hpet=off", "-accel", "tcg,thread=multi", "-cpu", "max", "-smp", "2", "-m", Settings.MemoryMB.ToString(),
                "-kernel", "runtime/vmlinuz", "-append", "root=/dev/vda1 rw console=ttyS0 noapic",
                "-drive", "file=userdata/demo.qcow2,if=virtio,format=qcow2,discard=unmap",
                "-drive", "file=fat:ro:userdata/boot,if=virtio,format=raw,readonly=on",
                "-device", "virtio-rng-pci", "-nic", "user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:" + Settings.SshPort + "-:22,hostfwd=tcp:127.0.0.1:" + Settings.DashboardPort + "-:8748,hostfwd=udp:127.0.0.1:" + Settings.GamePort + "-:5127",
                "-qmp", "tcp:127.0.0.1:" + Settings.ControlPort + ",server=on,wait=off",
                "-display", "none", "-monitor", "none", "-serial", "file:userdata/logs/boot.log" };
            Process process = LaunchDetached(Qemu, Arguments(args));
            Thread.Sleep(300);
            if (process.HasExited) throw new IOException("The virtual machine could not start. Open userdata/logs/qemu.log for details.");
            WriteJson(Path.Combine(UserData, "vm-state.json"), new VmRecord { Pid = process.Id, Started = process.StartTime.ToUniversalTime().Ticks });
        }
        public async Task WaitForDashboard(Action<string> status, CancellationToken cancel) {
            DateTime end = DateTime.UtcNow.AddMinutes(8);
            while (DateTime.UtcNow < end) {
                cancel.ThrowIfCancellationRequested();
                if (!IsRunning()) throw new IOException("The demo stopped during startup. Open userdata/logs/qemu.log for details.");
                try {
                    await Task.Run(() => Request("/login", null, false, 3000, cancel), cancel);
                    status("Dashboard ready. Connecting to the demo..."); return;
                } catch (WebException) { } catch (IOException) { }
                status("Starting Linux and the NWN server. The first start may take a few minutes...");
                await Task.Delay(2000, cancel);
            }
            throw new TimeoutException("The demo is taking longer than expected. It is still running. Check userdata/logs/boot.log, then choose Retry.");
        }
        public object Request(string path, object body = null, bool json = true, int timeout = 20000, CancellationToken cancel = default(CancellationToken)) {
            var request = (HttpWebRequest)WebRequest.Create(Dashboard + path);
            request.Proxy = null; request.AllowAutoRedirect = false; request.Timeout = timeout;
            request.ReadWriteTimeout = timeout; request.CookieContainer = cookies;
            // Abort the actual socket operation, not just the UI's wait for it.
            using (cancel.Register(request.Abort)) {
                try {
                    cancel.ThrowIfCancellationRequested();
                    if (body != null) {
                        request.Method = "POST"; request.ContentType = "application/json";
                        request.Headers["Origin"] = Dashboard;
                        byte[] bytes = Encoding.UTF8.GetBytes(Json.Serialize(body)); request.ContentLength = bytes.Length;
                        using (var stream = request.GetRequestStream()) stream.Write(bytes, 0, bytes.Length);
                    }
                    using (var response = request.GetResponse()) using (var reader = new StreamReader(response.GetResponseStream())) {
                        string text = reader.ReadToEnd(); cancel.ThrowIfCancellationRequested();
                        return json ? Json.DeserializeObject(text) : text;
                    }
                } catch (WebException) { cancel.ThrowIfCancellationRequested(); throw; }
                  catch (IOException) { cancel.ThrowIfCancellationRequested(); throw; }
            }
        }
        public void Login(string password, CancellationToken cancel = default(CancellationToken)) { Request("/api/login", new { password = password }, true, 60000, cancel); }
        public Dictionary<string, object> LlmStatus() { return (Dictionary<string, object>)Request("/api/llm"); }
        public string[] ListModels(string service, string key, string endpoint, CancellationToken cancel = default(CancellationToken)) {
            var result = (Dictionary<string, object>)Request("/api/llm-models", new {
                service = service, model = "", api_key = key.Trim(), base_url = endpoint,
                key_action = key.Length > 0 ? "replace" : "keep" }, true, 60000, cancel);
            return ((object[])result["models"]).Cast<string>().ToArray();
        }
        public void ChangePassword(string current, string kind, string password) {
            Request("/api/demo-password", new { current_password = current, kind = kind, password = password }, true, 60000);
        }
        public void SaveProvider(string service, string model, string key, string endpoint, bool keepKey) {
            var current = LlmStatus();
            Request("/api/llm", new { service = service, model = model.Trim(), api_key = key.Trim(),
                base_url = endpoint, key_action = keepKey && key.Length == 0 ? "keep" : key.Length > 0 ? "replace" : "clear",
                revision = (string)current["revision"] });
            Settings.SetupComplete = true; SaveSettings();
        }
        public string BridgeState() {
            var health = (Dictionary<string, object>)Request("/api/health");
            var parts = (Dictionary<string, object>)health["components"];
            var bridge = (Dictionary<string, object>)parts["bridge"];
            return (string)bridge["state"];
        }
        public void Shutdown() {
            using (var process = ManagedProcess()) {
                if (process == null) return;
                using (var client = new TcpClient()) {
                    client.Connect(IPAddress.Loopback, Settings.ControlPort);
                    var stream = client.GetStream(); stream.ReadTimeout = 5000; stream.WriteTimeout = 5000;
                    var reader = new StreamReader(stream); var writer = new StreamWriter(stream, new UTF8Encoding(false)) { AutoFlush = true };
                    var greeting = Json.Deserialize<Dictionary<string, object>>(reader.ReadLine());
                    if (!greeting.ContainsKey("QMP")) throw new IOException("Unexpected VM control response.");
                    foreach (string command in new[] { "qmp_capabilities", "system_powerdown" }) {
                        writer.WriteLine(Json.Serialize(new { execute = command }));
                        while (true) {
                            string line = reader.ReadLine(); if (line == null) throw new IOException("VM control connection closed.");
                            var reply = Json.Deserialize<Dictionary<string, object>>(line);
                            if (reply.ContainsKey("error")) throw new IOException("The VM declined the shutdown request.");
                            if (reply.ContainsKey("return")) break;
                        }
                    }
                }
                if (!process.WaitForExit(60000)) throw new TimeoutException("Shutdown is still in progress. Please wait before moving the folder. No forced power-off was used.");
                File.Delete(Path.Combine(UserData, "vm-state.json"));
            }
        }
    }
}
