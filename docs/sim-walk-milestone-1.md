# Milestone 1: virtual K1 walking

Executed 2026-10-11 in existing container `rxlma-k1`, SDK 1.5.6.
No dependencies installed. Container was stopped (exit 143); restarted in place.

## Commands

```bash
docker ps -a --format '{{.Names}}\t{{.Status}}\t{{.Image}}'
git -C ~/robocup_demo switch -c local/sim-autonomy
docker start rxlma-k1
docker exec rxlma-k1 bash -lc 'source /opt/ros/humble/setup.bash; ros2 topic list'
docker exec rxlma-k1 bash -lc 'source /opt/ros/humble/setup.bash; ros2 topic info /LocoApiTopicReq -v'
docker exec -i rxlma-k1 bash -lc 'source /opt/ros/humble/setup.bash; python3 -u - --interface lo' < ~/robocup_demo/scripts/sim_walk_smoke.py
```

Inspected installed official example:
`/usr/local/lib/python3.10/dist-packages/python_example/sdk_pybind_b1_example.py`.
Inspected `/opt/booster/BoosterRos2/fastdds_profile.xml`: loopback permitted.
An initial attempt with `--interface eth0` failed discovery with SDK code 100;
the loopback run succeeded without changing DDS configuration.

## Evidence

Ground truth topic: `/soccer/sim/localization/robot_pose` (`geometry_msgs/Pose2D`).

| Stage | x (m) | y (m) | theta (rad) |
|---|---:|---:|---:|
| Before | -4.999969 | 4.976532 | -1.569964 |
| WALKING / forward start | -4.991535 | 4.977155 | -1.496449 |
| After forward / settling | -5.117805 | 3.706115 | -1.513828 |
| After turn / settling | -5.049191 | 3.611607 | 0.210228 |
| Stopped / additional 2 s settling | -5.028338 | 3.625603 | 0.222867 |

SDK mode query returned `RobotMode.kWalking`. Script exited 0.
Forward displacement was 1.277 m; turn was 98.8 degrees to the after-turn
sample (99.5 degrees after further settling). Walking inertia and gait settling
overshot the 1 m / 90 degree feedback thresholds. Zero velocity was sent after
each phase and again in the final cleanup. The robot remains in WALKING mode.

## Limits and next step

This verifies locomotion only; soccer has not been started or built.
The script rejects stale pose data, bounds each motion phase, and attempts a stop
on errors. It does not provide precision stopping or obstacle avoidance.
An attempted ROS interface inspection without Booster's overlay reported
`Unknown package 'booster_msgs'`; locate/source the overlay for milestone 2.
Stop after this milestone report before starting milestone 2.
