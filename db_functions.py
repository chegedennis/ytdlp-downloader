import os
import sqlite3

database_dir = os.path.join(os.getcwd(), '.dbs')
app_database = os.path.join(os.path.join(database_dir, 'app_db.db'))


# Create the database or a database table
def create_database_or_database_table(table_name: str):
    connection = sqlite3.connect(app_database)
    cursor = connection.cursor()
    cursor.execute(f"""CREATE TABLE IF NOT EXISTS {table_name} (file_name TEXT, size TEXT, status TEXT, time_left 
    TEXT, transfer_rate TEXT)""")
    connection.commit()
    connection.close()


def add_file_to_database_table(file_name, size, status, time_left, transfer_rate, table, database=app_database):
    connection = sqlite3.connect(database)
    cursor = connection.cursor()
    info = (file_name, size, status, time_left, transfer_rate)
    cursor.execute(f""" INSERT INTO TABLE {table} VALUES (?,?,?,?,?)""", info)
    connection.commit()
    connection.close()


def delete_file_from_database(file_name, size, status, time_left, transfer_rate, table, database=app_database):
    connection = sqlite3.connect(database)
    cursor = connection.cursor()
    info = (file_name, size, status, time_left, transfer_rate)
    cursor.execute(f""" 
    DELETE FROM {table} WHERE file_name = {file_name}
""", )
    connection.commit()
    connection.close()
