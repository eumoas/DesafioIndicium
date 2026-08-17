import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import schema as schema_generator


class TypeInferenceTests(unittest.TestCase):
    def test_classifies_supported_types(self):
        cases = {
            "TRUE": schema_generator.BOOLEAN,
            "false": schema_generator.BOOLEAN,
            "42": schema_generator.INTEGER,
            str(2**31): schema_generator.BIGINT,
            str(2**63): schema_generator.NUMERIC,
            "10.50": schema_generator.NUMERIC,
            "1e3": schema_generator.NUMERIC,
            "2026-08-16": schema_generator.DATE,
            "2026-08-16 10:30:00": schema_generator.TIMESTAMP,
            "2026-08-16T10:30:00Z": schema_generator.TIMESTAMPTZ,
            "texto": schema_generator.TEXT,
            "001": schema_generator.TEXT,
        }

        for value, expected_type in cases.items():
            with self.subTest(value=value):
                self.assertEqual(schema_generator.classify_value(value), expected_type)

    def test_promotes_compatible_types(self):
        self.assertEqual(
            schema_generator.promote_type(
                schema_generator.INTEGER, schema_generator.BIGINT
            ),
            schema_generator.BIGINT,
        )
        self.assertEqual(
            schema_generator.promote_type(
                schema_generator.BIGINT, schema_generator.NUMERIC
            ),
            schema_generator.NUMERIC,
        )
        self.assertEqual(
            schema_generator.promote_type(
                schema_generator.DATE, schema_generator.TIMESTAMP
            ),
            schema_generator.TIMESTAMP,
        )
        self.assertEqual(
            schema_generator.promote_type(
                schema_generator.NUMERIC, schema_generator.TEXT
            ),
            schema_generator.TEXT,
        )

    def test_identifier_convention_preserves_codes_as_text(self):
        for column_name in (
            "cpf",
            "ncm_code",
            "nfe_access_key",
            "order_number",
            "supplier_sku",
            "barcode_ean",
        ):
            with self.subTest(column_name=column_name):
                self.assertTrue(schema_generator.is_text_identifier(column_name))


class CsvInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def write_csv(self, name, content):
        path = self.directory / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_inspects_the_whole_file_and_preserves_column_order(self):
        csv_path = self.write_csv(
            "sample.csv",
            "id,active,amount,event_date,event_at,cpf,mixed,empty\n"
            "1,TRUE,10,2026-08-16,2026-08-16 10:00:00,12345678901,1,\n"
            "2,FALSE,10.50,2026-08-17,2026-08-17 11:00:00,00123456789,texto,\n",
        )

        table = schema_generator.inspect_csv(csv_path)
        inferred_types = {
            column.name: column.postgres_type for column in table.columns
        }

        self.assertEqual(table.row_count, 2)
        self.assertEqual(
            [column.name for column in table.columns],
            [
                "id",
                "active",
                "amount",
                "event_date",
                "event_at",
                "cpf",
                "mixed",
                "empty",
            ],
        )
        self.assertEqual(inferred_types["id"], "INTEGER")
        self.assertEqual(inferred_types["active"], "BOOLEAN")
        self.assertEqual(inferred_types["amount"], "NUMERIC")
        self.assertEqual(inferred_types["event_date"], "DATE")
        self.assertEqual(
            inferred_types["event_at"], "TIMESTAMP WITHOUT TIME ZONE"
        )
        self.assertEqual(inferred_types["cpf"], "TEXT")
        self.assertEqual(inferred_types["mixed"], "TEXT")
        self.assertEqual(inferred_types["empty"], "TEXT")

    def test_handles_bom_unicode_and_quoted_comma(self):
        path = self.directory / "unicode.csv"
        path.write_bytes(
            '\ufeffid,descrição\r\n1,"peça, náutica"\r\n'.encode("utf-8")
        )

        table = schema_generator.inspect_csv(path)

        self.assertEqual(table.row_count, 1)
        self.assertEqual(table.columns[0].postgres_type, "INTEGER")
        self.assertEqual(table.columns[1].postgres_type, "TEXT")

    def test_header_only_file_falls_back_to_text(self):
        csv_path = self.write_csv("header_only.csv", "unknown_column\n")

        table = schema_generator.inspect_csv(csv_path)

        self.assertEqual(table.row_count, 0)
        self.assertEqual(table.columns[0].postgres_type, "TEXT")
        self.assertEqual(table.columns[0].non_empty_count, 0)

    def test_rejects_empty_file(self):
        csv_path = self.write_csv("empty.csv", "")

        with self.assertRaisesRegex(
            schema_generator.SchemaInferenceError, "arquivo vazio"
        ):
            schema_generator.inspect_csv(csv_path)

    def test_rejects_duplicate_header(self):
        csv_path = self.write_csv("duplicate.csv", "id,id\n1,2\n")

        with self.assertRaisesRegex(
            schema_generator.SchemaInferenceError, "coluna duplicada"
        ):
            schema_generator.inspect_csv(csv_path)

    def test_rejects_row_with_wrong_width(self):
        csv_path = self.write_csv("broken.csv", "id,name\n1\n")

        with self.assertRaisesRegex(
            schema_generator.SchemaInferenceError, "eram esperados 2"
        ):
            schema_generator.inspect_csv(csv_path)


class SchemaGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_quotes_identifiers_and_escapes_double_quotes(self):
        column = schema_generator.ColumnProfile('select"value')
        column.observe("content")
        table = schema_generator.TableSchema(
            name="order",
            source_path=Path("order.csv"),
            columns=[column],
            row_count=1,
        )

        sql = schema_generator.render_create_table(table)

        self.assertEqual(
            sql,
            'CREATE TABLE "order" (\n    "select""value" TEXT\n);',
        )

    def test_output_is_deterministic_and_contains_one_table_per_csv(self):
        (self.directory / "z.csv").write_text("id\n1\n", encoding="utf-8")
        (self.directory / "a.csv").write_text("name\nitem\n", encoding="utf-8")
        output = self.directory / "schema.sql"

        tables = schema_generator.generate_schema(self.directory, output)
        first_result = output.read_text(encoding="utf-8")
        schema_generator.generate_schema(self.directory, output)
        second_result = output.read_text(encoding="utf-8")

        self.assertEqual([table.name for table in tables], ["a", "z"])
        self.assertEqual(first_result, second_result)
        self.assertEqual(first_result.count("CREATE TABLE"), 2)
        self.assertLess(
            first_result.index('CREATE TABLE "a"'),
            first_result.index('CREATE TABLE "z"'),
        )
        self.assertTrue(first_result.startswith("-- Schema inferido"))
        self.assertTrue(first_result.endswith("COMMIT;\n"))

    def test_existing_output_is_not_changed_when_inspection_fails(self):
        (self.directory / "broken.csv").write_text("id,name\n1\n", encoding="utf-8")
        output = self.directory / "schema.sql"
        output.write_text("conteúdo anterior\n", encoding="utf-8")

        with self.assertRaises(schema_generator.SchemaInferenceError):
            schema_generator.generate_schema(self.directory, output)

        self.assertEqual(
            output.read_text(encoding="utf-8"), "conteúdo anterior\n"
        )


if __name__ == "__main__":
    unittest.main()
