import os
import sqlite3
from datetime import datetime

# Проверяем, запущены ли мы на Render (есть переменная DATABASE_URL)
DATABASE_URL = os.getenv('DATABASE_URL')
IS_RENDER = bool(DATABASE_URL)

if IS_RENDER:
    try:
        import asyncpg
    except ImportError:
        raise ImportError("asyncpg не установлен. Добавьте 'asyncpg' в requirements.txt")

class Database:
    def __init__(self):
        self.conn = None
        self.is_postgres = IS_RENDER
        self.init_db()
    
    def init_db(self):
        if self.is_postgres:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.connect_postgres())
        else:
            self.connect_sqlite()
    
    # ========== POSTGRESQL (Render/Supabase) ==========
    
    async def connect_postgres(self):
        """Подключение к PostgreSQL (Supabase)"""
        self.conn = await asyncpg.connect(DATABASE_URL)
        await self.create_tables_postgres()
        await self.add_sample_categories_postgres()
        await self.add_admin_to_allowed_postgres()
        await self.add_main_admin_postgres()
    
    async def create_tables_postgres(self):
        """Создание таблиц в PostgreSQL"""
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT
            )
        ''')
        
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id SERIAL PRIMARY KEY,
                category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                file_id TEXT NOT NULL,
                duration INTEGER,
                created_at TIMESTAMP
            )
        ''')
        
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                registered_at TIMESTAMP
            )
        ''')
        
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS allowed_users (
                user_id BIGINT PRIMARY KEY,
                added_at TIMESTAMP,
                added_by BIGINT
            )
        ''')
        
        await self.conn.execute('''
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
        
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY,
                added_at TIMESTAMP,
                added_by BIGINT
            )
        ''')
    
    async def add_sample_categories_postgres(self):
        """Добавление тестовых категорий в PostgreSQL"""
        count = await self.conn.fetchval("SELECT COUNT(*) FROM categories")
        if count == 0:
            categories = [
                ("Python для начинающих", "Базовый курс по Python"),
                ("Веб-разработка", "Django и Flask"),
                ("Data Science", "Анализ данных и ML"),
                ("Мобильная разработка", "Kotlin и Swift")
            ]
            for name, desc in categories:
                await self.conn.execute(
                    "INSERT INTO categories (name, description) VALUES ($1, $2)",
                    name, desc
                )
    
    async def add_admin_to_allowed_postgres(self):
        """Добавить админа в белый список в PostgreSQL"""
        from config import ADMIN_ID
        await self.conn.execute(
            "INSERT INTO allowed_users (user_id, added_at, added_by) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            ADMIN_ID, datetime.now(), ADMIN_ID
        )
    
    async def add_main_admin_postgres(self):
        """Добавить главного администратора в PostgreSQL"""
        from config import ADMIN_ID
        await self.conn.execute(
            "INSERT INTO admins (user_id, added_at, added_by) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            ADMIN_ID, datetime.now(), ADMIN_ID
        )
    
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
    
    # ========== ОБЩИЕ МЕТОДЫ (работают и с SQLite, и с PostgreSQL) ==========
    
    def get_categories(self):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._get_categories_postgres())
        else:
            return self._get_categories_sqlite()
    
    async def _get_categories_postgres(self):
        rows = await self.conn.fetch("SELECT id, name, description FROM categories ORDER BY id")
        return [(row['id'], row['name'], row['description']) for row in rows]
    
    def _get_categories_sqlite(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, description FROM categories")
        return cursor.fetchall()
    
    def get_category(self, category_id):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._get_category_postgres(category_id))
        else:
            return self._get_category_sqlite(category_id)
    
    async def _get_category_postgres(self, category_id):
        row = await self.conn.fetchrow("SELECT id, name, description FROM categories WHERE id = $1", category_id)
        return (row['id'], row['name'], row['description']) if row else None
    
    def _get_category_sqlite(self, category_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, description FROM categories WHERE id = ?", (category_id,))
        return cursor.fetchone()
    
    def get_videos_by_category(self, category_id):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._get_videos_by_category_postgres(category_id))
        else:
            return self._get_videos_by_category_sqlite(category_id)
    
    async def _get_videos_by_category_postgres(self, category_id):
        rows = await self.conn.fetch(
            "SELECT id, title, file_id, duration FROM videos WHERE category_id = $1 ORDER BY id",
            category_id
        )
        return [(row['id'], row['title'], row['file_id'], row['duration']) for row in rows]
    
    def _get_videos_by_category_sqlite(self, category_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, title, file_id, duration FROM videos WHERE category_id = ?", (category_id,))
        return cursor.fetchall()
    
    def get_videos_count_by_category(self, category_id):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._get_videos_count_by_category_postgres(category_id))
        else:
            return self._get_videos_count_by_category_sqlite(category_id)
    
    async def _get_videos_count_by_category_postgres(self, category_id):
        return await self.conn.fetchval("SELECT COUNT(*) FROM videos WHERE category_id = $1", category_id)
    
    def _get_videos_count_by_category_sqlite(self, category_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM videos WHERE category_id = ?", (category_id,))
        return cursor.fetchone()[0]
    
    def add_video(self, category_id, title, file_id, duration=None):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(
                self._add_video_postgres(category_id, title, file_id, duration)
            )
        else:
            return self._add_video_sqlite(category_id, title, file_id, duration)
    
    async def _add_video_postgres(self, category_id, title, file_id, duration):
        row = await self.conn.fetchrow(
            "INSERT INTO videos (category_id, title, file_id, duration, created_at) VALUES ($1, $2, $3, $4, $5) RETURNING id",
            category_id, title, file_id, duration, datetime.now()
        )
        return row['id']
    
    def _add_video_sqlite(self, category_id, title, file_id, duration):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO videos (category_id, title, file_id, duration, created_at) VALUES (?, ?, ?, ?, ?)",
            (category_id, title, file_id, duration, datetime.now())
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def add_user(self, user_id, username, first_name, last_name):
        if self.is_postgres:
            import asyncio
            asyncio.new_event_loop().run_until_complete(
                self._add_user_postgres(user_id, username, first_name, last_name)
            )
        else:
            self._add_user_sqlite(user_id, username, first_name, last_name)
    
    async def _add_user_postgres(self, user_id, username, first_name, last_name):
        await self.conn.execute(
            "INSERT INTO users (user_id, username, first_name, last_name, registered_at) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
            user_id, username, first_name, last_name, datetime.now()
        )
    
    def _add_user_sqlite(self, user_id, username, first_name, last_name):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, registered_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, first_name, last_name, datetime.now())
        )
        self.conn.commit()
    
    def update_category(self, category_id, new_name, new_description=None):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(
                self._update_category_postgres(category_id, new_name, new_description)
            )
        else:
            return self._update_category_sqlite(category_id, new_name, new_description)
    
    async def _update_category_postgres(self, category_id, new_name, new_description):
        if new_description is not None:
            result = await self.conn.execute(
                "UPDATE categories SET name = $1, description = $2 WHERE id = $3",
                new_name, new_description, category_id
            )
        else:
            result = await self.conn.execute(
                "UPDATE categories SET name = $1 WHERE id = $2",
                new_name, category_id
            )
        return result == "UPDATE 1"
    
    def _update_category_sqlite(self, category_id, new_name, new_description):
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
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._delete_category_postgres(category_id))
        else:
            return self._delete_category_sqlite(category_id)
    
    async def _delete_category_postgres(self, category_id):
        await self.conn.execute("DELETE FROM videos WHERE category_id = $1", category_id)
        result = await self.conn.execute("DELETE FROM categories WHERE id = $1", category_id)
        return result == "DELETE 1"
    
    def _delete_category_sqlite(self, category_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM videos WHERE category_id = ?", (category_id,))
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def is_user_allowed(self, user_id):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._is_user_allowed_postgres(user_id))
        else:
            return self._is_user_allowed_sqlite(user_id)
    
    async def _is_user_allowed_postgres(self, user_id):
        count = await self.conn.fetchval("SELECT COUNT(*) FROM allowed_users WHERE user_id = $1", user_id)
        return count > 0
    
    def _is_user_allowed_sqlite(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM allowed_users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()[0] > 0
    
    def add_allowed_user(self, user_id, added_by):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._add_allowed_user_postgres(user_id, added_by))
        else:
            return self._add_allowed_user_sqlite(user_id, added_by)
    
    async def _add_allowed_user_postgres(self, user_id, added_by):
        result = await self.conn.execute(
            "INSERT INTO allowed_users (user_id, added_at, added_by) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            user_id, datetime.now(), added_by
        )
        return result == "INSERT 0 1"
    
    def _add_allowed_user_sqlite(self, user_id, added_by):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO allowed_users (user_id, added_at, added_by) VALUES (?, ?, ?)",
            (user_id, datetime.now(), added_by)
        )
        self.conn.commit()
        return cursor.rowcount > 0
    
    def remove_allowed_user(self, user_id):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._remove_allowed_user_postgres(user_id))
        else:
            return self._remove_allowed_user_sqlite(user_id)
    
    async def _remove_allowed_user_postgres(self, user_id):
        result = await self.conn.execute("DELETE FROM allowed_users WHERE user_id = $1", user_id)
        return result == "DELETE 1"
    
    def _remove_allowed_user_sqlite(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM allowed_users WHERE user_id = ?", (user_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_allowed_users(self):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._get_allowed_users_postgres())
        else:
            return self._get_allowed_users_sqlite()
    
    async def _get_allowed_users_postgres(self):
        rows = await self.conn.fetch("SELECT user_id, added_at, added_by FROM allowed_users ORDER BY added_at")
        return [(row['user_id'], row['added_at'], row['added_by']) for row in rows]
    
    def _get_allowed_users_sqlite(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, added_at, added_by FROM allowed_users ORDER BY added_at")
        return cursor.fetchall()
    
    def get_user_info(self, user_id):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._get_user_info_postgres(user_id))
        else:
            return self._get_user_info_sqlite(user_id)
    
    async def _get_user_info_postgres(self, user_id):
        row = await self.conn.fetchrow("SELECT username, first_name, last_name FROM users WHERE user_id = $1", user_id)
        return (row['username'], row['first_name'], row['last_name']) if row else None
    
    def _get_user_info_sqlite(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT username, first_name, last_name FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()
    
    def add_access_request(self, user_id, username, first_name, last_name, message=None):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(
                self._add_access_request_postgres(user_id, username, first_name, last_name, message)
            )
        else:
            return self._add_access_request_sqlite(user_id, username, first_name, last_name, message)
    
    async def _add_access_request_postgres(self, user_id, username, first_name, last_name, message):
        row = await self.conn.fetchrow(
            "INSERT INTO access_requests (user_id, username, first_name, last_name, message, requested_at, status) VALUES ($1, $2, $3, $4, $5, $6, 'pending') RETURNING id",
            user_id, username, first_name, last_name, message, datetime.now()
        )
        return row['id']
    
    def _add_access_request_sqlite(self, user_id, username, first_name, last_name, message):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO access_requests (user_id, username, first_name, last_name, message, requested_at, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')",
            (user_id, username, first_name, last_name, message, datetime.now())
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def get_pending_requests(self):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._get_pending_requests_postgres())
        else:
            return self._get_pending_requests_sqlite()
    
    async def _get_pending_requests_postgres(self):
        rows = await self.conn.fetch(
            "SELECT id, user_id, username, first_name, last_name, message, requested_at FROM access_requests WHERE status = 'pending' ORDER BY requested_at"
        )
        return [(row['id'], row['user_id'], row['username'], row['first_name'], row['last_name'], row['message'], row['requested_at']) for row in rows]
    
    def _get_pending_requests_sqlite(self):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, user_id, username, first_name, last_name, message, requested_at FROM access_requests WHERE status = 'pending' ORDER BY requested_at"
        )
        return cursor.fetchall()
    
    def get_request_by_id(self, request_id):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._get_request_by_id_postgres(request_id))
        else:
            return self._get_request_by_id_sqlite(request_id)
    
    async def _get_request_by_id_postgres(self, request_id):
        row = await self.conn.fetchrow(
            "SELECT id, user_id, username, first_name, last_name, message, status FROM access_requests WHERE id = $1",
            request_id
        )
        return (row['id'], row['user_id'], row['username'], row['first_name'], row['last_name'], row['message'], row['status']) if row else None
    
    def _get_request_by_id_sqlite(self, request_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, user_id, username, first_name, last_name, message, status FROM access_requests WHERE id = ?",
            (request_id,)
        )
        return cursor.fetchone()
    
    def process_request(self, request_id, status, processed_by):
        if self.is_postgres:
            import asyncio
            asyncio.new_event_loop().run_until_complete(
                self._process_request_postgres(request_id, status, processed_by)
            )
        else:
            self._process_request_sqlite(request_id, status, processed_by)
    
    async def _process_request_postgres(self, request_id, status, processed_by):
        await self.conn.execute(
            "UPDATE access_requests SET status = $1, processed_at = $2, processed_by = $3 WHERE id = $4",
            status, datetime.now(), processed_by, request_id
        )
        
        if status == 'approved':
            request = await self._get_request_by_id_postgres(request_id)
            if request:
                await self._add_allowed_user_postgres(request[1], processed_by)
    
    def _process_request_sqlite(self, request_id, status, processed_by):
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
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._get_requests_count_postgres())
        else:
            return self._get_requests_count_sqlite()
    
    async def _get_requests_count_postgres(self):
        return await self.conn.fetchval("SELECT COUNT(*) FROM access_requests WHERE status = 'pending'")
    
    def _get_requests_count_sqlite(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM access_requests WHERE status = 'pending'")
        return cursor.fetchone()[0]
    
    def add_admin(self, user_id, added_by):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._add_admin_postgres(user_id, added_by))
        else:
            return self._add_admin_sqlite(user_id, added_by)
    
    async def _add_admin_postgres(self, user_id, added_by):
        result = await self.conn.execute(
            "INSERT INTO admins (user_id, added_at, added_by) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            user_id, datetime.now(), added_by
        )
        return result == "INSERT 0 1"
    
    def _add_admin_sqlite(self, user_id, added_by):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO admins (user_id, added_at, added_by) VALUES (?, ?, ?)",
            (user_id, datetime.now(), added_by)
        )
        self.conn.commit()
        return cursor.rowcount > 0
    
    def remove_admin(self, user_id):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._remove_admin_postgres(user_id))
        else:
            return self._remove_admin_sqlite(user_id)
    
    async def _remove_admin_postgres(self, user_id):
        result = await self.conn.execute("DELETE FROM admins WHERE user_id = $1", user_id)
        return result == "DELETE 1"
    
    def _remove_admin_sqlite(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def is_admin(self, user_id):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._is_admin_postgres(user_id))
        else:
            return self._is_admin_sqlite(user_id)
    
    async def _is_admin_postgres(self, user_id):
        count = await self.conn.fetchval("SELECT COUNT(*) FROM admins WHERE user_id = $1", user_id)
        return count > 0
    
    def _is_admin_sqlite(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM admins WHERE user_id = ?", (user_id,))
        return cursor.fetchone()[0] > 0
    
    def get_admins(self):
        if self.is_postgres:
            import asyncio
            return asyncio.new_event_loop().run_until_complete(self._get_admins_postgres())
        else:
            return self._get_admins_sqlite()
    
    async def _get_admins_postgres(self):
        rows = await self.conn.fetch("SELECT user_id, added_at, added_by FROM admins ORDER BY added_at")
        return [(row['user_id'], row['added_at'], row['added_by']) for row in rows]
    
    def _get_admins_sqlite(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, added_at, added_by FROM admins ORDER BY added_at")
        return cursor.fetchall()
    
    def close(self):
        if self.is_postgres:
            import asyncio
            if self.conn:
                asyncio.new_event_loop().run_until_complete(self.conn.close())
        else:
            if self.conn:
                self.conn.close()