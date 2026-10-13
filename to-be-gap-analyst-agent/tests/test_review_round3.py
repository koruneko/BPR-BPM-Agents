import argparse, importlib, json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SKILLS=ROOT/'skills' if (ROOT/'skills').exists() else ROOT
SRC=SKILLS/'gap-delivery/scripts'
sys.path.insert(0,str(SRC))
import inspect_sources as inspect
import gap_workflow as flow
import generate_delivery as gen
from render_report import render

class PR4Round3(unittest.TestCase):
    def test_metadata_fallback_standard_bpr_shape(self):
        text='''schema_version: '1.0'
process:
  id: reimbursement_to_be
  version: '2.0'
participants:
- id: p1
nodes:
- id: n1
edges:
- id: e1
metadata:
  open_questions: []
  bpr:
    source_process:
      id: reimbursement_as_is
    applied_improvements:
    - IMP-001
    conditional_improvements: []
    change_log:
    - improvement_id: IMP-001
      action: applied
      condition: null
'''
        with patch.dict(sys.modules,{'yaml':None}):
            parsed=inspect.parse_to_be_scope(text)
        self.assertEqual(parsed['applied'],['IMP-001'])
        self.assertEqual(parsed['change_log']['IMP-001']['action'],'applied')
        twin_path=SKILLS/'bpr-gap-analysis/scripts/inspect_sources.py'
        self.assertEqual((SRC/'inspect_sources.py').read_bytes(),twin_path.read_bytes())

    def test_bad_evidence_rejected(self):
        base={'file':'process.yaml','field':'nodes[id=n1]','note':'源資料と照合','evidence_kind':'documented'}
        self.assertTrue(gen._valid_source_refs([base]))
        for item in [{**base,'evidence_kind':'invalid'},{**base,'note':''},{**base,'note':None},{**base,'field':'  '}]:
            self.assertFalse(gen._valid_source_refs([item]))

    def args(self,p,zip_location,mode='final'):
        return argparse.Namespace(mode=mode,analysis=str(p/'analysis.json'),output_dir=str(p/'delivery'),pack=str(p/'pack.txt'),preparation=str(p/'prepared.json'),zip_path=str(zip_location),title=None,report_view='full')

    def test_zip_collisions_never_delete_workflow_inputs(self):
        for source in ('analysis.json','pack.txt','prepared.json'):
            with self.subTest(source=source),tempfile.TemporaryDirectory() as folder:
                p=Path(folder)
                for name in ('analysis.json','pack.txt','prepared.json'):(p/name).write_text(f'important-{name}',encoding='utf8')
                args=self.args(p,p/source)
                with self.assertRaisesRegex(ValueError,'overlaps a workflow input'):
                    flow.run_delivery(args,'final')
                for name in ('analysis.json','pack.txt','prepared.json'):
                    self.assertEqual((p/name).read_text(encoding='utf8'),f'important-{name}')
                self.assertFalse((p/'delivery').exists())
                with self.assertRaisesRegex(ValueError,'overlaps a workflow input'):
                    gen.generate(args)

    def test_failed_preflight_invalidates_old_success(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);out=p/'delivery';out.mkdir()
            for name in ('gap-analysis.json','gap-report.html','gap-register.csv','verification-manifest.json','gap-analysis-delivery.zip'):
                (out/name).write_text('previous success')
            (out/'scripts').mkdir();(out/'scripts'/'old.py').write_text('old')
            (p/'custom.zip').write_text('old')
            for name in ('analysis.json','pack.txt','prepared.json'):(p/name).write_text('{}')
            args=self.args(p,p/'custom.zip')
            with self.assertRaises(ValueError):flow.run_delivery(args,'final')
            for name in ('gap-analysis.json','gap-report.html','gap-register.csv','gap-analysis-delivery.zip'):
                self.assertFalse((out/name).exists(),name)
            self.assertFalse((out/'scripts').exists())
            self.assertFalse((p/'custom.zip').exists())
            v=json.loads((out/'verification-manifest.json').read_text())
            self.assertEqual(v['overall_status'],'fail');self.assertFalse(v['formal_verified'])

    def test_generator_draft_collisions_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);src=p/'analysis.json';src.write_text('{}')
            x=argparse.Namespace(mode='draft',analysis=str(src),output_dir=str(p/'out'),pack=None,title=None,report_view='full',zip_path=str(src))
            with self.assertRaisesRegex(ValueError,'overlaps a workflow input'):gen.generate(x)
            self.assertEqual(src.read_text(),'{}')
            self.assertFalse((p/'out').exists())

    def test_report_limitation_is_one_list_item(self):
        data={
            'verification':{'limitations':'To-Beへの反映は設計状態であり、実装・稼働済みではない。'},
            'gaps':[],'actions':[],'questions':[],'next_actions':[],'roadmap':[],
        }
        html=render(data)
        self.assertNotIn('<li>T</li><li>o</li>',html)
        self.assertIn('<li>変更後の業務への反映は設計状態であり',html)
        self.assertEqual(html.count('変更後の業務への反映は設計状態であり'),1)

if __name__=='__main__': unittest.main(verbosity=2)
