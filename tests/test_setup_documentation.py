"""Keep published setup examples aligned with the actual workflow generator."""
from __future__ import annotations

from pathlib import Path
import re
import shlex
import unittest
from urllib.parse import unquote, urlsplit

from maintainer_radar.cli import build_parser
from maintainer_radar.workflow import DEFAULT_ACTION_REF, render_github_action_workflow


ROOT = Path(__file__).resolve().parents[1]
SETUP_DOCS = ('adoption.md', 'github-action.md', 'github-actions.md', 'quickstart.md')
SETUP_REF = re.compile(r'uses:\s+(actions/setup-python@[^\s\'"`]+)')
ACTION_REF = re.compile(r'uses:\s+(JackSpiece/maintainer-radar@[^\s\'"`]+)')


class SetupDocumentationTests(unittest.TestCase):
    def test_setup_python_references_match_generator_and_checked_workflows(self) -> None:
        generated = render_github_action_workflow()
        expected = set(SETUP_REF.findall(generated))
        self.assertEqual(len(expected), 1)
        paths = [ROOT / 'README.md', *sorted((ROOT / 'docs').glob('*.md')),
                 *sorted((ROOT / '.github/workflows').glob('*.yml')),
                 *sorted((ROOT / 'examples/github-actions').glob('*.yml'))]
        found = set()
        for path in paths:
            refs = set(SETUP_REF.findall(path.read_text(encoding='utf-8')))
            if refs:
                with self.subTest(path=path.relative_to(ROOT)):
                    self.assertEqual(refs, expected)
                found.add(path.name)
        self.assertTrue(set(SETUP_DOCS).issubset(found))
        self.assertTrue({'README.md', 'ci.yml', 'release.yml'}.issubset(found))

    def test_setup_docs_keep_published_action_ref_and_read_only_permissions(self) -> None:
        for name in SETUP_DOCS:
            with self.subTest(doc=name):
                docs = (ROOT / 'docs' / name).read_text(encoding='utf-8')
                self.assertEqual(set(ACTION_REF.findall(docs)), {DEFAULT_ACTION_REF})
                self.assertIn('contents: read', docs)
                self.assertIn('pull-requests: read', docs)
                self.assertNotRegex(docs, r'(?m)^\s+(?:contents|pull-requests):\s*write\b')
                self.assertIn('GH_TOKEN: ${{ github.token }}', docs)

    def test_documented_cli_commands_parse_without_network_or_writes(self) -> None:
        parser = build_parser()
        for name in SETUP_DOCS:
            docs = (ROOT / 'docs' / name).read_text(encoding='utf-8')
            blocks = re.findall(r'```(?:bash|sh)\n(.*?)```', docs, flags=re.DOTALL)
            commands = [line for block in blocks for line in block.replace('\\\n', ' ').splitlines()
                        if line.startswith('maintainer-radar ')]
            self.assertTrue(commands, name)
            for command in commands:
                with self.subTest(doc=name, command=command):
                    parser.parse_args(shlex.split(command)[1:])

    def test_setup_docs_relative_links_resolve(self) -> None:
        for name in SETUP_DOCS:
            path = ROOT / 'docs' / name
            docs = path.read_text(encoding='utf-8')
            for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', docs):
                url = urlsplit(target)
                if url.scheme or url.netloc or not url.path:
                    continue
                with self.subTest(doc=name, target=target):
                    self.assertTrue((path.parent / unquote(url.path)).exists())


if __name__ == '__main__':
    unittest.main()
