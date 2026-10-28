"""Isolated pipeline tests: no browsers, Docker, devices or external packages."""
import ast
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import types
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pipeline_utils', ROOT / 'modules/state_machine_utils.py')
utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utils)


def load_isolated(path):
    """Use real loader/constants code with only business imports stubbed."""
    tree = ast.parse(path.read_text())
    namespace = {'__name__': 'isolated'}
    body = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module.startswith('modules.'):
            for alias in node.names:
                name = alias.asname or alias.name
                namespace[name] = getattr(utils, alias.name, Mock(name=alias.name))
        else:
            body.append(node)
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


def step(fn=lambda: None, key='value', phase='exec', args=None, when=None):
    return dict(fn=fn, result=key, phase=phase, args=args or [], when=when)


class PipelineContract(unittest.TestCase):
    def run_steps(self, pipeline, ctx=None, phase='exec'):
        ctx = {} if ctx is None else ctx
        with contextlib.redirect_stdout(io.StringIO()):
            ok = utils.run_pipeline_steps('group', {}, pipeline, phase=phase, label='test', ctx=ctx)
        return ok, ctx

    def test_actual_returns_are_separate_from_status(self):
        for value in (None, False, [], {}, 0, '', object()):
            with self.subTest(value=value):
                ok, ctx = self.run_steps([step(lambda: value)])
                self.assertTrue(ok)
                self.assertIs(ctx['value'], value)
                self.assertEqual(ctx['steps'][0]['status'], 'success')
                self.assertTrue(utils.result_available(ctx, 'value'))
                self.assertNotIn('result', ctx['steps'][0])

    def test_failure_dependency_independence_and_cleanup(self):
        def fail():
            raise ValueError('broken')
        dependent = Mock()
        cleanup = Mock(return_value=None)
        ok, ctx = self.run_steps([
            step(fail, 'source'),
            step(dependent, 'dependent', when=lambda j, m, c: utils.result_available(c, 'source')),
            step(lambda: False, 'independent'), step(cleanup, 'cleanup'),
        ])
        self.assertFalse(ok)
        self.assertEqual([s['status'] for s in ctx['steps']], ['failed', 'skipped', 'success', 'success'])
        self.assertEqual(ctx['steps'][0]['error'], 'broken')
        self.assertEqual(ctx['steps'][0]['error_type'], 'ValueError')
        self.assertIn('reason', ctx['steps'][1])
        dependent.assert_not_called()
        cleanup.assert_called_once()

    def test_failed_retry_preserves_value_but_invalidates_dependency(self):
        callback = Mock(side_effect=[{'large': 'value'}, RuntimeError('retry')])
        ok, ctx = self.run_steps([step(callback), step(callback),
            step(key='consumer', when=lambda j, m, c: utils.result_available(c, 'value'))])
        self.assertFalse(ok)
        self.assertEqual(ctx['value'], {'large': 'value'})
        self.assertEqual(ctx['steps'][-1]['status'], 'skipped')
        self.assertEqual(callback.call_count, 2)

    def test_pending_and_running_are_observable(self):
        ctx = {}
        def inspect():
            self.assertEqual([s['status'] for s in ctx['steps']], ['running', 'pending'])
        self.run_steps([step(inspect), step(key='next')], ctx)

    def test_argument_and_condition_exceptions_are_recorded(self):
        def fail(*args):
            raise FileNotFoundError(2, 'missing', '/test/file')
        for pipeline in ([step(args=[fail])], [step(when=fail)]):
            ok, ctx = self.run_steps(pipeline)
            self.assertFalse(ok)
            self.assertEqual(ctx['steps'][0]['error_type'], 'FileNotFoundError')
            self.assertIn('/test/file', ctx['steps'][0]['error'])

    def test_phase_handling_and_fresh_runs(self):
        pipeline = [step(lambda: [], 'source', 'pre'),
                    step(lambda value: value, args=[lambda j, m, c: c['source']])]
        for _ in range(2):
            ctx = {}
            self.assertTrue(self.run_steps(pipeline, ctx, 'pre')[0])
            self.assertEqual(len(ctx['steps']), 1)
            self.assertTrue(self.run_steps(pipeline, ctx)[0])
            self.assertEqual(len(ctx['steps']), 2)
            self.assertEqual(ctx['value'], [])

    def test_pre_continues_independent_steps(self):
        failed = Mock(side_effect=RuntimeError('pre'))
        ok, ctx = self.run_steps([step(failed, phase='pre'), step(key='other', phase='pre')], phase='pre')
        self.assertFalse(ok)
        self.assertEqual([s['status'] for s in ctx['steps']], ['failed', 'success'])

    def test_contract_rejects_legacy_definitions(self):
        with self.assertRaises(ValueError):
            self.run_steps([{'fn': lambda: None}])
        ok, ctx = self.run_steps([dict(fn=lambda: None, args=[], phase='exec')])
        self.assertFalse(ok)
        self.assertEqual(ctx['steps'][0]['error_type'], 'KeyError')

    def test_loader_pre_failure_blocks_confirmation_and_new_selection_resets_state(self):
        path = ROOT / ('ToolLoader.py' if (ROOT / 'ToolLoader.py').exists() else 'AutomationLoader.py')
        loader = load_isolated(path)
        machine = loader['StateMachine'](types.SimpleNamespace())
        machine.current_action_key = 'Run'
        machine.actions = {'Run': {'execute_state': 'RUN'}}
        machine._pending_pipeline_spec = {'pipeline': [step(Mock(side_effect=RuntimeError('pre')), phase='pre')]}
        machine.cfg_groups = {'group': {}}
        machine.selected_groups = ['group']
        machine.runtime_ctx = {'groups': {'group': {}}} if path.name == 'AutomationLoader.py' else {}
        with contextlib.redirect_stdout(io.StringIO()):
            machine.run_pipeline_pre()
        self.assertEqual(machine.state, loader['State'].MENU_SELECTION)
        machine.c = types.SimpleNamespace(PIPELINE_STATES={'RUN': {'pipeline': [step()]}})
        machine.cli_action = 'Run'
        with contextlib.redirect_stdout(io.StringIO()):
            machine.select_action()
        self.assertEqual(machine.runtime_ctx, {'groups': {}} if path.name == 'AutomationLoader.py' else {})

    def test_every_configured_pipeline_uses_contract_and_runs_both_phases(self):
        count = 0
        for path in sorted((ROOT / 'constants').glob('*Constants.py')):
            constants = load_isolated(path)
            for name, config in constants['PIPELINE_STATES'].items():
                with self.subTest(module=path.name, pipeline=name):
                    self.assertNotIn('success_key', config)
                    pipeline = config['pipeline']
                    for definition in pipeline:
                        self.assertTrue({'fn', 'phase', 'args', 'result'} <= definition.keys())
                        self.assertTrue(callable(definition['fn']))
                        self.assertIn(definition['phase'], ('pre', 'exec'))
                        self.assertIsInstance(definition['args'], list)
                        self.assertIsInstance(definition['result'], str)
                    # Execute the real flattened configuration safely with business calls
                    # disabled through the public condition mechanism.
                    ctx = {}
                    guarded = [dict(s, when=False) for s in pipeline]
                    self.run_steps(guarded, ctx, 'pre')
                    self.run_steps(guarded, ctx, 'exec')
                    self.assertEqual(len(ctx['steps']), len(pipeline))
                    self.assertTrue(all(s['status'] == 'skipped' for s in ctx['steps']))
                    count += 1
        self.assertGreater(count, 10)

    def test_configured_iso_and_text_pipelines_with_real_argument_resolution(self):
        if ROOT.name != 'AutomationTools':
            self.skipTest('AutomationTools pipelines')
        for module, config, failed_key, skipped_key, outputs in [
            ('UbuntuISOEditorConstants', 'UbuntuISOEditor.json', 'iso_valid', 'iso_created', {}),
            ('TextCreatorConstants', 'TextCreator.json', 'started_ollama_ok', 'text_summary',
             {'sources': ['page.html'], 'items': [{'title': 'test'}], 'saved_prompts_count': 1}),
        ]:
            constants = load_isolated(ROOT / 'constants' / (module + '.py'))
            metadata = next(iter(json.loads((ROOT / 'config' / config).read_text()).values()))
            original = constants['PIPELINE_STATES']['RUN_ALL']['pipeline']
            for fail in (False, True):
                pipeline = []
                for definition in original:
                    callback = Mock(return_value=outputs.get(definition['result'], True))
                    if fail and definition['result'] == failed_key:
                        callback.side_effect = RuntimeError('configured failure')
                    pipeline.append(dict(definition, fn=callback))
                ctx = {}
                with contextlib.redirect_stdout(io.StringIO()):
                    ok = utils.run_pipeline_steps('group', metadata, pipeline,
                                                  phase='exec', label='configured', ctx=ctx)
                self.assertEqual(ok, not fail)
                target = next(s for s in ctx['steps'] if s['result_key'] == skipped_key)
                self.assertEqual(target['status'], 'skipped' if fail else 'success')
                if module == 'TextCreatorConstants':
                    self.assertEqual(ctx['steps'][-1]['status'], 'success')

    def test_configured_run_all_dependency_gates(self):
        for filename, result, prerequisite in [
            ('UbuntuISOEditorConstants.py', 'iso_created', 'iso_valid'),
            ('TextCreatorConstants.py', 'text_summary', 'started_ollama_ok'),
            ('RouterConstants.py', 'edited_directory', 'decoded_data'),
        ]:
            path = ROOT / 'constants' / filename
            if not path.exists() or ROOT.name == 'TestingTools':
                continue
            pipeline = load_isolated(path)['PIPELINE_STATES']['RUN_ALL']['pipeline']
            target = next(s for s in pipeline if s['result'] == result)
            ctx = {'steps': [{'result_key': prerequisite, 'status': 'failed'}],
                   'model_specs': {}, 'yaml_valid': True, 'paths_valid': True,
                   'iso_valid': True, 'saved_prompts_count': 1, 'started_ollama_ok': True}
            self.assertFalse(target['when']('group', {}, ctx))


if __name__ == '__main__':
    unittest.main()
