#!/usr/bin/env python3
"""Exercise package boundaries, real link operations, and model-probe failures."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.evals import validate_evals
from scripts.packages import lint_skill_packages as lint

ROOT = Path(__file__).resolve().parents[1]


class PackageSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.skill = Path(self.temp.name) / 'sample'
        self.skill.mkdir()
        (self.skill / 'SKILL.md').write_text('---\nname: sample\ndescription: Test sample packages.\n---\n# Sample\n')

    def test_traversal_link_rejected(self):
        with (self.skill / 'SKILL.md').open('a') as out:
            out.write('\n[Outside](../outside.md)\n')
        self.assertIn('link.escape', [x.code for x in lint.validate_skill_diagnostics(self.skill)])

    @unittest.skipIf(os.name == 'nt', 'POSIX symlink test')
    def test_external_entrypoint_not_read(self):
        entry = self.skill / 'SKILL.md'
        entry.unlink()
        outside = Path(self.temp.name) / 'outside'
        outside.write_text('SECRET_MARKER')
        entry.symlink_to(outside)
        result = lint.validate_skill_diagnostics(self.skill)
        self.assertIn('path.external-symlink', [x.code for x in result])
        self.assertNotIn('SECRET_MARKER', str(result))

    def test_bad_utf8_diagnosed(self):
        (self.skill / 'SKILL.md').write_bytes(b'\xff')
        self.assertIn('skill.read', [x.code for x in lint.validate_skill_diagnostics(self.skill)])

    def test_unknown_standard_field_warns(self):
        entry = self.skill / 'SKILL.md'
        entry.write_text(entry.read_text().replace('name: sample', 'name: sample\nfuture-field: "yes"'))
        diagnostics = lint.validate_skill_diagnostics(self.skill)
        self.assertFalse(any(item.severity == 'error' for item in diagnostics))
        self.assertIn('frontmatter.extension', [item.code for item in diagnostics])

    def test_yaml_error_does_not_echo_secret(self):
        data, result = lint.load_mapping('token: [SECRET_MARKER', self.skill)
        self.assertEqual(data, {})
        self.assertNotIn('SECRET_MARKER', str(result))


@unittest.skipIf(os.name == 'nt', 'Bash link integration tests run on Linux')
class LinkIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='skill project ')
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name)

    def run_script(self, filename, *args):
        return subprocess.run(
            ['bash', str(ROOT / 'scripts' / 'links' / filename), *map(str, args)],
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_idempotence_and_uninstall(self):
        name = 'python-domain-modeling'
        first = self.run_script('install.sh', self.target, name)
        second = self.run_script('install.sh', self.target, name)
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertIn(f'keep  {name}', second.stdout)
        link = self.target / '.agents/skills' / name
        self.assertTrue(link.is_symlink())
        self.assertEqual(self.run_script('uninstall.sh', self.target, name).returncode, 0)
        self.assertFalse(link.is_symlink())
        self.assertTrue((ROOT / 'skills' / name / 'SKILL.md').is_file())

    def test_target_path_is_required(self):
        self.assertEqual(self.run_script('install.sh').returncode, 2)
        self.assertEqual(self.run_script('uninstall.sh').returncode, 2)

    def test_invalid_name_and_existing_directory_preserved(self):
        self.assertNotEqual(self.run_script('install.sh', self.target, '../escape').returncode, 0)
        dest = self.target / '.agents/skills/python-domain-modeling'
        dest.mkdir(parents=True)
        self.assertNotEqual(self.run_script('install.sh', self.target, dest.name).returncode, 0)
        self.assertTrue(dest.is_dir())

    def test_install_preflights_all_names_before_mutation(self):
        valid = 'python-domain-modeling'
        completed = self.run_script('install.sh', self.target, valid, 'unknown-skill')
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse((self.target / '.agents').exists())

    def test_uninstall_preflights_all_names_before_mutation(self):
        valid = 'python-domain-modeling'
        self.assertEqual(self.run_script('install.sh', self.target, valid).returncode, 0)
        link = self.target / '.agents/skills' / valid
        completed = self.run_script('uninstall.sh', self.target, valid, '../escape')
        self.assertNotEqual(completed.returncode, 0)
        self.assertTrue(link.is_symlink())

    def test_linked_destination_rejected_on_install_and_remove(self):
        outside = self.target / 'outside'
        outside.mkdir()
        (self.target / '.agents').symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(self.run_script('install.sh', self.target).returncode, 0)
        self.assertNotEqual(self.run_script('uninstall.sh', self.target).returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])

    def test_broken_link_requires_explicit_removal(self):
        name = 'python-domain-modeling'
        link = self.target / '.agents/skills' / name
        link.parent.mkdir(parents=True)
        link.symlink_to(self.target / 'missing-source', target_is_directory=True)

        install = self.run_script('install.sh', self.target, name)
        self.assertNotEqual(install.returncode, 0)
        self.assertIn('broken symbolic link', install.stderr)

        conservative = self.run_script('uninstall.sh', self.target, name)
        self.assertEqual(conservative.returncode, 0)
        self.assertIn('broken symbolic link', conservative.stdout)
        self.assertTrue(link.is_symlink())

        remove = self.run_script('uninstall.sh', '--remove-broken', self.target, name)
        self.assertEqual(remove.returncode, 0)
        self.assertFalse(link.is_symlink())


class EvalTests(unittest.TestCase):
    @staticmethod
    def write_dataset(root, skills=('sample-skill',)):
        skills_dir = root / 'skills'
        evals_dir = root / 'evals'
        skills_dir.mkdir()
        evals_dir.mkdir()
        for skill in skills:
            package = skills_dir / skill
            package.mkdir()
            (package / 'SKILL.md').write_text(
                f'---\nname: {skill}\ndescription: Test routing.\n---\n# Sample\n',
                encoding='utf-8',
            )
        for filename, numbers in (
            ('train_queries.json', range(1, 7)),
            ('validation_queries.json', range(7, 11)),
        ):
            cases = []
            for skill in skills:
                for should_trigger, label in ((True, 'positive'), (False, 'negative')):
                    for number in numbers:
                        cases.append({
                            'id': f'{skill}-{label}-{number:02d}',
                            'skill': skill,
                            'query': f'{filename} {skill} {label} {number}',
                            'should_trigger': should_trigger,
                        })
            (evals_dir / filename).write_text(json.dumps(cases), encoding='utf-8')
        return evals_dir, skills_dir

    def test_repository_splits(self):
        self.assertEqual(validate_evals.validate(ROOT / 'evals', ROOT / 'skills'), [])

    def test_bad_labels_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'cases.json'
            path.write_text(json.dumps([{'id': 'x', 'query': 'q', 'skill': 's', 'should_trigger': 'false'}]))
            _, errors = validate_evals.load_cases(path)
            self.assertTrue(errors)

    def test_case_id_must_match_label_and_split(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evals, skills = self.write_dataset(root)
            train_path = evals / 'train_queries.json'
            cases = json.loads(train_path.read_text())
            cases[0]['id'] = 'sample-skill-positive-07'
            train_path.write_text(json.dumps(cases), encoding='utf-8')
            errors = validate_evals.validate(evals, skills)
            self.assertTrue(any('wrong split' in error for error in errors))

    def test_missing_duplicate_unknown_and_missing_skill_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evals, skills = self.write_dataset(root, ('sample-skill', 'unused-skill'))
            train_path = evals / 'train_queries.json'
            cases = json.loads(train_path.read_text())
            cases = [case for case in cases if case['skill'] != 'unused-skill']
            cases[1]['id'] = cases[0]['id']
            cases.append({
                'id': 'unknown-skill-positive-01',
                'skill': 'unknown-skill',
                'query': 'Unknown skill query',
                'should_trigger': True,
            })
            train_path.write_text(json.dumps(cases), encoding='utf-8')
            validation_path = evals / 'validation_queries.json'
            validation_cases = [
                case for case in json.loads(validation_path.read_text())
                if case['skill'] != 'unused-skill'
            ]
            validation_path.write_text(json.dumps(validation_cases), encoding='utf-8')

            errors = validate_evals.validate(evals, skills)
            self.assertTrue(any('duplicate case id' in error for error in errors))
            self.assertTrue(any('unknown skills' in error for error in errors))
            self.assertTrue(any('skills without evals' in error for error in errors))
            self.assertTrue(any('exactly once' in error for error in errors))

    def test_missing_directories_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertTrue(validate_evals.validate(root / 'missing-evals', root / 'missing-skills'))

if __name__ == '__main__':
    unittest.main()
