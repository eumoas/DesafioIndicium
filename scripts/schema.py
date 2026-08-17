#!/usr/bin/env python3
"""Gera um schema PostgreSQL a partir dos CSVs de um diretório."""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional, Sequence


UNKNOWN = "UNKNOWN"
BOOLEAN = "BOOLEAN"
INTEGER = "INTEGER"
BIGINT = "BIGINT"
NUMERIC = "NUMERIC"
DATE = "DATE"
TIMESTAMP = "TIMESTAMP"
TIMESTAMPTZ = "TIMESTAMPTZ"
TEXT = "TEXT"

INTEGER_MIN = -(2**31)
INTEGER_MAX = 2**31 - 1
BIGINT_MIN = -(2**63)
BIGINT_MAX = 2**63 - 1
POSTGRES_IDENTIFIER_MAX_BYTES = 63

INTEGER_PATTERN = re.compile(r"[+-]?\d+\Z")
NUMERIC_PATTERN = re.compile(
    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z"
)

# Estes nomes representam códigos, não valores usados em cálculos. A lista é
# uma convenção de ingestão e pode ser ampliada quando houver um dicionário de dados.
TEXT_IDENTIFIER_NAMES = frozenset(
    {
        "barcode_ean",
        "cnpj",
        "code",
        "cpf",
        "number",
        "phone",
        "postal_code",
        "series",
        "state_registration",
        "tax_id",
    }
)
TEXT_IDENTIFIER_SUFFIXES = ("_code", "_ean", "_key", "_number", "_sku")

POSTGRES_TYPES = {
    BOOLEAN: "BOOLEAN",
    INTEGER: "INTEGER",
    BIGINT: "BIGINT",
    NUMERIC: "NUMERIC",
    DATE: "DATE",
    TIMESTAMP: "TIMESTAMP WITHOUT TIME ZONE",
    TIMESTAMPTZ: "TIMESTAMP WITH TIME ZONE",
    TEXT: "TEXT",
}


class SchemaInferenceError(Exception):
    """Erro esperado durante a leitura ou a inferência do schema."""


@dataclass
class ColumnProfile:
    name: str
    inferred_type: str = UNKNOWN
    non_empty_count: int = 0

    def observe(self, value: str) -> None:
        # O campo vazio não ajuda a descobrir o tipo da coluna.
        if value == "":
            return

        self.non_empty_count += 1
        if self.inferred_type == TEXT:
            return

        if is_text_identifier(self.name):
            observed_type = TEXT
        else:
            observed_type = classify_value(value)

        self.inferred_type = promote_type(self.inferred_type, observed_type)

    @property
    def postgres_type(self) -> str:
        inferred_type = TEXT if self.inferred_type == UNKNOWN else self.inferred_type
        return POSTGRES_TYPES[inferred_type]


@dataclass
class TableSchema:
    name: str
    source_path: Path
    columns: List[ColumnProfile]
    row_count: int


def is_text_identifier(column_name: str) -> bool:
    normalized_name = column_name.casefold()
    return (
        normalized_name in TEXT_IDENTIFIER_NAMES
        or normalized_name.endswith(TEXT_IDENTIFIER_SUFFIXES)
    )


def has_leading_zero(value: str) -> bool:
    unsigned_value = value.lstrip("+-")
    return len(unsigned_value) > 1 and unsigned_value.startswith("0")


def classify_value(value: str) -> str:
    # Começo pelos tipos mais específicos e deixo TEXT como última opção.
    if value.casefold() in {"true", "false"}:
        return BOOLEAN

    if INTEGER_PATTERN.fullmatch(value):
        # Um zero à esquerda pode fazer parte de um código, como 001.
        if has_leading_zero(value):
            return TEXT

        integer_value = int(value)
        if INTEGER_MIN <= integer_value <= INTEGER_MAX:
            return INTEGER
        if BIGINT_MIN <= integer_value <= BIGINT_MAX:
            return BIGINT
        return NUMERIC

    if NUMERIC_PATTERN.fullmatch(value):
        try:
            numeric_value = Decimal(value)
        except InvalidOperation:
            pass
        else:
            if numeric_value.is_finite():
                return NUMERIC

    try:
        date.fromisoformat(value)
    except ValueError:
        pass
    else:
        return DATE

    timestamp_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp_value)
    except ValueError:
        return TEXT

    if (
        parsed_timestamp.tzinfo is not None
        and parsed_timestamp.utcoffset() is not None
    ):
        return TIMESTAMPTZ
    return TIMESTAMP


