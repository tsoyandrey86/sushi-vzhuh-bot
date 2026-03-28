import logging
import sys

logging.basicConfig(level=logging.DEBUG)

try:
    print("1. Импортируем config...")
    from config import TOKEN, ADMIN_ID
    print(f"✓ TOKEN установлен: {TOKEN[:10]}...")
    print(f"✓ ADMIN_ID: {ADMIN_ID}")
    
    print("\n2. Импортируем database...")
    from database import Database
    print("✓ Database импортирован")
    
    print("\n3. Создаем базу данных...")
    db = Database()
    print("✓ База данных создана")
    
    print("\n4. Импортируем telegram...")
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
    print("✓ Telegram импортирован")
    
    print("\n5. Пытаемся запустить бота...")
    from bot import main
    
    print("✓ Все готово, запускаем...")
    main()
    
except Exception as e:
    print(f"\n❌ ОШИБКА: {e}")
    import traceback
    traceback.print_exc()
    input("\nНажмите Enter для выхода...")