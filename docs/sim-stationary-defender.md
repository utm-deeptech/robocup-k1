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
