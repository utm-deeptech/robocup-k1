# Official Booster Champion 3v3 match research

Research snapshot: 2026-10-12. **Research only: no official-match agent, package, extension installation, match deployment, simulator change, or Booster Studio GUI action was performed.** The visual API failure is a dead end for this local sim; auto visual kick is disabled and its internals are not being investigated further.

## Findings

The official setup is a six-robot match with **one packaged Agent per team**, not six independent Studio agents. The runner assigns team 1 `robot1,robot2,robot3` and team 2 `robot4,robot5,robot6`, supplies team/roster environment variables, and runs each team's Agent in a separate mount/data sandbox. Our local two-robot fixture uses a different roster (robot2 is the stationary opponent); it must not be carried into the official match unchanged.

Our C++ robocup_demo strategy can in principle be hosted in this framework, but the existing single-robot launch is not a compliant drop-in Agent. It needs an Agent lifecycle wrapper, three robot instances or a team controller, correct per-team/per-robot I/O, referee integration, relocatable dependencies, and an official sensing source. The largest obstacle to reusing our current camera pipeline is that **this installed stock simulator deliberately disables native camera render-model publication for more than one robot**. The official bundled opponent avoids this by reading documented simulator truth topics. We have not changed the user's rule that truth is for tests only; no final agent has been switched to truth.

## How matches run

The installed Booster Studio version is `1.110.1`; the existing container image is `virtual-robot:0.8.4-beta-humble`. Studio ships these official runtime sources on the host:

- `/usr/share/booster-studio/resources/app/booster-native/statics/scripts/football3v3_runner/run.py`
- `launcher.py`, `sandbox.py`, `supervisor.py` in the same directory.
- `/usr/share/booster-studio/resources/app/booster-native/statics/ai-agent/football3v3/com.booster.default3v3ai.agent`

The team runner locates deployed Agents under `/opt/booster/booster_agent_data/data/agents/extract/<id>/`. It launches a supervisor for each team with `SOCCER_TEAM_ID` and `SOCCER_ROBOT_NAMES`. The supervisor reads `agent.json`, builds the packaged ROS/library environment, and invokes `ros2 launch <ros2.package_name> <ros2.launch_file>`. It then waits for the framework's `Inactive` state, requests lifecycle activation, and waits for `Active` (10-second waits). Merely starting three brain processes does not satisfy that Agent lifecycle handshake.

The referee handles Initial → Ready → Set → Playing and set plays, penalties, goals and match end. An agent consumes referee state and issues robot commands; it does not place balls, reset robots, change the scene, or operate match-control HTTP endpoints. Those actions in our kick harness are test-fixture operations and must stay outside a submitted Agent. Runtime control/observation uses the in-container HTTP service on port 38383; the match runner/operator uses `/health`, `/status`, `/match/start`, `/match/end` and referee event logs. Match duration and draw policy are configured by the organizer/runtime; the 120-second kick experiment is not an official match format.

These facts are verified against the installed official runtime, whose file hashes are saved in [local-source-manifest.json](official-match-research/local-source-manifest.json). They also align with the project's [runner internals](https://github.com/Samge0/booster-match-runner/blob/9e9b8bfcf00bfa632b57ffa122dc12b2bd483da4/docs/booster-internals.md).

**Current deployment status:** our existing container has only `com.boosterobotics.default` in its deployed Agent directory, and `/usr/local/booster_agent/football3v3_runner` is absent. The working port-38383 service is our local referee helper, not evidence that the official team Agent stack has been deployed. The stock runner/default opponent exist on the host, ready for Studio deployment. The Match Runner README says Studio's Run action deploys the required stack. Doing that is a future GUI action requiring the user's approval, and could replace the current local setup; it was not done during research.

## Agent packaging and submission

Booster's [Agent quick start](https://docs.booster.tech/docs/developer-guide/agent-development/quick-start/) uses `agent.toml` for identity, version, entry and requirements, plus `build.toml` for target platforms and dependencies. The entry class implements `AgentBase` lifecycle behavior. Studio's build produces a distributable `.agent` archive; its runtime metadata is `agent.json`, not the source TOML. For this machine the relevant target is `sim_x86_64`; binaries and linked ROS libraries must match the runtime architecture/ABI. Keep the Agent relocatable and include its libraries/models/configuration instead of relying on `/root/robocup_demo`, `.cache`, our renderer relay, or host paths.

Inspection of the actual bundled `.agent` ZIP verifies a concrete structure: root `agent.json`, resources under `res/`, an installed ROS layout under `agent/<package>/`, and architecture-specific dependency directories under `libs/`. The metadata names the ROS launch package/file. Do not assume a hand-written ZIP that merely starts a shell command will pass lifecycle checks or portal validation. Use the official build/package flow for the eventual submission; no package has been built in this phase.

Competition submission is through the signed-in team's **code upload** UI on [Booster Champion](https://champion.booster.tech/), distinct from installing a local Agent or publishing to the general Agent Store. The currently served portal frontend accepts `.agent` files and enforces a **300 MiB client-side file limit**. Its code requests an upload URL, uploads the archive, computes SHA-256, and submits the uploaded key, size and hash. No authenticated API, registration, upload, or submission was attempted. Backend acceptance and account eligibility have not been tested.

