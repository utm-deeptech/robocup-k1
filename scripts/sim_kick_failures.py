#!/usr/bin/env python3
"""Classify saved kick trials using physics distance and BT decision timelines.

No robot/simulator connection. Durations use simulation time and exclude setup
and the test's final stop. Cooldown is an overlapping diagnostic interval,
estimated from visual-kick stop RPCs plus the configured 1.5 s cooldown.
"""
import argparse
import bisect
import collections
import csv
import json
import math
from pathlib import Path
import re

from sim_kick_metrics import wrap

CATEGORIES = ['never reached the ball', 'reached but never aligned (stuck in adjust)',
              'kick started but no contact', 'blocked by our added pause/cooldown logic', 'timeout / other']


def state_value(frame, key):
    return frame.get('state', {}).get(key, {}).get('value')


def analyze_trial(base, row, profile):
    trial = row['trial']
    begin = row['start_sim_time']
    events = json.loads((base / f'trial-{trial:02d}-events.json').read_text())
    finishes = [e['simTime'] for e in events if e.get('type') == 'match_finished'
                and e.get('simTime') is not None and e['simTime'] >= begin]
    end = min(finishes) if finishes else float('inf')
    durations = collections.defaultdict(float)
    longest = collections.defaultdict(float)
    ranges = []
    samples = []
    requests = []
    responses = []
    closest = None
    distance_min = float('inf')
    contacts = []
    prev = None
    run_state = None
    run_begin = None
    reset_wall_time = 0
    for line in (base / f'trial-{trial:02d}.jsonl').open():
        frame = json.loads(line)
        if frame.get('kind') == 'command_sent' and frame.get('command') == 'reset_robot':
            reset_wall_time = frame['wall_time']
        if frame.get('kind') == 'kick_rpc' and begin <= frame['sim_time'] <= end:
            requests.append(frame)
        if frame.get('kind') == 'kick_rpc_response' and begin <= frame['sim_time'] <= end:
            responses.append(frame)
        if frame.get('kind') != 'world' or not begin <= frame['time'] <= end:
            continue
        robot = next(r for r in frame['world']['robots'] if r['name'] == 'robot1')
        ball = frame['world']['ballPosition']
        distance = math.dist(robot['position'][:2], ball[:2])
        decision_sample = frame.get('state', {}).get('decision', {})
        decision = ((decision_sample.get('value') if decision_sample.get('wall_time',0) >= reset_wall_time else None)
                    or 'unknown').removeprefix('striker-')
        if prev:
            durations[prev[1]] += frame['time'] - prev[0]
        if decision != run_state:
            if run_state is not None:
                longest[run_state] = max(longest[run_state], frame['time'] - run_begin)
                ranges.append([run_begin, frame['time'], run_state])
            run_state, run_begin = decision, frame['time']
        prev = (frame['time'], decision)
        samples.append((frame['time'], robot['position'][:2], robot['yaw'], ball[:2], decision,
                        frame['wall_time'], state_value(frame, 'kick')))
        if any(c['name'] == 'robot1' for c in frame['world'].get('ballContacts', [])):
            contacts.append(frame['time'])
        if distance < distance_min:
            distance_min, closest = distance, frame
    if prev:
        longest[run_state] = max(longest[run_state], prev[0] - run_begin)
        ranges.append([run_begin, prev[0], run_state])
    times = [s[0] for s in samples]

    def at(seconds):
        return samples[min(bisect.bisect_left(times, seconds), len(samples) - 1)]

    starts = [q for q in requests if q['body'].get('start')]
    stops = [q for q in requests if not q['body'].get('start')]
    # Merge overlapping stop/cooldown intervals; count only observed PLAY time.
    cooling = []
    if profile == 'enhanced':
        for q in stops:
            low, high = q['sim_time'], min(q['sim_time'] + 1.5, prev[0])
            if cooling and low <= cooling[-1][1]:
                cooling[-1][1] = max(cooling[-1][1], high)
            elif high > low:
                cooling.append([low, high])
    result = {'trial': trial, 'baseline_result': row['result'], 'profile': profile,
              'ball_start_x': row['ball_start_x'], 'ball_start_y': row['ball_start_y'],
              'closest_truth_distance_m': distance_min, 'closest_sim_time': closest['time'],
              'closest_decision': (state_value(closest, 'decision') or 'unknown'),
              'visual_rpc_start_count': len(starts), 'visual_node_selected': durations['auto_visual_kick'] > 0,
              'Kick_node_ever_started': durations['kick'] > 0 or durations['cross'] > 0,
              'contact_anywhere_in_trial': bool(contacts),
              'kick_contact_after_first_activation': bool(row['contact_observed']),
              'observed_play_duration_s': samples[-1][0] - samples[0][0],
              'settle_pause_s': durations['settle'], 'settle_longest_s': longest['settle'],
              'cooldown_overlap_s': sum(high-low for low, high in cooling),
              'final_decision': samples[-1][4], 'final_decision_run_s': ranges[-1][1] - ranges[-1][0]}
    for name in ('find', 'chase', 'adjust', 'auto_visual_kick', 'kick', 'cross', 'settle', 'assist', 'unknown'):
        result[name + '_total_s'] = durations[name]
        result[name + '_longest_s'] = longest[name]
    dominant = max(durations, key=durations.get)
    result['longest_occupied_decision'] = dominant
    result['longest_occupied_decision_total_s'] = durations[dominant]
    robot = next(r for r in closest['world']['robots'] if r['name'] == 'robot1')
    ball = closest['world']['ballPosition']
    true_target = math.atan2(-ball[1], 7 - ball[0])
    result['closest_truth_heading_error_to_goal_deg'] = math.degrees(wrap(robot['yaw'] - true_target))
    result['closest_truth_robot_ball_line_error_deg'] = math.degrees(wrap(math.atan2(
        ball[1] - robot['position'][1], ball[0] - robot['position'][0]) - true_target))
    kick = state_value(closest, 'kick')
    estimate = state_value(closest, 'estimate')
    estimated_ball = state_value(closest, 'ball_estimate')
    if kick:
        result['closest_kick_target_age_s'] = closest['time'] - kick['stamp']
        result['closest_estimated_ball_range_m'] = math.hypot(*kick['ball_relative'])
        result['closest_estimated_ball_yaw_deg'] = math.degrees(math.atan2(kick['ball_relative'][1],kick['ball_relative'][0]))
        result['closest_truth_heading_error_to_CalcKickDir_deg'] = math.degrees(wrap(robot['yaw'] - kick['calc_dir']))
        if estimate and estimated_ball:
            rb = math.atan2(estimated_ball[1]-estimate[1], estimated_ball[0]-estimate[0])
            result['closest_brain_alignment_error_deg'] = math.degrees(wrap(kick['calc_dir'] - rb))
            result['closest_brain_heading_error_deg'] = math.degrees(wrap(kick['calc_dir'] - estimate[2]))
    visual_intervals = []
    for start in starts:
        t0 = start['sim_time']
        stop = next((q for q in stops if q['sim_time'] > t0), None)
        t1 = stop['sim_time'] if stop else samples[-1][0]
        first, last = at(t0), at(t1)
        target = state_value(start, 'kick')
        start_robot = start.get('world', {}).get('world', {}).get('robots', [])
        original_robot = next((r for r in start_robot if r['name']=='robot1'), None)
        start_ball = start.get('world', {}).get('world', {}).get('ballPosition')
        start_distance = math.dist(original_robot['position'][:2], start_ball[:2]) if original_robot and start_ball else math.dist(first[1],first[3])
        relevant = [s for s in samples if t0 <= s[0] <= t1]
        age_max = max((s[0] - s[6]['stamp'] for s in relevant if s[6]), default=None)
        entry = {'start_sim_time': t0, 'stop_sim_time': t1, 'rpc_active_s': t1-t0,
                 'truth_start_distance_m': start_distance,
                 'truth_end_distance_m': math.dist(last[1],last[3]),
                 'robot_displacement_m': math.dist(first[1],last[1]),
                 'maximum_kick_target_age_s': age_max,
                 'contact_while_rpc_active': any(t0 <= t <= t1 for t in contacts),
                 'estimated_start_range_m': math.hypot(*target['ball_relative']) if target else None}
        if target:
            entry['activation_truth_heading_error_deg'] = math.degrees(wrap(first[2]-target['calc_dir']))
        visual_intervals.append(entry)
    result['contact_while_visual_rpc_active'] = any(i['contact_while_rpc_active'] for i in visual_intervals)
    if visual_intervals:
        first = visual_intervals[0]
        result.update({'first_visual_active_s': first['rpc_active_s'],
                       'first_visual_truth_start_distance_m': first['truth_start_distance_m'],
                       'first_visual_robot_displacement_m': first['robot_displacement_m'],
                       'first_visual_maximum_target_age_s': first['maximum_kick_target_age_s']})
    if row['result'] != 'missed_contact':
        category = 'measured launch (not one of the 19 failures)'
    elif starts or result['Kick_node_ever_started']:
        category = CATEGORIES[2]
    elif distance_min > 1.0:
        category = CATEGORIES[0]
    elif durations['settle'] > 0 and profile == 'enhanced':
        category = CATEGORIES[3]
    elif durations['adjust'] > 0:
        category = CATEGORIES[1]
    else:
        category = CATEGORIES[4]
    result['category'] = category
    source_log = (base / f'trial-{trial:02d}-brain.log').read_text(errors='replace')
    result['visual_duration_limit_log_count'] = source_log.count('RLVisionKick duration limit reached')
    details = {'trial': trial, 'decision_intervals': ranges, 'cooldown_intervals': cooling,
               'visual_skill_intervals': visual_intervals,
               'responses': responses, 'contact_sim_times': contacts,
               'precision_transitions': [line for line in source_log.splitlines() if 'Precision striker:' in line]}
    return result, details


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', choices=('enhanced','upstream'), required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = json.loads((args.input / 'results.json').read_text())
    results, details = [], []
    for row in rows:
        result, detail = analyze_trial(args.input, row, args.profile)
        results.append(result)
        details.append(detail)
    (args.output / 'classification.json').write_text(json.dumps(results,indent=2)+'\n')
    (args.output / 'decision-timelines.json').write_text(json.dumps(details,indent=2)+'\n')
    columns = sorted(set().union(*(r.keys() for r in results)))
    with (args.output / 'classification.csv').open('w') as stream:
        writer = csv.DictWriter(stream,fieldnames=columns)
        writer.writeheader()
        writer.writerows(results)
    counts = {name:sum(r['category']==name for r in results) for name in CATEGORIES}
    summary = {'profile':args.profile,'trials':len(results),'failed_trials':sum(counts.values()),
               'categories':counts,'kick_node_started_trials':sum(r['Kick_node_ever_started'] for r in results),
               'visual_rpc_started_trials':sum(r['visual_rpc_start_count']>0 for r in results),
               'contact_while_visual_rpc_active_trials':sum(r['contact_while_visual_rpc_active'] for r in results),
               'post_activation_contact_trials':sum(r['kick_contact_after_first_activation'] for r in results),
               'notes':['Closest distance is ground-truth robot root to ball center, in meters.',
                        'Cached decision samples from before this trial robot reset are ignored.',
                        'Reached = within the 1 m chase/adjust threshold; activation failures take precedence.',
                        'Kick-node selection in the synchronous tree is the start evidence; visual RPC is recorded separately.',
                        'Cooldown duration overlaps other decisions; it is inferred from stop RPC time plus 1.5 s, not additive.',
                        'A reached, unactivated trial with observed settle is classified as pause/cooldown gate blocked; alignment oscillation can contribute.',
                        'Timeline excludes RESET/READY/SET and stops at the trial end referee event.']}
    (args.output / 'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
