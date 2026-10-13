"""Synthetic contract regressions: no customer or business source files."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills' / 'gap-delivery' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from generate_delivery import _validate_quality, _write_markdown_report, _write_roadmap, _verify_outputs, _write_csv
from render_report import render
from business_calendar import serial_schedule, schedule_diagram


def fixture():
    refs = [{'file': 'process.yaml', 'field': 'nodes[id=task]', 'note': 'Source example node', 'evidence_kind': 'documented'}]
    return {'analysis_id':'demo', 'analysis_version':'1', 'status':'analysis_complete', 'schema_version':'1.0',
        'source_manifest': [], 'mappings':[{'id':'MAP-001','change_type':'maintained','semantic_delta':'The task remains and input rules are retained','source_refs':copy.deepcopy(refs),'as_is_ids':['task'],'to_be_ids':['task']}], 'verification':{},
        'scope_summary': {k:'Outcomes and constraints grounded in this example' for k in ('included','excluded','later','external','temporary')},
        'input_validation': {'status':'pass','issues':[]},
        'workflow':{'prepared_by':'gap-delivery/scripts/gap_workflow.py@3','source_pack_sha256':'abc','source_index_sha256':'def'},
        'analysis_dimensions':{k:{'status':'確認済み', 'summary':f'Observed evidence and constraints for {k}: specific to this dimension.', 'source_refs':copy.deepcopy(refs),'gap_ids':[],'question_ids':[]} for k in ('process','technology','data','people','organization','rules','control','measurement')},
        'gaps':[{'id':f'GAP-{i:03d}','title':f'Change {i}','priority':'high','priority_reason':f'Specific effect {i}: avoid manual work at stage {i} and verify limits', 'source_refs':copy.deepcopy(refs), 'decision_context':{**{k: f'Evidence for {k} in dimension {i}' for k in ('impact','root_cause','preserve','target_outcome','response_strategy','scope','success_measure','priority_assessment','tradeoff')},'source_refs':copy.deepcopy(refs)},'action_ids':[f'ACT-{i:03d}'],'question_ids':[]} for i in (1,2,3)],
        'actions':[{'id':f'ACT-{i:03d}', 'title':f'Prepare requirements {i}', 'priority':'high', 'priority_reason':f'Specific benefit of task {i}: reduce delay for role {i}', 'owner_candidate':'Business user', 'source_refs':copy.deepcopy(refs), 'gap_ids':[f'GAP-{i:03d}'],'deliverables':[f'Verified requirement table {i}'], 'dependency_relations':[], 'depends_on':[], 'question_ids':[]} for i in (1,2,3)],
        'questions':[], 'next_actions':[{'id':'NA-001','title':'Review task','first_step':'Review scope with owner', 'expected_result':'Scoped work','priority':'high','consult_with':'Process owner','status':'confirmed','source':'User response','related_action_ids':['ACT-001'],'question_ids':[]}],
        'roadmap':[{'phase':'1. Preparation','action_ids':['ACT-001','ACT-002','ACT-003'],'start_condition':'初回準備を開始できること','transition_condition':'項目整理を確認したこと'}],
        'execution_sequence':[{'order':1,'name':'Research','action_ids':['ACT-001','ACT-002','ACT-003'],'status':'confirmed','reason':'Owner agreed to work order'}],
        'dialogue':{'status':'completed','agreed_scope':'Assess selected tasks','confirmation_source':'User approved'},
    }


class PlanningQuality(unittest.TestCase):
    def messages(self, x):
        return '\n'.join(_validate_quality(x,'final')['issues'])

    def test_good_synthetic_quality(self):
        self.assertEqual(self.messages(fixture()), '')

    def test_repeated_priority_rationale_rejected(self):
        x=fixture()
        for g in x['gaps']:g['priority_reason']='The same generic business rationale copied to every GAP'
        for a in x['actions']:a['priority_reason']='The same generic business rationale copied to every ACT'
        v=self.messages(x)
        self.assertIn('GAP priority_reason is overly repetitive',v)
        self.assertIn('ACT priority_reason is overly repetitive',v)

    def test_bad_dependency_and_mixed_task_rejected(self):
        x=fixture();x['actions'][1]['title']='Check API specification and implement connection'
        x['actions'][1]['title']='API仕様を確認し連携を実装'
        x['actions'][1]['dependency_relations']=[{'predecessor_id':'ACT-001','type':'required','gate':'start','status':'confirmed',
            'condition':'ACT-001の成果のうち本作業に必要なルール・仕様・設定が確認可能であること',
            'reason':'後続作業の入力または検証対象になるため。', 'source':'To-Beの制御順と実装上の論理関係に基づく分析提案。'}]
        self.assertIn('combines investigation and implementation',self.messages(x))
        self.assertIn('unsupported generic required dependency',self.messages(x))

    def test_legitimate_specific_dependency_passes(self):
        x=fixture()
        x['actions'][1]['dependency_relations']=[{'predecessor_id':'ACT-001','type':'required','gate':'finalize','status':'proposed',
            'condition':'The signed field dictionary from ACT-001 must be available before finalizing the mapping',
            'reason':'Without field types the mapping cannot be approved reliably', 'source':'Analysis of process.yaml nodes[id=task]',
            'can_proceed':'Draft a candidate mapping from available examples', 'if_deferred':'Final signoff cannot occur'}]
        self.assertEqual(self.messages(x),'')

    def test_generic_deliverables_rejected(self):
        x=fixture();x['actions'][0]['deliverables']=['Prepare requirements 1の業務ルール・設定または検証記録']
        self.assertIn('generic/placeholder value',self.messages(x))

    def test_resource_role_does_not_confirm_one_person(self):
        x=fixture();x['schedule']={'tasks':[{'action_id':'ACT-001','status':'confirmed','start':'2026-11-02'}],
          'resource_constraints':{'owner':'Business user','concurrency':1,'resource_mode':'scenario','assumption_source':'One-person hypothetical only','user_confirmed':False}}
        self.assertIn('scenario schedule must not be shown as confirmed',self.messages(x))
        x['schedule']['tasks'][0]['status']='proposed'
        self.assertEqual(self.messages(x),'')
        x['schedule']['resource_constraints']['resource_mode']='confirmed'
        self.assertIn('requires explicit user confirmation',self.messages(x))

    def test_serial_sequence_mismatch_rejected(self):
        x=fixture();x['schedule']={'tasks':[{'action_id':'ACT-002','status':'proposed','start':'2026-11-02'},
         {'action_id':'ACT-001','status':'proposed','start':'2026-11-04'},
         {'action_id':'ACT-003','status':'proposed','start':'2026-11-06'}],
          'resource_constraints':{'owner':'Business user','concurrency':1,'resource_mode':'scenario','assumption_source':'One-person hypothetical only','user_confirmed':False,'sequence_policy':'follow_execution_sequence'}}
        self.assertIn('schedule order disagrees',self.messages(x))

    def test_html_and_markdown_business_fields(self):
        x=fixture()
        with tempfile.TemporaryDirectory() as t:
            t=Path(t)
            html=render(x)
            self.assertIn('初回準備を開始できること',html)
            self.assertIn('項目整理を確認したこと',html)
            self.assertIn('Verified requirement table 1',html)
            (t/'gap-report.html').write_text(html,encoding='utf8')
            _write_csv(x,t/'gap-register.csv')
            _write_markdown_report(x,t/'gap-report.md')
            _write_roadmap(x,t/'implementation-roadmap.md')
            issues=_verify_outputs(x,dict(csv=t/'gap-register.csv',markdown=t/'gap-report.md',roadmap=t/'implementation-roadmap.md'),html)
            self.assertEqual(issues['issues'],[])
            self.assertIn('初回準備を開始できること',(t/'implementation-roadmap.md').read_text())
            self.assertIn('Verified requirement table 1',(t/'gap-report.md').read_text())
            self.assertIn('deliverables',(t/'gap-register.csv').read_text(encoding='utf-8-sig').splitlines()[0])
            bad_html=html.replace('初回準備を開始できること','MISSING VALUE')
            self.assertIn('HTML roadmap is missing',str(_verify_outputs(x,dict(csv=t/'gap-register.csv',markdown=t/'gap-report.md',roadmap=t/'implementation-roadmap.md'),bad_html)['issues']))

    def test_calendar_capacity_confirmation_required(self):
        x=fixture()
        estimate={a['id']:{'duration_business_days':1,'source':'Scenario assumption'} for a in x['actions']}
        plan=serial_schedule(x['actions'],[a['id'] for a in x['actions']],estimate,'2026-11-02','Business user')
        self.assertEqual(plan['resource_constraints']['resource_mode'],'scenario')
        self.assertTrue(all(r['status']=='proposed' for r in plan['tasks']))
        with self.assertRaisesRegex(ValueError,'明示的な了承'):
            serial_schedule(x['actions'],[a['id'] for a in x['actions']],estimate,'2026-11-02','Business user',status='confirmed')

if __name__=='__main__': unittest.main(verbosity=2)
