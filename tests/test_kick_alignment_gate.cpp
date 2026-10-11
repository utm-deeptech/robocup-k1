#include <cassert>
#include <limits>
#include "utils/kick_alignment_gate.h"

int main() {
    KickAlignmentGate gate;
    // Alignment while walking from far away must not prime an immediate kick.
    assert(!gate.update(1000, true, false, 500));
    assert(!gate.update(10000, true, false, 500));
    assert(!gate.update(10010, true, true, 500));
    assert(!gate.update(10509, true, true, 500));
    assert(gate.update(10510, true, true, 500));
    // Losing the ball/alignment cancels the accumulated hold.
    assert(!gate.update(10520, false, true, 500));
    assert(!gate.update(10530, true, true, 500));
    assert(gate.update(11030, true, true, 500));
    // A simulator clock reset must require a fresh hold period.
    assert(!gate.update(100, true, true, 500));
    assert(gate.update(600, true, true, 500));
    // Invalid clock samples cannot authorize a kick.
    assert(!gate.update(std::numeric_limits<double>::quiet_NaN(), true, true, 500));
    assert(!gate.update(700, true, true, 500));
}
