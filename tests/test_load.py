import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import load as csv_loader  # noqa: E402


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

    def test_discovers_csvs_in_a_deterministic_order(self):
        self.write_csv("z.CSV", "id\n1\n")
        self.write_csv("a.csv", "id\n2\n")
        self.write_csv("notes.txt", "não é uma fonte")

        files = csv_loader.discover_csv_files(self.directory)

        self.assertEqual([path.name for path in files], ["a.csv", "z.CSV"])

    def test_inspects_bom_unicode_and_a_quoted_line_break(self):
        path = self.directory / "sample.csv"
        path.write_bytes(
            (
                "\ufeffid,description,optional\r\n"
                '1,"peça, náutica",\r\n'
                '2,"texto em\nduas linhas",N/A\r\n'
            ).encode("utf-8")
        )

        source = csv_loader.inspect_csv(path)

        self.assertEqual(source.table_name, "sample")
        self.assertEqual(source.columns, ["id", "description", "optional"])
        self.assertEqual(source.row_count, 2)

    def test_rejects_duplicate_header(self):
        path = self.write_csv("duplicate.csv", "id,id\n1,2\n")

        with self.assertRaisesRegex(csv_loader.LoadError, "coluna duplicada"):
            csv_loader.inspect_csv(path)

    def test_rejects_row_with_wrong_width(self):
        path = self.write_csv("broken.csv", "id,name\n1\n")

        with self.assertRaisesRegex(csv_loader.LoadError, "eram esperados 2"):
            csv_loader.inspect_csv(path)


class DatabasePreflightTests(unittest.TestCase):
    class CatalogCursor:
        def __init__(self, columns):
            self.columns = columns
            self.parameters = None

        def execute(self, statement, parameters=None):
            self.parameters = parameters

        def fetchall(self):
            return [(column,) for column in self.columns]

    def test_accepts_the_same_columns_in_the_same_order(self):
        source = csv_loader.CsvSource(Path("orders.csv"), "orders", ["id", "total"], 1)
        cursor = self.CatalogCursor(["id", "total"])

        csv_loader.validate_database_schema(cursor, [source], "public")

        self.assertEqual(cursor.parameters, ("public", "orders"))

    def test_rejects_schema_drift_before_loading(self):
        source = csv_loader.CsvSource(Path("orders.csv"), "orders", ["id", "total"], 1)
        cursor = self.CatalogCursor(["total", "id"])

        with self.assertRaisesRegex(csv_loader.LoadError, "não correspondem"):
            csv_loader.validate_database_schema(cursor, [source], "public")


class CopyTests(unittest.TestCase):
    class CopyCursor:
        def __init__(self):
            self.statement = None
            self.received_text = None

        def copy_expert(self, statement, csv_file):
            self.statement = statement
            self.received_text = csv_file.read()

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_sends_the_original_csv_without_cleaning_values(self):
        content = (
            "id,description,missing,empty_string\r\n"
            '1," peça, náutica ",,""\r\n'
            '2,N/A,,"duas\nlinhas"\r\n'
        )
        path = self.directory / "items.csv"
        path.write_bytes(("\ufeff" + content).encode("utf-8"))
        source = csv_loader.CsvSource(
            path,
            "items",
            ["id", "description", "missing", "empty_string"],
            2,
        )
        cursor = self.CopyCursor()

        csv_loader.copy_source(cursor, source, "public")

        self.assertEqual(cursor.received_text, content)
        self.assertIsInstance(cursor.statement, csv_loader.sql.Composable)

    def test_rejects_a_header_changed_after_the_inspection(self):
        path = self.directory / "items.csv"
        path.write_text("name,id\nitem,1\n", encoding="utf-8")
        source = csv_loader.CsvSource(path, "items", ["id", "name"], 1)
        cursor = self.CopyCursor()

        with self.assertRaisesRegex(csv_loader.LoadError, "cabeçalho mudou"):
            csv_loader.copy_source(cursor, source, "public")

        self.assertIsNone(cursor.received_text)

    def test_copy_statement_keeps_names_as_identifiers(self):
        source = csv_loader.CsvSource(
            Path("order.csv"), "order", ["select", 'column"name'], 1
        )

        statement = csv_loader.build_copy_statement(source, "raw-data")
        representation = repr(statement)

        self.assertIn("Identifier('raw-data', 'order')", representation)
        self.assertIn("Identifier('select')", representation)
        self.assertIn("Identifier('column\"name')", representation)
        self.assertNotIn("COPY raw-data.order", representation)


