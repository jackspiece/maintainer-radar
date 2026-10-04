from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from maintainer_radar.cli import main
from maintainer_radar.workflow import DEFAULT_ACTION_REF, render_github_action_workflow

try:
    import yaml
except ImportError:
    yaml = None


SEPARATORS = ("\x85", "\u2028", "\u2029")
ORDINARY_REFS = (
    DEFAULT_ACTION_REF,
    "owner/repository@0123456789abcdef0123456789abcdef01234567",
    "owner/repository/sub-action@feature/next",
    "owner/repository@release-1.2+build",
    "owner/repository@日本語",
    "./",
    "./.github/actions/review",
    "./日本語",
    "docker://alpine:3.20",
    "docker://ghcr.io/owner/image@sha256:" + "a" * 64,
)
QUOTED_REFS = (
    'owner/repository@say"yes',
    "owner/repository@single'quote",
    '"owner/repository@v1"',
    "'owner/repository@v1'",
    r"owner/repository@literal\u0085\u2028\u2029",
    'owner/repository@backslash\\"quote',
    "owner/repository@日本語-🛰️",
    "./local action",
    "$/path/to/action",
    "owner/repository@tab\there",
    "owner/repository@${literal}",
    "owner/repository@${{literal}}",
    "${{ inputs.action_ref }}",
    "owner/repository@tag # literal",
    "owner/repository@tag#literal",
    "owner/repository@branch]",
    "owner/repository@tag: literal",
    "owner/repository@tag:",
    "true",
    "null",
    "123",
    "*alias",
    "[one, two]",
    "{key: value}",
)


def action_scalar(output: str) -> str:
    return output.split("        uses: ", 1)[1].split("\n", 1)[0]


class WorkflowActionReferenceTests(unittest.TestCase):
    def test_unicode_separators_are_escaped_without_a_yaml_dependency(self) -> None:
        for separator in SEPARATORS:
            with self.subTest(separator=ascii(separator)):
                value = f"alpha{separator}beta"
                output = render_github_action_workflow(action_ref=value)
                self.assertEqual(action_scalar(output), f'"alpha\\u{ord(separator):04x}beta"')
                self.assertNotIn(separator, output)
                self.assertEqual(json.loads(action_scalar(output)), value)

    def test_quoted_values_round_trip_without_a_yaml_dependency(self) -> None:
        for value in QUOTED_REFS:
            with self.subTest(value=value):
                scalar = action_scalar(render_github_action_workflow(action_ref=value))
                self.assertEqual(json.loads(scalar), value)
        # YAML does not combine JSON's paired UTF-16 surrogate escapes.
        scalar = action_scalar(render_github_action_workflow(action_ref="./🛰️"))
        self.assertIn("🛰️", scalar)
        self.assertNotIn("\\ud83d", scalar)

    def test_ordinary_references_keep_exact_workflow_bytes(self) -> None:
        default_output = render_github_action_workflow()
        for value in ORDINARY_REFS:
            with self.subTest(value=value):
                self.assertEqual(
                    render_github_action_workflow(action_ref=value),
                    default_output.replace(f"uses: {DEFAULT_ACTION_REF}", f"uses: {value}"),
                )

    def test_existing_whitespace_and_empty_value_contract_is_preserved(self) -> None:
        default_output = render_github_action_workflow()
        for value in (None, "", " \t ", *SEPARATORS):
            with self.subTest(value=ascii(value)):
                self.assertEqual(render_github_action_workflow(action_ref=value), default_output)
        for separator in (" ", "\t", *SEPARATORS):
            with self.subTest(separator=ascii(separator)):
                value = separator + "owner/repository@v1" + separator
                self.assertEqual(action_scalar(render_github_action_workflow(action_ref=value)),
                                 "owner/repository@v1")

    def test_existing_forbidden_characters_and_cr_lf_still_reject(self) -> None:
        for character in ("\n", "\r", "\x01", "\ud800", "\uffff"):
            with self.subTest(character=ascii(character)):
                with self.assertRaisesRegex(ValueError, "--action-ref"):
                    render_github_action_workflow(action_ref=f"alpha{character}beta")

    def test_cli_preserves_separators_in_stdout_and_written_workflows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for index, separator in enumerate(SEPARATORS):
                value = f'owner/repository@日本語"{separator}🛰️'
                destination = Path(directory) / "nested" / f"workflow-{index}.yml"
                for extra in ([], ["--path", str(destination)]):
                    with self.subTest(separator=ascii(separator), destination=bool(extra)):
                        stdout, stderr = io.StringIO(), io.StringIO()
                        with redirect_stdout(stdout), redirect_stderr(stderr):
                            status = main(["init-action", "--action-ref", value, *extra])
                        self.assertEqual(status, 0, stderr.getvalue())
                        output = destination.read_text() if extra else stdout.getvalue()
                        self.assertEqual(json.loads(action_scalar(output)), value)
                        self.assertEqual(output, render_github_action_workflow(action_ref=value))


@unittest.skipIf(yaml is None, "PyYAML is required for full workflow parse/round-trip checks")
class WorkflowActionReferenceYamlTests(unittest.TestCase):
    def assert_workflow_round_trip(self, value: str, **kwargs: str) -> None:
        output = render_github_action_workflow(action_ref=value, **kwargs)
        for loader in (yaml.BaseLoader, yaml.SafeLoader):
            with self.subTest(loader=loader.__name__):
                document = yaml.load(output, Loader=loader)
                expected = yaml.load(render_github_action_workflow(**kwargs), Loader=loader)
                step = next(step for step in document["jobs"]["report"]["steps"] if step.get("id") == "radar")
                expected_step = next(step for step in expected["jobs"]["report"]["steps"]
                                     if step.get("id") == "radar")
                self.assertEqual(step["uses"], value.strip())
                self.assertIsInstance(step["uses"], str)
                expected_step["uses"] = value.strip()
                self.assertEqual(document, expected)

    def test_exact_auditor_unicode_separator_reproductions(self) -> None:
        for separator in SEPARATORS:
            with self.subTest(separator=ascii(separator)):
                self.assert_workflow_round_trip(f"alpha{separator}beta")

    def test_unicode_separators_in_references_quotes_and_expressions(self) -> None:
        for separator in SEPARATORS:
            values = (
                f"owner/repository@alpha{separator}beta",
                f"./alpha{separator}beta",
                f'owner/repository@日本語"{separator}🛰️\\branch',
                f"owner/repository@${{{{alpha{separator}beta}}}}",
                f"alpha{separator}beta{separator}gamma",
            )
            for value in values:
                with self.subTest(value=ascii(value)):
                    self.assert_workflow_round_trip(value)

    def test_ordinary_unicode_and_quoted_values_are_literal_strings(self) -> None:
        for value in (*ORDINARY_REFS, *QUOTED_REFS):
            with self.subTest(value=value):
                self.assert_workflow_round_trip(value)

    def test_existing_expression_bearing_options_are_preserved(self) -> None:
        self.assert_workflow_round_trip(
            "owner/repository@${{literal}}",
            label="${{ inputs.filter }}",
            config="${{ inputs.config }}",
            author="${{ github.actor }}",
        )


if __name__ == "__main__":
    unittest.main()