The public Season 1 page describes registration/course assessment, code submission and beating the entry-level AI to qualify, followed by Swiss rounds, groups and knockout stages. Its listed tournament dates are July 8–26, 2026, which are already past on this research date; it also advertises longer-term free battles. This is not a claim that a new tournament deadline or this account's submissions are open. The portal's linked complete Feishu rules/tutorials could not be accessed by the tools, so rules beyond the visible public summary are unverified.

Portal evidence was read from the public release-0.0.34 frontend, including [team uploader](https://fe-cdn.booster.tech/booster_competition_portal/release-0.0.34/assets/my-team-B3I1XTgH.js), [upload API flow](https://fe-cdn.booster.tech/booster_competition_portal/release-0.0.34/assets/index-DYWky5tO.js), and [public rules text](https://fe-cdn.booster.tech/booster_competition_portal/release-0.0.34/assets/home-CrTZX9-W.js). This is frontend evidence, not a successful submission or guarantee about future portal versions.

## The default opponent

The correct soccer opponent ID is **`com.booster.default3v3ai`**. It differs from **`com.boosterobotics.default`**, which is the generic built-in demo currently deployed here and does not play a 3v3 match. The bundled soccer Agent metadata is [saved here](official-match-research/default3v3ai-metadata.json): version `1.1.0`, Python Agent, entry `src/main.py:SoccerSimAgent`, ROS package `com_booster_default3v3ai`, launch file `launch.py`, minimum API level 10700. The stock `version.lock` has a separate distribution version and should not be confused with the Agent's own version.

The packaged Python source has a team behavior-tree runtime and an AgentBase lifecycle entry. Its truth provider subscribes to robot poses at `/teamN/robotX/soccer/sim/ground_truth/robot_pose` (own team and opponents) and ball pose at `/teamN/soccer/sim/ground_truth/ball`; referee state defaults to `/soccer/game_controller`. This is a **team strategy baseline using simulator state**, not a camera/YOLO opponent. It controls named virtual robots through the official SDK. It demonstrates the framework's intended multi-robot I/O, not blanket permission for every privately obtainable simulator datum.

## booster-match-runner

[Samge0/booster-match-runner](https://github.com/Samge0/booster-match-runner) is a community Studio extension that orchestrates the official runtime: select Red/Blue Agents, run visual or headless local matches, poll score/events, and archive results. It is not the competition submission service and does not provide missing camera support. We inspected source at commit `9e9b8bfcf00bfa632b57ffa122dc12b2bd483da4` (read-only clone in `.cache/research`), without building or installing it.

Its deployment code extracts a `.agent` according to `agent.json.id`; its default Blue opponent is `com.booster.default3v3ai`. It can clone an Agent under a different ID/package name for self-play. Its current start path also patches `/etc/profile.d/ros_env.sh` to inject framework environment exports and tears down stale team processes/cgroups before restarting the runner. These are real side effects to review before choosing to install/use it. None were executed in this phase. Installing this extension is optional: Studio's own match mode and official runner provide the underlying execution path.

## Cameras without our relay

The installed official simulator's `physics/process.py` around line 430 computes native rendering eligibility as `len(detect_robot_instances(model)) <= 1`; for multi-robot scenes it disables render-model publication and returns without exporting the native render model. The same source is installed inside the current container. We previously measured the resulting absence of native RGB publishers after attaching robot2; our relay only restores images for local experiments.

Thus, **on the version inspected here, a stock six-robot match does not supply the native multi-robot camera stream that our YOLO/locator pipeline requires without the relay**. The default opponent works without cameras because it uses the official truth provider. A visual match viewer is not proof that robot camera topics publish frames. No six-robot live camera test was performed in this phase because the official stack is not deployed and starting it would require the reserved GUI/deployment action. A future organizer/runtime version may change support; that must be measured on that version rather than inferred from a match viewer or this source snapshot.

The final Agent must not package or start `sim_multi_camera_relay.py`, access private physics WebSockets, export scenes, or modify the simulator to obtain images. Under the existing **truth-for-tests-only** rule, carrying our current camera pipeline unchanged into the stock official runtime is blocked by camera availability. If the user later chooses the organizer-documented truth interface for the final strategy, that is an explicit change to the sensing policy, not an automatic consequence of this research.

## What can be reused, and what needs adaptation

- Reuse the strategy's C++ behavior-tree logic, goal calculation and selected sim kick behavior, subject to further 3v3 validation.
- Add an AgentBase lifecycle wrapper that owns startup/stop of packaged brain processes and passes the supplied team/roster configuration. It must activate without manual controller-button sequences.
- Implement team/robot I/O through documented interfaces; remap all absolute brain/control topics and SDK endpoints correctly, rather than shipping our single-robot relay/bridge. Creating a ROS namespace alone does not remap absolute topic strings.
- Feed official referee state and obey READY/SET/set-play/penalty rules for all three players. Assign roles and team coordination under the actual roster.
- Resolve sensing first: either an official runtime with supported native multi-robot images, or a user-approved documented sensing interface. Do not build around our local camera workaround.
- Package binaries, compatible BehaviorTree/ROS dependencies and optional vision models for `sim_x86_64`; verify lifecycle activation and six-robot topic isolation before measuring performance against the default AI.

This is a feasibility assessment from source inspection, not a demonstrated packaged robocup_demo match. **No official-match implementation or build has begun.** Nothing was installed: only public-source downloads/read-only extraction and documentation were added. Full Feishu rules and account-specific submission eligibility remain unverified.
