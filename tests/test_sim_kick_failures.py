"""Check trial boundaries and action attribution in saved failure analysis."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sim_kick_failures import analyze_trial


class FailureAnalysisTest(unittest.TestCase):
    def analyze(self, frames, profile='enhanced'):
        row = dict(trial=1, start_sim_time=10, ball_start_x=0, ball_start_y=0,
                   result='missed_contact', contact_observed=False)
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base/'trial-01-events.json').write_text(json.dumps([
                {'type':'match_finished', 'simTime':13}]))
            (base/'trial-01-brain.log').write_text('')
            (base/'trial-01.jsonl').write_text('\n'.join(json.dumps(f) for f in frames))
            return analyze_trial(base, row, profile)[0]

    def world(self, t, decision='adjust', contact=False, sample_wall=101):
        return dict(kind='world', time=t, wall_time=101+t,
                    world={'robots':[{'name':'robot1', 'position':[.3,0,0], 'yaw':0}],
                           'ballPosition':[0,0,.11],
                           'ballContacts':[{'name':'robot1'}] if contact else []},
                    state={'decision':{'value':'striker-'+decision, 'wall_time':sample_wall}})

    def test_reset_cache_and_outside_play_contacts_do_not_count(self):
        frames=[{'kind':'command_sent','command':'reset_robot','wall_time':100},
                self.world(9, 'kick', True), self.world(10, 'kick', True, 99),
                self.world(11),self.world(12),self.world(13),self.world(14,'kick',True)]
        result=self.analyze(frames)
        self.assertFalse(result['Kick_node_ever_started'])
        self.assertFalse(result['contact_during_Kick_decision'])
        self.assertEqual(result['unknown_total_s'],1)
        self.assertEqual(result['adjust_total_s'],2)
        self.assertEqual(result['category'],'reached but never aligned (stuck in adjust)')

    def test_legacy_contact_recognized_without_visual_activation(self):
        result=self.analyze([self.world(10),self.world(11,'kick'),
                             self.world(12,'kick',True),self.world(13,'kick')], 'upstream')
        self.assertTrue(result['Kick_node_ever_started'])
        self.assertEqual(result['visual_rpc_start_count'],0)
        self.assertTrue(result['first_action_contact_within_8s'])
        self.assertEqual(result['category'],'kick action produced contact')

    def test_contact_after_visual_stop_is_not_visual_success(self):
        frames=[self.world(10),
                {'kind':'kick_rpc','sim_time':10.5,'body':{'start':True}},
                self.world(11,'auto_visual_kick'),
                {'kind':'kick_rpc','sim_time':11.5,'body':{'start':False}},
                self.world(12,'adjust',True),self.world(13)]
        result=self.analyze(frames)
        self.assertTrue(result['contact_anywhere_in_trial'])
        self.assertFalse(result['contact_while_visual_rpc_active'])
        self.assertFalse(result['first_action_contact_within_8s'])
        self.assertEqual(result['category'],'kick started but no contact')

    def test_fixed_window_excludes_later_cleanup_contacts(self):
        frames=[self.world(10),self.world(11),self.world(12),
                self.world(13),self.world(14,'kick',True)]
        row=dict(trial=1,start_sim_time=10,ball_start_x=0,ball_start_y=0,
                 result='missed_contact',contact_observed=False,
                 observation_window_sim_s=3,observation_end_sim_time=13)
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            (base/'trial-01-events.json').write_text(json.dumps([
                {'type':'match_finished','simTime':15}]))
            (base/'trial-01-brain.log').write_text('')
            (base/'trial-01.jsonl').write_text('\n'.join(json.dumps(f) for f in frames))
            result,_=analyze_trial(base,row,'upstream')
        self.assertEqual(result['observed_play_duration_s'],3)
        self.assertFalse(result['contact_anywhere_in_trial'])
        self.assertFalse(result['Kick_node_ever_started'])


if __name__=='__main__':
    unittest.main()
