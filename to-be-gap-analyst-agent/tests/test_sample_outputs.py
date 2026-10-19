"""Regression for curated public Gap Analyst example and Markdown output."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = AGENT_ROOT / 'gap-delivery' / 'scripts'
SAMPLES = AGENT_ROOT / 'sample-outputs'
sys.path.insert(0, str(SCRIPTS))
from generate_delivery import _validate_quality, _write_markdown_report, _verify_outputs
from render_report import render

class SampleOutputsRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((SAMPLES/'gap-analysis.json').read_text(encoding='utf-8'))

    def test_current_quality_contract(self):
        q=_validate_quality(self.data,'final')
        self.assertEqual(q['issues'],[],q['issues'])
        self.assertEqual(len(self.data['questions']),49)
        self.assertEqual(len(self.data['actions']),17)
        self.assertEqual(self.data['dialogue']['final_confirmation']['scope'],'overall_gap_analysis')

    def test_markdown_with_many_questions(self):
        with tempfile.TemporaryDirectory() as t:
            target=Path(t)/'gap-report.md'
            _write_markdown_report(self.data,target)
            s=target.read_text(encoding='utf-8')
            self.assertIn('Q-049',s)
            self.assertIn('NA-001',s)

    def test_checked_derived_outputs(self):
        html=(SAMPLES/'gap-report.html').read_text(encoding='utf-8')
        self.assertEqual(render(self.data),html)
        r=_verify_outputs(self.data,{
            'csv':SAMPLES/'gap-register.csv',
            'markdown':SAMPLES/'gap-report.md',
            'roadmap':SAMPLES/'implementation-roadmap.md',
        },html)
        self.assertEqual(r['issues'],[],r['issues'])

    def test_verification_disclosure(self):
        v=json.loads((SAMPLES/'sample-quality-check.json').read_text(encoding='utf-8'))
        self.assertFalse(v['final_workflow_rerun'])
        self.assertFalse(v['formal_verified'])
        self.assertTrue(v['analysis_manually_adjusted_for_demo'])

if __name__=='__main__':
    unittest.main()
