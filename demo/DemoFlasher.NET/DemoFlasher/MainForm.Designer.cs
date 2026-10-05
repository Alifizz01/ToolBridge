// demo/DemoFlasher.NET/DemoFlasher/MainForm.Designer.cs
namespace DemoFlasher;
partial class MainForm
{
    private System.ComponentModel.IContainer components = null;
    private ComboBox cmbEcu; private TextBox txtPath; private Button btnBrowse; private Button btnFlash;
    private ProgressBar prgFlash; private Label lblStatus; private CheckBox chkNoResponse; private Button btnEraseAll;

    private void InitializeComponent()
    {
        cmbEcu = new ComboBox(); txtPath = new TextBox(); btnBrowse = new Button(); btnFlash = new Button();
        prgFlash = new ProgressBar(); lblStatus = new Label(); chkNoResponse = new CheckBox(); btnEraseAll = new Button();
        SuspendLayout();
        cmbEcu.Name = "cmbEcu"; cmbEcu.DropDownStyle = ComboBoxStyle.DropDownList; cmbEcu.SetBounds(20, 20, 200, 24);
        txtPath.Name = "txtPath"; txtPath.SetBounds(20, 56, 300, 24);
        btnBrowse.Name = "btnBrowse"; btnBrowse.Text = "Browse..."; btnBrowse.SetBounds(330, 55, 90, 26);
        btnBrowse.Click += btnBrowse_Click;
        btnFlash.Name = "btnFlash"; btnFlash.Text = "Flash"; btnFlash.SetBounds(20, 92, 100, 30);
        btnFlash.Click += btnFlash_Click;
        btnEraseAll.Name = "btnEraseAll"; btnEraseAll.Text = "Erase all"; btnEraseAll.SetBounds(130, 92, 100, 30);
        btnEraseAll.Click += btnEraseAll_Click;
        chkNoResponse.Name = "chkNoResponse"; chkNoResponse.Text = "Simulate no response"; chkNoResponse.SetBounds(250, 96, 180, 24);
        prgFlash.Name = "prgFlash"; prgFlash.SetBounds(20, 134, 400, 18);
        lblStatus.Name = "lblStatus"; lblStatus.Text = "Ready"; lblStatus.SetBounds(20, 162, 400, 22);
        ClientSize = new Size(440, 200);
        Controls.AddRange(new Control[] { cmbEcu, txtPath, btnBrowse, btnFlash, btnEraseAll, chkNoResponse, prgFlash, lblStatus });
        Name = "MainForm"; Text = "DemoFlasher";
        ResumeLayout(false); PerformLayout();
    }
}
