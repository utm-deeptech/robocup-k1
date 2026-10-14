# Research digest (collected 2026-10-15)

PDFs and `.txt` extractions are in `docs/research/papers/`.

| file | source | why it matters |
|---|---|---|
| rhoban2023.pdf | [Rhoban, KidSize champion 2023](https://arxiv.org/pdf/2402.00612) | Kick strategy as an MDP: value iteration offline, one-step search online |
| htwk_k1_2026.pdf | [HTWK TDP 2026](https://hsl.robocup.org/wp-content/uploads/2026/03/HTWK_Robots-tdp-697e37376feb4.pdf) | KidSize 2025 champions **on the K1**. Open firmware and RL gym |
| runswift_k1_2026.pdf | [rUNSWift TDP 2026](https://hsl.robocup.org/wp-content/uploads/2026/03/rUNSWift-tdp-69730fadbaa05.pdf) | Booster demo localisation is broken on the K1, and the stock BT is only "go to ball, kick" |
| berlin_united_k1_2026.pdf | [Berlin United TDP 2026](https://hsl.robocup.org/wp-content/uploads/2026/03/Berlin_United-tdp-69802e227011f.pdf) | Decide actions by simulating each kick's outcome. Team params optimised in sim |
| kura_3v3_2026.pdf | [KURA TDP 2026](https://lists.robocup.org/archives/list/robocup-humanoid@lists.robocup.org/message/7SQAEIWKAC5ESXNFQ24BNH6YSM7CTUJP/attachment/4/KURA_TDP_2026.pdf) | Coordination decides 3v3 games; dynamic attacker, support and keeper roles |
| nimbro2017.pdf | [NimbRo TeenSize 2017](https://arxiv.org/pdf/1809.05361) | Attack task: kick directly vs dribble to a better spot; task reassignment |
| redbackbots_k1_2026.pdf | [RedbackBots TDP 2026](https://hsl.robocup.org/wp-content/uploads/2026/04/RedbackBots-tdp-69c3420ddd041.pdf) | Replaces Booster vision, behaviour and localisation; test-driven behaviours |
| striker_rl_2025.pdf | [Agile striker from noisy input](https://arxiv.org/pdf/2512.06571) | RL striker, 66.7% success from 6.5 m. Long-term option only |
| repos/htwk-firmware | [NaoHTWK/Firmware-Salvador](https://github.com/NaoHTWK/Firmware-Salvador) | Real K1 competition code (see htwk-dribble.md) |

## Rhoban kick strategy (most transferable idea)
- State = ball position. Action = (kick type, yaw). Reward = −kick time − walk time to the new ball spot. Ball out of field = −penalty, goal = 0 extra.
- Offline: run value iteration over a field grid. V(s) means "seconds until we score from here".
- Online: for each candidate action, sample kick length and angle from a measured distribution and score `r + V(s')`. Add these penalties:
  - collision with any robot (recurse with a hit probability)
  - landing nearer to opponents than to us
  - the robot blocking our own goal while kicking
  - scoring when not allowed (indirect kick)
- Use the closest ally's walk time, not the kicker's own.
- Keep the top 10% of actions and pick by footstep cost.

**For us:** we have one kick type, at variable power and direction. Measure the kick's distance and angle spread per power, precompute V on a 0.25 m grid, then pick (direction, power) per tick. This fits easily inside the brain's tick.

## Lessons repeated across teams
1. Coordination beats individual skill in 3v3 (KURA). Avoid two robots chasing, and keep the goal covered.
2. Role switching needs hysteresis (HTWK, Rhoban "bonus for previous kicker").
3. Booster's stock behaviours are minimal. Every serious K1 team replaces the behaviour layer (rUNSWift, RedbackBots, HTWK).
4. Learned kicks (RL) are where top teams are heading. For us the built-in visual-kick policy *is* that learned kick, so use it.
