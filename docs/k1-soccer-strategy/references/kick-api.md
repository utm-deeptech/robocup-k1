# K1 visual kick: verified mechanics

## Root cause of "ball never moves" (2026-10-14 to 15)
Our probe enabled VisualKick and streamed `Kick` refs, but **never switched the robot to Soccer mode**. Booster's `SoccerKickManager.start()` always calls `ChangeMode(kSoccer)` first. With Soccer mode on, the kick worked on the first try.

The `version` field was not the problem: JSON `1` is `kV2` (`b1_loco_api.hpp`: kV1 = 0, kV2 = 1), which matches Booster.

## Reference implementation (Booster SDK, read-only)
`/usr/local/lib/python3.10/dist-packages/boosteros/robots/booster/_motion/soccer_kick.py` in the container.

```
start():   loco_client.ChangeMode(RobotMode.kSoccer)   # wait until GetMode()==kSoccer (5 s timeout)
           loco_client.VisualKick(True, version=VisualKickVersion.kV2)
update_command(direction, power):    # direction = yaw relative to current heading, rad; power 1..10
           freeze a virtual goal 8 m away along heading+direction, in odom
update_ball(x, y):                   # ball in current robot frame (x fwd, y left), metres
           publish Kick{x, y, goal_x, goal_y (goal re-projected into the robot frame), power,
                        robot_theta_to_field = robot_yaw_odom - goal_dir_odom, dir = 0}
stop():    VisualKick(False)
```
Publisher: `B1VisualKickReferencePublisher().InitChannelWithName(robot_name)`, which is DDS `rt/<robot>/kick_ball`, or `rt/kick_ball` when no name is set.

Our C++ equivalents are in `src/brain/src/robot_client.cpp`: `changeRobocupMode()` sends kSoccer, and `RLVisionKick(start)` sends api 2038. Make sure the brain calls `changeRobocupMode()` before `RLVisionKick(true)`.

## How Booster's AI drives it (`com.booster.default3v3ai`)
- Kick hysteresis: enter at ball distance **< 2.5 m**, exit at **> 3.0 m** after a **1.5 s** delay, with a minimum of **1.0 s** active.
- Power **1.5** for all shots.
- While kicking, the policy owns the chassis. Velocity commands are ignored until the kick is released.
- Kick targets are field points (goal centre, pass target or dribble point), converted to a relative `direction`.

## Measurements (truth used for measuring only)
| date | power | ball start dist | travel | peak speed | notes |
|---|---|---|---|---|---|
| 2026-10-15 | 1.5 | 1.0 m | 8.73 m | 2.68 m/s | robot upright, clean |
| 2026-10-15 | 3.0 | 1.5 m | 4.0 m* | 3.19 m/s | *ball reached the field edge, so travel is truncated |
| 2026-10-15 | 1.0 | 1.5 m | 0 | 0 | invalid: ball was placed outside the field (y = −6.4) |

TODO: build a full power-to-distance curve with the robot reset to the field centre, facing +x.

## Gotchas
- Fresh container (robot1 only): topics have no namespace (`/LocoApiTopicReq`, `/kick_ball`), so use `BoosterRobot(virtual_robot_name='')`. After `sim_add_opponent.py`, they become `/robot1/...`.
- `BoosterRobot.get_mode()` reports Soccer mode as "walk" (a public alias). Check `loco_client.GetMode().mode` for the raw `kSoccer(4)`. After `VisualKick(False)`, the raw mode stays kSoccer.
- Our brain calls `changeRobocupMode()` (kSoccer) **only once at startup** (`RobocupWalk` under RunOnce, `brain_tree.cpp`). Anything that resets the motion controller can drop the mode, for example a sim reset or teleport, a penalty, a get-up, or attaching a second robot. After that, `RLVisionKick()` silently does nothing. Re-assert kSoccer before every `RLVisionKick(true)`, which is cheap and idempotent.
