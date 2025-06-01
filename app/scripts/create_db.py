import sqlite3
import os

DATABASE_NAME = "open5e.db"
INSTANCE_FOLDER = "instance"
DATABASE_PATH = os.path.join(INSTANCE_FOLDER, DATABASE_NAME)

TABLE_CATEGORIES = [
    "manifest",
    "spells",
    "spelllist",
    "monsters",
    "documents",
    "backgrounds",
    "planes",
    "sections",
    "feats",
    "conditions",
    "races",
    "classes",
    "magicitems",
    "weapons",
    "armor",
]

def create_tables():
    """Creates the database and all necessary tables."""
    # Ensure the instance folder exists
    if not os.path.exists(INSTANCE_FOLDER):
        os.makedirs(INSTANCE_FOLDER)
        print(f"Created directory: {INSTANCE_FOLDER}")

    conn = None
    try:
        # Connect to the SQLite database (it will be created if it doesn't exist)
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        print(f"Successfully connected to database: {DATABASE_PATH}")

        # Create table for each category
        for table_name in TABLE_CATEGORIES:
            # Using TEXT for slug and making it PRIMARY KEY as it's unique and from API
            # Storing the full JSON object in 'data' column as TEXT
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                slug TEXT PRIMARY KEY NOT NULL,
                data TEXT NOT NULL
            );
            """
            cursor.execute(create_table_sql)
            print(f"Table '{table_name}' created successfully or already exists.")

        # Commit the changes
        conn.commit()
        print("Database tables created and changes committed.")

    except sqlite3.Error as e:
        print(f"Error creating tables: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    print("Running script to create database and tables...")
    create_tables()
    print("Script finished.")
