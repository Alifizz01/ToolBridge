using System.Globalization;
namespace DemoCalibrator;

public partial class MainForm : Form
{
    readonly CalibrationService service = new CalibrationService();
    static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

    public MainForm()
    {
        InitializeComponent();
        lblSerial.Text = service.SerialNumber;
    }

    static bool TryNumber(string s, out double v) =>
        double.TryParse(s.Replace(',', '.'), NumberStyles.Float, Inv, out v);

    private async void btnMeasure_Click(object sender, EventArgs e)
    {
        if (!TryNumber(txtSetpoint.Text, out double sp))
        {
            MessageBox.Show(this, "Set point is not a number", "DemoCalibrator", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        btnMeasure.Enabled = false; lblStatus.Text = "Measuring...";
        double v = await Task.Run(() => service.Measure(sp));
        lblMeasured.Text = v.ToString("0.000", Inv) + " V";
        lblStatus.Text = "Ready"; btnMeasure.Enabled = true;
    }

    private void btnApply_Click(object sender, EventArgs e)
    {
        if (!TryNumber(txtOffset.Text, out double off))
        {
            MessageBox.Show(this, "Offset is not a number", "DemoCalibrator", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        service.ApplyOffset(off);
        lblStatus.Text = "Offset applied";
    }

    private void btnSave_Click(object sender, EventArgs e) => lblStatus.Text = service.SaveToDevice();
}
