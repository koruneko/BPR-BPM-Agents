import importlib.util,sys,tempfile,json,argparse,subprocess,unittest
from pathlib import Path
S=Path(__file__).resolve().parents[1]/'gap-delivery/scripts'
sys.path.insert(0,str(S))
import inspect_sources as ins
import gap_workflow as flow
import generate_delivery as gen

class ReviewRegressions(unittest.TestCase):
 def source(self,decision='approved',applied=True,conditional=False):
  src={
   'process.yaml': '''process:\n  id: x\nparticipants:\n- id: p1\nnodes:\n- id: n1\nedges:\n- id: e1\n''',
   'to-be-process.yaml': '''process:\n  id: y\n  bpr:\n    applied_improvements:\n'''+('    - IMP-001\n' if applied else '      []\n')+'''    conditional_improvements:\n'''+('    - IMP-001\n' if conditional else '      []\n')+'''    change_log:\n'''+('    - improvement_id: IMP-001\n      action: applied\n      condition: reviewed\n' if applied or conditional else '      []\n')+'''participants:\n- id: p1\nnodes:\n- id: n1\nedges:\n- id: e1\n''',
   'improvement-analysis.yaml':'improvements:\n- id: IMP-001\n  unresolved_questions: []\n',
   'improvement-decisions.yaml':'decisions:\n- improvement_id: IMP-001\n  decision: '+decision+'\n',
  }
  return src
 def analysis(self):
  return {'source_manifest': [{'file':'process.yaml','artifact_role':'as_is_process'},{'file':'to-be-process.yaml','artifact_role':'to_be_process'},{'file':'improvement-analysis.yaml','artifact_role':'improvement_analysis'},{'file':'improvement-decisions.yaml','artifact_role':'improvement_decisions'}],
    'questions':[],'coverage':{'source_question_lineage':[],'improvement_lineage':[{'improvement_id':'IMP-001','status':'applied','gap_ids':['GAP-1'],'action_ids':[]}]},
    'mappings':[{'type':type,'as_is_ids':[val],'to_be_ids':[val]} for type,val in [('participant','p1'),('node','n1'),('edge','e1')]]}
 def test_duplicate_pack_rejected_both_copies(self):
  text='## FILE: process.yaml\nBEGIN FILE\none\nEND FILE\n\n## FILE: process.yaml\nBEGIN FILE\ntwo\nEND FILE\n'
  with self.assertRaisesRegex(ValueError,'Duplicate ## FILE'): ins.pack_files(text)
  p=Path(__file__).resolve().parents[1]/'bpr-gap-analysis/scripts/inspect_sources.py'
  spec=importlib.util.spec_from_file_location('independent_inspection',p)
  m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with self.assertRaisesRegex(ValueError,'Duplicate ## FILE'): m.pack_files(text)
 def test_decisions_consistent(self):
  src=self.source(); ix=ins.inspect(src)
  self.assertEqual(ins.validate(ix,self.analysis())['status'],'pass')
 def test_rejected_decision_blocks_formal(self):
  src=self.source(decision='rejected')
  v=ins.validate(ins.inspect(src),self.analysis())
  self.assertEqual(v['status'],'fail');self.assertTrue(any('non-approved decision' in s for s in v['issues']))
 def test_missing_decision_blocks_formal(self):
  src=self.source();src['improvement-decisions.yaml']='decisions:\n- improvement_id: IMP-002\n  decision: approved\n'
  v=ins.validate(ins.inspect(src),self.analysis())
  self.assertEqual(v['status'],'fail');self.assertTrue(any('Decision records' in s for s in v['issues']))
 def test_conditional_approval_matches_real_bpr_shape(self):
  src=self.source(decision='conditional_approved')
  src['improvement-decisions.yaml']+='  note: Subject to accounting signoff\n'
  src['to-be-process.yaml']=src['to-be-process.yaml'].replace(
      '    conditional_improvements:\n      []',
      '    conditional_improvements:\n    - improvement_id: IMP-001\n      condition: Subject to accounting signoff')
  v=ins.validate(ins.inspect(src),self.analysis())
  self.assertEqual(v['status'],'pass',v['issues'])
 def test_standard_library_fallback_for_decisions(self):
  from unittest.mock import patch
  src=self.source(decision='conditional_approved')
  src['improvement-decisions.yaml']+='  note: Subject to accounting signoff\n'
  src['to-be-process.yaml']=src['to-be-process.yaml'].replace(
      '    conditional_improvements:\n      []',
      '    conditional_improvements:\n    - improvement_id: IMP-001\n      condition: Subject to accounting signoff')
  with patch.dict(sys.modules,{'yaml':None}):
   v=ins.validate(ins.inspect(src),self.analysis())
  self.assertEqual(v['status'],'pass',v['issues'])
 def test_validation_fail_not_formal(self):
  d={'input_validation':{'status':'fail','issues':[]},'workflow':{'prepared_by':flow.WORKFLOW_ID,'source_pack_sha256':'x','source_index_sha256':'x'},'gaps':[],'actions':[],'questions':[],'next_actions':[]}
  r=gen._validate_quality(d,'final')
  self.assertEqual(r['status'],'fail');self.assertTrue(any('input_validation.status=pass' in s for s in r['issues']))
 def test_generator_direct_final_not_allowed(self):
  r=subprocess.run([sys.executable,str(S/'generate_delivery.py'),'--analysis','x','--output-dir','y','--mode','final'],capture_output=True,text=True)
  self.assertNotEqual(r.returncode,0);self.assertIn('Direct final generation is unsupported',r.stderr)
 def test_custom_zip_removed_on_failed_final(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t); (d/'analysis.json').write_text('{}'); (d/'old.zip').write_bytes(b'previous-good-zip')
   args=argparse.Namespace(mode='final',analysis=str(d/'analysis.json'),output_dir=str(d/'output'),pack=None,title=None,report_view='full',zip_path=str(d/'old.zip'))
   with self.assertRaises(ValueError):gen.generate(args)
   self.assertFalse((d/'old.zip').exists())
 def test_workflow_preparation_binding(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t); sources=self.source()
   paths=[]
   for name,content in sources.items():
    f=p/name;f.write_text(content);paths.append(str(f))
   dest=p/'prepared'
   args=argparse.Namespace(pack=None,source=paths,output_dir=str(dest),analysis_id='a',analysis_version='1',process_name='test',allow_missing_core=False)
   self.assertEqual(flow.cmd_prepare(args),0)
   a=json.loads((dest/'gap-analysis.template.json').read_text())
   analysis=p/'analysis.json'; analysis.write_text(json.dumps(a))
   final=argparse.Namespace(pack=str(dest/'source-pack.txt'),preparation=str(dest/'workflow-preparation.json'),analysis=str(analysis),output_dir=str(p/'output'),zip_path=str(p/'old.zip'))
   flow.verify_preparation(final)
   a['source_manifest'][0]['artifact_role']='improvement_decisions'
   analysis.write_text(json.dumps(a))
   with self.assertRaisesRegex(ValueError,'source_manifest'):flow.verify_preparation(final)
   # Even before calling the generator, a failed final attempt invalidates the old ZIP.
   (p/'old.zip').write_bytes(b'stale')
   with self.assertRaises(ValueError):flow.run_delivery(final,'final')
   self.assertFalse((p/'old.zip').exists())

if __name__=='__main__': unittest.main()
