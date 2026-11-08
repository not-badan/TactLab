using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

[assembly: AssemblyTitle("Такт — конструктор кнопок")]
[assembly: AssemblyProduct("TactLab")]
[assembly: AssemblyCompany("TactLab contributors")]
[assembly: AssemblyVersion("1.0.0.0")]

namespace TactLab {
    sealed class Desktop : Form {
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool SetDllDirectory(string path);
        private readonly string root = AppDomain.CurrentDomain.BaseDirectory;
        private readonly Label status = new Label();
        private readonly Button browser = new Button();
        private readonly Panel controls = new Panel();
        private readonly string profile = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "TactLab", "WebView");
        private Process engine;
        private Uri address;
        private bool closing;

        [STAThread]
        static void Main() {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new Desktop());
        }

        Desktop() {
            Text = "Такт · конструктор кнопок";
            Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(1160, 820);
            MinimumSize = new Size(540, 420);
            Font = new Font("Segoe UI", 11);
            BackColor = Color.FromArgb(243, 246, 247);
            status.Text = "Открываем конструктор…";
            status.AutoSize = false;
            status.Dock = DockStyle.Fill;
            status.TextAlign = ContentAlignment.MiddleCenter;
            controls.Dock = DockStyle.Bottom;
            controls.Height = 68;
            browser.Text = "Открыть в браузере";
            browser.AutoSize = true;
            browser.Visible = false;
            browser.Anchor = AnchorStyles.Top;
            browser.Click += (s, e) => OpenBrowser();
            controls.Controls.Add(browser);
            controls.Resize += (s, e) => browser.Left = (controls.Width - browser.Width) / 2;
            Controls.Add(status);
            Controls.Add(controls);
            Shown += async (s, e) => await Start();
        }

        async Task Start() {
            try {
                SetDllDirectory(Path.Combine(root, "runtime", "desktop"));
                var info = new ProcessStartInfo(Path.Combine(root, "runtime", "python.exe"), "-B -u desktop_server.py");
                info.WorkingDirectory = Path.Combine(root, "app");
                info.UseShellExecute = false;
                info.CreateNoWindow = true;
                info.RedirectStandardInput = true;
                info.RedirectStandardOutput = true;
                info.RedirectStandardError = true;
                engine = Process.Start(info);
                // Keep diagnostics for startup failures, drain the pipe during the session.
                var errors = new System.Text.StringBuilder();
                engine.ErrorDataReceived += (s, e) => {
                    if (e.Data != null) lock (errors) {
                        if (errors.Length > 6000) errors.Remove(0, 3000);
                        errors.AppendLine(e.Data);
                    }
                };
                engine.BeginErrorReadLine();
                var read = engine.StandardOutput.ReadLineAsync();
                if (await Task.WhenAny(read, Task.Delay(90000)) != read)
                    throw new Exception("Локальный модуль расчёта не успел запуститься.");
                var line = await read;
                if (closing) return;
                if (!Uri.TryCreate(line, UriKind.Absolute, out address) ||
                    address.Scheme != "http" || address.Host != "127.0.0.1") {
                    string diagnostic;
                    lock (errors) diagnostic = errors.ToString();
                    throw new Exception("Не запустился модуль расчёта. Распакуйте архив целиком.\n" + diagnostic);
                }
                engine.EnableRaisingEvents = true;
                engine.Exited += (s, e) => {
                    if (!closing && IsHandleCreated) BeginInvoke((Action)(() => {
                        if (!closing) { MessageBox.Show(this, "Модуль расчёта остановился. Откройте Тaкт снова.", Text); Close(); }
                    }));
                };
                await ShowConstructor();
            } catch (Exception ex) {
                if (!closing) { MessageBox.Show(this, ex.Message, Text, MessageBoxButtons.OK, MessageBoxIcon.Error); Close(); }
            }
        }

        async Task ShowConstructor() {
            WebView2 view = null;
            try {
                var environment = await CoreWebView2Environment.CreateAsync(null, profile);
                if (closing) return;
                view = new WebView2 { Dock = DockStyle.Fill };
                Controls.Add(view);
                view.BringToFront();
                await view.EnsureCoreWebView2Async(environment);
                if (closing) return;
                view.CoreWebView2.Settings.IsStatusBarEnabled = false;
                view.CoreWebView2.Settings.AreDevToolsEnabled = false;
                view.CoreWebView2.DownloadStarting += PickDestination;
                view.Source = address;
            } catch (Exception) {
                if (closing) return;
                if (view != null) view.Dispose();
                status.Text = "Конструктор работает в вашем браузере.\nЗакройте это окно, чтобы завершить программу.";
                browser.Visible = true;
                OpenBrowser();
            }
        }

        void PickDestination(object sender, CoreWebView2DownloadStartingEventArgs args) {
            var deferral = args.GetDeferral();
            BeginInvoke((Action)(() => {
                try {
                    using (var dialog = new SaveFileDialog {
                        FileName = Path.GetFileName(args.ResultFilePath),
                        Filter = "Комплект для печати (*.zip)|*.zip", DefaultExt = "zip"
                    }) {
                        if (dialog.ShowDialog(this) == DialogResult.OK)
                            args.ResultFilePath = dialog.FileName;
                        else args.Cancel = true;
                    }
                } finally { deferral.Complete(); }
            }));
        }

        void OpenBrowser() {
            try { Process.Start(new ProcessStartInfo(address.AbsoluteUri) { UseShellExecute = true }); }
            catch { status.Text = "Откройте в браузере " + address.AbsoluteUri; }
        }

        protected override void OnFormClosing(FormClosingEventArgs e) {
            closing = true;
            if (engine != null) {
                try { engine.StandardInput.Close(); } catch (IOException) {}
                catch (InvalidOperationException) {}
            }
            base.OnFormClosing(e);
        }
    }
}