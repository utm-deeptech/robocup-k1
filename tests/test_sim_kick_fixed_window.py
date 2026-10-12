"""An early walking contact must not shorten either profile's observation."""
import contextlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from sim_kick_baseline import fixed_window_trial


class RecorderStub:
    def __init__(self):
        self.world=self.frame(10)
        self.frames=[]
        self.starts=[]
        self.worker=type('Worker',(),{'poll':lambda _:None})()
        self.stopped=False

    def frame(self,t):
        return {'time':t,'wall_time':100+t,'kind':'world',
                'world':{'ballPosition':[0,0,.11],
                         'ballContacts':[{'name':'robot1'}] if t==11 else [],
                         'robots':[{'name':'robot1','position':[.3,0,0],'yaw':0}]},
                'state':{'decision':{'value':'striker-kick','wall_time':100+t}}}

    @property
    @contextlib.contextmanager
    def lock(self):
        self.world=self.frame(self.world['time']+1)
        self.frames.append(self.world)
        yield

    def open_trial(self,path):
        pass

    def command(self,*args,**kwargs):
        pass

    def wait(self,predicate,*args):
        assert predicate()

    def buttons(self,**kwargs):
        self.stopped=True


class FixedWindowTest(unittest.TestCase):
    def test_contact_at_one_second_still_observes_all_three(self):
        rec=RecorderStub()
        with tempfile.TemporaryDirectory() as folder:
            previous=os.getcwd()
            try:
                os.chdir(folder)
                p=Path('.cache/kick-test-referee');p.mkdir(parents=True)
                (p/'events.jsonl').write_text('')
                Path('brain.log').write_text('')
                with patch('sim_kick_baseline.initialize'),patch('sim_kick_baseline.http',return_value={}), \
                     patch('sim_kick_baseline.stop_motion'),patch('sim_kick_baseline.time.time',return_value=100), \
                     patch('sim_kick_baseline.time.sleep'):
                    row=fixed_window_trial(rec,None,None,Path('.'),1,1,(0,0),3)
            finally:
                os.chdir(previous)
        self.assertTrue(row['contact_observed'])
        self.assertTrue(row['contact_during_Kick_decision'])
        self.assertEqual(row['contact_sim_time'],11)
        self.assertEqual(row['observation_end_sim_time'],13)
        self.assertEqual(rec.world['time'],13)


if __name__=='__main__':
    unittest.main()
