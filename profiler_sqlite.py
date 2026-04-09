import sqlite3
import json
from concurrent.futures import ThreadPoolExecutor


class BaseConnector:
    def list_tables(self):
        raise NotImplementedError

    def get_schema(self, table):
        raise NotImplementedError

    def get_row_count(self, table):
        raise NotImplementedError

    def profile_column(self, table, column, config):
        raise NotImplementedError


class SQLiteConnector(BaseConnector):
    def __init__(self, path):
        self.conn = sqlite3.connect(path, check_same_thread=False)

    def list_tables(self):
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        )
        return [r[0] for r in cur.fetchall()]

    def get_schema(self, table):
        cur = self.conn.execute(f"PRAGMA table_info({table});")
        return [
            {
                "name": r[1],
                "type": r[2],
                "nullable": not r[3]
            }
            for r in cur.fetchall()
        ]

    def get_row_count(self, table):
        cur = self.conn.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]

    def profile_column(self, table, column, config):
        query = f"""
        SELECT
            MIN({column}),
            MAX({column}),
            COUNT(DISTINCT {column}),
            SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END)
        FROM {table}
        """
        cur = self.conn.execute(query)
        row = cur.fetchone()

        return {
            "min": row[0],
            "max": row[1],
            "distinct_count": row[2],
            "null_count": row[3]
        }


class Profiler:
    def __init__(self, connector, config):
        self.connector = connector
        self.config = config

    def map_type(self, physical):
        p = physical.upper()
        if "INT" in p:
            return "integer"
        if "CHAR" in p or "TEXT" in p:
            return "string"
        if "REAL" in p or "FLOA" in p or "DOUB" in p:
            return "float"
        return "unknown"

    def profile_table(self, table):
        schema = self.connector.get_schema(table)
        row_count = self.connector.get_row_count(table)

        columns = []
        for col in schema:
            stats = self.connector.profile_column(
                table, col["name"], self.config
            )
            columns.append({
                "name": col["name"],
                "physical_type": col["type"],
                "logical_type": self.map_type(col["type"]),
                "nullable": col["nullable"],
                "stats": stats
            })

        return {
            "table_name": table,
            "row_count": row_count,
            "columns": columns
        }

    def run(self):
        tables = self.connector.list_tables()
        results = []

        with ThreadPoolExecutor(max_workers=self.config.get("max_workers", 4)) as ex:
            results = list(ex.map(self.profile_table, tables))

        return results


class StateManager:
    def __init__(self, path):
        self.path = path
        try:
            with open(path) as f:
                self.state = json.load(f)
        except:
            self.state = {}

    def save_table(self, table, result):
        self.state[table] = result
        with open(self.path, "w") as f:
            json.dump(self.state, f, indent=2, default=str)


def write_output(results, path):
    with open(path, "w") as f:
        json.dump(results, f, indent=2, default=str)


if __name__ == "__main__":
    config = {
        "max_workers": 4
    }

    connector = SQLiteConnector("example.db")
    profiler = Profiler(connector, config)

    results = profiler.run()

    write_output(results, "profile_output.json")
