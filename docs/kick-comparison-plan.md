# Completing the kick comparison

Plan agreed in the 2026-10-12 continuation. Work stays on `local/sim-autonomy`.

1. Restore the existing container's two-body scene, camera relay, robot1 bridge,
   and measurement referee. Require live camera samples, not just publishers.
2. Audit saved equal-window results before resuming. Six completed enhanced
   trials have 120-second windows; historical defender tilting remains a
   limitation and must be reported with the new profiles.
3. Use `--resume --max-new-trials 1` for a validation trial. Require vision-based
   localization, normal PLAY, a complete window, and a saved result. Inspect
   defender movement and runtime before committing to the remaining batch.
4. Finish enhanced and upstream visual-off profiles at the same five positions,
   four repeats each, with full 120-second simulation-time windows. Save raw
   observations and summary after every trial. Preserve failed setup recordings.
5. Compare goals, contacts, active-Kick contacts and exclusive failure categories
   against both historical profiles. Historical unequal windows are contextual
   only. Goals decide the new pair; active-Kick contacts break ties; an exact tie
   retains our gates. Report defender drift/tilt alongside the performance.
6. Keep our gates if they win or tie; otherwise select original upstream behavior
   while retaining the sim-only visual-off change. Document and commit that
   choice separately, then verify the selected startup.

Do not investigate the failed visual API further. Ground truth stays in the
test observer. No official-match agent is built until the sensing interface is
resolved; existing official-match research remains the feasibility report.

## Runtime and stopping criteria

Each observed trial costs at least two real minutes plus reset/localization and
READY/SET setup. The remaining 34 trials therefore need at least 68 minutes of
observation. The agent can wait for the simulator without consuming reasoning
tokens continuously, and uses compact result checks rather than streaming logs.

Do not silently restart an entire profile. Stop a batch on stalled physics,
missing camera samples, repeated localization failure, or a scene mismatch.
Inspect the saved error before retrying. No simulator/system patch or dependency
installation is part of this comparison.

The existing container is restarted in place. Opening Studio/its 3D view was
confirmed by the user in this continuation; no other GUI action is authorized.
