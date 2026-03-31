import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Проверяем, запущены ли мы на Render (есть переменная DATABASE_URL)
DATABASE_URL = os.getenv('DATABASE_URL')
IS_RENDER = bool(DATABASE_URL)

class Database:
    def __init__(self):
        self.conn = None
        self.is_postgres = IS_RENDER
        self.init_db()
    
    def init_db(self):
        if self.is_postgres:
            self.connect_postgres()
        else:
            self.connect_sqlite()
    
    # ========== POSTGRESQL (Render/Supabase) ==========
    
    def connect_postgres(self):
        """Подключение к PostgreSQL (Supabase)"""
        self.conn = psycopg2.connect(DATABASE_URL)
        self.create_tables_postgres()
        self.add_sample_categories_postgres()
        self.add_admin_to_allowed_postgres()
        self.add_main_admin_postgres()
    
    def create_tables_postgres(self):
        with self.conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT
                )
            ''')
            
            cur.execute('''
                CREATE TABLE IF NOT EXISTS videos (
                    id SERIAL PRIMARY KEY,
                    category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    duration INTEGER,
                    created_at TIMESTAMP
                )
            ''')
            
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    registered_at TIMESTAMP
                )
            ''')
            
            cur.execute('''
                CREATE TABLE IF NOT EXISTS allowed_users (
                    user_id BIGINT PRIMARY KEY,
                    added_at TIMESTAMP,
                    added_by BIGINT
                )
            ''')
            
            cur.execute('''
                CREATE TABLE IF NOT EXISTS access_requests (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    message TEXT,
                    status TEXT DEFAULT 'pending',
                    requested_at TIMESTAMP,
                    processed_at TIMESTAMP,
                    processed_by BIGINT
                )
            ''')
            
            cur.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    user_id BIGINT PRIMARY KEY,
                    added_at TIMESTAMP,
                    added_by BIGINT
                )
            ''')
            self.conn.commit()
    
    def add_sample_categories_postgres(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM categories")
            count = cur.fetchone()[0]
            if count == 0:
                categories = [
                    ("Python для начинающих", "Базовый курс по Python"),
                    ("Веб-разработка", "Django и Flask"),
                    ("Data Science", "Анализ данных и ML"),
                    ("Мобильная разработка", "Kotlin и Swift")
                ]
                for name, desc in categories:
                    cur.execute(
                        "INSERT INTO categories (name, description) VALUES (%s, %s)",
                        (name, desc)
                    )
                self.conn.commit()
    
    def add_admin_to_allowed_postgres(self):
        from config import ADMIN_ID
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO allowed_users (user_id, added_at, added_by) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (ADMIN_ID, datetime.now(), ADMIN_ID)
            )
            self.conn.commit()
    
    def add_main_admin_postgres(self):
        from config import ADMIN_ID
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO admins (user_id, added_at, added_by) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (ADMIN_ID, datetime.now(), ADMIN_ID)
            )
            self.conn.commit()
    
    # ========== SQLITE (локальная разработка) ==========
    
    def connect_sqlite(self):
        """Подключение к SQLite (локально)"""
        self.conn = sqlite3.connect('videos.db', check_same_thread=False)
        self.create_tables_sqlite()
        self.add_sample_categories_sqlite()
        self.add_admin_to_allowed_sqlite()
        self.add_main_admin_sqlite()
    
    def create_tables_sqlite(self):
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER,
                title TEXT NOT NULL,
                file_id TEXT NOT NULL,
                duration INTEGER,
                created_at TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                registered_at TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS allowed_users (
                user_id INTEGER PRIMARY KEY,
                added_at TIMESTAMP,
                added_by INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS access_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                message TEXT,
                status TEXT DEFAULT 'pending',
                requested_at TIMESTAMP,
                processed_at TIMESTAMP,
                processed_by INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_at TIMESTAMP,
                added_by INTEGER
            )
        ''')
        
        self.conn.commit()
    
    def add_sample_categories_sqlite(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM categories")
        count = cursor.fetchone()[0]
        
        if count == 0:
            categories = [
                ("Python для начинающих", "Базовый курс по Python"),
                ("Веб-разработка", "Django и Flask"),
                ("Data Science", "Анализ данных и ML"),
                ("Мобильная разработка", "Kotlin и Swift")
            ]
            cursor.executemany("INSERT INTO categories (name, description) VALUES (?, ?)", categories)
            self.conn.commit()
    
    def add_admin_to_allowed_sqlite(self):
        from config import ADMIN_ID
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO allowed_users (user_id, added_at, added_by) VALUES (?, ?, ?)",
            (ADMIN_ID, datetime.now(), ADMIN_ID)
        )
        self.conn.commit()
    
    def add_main_admin_sqlite(self):
        from config import ADMIN_ID
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO admins (user_id, added_at, added_by) VALUES (?, ?, ?)",
            (ADMIN_ID, datetime.now(), ADMIN_ID)
        )
        self.conn.commit()
    
    # ========== ОБЩИЕ МЕТОДЫ ==========
    
    def get_categories(self):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id, name, description FROM categories ORDER BY id")
                return cur.fetchall()
        else:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, name, description FROM categories")
            return cursor.fetchall()
    
    def get_category(self, category_id):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id, name, description FROM categories WHERE id = %s", (category_id,))
                return cur.fetchone()
        else:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, name, description FROM categories WHERE id = ?", (category_id,))
            return cursor.fetchone()
    
    def get_videos_by_category(self, category_id):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT id, title, file_id, duration FROM videos WHERE category_id = %s ORDER BY id",
                    (category_id,)
                )
                return cur.fetchall()
        else:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, title, file_id, duration FROM videos WHERE category_id = ?", (category_id,))
            return cursor.fetchall()
    
    def get_videos_count_by_category(self, category_id):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM videos WHERE category_id = %s", (category_id,))
                return cur.fetchone()[0]
        else:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM videos WHERE category_id = ?", (category_id,))
            return cursor.fetchone()[0]
    
    def add_video(self, category_id, title, file_id, duration=None):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO videos (category_id, title, file_id, duration, created_at) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (category_id, title, file_id, duration, datetime.now())
                )
                self.conn.commit()
                return cur.fetchone()[0]
        else:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO videos (category_id, title, file_id, duration, created_at) VALUES (?, ?, ?, ?, ?)",
                (category_id, title, file_id, duration, datetime.now())
            )
            self.conn.commit()
            return cursor.lastrowid
    
    def add_user(self, user_id, username, first_name, last_name):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (user_id, username, first_name, last_name, registered_at) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (user_id, username, first_name, last_name, datetime.now())
                )
                self.conn.commit()
        else:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, registered_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, first_name, last_name, datetime.now())
            )
            self.conn.commit()
    
    def update_category(self, category_id, new_name, new_description=None):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                if new_description is not None:
                    cur.execute(
                        "UPDATE categories SET name = %s, description = %s WHERE id = %s",
                        (new_name, new_description, category_id)
                    )
                else:
                    cur.execute(
                        "UPDATE categories SET name = %s WHERE id = %s",
                        (new_name, category_id)
                    )
                self.conn.commit()
                return cur.rowcount > 0
        else:
            cursor = self.conn.cursor()
            if new_description is not None:
                cursor.execute(
                    "UPDATE categories SET name = ?, description = ? WHERE id = ?",
                    (new_name, new_description, category_id)
                )
            else:
                cursor.execute(
                    "UPDATE categories SET name = ? WHERE id = ?",
                    (new_name, category_id)
                )
            self.conn.commit()
            return cursor.rowcount > 0
    
    def delete_category(self, category_id):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM videos WHERE category_id = %s", (category_id,))
                cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))
                self.conn.commit()
                return cur.rowcount > 0
        else:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM videos WHERE category_id = ?", (category_id,))
            cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            self.conn.commit()
            return cursor.rowcount > 0
    
    def is_user_allowed(self, user_id):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM allowed_users WHERE user_id = %s", (user_id,))
                return cur.fetchone()[0] > 0
        else:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM allowed_users WHERE user_id = ?", (user_id,))
            return cursor.fetchone()[0] > 0
    
    def add_allowed_user(self, user_id, added_by):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO allowed_users (user_id, added_at, added_by) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (user_id, datetime.now(), added_by)
                )
                self.conn.commit()
                return cur.rowcount > 0
        else:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO allowed_users (user_id, added_at, added_by) VALUES (?, ?, ?)",
                (user_id, datetime.now(), added_by)
            )
            self.conn.commit()
            return cursor.rowcount > 0
    
    def remove_allowed_user(self, user_id):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM allowed_users WHERE user_id = %s", (user_id,))
                self.conn.commit()
                return cur.rowcount > 0
        else:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM allowed_users WHERE user_id = ?", (user_id,))
            self.conn.commit()
            return cursor.rowcount > 0
    
    def get_allowed_users(self):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute("SELECT user_id, added_at, added_by FROM allowed_users ORDER BY added_at")
                return cur.fetchall()
        else:
            cursor = self.conn.cursor()
            cursor.execute("SELECT user_id, added_at, added_by FROM allowed_users ORDER BY added_at")
            return cursor.fetchall()
    
    def get_user_info(self, user_id):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute("SELECT username, first_name, last_name FROM users WHERE user_id = %s", (user_id,))
                return cur.fetchone()
        else:
            cursor = self.conn.cursor()
            cursor.execute("SELECT username, first_name, last_name FROM users WHERE user_id = ?", (user_id,))
            return cursor.fetchone()
    
    def add_access_request(self, user_id, username, first_name, last_name, message=None):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO access_requests (user_id, username, first_name, last_name, message, requested_at, status) VALUES (%s, %s, %s, %s, %s, %s, 'pending') RETURNING id",
                    (user_id, username, first_name, last_name, message, datetime.now())
                )
                self.conn.commit()
                return cur.fetchone()[0]
        else:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO access_requests (user_id, username, first_name, last_name, message, requested_at, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')",
                (user_id, username, first_name, last_name, message, datetime.now())
            )
            self.conn.commit()
            return cursor.lastrowid
    
    def get_pending_requests(self):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT id, user_id, username, first_name, last_name, message, requested_at FROM access_requests WHERE status = 'pending' ORDER BY requested_at"
                )
                return cur.fetchall()
        else:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT id, user_id, username, first_name, last_name, message, requested_at FROM access_requests WHERE status = 'pending' ORDER BY requested_at"
            )
            return cursor.fetchall()
    
    def get_request_by_id(self, request_id):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT id, user_id, username, first_name, last_name, message, status FROM access_requests WHERE id = %s",
                    (request_id,)
                )
                return cur.fetchone()
        else:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT id, user_id, username, first_name, last_name, message, status FROM access_requests WHERE id = ?",
                (request_id,)
            )
            return cursor.fetchone()
    
    def process_request(self, request_id, status, processed_by):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute(
                    "UPDATE access_requests SET status = %s, processed_at = %s, processed_by = %s WHERE id = %s",
                    (status, datetime.now(), processed_by, request_id)
                )
                self.conn.commit()
                
                if status == 'approved':
                    request = self.get_request_by_id(request_id)
                    if request:
                        self.add_allowed_user(request[1], processed_by)
        else:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE access_requests SET status = ?, processed_at = ?, processed_by = ? WHERE id = ?",
                (status, datetime.now(), processed_by, request_id)
            )
            self.conn.commit()
            
            if status == 'approved':
                request = self.get_request_by_id(request_id)
                if request:
                    self.add_allowed_user(request[1], processed_by)
    
    def get_requests_count(self):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM access_requests WHERE status = 'pending'")
                return cur.fetchone()[0]
        else:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM access_requests WHERE status = 'pending'")
            return cursor.fetchone()[0]
    
    def add_admin(self, user_id, added_by):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO admins (user_id, added_at, added_by) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (user_id, datetime.now(), added_by)
                )
                self.conn.commit()
                return cur.rowcount > 0
        else:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO admins (user_id, added_at, added_by) VALUES (?, ?, ?)",
                (user_id, datetime.now(), added_by)
            )
            self.conn.commit()
            return cursor.rowcount > 0
    
    def remove_admin(self, user_id):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM admins WHERE user_id = %s", (user_id,))
                self.conn.commit()
                return cur.rowcount > 0
        else:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
            self.conn.commit()
            return cursor.rowcount > 0
    
    def is_admin(self, user_id):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM admins WHERE user_id = %s", (user_id,))
                return cur.fetchone()[0] > 0
        else:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM admins WHERE user_id = ?", (user_id,))
            return cursor.fetchone()[0] > 0
    
    def get_admins(self):
        if self.is_postgres:
            with self.conn.cursor() as cur:
                cur.execute("SELECT user_id, added_at, added_by FROM admins ORDER BY added_at")
                return cur.fetchall()
        else:
            cursor = self.conn.cursor()
            cursor.execute("SELECT user_id, added_at, added_by FROM admins ORDER BY added_at")
            return cursor.fetchall()
    
    def close(self):
        if self.conn:
            self.conn.close()