def promote_type(current_type: str, observed_type: str) -> str:
    if current_type == UNKNOWN:
        return observed_type
    if current_type == observed_type:
        return current_type
    if TEXT in {current_type, observed_type}:
        return TEXT

    numeric_order = {INTEGER: 0, BIGINT: 1, NUMERIC: 2}
    if current_type in numeric_order and observed_type in numeric_order:
        # Se aparecem 10 e 10.5, a coluna precisa aceitar os dois valores.
        return max((current_type, observed_type), key=numeric_order.get)

    if {current_type, observed_type} <= {DATE, TIMESTAMP}:
        return TIMESTAMP

    return TEXT


def validate_identifier(identifier: str, context: str) -> None:
    if not identifier or not identifier.strip():
        raise SchemaInferenceError(f"{context}: identificador vazio")

    if any(ord(character) < 32 or ord(character) == 127 for character in identifier):
        raise SchemaInferenceError(
            f"{context}: identificador possui caractere de controle"
        )

    identifier_size = len(identifier.encode("utf-8"))
    if identifier_size > POSTGRES_IDENTIFIER_MAX_BYTES:
        raise SchemaInferenceError(
            f"{context}: identificador possui {identifier_size} bytes; "
            f"o limite padrão do PostgreSQL é {POSTGRES_IDENTIFIER_MAX_BYTES}"
        )


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def discover_csv_files(input_directory: Path) -> List[Path]:
    if not input_directory.exists():
        raise SchemaInferenceError(f"diretório não encontrado: {input_directory}")
    if not input_directory.is_dir():
        raise SchemaInferenceError(f"o caminho não é um diretório: {input_directory}")

    try:
        csv_files = sorted(
            (
                path
                for path in input_directory.iterdir()
                if path.is_file() and path.suffix.casefold() == ".csv"
            ),
            key=lambda path: (path.name.casefold(), path.name),
        )
    except OSError as error:
        raise SchemaInferenceError(
            f"não foi possível listar o diretório {input_directory}: {error}"
        ) from error

    if not csv_files:
        raise SchemaInferenceError(
            f"nenhum arquivo CSV foi encontrado em {input_directory}"
        )
    return csv_files


def inspect_csv(csv_path: Path) -> TableSchema:
    table_name = csv_path.stem
    validate_identifier(table_name, f"arquivo {csv_path.name}")

    try:
        with csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.reader(csv_file, strict=True)
            try:
                header = next(reader)
            except StopIteration as error:
                raise SchemaInferenceError(f"{csv_path}: arquivo vazio") from error

            if not header:
                raise SchemaInferenceError(f"{csv_path}: cabeçalho vazio")

            seen_columns = set()
            for column_name in header:
                validate_identifier(
                    column_name,
                    f"arquivo {csv_path.name}, coluna do cabeçalho",
                )
                if column_name in seen_columns:
                    raise SchemaInferenceError(
                        f"{csv_path}: coluna duplicada no cabeçalho: {column_name!r}"
                    )
                seen_columns.add(column_name)

            columns = [ColumnProfile(name) for name in header]
            row_count = 0

            # Preferi analisar o arquivo inteiro. Uma amostra poderia não encontrar
            # um texto ou decimal que aparecesse apenas nas últimas linhas.
            for row in reader:
                if len(row) != len(columns):
                    raise SchemaInferenceError(
                        f"{csv_path}: linha {reader.line_num} possui "
                        f"{len(row)} campos; "
                        f"eram esperados {len(columns)}"
                    )

                row_count += 1
                for column, value in zip(columns, row):
                    column.observe(value)

    except UnicodeDecodeError as error:
        raise SchemaInferenceError(
            f"{csv_path}: o arquivo não está em UTF-8: {error}"
        ) from error
    except csv.Error as error:
        raise SchemaInferenceError(
            f"{csv_path}: CSV inválido próximo à linha {reader.line_num}: {error}"
        ) from error
    except OSError as error:
        raise SchemaInferenceError(
            f"não foi possível ler {csv_path}: {error}"
        ) from error

    return TableSchema(table_name, csv_path, columns, row_count)


