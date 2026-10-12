#!/usr/bin/env python3
"""Repeat first-kick trials against the frozen, camera-based two-robot setup.

Run in /root/robocup_demo with ROS and install/setup.bash sourced. Requires
the relay, native renderer, robot1 bridge, and corrected referee already live.
Ground truth is recorded by this test only, never fed to the soccer brain.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import threading
import time
import urllib.request

from sim_kick_metrics import boundary_result, direction, wrap

POSITIONS = [(0.0, 0.0), (1.0, -1.5), (1.0, 1.5), (2.0, -2.0), (2.0, 2.0)]
SIM_PYTHON = '/usr/local/booster_robot/booster_robocup_sim/.venv/bin/python'


def http(path, post=False):
    req = urllib.request.Request('http://127.0.0.1:38383' + path,
                                 data=b'' if post else None,
                                 method='POST' if post else 'GET')
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.load(response)


class Recorder:
    def __init__(self, output):
        import rclpy
        from rclpy.parameter import Parameter
        from rclpy.qos import qos_profile_sensor_data
        from geometry_msgs.msg import Pose2D, Point
        from sensor_msgs.msg import CompressedImage
        from std_msgs.msg import String
        from booster_msgs.msg import RpcReqMsg
        from brain.msg import Kick
        from booster_interface.msg import RemoteControllerState
        self.rclpy = rclpy
        self.remote_type = RemoteControllerState
        rclpy.init()
        self.node = rclpy.create_node('kick_baseline_test', parameter_overrides=[Parameter('use_sim_time', value=True)])
        self.remote = self.node.create_publisher(RemoteControllerState, '/remote_controller_state', 10)
        self.lock = threading.RLock()
        self.state = {}
        self.frames = []
        self.starts = []
        self.world = None
        self.raw = None
        self.last_decision = None
        self.closed = False

        def pose(key):
            return lambda m: self.update(key, [m.x, m.y, m.theta])

        self.subscriptions = [
            self.node.create_subscription(Pose2D, '/booster_soccer/robot_pose', pose('estimate'), qos_profile_sensor_data),
            self.node.create_subscription(Pose2D, '/soccer/sim/localization/robot_pose', pose('truth'), qos_profile_sensor_data),
            self.node.create_subscription(Point, '/booster_soccer/ball_position', lambda m: self.update('ball_estimate', [m.x, m.y]), qos_profile_sensor_data),
            self.node.create_subscription(CompressedImage, '/rgbd_camera/rgb/image_compressed', lambda m: self.update('camera', True), qos_profile_sensor_data),
            self.node.create_subscription(String, '/booster_soccer/player_decision', lambda m: self.update('decision', m.data), qos_profile_sensor_data),
            self.node.create_subscription(Kick, '/kick_ball', self.kick, qos_profile_sensor_data),
            self.node.create_subscription(RpcReqMsg, '/LocoApiTopicReq', self.rpc, qos_profile_sensor_data),
        ]
        def spin():
            from rclpy.executors import ExternalShutdownException
            try:
                rclpy.spin(self.node)
            except ExternalShutdownException:
                pass
        self.spin_thread = threading.Thread(target=spin, daemon=True)
        self.spin_thread.start()
        self.worker_log = (output / 'physics-worker.log').open('w')
        self.worker = subprocess.Popen([SIM_PYTHON, '-u', 'scripts/sim_kick_physics_worker.py'],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=self.worker_log, text=True, bufsize=1)
        self.reader = threading.Thread(target=self.read_world, daemon=True)
        self.reader.start()

    def update(self, key, value):
        with self.lock:
            self.state[key] = {'value': value, 'wall_time': time.time(),
                               'sim_time': self.node.get_clock().now().nanoseconds / 1e9}

    def kick(self, msg):
        self.update('kick', {'relative_dir': msg.dir, 'robot_theta': msg.robot_theta_to_field,
                            'ball_relative': [msg.x, msg.y], 'goal_relative': [msg.goal_x, msg.goal_y],
                            'power': msg.power, 'stamp': msg.header.stamp.sec + msg.header.stamp.nanosec / 1e9,
                            # Exact inverse of Brain::pubKickMsg in normal play / kickoff.
                            'calc_dir': wrap(msg.dir + msg.robot_theta_to_field)})

    def rpc(self, msg):
        try:
            header = json.loads(msg.header)
            if header.get('api_id') != 2038:
                return
            body = json.loads(msg.body)
        except (TypeError, ValueError):
            return
        with self.lock:
            event = {'kind': 'kick_rpc', 'wall_time': time.time(), 'body': body,
                     'sim_time': self.node.get_clock().now().nanoseconds / 1e9,
                     'state': dict(self.state), 'world': self.world}
            if self.raw:
                self.raw.write(json.dumps(event) + '\n')
            if body.get('start'):
                self.starts.append(event)

    def read_world(self):
        for line in self.worker.stdout:
            try:
                frame = json.loads(line)
            except ValueError:
                continue
            with self.lock:
                if frame.get('kind') == 'world':
                    self.world = frame
                    sample = {**frame, 'state': dict(self.state)}
                    self.frames.append(sample)
                    if len(self.frames) > 10000:
                        del self.frames[:5000]
                else:
                    sample = frame
                if self.raw:
                    self.raw.write(json.dumps(sample) + '\n')

    def command(self, command, **kwargs):
        self.worker.stdin.write(json.dumps({'command': command, **kwargs}) + '\n')
        self.worker.stdin.flush()

    def buttons(self, **fields):
        msg = self.remote_type(**fields)
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            self.remote.publish(msg)
            time.sleep(0.1)
        self.remote.publish(self.remote_type())

    def wait(self, predicate, seconds, label):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if predicate():
                return
            if self.worker.poll() is not None:
                raise RuntimeError('Physics worker exited')
            time.sleep(0.1)
        raise TimeoutError(label)

    def open_trial(self, path):
        with self.lock:
            if self.raw:
                self.raw.close()
            self.raw = path.open('w', buffering=1)
            self.frames.clear()
            self.starts.clear()

    def close(self):
        self.command('quit')
        self.worker.wait(timeout=10)
        self.reader.join(timeout=2)
        self.worker_log.close()
        if self.rclpy.ok():
            self.rclpy.shutdown()
        self.spin_thread.join(timeout=3)
        self.node.destroy_node()
        if self.raw:
            self.raw.close()


def state_at(event, key):
    sample = event['state'].get(key)
    return sample['value'] if sample else None


def stop_motion(client):
    # A walking RPC may be rejected while the skill changes modes or after END.
    # The brain's LT+X / END handling is the primary stop; preserve the result.
    try:
        client.Move(0, 0, 0)
    except RuntimeError as error:
        print(json.dumps({'stage': 'cleanup_move_rejected', 'error': str(error)}), flush=True)


def add_snapshot(row, prefix, event):
    row[prefix + '_sim_time'] = event.get('sim_time', event.get('time'))
    for key in ('truth', 'estimate'):
        sample = event['state'].get(key)
        if sample:
            for axis, value in zip(('x', 'y', 'theta'), sample['value']):
                row[prefix + '_' + key + '_' + axis] = value
            row[prefix + '_' + key + '_age_s'] = event['wall_time'] - sample['wall_time']
    kick = state_at(event, 'kick')
    if kick:
        row[prefix + '_calc_dir_rad'] = kick['calc_dir']
        row[prefix + '_relative_dir_rad'] = kick['relative_dir']
        row[prefix + '_kick_robot_theta_rad'] = kick['robot_theta']
        row[prefix + '_power'] = kick['power']
        row[prefix + '_kick_stamp'] = kick['stamp']
        row[prefix + '_kick_age_s'] = event['wall_time'] - event['state']['kick']['wall_time']
    ball = event.get('world')
    if ball and 'world' in ball:
        ball = ball['world']
    if ball and ball.get('ballPosition'):
        for axis, value in zip(('x', 'y', 'z'), ball['ballPosition']):
            row[prefix + '_ball_' + axis] = value
    estimate = state_at(event, 'ball_estimate')
    if estimate:
        row[prefix + '_ball_estimate_x'], row[prefix + '_ball_estimate_y'] = estimate


def initialize(rec, sdk_client, sdk, folder, trial):
    http('/match/end', True)
    subprocess.run(['bash', 'scripts/stop.sh'], stdout=subprocess.DEVNULL)
    rec.command('reset_robot')
    time.sleep(5)
    # Wait for the restarted locomotion service; this affects setup only.
    for attempt in range(5):
        try:
            sdk_client.ChangeMode(sdk.RobotMode.kSoccer)
            break
        except RuntimeError:
            if attempt == 4:
                raise
            time.sleep(1)
    with (folder / f'trial-{trial:02d}-startup.log').open('w') as log:
        subprocess.run(['bash', 'scripts/sim_start.sh', 'tree:=game_sim.xml', 'disable_com:=true'],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    time.sleep(3)
    rec.buttons(lt=True, a=True)
    rec.wait(lambda: 'Locate Success:' in Path('brain.log').read_text(errors='replace'), 60,
             'Vision localization did not succeed')
    rec.buttons(lt=True, b=True)
    http('/match/start', True)
    rec.wait(lambda: http('/status')['game']['state'] == 'playing', 100, 'Referee did not reach PLAY')


def run_trial(rec, client, sdk, folder, trial, repeat, position, timeout):
    row = {'trial': trial, 'repeat': repeat, 'requested_ball_x': position[0], 'requested_ball_y': position[1]}
    rec.open_trial(folder / f'trial-{trial:02d}.jsonl')
    initialize(rec, client, sdk, folder, trial)
    rec.starts.clear()
    rec.command('place_ball', position=[*position, 0.11])
    rec.wait(lambda: math.dist(rec.world['world']['ballPosition'][:2], position) < 0.03, 5, 'Ball placement failed')
    world = rec.world
    row.update({'start_sim_time': world['time'], 'ball_start_x': world['world']['ballPosition'][0],
                'ball_start_y': world['world']['ballPosition'][1]})
    print(json.dumps({'stage': 'trial_started', 'trial': trial, 'repeat': repeat, 'ball': position}), flush=True)
    Path(folder / f'trial-{trial:02d}-start-status.json').write_text(json.dumps(http('/status'), indent=2))
    started_wall = time.time()
    event_path = Path('.cache/defender-referee/events.jsonl')
    event_offset = event_path.stat().st_size
    begin = time.monotonic()
    activation = None
    contact = None
    impulse = None
    track = []
    fit_points = []
    last = None
    processed_wall = 0
    stopped = False
    stationary_since = None
    row['result'] = 'missed_contact'
    row['reason'] = 'no_kick_activation_before_timeout'
    while time.monotonic() - begin < timeout:
        with rec.lock:
            if not activation and rec.starts:
                activation = rec.starts[0]
                add_snapshot(row, 'activation', activation)
                print(json.dumps({'stage': 'kick_activation', 'trial': trial, 'time': activation['sim_time']}), flush=True)
            frames = [f for f in rec.frames if f['wall_time'] > processed_wall and f['wall_time'] >= started_wall]
        for frame in frames:
            processed_wall = frame['wall_time']
            ball = frame['world']['ballPosition']
            contacts = frame['world'].get('ballContacts', [])
            after_activation = activation and frame['wall_time'] >= activation['wall_time']
            if after_activation and not contact and any(c['name'] == 'robot1' for c in contacts):
                contact = frame
                add_snapshot(row, 'contact', frame)
            if after_activation:
                if last:
                    dt = frame['time'] - last['time']
                    travel = math.dist(ball[:2], last['world']['ballPosition'][:2])
                    speed = travel / dt if dt > 0 else 0
                    if dt <= 0 or travel > 0.4:
                        row['trajectory_discontinuity'] = True
                        break
                    if not impulse and contact and speed > 1.0:
                        impulse = last
                        add_snapshot(row, 'impulse', last)
                    if impulse:
                        dist = math.dist(ball[:2], impulse['world']['ballPosition'][:2])
                        if 0.10 <= dist <= 0.80 and not row.get('defender_contact') and not any(c['name'] == 'robot2' for c in contacts):
                            fit_points.append((frame['time'], ball[0], ball[1]))
                        if any(c['name'] == 'robot2' for c in contacts):
                            row['defender_contact'] = True
                        if speed < 0.05:
                            stationary_since = stationary_since or frame['time']
                        else:
                            stationary_since = None
                        robot = next(r for r in frame['world']['robots'] if r['name'] == 'robot1')
                        # Prevent later attempts from contaminating the first shot.
                        if not stopped and dist > 1.0 and math.dist(ball[:2], robot['position'][:2]) > 1.2:
                            rec.buttons(lt=True, x=True)
                            stop_motion(client)
                            stopped = True
                result = boundary_result(ball)
                if result:
                    row['result'], row['reason'] = result, 'whole_ball_crossed_boundary'
                    row['end_ball_x'], row['end_ball_y'] = ball[:2]
                    row['end_sim_time'] = frame['time']
                    break
                if impulse and stationary_since and frame['time'] - stationary_since > 3:
                    row['result'], row['reason'] = 'short', 'ball_stopped_inside_field'
                    row['end_ball_x'], row['end_ball_y'] = ball[:2]
                    break
            last = frame
            track.append((frame['time'], *ball))
        if row['reason'] not in ('no_kick_activation_before_timeout',):
            break
        if row.get('trajectory_discontinuity'):
            row['reason'] = 'referee_repositioned_ball'
            row['result'] = 'unresolved'
            break
        if activation and rec.world['time'] - activation['sim_time'] > 8 and not impulse:
            row['reason'] = 'no_shot_after_first_activation'
            break
        if impulse and rec.world['time'] - impulse['time'] > 30:
            row['result'], row['reason'] = 'unresolved', 'shot_observation_timeout'
            break
        time.sleep(0.05)
    events = []
    with event_path.open() as stream:
        stream.seek(event_offset)
        for line in stream:
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
    (folder / f'trial-{trial:02d}-events.json').write_text(json.dumps(events, indent=2))
    (folder / f'trial-{trial:02d}-brain.log').write_bytes(Path('brain.log').read_bytes())
    row['goal_confirmed_by_referee'] = any(e['type'] == 'goal' for e in events)
    if row['goal_confirmed_by_referee']:
        row['result'] = 'goal'
    elif row['result'] == 'goal':
        # Allow asynchronous referee events to arrive; require an actual goal event.
        time.sleep(0.5)
        with event_path.open() as stream:
            stream.seek(event_offset)
            events = [json.loads(line) for line in stream if line.strip()]
        row['goal_confirmed_by_referee'] = any(e['type'] == 'goal' for e in events)
        (folder / f'trial-{trial:02d}-events.json').write_text(json.dumps(events, indent=2))
        if not row['goal_confirmed_by_referee']:
            row['result'], row['reason'] = 'unresolved', 'geometric_goal_without_referee_confirmation'
    actual = direction(fit_points)
    row['direction_sample_count'] = len(fit_points)
    row['actual_dir_rad'] = actual
    row['contact_observed'] = bool(contact)
    row['kick_activations'] = len(rec.starts)
    row['duration_wall_s'] = time.time() - started_wall
    if actual is not None and activation and state_at(activation, 'kick'):
        row['aim_error_deg'] = math.degrees(wrap(actual - row['activation_calc_dir_rad']))
        reference = impulse or contact or activation
        rawworld = reference['world']
        if 'world' in rawworld:
            rawworld = rawworld['world']
        ball = rawworld['ballPosition']
        row['true_goal_dir_rad'] = math.atan2(-ball[1], 7.0 - ball[0])
        row['goal_center_error_deg'] = math.degrees(wrap(actual - row['true_goal_dir_rad']))
    http('/match/end', True)
    rec.buttons(lt=True, x=True)
    stop_motion(client)
    print(json.dumps({'stage': 'trial_result', **row}), flush=True)
    return row


def summary(rows, output):
    errors = [abs(r['aim_error_deg']) for r in rows if r.get('aim_error_deg') is not None]
    centers = [abs(r['goal_center_error_deg']) for r in rows if r.get('goal_center_error_deg') is not None]
    result = {'trials': len(rows), 'goals': sum(r['result'] == 'goal' for r in rows),
              'goal_percent': 100 * sum(r['result'] == 'goal' for r in rows) / len(rows),
              'trials_with_direction': len(errors),
              'mean_absolute_aim_error_deg': statistics.mean(errors) if errors else None,
              'max_absolute_aim_error_deg': max(errors) if errors else None,
              'mean_absolute_goal_center_error_deg': statistics.mean(centers) if centers else None,
              'max_absolute_goal_center_error_deg': max(centers) if centers else None,
              'outcomes': {key: sum(r['result'] == key for r in rows) for key in sorted(set(r['result'] for r in rows))}}
    (output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    columns = sorted(set().union(*(r.keys() for r in rows)))
    with (output / 'trials.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=4)
    parser.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Use a new output directory to preserve raw evidence')
    args.output.mkdir(parents=True)
    freeze = json.loads(Path('docs/two-robot-freeze.json').read_text())
    for file, expected in freeze['sha256'].items():
        if hashlib.sha256(Path(file).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Frozen baseline differs: ' + file)
    (args.output / 'protocol.json').write_text(json.dumps({
        'positions': POSITIONS, 'repeats': args.repeats, 'timeout_wall_s': args.timeout,
        'freeze': freeze, 'calc_dir_source': 'wrap(Kick.dir + Kick.robot_theta_to_field); exact in normal play and kickoff',
        'direction_fit': 'time regression on initial 0.10–0.80 m travel after first >1 m/s motion with robot1 contact',
        'target_goal': [7.0, 0.0], 'defender': [4.5, 0.0],
        'start_protocol': 'reset robot, vision localization, READY/SET/PLAY, place ball, first kick attempt',
        'post_shot_stop': 'stop striker once ball travels >1 m and is >1.2 m from striker',
        'truth_policy': 'test observer only; never published to brain',
        'additional_outcomes': 'short/unresolved retained rather than mislabelled as wide/out/missed contact'
    }, indent=2))
    rec = Recorder(args.output)
    rows = []
    import booster_robotics_sdk_python as sdk
    sdk.ChannelFactory.Instance().Init(0, 'lo')
    client = sdk.B1LocoClient()
    client.Init()
    try:
        rec.wait(lambda: rec.world and len(rec.world['world']['robots']) == 2, 10, 'Need two robot bodies')
        rec.wait(lambda: 'camera' in rec.state and time.time() - rec.state['camera']['wall_time'] < 1, 15, 'No camera frames')
        rec.wait(lambda: 'truth' in rec.state, 10, 'No ROS robot pose ground truth')
        for repeat in range(1, args.repeats + 1):
            for position in POSITIONS:
                trial = len(rows) + 1
                rows.append(run_trial(rec, client, sdk, args.output, trial, repeat, position, args.timeout))
                summary(rows, args.output)
        print(json.dumps({'stage': 'baseline_complete', **summary(rows, args.output)}), flush=True)
    finally:
        try:
            http('/match/end', True)
            stop_motion(client)
        finally:
            rec.close()


if __name__ == '__main__':
    main()
