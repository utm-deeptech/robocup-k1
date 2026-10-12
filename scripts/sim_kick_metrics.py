"""Pure measurement helpers shared by the baseline recorder and summary."""
import math


def wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def direction(points):
    """Direction of a least-squares time-parametrized initial ball trajectory.

    Points are (simulation seconds, x, y); temporal fitting resolves the sign
    without assuming positive x travel. Never fit across a referee teleport.
    """
    if len(points) < 3:
        return None
    t0 = points[0][0]
    ts = [p[0] - t0 for p in points]
    mt = sum(ts) / len(ts)
    denom = sum((t - mt) ** 2 for t in ts)
    if denom <= 0:
        return None
    mx = sum(p[1] for p in points) / len(points)
    my = sum(p[2] for p in points) / len(points)
    vx = sum((t - mt) * (p[1] - mx) for t, p in zip(ts, points)) / denom
    vy = sum((t - mt) * (p[2] - my) for t, p in zip(ts, points)) / denom
    return math.atan2(vy, vx) if math.hypot(vx, vy) > 0.01 else None


def boundary_result(ball, length=14.0, width=9.0, goal_width=2.6, radius=0.11):
    """Geometric outcome; scoring is additionally confirmed by referee events."""
    x, y, z = ball
    # Match the installed referee: whole ball crosses the outer edge of the line.
    if x - radius > length / 2 + 0.025:
        if abs(y) + radius < goal_width / 2 and z + radius < 1.8:
            return 'goal'
        return 'wide'
    if abs(y) - radius > width / 2 + 0.025 or x + radius < -length / 2 - 0.025:
        return 'out'
    return None
