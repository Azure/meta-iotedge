"""Offline execution of the workflow's selectors; no builds or GitHub calls."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/ci-build.yml'
ALL = ['scarthgap', 'wrynose', 'scarthgap-1.6']


def expression(source, context):
    # Selector expressions use only context lookups, string literals and ||.
    for term in source.split('||'):
        term = term.strip()
        value = term[1:-1] if term.startswith("'") else context.get(term, '')
        if value:
            return value
    return ''


def render(text, context):
    return re.sub(r'\$\{\{\s*(.*?)\s*\}\}',
                  lambda match: expression(match[1], context), text)


def step_script(step_id):
    text = WORKFLOW.read_text().split(f'        id: {step_id}\n', 1)[1]
    return textwrap.dedent(text.split('        run: |\n', 1)[1]
                           .split('\n      - name:', 1)[0].split('\n  regression-tests:', 1)[0])


class ManualScopeTests(unittest.TestCase):
    def context(self, event='workflow_dispatch', choice='all', ref='main',
                ref_type='branch', checkout='', release='', base=''):
        return {'github.event_name': event, 'inputs.template': choice,
                'github.ref_name': ref, 'github.ref_type': ref_type,
                'github.base_ref': base, 'inputs.ref': checkout,
                'inputs.release_tag': release}

    def execute(self, step_id, context):
        job = WORKFLOW.read_text().split('  check-changes:\n', 1)[1].split('    steps:', 1)[0]
        env = dict(os.environ)
        # Read actual job env declarations; an absent env on the baseline is valid.
        if '    env:\n' in job:
            block = job.split('    env:\n', 1)[1].split('\n    outputs:', 1)[0]
            for name, value in re.findall(r'^      (\w+): (.+)$', block, re.M):
                env[name] = render(value, context)
        with tempfile.TemporaryDirectory(prefix='manual-selector-') as tmp:
            output = Path(tmp) / 'output'
            env['GITHUB_OUTPUT'] = str(output)
            result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c',
                                     render(step_script(step_id), context)],
                                    cwd=tmp, env=env, text=True, capture_output=True)
            values = dict(line.split('=', 1) for line in output.read_text().splitlines()) if output.exists() else {}
        return result, values

    def selection(self, **kwargs):
        context = self.context(**kwargs)
        result, outputs = self.execute('set-template', context)
        self.assertEqual(result.returncode, 0, result.stderr)
        context['steps.set-template.outputs.template'] = outputs['template']
        result, matrix = self.execute('set-matrix', context)
        self.assertEqual(result.returncode, 0, result.stderr)
        return outputs['template'], json.loads(matrix['templates'])

    def test_manual_single_template_matches_output(self):
        for template in ALL:
            with self.subTest(template=template):
                self.assertEqual(self.selection(choice=template), (template, [template]))

    def job_name(self, job_id, context):
        name = WORKFLOW.read_text().split(f'  {job_id}:\n', 1)[1].splitlines()[0].strip()[6:]
        if not name.startswith('${{'):
            return name
        source = name[3:-2].strip()
        source = re.sub(r'\b(?:github|inputs)\.[a-z_]+',
                        lambda match: json.dumps(context.get(match[0], '')), source)
        return subprocess.run(['node', '-p', source], text=True, capture_output=True,
                              check=True).stdout.strip()

    def test_scoped_checks_cannot_satisfy_normal_acceptance(self):
        # Even failed/invalid selections must not emit a normal required check.
        for template in [*ALL, 'invalid']:
            for job_id, normal in [('build', 'Build and validate'), ('status-check', 'Status check')]:
                with self.subTest(template=template, job=job_id):
                    name = self.job_name(job_id, self.context(choice=template))
                    self.assertNotEqual(name, normal)
                    self.assertIn('Diagnostic', name)
                    self.assertIn('not full acceptance', name)

    def test_release_tags_cannot_be_overridden_by_manual_choice(self):
        for ref, template in [('1.5.35', 'scarthgap'), ('1.6.0', 'wrynose'),
                              ('1.6.0-scarthgap', 'scarthgap-1.6'), ('custom-tag', 'scarthgap')]:
            for ref_type in (('tag', 'branch') if ref.startswith('1.') else ('tag',)):
                with self.subTest(ref=ref, ref_type=ref_type):
                    # Scoped diagnostics are branch-only; reject rather than retag.
                    result, values = self.execute('set-template', self.context(
                        choice='wrynose' if template != 'wrynose' else 'scarthgap',
                        ref=ref, ref_type=ref_type))
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn('template', values)

    def test_default_and_nonmanual_events_preserve_full_matrix_and_check_names(self):
        for event in ('pull_request', 'push', 'workflow_call', 'workflow_dispatch'):
            for branch in ('main', 'kirkstone'):
                for choice in (('all', '') if event == 'workflow_dispatch' else ('all', 'wrynose', 'invalid')):
                    with self.subTest(event=event, branch=branch, choice=choice):
                        self.assertEqual(self.selection(event=event, ref=branch, choice=choice),
                                         ('kirkstone' if branch == 'kirkstone' else 'scarthgap', ALL))
                        for job_id, name in [('build', 'Build and validate'), ('status-check', 'Status check')]:
                            self.assertEqual(self.job_name(job_id, self.context(
                                event=event, ref=branch, choice=choice)), name)
        self.assertEqual(self.selection(event='pull_request', ref='feature', base='kirkstone',
                                        choice='wrynose'), ('kirkstone', ALL))

    def test_release_mapping_preserves_tag_identity_and_immutable_checkout(self):
        for release, template in [('1.5.35', 'scarthgap'), ('1.6.0', 'wrynose'),
                                  ('1.6.0-scarthgap', 'scarthgap-1.6'),
                                  ('1.6.0-scarthgap.2', 'scarthgap-1.6')]:
            for context in [dict(event='workflow_dispatch', ref=release, ref_type='tag'),
                            dict(event='workflow_call', checkout=release, choice='scarthgap'),
                            dict(event='workflow_dispatch', checkout='a' * 40, release=release)]:
                with self.subTest(release=release, context=context):
                    self.assertEqual(self.selection(**context), (template, [template]))

    def test_invalid_manual_choices_are_data_not_shell(self):
        for choice in ('kirkstone', 'invalid', 'all\nscarthgap', '$(exit 73)',
                       '"; exit 73; #', "wrynose'; exit 73; #"):
            with self.subTest(choice=choice):
                result, values = self.execute('set-template', self.context(choice=choice))
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('Invalid manual template', result.stderr)
                self.assertNotIn('template', values)
        with tempfile.TemporaryDirectory(prefix='selector-injection-') as tmp:
            sentinel = Path(tmp) / 'must-not-exist'
            for choice in (f'$(touch {sentinel})', f'"; touch {sentinel}; #'):
                result, values = self.execute('set-template', self.context(choice=choice))
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertNotIn('template', values)
                self.assertFalse(sentinel.exists(), 'manual input executed as shell source')
        for step_id in ('set-template', 'set-matrix'):
            self.assertNotIn('inputs.template', step_script(step_id))

    def test_input_contract_and_qemu_default_remain_explicit(self):
        text = WORKFLOW.read_text()
        dispatch = text.split('  workflow_dispatch:\n', 1)[1].split('  workflow_call:', 1)[0]
        self.assertIn('type: choice\n        default: all\n', dispatch)
        choices = re.findall(r'^          - (.+)$', dispatch, re.M)
        self.assertEqual(choices, ['all', *ALL])
        self.assertIn('type: boolean\n        default: false', dispatch)
        self.assertIn('if: ${{ !inputs.skip_qemu }}', text)
        self.assertIn('RELEASE_TAG: ${{ inputs.release_tag', text)


if __name__ == '__main__':
    unittest.main()
