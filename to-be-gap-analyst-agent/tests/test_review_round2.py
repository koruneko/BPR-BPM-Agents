import argparse, json, sys, tempfile, unittest, zipfile
from pathlib import Path
from unittest.mock import patch

SKILLS = Path(__file__).resolve().parents[1] / 'gap-delivery' / 'scripts'
sys.path.insert(0, str(SKILLS))
import gap_workflow as workflow
import generate_delivery as delivery

class PR4Round2(unittest.TestCase):
    def prepare_fixture(self, root):
        sources={
          'process.yaml': 'process:\n  id: old\nparticipants:\n- id: p1\nnodes:\n- id: n1\nedges:\n- id: e1\n',
          'to-be-process.yaml':'process:\n  id: new\n  bpr:\n    applied_improvements:\n    - IMP-001\n    conditional_improvements: []\n    change_log:\n    - improvement_id: IMP-001\n      action: applied\nparticipants:\n- id: p1\nnodes:\n- id: n1\nedges:\n- id: e1\n',
          'improvement-analysis.yaml':'improvements:\n- id: IMP-001\n  unresolved_questions: []\n',
          'improvement-decisions.yaml':'decisions:\n- improvement_id: IMP-001\n  decision: approved\n',
        }
        paths=[]
        for name,contents in sources.items():
            p=root/name;p.write_text(contents,encoding='utf8');paths.append(str(p))
        out=root/'prepare';out.mkdir()
        args=argparse.Namespace(pack=None,source=paths,output_dir=str(out),analysis_id='x',analysis_version='1.0',process_name='Demo',allow_missing_core=False)
        with patch('builtins.print'):
            self.assertEqual(workflow.cmd_prepare(args),0)
        return json.loads((out/'gap-analysis.template.json').read_text())

    def test_source_zero_questions_is_legitimate(self):
        with tempfile.TemporaryDirectory() as t:
            a=self.prepare_fixture(Path(t))
            self.assertEqual(a['questions'],[])
            self.assertEqual(a['coverage']['source_question_lineage'],[])
            a['input_validation']={'status':'pass','issues':[]}
            quality=delivery._validate_quality(a,'final')
            self.assertFalse(any('non-empty GAP, ACT, Q' in x or 'questions' in x.lower() and 'non-empty' in x for x in quality['issues']),quality['issues'])
            a['questions']=[{'id':'Q-001','status':'open','impact':'想定影響','source_refs':[],'gap_ids':[]}]
            with_q=delivery._validate_quality(a,'final')
            self.assertFalse(any('non-empty GAP, ACT, Q' in x for x in with_q['issues']))

    def test_zip_allowlist_omits_foreign_files_and_stale_ones(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);template=self.prepare_fixture(p)
            analysis=p/'analysis.json';analysis.write_text(json.dumps(template,ensure_ascii=False),encoding='utf8')
            out=p/'output';out.mkdir()
            (out/'credentials.txt').write_text('SECRET')
            (out/'original-source.yaml').write_text('UNEXPECTED SOURCE')
            (out/'old-report.pdf').write_bytes(b'OLD')
            options=argparse.Namespace(mode='draft',analysis=str(analysis),output_dir=str(out),pack=None,title=None,report_view='full',zip_path=str(p/'result.zip'))
            with patch('builtins.print'):
                self.assertEqual(delivery.generate(options),0)
            with zipfile.ZipFile(p/'result.zip') as z:
                names=set(z.namelist())
                self.assertIn('verification-manifest.json', names)
                self.assertIn('gap-report.html', names)
                self.assertIn('gap-analysis.json', names)
                self.assertNotIn('credentials.txt', names)
                self.assertNotIn('original-source.yaml', names)
                self.assertNotIn('old-report.pdf', names)
                m=json.loads(z.read('verification-manifest.json'))
                self.assertEqual(names,set(m['artifacts'])|{'verification-manifest.json'})

