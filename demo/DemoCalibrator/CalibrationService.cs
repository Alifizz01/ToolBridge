using System.Globalization;

namespace DemoCalibrator;

/// A simulated measurement channel with a factory offset error, like a real bench
/// instrument before calibration. The GUI is the only way the "vendor" exposes it.
public class CalibrationService
{
    const double FactoryOffsetError = 0.31;   // volts the channel reads too high, uncalibrated
    readonly Random noise = new Random(42);
    double appliedOffset;

    public string SerialNumber { get; } = "SN-0042";

    public double Measure(double setpoint)
    {
        Thread.Sleep(400);                               // the meter settles
        return setpoint + FactoryOffsetError - appliedOffset + (noise.NextDouble() - 0.5) * 0.004;
    }

    public void ApplyOffset(double offset) => appliedOffset = offset;

    public string SaveToDevice() => $"Saved offset {appliedOffset.ToString("0.000", CultureInfo.InvariantCulture)} V to {SerialNumber}";
}
