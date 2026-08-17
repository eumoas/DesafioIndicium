#!/usr/bin/env python3
"""Carrega os CSVs em tabelas PostgreSQL já criadas."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:  # A mensagem amigável é exibida apenas ao executar o script.
    psycopg2 = None
    sql = None


POSTGRES_ERRORS = (psycopg2.Error,) if psycopg2 is not None else ()


POSTGRES_IDENTIFIER_MAX_BYTES = 63
DEFAULT_DATABASE_SCHEMA = "public"
DATABASE_URL_ENVIRONMENT_VARIABLE = "LH_NAUTICAL_DATABASE_URL"


class LoadError(Exception):
    """Erro esperado durante a validação ou o carregamento."""


@dataclass(frozen=True)
class CsvSource:
    path: Path
    table_name: str
    columns: List[str]
    row_count: int


def validate_identifier(identifier: str, context: str) -> None:
    if not identifier or not identifier.strip():
        raise LoadError(f"{context}: identificador vazio")

    if any(ord(character) < 32 or ord(character) == 127 for character in identifier):
        raise LoadError(f"{context}: identificador possui caractere de controle")

    identifier_size = len(identifier.encode("utf-8"))
    if identifier_size > POSTGRES_IDENTIFIER_MAX_BYTES:
        raise LoadError(
            f"{context}: identificador possui {identifier_size} bytes; "
            f"o limite padrão do PostgreSQL é {POSTGRES_IDENTIFIER_MAX_BYTES}"
        )


def discover_csv_files(input_directory: Path) -> List[Path]:
    if not input_directory.exists():
        raise LoadError(f"diretório não encontrado: {input_directory}")
    if not input_directory.is_dir():
        raise LoadError(f"o caminho não é um diretório: {input_directory}")

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
        raise LoadError(
            f"não foi possível listar o diretório {input_directory}: {error}"
        ) from error

    if not csv_files:
        raise LoadError(f"nenhum CSV encontrado em {input_directory}")
    return csv_files


def inspect_csv(csv_path: Path) -> CsvSource:
    table_name = csv_path.stem
    validate_identifier(table_name, f"arquivo {csv_path.name}")
    reader = None

    try:
        with csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.reader(csv_file, strict=True)
            try:
                header = next(reader)
            except StopIteration as error:
                raise LoadError(f"{csv_path}: arquivo vazio") from error

            if not header:
                raise LoadError(f"{csv_path}: cabeçalho vazio")

            seen_columns = set()
            for column_name in header:
                validate_identifier(
                    column_name,
                    f"arquivo {csv_path.name}, coluna do cabeçalho",
                )
                if column_name in seen_columns:
                    raise LoadError(
                        f"{csv_path}: coluna duplicada no cabeçalho: {column_name!r}"
                    )
                seen_columns.add(column_name)

            row_count = 0
            # Esta leitura só valida o arquivo. Os valores não são alterados nem
            # guardados em memória; o COPY reabre o CSV original depois.
            for row in reader:
                if len(row) != len(header):
                    raise LoadError(
                        f"{csv_path}: linha {reader.line_num} possui "
                        f"{len(row)} campos; eram esperados {len(header)}"
                    )
                row_count += 1

    except UnicodeDecodeError as error:
        raise LoadError(f"{csv_path}: o arquivo não está em UTF-8: {error}") from error
    except csv.Error as error:
        line_number = reader.line_num if reader is not None else "desconhecida"
        raise LoadError(
            f"{csv_path}: CSV inválido próximo à linha {line_number}: {error}"
        ) from error
    except OSError as error:
        raise LoadError(f"não foi possível ler {csv_path}: {error}") from error

    return CsvSource(csv_path, table_name, header, row_count)


def inspect_sources(input_directory: Path) -> List[CsvSource]:
    sources = []
    table_names = set()

    for csv_path in discover_csv_files(input_directory):
        source = inspect_csv(csv_path)
        if source.table_name in table_names:
            raise LoadError(f"mais de um CSV gerou a tabela {source.table_name!r}")
        table_names.add(source.table_name)
        sources.append(source)

    return sources


def get_database_columns(cursor, database_schema: str, table_name: str) -> List[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (database_schema, table_name),
    )
    return [row[0] for row in cursor.fetchall()]


def validate_database_schema(
    cursor,
    sources: Sequence[CsvSource],
    database_schema: str,
) -> None:
    for source in sources:
        database_columns = get_database_columns(
            cursor,
            database_schema,
            source.table_name,
        )

        if not database_columns:
            raise LoadError(
                f"tabela {database_schema}.{source.table_name} não encontrada "
                "ou sem permissão de leitura no catálogo"
            )

        if database_columns != source.columns:
            raise LoadError(
                f"colunas de {source.path.name} não correspondem à tabela "
                f"{database_schema}.{source.table_name}. "
                f"CSV: {source.columns}; banco: {database_columns}"
            )


def lock_target_tables(
    cursor,
    sources: Sequence[CsvSource],
    database_schema: str,
) -> None:
    ordered_sources = sorted(
        sources,
        key=lambda source: (source.table_name.casefold(), source.table_name),
    )
    tables = sql.SQL(", ").join(
        sql.Identifier(database_schema, source.table_name) for source in ordered_sources
    )
    cursor.execute(sql.SQL("LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE").format(tables))


def table_has_rows(cursor, database_schema: str, table_name: str) -> bool:
    statement = sql.SQL("SELECT EXISTS (SELECT 1 FROM {} LIMIT 1)").format(
        sql.Identifier(database_schema, table_name)
    )
    cursor.execute(statement)
    return bool(cursor.fetchone()[0])


def ensure_target_tables_are_empty(
    cursor,
    sources: Sequence[CsvSource],
    database_schema: str,
) -> None:
    non_empty_tables = [
        source.table_name
        for source in sources
        if table_has_rows(cursor, database_schema, source.table_name)
    ]
    if non_empty_tables:
        tables = ", ".join(non_empty_tables)
        raise LoadError(
            f"as tabelas a seguir já possuem dados: {tables}. "
            "A carga foi cancelada para evitar duplicação; use --replace "
            "somente se desejar substituir todo o conteúdo."
        )


def truncate_target_tables(
    cursor,
    sources: Sequence[CsvSource],
    database_schema: str,
) -> None:
    tables = sql.SQL(", ").join(
        sql.Identifier(database_schema, source.table_name) for source in sources
    )
    cursor.execute(sql.SQL("TRUNCATE TABLE {}").format(tables))


def build_copy_statement(source: CsvSource, database_schema: str):
    columns = sql.SQL(", ").join(sql.Identifier(name) for name in source.columns)
    return sql.SQL(
        "COPY {} ({}) FROM STDIN "
        "WITH (FORMAT CSV, HEADER TRUE, DELIMITER ',', "
        "QUOTE '\"', ESCAPE '\"', NULL '', ENCODING 'UTF8')"
    ).format(
        sql.Identifier(database_schema, source.table_name),
        columns,
    )


def format_database_error(error) -> str:
    diagnostic = getattr(error, "diag", None)
    primary_message = getattr(diagnostic, "message_primary", None)
    context = getattr(diagnostic, "context", None)

    # O contexto do COPY costuma trazer também o conteúdo rejeitado. A linha e
    # a coluna ajudam no diagnóstico, mas o valor pode ser um dado pessoal.
    if context and context.lstrip().startswith("COPY "):
        copy_location = context.split(":", 1)[0]
        safe_primary_message = (
            primary_message.split(":", 1)[0] if primary_message else None
        )
        details = [detail for detail in (safe_primary_message, copy_location) if detail]
    else:
        details = [detail for detail in (primary_message, context) if detail]

    if details:
        return " | ".join(details)
    fallback_message = str(error).strip()
    if fallback_message:
        return fallback_message.splitlines()[0]
    return error.__class__.__name__


def copy_source(cursor, source: CsvSource, database_schema: str) -> None:
    statement = build_copy_statement(source, database_schema)

    try:
        # newline="" mantém a estrutura CSV e utf-8-sig também aceita um BOM.
        with source.path.open(encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.reader(csv_file, strict=True)
            try:
                current_header = next(reader)
            except StopIteration as error:
                raise LoadError(
                    f"{source.path}: o arquivo ficou vazio após a validação"
                ) from error

            if current_header != source.columns:
                raise LoadError(
                    f"{source.path}: o cabeçalho mudou após a validação; "
                    "a carga foi cancelada"
                )

            csv_file.seek(0)
            cursor.copy_expert(statement, csv_file)
    except UnicodeDecodeError as error:
        raise LoadError(
            f"{source.path}: o arquivo mudou e não está mais em UTF-8: {error}"
        ) from error
    except OSError as error:
        raise LoadError(f"não foi possível ler {source.path}: {error}") from error
    except csv.Error as error:
        raise LoadError(
            f"{source.path}: o cabeçalho mudou ou ficou inválido: {error}"
        ) from error
    except POSTGRES_ERRORS as error:
        raise LoadError(
            f"falha ao carregar {source.path.name}: {format_database_error(error)}"
        ) from error


def get_table_row_count(cursor, database_schema: str, table_name: str) -> int:
    statement = sql.SQL("SELECT COUNT(*) FROM {}").format(
        sql.Identifier(database_schema, table_name)
    )
    cursor.execute(statement)
    return int(cursor.fetchone()[0])


def load_sources(
    connection,
    sources: Sequence[CsvSource],
    database_schema: str,
    replace: bool = False,
) -> int:
    connection.set_client_encoding("UTF8")

    # A transação inclui todas as tabelas. Qualquer falha desfaz o lote inteiro.
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL DateStyle TO 'ISO, YMD'")
            # O lock impede que duas execuções vejam as tabelas vazias e
            # carreguem o mesmo snapshot ao mesmo tempo.
            lock_target_tables(cursor, sources, database_schema)
            validate_database_schema(cursor, sources, database_schema)

            if replace:
                truncate_target_tables(cursor, sources, database_schema)
            else:
                ensure_target_tables_are_empty(cursor, sources, database_schema)

            loaded_rows = 0
            for source in sources:
                print(
                    f"Carregando {source.path.name} em "
                    f"{database_schema}.{source.table_name} "
                    f"({source.row_count} registros)..."
                )
                copy_source(cursor, source, database_schema)

                database_row_count = get_table_row_count(
                    cursor,
                    database_schema,
                    source.table_name,
                )
                if database_row_count != source.row_count:
                    raise LoadError(
                        f"contagem divergente em {database_schema}."
                        f"{source.table_name}: CSV={source.row_count}, "
                        f"banco={database_row_count}"
                    )
                loaded_rows += database_row_count

    return loaded_rows


def connect_to_database(dsn: str):
    if psycopg2 is None:
        raise LoadError(
            "psycopg2 não está instalado. Instale com: "
            "python3 -m pip install psycopg2-binary"
        )

    try:
        return psycopg2.connect(dsn)
    except POSTGRES_ERRORS as error:
        raise LoadError(
            f"não foi possível conectar ao PostgreSQL: "
            f"{format_database_error(error)}"
        ) from error


def parse_arguments(arguments: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Carrega todos os CSVs em tabelas PostgreSQL já existentes."
    )
    parser.add_argument(
        "input_directory",
        nargs="?",
        type=Path,
        default=Path("."),
        help="diretório com os CSVs (padrão: diretório atual)",
    )
    parser.add_argument(
        "--dsn",
        help=(
            "string de conexão PostgreSQL; se omitida, usa "
            f"{DATABASE_URL_ENVIRONMENT_VARIABLE} ou variáveis PG*"
        ),
    )
    parser.add_argument(
        "--db-schema",
        default=DEFAULT_DATABASE_SCHEMA,
        help=f"schema de destino (padrão: {DEFAULT_DATABASE_SCHEMA})",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help=(
            "esvazia todas as tabelas alvo na mesma transação antes da carga; "
            "sem esta opção, tabelas não vazias cancelam a execução"
        ),
    )
    return parser.parse_args(arguments)


def main(arguments: Optional[Sequence[str]] = None) -> int:
    options = parse_arguments(arguments)

    try:
        validate_identifier(options.db_schema, "schema de destino")
        sources = inspect_sources(options.input_directory)

        dsn = options.dsn
        if dsn is None:
            dsn = os.environ.get(DATABASE_URL_ENVIRONMENT_VARIABLE, "")

        connection = connect_to_database(dsn)
        try:
            loaded_rows = load_sources(
                connection,
                sources,
                options.db_schema,
                replace=options.replace,
            )
        finally:
            connection.close()

    except LoadError as error:
        print(f"Erro: {error}", file=sys.stderr)
        print(
            "Nenhuma alteração desta execução foi confirmada.",
            file=sys.stderr,
        )
        return 1
    except POSTGRES_ERRORS as error:
        print(f"Erro do PostgreSQL: {format_database_error(error)}", file=sys.stderr)
        print(
            "Nenhuma alteração desta execução foi confirmada.",
            file=sys.stderr,
        )
        return 1

    print(
        f"Carga concluída: {len(sources)} tabelas e "
        f"{loaded_rows} registros carregados."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
