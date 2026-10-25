import base64
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

from modules import router_utils as router
from modules import router_encryption_utils as encryption

ROOT = Path(__file__).resolve().parents[1]
DATA = Path.home() / 'Documents/AutomationToolsData/routers'


def model_specs():
    return json.loads((ROOT / 'routers/model_specs/Spark_SmartModem_VRV9517-spec.json').read_text())


def tar_bytes(entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        for name, content in entries.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            archive.addfile(entry, io.BytesIO(content))
    return buffer.getvalue()


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.specs = model_specs()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = io.StringIO()
        redirect = contextlib.redirect_stdout(self.output)
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)

    def prepare_job(self):
        specs = self.specs
        contents = ''.join(f'{key}=old-{label}\r\n' for label, key in specs['config_fields'].items() if label != 'file') + '# retained\r\nLOCKED=value\r\n'
        archive = tar_bytes({specs['config_fields']['file']: contents.encode(), 'unchanged': b'keep'})
        encrypted = router.encrypt_router_payload(archive, 'template', specs)
        # The wrapper places a checksum after eight payload lines.
        if len(router.encode_router_payload(encrypted, specs).splitlines()) < 8:
            specs['backup_format']['checksum']['after_payload_lines'] = 1
        backup = router.rebuild_router_wrapper(router.encode_router_payload(encrypted, specs), b'header\n', specs)
        paths = {key: str(self.root / name) for key, name in {
            'template_config_path': 'original.cfg', 'template_router_password_path': 'template.txt',
            'target_router_password_path': 'target.txt', 'router_details_path': 'details.json',
            'decoded_config_archive_path': 'decoded.tar.gz', 'decoded_config_path': 'decoded',
            'edited_config_path': 'edited', 'encoded_config_path': 'encoded.cfg'}.items()}
        paths['model_specs_path'] = str(self.root / 'model.json')
        paths['model_specs_readme_path'] = str(ROOT / 'routers/model_specs/ModelSpecsReadMe.md')
        Path(paths['model_specs_path']).write_text(json.dumps(specs))
        Path(paths['template_config_path']).write_bytes(backup)
        Path(paths['template_router_password_path']).write_text('template\n')
        Path(paths['target_router_password_path']).write_text('target\n')
        Path(paths['router_details_path']).write_text(json.dumps({'wifi_2g_ssid': 'replacement'}))
        return paths, archive, backup

    def test_supported_spec_and_incomplete_spec(self):
        self.assertEqual(router.load_router_model_specs(str(ROOT / 'routers/model_specs/Spark_SmartModem_VRV9517-spec.json')), self.specs)
        vodafone = router.load_router_model_specs(str(ROOT / 'routers/model_specs/Vodafone_UltraHub_DGA0130VDF-spec.json'))
        self.assertEqual(vodafone['key_derivation'], 'device-key')
        with self.assertRaisesRegex(ValueError, 'device key unavailable'):
            router.read_router_credential('export-password.txt', vodafone)

    def test_legacy_encryption_golden_and_roundtrip(self):
        plain = bytes(range(256)) * 4
        for salted in (False, True):
            self.specs['salted'] = salted
            encrypted = router.encrypt_router_payload(plain, 'test-password', self.specs)
            self.assertEqual(router.decrypt_router_payload(encrypted, 'test-password', self.specs), plain)
            if not salted:
                self.assertEqual(hashlib.sha256(encrypted).hexdigest(), 'aa7a511a17e39f5fc4ed3b8b70d0a272f5a8fd0a1ad61f1ca100ec5ebc1cf465')

    def test_wrapper_layout_and_corruption(self):
        encrypted = bytes(range(256)) * 4
        encoded = router.encode_router_payload(encrypted, self.specs)
        with patch.object(router.os, 'urandom', return_value=b'x' * 24):
            backup = router.rebuild_router_wrapper(encoded, b'header\n', self.specs)
        lines = encoded.splitlines(keepends=True)
        checksum = base64.b64encode(b'x' * 24) + hashlib.md5(encoded).hexdigest().encode() + b'\n'
        self.assertEqual(backup, b'header\n' + b''.join(lines[:8]) + checksum + b''.join(lines[8:]) + b'=' * 64 + b'\n')
        self.assertEqual(router.parse_router_wrapper(backup, self.specs)['encrypted'], encrypted)
        for corrupt in (backup.replace(encoded[:10], b'!' + encoded[1:10]), backup[:-1], backup.replace(b'\n', b'\r\n')):
            with self.subTest(corrupt=corrupt[:10]), self.assertRaises(ValueError):
                router.parse_router_wrapper(corrupt, self.specs)

    def test_validation_rejects_unknown_and_incomplete_settings(self):
        for key, value in [('encoding', 'unknown'), ('encryption', 'unknown'), ('configuration_format', 'unknown'), ('key_derivation_digest', 'unknown'), ('password_hash', 'unknown'), ('extra', True)]:
            specs = copy.deepcopy(self.specs)
            specs[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                router.validate_model_specs(specs)
        for path in [('archive',), ('backup_format',), ('backup_format', 'checksum'), ('backup_format', 'checksum', 'prefix'), ('backup_format', 'trailer')]:
            specs = copy.deepcopy(self.specs)
            section = specs
            for key in path:
                section = section[key]
            section['extra'] = True
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'Unexpected JSON key: ' + '.'.join(path) + '.extra'):
                router.validate_model_specs(specs)
        for key in ('salted', 'password_hash', 'config_fields', 'archive'):
            specs = copy.deepcopy(self.specs)
            del specs[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                router.validate_model_specs(specs)

    def test_credentials_fail_cleanly(self):
        with self.assertRaises(FileNotFoundError):
            router.read_router_credential(str(self.root / 'missing'), self.specs)
        for data in (b'', b'\xff\x00', b'one\ntwo'):
            path = self.root / 'password'
            path.write_bytes(data)
            with self.subTest(data=data), self.assertRaises(ValueError):
                router.read_router_credential(str(path), self.specs)
        self.specs['key_derivation'] = 'device-key'
        with self.assertRaisesRegex(ValueError, 'THENC device key unavailable'):
            router.read_router_credential(str(self.root / 'password'), self.specs)

    def test_direct_encryption_credentials_and_encoding_selection(self):
        with patch.object(router, 'encode_base64_payload', return_value=b'transport') as helper:
            self.assertEqual(router.encode_router_payload(b'data', self.specs), b'transport')
            helper.assert_called_once_with(b'data', self.specs)
        with patch.object(router, 'decode_base64_payload', return_value=b'decoded') as helper:
            self.assertEqual(router.decode_router_payload(b'transport', self.specs), b'decoded')
            helper.assert_called_once_with(b'transport', self.specs)
        self.specs['key_derivation'] = 'device-key'
        with patch.object(router, 'load_device_key_credentials', side_effect=ValueError('device key unavailable')) as helper:
            with self.assertRaisesRegex(ValueError, 'device key unavailable'):
                router.read_router_credential('password.txt', self.specs)
            helper.assert_called_once_with('password.txt', self.specs)

    def test_legacy_crypto_performs_its_own_key_preparation(self):
        prepare = Mock(wraps=encryption.prepare_legacy_key)
        self.assertIs(router.crypt_aes_256_cbc, encryption.crypt_aes_256_cbc)
        with patch.object(encryption, 'prepare_legacy_key', prepare):
            encrypted = router.encrypt_router_payload(b'legacy preparation', 'password', self.specs)
            self.assertEqual(router.decrypt_router_payload(encrypted, 'password', self.specs), b'legacy preparation')
        self.assertEqual(prepare.call_count, 2)
        self.assertIs(prepare.call_args_list[0].args[-1], False)
        self.assertIs(prepare.call_args_list[1].args[-1], True)

    def test_direct_wrapper_archive_and_configuration_processing(self):
        paths, archive, backup = self.prepare_job()
        with patch.object(router, 'parse_line_wrapper', wraps=router.parse_line_wrapper) as parse:
            self.assertIn('encrypted', router.parse_router_wrapper(backup, self.specs))
            parse.assert_called_once_with(backup, self.specs)
        self.assertTrue(router.save_router_config(archive, paths['decoded_config_archive_path'], self.specs))
        with patch.object(router, 'extract_tar_archive', wraps=router.extract_tar_archive) as extract:
            self.assertTrue(router.extract_router_config(paths['decoded_config_archive_path'], paths['decoded_config_path'], self.specs))
            extract.assert_called_once_with(Path(paths['decoded_config_archive_path']), Path(paths['decoded_config_path']), self.specs)
        self.assertEqual(router.rebuild_tar_archive(archive, paths['decoded_config_path'], self.specs), (archive, []))
        files = router.read_tar_files(archive, self.specs)
        lines, fields = router.parse_key_value_fields(files[self.specs['config_fields']['file']].decode(), self.specs)
        self.assertEqual(len(fields), 4)
        self.assertTrue(lines)

    def test_archive_safety(self):
        for name in ('../escape', '/absolute'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                router.read_tar_files(tar_bytes({name: b'bad'}), self.specs)
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE):
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
                entry = tarfile.TarInfo('unsafe')
                entry.type = kind
                entry.linkname = '../escape'
                archive.addfile(entry)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                router.read_tar_files(buffer.getvalue(), self.specs)
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
            for _ in range(2):
                archive.addfile(tarfile.TarInfo('duplicate'))
        with self.assertRaises(ValueError):
            router.read_tar_files(buffer.getvalue(), self.specs)

    def test_symlink_directory_rejected(self):
        source = self.root / 'source'
        source.mkdir()
        (source / 'unsafe').symlink_to('/tmp')
        with self.assertRaises(ValueError):
            router.validate_directory(source)

    def test_edit_integrity_and_unchanged_rebuild(self):
        paths, archive, backup = self.prepare_job()
        router.save_router_config(archive, paths['decoded_config_archive_path'], self.specs)
        router.extract_router_config(paths['decoded_config_archive_path'], paths['decoded_config_path'], self.specs)
        self.assertEqual(router.rebuild_tar_archive(archive, paths['decoded_config_path'], self.specs), (archive, []))
        edited = router.edit_router_config_fields(paths['decoded_config_path'], paths['edited_config_path'], self.specs, paths['router_details_path'])
        self.assertTrue(edited)
        router.validate_edited_fields(archive, Path(edited), self.specs)
        config = Path(edited) / self.specs['config_fields']['file']
        self.assertIn(b'=replacement\r\n', config.read_bytes())
        config.write_bytes(config.read_bytes().replace(b'LOCKED=value', b'LOCKED=changed'))
        with self.assertRaisesRegex(ValueError, 'outside declared'):
            router.validate_edited_fields(archive, Path(edited), self.specs)
        self.assertIs(router.encode_router_config(edited, paths['template_config_path'], paths['encoded_config_path'], self.specs, paths['template_router_password_path'], paths['target_router_password_path']), False)
        self.assertFalse(Path(paths['encoded_config_path']).exists())
        self.assertEqual(Path(paths['template_config_path']).read_bytes(), backup)

    def test_config_parser_rejections(self):
        content = ''.join(f'{key}=value\n' for label, key in self.specs['config_fields'].items() if label != 'file')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            router.parse_key_value_fields(content + content, self.specs)
        with self.assertRaisesRegex(ValueError, 'Missing'):
            router.parse_key_value_fields('', self.specs)
        lines, fields = router.parse_key_value_fields(content, self.specs)
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            router.update_key_value_fields(lines, fields, {'invalid': 'value'})

    def test_configuration_validation_rejects_overlap(self):
        paths, _, _ = self.prepare_job()
        self.assertTrue(router.validate_router_configuration(paths, self.specs))
        paths['encoded_config_path'] = paths['decoded_config_path']
        with self.assertRaisesRegex(ValueError, 'distinct'):
            router.validate_router_configuration(paths, self.specs)

    def test_state_machine_run_all(self):
        from AutomationLoader import StateMachine, State
        from constants import RouterConstants
        paths, _, backup = self.prepare_job()
        machine = StateMachine(RouterConstants, auto_yes=True, cli_action='Run All Steps')
        machine.cfg_groups = {'configured-model': paths}
        machine.actions = RouterConstants.ACTIONS
        machine.select_action()
        self.assertEqual(machine.state, State.PIPELINE_PRE)
        machine.run_pipeline_pre()
        self.assertEqual(machine.state, State.CONFIRM)
        machine.confirm_action()
        self.assertEqual(machine.state, State.EXECUTE)
        machine.run_pipeline_action()
        self.assertEqual(machine.state, State.MENU_SELECTION)
        ctx = machine.runtime_ctx['groups']['configured-model']
        self.assertTrue(ctx.get('encoded_config'), self.output.getvalue())
        decoded = router.decode_router_config(paths['encoded_config_path'], self.specs, paths['target_router_password_path'])
        self.assertIn(b'=replacement\r\n', router.read_tar_files(decoded, self.specs)[self.specs['config_fields']['file']])
        self.assertEqual(Path(paths['template_config_path']).read_bytes(), backup)
        # Repeat to exercise existing output replacement.
        machine.select_action()
        machine.run_pipeline_pre()
        machine.confirm_action()
        machine.run_pipeline_action()
        self.assertTrue(machine.runtime_ctx['groups']['configured-model'].get('encoded_config'))

    def test_pipeline_failure_does_not_deploy(self):
        from AutomationLoader import StateMachine
        from constants import RouterConstants
        paths, _, backup = self.prepare_job()
        Path(paths['template_router_password_path']).unlink()
        machine = StateMachine(RouterConstants, auto_yes=True, cli_action='Run All Steps')
        machine.cfg_groups = {'test': paths}
        machine.actions = RouterConstants.ACTIONS
        machine.select_action()
        machine.run_pipeline_pre()
        machine.confirm_action()
        machine.run_pipeline_action()
        self.assertTrue(machine.runtime_ctx['groups']['test'].get('errors'))
        self.assertFalse(Path(paths['encoded_config_path']).exists())
        self.assertEqual(Path(paths['template_config_path']).read_bytes(), backup)

    def test_existing_mechanisms_through_pipeline_for_another_model(self):
        from AutomationLoader import StateMachine
        from constants import RouterConstants
        paths, _, backup = self.prepare_job()
        current = copy.deepcopy(self.specs)
        current.update(model='another-model', firmware='another-firmware', hardware='another-hardware')
        Path(paths['model_specs_path']).write_text(json.dumps(current))
        machine = StateMachine(RouterConstants, auto_yes=True, cli_action='Run All Steps')
        machine.cfg_groups = {'new-model': paths}
        machine.actions = RouterConstants.ACTIONS
        machine.select_action()
        machine.run_pipeline_pre()
        machine.confirm_action()
        machine.run_pipeline_action()
        self.assertTrue(machine.runtime_ctx['groups']['new-model'].get('encoded_config'), self.output.getvalue())
        decoded = router.decode_router_config(paths['encoded_config_path'], current, paths['target_router_password_path'])
        self.assertIn(b'=replacement\r\n', router.read_tar_files(decoded, current)[current['config_fields']['file']])
        self.assertEqual(Path(paths['template_config_path']).read_bytes(), backup)

    def test_optional_template_target_key_paths_through_run_all(self):
        import inspect
        from AutomationLoader import StateMachine
        from constants import RouterConstants as constants
        from modules.state_machine_utils import resolve_arg
        paths, _, backup = self.prepare_job()
        paths['template_device_key_path'] = str(self.root / 'unread-template-key.bin')
        paths['target_device_key_path'] = str(self.root / 'unread-target-key.bin')
        self.assertNotIn(constants.TEMPLATE_DEVICE_KEY_PATH, constants.VALIDATION_CONFIG['required_job_fields'])
        self.assertNotIn(constants.TARGET_DEVICE_KEY_PATH, constants.VALIDATION_CONFIG['required_job_fields'])
        for step in (constants.DECODE_CONFIG_EXEC[0], constants.ENCODE_CONFIG_EXEC[0]):
            values = [resolve_arg(value, 'job', paths, {'model_specs': self.specs}) for value in step['args']]
            bound = inspect.signature(step['fn']).bind(*values)
            self.assertEqual(bound.arguments['device_key_path'], paths['template_device_key_path' if step['fn'] is router.decode_router_config else 'target_device_key_path'])
            if step['fn'] is router.encode_router_config:
                self.assertEqual(bound.arguments['template_device_key_path'], paths['template_device_key_path'])
                self.assertEqual(bound.arguments['template_password_path'], paths['template_router_password_path'])
                self.assertEqual(bound.arguments['target_password_path'], paths['target_router_password_path'])
            optional = {key: value for key, value in paths.items() if key not in ('template_device_key_path', 'target_device_key_path')}
            values = [resolve_arg(value, 'job', optional, {'model_specs': self.specs}) for value in step['args']]
            self.assertIsNone(inspect.signature(step['fn']).bind(*values).arguments['device_key_path'])
        machine = StateMachine(constants, auto_yes=True, cli_action='Run All Steps')
        machine.cfg_groups = {'configured-model': paths}
        machine.actions = constants.ACTIONS
        with patch.object(router, 'decrypt_router_payload', wraps=router.decrypt_router_payload) as decrypt, patch.object(router, 'encrypt_router_payload', wraps=router.encrypt_router_payload) as encrypt:
            machine.select_action()
            machine.run_pipeline_pre()
            machine.confirm_action()
            machine.run_pipeline_action()
        self.assertTrue(machine.runtime_ctx['groups']['configured-model'].get('encoded_config'), self.output.getvalue())
        self.assertEqual([call.kwargs['device_key_path'] for call in decrypt.call_args_list],
                         [paths['template_device_key_path'], paths['template_device_key_path'], paths['target_device_key_path']])
        self.assertEqual(encrypt.call_args.kwargs['device_key_path'], paths['target_device_key_path'])
        self.assertEqual(Path(paths['template_config_path']).read_bytes(), backup)
        self.assertFalse(Path(paths['template_device_key_path']).exists())
        self.assertFalse(Path(paths['target_device_key_path']).exists())

    def test_device_key_preflight_checks_both_paths_without_reading_passwords(self):
        paths, _, _ = self.prepare_job()
        vodafone = json.loads((ROOT / 'routers/model_specs/Vodafone_UltraHub_DGA0130VDF-spec.json').read_text())
        Path(paths['router_details_path']).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'template_device_key_path is required'):
            router.validate_router_configuration(paths, vodafone)
        key = self.root / 'template-key.bin'
        key.write_bytes(b'\xff\x00test-key')
        paths['template_device_key_path'] = str(key)
        with self.assertRaisesRegex(ValueError, 'target_device_key_path is required'):
            router.validate_router_configuration(paths, vodafone)
        paths['target_device_key_path'] = str(self.root / 'missing-key.bin')
        with self.assertRaisesRegex(FileNotFoundError, 'target_device_key_path'):
            router.validate_router_configuration(paths, vodafone)
        target = self.root / 'target-key.bin'
        target.write_bytes(b'')
        paths['target_device_key_path'] = str(target)
        with self.assertRaisesRegex(ValueError, 'empty.*target_device_key_path'):
            router.validate_router_configuration(paths, vodafone)
        target.write_bytes(b'other-test-key')
        with patch.object(router, 'read_router_credential', side_effect=AssertionError('Device keys must not read password files')), patch.object(router, 'parse_router_wrapper'):
            self.assertTrue(router.validate_router_configuration(paths, vodafone))

    def test_real_spark_fixture(self):
        source = DATA / 'templates/Spark_SmartModem_VRV9517-template.cfg'
        password = DATA / 'templatePasswords/Spark_SmartModem_VRV9517-password.txt'
        if not source.is_file() or not password.is_file():
            self.skipTest('Local Spark backup/password unavailable')
        before = hashlib.sha256(source.read_bytes()).digest()
        decoded = router.decode_router_config(str(source), self.specs, str(password))
        archive = self.root / 'decoded.tar.gz'
        directory = self.root / 'decoded'
        edited = self.root / 'edited'
        details = self.root / 'details.json'
        details.write_text(json.dumps({'wifi_2g_ssid': 'RegressionTestSSID'}))
        self.assertTrue(router.save_router_config(decoded, str(archive), self.specs))
        self.assertTrue(router.extract_router_config(str(archive), str(directory), self.specs))
        self.assertTrue(router.edit_router_config_fields(str(directory), str(edited), self.specs, str(details)))
        output = self.root / 'encoded.cfg'
        self.assertTrue(router.encode_router_config(str(edited), str(source), str(output), self.specs, str(password), str(password)))
        result = router.decode_router_config(str(output), self.specs, str(password))
        self.assertIn(b'=RegressionTestSSID', router.read_tar_files(result, self.specs)[self.specs['config_fields']['file']])
        self.assertEqual(before, hashlib.sha256(source.read_bytes()).digest())

class RouterArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.spark = json.loads(next((ROOT / 'routers/model_specs').glob('Spark*.json')).read_text())
        self.vodafone = json.loads((ROOT / 'routers/model_specs/Vodafone_UltraHub_DGA0130VDF-spec.json').read_text())

    def schema_paths(self, schema=None, prefix=()):
        for key, kind in (router.ROUTER_SPEC_SCHEMA if schema is None else schema).items():
            path = prefix + (key,)
            yield path, kind
            if isinstance(kind, dict):
                yield from self.schema_paths(kind, path)

    def parent_at(self, data, path):
        for key in path[:-1]:
            data = data[key]
        return data

    def test_every_schema_key_is_required_and_type_checked(self):
        for original in (self.spark, self.vodafone):
            for path, kind in self.schema_paths():
                label = '.'.join(path)
                with self.subTest(model=original['model'], key=label, mutation='missing'):
                    current = copy.deepcopy(original)
                    del self.parent_at(current, path)[path[-1]]
                    with self.assertRaisesRegex(ValueError, label):
                        router.validate_model_specs(current)
                with self.subTest(model=original['model'], key=label, mutation='type'):
                    current = copy.deepcopy(original)
                    self.parent_at(current, path)[path[-1]] = []
                    with self.assertRaisesRegex(ValueError, label):
                        router.validate_model_specs(current)
                if kind is int:
                    current = copy.deepcopy(original)
                    self.parent_at(current, path)[path[-1]] = True
                    with self.subTest(model=original['model'], key=label, mutation='bool'), self.assertRaisesRegex(ValueError, label):
                        router.validate_model_specs(current)

    def test_unexpected_keys_in_every_object_are_rejected(self):
        objects = [()] + [path for path, kind in self.schema_paths() if isinstance(kind, dict)]
        for original in (self.spark, self.vodafone):
            for path in objects:
                current = copy.deepcopy(original)
                target = current
                for key in path:
                    target = target[key]
                target['misspelled'] = None
                label = '.'.join(path + ('misspelled',))
                with self.subTest(model=original['model'], key=label), self.assertRaisesRegex(ValueError, label):
                    router.validate_model_specs(current)

    def test_null_applicability_and_required_values(self):
        router.validate_model_specs(self.spark)
        router.validate_model_specs(self.vodafone)
        paths = [('salted',), ('password_required',), ('password_base',), ('password_hash',), ('key_derivation_digest',),
                 ('backup_format', 'header_lines'), ('backup_format', 'preserve_header'),
                 ('backup_format', 'payload_line_length'), ('backup_format', 'newline'),
                 ('backup_format', 'checksum', 'algorithm'), ('backup_format', 'checksum', 'scope'),
                 ('backup_format', 'checksum', 'encoding'), ('backup_format', 'checksum', 'after_payload_lines'),
                 ('backup_format', 'checksum', 'prefix', 'encoding'), ('backup_format', 'checksum', 'prefix', 'random_bytes'),
                 ('backup_format', 'trailer', 'character'), ('backup_format', 'trailer', 'repeat'),
                 ('archive', 'compression'), ('config_fields', 'file')]
        for path in paths:
            current = copy.deepcopy(self.spark)
            self.parent_at(current, path)[path[-1]] = None
            with self.subTest(key='.'.join(path)), self.assertRaisesRegex(ValueError, '.'.join(path)):
                router.validate_model_specs(current)
        for key in ('iv_length', 'signature_length', 'preamble', 'backup_version', 'header_terminator'):
            current = copy.deepcopy(self.vodafone)
            current['backup_format'][key] = None
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'backup_format.' + key):
                router.validate_model_specs(current)
        for key in self.spark['config_fields']:
            if key != 'file':
                self.spark['config_fields'][key] = None
        router.validate_model_specs(self.spark)
        self.assertEqual(router.parse_key_value_fields('LOCKED=value\n', self.spark)[1], {})
        for field in ('password_base', 'password_hash', 'key_derivation_digest'):
            self.assertIsNone(self.vodafone[field])
        self.assertTrue(all(value is None for value in self.vodafone['config_fields'].values()))

    def test_specs_schema_and_crypto_match_across_projects(self):
        import ast
        other_name = 'AutomationTools' if ROOT.name == 'TestingTools' else 'TestingTools'
        other = ROOT.parent / other_name
        other_specs = {data['model']: data for path in (other / 'routers/model_specs').glob('*.json')
                       for data in [json.loads(path.read_text())]}
        for current in (self.spark, self.vodafone):
            self.assertEqual(current, other_specs[current['model']])
        template = json.loads((ROOT / 'doc/RouterSpecificationTemplate.json').read_text())
        router.validate_spec_schema(template)
        self.assertEqual(template, json.loads((other / 'doc/RouterSpecificationTemplate.json').read_text()))
        def definitions(path):
            tree = ast.parse(path.read_text())
            return {node.targets[0].id if isinstance(node, ast.Assign) else node.name: ast.dump(node)
                    for node in tree.body if isinstance(node, ast.FunctionDef) or
                    isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'ROUTER_SPEC_SCHEMA'}
        current = definitions(ROOT / 'modules/router_utils.py')
        peer = definitions(other / 'modules/router_utils.py')
        for name in ('ROUTER_SPEC_SCHEMA', 'validate_model_specs', 'decrypt_router_payload', 'encrypt_router_payload',
                     'encode_router_payload', 'decode_router_payload', 'parse_router_wrapper', 'rebuild_router_wrapper',
                     'tar_gzip_mode', 'read_tar_files', 'extract_tar_archive', 'rebuild_tar_archive', 'parse_key_value_fields'):
            self.assertEqual(current[name], peer[name], name)
        self.assertEqual((ROOT / 'modules/router_encryption_utils.py').read_text(), (other / 'modules/router_encryption_utils.py').read_text())

    def test_thenc_parsing_and_explicit_crypto_failure(self):
        spec = copy.deepcopy(self.vodafone)
        fmt = spec['backup_format']
        header = ('PREAMBLE=THENC\nBACKUPVERSION=1.00\nBOARDMNEMONIC=VANT-9\n'
                  'PRODUCTNAME=MediaAccess\nSERIALNUMBER=test\nMAC=00:00:00:00:00:00\n'
                  'BUILDVERSION=17.4.b.0380-test\n'
                  'CIPHERKEY=test-cipher-id\nSIGNATUREKEY=test-signature-id\n\n').encode()
        data = header + bytes(range(16)) + b'ciphertext-block' * 4 + b's' * fmt['signature_length']
        wrapper = router.parse_router_wrapper(data, spec)
        self.assertEqual(wrapper['header'] + wrapper['iv'] + wrapper['encrypted'] + wrapper['signature'], data)
        self.assertEqual(wrapper['iv'], bytes(range(16)))
        self.assertEqual(wrapper['signature'], b's' * fmt['signature_length'])
        with patch.object(router.subprocess, 'run') as command:
            with self.assertRaisesRegex(ValueError, 'device key unavailable.*export password is not a device key'):
                router.decrypt_router_payload(wrapper['encrypted'], 'export-password', spec, wrapper=wrapper)
            with self.assertRaisesRegex(ValueError, 'signature verification are not established'):
                router.decrypt_router_payload(wrapper['encrypted'], '', spec, wrapper=wrapper, device_key=b'k' * 32)
            with self.assertRaisesRegex(ValueError, 'device key unavailable.*device_key_path'):
                router.encrypt_router_payload(b'plain', '', spec)
            command.assert_not_called()
        for malformed in (data[:-1], data.replace(b'VANT-9', b'VANT-8'), data.replace(b'THENC', b'WRONG')):
            with self.assertRaises(ValueError):
                router.parse_router_wrapper(malformed, spec)
        with tempfile.TemporaryDirectory() as temporary:
            password = Path(temporary) / 'export-password.txt'
            password.write_text('export-password')
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('Must not read a text password as a key')):
                with self.assertRaisesRegex(ValueError, 'export password is not a device key'):
                    router.read_router_credential(str(password), spec)

    def test_null_mappings_can_be_viewed(self):
        current = copy.deepcopy(self.spark)
        current['config_fields'] = {key: value if key == 'file' else None for key, value in current['config_fields'].items()}
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stdout(io.StringIO()):
            path = Path(temporary) / current['config_fields']['file']
            path.parent.mkdir(parents=True)
            path.write_text('LOCKED=keep\n')
            self.assertTrue(router.view_router_config_fields(temporary, current))

    def test_archive_replacement_restores_destination_on_interruption(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination, staged = Path(temporary) / 'destination', Path(temporary) / 'staged'
            destination.mkdir()
            staged.mkdir()
            (destination / 'old').write_bytes(b'original')
            (staged / 'new').write_bytes(b'replacement')
            replace = router.os.replace
            def interrupt(source, target):
                if Path(source) == staged:
                    raise KeyboardInterrupt()
                return replace(source, target)
            with patch.object(router.os, 'replace', side_effect=interrupt), self.assertRaises(KeyboardInterrupt):
                router.replace_router_directory(staged, destination)
            self.assertEqual((destination / 'old').read_bytes(), b'original')
            self.assertTrue((staged / 'new').exists())

    def test_encryption_selection_calls_imported_implementation_directly(self):
        self.assertIs(router.crypt_aes_256_cbc, encryption.crypt_aes_256_cbc)
        self.assertIs(router.crypt_technicolor_thenc, encryption.crypt_technicolor_thenc)
        self.assertEqual(router.ENCRYPTION_HANDLERS, {('aes-256-cbc', 'openssl-legacy'): encryption.crypt_aes_256_cbc, ('aes-256-cbc', 'device-key'): encryption.crypt_technicolor_thenc})
        helper = unittest.mock.Mock(wraps=encryption.crypt_aes_256_cbc)
        with patch.dict(router.ENCRYPTION_HANDLERS, {('aes-256-cbc', 'openssl-legacy'): helper}):
            encrypted = router.encrypt_router_payload(b'direct implementation', 'password', self.spark)
            self.assertEqual(router.decrypt_router_payload(encrypted, 'password', self.spark), b'direct implementation')
        self.assertEqual(helper.call_count, 2)
        self.assertEqual(helper.call_args_list[0], unittest.mock.call(b'direct implementation', 'password', self.spark, False))
        self.assertEqual(helper.call_args_list[1], unittest.mock.call(encrypted, 'password', self.spark, True, wrapper=None, device_key=None))
        wrapper = {'iv': b'context'}
        helper = unittest.mock.Mock(side_effect=ValueError('test failure'))
        with patch.dict(router.ENCRYPTION_HANDLERS, {('aes-256-cbc', 'device-key'): helper}):
            with self.assertRaisesRegex(ValueError, 'test failure'):
                router.decrypt_router_payload(b'cipher', '', self.vodafone, wrapper=wrapper, device_key=b'key')
            helper.assert_called_once_with(b'cipher', '', self.vodafone, True, wrapper=wrapper, device_key=b'key')

    def test_unsupported_encryption_pairs_fail_before_crypto(self):
        for cipher, derivation in (('unsupported-cipher', 'openssl-legacy'), ('aes-256-cbc', 'unsupported-derivation')):
            current = copy.deepcopy(self.spark)
            current.update(encryption=cipher, key_derivation=derivation)
            for operation in (router.encrypt_router_payload, router.decrypt_router_payload):
                with self.subTest(cipher=cipher, derivation=derivation, operation=operation.__name__):
                    with patch.object(encryption.subprocess, 'run') as command, self.assertRaisesRegex(ValueError, 'Unsupported encryption mechanism:'):
                        operation(b'data', 'password', current)
                    command.assert_not_called()
                    with patch.object(router, 'validate_model_specs'), self.assertRaisesRegex(ValueError, 'Unsupported encryption mechanism:'):
                        operation(b'data', 'password', current)

    def test_module_layout_has_no_encryption_forwarding_functions(self):
        import ast
        forbidden = {'mechanism_handler', 'archive_handler', 'archive_mode', 'rebuild_router_archive', 'configuration_handler', 'parse_config_fields', 'decrypt_openssl_legacy_payload', 'encrypt_openssl_legacy_payload', 'decrypt_device_key_payload',
                     'decrypt_password_payload', 'encrypt_password_payload'}
        module_files = {path.name for path in (ROOT / 'modules').glob('router*.py')}
        self.assertEqual(module_files, {'router_utils.py', 'router_encryption_utils.py'})
        for filename in module_files:
            path = ROOT / 'modules' / filename
            source = path.read_text()
            tree = ast.parse(source)
            definitions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
            self.assertFalse(forbidden & definitions.keys())
            if filename == 'router_utils.py':
                self.assertNotIn('crypt_aes_256_cbc', definitions)
                self.assertNotIn('globals()', source)
                self.assertEqual({node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id.endswith('_HANDLERS')}, {'ENCRYPTION_HANDLERS'})
                self.assertNotIn('binary_payload', source)
                self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'update' for node in ast.walk(tree)))
            lines = source.splitlines()
            previous = None
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    self.assertTrue(all(line.strip() for line in lines[node.lineno-1:node.end_lineno]), node.name)
                    if previous is not None:
                        gap = lines[previous.end_lineno:node.lineno-1]
                        if not any(line.strip() for line in gap):
                            self.assertEqual(len(gap), 2, node.name)
                    previous = node

    def test_binary_transport_returns_original_object(self):
        data = bytes(range(256))
        for value in (data, b''):
            self.assertIs(router.encode_router_payload(value, self.vodafone), value)
            self.assertIs(router.decode_router_payload(value, self.vodafone), value)
        self.assertFalse(hasattr(router, 'binary_payload'))

    def test_device_key_files_are_binary_and_crypto_remains_unavailable(self):
        key = bytes(range(32)) + b'\xff\x00\n'
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'key.bin'
            path.write_bytes(key)
            helper = unittest.mock.Mock(side_effect=ValueError('crypto unavailable'))
            wrapper = {'iv': b'context'}
            with patch.dict(router.ENCRYPTION_HANDLERS, {('aes-256-cbc', 'device-key'): helper}):
                with self.assertRaisesRegex(ValueError, 'crypto unavailable'):
                    router.decrypt_router_payload(b'cipher', '', self.vodafone, wrapper=wrapper, device_key_path=str(path))
                helper.assert_called_once_with(b'cipher', '', self.vodafone, True, wrapper=wrapper, device_key=key)
                helper.reset_mock()
                with self.assertRaisesRegex(ValueError, 'crypto unavailable'):
                    router.encrypt_router_payload(b'plain', '', self.vodafone, str(path))
                helper.assert_called_once_with(b'plain', '', self.vodafone, False, device_key=key)
            with patch.object(encryption.subprocess, 'run') as command:
                with self.assertRaisesRegex(ValueError, 'derivation and signature verification are not established'):
                    router.decrypt_router_payload(b'cipher', '', self.vodafone, device_key_path=str(path))
                with self.assertRaisesRegex(ValueError, 'signature signing are not established'):
                    router.encrypt_router_payload(b'plain', '', self.vodafone, str(path))
                command.assert_not_called()

    def test_device_key_paths_are_required_only_for_device_key_mechanisms(self):
        with tempfile.TemporaryDirectory() as temporary:
            empty = Path(temporary) / 'empty.bin'
            empty.write_bytes(b'')
            for operation in (router.decrypt_router_payload, router.encrypt_router_payload):
                for path in (None, ''):
                    with self.subTest(operation=operation.__name__, path=path), self.assertRaisesRegex(ValueError, 'device_key_path is required'):
                        operation(b'data', '', self.vodafone, device_key_path=path)
                with self.assertRaisesRegex(ValueError, 'device key file is empty'):
                    operation(b'data', '', self.vodafone, device_key_path=str(empty))
                with self.assertRaises(FileNotFoundError):
                    operation(b'data', '', self.vodafone, device_key_path=str(empty.parent / 'missing.bin'))
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('Spark must not read a device key')):
                encrypted = router.encrypt_router_payload(b'Spark without a key', 'password', self.spark, str(empty))
                self.assertEqual(router.decrypt_router_payload(encrypted, 'password', self.spark, device_key_path='missing.bin'), b'Spark without a key')

    def test_thenc_identifiers_come_from_each_header_and_decode_receives_key(self):
        fmt = self.vodafone['backup_format']
        header = ('PREAMBLE=THENC\nBACKUPVERSION=1.00\nBOARDMNEMONIC=VANT-9\n'
                  'PRODUCTNAME=MediaAccess\nSERIALNUMBER=test\nMAC=00:00:00:00:00:00\n'
                  'BUILDVERSION=17.4.b.0380-test\nCIPHERKEY=dynamic-cipher\nSIGNATUREKEY=dynamic-signature\n\n').encode()
        backup = header + bytes(range(16)) + b'x' * 32 + b's' * fmt['signature_length']
        wrapper = router.parse_router_wrapper(backup, self.vodafone)
        self.assertEqual(wrapper['cipher_key_id'], 'dynamic-cipher')
        self.assertEqual(wrapper['signature_key_id'], 'dynamic-signature')
        self.assertEqual(wrapper['header'], header)
        for field in ('CIPHERKEY', 'SIGNATUREKEY'):
            changed = backup.replace((field + '=dynamic-').encode(), (field + '=different-').encode())
            self.assertEqual(router.parse_router_wrapper(changed, self.vodafone)['header'], changed.partition(b'\n\n')[0] + b'\n\n')
        for field in ('CIPHERKEY=dynamic-cipher', 'SIGNATUREKEY=dynamic-signature'):
            malformed = backup.replace(field.encode(), (field.split('=')[0] + '=').encode())
            with self.assertRaisesRegex(ValueError, 'Invalid THENC header field'):
                router.parse_router_wrapper(malformed, self.vodafone)
        with tempfile.TemporaryDirectory() as temporary:
            source, key_path = Path(temporary) / 'backup.bin', Path(temporary) / 'key.bin'
            source.write_bytes(backup)
            key_path.write_bytes(b'\xff\x00binary-key')
            with self.assertRaisesRegex(ValueError, 'signature verification are not established'):
                if ROOT.name == 'TestingTools':
                    router.decode_router_config(str(source), self.vodafone, 'not-a-key.txt', 'Existing prompt: ', str(key_path))
                else:
                    router.decode_router_config(str(source), self.vodafone, 'not-a-key.txt', str(key_path))
            self.assertEqual(source.read_bytes(), backup)

    def test_static_specs_and_templates_have_no_thenc_key_identifiers(self):
        self.assertNotIn('cipher_key_id', router.ROUTER_SPEC_SCHEMA['backup_format'])
        self.assertNotIn('signature_key_id', router.ROUTER_SPEC_SCHEMA['backup_format'])
        for spec in (self.spark, self.vodafone, json.loads((ROOT / 'doc/RouterSpecificationTemplate.json').read_text())):
            self.assertNotIn('cipher_key_id', spec['backup_format'])
            self.assertNotIn('signature_key_id', spec['backup_format'])

    def test_router_modules_import_in_either_order(self):
        import subprocess
        import sys
        for order in ('router_encryption_utils, router_utils', 'router_utils, router_encryption_utils'):
            result = subprocess.run([sys.executable, '-c', 'from modules import ' + order], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_supplied_thenc_fixture_is_preserved(self):
        data_root = Path.home() / ('Documents/' + ROOT.name + 'Data/routers')
        source = data_root / 'templates/Vodafone_Ultra_Hub-template.bin'
        if not source.is_file():
            self.skipTest('Local Vodafone fixture unavailable')
        original = source.read_bytes()
        wrapper = router.parse_router_wrapper(original, self.vodafone)
        self.assertEqual(wrapper['header'] + wrapper['iv'] + wrapper['encrypted'] + wrapper['signature'], original)
        with self.assertRaisesRegex(ValueError, 'device key unavailable'):
            router.decode_router_config(str(source), self.vodafone, str(data_root / 'templatePasswords/Vodafone_Ultra_Hub-password.txt'))
        self.assertEqual(source.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
