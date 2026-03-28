import sqlite3
from datetime import datetime

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('videos.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Таблица категорий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT
            )
        ''')
        
        # Таблица видео
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER,
                title TEXT NOT NULL,
                file_id TEXT NOT NULL,
                duration INTEGER,
                created_at TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
        ''')
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                registered_at TIMESTAMP
            )
        ''')
        
        # Таблица разрешенных пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS allowed_users (
                user_id INTEGER PRIMARY KEY,
                added_at TIMESTAMP,
                added_by INTEGER
            )
        ''')
        
        # Таблица заявок на доступ
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
        
        # Таблица администраторов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_at TIMESTAMP,
                added_by INTEGER
            )
        ''')
        
        self.conn.commit()
        self.add_sample_categories()
        self.add_admin_to_allowed()
        self.add_main_admin()
    
    def add_sample_categories(self):
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
    
    def add_admin_to_allowed(self):
        from config import ADMIN_ID
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO allowed_users (user_id, added_at, added_by) VALUES (?, ?, ?)",
            (ADMIN_ID, datetime.now(), ADMIN_ID)
        )
        self.conn.commit()
    
    def add_main_admin(self):
        from config import ADMIN_ID
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO admins (user_id, added_at, added_by) VALUES (?, ?, ?)",
            (ADMIN_ID, datetime.now(), ADMIN_ID)
        )
        self.conn.commit()
    
    def get_categories(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, description FROM categories")
        return cursor.fetchall()
    
    def get_category(self, category_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, description FROM categories WHERE id = ?", (category_id,))
        return cursor.fetchone()
    
    def get_videos_by_category(self, category_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, title, file_id, duration FROM videos WHERE category_id = ?", (category_id,))
        return cursor.fetchall()
    
    def get_videos_count_by_category(self, category_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM videos WHERE category_id = ?", (category_id,))
        return cursor.fetchone()[0]
    
    def add_video(self, category_id, title, file_id, duration=None):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO videos (category_id, title, file_id, duration, created_at) VALUES (?, ?, ?, ?, ?)",
            (category_id, title, file_id, duration, datetime.now())
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def add_user(self, user_id, username, first_name, last_name):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, registered_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, first_name, last_name, datetime.now())
        )
        self.conn.commit()
    
    def update_category(self, category_id, new_name, new_description=None):
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
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM videos WHERE category_id = ?", (category_id,))
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def is_user_allowed(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM allowed_users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()[0] > 0
    
    def add_allowed_user(self, user_id, added_by):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO allowed_users (user_id, added_at, added_by) VALUES (?, ?, ?)",
            (user_id, datetime.now(), added_by)
        )
        self.conn.commit()
        return cursor.rowcount > 0
    
    def remove_allowed_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM allowed_users WHERE user_id = ?", (user_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_allowed_users(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, added_at, added_by FROM allowed_users ORDER BY added_at")
        return cursor.fetchall()
    
    def get_user_info(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT username, first_name, last_name FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()
    
    def add_access_request(self, user_id, username, first_name, last_name, message=None):
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO access_requests 
               (user_id, username, first_name, last_name, message, requested_at, status) 
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            (user_id, username, first_name, last_name, message, datetime.now())
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def get_pending_requests(self):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, user_id, username, first_name, last_name, message, requested_at "
            "FROM access_requests WHERE status = 'pending' ORDER BY requested_at"
        )
        return cursor.fetchall()
    
    def get_request_by_id(self, request_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, user_id, username, first_name, last_name, message, status FROM access_requests WHERE id = ?",
            (request_id,)
        )
        return cursor.fetchone()
    
    def process_request(self, request_id, status, processed_by):
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
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM access_requests WHERE status = 'pending'")
        return cursor.fetchone()[0]
    
    # Методы для работы с администраторами
    def add_admin(self, user_id, added_by):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO admins (user_id, added_at, added_by) VALUES (?, ?, ?)",
            (user_id, datetime.now(), added_by)
        )
        self.conn.commit()
        return cursor.rowcount > 0
    
    def remove_admin(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def is_admin(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM admins WHERE user_id = ?", (user_id,))
        return cursor.fetchone()[0] > 0
    
    def get_admins(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, added_at, added_by FROM admins ORDER BY added_at")
        return cursor.fetchall()
    
    def close(self):
        self.conn.close()