def inspect_directory(input_directory: Path) -> List[TableSchema]:
    tables = []
    table_names = set()

    for csv_path in discover_csv_files(input_directory):
        table = inspect_csv(csv_path)
        if table.name in table_names:
            raise SchemaInferenceError(
                f"mais de um CSV gerou o nome de tabela {table.name!r}"
            )
        table_names.add(table.name)
        tables.append(table)

    return tables


def render_create_table(table: TableSchema) -> str:
    lines = [f"CREATE TABLE {quote_identifier(table.name)} ("]
    for index, column in enumerate(table.columns):
        comma = "," if index < len(table.columns) - 1 else ""
        lines.append(
            f"    {quote_identifier(column.name)} {column.postgres_type}{comma}"
        )
    lines.append(");")
    return "\n".join(lines)


def render_schema(tables: Sequence[TableSchema]) -> str:
    statements = [
        "-- Schema inferido a partir dos arquivos CSV.",
        "-- Revisar os tipos com o dicionário de dados do ERP antes de produção.",
        "",
        "BEGIN;",
        "",
    ]

    for table in tables:
        statements.append(render_create_table(table))
        statements.append("")

    statements.append("COMMIT;")
    return "\n".join(statements) + "\n"


def write_atomic(output_path: Path, content: str) -> None:
    output_directory = output_path.parent
    if not output_directory.exists():
        raise SchemaInferenceError(
            f"diretório de saída não encontrado: {output_directory}"
        )
    if not output_directory.is_dir():
        raise SchemaInferenceError(
            f"o diretório de saída não é válido: {output_directory}"
        )

    temporary_path = None
    try:
        # O arquivo temporário evita deixar um schema incompleto se a escrita falhar.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            dir=output_directory,
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)

        os.replace(temporary_path, output_path)
        temporary_path = None
    except OSError as error:
        raise SchemaInferenceError(
            f"não foi possível escrever {output_path}: {error}"
        ) from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def generate_schema(input_directory: Path, output_path: Path) -> List[TableSchema]:
    tables = inspect_directory(input_directory)
    schema = render_schema(tables)
    write_atomic(output_path, schema)
    return tables


def parse_arguments(arguments: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera um schema PostgreSQL a partir dos CSVs de um diretório."
    )
    parser.add_argument(
        "input_directory",
        nargs="?",
        type=Path,
        default=Path("."),
        help="diretório com os CSVs (padrão: diretório atual)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("schema.sql"),
        help="arquivo SQL de saída (padrão: schema.sql)",
    )
    return parser.parse_args(arguments)


def main(arguments: Optional[Sequence[str]] = None) -> int:
    options = parse_arguments(arguments)

    try:
        tables = generate_schema(options.input_directory, options.output)
    except SchemaInferenceError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1

    for table in tables:
        for column in table.columns:
            if column.non_empty_count == 0:
                print(
                    f"Aviso: {table.source_path.name}.{column.name} não possui "
                    "valores preenchidos; tipo definido como TEXT.",
                    file=sys.stderr,
                )

    total_rows = sum(table.row_count for table in tables)
    print(
        f"Schema gerado em {options.output}: "
        f"{len(tables)} tabelas e {total_rows} registros analisados."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
