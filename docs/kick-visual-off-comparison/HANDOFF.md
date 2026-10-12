# Visual-kick-off comparison: result (2026-10-12, 23:45)

Both profiles: 20 trials, same 5 ball positions x 4 repeats, fixed 120 s sim window,
`RLVisionKick.enableAutoVisualKick: false`.

| Profile | Goals | Walking-Kick contact | Failed trials |
|---|---:|---:|---:|
| Enhanced (our settle/cooldown gates) | 9/20 | 13/20 | 7 (4 gate-blocked, 3 stuck in adjust) |
| Original upstream | **12/20** | **20/20** | 0 |

Decision rule (approved 12:32): upstream wins, so revert our gates and keep only the
visual-kick-off change. **Not yet applied**: do it next session, then rebuild and verify startup.

Raw data: inside container `rxlma-k1:/root/robocup_demo/.cache/kick-upstream-visual-off-v1`
(909 MB). Host copy: `.cache/kick-upstream-visual-off-v1.tar.gz`.
