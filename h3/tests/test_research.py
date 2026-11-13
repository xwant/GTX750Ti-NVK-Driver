import copy
import unittest
from h3.dataset import Invalid, canonical
from h3.synthetic import dataset,record
from h3.research import experiment,grouped_split,predict

class ResearchTests(unittest.TestCase):
    def test_reproducible(self):
        a=experiment(dataset());b=experiment(dataset())
        self.assertEqual(canonical(a),canonical(b));self.assertFalse(a['driver_ready'])
        self.assertTrue(a['metrics']['h2_fixed']['harmful_h2']>0)
        self.assertEqual(a['metrics']['base_fallback']['harmful_h2'],0)
    def test_permuted_input(self):
        a=dataset();b=copy.deepcopy(a);b['records'].reverse()
        self.assertEqual(canonical(experiment(a)),canonical(experiment(b)))
    def test_shader_or_scenario_connected_groups(self):
        rows=[record(i) for i in range(20)]
        rows[1]['identity']['scenario_group']=rows[0]['identity']['scenario_group']
        rows[2]['identity']['config']=rows[1]['identity']['config']
        train,test=grouped_split(rows)
        side=lambda r: r in train
        self.assertEqual(side(rows[0]),side(rows[1]));self.assertEqual(side(rows[1]),side(rows[2]))
        self.assertFalse(set(r['identity']['scenario_group'] for r in train)&set(r['identity']['scenario_group'] for r in test))
    def test_insufficient_or_mixed_data(self):
        a=dataset();a['records'][0]['pairs']=a['records'][0]['pairs'][:8]
        with self.assertRaises(Invalid):experiment(a)
        a=dataset();a['records'][0]['origin']='lavapipe';a['records'][0]['identity']['gpu']='lavapipe'
        with self.assertRaises(Invalid):experiment(a)
    def test_evaluation_does_not_train_tree(self):
        a=dataset();b=copy.deepcopy(a)
        for r in b['records']:
            for p in r['pairs'][8:]:p['b']['samples_ns']=[v*2 for v in p['b']['samples_ns']]
        x,y=experiment(a),experiment(b)
        self.assertEqual(x['model'],y['model']);self.assertNotEqual(x['metrics'],y['metrics'])
    def test_missing_feature_fallback(self):
        f=record()['features'];f['draws']=None
        self.assertEqual(predict(dict(feature='draws',threshold=32,left=dict(mode='h2'),right=dict(mode='base')),f),'base')
    def test_same_shader_different_layouts_stay_together(self):
        from h3.dataset import digest
        rows=[record(i) for i in range(20)]
        for i,r in enumerate(rows):
            r['kind']='per_shader'
            r['identity'].update(shader_sha256=digest('shared' if i<2 else str(i)),
                                 layout_sha256=digest('layout'+str(i)),compiler_identity=digest('compiler'))
        train,test=grouped_split(rows)
        self.assertEqual(rows[0] in train,rows[1] in train)
