"""Public-safe synthetic regressions for dialogue scope and implementation planning."""
import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'skills'/'gap-delivery'/'scripts'
sys.path.insert(0,str(SCRIPTS))
from generate_delivery import _validate_quality, _final_approval_issues, _stage_coverage_issues
from render_report import render


def fixture():
    refs=[{'file':'process.yaml','field':'nodes[id=demo]','note':'Synthetic process node','evidence_kind':'documented'}]
    dims=('process','technology','data','people','organization','rules','control','measurement')
    return {'analysis_id':'example','analysis_version':'1','status':'analysis_complete','source_manifest':[],
      'workflow':{'prepared_by':'gap-delivery/scripts/gap_workflow.py@3','source_pack_sha256':'a','source_index_sha256':'b'},
      'input_validation':{'status':'pass','issues':[]},'questions':[],
      'scope_summary':{k:f'Synthetic scope for {k}' for k in ('included','excluded','later','external','temporary')},
      'analysis_dimensions':{k:{'status':'確認済み','summary':f'Synthetic findings for {k} dimension', 'source_refs':copy.deepcopy(refs),'gap_ids':[],'question_ids':[]} for k in dims},
      'gaps':[{'id':f'GAP-{i:03d}','title':f'Illustrative item {i}','priority':'high','priority_reason':f'Synthetic risk for example area {i}',
        'source_refs':copy.deepcopy(refs),'action_ids':[f'ACT-{i:03d}'],'question_ids':[],
        'decision_context':{**{field:f'Synthetic {field} details for item {i}' for field in ('impact','root_cause','preserve','target_outcome','response_strategy','scope','success_measure','priority_assessment','tradeoff')},'source_refs':copy.deepcopy(refs)}} for i in range(1,4)],
      'actions':[{'id':f'ACT-{i:03d}','title':f'Synthetic requirement {i}','priority':'high','priority_reason':f'Synthetic priority for item {i}',
        'owner_candidate':'Example owner','source_refs':copy.deepcopy(refs),'gap_ids':[f'GAP-{i:03d}'], 'deliverables':[f'Reviewed output {i}'],'question_ids':[], 'depends_on':[],'dependency_relations':[]} for i in range(1,4)],
      'mappings':[{'id':'MAP-001','change_type':'maintained','semantic_delta':'Example retained node','source_refs':copy.deepcopy(refs),'as_is_ids':['demo'],'to_be_ids':['demo']}],
      'next_actions':[{'id':'NA-001','title':'Example follow-up','first_step':'Ask assigned role','expected_result':'Clarified scope','priority':'high','consult_with':'Example owner','status':'confirmed','source':'Specific follow-up agreed','related_action_ids':['ACT-001'],'question_ids':[]}],
      'roadmap':[{'title':'Example phase','action_ids':['ACT-001','ACT-002','ACT-003']}],
      'execution_sequence':[{'action_ids':['ACT-001','ACT-002','ACT-003']}],
      'verification':{'performed':['Checked synthetic data'],'not_performed':[]},
      'dialogue':{'status':'completed','agreed_scope':'Illustrative overall scope','confirmation_source':'User expressly agreed to entire scope',
        'final_confirmation':{'scope':'overall_gap_analysis','prompt':'今回のGap分析の整理内容全体を了承しますか？','response':'はい、全体を了承します'}}}


class ScopeAndTraceabilityTests(unittest.TestCase):
    def issues(self, model):
        return _validate_quality(model,'final')['issues']

    def test_specific_role_ok_is_not_overall_approval(self):
        d=fixture()
        d['dialogue']['final_confirmation']={'scope':'individual_decision','prompt':'取りまとめ役の候補を承認しますか？','response':'OK'}
        self.assertTrue(any('final_confirmation.scope' in i for i in self.issues(d)))
        d['dialogue']['final_confirmation']['scope']='overall_gap_analysis'
        self.assertTrue(any('final_confirmation.prompt' in i for i in self.issues(d)))

    def test_overall_scope_approval_passes(self):
        d=fixture()
        self.assertEqual(self.issues(d),[])
        self.assertEqual(_final_approval_issues(d['dialogue']),[])

    def test_missing_approval_exchange_is_rejected(self):
        d=fixture()
        del d['dialogue']['final_confirmation']
        self.assertTrue(any('final_confirmation' in i for i in self.issues(d)))

    def test_one_na_must_not_link_all_open_questions(self):
        d=fixture()
        refs=d['gaps'][0]['source_refs']
        d['questions']=[{'id':f'Q-{i:03}','question':f'Example question {i}','status':'open',
                         'impact':'Follow-up will be needed','source_refs':copy.deepcopy(refs),'gap_ids':[]} for i in range(1,17)]
        d['next_actions'][0]['question_ids']=[q['id'] for q in d['questions']]
        self.assertTrue(any('Next Action links almost all open questions' in i for i in self.issues(d)))
        d['next_actions'][0]['question_ids']=[q['id'] for q in d['questions'][:3]]
        self.assertEqual(self.issues(d),[])

    def test_technical_implementation_cannot_be_omitted_before_acceptance(self):
        d=fixture()
        d['actions'][0]['title']='会計連携の項目仕様を設計'
        d['actions'][1]['title']='エビデンス保管の連携条件を設計'
        d['actions'][2]['title']='会計連携・保管の結合受入試験を実施'
        self.assertEqual(len(_stage_coverage_issues(d['actions'])),2)
        self.assertTrue(any('implementation' in i for i in self.issues(d)))
        d['actions'][0]['title']='会計連携の設計と実装を分け、会計連携を実装'
        d['actions'][1]['title']='エビデンス保管の設計と実装を分け、エビデンス保管を実装'
        self.assertEqual(_stage_coverage_issues(d['actions']),[])

    def test_unsupported_dependency_is_rejected(self):
        d=fixture()
        d['actions'][1]['dependency_relations']=[{'predecessor_id':'ACT-001','type':'required','gate':'execute','status':'proposed',
              'condition':'ACT-001の具体的成果物が利用可能であること', 'reason':'The specific field dictionary is needed for sign-off',
              'source':'原本の前提条件と分析上の段階分割', 'can_proceed':'Draft is possible', 'if_deferred':'Sign-off is blocked'}]
        s='\n'.join(self.issues(d))
        self.assertIn('generic required condition',s)
        self.assertIn('dependency source must cite',s)

    def test_planned_verification_does_not_count_as_performed(self):
        d=fixture();d['verification']['performed']=['ACT依存の循環・未知ID検証をfinal workflowで実施予定']
        self.assertTrue(any('verification.performed' in i for i in self.issues(d)))

    def test_agreement_provenance_is_rendered(self):
        html=render(fixture())
        self.assertIn('最終整理への了承を求めた質問',html)
        self.assertIn('今回のGap分析',html)

if __name__=='__main__':unittest.main(verbosity=2)
