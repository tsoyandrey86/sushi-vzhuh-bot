import asyncio
import sys

# Для Windows
if sys.platform == 'win32':
    # Убираем предупреждение, устанавливая политику
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except:
        pass

# Импортируем бота
from bot import main

if __name__ == '__main__':
    try:
        # Создаем новый event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Запускаем бота
        main()
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        input("Нажмите Enter для выхода...")