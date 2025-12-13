"""
db_functions.py
SQLite handling for the YouTube Downloader.
"""

import os
import sqlite3

DATABASE_DIR = os.path.join(os.getcwd(), ".dbs")
APP_DATABASE = os.path.join(DATABASE_DIR, "app_db.db")


def create_db_dir():
    os.makedirs(DATABASE_DIR, exist_ok=True)


def create_database_or_database_table(table_name: str) -> None:
    with sqlite3.connect(APP_DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_size TEXT NOT NULL,
            status TEXT NOT NULL,
            time_left TEXT,
            transfer_rate TEXT
        );
        """
        )


def fetch_entries_from_database(table_name: str):
    try:
        with sqlite3.connect(APP_DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name}")
            return cursor.fetchall()
    except sqlite3.OperationalError:
        return []


def add_file_to_database_table(filename, size, status, time_left, transfer_rate, table):
    with sqlite3.connect(APP_DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
        INSERT INTO {table} (filename, file_size, status, time_left, transfer_rate) 
        VALUES (?, ?, ?, ?, ?)
        """,
            (filename, size, status, time_left, transfer_rate),
        )


def delete_files_from_database(filenames, table):
    with sqlite3.connect(APP_DATABASE) as conn:
        cursor = conn.cursor()
        cursor.executemany(
            f"DELETE FROM {table} WHERE filename = ?", [(f,) for f in filenames]
        )
