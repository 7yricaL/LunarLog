import sqlite3

def initialize_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Create volunteers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS volunteers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    ''')
    
    # Create sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            volunteer_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            FOREIGN KEY(volunteer_id) REFERENCES volunteers(id)
        )
    ''')
    
    # Create current_sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS current_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            volunteer_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            FOREIGN KEY(volunteer_id) REFERENCES volunteers(id)
        )
    ''')
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    initialize_db()
