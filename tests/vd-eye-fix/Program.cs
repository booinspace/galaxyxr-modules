using System;
using VirtualDesktop.FaceTracking;

internal static class Program
{
    private static Quaternion Multiply(Quaternion a, Quaternion b) => new Quaternion(
        a.W*b.X + a.X*b.W + a.Y*b.Z - a.Z*b.Y,
        a.W*b.Y - a.X*b.Z + a.Y*b.W + a.Z*b.X,
        a.W*b.Z + a.X*b.Y - a.Y*b.X + a.Z*b.W,
        a.W*b.W - a.X*b.X - a.Y*b.Y - a.Z*b.Z);

    private static void Main()
    {
        int cases = 0;
        foreach (int yaw in new[] {-60, -30, 0, 30, 60})
        foreach (int pitch in new[] {-60, -30, 0, 30, 60})
        {
            double y = yaw*Math.PI/360, p = pitch*Math.PI/360;
            var q = Multiply(new Quaternion(0, (float)Math.Sin(y), 0, (float)Math.Cos(y)),
                             new Quaternion((float)Math.Sin(p), 0, 0, (float)Math.Cos(p)));
            var expected = q.Cartesian();
            foreach (int roll in new[] {-180, -90, -45, 0, 45, 90, 180})
            foreach (float scale in new[] {-1e12f, -1f, -1e-12f, 1e-12f, 1f, 1e12f})
            {
                double r = roll*Math.PI/360;
                var tilted = Multiply(q, new Quaternion(0, 0, (float)Math.Sin(r), (float)Math.Cos(r)));
                tilted = new Quaternion(tilted.X*scale, tilted.Y*scale, tilted.Z*scale, tilted.W*scale);
                var actual = GazeFix.FromDirection(tilted);
                if (Math.Abs(actual.x - expected.x) > 0.000003 || Math.Abs(actual.y - expected.y) > 0.000003)
                    throw new Exception($"Gaze mismatch: yaw={yaw} pitch={pitch} roll={roll} scale={scale}");
                cases++;
            }
        }
        foreach (var bad in new[] {new Quaternion(0,0,0,0), new Quaternion(float.NaN,0,0,1),
                                    new Quaternion(0,float.PositiveInfinity,0,1)})
        {
            var result = GazeFix.FromDirection(bad);
            if (result.x != 0 || result.y != 0) throw new Exception("Invalid input did not return neutral gaze");
        }
        Console.WriteLine($"PASS: {cases} gaze/roll/scale cases, zero and non-finite inputs");
    }
}
