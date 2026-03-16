"""
DuckDB connection factory.
Reads db_path from config.yaml. All pipeline modules import from here.
"""
import duckdb
import yaml
from pathlib import Path


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_connection(config_path: str = "config.yaml") -> duckdb.DuckDBPyConnection:
    config = load_config(config_path)
    db_path = config["db_path"]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(db_path)