class LoadTransactionTests(unittest.TestCase):
    class Cursor:
        def __init__(self, source, fail_copy=False):
            self.source = source
            self.fail_copy = fail_copy
            self.last_result = None
            self.copied_text = None
            self.executed_statements = []

        def __enter__(self):
            return self

        def __exit__(self, exception_type, exception, traceback):
            return False

        def execute(self, statement, parameters=None):
            representation = str(statement)
            self.executed_statements.append(representation)
            if "information_schema.columns" in representation:
                self.last_result = [(column,) for column in self.source.columns]
            elif "SELECT EXISTS" in representation:
                self.last_result = [(False,)]
            elif "SELECT COUNT" in representation:
                self.last_result = [(self.source.row_count,)]

        def fetchall(self):
            return self.last_result

        def fetchone(self):
            return self.last_result[0]

        def copy_expert(self, statement, csv_file):
            if self.fail_copy:
                raise csv_loader.psycopg2.DataError("valor incompatível")
            self.copied_text = csv_file.read()

    class Connection:
        def __init__(self, cursor):
            self.test_cursor = cursor
            self.client_encoding = None
            self.exit_exception_type = None

        def set_client_encoding(self, encoding):
            self.client_encoding = encoding

        def __enter__(self):
            return self

        def __exit__(self, exception_type, exception, traceback):
            self.exit_exception_type = exception_type
            return False

        def cursor(self):
            return self.test_cursor

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.path = self.directory / "orders.csv"
        self.path.write_text("id,total\n1,10.50\n", encoding="utf-8")
        self.source = csv_loader.CsvSource(self.path, "orders", ["id", "total"], 1)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_loads_and_checks_the_final_row_count(self):
        cursor = self.Cursor(self.source)
        connection = self.Connection(cursor)

        with contextlib.redirect_stdout(io.StringIO()):
            loaded_rows = csv_loader.load_sources(connection, [self.source], "public")

        self.assertEqual(loaded_rows, 1)
        self.assertEqual(connection.client_encoding, "UTF8")
        self.assertIsNone(connection.exit_exception_type)
        self.assertEqual(cursor.copied_text, "id,total\n1,10.50\n")
        lock_position = next(
            index
            for index, statement in enumerate(cursor.executed_statements)
            if "LOCK TABLE" in statement
        )
        empty_check_position = next(
            index
            for index, statement in enumerate(cursor.executed_statements)
            if "SELECT EXISTS" in statement
        )
        self.assertLess(lock_position, empty_check_position)

    def test_copy_failure_leaves_the_transaction_with_an_exception(self):
        cursor = self.Cursor(self.source, fail_copy=True)
        connection = self.Connection(cursor)

        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(csv_loader.LoadError, "orders.csv"):
                csv_loader.load_sources(connection, [self.source], "public")

        self.assertIs(connection.exit_exception_type, csv_loader.LoadError)


class ErrorFormattingTests(unittest.TestCase):
    def test_copy_error_does_not_expose_the_rejected_value(self):
        class Diagnostic:
            message_primary = 'invalid input syntax for integer: "12345678901"'
            context = 'COPY customers, line 3, column cpf: "12345678901"'

        class DatabaseError:
            diag = Diagnostic()

        message = csv_loader.format_database_error(DatabaseError())

        self.assertIn("line 3, column cpf", message)
        self.assertNotIn("12345678901", message)


if __name__ == "__main__":
    unittest.main()
