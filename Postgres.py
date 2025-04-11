import os
import psycopg2
import numpy as np
from datetime import datetime
import pytz

# Database Connection Parameters
# DB_PARAMS = {
#     "dbname": "docze",
#     "user": "docze",
#     "password": "docze123",
#     "host": "localhost",  # or the container name if you're inside another container
#     "port": "5432"
# }
DB_PARAMS = {
    "dbname": "b9jyxdclhovva7tmepet",
    "user": "uft7opwwglviqezcljox",
    "password": "4TSIIJFnRnmdE5S7lk1tgbem2grZ2U",
    "host": "b9jyxdclhovva7tmepet-postgresql.services.clever-cloud.com",  # or the container name if you're inside another container
    "port": "50013"
}

# Utility to get DB connection
def get_connection():
    return psycopg2.connect(**DB_PARAMS)

# Initialize Database
def init_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                password TEXT UNIQUE NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_embeddings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                filename TEXT,
                embedding BYTEA,
                text_snippet TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                newchat_id TEXT,
                embedding BYTEA,
                message TEXT,
                role TEXT CHECK(role IN ('user', 'assistant'))
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_storage (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                file_name TEXT,
                file_type TEXT,
                file_size INTEGER,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used_space INTEGER DEFAULT 0,
                file_path TEXT
            )
        """)
        conn.commit()
    except psycopg2.Error as e:
        print(f"Database initialization error: {e}")
    finally:
        conn.close()

# User Operations
def register_user(username, password):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        conn.commit()
        return True, None
    except psycopg2.IntegrityError:
        return False, "Password already exists"
    except psycopg2.Error as e:
        return False, f"Database error: {e}"
    finally:
        conn.close()

def get_user_by_password(password):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username, id FROM users WHERE password = %s", (password,))
        return cursor.fetchone()
    except psycopg2.Error as e:
        print(f"Error getting user by password: {e}")
        return None
    finally:
        conn.close()

def get_username(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except psycopg2.Error as e:
        print(f"Error getting username: {e}")
        return None
    finally:
        conn.close()

# Chat Operations
def store_chat_embedding(user_id, newchat_id, message, role, embedding):
    try:
        embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO chat_history (user_id, newchat_id, embedding, message, role)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, newchat_id, psycopg2.Binary(embedding_blob), message, role))
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error storing chat embedding: {e}")
    finally:
        conn.close()

def get_chat_history(user_id, chat_id=None):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        if chat_id:
            cursor.execute("""
                SELECT message, role FROM chat_history
                WHERE user_id = %s AND newchat_id = %s
                ORDER BY id ASC
            """, (user_id, chat_id))
        else:
            cursor.execute("""
                SELECT DISTINCT newchat_id FROM chat_history
                WHERE user_id = %s
            """, (user_id,))
            chat_ids = [row[0] for row in cursor.fetchall()]
            chat_data = {}
            for cid in chat_ids:
                cursor.execute("""
                    SELECT message, role FROM chat_history
                    WHERE user_id = %s AND newchat_id = %s
                    ORDER BY id ASC
                """, (user_id, cid))
                chat_data[cid] = [{"role": row[1], "content": row[0]} for row in cursor.fetchall()]
            return chat_data
        return [{"role": row[1], "content": row[0]} for row in cursor.fetchall()]
    except psycopg2.Error as e:
        print(f"Error getting chat history: {e}")
        return None
    finally:
        conn.close()

def get_recent_chat_embeddings(user_id, chat_id, limit=50):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT message, embedding FROM chat_history
            WHERE user_id = %s AND newchat_id = %s
            ORDER BY id DESC LIMIT %s
        """, (user_id, chat_id, limit))
        return cursor.fetchall()
    except psycopg2.Error as e:
        print(f"Error getting recent chat embeddings: {e}")
        return []
    finally:
        conn.close()

# Document Operations
def store_document_embedding(user_id, filename, text_snippet, embedding):
    try:
        embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO document_embeddings (user_id, filename, embedding, text_snippet)
            VALUES (%s, %s, %s, %s)
        """, (user_id, filename, psycopg2.Binary(embedding_blob), text_snippet))
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error storing document embedding: {e}")
    finally:
        conn.close()

def get_document_embeddings(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT text_snippet, embedding FROM document_embeddings
            WHERE user_id = %s
        """, (user_id,))
        return cursor.fetchall()
    except psycopg2.Error as e:
        print(f"Error getting document embeddings: {e}")
        return []
    finally:
        conn.close()

# File Storage Operations
def store_file_metadata(user_id, file_name, file_type, file_size, file_path):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(file_size) FROM user_storage WHERE user_id = %s", (user_id,))
        current_used_space = cursor.fetchone()[0] or 0
        new_used_space = current_used_space + file_size
        ist = pytz.timezone('Asia/Kolkata')
        ist_time = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            INSERT INTO user_storage (user_id, file_name, file_type, file_size, uploaded_at, used_space, file_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_id, file_name, file_type, file_size, ist_time, new_used_space, file_path))
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error storing file metadata: {e}")
    finally:
        conn.close()

def get_user_files(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT file_name, file_type, uploaded_at, file_path
            FROM user_storage
            WHERE user_id = %s
        """, (user_id,))
        return [{
            "file_name": row[0],
            "file_type": row[1],
            "uploaded_at": row[2],
            "file_path": row[3]
        } for row in cursor.fetchall()]
    except psycopg2.Error as e:
        print(f"Error getting user files: {e}")
        return []
    finally:
        conn.close()

def get_existing_files(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT file_name, file_size FROM user_storage
            WHERE user_id = %s
        """, (user_id,))
        return {row[0]: row[1] for row in cursor.fetchall()}
    except psycopg2.Error as e:
        print(f"Error getting existing files: {e}")
        return {}
    finally:
        conn.close()

def delete_file(user_id, file_name):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM user_storage
            WHERE user_id = %s AND file_name = %s
        """, (user_id, file_name))
        cursor.execute("""
            DELETE FROM document_embeddings
            WHERE user_id = %s AND filename = %s
        """, (user_id, file_name))
        conn.commit()
        return True
    except psycopg2.Error as e:
        print(f"Error deleting file: {e}")
        return False
    finally:
        conn.close()

def get_used_storage(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT SUM(file_size) FROM user_storage
            WHERE user_id = %s
        """, (user_id,))
        result = cursor.fetchone()
        return result[0] or 0
    except psycopg2.Error as e:
        print(f"Error getting used storage: {e}")
        return 0
    finally:
        conn.close()

# Initialize DB
init_db()
