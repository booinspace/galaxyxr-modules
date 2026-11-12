using System;
using VRCFaceTracking.Core.Types;

namespace VirtualDesktop.FaceTracking
{
    /// <summary>
    /// Builds the (first, second) gaze pair from the direction the eye points,
    /// not from the eye quaternion's full orientation.
    ///
    /// Any spin about the line of sight (e.g. head roll baked into the
    /// quaternion as torsion) cannot change the direction, so it does not
    /// leak into the gaze values.
    ///
    /// The two angles are decomposed the same way the module's original
    /// conversion did (exact for Ry(yaw) * Rx(pitch)), so with a level head
    /// the output is identical to the original, including large diagonals.
    ///
    /// Homogeneous terms keep non-unit input scale-invariant. Invalid or
    /// zero quaternions return neutral gaze.
    /// </summary>
    internal static class GazeFix
    {
        public static Vector2 FromDirection(Quaternion q)
        {
            double x = q.X, y = q.Y, z = q.Z, w = q.W;
            double norm = x*x + y*y + z*z + w*w;
            if (!double.IsFinite(norm) || norm <= 0) return new Vector2(0, 0);

            // Homogeneous form preserves direction for non-unit input too.
            double dx = -2 * (x*z + w*y);
            double dy =  2 * (w*x - y*z);
            double c = w*w + z*z - x*x - y*y;
            float first = (float)Math.Atan2(dx, c);
            float second = (float)Math.Atan2(dy, Math.Sqrt(dx*dx + c*c));

            return new Vector2(first, second);
        }
    }
}
