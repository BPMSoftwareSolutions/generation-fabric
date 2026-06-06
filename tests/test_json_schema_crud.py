from __future__ import annotations

import contextlib
import io
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import json_schema_crud as jsc
from generation_fabric.markdown.registry import (
    DEFAULT_MARKDOWN_CONTRACT_KIND,
    get_markdown_contract_spec,
    list_markdown_contract_kinds,
)


class JsonSchemaCrudTests(unittest.TestCase):
    def run_cli(self, *args: str, input_lines: list[str] | None = None) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            if input_lines is None:
                code = jsc.main(list(args))
            else:
                with patch("builtins.input", side_effect=input_lines):
                    code = jsc.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_new_create_validate_and_subschema_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            schema_path = tmp_path / "user.schema.json"

            code, stdout, stderr = self.run_cli(
                "new",
                "--output",
                str(schema_path),
                "--title",
                "User",
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("created schema", stdout)

            code, _, stderr = self.run_cli(
                "create",
                "--file",
                str(schema_path),
                "--pointer",
                "/properties/name",
                "--value",
                '{"type":"string"}',
            )
            self.assertEqual(code, 0, stderr)

            code, stdout, stderr = self.run_cli("validate", "--file", str(schema_path))
            self.assertEqual(code, 0, stderr)
            self.assertIn("schema is valid", stdout)

            code, stdout, stderr = self.run_cli(
                "validate",
                "--file",
                str(schema_path),
                "--pointer",
                "/properties/name",
                "--instance",
                '"Ada"',
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("schema and instance are valid", stdout)

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            self.assertEqual(schema["title"], "User")
            self.assertEqual(schema["properties"]["name"]["type"], "string")

    def test_infer_generates_schema_from_sample_array(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            sample_path = tmp_path / "sample.json"
            output_path = tmp_path / "inferred.schema.json"

            sample_path.write_text(
                json.dumps(
                    [
                        {"id": 1, "name": "Ada"},
                        {"id": 2, "name": "Bob", "email": "bob@example.com"},
                    ]
                ),
                encoding="utf-8",
            )

            code, stdout, stderr = self.run_cli(
                "infer",
                "--sample-file",
                str(sample_path),
                "--output",
                str(output_path),
                "--title",
                "Users",
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("inferred schema written", stdout)

            schema = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(schema["type"], "array")
            self.assertEqual(schema["items"]["type"], "object")
            self.assertEqual(set(schema["items"]["properties"].keys()), {"email", "id", "name"})
            self.assertEqual(schema["items"]["required"], ["id", "name"])

            code, stdout, stderr = self.run_cli(
                "validate",
                "--file",
                str(output_path),
                "--instance-file",
                str(sample_path),
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("schema and instance are valid", stdout)

    def test_json_document_crud_commands_work_on_generic_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            data_path = tmp_path / "data.json"

            data_path.write_text(
                json.dumps({"user": {"name": "Ada"}, "items": [1, 2]}),
                encoding="utf-8",
            )

            code, stdout, stderr = self.run_cli(
                "json-read",
                "--file",
                str(data_path),
                "--pointer",
                "/user/name",
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(stdout.strip(), '"Ada"')

            code, _, stderr = self.run_cli(
                "json-create",
                "--file",
                str(data_path),
                "--pointer",
                "/user/email",
                "--value",
                '"ada@example.com"',
            )
            self.assertEqual(code, 0, stderr)

            code, _, stderr = self.run_cli(
                "json-update",
                "--file",
                str(data_path),
                "--pointer",
                "/items/0",
                "--value",
                "10",
            )
            self.assertEqual(code, 0, stderr)

            code, _, stderr = self.run_cli(
                "json-delete",
                "--file",
                str(data_path),
                "--pointer",
                "/user/name",
            )
            self.assertEqual(code, 0, stderr)

            document = json.loads(data_path.read_text(encoding="utf-8"))
            self.assertEqual(document, {"user": {"email": "ada@example.com"}, "items": [10, 2]})

    def test_oneof_and_anyof_helpers_attach_combinators(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            schema_path = tmp_path / "combo.schema.json"

            self.run_cli("new", "--output", str(schema_path), "--title", "Combo")
            self.run_cli(
                "create",
                "--file",
                str(schema_path),
                "--pointer",
                "/properties/contact",
                "--value",
                "{}",
            )

            code, _, stderr = self.run_cli(
                "oneof",
                "--file",
                str(schema_path),
                "--pointer",
                "/properties/contact",
                "--variant",
                '{"type":"string"}',
                "--variant",
                '{"type":"null"}',
            )
            self.assertEqual(code, 0, stderr)

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            self.assertEqual(schema["properties"]["contact"]["oneOf"][1]["type"], "null")

            code, _, stderr = self.run_cli(
                "anyof",
                "--file",
                str(schema_path),
                "--pointer",
                "/properties/contact",
                "--variant",
                '{"type":"string"}',
                "--variant",
                '{"type":"number"}',
            )
            self.assertEqual(code, 0, stderr)

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            self.assertEqual(schema["properties"]["contact"]["anyOf"][1]["type"], "number")

    def test_markdown_contract_scaffold_and_render(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            contract_dir = tmp_path / "examples"
            rendered_path = contract_dir / "rendered-release-notes.md"
            code, stdout, stderr = self.run_cli(
                "markdown-contract",
                "--directory",
                str(contract_dir),
                "--with-markdown",
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("scaffolded markdown contract", stdout)

            schema_path = contract_dir / "release-notes.schema.json"
            data_path = contract_dir / "release-notes.json"
            output_path = contract_dir / "release-notes.md"
            self.assertTrue(schema_path.exists())
            self.assertTrue(data_path.exists())
            self.assertTrue(output_path.exists())

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            data = json.loads(data_path.read_text(encoding="utf-8"))
            scaffolded_markdown = output_path.read_text(encoding="utf-8")
            self.assertEqual(schema["title"], "Release Notes")
            self.assertEqual(schema["properties"]["sections"]["items"]["x-markdown"]["heading"], "")
            self.assertEqual(data["sections"][0]["title"], "Renderer")

            code, stdout, stderr = self.run_cli(
                "markdown",
                "--schema",
                str(schema_path),
                "--data-file",
                str(data_path),
                "--output",
                str(rendered_path),
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("markdown written", stdout)

            rendered = rendered_path.read_text(encoding="utf-8")
            self.assertEqual(rendered, scaffolded_markdown)
            self.assertIn("# Release Notes", rendered)
            self.assertIn("**version**: 1.0.0", rendered)
            self.assertIn("## Renderer", rendered)
            self.assertIn("- Validates the schema before rendering", rendered)

    def test_markdown_import_generates_a_reusable_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            source_path = tmp_path / "legacy.md"
            output_dir = tmp_path / "generated"
            source_text = (
                "# Legacy Notes\n\n"
                "This is an intro paragraph.\n\n"
                "> Self-healing starts here.\n"
                "> Legacy content becomes structure.\n\n"
                "- Alpha\n"
                "- Beta\n\n"
                "1. First\n"
                "2. Second\n\n"
                "```python\n"
                "print(\"hello\")\n"
                "```\n\n"
                "| Name | Value |\n"
                "| --- | --- |\n"
                "| One | 1 |\n"
                "| Two | 2 |\n"
            )
            source_path.write_text(source_text, encoding="utf-8")

            code, stdout, stderr = self.run_cli(
                "markdown-import",
                "--file",
                str(source_path),
                "--directory",
                str(output_dir),
                "--with-markdown",
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("imported markdown contract", stdout)

            schema_path = output_dir / "legacy.schema.json"
            data_path = output_dir / "legacy.json"
            markdown_path = output_dir / "legacy.md"
            self.assertTrue(schema_path.exists())
            self.assertTrue(data_path.exists())
            self.assertTrue(markdown_path.exists())

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            data = json.loads(data_path.read_text(encoding="utf-8"))
            rendered = markdown_path.read_text(encoding="utf-8")

            self.assertEqual(schema["title"], "Legacy Notes")
            self.assertEqual(schema["properties"]["paragraph_1"]["x-markdown"]["kind"], "paragraph")
            self.assertEqual(schema["properties"]["paragraph_1"]["x-sample"], "This is an intro paragraph.")
            self.assertEqual(schema["properties"]["blockquote_1"]["x-markdown"]["kind"], "blockquote")
            self.assertEqual(schema["properties"]["list_1"]["x-markdown"]["kind"], "list")
            self.assertEqual(schema["properties"]["ordered_list_1"]["x-markdown"]["kind"], "ordered-list")
            self.assertEqual(schema["properties"]["code_1"]["x-markdown"]["kind"], "code")
            self.assertEqual(schema["properties"]["table_1"]["x-markdown"]["kind"], "table")
            self.assertEqual(data["paragraph_1"], "This is an intro paragraph.")
            self.assertEqual(data["blockquote_1"], "Self-healing starts here.\nLegacy content becomes structure.")
            self.assertEqual(data["list_1"], ["Alpha", "Beta"])
            self.assertEqual(data["ordered_list_1"], ["First", "Second"])
            self.assertEqual(data["code_1"], 'print("hello")')
            self.assertEqual(data["table_1"][0]["Name"], "One")

            code, stdout, stderr = self.run_cli(
                "markdown",
                "--schema",
                str(schema_path),
                "--data-file",
                str(data_path),
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(stdout, rendered)
            self.assertEqual(rendered.strip(), source_text.strip())

    def test_json_sample_scaffolds_from_schema_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            schema_path = tmp_path / "hints.schema.json"
            output_path = tmp_path / "hints.json"

            schema_path.write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "title": "Hints",
                        "type": "object",
                        "properties": {
                            "email": {"type": "string", "format": "email"},
                            "status": {"type": "string", "enum": ["draft", "published"]},
                            "count": {"type": "integer"},
                            "enabled": {"type": "boolean"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["email", "status", "count", "enabled", "tags"],
                    }
                ),
                encoding="utf-8",
            )

            code, stdout, stderr = self.run_cli(
                "json-sample",
                "--schema",
                str(schema_path),
                "--output",
                str(output_path),
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("json sample written", stdout)

            sample = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(sample["email"], "user@example.com")
            self.assertEqual(sample["status"], "draft")
            self.assertEqual(sample["count"], 1)
            self.assertTrue(sample["enabled"])
            self.assertEqual(sample["tags"], ["sample"])

    def test_example_contract_files_are_in_sync(self) -> None:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        schema_path = repo_root / "examples" / "release-notes.schema.json"
        data_path = repo_root / "examples" / "release-notes.json"

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        data = json.loads(data_path.read_text(encoding="utf-8"))

        code, stdout, stderr = self.run_cli(
            "markdown",
            "--schema",
            str(schema_path),
            "--data-file",
            str(data_path),
        )
        self.assertEqual(code, 0, stderr)
        self.assertEqual(stdout, (repo_root / "examples" / "release-notes.md").read_text(encoding="utf-8"))
        self.assertEqual(schema["title"], "Release Notes")
        self.assertEqual(data["sections"][1]["title"], "Quality")

    def test_markdown_contract_registry_is_discoverable(self) -> None:
        kinds = list_markdown_contract_kinds()
        self.assertIn(DEFAULT_MARKDOWN_CONTRACT_KIND, kinds)
        self.assertIn("docs-showcase", kinds)
        self.assertIn("readme", kinds)

        spec = get_markdown_contract_spec(DEFAULT_MARKDOWN_CONTRACT_KIND)
        self.assertEqual(spec.kind, DEFAULT_MARKDOWN_CONTRACT_KIND)
        self.assertEqual(spec.base_name, "release-notes")
        self.assertTrue(spec.schema_path.exists())
        self.assertTrue(spec.sample_path.exists())

        docs_spec = get_markdown_contract_spec("docs-showcase")
        self.assertEqual(docs_spec.kind, "docs-showcase")
        self.assertEqual(docs_spec.base_name, "docs-showcase")
        self.assertTrue(docs_spec.schema_path.exists())
        self.assertTrue(docs_spec.sample_path.exists())

        readme_spec = get_markdown_contract_spec("readme")
        self.assertEqual(readme_spec.kind, "readme")
        self.assertEqual(readme_spec.base_name, "readme")
        self.assertTrue(readme_spec.schema_path.exists())
        self.assertTrue(readme_spec.sample_path.exists())

        with self.assertRaises(jsc.SchemaError):
            get_markdown_contract_spec("does-not-exist")

    def test_readme_contract_renders_the_checked_in_readme(self) -> None:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        schema_path = repo_root / "examples" / "readme.schema.json"
        data_path = repo_root / "examples" / "readme.json"
        readme_path = repo_root / "README.md"

        code, stdout, stderr = self.run_cli(
            "markdown",
            "--schema",
            str(schema_path),
            "--data-file",
            str(data_path),
        )
        self.assertEqual(code, 0, stderr)
        self.assertEqual(stdout, readme_path.read_text(encoding="utf-8"))

    def test_docs_showcase_contract_renders_code_fences(self) -> None:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        schema_path = repo_root / "examples" / "docs-showcase.schema.json"
        data_path = repo_root / "examples" / "docs-showcase.json"
        showcase_path = repo_root / "examples" / "docs-showcase.md"

        code, stdout, stderr = self.run_cli(
            "markdown",
            "--schema",
            str(schema_path),
            "--data-file",
            str(data_path),
        )
        self.assertEqual(code, 0, stderr)
        self.assertEqual(stdout, showcase_path.read_text(encoding="utf-8"))
        self.assertIn("```mermaid", stdout)
        self.assertIn("```csharp", stdout)
        self.assertIn("```json", stdout)

    def test_json_sample_command_can_generate_the_workflow_showcase(self) -> None:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        schema_path = repo_root / "examples" / "workflow-showcase.schema.json"
        expected_path = repo_root / "examples" / "workflow-showcase.json"
        markdown_path = repo_root / "examples" / "workflow-showcase.md"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            output_path = tmp_path / "workflow-showcase.json"

            code, stdout, stderr = self.run_cli(
                "json-sample",
                "--schema",
                str(schema_path),
                "--output",
                str(output_path),
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("json sample written", stdout)

            generated = json.loads(output_path.read_text(encoding="utf-8"))
            expected = json.loads(expected_path.read_text(encoding="utf-8"))
            self.assertEqual(generated, expected)

            code, stdout, stderr = self.run_cli(
                "markdown",
                "--schema",
                str(schema_path),
                "--data-file",
                str(output_path),
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(stdout, markdown_path.read_text(encoding="utf-8"))
            self.assertIn("```mermaid", stdout)
            self.assertIn("```text", stdout)

    def test_markdown_contract_scaffold_can_emit_docs_showcase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            code, stdout, stderr = self.run_cli(
                "markdown-contract",
                "--kind",
                "docs-showcase",
                "--directory",
                str(tmp_path),
                "--with-markdown",
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("scaffolded markdown contract", stdout)

            schema_path = tmp_path / "docs-showcase.schema.json"
            data_path = tmp_path / "docs-showcase.json"
            markdown_path = tmp_path / "docs-showcase.md"
            self.assertTrue(schema_path.exists())
            self.assertTrue(data_path.exists())
            self.assertTrue(markdown_path.exists())

            code, stdout, stderr = self.run_cli(
                "markdown",
                "--schema",
                str(schema_path),
                "--data-file",
                str(data_path),
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(stdout, markdown_path.read_text(encoding="utf-8"))

    def test_interactive_mode_can_create_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            schema_path = tmp_path / "shell.schema.json"

            code, stdout, stderr = self.run_cli(
                "interactive",
                input_lines=[
                    f"new {schema_path} Shell",
                    'create /properties/flag {"type":"boolean"}',
                    "validate",
                    "exit",
                ],
            )

            self.assertEqual(code, 0, stderr)
            self.assertIn("interactive mode ready", stdout)
            self.assertTrue(schema_path.exists())

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            self.assertEqual(schema["properties"]["flag"]["type"], "boolean")


if __name__ == "__main__":
    unittest.main()
