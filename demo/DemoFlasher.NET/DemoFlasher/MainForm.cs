// demo/DemoFlasher.NET/DemoFlasher/MainForm.cs
using FlashCore;
namespace DemoFlasher;

public partial class MainForm : Form
{
    readonly FlashService service = new FlashService();

    public MainForm()
    {
        InitializeComponent();
        cmbEcu.Items.AddRange(FlashService.KnownEcus());
    }

    private void btnBrowse_Click(object sender, EventArgs e)
    {
        using var dlg = new OpenFileDialog { Title = "Open", Filter = "Hex files|*.hex|All files|*.*" };
        if (dlg.ShowDialog(this) == DialogResult.OK) txtPath.Text = dlg.FileName;
    }

    private async void btnFlash_Click(object sender, EventArgs e)
    {
        btnFlash.Enabled = false; lblStatus.Text = "Flashing..."; prgFlash.Value = 0;
        service.SimulateNoResponse = chkNoResponse.Checked;
        string path = txtPath.Text, ecu = cmbEcu.Text;
        try
        {
            long n = await Task.Run(() => service.Program(path, ecu, p => Invoke(() => prgFlash.Value = p)));
            lblStatus.Text = $"Done: {n / 1024.0:0.0} kB written to {ecu}";
        }
        catch (Exception ex)
        {
            lblStatus.Text = "Error";
            MessageBox.Show(this, "Error: " + ex.Message, "DemoFlasher", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally { btnFlash.Enabled = true; }
    }

    private void btnEraseAll_Click(object sender, EventArgs e) => lblStatus.Text = "Erased";
}
