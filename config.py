import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла (для локальной разработки)
load_dotenv()

# Получаем переменные окружения
TOKEN = "8708743751:AAH1dfsL5Xr-voTXyGhl9WXZylQIPtnLd1U"  # Замените на токен вашего бота
ADMIN_ID = 607683666  # ID администратора (ваш Telegram ID)

# Список разрешенных пользователей (можно добавлять через переменные окружения)
ALLOWED_USERS_STR = os.getenv('ALLOWED_USERS', '')
ALLOWED_USERS = [int(x.strip()) for x in ALLOWED_USERS_STR.split(',') if x.strip()]

# Добавляем админа в список разрешенных, если его там нет
if ADMIN_ID not in ALLOWED_USERS:
    ALLOWED_USERS.append(ADMIN_ID)

# Проверка наличия токена
if not TOKEN:
    raise ValueError("TOKEN не найден в переменных окружения!")