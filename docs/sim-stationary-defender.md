# Stationary defender added

A second K1 was attached to the current field through Booster's official `scene_edit/attach_robot` API. No container was recreated and no system source was changed. No dependencies were installed.

Requested position: (4.5, 0, 0), facing toward the center, blue color, team 2. Live physics confirmed the second K1 standing near (4.478, 0, 0.550), yaw approximately pi, upright (upDot approximately 0.999). It receives no soccer brain or movement commands.

The simulator renumbered the requested `robot4` to `robot2`. Its default referee roster treats robot2 as home player 2, so the new body is currently a stationary defender obstacle; opposing referee identity has not been verified or corrected. It should not be presented as a full two-team match.

Adding the body switched the simulator to per-robot ROS topics and restarted motion controllers in PREP. `scripts/sim_first_robot_bridge.py` bridges only robot1's RPC and state topics to the original single-player demo, leaving robot2's commands isolated. That bridge is running in the container; its log is `/root/robocup_demo/sim_first_robot_bridge.log`.

The RGB topic currently has zero publishers after the live scene change. The match was ended through `/match/end`. Reload Booster Studio's 3D view before restarting soccer; verify the camera resumes and remap its new robot1 camera topics if necessary.

Attach command (run from the host):

```bash
docker exec rxlma-k1 /usr/local/booster_robot/booster_robocup_sim/.venv/bin/python /root/robocup_demo/scripts/sim_add_opponent.py
```

The script performs a scene-edit budget preflight, checks the response, and checks live topology. Running again with a second robot already present returns `already_present` without creating another body. The first attempt using the source template failed because the packaged simulator has no `mjcf/K1_22dof.xml`; using its installed `robot_k1.basset` succeeded.

Evidence: `sim-add-opponent.log`, `sim-add-opponent-verify.log`, and live output of `scripts/sim_world_probe.py`. Changes remain on `local/sim-autonomy`: two helper scripts and this report.

## Retry after Studio reload (2026-10-11)

Reloading Studio did not restore images: `/rgbd_camera/rgb/image_compressed` had zero publishers. Restarting the host `booster-camera-renderer` with its existing command-line arguments and environment also produced no frames. The replacement renderer is subscribed and its log is `sim-camera-renderer.log`.

The cause is explicit in the installed simulator's `physics/process.py`, function `_update_native_render_model` (around line 422): native rendering is enabled only when `len(detect_robot_instances(model)) <= 1`. The simulator logs confirm `native render model disabled` and `Native render model skipped for multi-robot topology`. Thus the earlier recommendation to reload Studio was insufficient; this is a simulator feature restriction, not a stale GUI tab.

The first-robot bridge was verified with a successful SDK soccer-mode request and GetMode response after stopping the brain's repeated PREP-mode velocity calls. However, the camera-based soccer stack cannot resume autonomous perception with two robot instances through this native camera path. The referee match remains ended and the demo nodes were stopped; both robot bodies remain in the scene.

A single-robot scene restores the supported native rendering path. Retaining two robots requires a separately validated perception/rendering workflow; the repo's existing multi-robot detection converter is aimed at an older JSON topic API and is not a drop-in replacement for this simulator's typed detection topics. No system source was patched and no dependencies were installed.

The host-only helper `scripts/sim_restart_camera_renderer.py PID` preserves the existing renderer arguments and environment, waits for termination, and avoids launching a duplicate if Studio restarts it. Restarting alone cannot overcome the simulator's multi-robot rendering gate.
