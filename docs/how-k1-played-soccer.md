# How the K1 walked and kicked the ball

**Yes: a behavior tree (BT) made the soccer decisions.** It worked together
with camera vision, localization, a referee, and Booster's motion controller.
We configured and ran Booster's existing software; we did not train a new model.

**1. What each part does**

| Part | Plain-language job |
|---|---|
| Simulator | Creates the field, ball and robot, and calculates physical movement and contact. |
| Vision | Looks at robot-camera images and detects the ball, goalposts and field markings. |
| Localization | Uses detected field markings and robot motion measurements to estimate where the robot is on the field. |
| GameController | Acts as the referee: tells the robot whether the match is INITIAL, READY, SET or PLAY. |
| Brain / behavior tree | Chooses what to do next: look around, find the ball, approach it, adjust or activate a kick. |
| Booster motion controller | Turns movement and skill requests into coordinated robot motion. |
| ROS 2 | Carries messages between these parts. |

The basic flow is:

```text
Robot camera → Vision → Brain / behavior tree → Booster motion controller
                             ↑                           ↓
                       Referee + position          Robot moves in simulator
                             ↑                           ↓
                             └──── Updated observations ─┘
```

This is a feedback loop. As the robot moves, it receives new observations and
updates its next action.

**2. What a behavior tree means here**

A behavior tree is a structured set of conditions and actions. For example:

- If the referee has not started play, follow the preparation behavior.
- If the ball is lost, search for it.
- If the ball is visible, choose an approach or kicking action.
- If the conditions for the automatic visual kick are met, activate that skill.
- If the robot falls, use the recovery behavior.

The main tree is `src/brain/behavior_trees/game.xml`. It selects the appropriate
behavior for the current match state. During PLAY, a striker uses
`subtrees/subtree_striker_play.xml`.

That striker tree includes actions named `StrikerDecide`, `FindBall`, `Chase`,
`Adjust` and `RLVisionKick`. The XML organizes these actions; their detailed
logic is implemented in C++. The brain repeatedly evaluates the tree, with a
nominal loop rate of 100 times per second.

The BT selects and supervises actions. Booster's motion controller handles the
robot's movement. We did not implement walking balance or individual joint
trajectories ourselves. In this run, the brain requested Booster's existing
`RLVisionKick` skill through the locomotion API.

**3. What I did to make it work**

First, I tested basic movement independently of soccer. A small Python script
used the installed Booster SDK to request PREP, then WALKING, move forward,
turn and stop. It watched the simulator's position topic to decide when to stop.
This proved that code could control the robot.

Then I prepared the official `robocup_demo` stack inside the existing robot
container, where it could communicate directly with the robot:

- Connected its vision settings to the simulator's camera topics.
- Downloaded the actual simulation ONNX models; the cloned files were only
  Git LFS placeholders.
- Set the robot to team 1, striker, with role switching disabled.
- Installed missing build dependencies and built all nine packages without CUDA.
- Worked around a misplaced BehaviorTree library export using files inside the
  repo, without changing `/opt/ros`.
- Fixed simulator launch settings so the GameController accepted the built-in
  referee's packets.

The walking test had left the robot away from the demo's expected entrance
position. I returned robot1 to its initial position using the simulator's reset
command. I then sent the documented LT+A localization and LT+B handover signals
from code, requested soccer motion mode, and started the built-in referee.

Once initialized, the official stack selected the approach and kick itself.
I did not send a timed sequence of walking commands to reach the ball or manually
trigger the kick. The behavior-tree XML was unchanged.

**4. What proves it worked**

| Observation | Evidence |
|---|---|
| Robot localized | Brain estimated approximately `(-5.01, 5.01)` m; simulator truth was approximately `(-5.00, 4.98)` m. |
| Vision ran | The ONNX vision node processed live camera frames and published ball and field detections. |
| Match started | The referee advanced through READY → SET → PLAY. |
| Robot acted autonomously | It moved into the field, approached the center ball and the brain issued `RLVisionKick(start=true)`. |
| Physical ball contact occurred | The automatic referee recorded `ball_touch` by `robot1` at simulation time `1021.512 s`. |
| Ball moved | Its position changed from `(0, 0)` to approximately `(6.36, -4.64)` m. |

Simulator ground-truth positions were used to verify the result. The demo's
localization used vision and motion measurements; we did not feed the ground-truth
robot pose into the brain to replace localization.

**5. What this result does and does not establish**

We demonstrated autonomous localization, ball finding, approach and a physical
kick after initialization. The kick went toward the sideline and did not score.
Reliable goal aiming, repeated successful play and a match against opponents
still need further work.

Startup was initialized through commands during this session. We have not yet
packaged the entire startup, localization and referee handover into a single
automatic launch procedure.

The next improvement is to check camera geometry and odometry calibration,
compare estimated ball/robot positions with simulator truth, and improve kick aim.

All authored changes are on branch `local/sim-autonomy` in `~/robocup_demo`.
The technical commands and dependency details are in
[the milestone report](sim-soccer-progress.md); recorded verification is in
[the evidence file](sim-soccer-evidence.json).
