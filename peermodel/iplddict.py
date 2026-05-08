from collections.abc import MutableMapping
import sqlite3

"""
Dict-like interface into the IPLD merkle forest, with namespace support.

"""

class NamespacedIPLDDictionary(MutableMapping):

        def __init__(self, namespace, *args, **kwargs):
            pass

        def __getitem__(self, key):
            pass

        def __setitem__(self, key, value):
            pass

        def __delitem__(self, key):
            pass

        def __iter__(self):
            pass

        def __len__(self):
            pass


class SqliteRecordManagerDictionary(MutableMapping):
    "Implements the MutableMapping interface for sqlite rows"

    def __init__(self, write_db, read_dbs=[]) -> None:
        self.write_db = sqlite3.connect(write_db)
        self.read_dbs = [sqlite3.connect(db) for db in read_dbs]
        self.memory_db = sqlite3.connect(":memory:")

        # Load all rows from all tables into memory_db
        for db in [self.write_db] + self.read_dbs:
            cursor = db.cursor()
            wcur = self.memory_db.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                for row in rows:
                    record = dict(zip(columns, row))
                    wcur.execute(f"INSERT INTO {table_name} VALUES ({', '.join(['?']*len(columns))})", tuple(record.values()))
            cursor.close()
        wcur.close()

    def __getitem__(self, key):
        cursor = self.memory_db.cursor()
        cursor.execute(f"SELECT * FROM {key[0]} WHERE _id=?", (key[1],))
        row = cursor.fetchone()
        cursor.close()
        return row
    
    def __setitem__(self, key, value):
        cursor = self.write_db.cursor()
        cursor.execute(f"INSERT INTO {key[0]} VALUES ({', '.join(['?']*len(value))})", value)
        cursor.close()

    def __delitem__(self, key):
        cursor = self.write_db.cursor()
        cursor.execute(f"DELETE FROM {key[0]} WHERE _id=?", (key[1],))
        cursor.close()

    def __iter__(self):
        cursor = self.memory_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT _id FROM {table_name}")
            rows = cursor.fetchall()
            for row in rows:
                yield table_name, row[0]
        cursor.close()

    def __len__(self):
        cursor = self.memory_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        count = 0
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count += cursor.fetchone()[0]
        cursor.close()
        return count
    
    def __repr__(self):
        return f"{self.__class__.__name__}({self.write_db}, {len(self)} records in memory)"
    
    @staticmethod
    def new_database(path, models):
        db = sqlite3.connect(path)
        cursor = db.cursor()
        for cls in models:
            cursor.execute(f"CREATE TABLE {cls.__name__} ({', '.join([f'{field.name} {field.type}' for field in fields(cls)])})")
        cursor.close()
        return db