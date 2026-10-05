// demo/DemoFlasher.NET/DemoFlasher/Program.cs
namespace DemoFlasher;
static class Program
{
    [STAThread]
    static void Main() { ApplicationConfiguration.Initialize(); Application.Run(new MainForm()); }
}