# A strictly zero-Q scenario must be able to traverse the *entire* final gate.
def _test_complete_final_without_questions(self):
    with tempfile.TemporaryDirectory() as t:
        root=Path(t)
        data=self.prepare_fixture(root)
        sr={'file':'process.yaml','field':'nodes[id=n1]','note':'Verified directly against input','evidence_kind':'documented'}
        def refs(): return [dict(sr)]
        data.update({'status':'analysis_complete','input_validation':{'status':'pass','issues':[]},
          'scope_summary':{k:f'{k}: Recorded agreed scope and evidence' for k in ('included','excluded','later','external','temporary')},
          'gaps':[{'id':'GAP-001','title':'入力条件の差異','priority':'high','action_ids':['ACT-001'], 'question_ids':[], 'improvement_ids':['IMP-001'], 'source_refs':refs(),
             'decision_context': {k:'Evidence and agreed context for '+k for k in delivery.DECISION_CONTEXT_FIELDS if k!='source_refs'} | {'source_refs':refs()}}],
          'actions':[{'id':'ACT-001','title':'変更内容を整理','priority':'high','owner_candidate':'Business owner','gap_ids':['GAP-001'],'question_ids':[], 'source_refs':refs(), 'depends_on':[],'dependency_relations':[]}],
          'next_actions':[{'id':'NA-001','title':'責任者と確認','kind':'確認','priority':'high','reason':'To-Be検討のため', 'first_step':'担当者と要件を確認','consult_with':'Business owner','owner_status':'unassigned','expected_result':'合意した実行範囲','related_action_ids':['ACT-001'],'question_ids':[], 'depends_on':[],'status':'confirmed','source':'User confirmed the plan'}],
          'roadmap':[{'title':'Phase One','action_ids':['ACT-001']}],
          'execution_sequence':[{'action_ids':['ACT-001']}],
          'dialogue':{'status':'completed','agreed_scope':'Confirm target process scope','summary':'User agreed','deferred_topics':[],'confirmation_source':'User confirmed the plan'},
        })
        for i,k in enumerate(delivery.DIMENSIONS):
            data['analysis_dimensions'][k]={'status':'確認済み','summary':f'Process evidence and assessment specific to {k}, observation {i} supported by the As-Is and To-Be processes.', 'gap_ids':['GAP-001'],'question_ids':[],'source_refs':refs()}
        data['mappings']=[{'id':f'MAP-{i:04d}','type':kind,'as_is_ids':[eid],'to_be_ids':[eid], 'change_type':'maintained','semantic_delta':f'Compared {kind} and confirmed the retained ID','source_refs':refs(),'improvement_ids':[]} for i,(kind,eid) in enumerate([('participant','p1'),('node','n1'),('edge','e1')],1)]
        data['coverage']['improvement_lineage']=[{'improvement_id':'IMP-001','status':'applied','gap_ids':['GAP-001'],'action_ids':['ACT-001']}]
        self.assertEqual(data['questions'],[])
        issues=delivery._validate_quality(data,'final')['issues']
        self.assertEqual(issues,[],issues)
        src=root/'analysis.json';src.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
        prep=root/'prepare'
        (root/'final').mkdir()
        (root/'final'/'private.env').write_text('PRIVATE DATA', encoding='utf8')
        (root/'final'/'old-analysis.json').write_text('STALE DATA', encoding='utf8')
        args=argparse.Namespace(mode='final',analysis=str(src), output_dir=str(root/'final'),pack=str(prep/'source-pack.txt'),preparation=str(prep/'workflow-preparation.json'),zip_path=str(root/'report.zip'),title=None,report_view='full')
        with patch('builtins.print'):
            self.assertEqual(workflow.run_delivery(args,'final'),0)
        with zipfile.ZipFile(root/'report.zip') as z:
            m=json.loads(z.read('verification-manifest.json'))
            self.assertEqual(m['overall_status'],'pass')
            self.assertTrue(m['formal_verified'])
            self.assertEqual(m['quality']['counts']['questions'],0)
            self.assertNotIn('private.env',z.namelist())
            self.assertNotIn('old-analysis.json',z.namelist())
            self.assertEqual(set(z.namelist()),set(m['artifacts']) | {'verification-manifest.json'})
PR4Round2.test_complete_final_without_questions=_test_complete_final_without_questions

if __name__=='__main__': unittest.main(verbosity=2)
