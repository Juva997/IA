#!/usr/bin/env python3
"""
Script PoC para migrar dados de um arquivo SQLite para um banco PostgreSQL.

Uso:
  python migrate.py --sqlite /path/to/db.sqlite --pg "postgresql://user:pass@host:5432/dbname" [--batch-size 1000]

Aviso: este é um utilitário PoC. Teste em ambiente de desenvolvimento antes
de executar em produção.
"""
import argparse
import sqlite3
import re
import sys


def map_type(sqlite_type: str) -> str:
    if not sqlite_type:
        return "TEXT"
    t = sqlite_type.strip().upper()
    if "INT" in t:
        return "BIGINT"
    if "CHAR" in t or "CLOB" in t or "TEXT" in t:
        return "TEXT"
    if "BLOB" in t:
        return "BYTEA"
    if "REAL" in t or "FLOA" in t or "DOUB" in t:
        return "DOUBLE PRECISION"
    # fallback
    return "TEXT"


def quote_ident(name: str) -> str:
    # simples escape para identificação SQL do Postgres
    return '"' + name.replace('"', '""') + '"'


def migrate(sqlite_path: str, pg_dsn: str, batch_size: int = 1000):
    try:
        import psycopg2
        import psycopg2.extras as pg_extras
    except Exception as e:
        print("psycopg2 não instalado:", e)
        sys.exit(1)

    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row
    cur = src.cursor()

    # listar tabelas (ignorar objetos internos)
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [r[0] for r in cur.fetchall()]

    if not tables:
        print("Nenhuma tabela encontrada no banco SQLite.")
        return

    pg_conn = psycopg2.connect(pg_dsn)
    pg_cur = pg_conn.cursor()

    for table in tables:
        print(f"Migrando tabela: {table}")
        cur.execute(f"PRAGMA table_info('{table}')")
        cols = cur.fetchall()  # cid, name, type, notnull, dflt_value, pk
        if not cols:
            print(f"  (ignorar tabela vazia: {table})")
            continue

        col_defs = []
        col_names = []
        for c in cols:
            name = c[1]
            ctype = c[2]
            notnull = c[3]
            mapped = map_type(ctype)
            null_sql = "NOT NULL" if notnull else ""
            col_defs.append(f"{quote_ident(name)} {mapped} {null_sql}")
            col_names.append(name)

        create_sql = f"CREATE TABLE IF NOT EXISTS {quote_ident(table)} ({', '.join(col_defs)});"
        pg_cur.execute(create_sql)
        pg_conn.commit()

        # copiar dados em lotes
        select_sql = f"SELECT {', '.join([quote_ident(n) for n in col_names])} FROM {quote_ident(table)}"
        src_cur = src.cursor()
        src_cur.execute(select_sql)

        insert_sql = f"INSERT INTO {quote_ident(table)} ({', '.join([quote_ident(n) for n in col_names])}) VALUES %s"
        from psycopg2.extras import execute_values

        rows_copied = 0
        while True:
            batch = src_cur.fetchmany(batch_size)
            if not batch:
                break
            # converter Row objects para tuplas
            values = [tuple(r) for r in batch]
            try:
                execute_values(pg_cur, insert_sql, values)
                pg_conn.commit()
                rows_copied += len(values)
            except Exception as e:
                pg_conn.rollback()
                print(f"  Erro ao inserir lote na tabela {table}: {e}")
                # tentar inserir linha-a-linha como fallback
                for v in values:
                    try:
                        pg_cur.execute(insert_sql.replace(" %s", "(%s)"), (v,))
                        pg_conn.commit()
                        rows_copied += 1
                    except Exception:
                        pg_conn.rollback()
                        print(f"    falha na linha: {v}")

        print(f"  {rows_copied} linhas copiadas para {table}")

    pg_cur.close()
    pg_conn.close()
    src.close()


def main():
    parser = argparse.ArgumentParser(description="Migrar SQLite para Postgres (PoC)")
    parser.add_argument("--sqlite", required=True, help="Caminho para o arquivo sqlite (.db)")
    parser.add_argument("--pg", required=True, help="DSN Postgres, ex: postgresql://user:pass@host:5432/dbname")
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()

    migrate(args.sqlite, args.pg, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
