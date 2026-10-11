#pragma once
#include <cmath>

// Require uninterrupted near-ball alignment, measured in the caller's clock.
class KickAlignmentGate {
public:
    bool update(double nowMs, bool aligned, bool nearBall, double holdMs) {
        if (!std::isfinite(nowMs) || !aligned || !nearBall || nowMs < sinceMs_) {
            sinceMs_ = -1.0;
        }
        if (!std::isfinite(nowMs) || !aligned || !nearBall) return false;
        if (sinceMs_ < 0.0) sinceMs_ = nowMs;
        return nowMs - sinceMs_ >= holdMs;
    }

private:
    double sinceMs_ = -1.0;
};
