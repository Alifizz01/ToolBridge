namespace DemoCalibrator;
partial class MainForm
{
    private System.ComponentModel.IContainer components = null;
    private Label lblSetpointCaption; private TextBox txtSetpoint; private Button btnMeasure; private Label lblMeasured;
    private Label lblOffsetCaption; private TextBox txtOffset; private Button btnApply; private Button btnSave;
    private Label lblSerial; private Label lblStatus;

    private void InitializeComponent()
    {
        lblSetpointCaption = new Label(); txtSetpoint = new TextBox(); btnMeasure = new Button(); lblMeasured = new Label();
        lblOffsetCaption = new Label(); txtOffset = new TextBox(); btnApply = new Button(); btnSave = new Button();
        lblSerial = new Label(); lblStatus = new Label();
        SuspendLayout();
        lblSetpointCaption.Name = "lblSetpointCaption"; lblSetpointCaption.Text = "Set point (V)"; lblSetpointCaption.SetBounds(20, 23, 100, 20);
        txtSetpoint.Name = "txtSetpoint"; txtSetpoint.Text = "10.000"; txtSetpoint.SetBounds(130, 20, 90, 24);
        btnMeasure.Name = "btnMeasure"; btnMeasure.Text = "Measure"; btnMeasure.SetBounds(230, 18, 90, 28);
        btnMeasure.Click += btnMeasure_Click;
        lblMeasured.Name = "lblMeasured"; lblMeasured.Text = "-"; lblMeasured.SetBounds(330, 23, 110, 20);
        lblOffsetCaption.Name = "lblOffsetCaption"; lblOffsetCaption.Text = "Offset (V)"; lblOffsetCaption.SetBounds(20, 63, 100, 20);
        txtOffset.Name = "txtOffset"; txtOffset.Text = "0.000"; txtOffset.SetBounds(130, 60, 90, 24);
        btnApply.Name = "btnApply"; btnApply.Text = "Apply"; btnApply.SetBounds(230, 58, 90, 28);
        btnApply.Click += btnApply_Click;
        btnSave.Name = "btnSave"; btnSave.Text = "Save to device"; btnSave.SetBounds(330, 58, 110, 28);
        btnSave.Click += btnSave_Click;
        lblSerial.Name = "lblSerial"; lblSerial.SetBounds(20, 103, 200, 20);
        lblStatus.Name = "lblStatus"; lblStatus.Text = "Ready"; lblStatus.SetBounds(20, 130, 420, 20);
        ClientSize = new Size(460, 165);
        Controls.AddRange(new Control[] { lblSetpointCaption, txtSetpoint, btnMeasure, lblMeasured, lblOffsetCaption,
                                          txtOffset, btnApply, btnSave, lblSerial, lblStatus });
        Name = "MainForm"; Text = "DemoCalibrator";
        ResumeLayout(false); PerformLayout();
    }
}
