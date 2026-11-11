"""Tests for the CDM version and SQL dialect lookups behind Get_CDM_Version and Get_SQL_Dialect."""

import duckdb
import pytest

import omcp.exceptions as ex
from omcp.db import QUERY_DIALECT, OmopDatabase


def make_database(path, cdm_source_rows):
    """A DuckDB file with a `base` schema holding cdm_source and the concept it points to."""
    con = duckdb.connect(str(path))
    con.execute("CREATE SCHEMA base")
    con.execute(
        "CREATE TABLE base.cdm_source (cdm_source_name VARCHAR, cdm_version VARCHAR, "
        "cdm_version_concept_id BIGINT, vocabulary_version VARCHAR)"
    )
    con.execute("CREATE TABLE base.concept (concept_id BIGINT, concept_name VARCHAR)")
    con.execute("INSERT INTO base.concept VALUES (756265, 'OMOP CDM Version 5.4.0')")
    for row in cdm_source_rows:
        con.execute("INSERT INTO base.cdm_source VALUES (?, ?, ?, ?)", row)
    con.close()
    return OmopDatabase(f"duckdb:///{path}", cdm_schema="base", vocab_schema="base")


def test_query_dialect_is_what_read_query_translates_from():
    assert QUERY_DIALECT == "postgres"


def test_dialect_on_duckdb_is_translated(tmp_path):
    db = make_database(tmp_path / "omop.duckdb", [])
    assert db.get_sql_dialect() == {"query_dialect": "postgres", "database_dialect": "duckdb", "translated": True}


def test_dialect_on_postgres_runs_as_written(tmp_path):
    db = make_database(tmp_path / "omop.duckdb", [])
    db.target_dialect = "postgres"
    assert db.get_sql_dialect()["translated"] is False


def test_cdm_version_names_its_concept(tmp_path):
    db = make_database(tmp_path / "omop.duckdb", [("Synthea", "5.4", 756265, "v5.0 30-AUG-24")])
    assert db.get_cdm_version() == [
        {
            "cdm_source_name": "Synthea",
            "cdm_version": "5.4",
            "cdm_version_concept_id": 756265,
            "cdm_version_concept_name": "OMOP CDM Version 5.4.0",
            "vocabulary_version": "v5.0 30-AUG-24",
        }
    ]


def test_cdm_version_with_unknown_concept_has_no_name(tmp_path):
    db = make_database(tmp_path / "omop.duckdb", [("Synthea", "5.3", 123, "v5.0")])
    [row] = db.get_cdm_version()
    assert row["cdm_version"] == "5.3" and row["cdm_version_concept_name"] is None


def test_empty_cdm_source_returns_no_rows(tmp_path):
    db = make_database(tmp_path / "omop.duckdb", [])
    assert db.get_cdm_version() == []


def test_missing_cdm_source_is_a_query_error(tmp_path):
    path = tmp_path / "omop.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE SCHEMA base")
    con.close()
    db = OmopDatabase(f"duckdb:///{path}", cdm_schema="base", vocab_schema="base")
    with pytest.raises(ex.QueryError, match="cdm_source"):
        db.get_cdm_version()
