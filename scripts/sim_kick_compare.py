#!/usr/bin/env python3
"""Compare archived profiles; choose gates only after two complete equal windows."""
import argparse
import json
import math
from pathlib import Path

from sim_kick_failures import CATEGORIES


def load_metrics(folder):
    rows=json.loads((folder/'classification.json').read_text())
    results=json.loads((folder/'results.json').read_text())
    metrics={'trials':len(rows), 'goals':sum(r['result']=='goal' for r in results),
             'any_contact_trials':sum(r['contact_anywhere_in_trial'] for r in rows),
             'Kick_contact_trials':sum(r['contact_during_Kick_decision'] for r in rows),
             'visual_contact_trials':sum(r['contact_while_visual_rpc_active'] for r in rows),
             'Kick_started_trials':sum(r['Kick_node_ever_started'] for r in rows),
             'visual_started_trials':sum(r['visual_rpc_start_count']>0 for r in rows),
             'failure_categories':{c:sum(r['category']==c for r in rows) for c in CATEGORIES}}
    return metrics,results,json.loads((folder/'protocol.json').read_text())


def validate_completed_windows(results, classifications, protocol):
    """Reject duplicate trials or incomplete recordings before choosing gates."""
    expected = list(range(1, 21))
    if sorted(r['trial'] for r in results) != expected or sorted(r['trial'] for r in classifications) != expected:
        raise ValueError('Expected exactly one result and classification for each trial 1–20')
    window = protocol['observation_window_sim_s']
    if not window or not math.isfinite(window) or window <= 0:
        raise ValueError('A positive finite observation window is required')
    positions = protocol['positions']
    for row in results:
        position = positions[(row['trial'] - 1) % len(positions)]
        if [row['requested_ball_x'], row['requested_ball_y']] != position:
            raise ValueError('Wrong starting position for trial '+str(row['trial']))
        if row.get('reason') != 'fixed_sim_window_complete' or not math.isclose(
                row['observation_end_sim_time'] - row['start_sim_time'], window, abs_tol=1e-6):
            raise ValueError('Incomplete observation for trial '+str(row['trial']))
    for row in classifications:
        if row['observed_play_duration_s'] < window - 0.5:
            raise ValueError('Raw recording does not cover the window for trial '+str(row['trial']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous-enhanced',type=Path,required=True)
    parser.add_argument('--previous-upstream',type=Path,required=True)
    parser.add_argument('--new-enhanced',type=Path,required=True)
    parser.add_argument('--new-upstream',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    labels=['Previous ours','Previous upstream','Ours + visual off','Upstream + visual off']
    loaded=[load_metrics(f) for f in [args.previous_enhanced,args.previous_upstream,
                                     args.new_enhanced,args.new_upstream]]
    for metrics,rows,protocol in loaded:
        if metrics['trials']!=20 or len(rows)!=20:
            raise ValueError('Decision requires all 20 trials per profile')
    for key in ['positions','repeats','observation_window_sim_s','post_shot_stop',
                'start_protocol','test_referee_options','defender','target_goal']:
        if loaded[2][2][key]!=loaded[3][2][key]:
            raise ValueError('New observation protocols differ: '+key)
    window=loaded[2][2]['observation_window_sim_s']
    for folder, entry in zip([args.new_enhanced, args.new_upstream], loaded[2:]):
        validate_completed_windows(entry[1], json.loads((folder/'classification.json').read_text()), entry[2])
    if not window or not all(r.get('observation_window_sim_s')==window
                             for entry in loaded[2:] for r in entry[1]):
        raise ValueError('New profiles need the same fixed window in every trial')
    if any(entry[0]['visual_started_trials'] for entry in loaded[2:]):
        raise ValueError('Visual kick started in a supposedly visual-off profile')
    ours,upstream=loaded[2][0],loaded[3][0]
    keep=(ours['goals'],ours['Kick_contact_trials']) >= (upstream['goals'],upstream['Kick_contact_trials'])
    result={'profiles':dict(zip(labels,[x[0] for x in loaded])),
            'equal_new_window_sim_s':window,
            'decision_rule':'Goals first; active Kick contact trials break goal ties; an exact tie keeps gates.',
            'decision':'keep our gates' if keep else 'revert our gates; retain visual kick off',
            'old_runs_note':'Historical profiles used unequal action-dependent windows; only the new pair drives the decision.'}
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    table='| Metric | '+' | '.join(labels)+' |\n|---|---:|---:|---:|---:|\n'
    for label,key in [('Goals','goals'),('Any contact','any_contact_trials'),
                      ('Contact during Kick','Kick_contact_trials'),('Contact during visual kick','visual_contact_trials'),
                      ('Kick started','Kick_started_trials'),('Visual kick started','visual_started_trials')]:
        table+='| '+label+' | '+' | '.join(str(x[0][key]) for x in loaded)+' |\n'
    for category in CATEGORIES:
        table+='| '+category+' | '+' | '.join(str(x[0]['failure_categories'][category]) for x in loaded)+' |\n'
    (args.output/'comparison-table.md').write_text(table)
    print(json.dumps(result))


if __name__=='__main__':
    main()
