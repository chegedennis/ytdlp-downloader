"""
This module provides functions to interact with an SQLite database for managing download information.

Functions:
    create_database_or_database_table(table_name: str) -> None:
        Creates a database and a table if they do not already exist.

    add_file_to_database_table(filename: str, size: str, status: str, time_left: str, transfer_rate: str, table: str,
    database: str = app_database) -> None: Adds a file record to the specified database table.

    delete_file_from_database(filename: str, table: str, database: str = app_database) -> None:
        Deletes a file record from the specified database table based on the filename.
"""

import os
import sqlite3

# Directory and database paths
database_dir = os.path.join(os.getcwd(), ".dbs")
app_database = os.path.join(database_dir, "app_db.db")


def create_database_or_database_table(table_name: str) -> None:
    """
    Creates a database and a table if they do not already exist.

    Args:
        table_name (str): The name of the table to create.
    """
    connection = sqlite3.connect(app_database)
    cursor = connection.cursor()
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
    connection.commit()
    connection.close()


def add_file_to_database_table(
    filename: str,
    size: str,
    status: str,
    time_left: str,
    transfer_rate: str,
    table: str,
    database: str = app_database,
) -> None:
    """
    Adds a file record to the specified database table.

    Args:
        filename (str): The name of the file.
        size (str): The size of the file.
        status (str): The status of the download.
        time_left (str): The time left for the download.
        transfer_rate (str): The transfer rate of the download.
        table (str): The name of the table to add the record to.
        database (str, optional): The path to the database. Defaults to app_database.
    """
    connection = sqlite3.connect(database)
    cursor = connection.cursor()
    info = (filename, size, status, time_left, transfer_rate)
    cursor.execute(
        f"""
    INSERT INTO {table} (filename, file_size, status, time_left, transfer_rate) 
    VALUES (?, ?, ?, ?, ?)
    """,
        info,
    )
    connection.commit()
    connection.close()


def delete_file_from_database(
    filename: str, table: str, database: str = app_database
) -> None:
    """
    Deletes a file record from the specified database table based on the filename.

    Args:
        filename (str): The name of the file to delete.
        table (str): The name of the table to delete the record from.
        database (str, optional): The path to the database. Defaults to app_database.
    """
    connection = sqlite3.connect(database)
    cursor = connection.cursor()
    cursor.execute(
        f"""
    DELETE FROM {table} 
    WHERE filename = ?
    """,
        (filename,),
    )
    connection.commit()
    connection.close()
