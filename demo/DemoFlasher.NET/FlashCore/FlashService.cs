// demo/DemoFlasher.NET/FlashCore/FlashService.cs
using System;
using System.IO;
using System.Threading;

namespace FlashCore
{
    /// The "vendor" logic a real flasher hides behind its GUI.
    public class FlashService
    {
        public bool SimulateNoResponse { get; set; }

        /// Flashes the file to the ECU. Returns bytes written; throws on error.
        public long Program(string path, string ecu, Action<int> progress = null)
        {
            if (string.IsNullOrEmpty(ecu)) throw new ArgumentException("No ECU selected");
            if (!File.Exists(path)) throw new FileNotFoundException("Hex file not found", path);
            if (SimulateNoResponse) { Thread.Sleep(500); throw new TimeoutException("ECU not responding"); }
            long size = new FileInfo(path).Length;
            for (int i = 1; i <= 10; i++) { Thread.Sleep(300); progress?.Invoke(i * 10); }
            return size;
        }

        public static string[] KnownEcus() => new[] { "ECU1", "ECU2", "Gateway" };
    }
}
