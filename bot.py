import logging
import asyncio
import sys
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from config import TOKEN, ADMIN_ID, ALLOWED_USERS
from database import Database

# Добавьте в начало bot.py, после других импортов
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is running!')
    
    def log_message(self, format, *args):
        pass  # Отключаем логи

def run_health_server():
    try:
        server = HTTPServer(('0.0.0.0', 10000), HealthHandler)
        server.serve_forever()
    except:
        pass

# Запускаем health-check сервер в фоне
threading.Thread(target=run_health_server, daemon=True).start()

# Для Windows и Python 3.14
if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except:
        pass

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()

# ========== ПРОВЕРКА ДОСТУПА ==========

async def check_admin(update: Update) -> bool:
    """Проверка, является ли пользователь администратором"""
    user_id = update.effective_user.id
    
    # Главный админ из config всегда админ
    if user_id == ADMIN_ID:
        return True
    
    # Проверка по базе данных
    if db.is_admin(user_id):
        return True
    
    return False

async def check_access(update: Update) -> bool:
    """Проверка, есть ли у пользователя доступ к боту"""
    user_id = update.effective_user.id
    
    # Админы всегда имеют доступ
    if await check_admin(update):
        return True
    
    # Проверка по списку ALLOWED_USERS из config
    if user_id in ALLOWED_USERS:
        return True
    
    # Проверка по базе данных
    if db.is_user_allowed(user_id):
        return True
    
    return False

def admin_only(func):
    """Декоратор для функций, доступных только администраторам"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not await check_admin(update):
            if update.message:
                await update.message.reply_text(
                    "⛔ *Доступ запрещен*\n\n"
                    "Эта функция доступна только администраторам.",
                    parse_mode=ParseMode.MARKDOWN
                )
            elif update.callback_query:
                await update.callback_query.answer("Только для администраторов!", show_alert=True)
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def restricted(func):
    """Декоратор для ограничения доступа к функциям (только для пользователей с доступом)"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not await check_access(update):
            if update.message:
                keyboard = [
                    [InlineKeyboardButton("📝 Запросить доступ", callback_data='request_access')],
                    [InlineKeyboardButton("ℹ️ Что делать?", callback_data='help_access')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "⛔ *Доступ запрещен*\n\n"
                    "Этот бот предназначен только для ограниченного круга пользователей.\n\n"
                    "👤 *Ваш ID:* `{}`\n\n"
                    "Вы можете запросить доступ у администратора, нажав на кнопку ниже.".format(
                        update.effective_user.id
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
            elif update.callback_query:
                await update.callback_query.answer("Доступ запрещен", show_alert=True)
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# ========== ЗАПРОС ДОСТУПА ==========

async def request_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    
    pending_requests = db.get_pending_requests()
    for req in pending_requests:
        if req[1] == user.id:
            await query.edit_message_text(
                "⏳ *Заявка уже отправлена*\n\n"
                "Ваша заявка на доступ уже рассматривается администратором.\n"
                "Пожалуйста, ожидайте ответа.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Закрыть", callback_data='close')]
                ])
            )
            return
    
    context.user_data['request_access'] = True
    await query.edit_message_text(
        "📝 *Запрос доступа*\n\n"
        f"👤 *Ваше имя:* {user.first_name}\n"
        f"🆔 *Ваш ID:* `{user.id}`\n\n"
        "Вы можете добавить сообщение для администратора "
        "(например, представьтесь или укажите причину запроса):\n\n"
        "Отправьте текстовое сообщение или нажмите 'Пропустить'.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏩ Пропустить", callback_data='skip_message')],
            [InlineKeyboardButton("🔙 Отмена", callback_data='close')]
        ])
    )

async def skip_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db.add_access_request(user.id, user.username, user.first_name, user.last_name, None)
    
    await notify_admin_about_request(user, None)
    
    await query.edit_message_text(
        "✅ *Заявка отправлена!*\n\n"
        "Администратор получил уведомление о вашем запросе.\n"
        "Как только доступ будет предоставлен, вы получите уведомление.\n\n"
        "Обычно это занимает несколько минут.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Закрыть", callback_data='close')]
        ])
    )
    
    context.user_data.pop('request_access', None)

async def handle_access_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('request_access'):
        user = update.effective_user
        message = update.message.text
        
        db.add_access_request(user.id, user.username, user.first_name, user.last_name, message)
        
        await notify_admin_about_request(user, message)
        
        await update.message.reply_text(
            "✅ *Заявка отправлена!*\n\n"
            "Администратор получил уведомление о вашем запросе.\n"
            "Как только доступ будет предоставлен, вы получите уведомление.\n\n"
            "Обычно это занимает несколько минут.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Закрыть", callback_data='close')]
            ])
        )
        
        context.user_data.pop('request_access', None)

async def notify_admin_about_request(user, message):
    requests_count = db.get_requests_count()
    
    notification_text = (
        "📝 *Новая заявка на доступ!*\n\n"
        f"👤 *Пользователь:* {user.first_name}\n"
        f"🆔 *ID:* `{user.id}`\n"
        f"📱 *Username:* @{user.username if user.username else 'нет'}\n"
    )
    
    if message:
        notification_text += f"💬 *Сообщение:* {message}\n\n"
    else:
        notification_text += "\n"
    
    notification_text += (
        f"📊 *Всего заявок:* {requests_count}\n\n"
        "Используйте кнопку ниже для управления заявками."
    )
    
    keyboard = [[InlineKeyboardButton("👥 Управление заявками", callback_data='admin_requests')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        bot = Application.builder().token(TOKEN).build().bot
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=notification_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления админу: {e}")

async def help_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    help_text = (
        "ℹ️ *Как получить доступ:*\n\n"
        "1. Нажмите кнопку 'Запросить доступ'\n"
        "2. Добавьте сообщение для администратора (по желанию)\n"
        "3. Дождитесь подтверждения\n\n"
        "После одобрения вы сможете пользоваться всеми функциями бота.\n\n"
        "Если у вас есть вопросы, свяжитесь с администратором напрямую."
    )
    
    await query.edit_message_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Запросить доступ", callback_data='request_access')],
            [InlineKeyboardButton("🔙 Назад", callback_data='close')]
        ])
    )

# ========== УПРАВЛЕНИЕ ЗАЯВКАМИ (АДМИН) ==========

async def admin_requests_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not await check_admin(update):
        await query.answer("Только для администратора!", show_alert=True)
        return
    
    requests = db.get_pending_requests()
    
    if not requests:
        await query.edit_message_text(
            "📭 *Нет непросмотренных заявок*\n\n"
            "Все заявки обработаны.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='admin')]
            ])
        )
        return
    
    context.user_data['current_request_index'] = 0
    context.user_data['requests_list'] = requests
    
    await show_request(update, context, 0)

async def show_request(update: Update, context: ContextTypes.DEFAULT_TYPE, index):
    query = update.callback_query
    requests = context.user_data['requests_list']
    if index >= len(requests):
        await admin_requests_panel(update, context)
        return
    
    request = requests[index]
    req_id, user_id, username, first_name, last_name, message, requested_at = request
    
    try:
        if isinstance(requested_at, datetime):
            date_str = requested_at.strftime('%d.%m.%Y %H:%M')
        elif requested_at:
            if isinstance(requested_at, str):
                date_str = requested_at.split('.')[0] if '.' in requested_at else requested_at
            else:
                date_str = str(requested_at)
        else:
            date_str = "Дата неизвестна"
    except Exception:
        date_str = "Дата неизвестна"
    
    text = (
        f"📝 *Заявка #{req_id}* ({index + 1}/{len(requests)})\n\n"
        f"👤 *Имя:* {first_name or 'Не указано'}\n"
        f"🆔 *ID:* `{user_id}`\n"
        f"📱 *Username:* @{username if username else 'нет'}\n"
        f"📅 *Дата:* {date_str}\n"
    )
    
    if message:
        text += f"\n💬 *Сообщение:*\n{message}\n"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f'approve_req_{req_id}'),
            InlineKeyboardButton("❌ Отклонить", callback_data=f'reject_req_{req_id}')
        ]
    ]
    
    if index > 0:
        keyboard.append([InlineKeyboardButton("◀️ Предыдущая", callback_data='prev_request')])
    if index < len(requests) - 1:
        keyboard.append([InlineKeyboardButton("Следующая ▶️", callback_data='next_request')])
    
    keyboard.append([InlineKeyboardButton("🔙 К списку", callback_data='admin_requests')])
    keyboard.append([InlineKeyboardButton("🔙 В админ панель", callback_data='admin')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def next_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    current_index = context.user_data.get('current_request_index', 0)
    context.user_data['current_request_index'] = current_index + 1
    await show_request(update, context, current_index + 1)

async def prev_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    current_index = context.user_data.get('current_request_index', 0)
    context.user_data['current_request_index'] = current_index - 1
    await show_request(update, context, current_index - 1)

async def approve_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    request_id = int(query.data.split('_')[2])
    request = db.get_request_by_id(request_id)
    
    if not request:
        await query.edit_message_text("❌ Заявка не найдена.")
        return
    
    db.process_request(request_id, 'approved', ADMIN_ID)
    
    try:
        await query.bot.send_message(
            chat_id=request[1],
            text="🎉 *Доступ предоставлен!*\n\n"
                 "Ваша заявка на доступ одобрена администратором.\n"
                 "Теперь вы можете пользоваться всеми функциями бота.\n\n"
                 "Нажмите /start для начала работы.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление пользователю {request[1]}: {e}")
    
    await query.edit_message_text(
        f"✅ *Заявка #{request_id} одобрена!*\n\n"
        f"Пользователь уведомлен и добавлен в белый список.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 К списку заявок", callback_data='admin_requests')]
        ])
    )

async def reject_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    request_id = int(query.data.split('_')[2])
    request = db.get_request_by_id(request_id)
    
    if not request:
        await query.edit_message_text("❌ Заявка не найдена.")
        return
    
    db.process_request(request_id, 'rejected', ADMIN_ID)
    
    try:
        await query.bot.send_message(
            chat_id=request[1],
            text="❌ *Доступ отклонен*\n\n"
                 "К сожалению, ваша заявка на доступ была отклонена.\n\n"
                 "Если вы считаете, что это ошибка, свяжитесь с администратором.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление пользователю {request[1]}: {e}")
    
    await query.edit_message_text(
        f"❌ *Заявка #{request_id} отклонена!*\n\n"
        f"Пользователь уведомлен.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 К списку заявок", callback_data='admin_requests')]
        ])
    )

# ========== ОСНОВНЫЕ ФУНКЦИИ ==========

@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    
    keyboard = [
        [InlineKeyboardButton("📚 Категории курсов", callback_data='categories')],
        [InlineKeyboardButton("ℹ️ О боте", callback_data='info')],
    ]
    
    if await check_admin(update):
        keyboard.append([InlineKeyboardButton("🔧 Админ панель", callback_data='admin')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        f"Я бот для просмотра видеокурсов.\n"
        f"Выберите категорию для начала обучения.",
        reply_markup=reply_markup
    )

@restricted
async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    categories = db.get_categories()
    
    if not categories:
        await query.edit_message_text("📭 Категории пока не добавлены.")
        return
    
    keyboard = []
    for cat_id, name, description in categories:
        keyboard.append([InlineKeyboardButton(f"📁 {name}", callback_data=f'cat_{cat_id}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='main')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📂 *Выберите категорию курса:*\n\n"
        "Нажмите на интересующую вас категорию, чтобы увидеть доступные видео.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

@restricted
async def show_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    category_id = int(query.data.split('_')[1])
    context.user_data['current_category'] = category_id
    
    videos = db.get_videos_by_category(category_id)
    
    if not videos:
        await query.edit_message_text(
            "📭 В этой категории пока нет видео.\n\n"
            "Проверьте позже!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад к категориям", callback_data='categories')]
            ])
        )
        return
    
    keyboard = []
    for video_id, title, file_id, duration in videos:
        duration_text = f" ({duration // 60}:{duration % 60:02d})" if duration else ""
        keyboard.append([InlineKeyboardButton(f"🎬 {title}{duration_text}", callback_data=f'video_{video_id}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад к категориям", callback_data='categories')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📺 *Видео в этой категории:*\n\n"
        f"Нажмите на видео для просмотра.\n"
        f"⚠️ *Важно:* Скачивание и запись экрана запрещены!",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

@restricted
async def play_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    video_id = int(query.data.split('_')[1])
    
    cursor = db.conn.cursor()
    cursor.execute("SELECT title, file_id, duration FROM videos WHERE id = ?", (video_id,))
    video = cursor.fetchone()
    
    if not video:
        await query.edit_message_text("❌ Видео не найдено.")
        return
    
    title, file_id, duration = video
    
    try:
        await query.message.reply_video(
            video=file_id,
            caption=f"🎬 *{title}*\n\n"
                    f"⚠️ *Защита контента:*\n"
                    f"• Скачивание видео запрещено\n"
                    f"• Запись экрана запрещена\n"
                    f"• Только просмотр в Telegram",
            parse_mode=ParseMode.MARKDOWN,
            protect_content=True,
            has_spoiler=False
        )
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        await query.message.reply_text("❌ Ошибка при отправке видео.")
        return
    
    keyboard = [[InlineKeyboardButton("🔙 К списку видео", callback_data=f'cat_{context.user_data.get("current_category")}')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        "✅ Видео отправлено! Приятного просмотра.",
        reply_markup=reply_markup
    )

@restricted
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    info_text = (
        "🤖 *О боте:*\n\n"
        "Этот бот предназначен для просмотра видеокурсов.\n\n"
        "📌 *Особенности:*\n"
        "• Видео защищены от скачивания\n"
        "• Запись экрана невозможна\n"
        "• Только потоковый просмотр\n"
        "• Доступ только по приглашению\n\n"
        f"👤 *Ваш ID:* `{update.effective_user.id}`\n\n"
        "По всем вопросам: @tsoyandrey86"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        info_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

# ========== АДМИН ПАНЕЛЬ ==========

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not await check_admin(update):
        await query.edit_message_text("⛔ У вас нет доступа к админ панели.")
        return
    
    pending_requests = db.get_requests_count()
    requests_button_text = f"📝 Заявки на доступ"
    if pending_requests > 0:
        requests_button_text += f" ({pending_requests})"
    
    keyboard = [
        [InlineKeyboardButton("📤 Добавить видео", callback_data='admin_add_video')],
        [InlineKeyboardButton("📁 Добавить категорию", callback_data='admin_add_category')],
        [InlineKeyboardButton("✏️ Редактировать категории", callback_data='admin_edit_categories')],
        [InlineKeyboardButton(requests_button_text, callback_data='admin_requests')],
        [InlineKeyboardButton("👥 Управление доступом", callback_data='access_management')],
    ]
    
    # Кнопка управления администраторами только для главного админа
    if update.effective_user.id == 607683666:
        keyboard.append([InlineKeyboardButton("👑 Управление админами", callback_data='admin_management')])
    
    keyboard.append([InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='main')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🔧 *Админ панель*\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action = query.data.replace('admin_', '')
    
    if action == 'add_video':
        context.user_data['admin_state'] = 'waiting_category_for_video'
        categories = db.get_categories()
        
        keyboard = []
        for cat_id, name, _ in categories:
            keyboard.append([InlineKeyboardButton(name, callback_data=f'select_cat_{cat_id}')])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='admin')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Выберите категорию для добавления видео:",
            reply_markup=reply_markup
        )
    
    elif action == 'add_category':
        context.user_data['admin_state'] = 'waiting_category_name'
        await query.edit_message_text(
            "Введите название новой категории:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data='admin')]])
        )
    
    elif action == 'edit_categories':
        await admin_edit_categories(update, context)
    
    elif action == 'requests':
        await admin_requests_panel(update, context)
    
    elif action == 'stats':
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        users_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM videos")
        videos_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM categories")
        categories_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM allowed_users")
        allowed_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM access_requests WHERE status = 'pending'")
        pending_requests = cursor.fetchone()[0]
        
        stats_text = (
            f"📊 *Статистика бота:*\n\n"
            f"👥 Всего пользователей: {users_count}\n"
            f"✅ Пользователей с доступом: {allowed_count}\n"
            f"📹 Видео: {videos_count}\n"
            f"📁 Категорий: {categories_count}\n"
            f"📝 Ожидают рассмотрения: {pending_requests}"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='admin')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            stats_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

async def select_category_for_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    category_id = int(query.data.split('_')[2])
    context.user_data['category_id'] = category_id
    context.user_data['admin_state'] = 'waiting_video'
    
    category = db.get_category(category_id)
    category_name = category[1] if category else "выбранной категории"
    
    await query.edit_message_text(
        f"✅ Выбрана категория: *{category_name}*\n\n"
        f"📤 Отправьте видео файл.\n\n"
        f"💡 *Совет:* Добавьте название в подпись к видео.\n"
        f"Если подписи не будет, видео получит автоматическое название с датой.\n\n"
        f"Поддерживаемые форматы: MP4, AVI, MOV",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data='admin')]
        ])
    )

# ========== РЕДАКТИРОВАНИЕ КАТЕГОРИЙ ==========

async def admin_edit_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not await check_admin(update):
        return
    
    categories = db.get_categories()
    
    if not categories:
        await query.edit_message_text(
            "📭 Нет доступных категорий.\n\n"
            "Сначала создайте категорию.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Создать категорию", callback_data='admin_add_category')],
                [InlineKeyboardButton("🔙 Назад", callback_data='admin')]
            ])
        )
        return
    
    keyboard = []
    for cat_id, name, description in categories:
        videos_count = db.get_videos_count_by_category(cat_id)
        keyboard.append([
            InlineKeyboardButton(f"📁 {name} ({videos_count} видео)", callback_data=f'edit_cat_{cat_id}')
        ])
    
    keyboard.append([InlineKeyboardButton("➕ Создать категорию", callback_data='admin_add_category')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='admin')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "✏️ *Редактирование категорий*\n\n"
        "Выберите категорию для редактирования или удаления:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def edit_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    category_id = int(query.data.split('_')[2])
    category = db.get_category(category_id)
    
    if not category:
        await query.edit_message_text("❌ Категория не найдена.")
        return
    
    cat_id, name, description = category
    context.user_data['editing_category_id'] = cat_id
    videos_count = db.get_videos_count_by_category(cat_id)
    
    keyboard = [
        [InlineKeyboardButton("✏️ Изменить название", callback_data=f'edit_cat_name_{cat_id}')],
        [InlineKeyboardButton("📝 Изменить описание", callback_data=f'edit_cat_desc_{cat_id}')],
        [InlineKeyboardButton("🎬 Просмотреть видео", callback_data=f'cat_{cat_id}')],
    ]
    
    if videos_count == 0:
        keyboard.append([InlineKeyboardButton("🗑️ Удалить категорию", callback_data=f'delete_cat_{cat_id}')])
    else:
        keyboard.append([InlineKeyboardButton("⚠️ Удалить нельзя (есть видео)", callback_data='no_action')])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад к списку", callback_data='admin_edit_categories')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    info_text = (
        f"📁 *Категория: {name}*\n\n"
        f"📝 *Описание:* {description if description else 'Нет описания'}\n"
        f"📊 *Видео в категории:* {videos_count}\n\n"
        f"Выберите действие:"
    )
    
    await query.edit_message_text(
        info_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def edit_category_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    category_id = int(query.data.split('_')[3])
    context.user_data['editing_category_id'] = category_id
    context.user_data['admin_state'] = 'waiting_new_category_name'
    
    await query.edit_message_text(
        "✏️ Введите новое название для категории:\n\n"
        "Отправьте текстовое сообщение с новым названием.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data=f'edit_cat_{category_id}')]
        ])
    )

async def edit_category_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    category_id = int(query.data.split('_')[3])
    context.user_data['editing_category_id'] = category_id
    context.user_data['admin_state'] = 'waiting_new_category_description'
    
    await query.edit_message_text(
        "📝 Введите новое описание для категории:\n\n"
        "Отправьте текстовое сообщение с новым описанием.\n"
        "Чтобы оставить описание пустым, отправьте '-'",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data=f'edit_cat_{category_id}')]
        ])
    )

async def delete_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    category_id = int(query.data.split('_')[2])
    category = db.get_category(category_id)
    videos_count = db.get_videos_count_by_category(category_id)
    
    if videos_count > 0:
        await query.edit_message_text(
            f"❌ Нельзя удалить категорию '{category[1]}', так как в ней есть видео ({videos_count} шт.).\n\n"
            f"Сначала удалите все видео из этой категории.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data=f'edit_cat_{category_id}')]
            ])
        )
        return
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data=f'confirm_delete_cat_{category_id}'),
            InlineKeyboardButton("❌ Нет", callback_data=f'edit_cat_{category_id}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"⚠️ *Подтверждение удаления*\n\n"
        f"Вы уверены, что хотите удалить категорию '{category[1]}'?\n\n"
        f"Это действие нельзя отменить.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def confirm_delete_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    category_id = int(query.data.split('_')[3])
    category = db.get_category(category_id)
    
    if db.delete_category(category_id):
        await query.edit_message_text(
            f"✅ Категория '{category[1]}' успешно удалена!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Вернуться к списку", callback_data='admin_edit_categories')]
            ])
        )
    else:
        await query.edit_message_text(
            "❌ Ошибка при удалении категории.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_edit_categories')]
            ])
        )

async def no_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Это действие недоступно", show_alert=True)

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    
    keyboard = [
        [InlineKeyboardButton("📚 Категории курсов", callback_data='categories')],
        [InlineKeyboardButton("ℹ️ О боте", callback_data='info')],
    ]
    
    if await check_admin(update):
        keyboard.append([InlineKeyboardButton("🔧 Админ панель", callback_data='admin')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👋 *Главное меню*\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

# ========== УПРАВЛЕНИЕ ДОСТУПОМ ==========

async def access_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not await check_admin(update):
        await query.edit_message_text("⛔ Только для администратора!")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить пользователя", callback_data='access_add')],
        [InlineKeyboardButton("➖ Удалить пользователя", callback_data='access_remove')],
        [InlineKeyboardButton("📋 Список пользователей", callback_data='access_list')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👥 *Управление доступом*\n\n"
        "Здесь вы можете добавлять и удалять пользователей, "
        "которым разрешен доступ к боту.\n\n"
        "Пользователи с доступом могут просматривать видео.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def add_user_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['admin_state'] = 'waiting_user_id_to_add'
    
    await query.edit_message_text(
        "➕ *Добавление пользователя*\n\n"
        "Введите Telegram ID пользователя, которого хотите добавить.\n\n"
        "🔍 *Как найти ID пользователя:*\n"
        "1. Попросите пользователя отправить /id в любом боте\n"
        "2. Или используйте @userinfobot\n\n"
        "📝 *Формат:* Просто число\n\n"
        "Отправьте ID:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data='access_management')]
        ])
    )

async def remove_user_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    users = db.get_allowed_users()
    if not users:
        await query.edit_message_text(
            "📭 Список пользователей пуст.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='access_management')]
            ])
        )
        return
    
    keyboard = []
    for user_id, added_at, added_by in users:
        if user_id != ADMIN_ID:
            user_info = db.get_user_info(user_id)
            if user_info:
                username, first_name, last_name = user_info
                if first_name:
                    name = first_name
                    if last_name:
                        name += f" {last_name}"
                    if username:
                        name += f" (@{username})"
                elif username:
                    name = f"@{username}"
                else:
                    name = str(user_id)
            else:
                name = str(user_id)
            
            keyboard.append([InlineKeyboardButton(f"🗑️ {name}", callback_data=f'remove_user_{user_id}')])
    
    if not keyboard:
        await query.edit_message_text(
            "📭 Нет пользователей для удаления (кроме админа).",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='access_management')]
            ])
        )
        return
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='access_management')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👥 *Выберите пользователя для удаления:*\n\n"
        "Нажмите на пользователя, чтобы удалить его из белого списка.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def list_users_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    users = db.get_allowed_users()
    
    if not users:
        await query.edit_message_text(
            "📭 Список пользователей пуст.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='access_management')]
            ])
        )
        return
    
    text = "👥 *Список пользователей с доступом:*\n\n"
    for i, (user_id, added_at, added_by) in enumerate(users, 1):
        user_info = db.get_user_info(user_id)
        
        if user_info:
            username, first_name, last_name = user_info
            if first_name:
                name = first_name
                if last_name:
                    name += f" {last_name}"
                if username:
                    name += f" (@{username})"
            elif username:
                name = f"@{username}"
            else:
                name = str(user_id)
        else:
            name = str(user_id)
        
        text += f"{i}. **{name}**\n"
        text += f"   🆔 `{user_id}`\n"
        
        if isinstance(added_at, datetime):
            date_str = added_at.strftime('%d.%m.%Y')
            text += f"   📅 Добавлен: {date_str}\n"
        
        if user_id == ADMIN_ID:
            text += "   👑 *Администратор*\n"
        text += "\n"
    
    text += f"\n📊 *Всего:* {len(users)} пользователей"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='access_management')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def remove_user_by_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split('_')[2])
    
    if user_id == ADMIN_ID:
        await query.answer("Нельзя удалить администратора!", show_alert=True)
        return
    
    if db.remove_allowed_user(user_id):
        await query.edit_message_text(
            f"✅ Пользователь `{user_id}` удален из белого списка!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Вернуться", callback_data='access_management')]
            ])
        )
    else:
        await query.edit_message_text(
            "❌ Ошибка при удалении пользователя.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='access_management')]
            ])
        )

# ========== УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ ==========

async def admin_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        await query.answer("Только главный администратор!", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить администратора", callback_data='admin_add_admin')],
        [InlineKeyboardButton("➖ Удалить администратора", callback_data='admin_remove_admin')],
        [InlineKeyboardButton("📋 Список администраторов", callback_data='admin_list_admins')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👑 *Управление администраторами*\n\n"
        "Здесь вы можете назначать и удалять администраторов.\n\n"
        "Администраторы имеют доступ к админ-панели и могут:\n"
        "• Добавлять/удалять видео\n"
        "• Управлять категориями\n"
        "• Управлять заявками на доступ\n"
        "• Добавлять/удалять пользователей\n\n"
        "⚠️ *Внимание:* Только главный администратор может управлять другими админами.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def add_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        await query.answer("Только главный администратор!", show_alert=True)
        return
    
    context.user_data['admin_state'] = 'waiting_user_id_to_add_admin'
    
    await query.edit_message_text(
        "👑 *Добавление администратора*\n\n"
        "Введите Telegram ID пользователя, которого хотите сделать администратором.\n\n"
        "🔍 *Как найти ID пользователя:*\n"
        "1. Попросите пользователя отправить /id в любом боте\n"
        "2. Или используйте @userinfobot\n\n"
        "📝 *Формат:* Просто число\n\n"
        "Отправьте ID:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data='admin_management')]
        ])
    )

async def remove_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        await query.answer("Только главный администратор!", show_alert=True)
        return
    
    admins = db.get_admins()
    
    if not admins:
        await query.edit_message_text(
            "📭 Список администраторов пуст.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_management')]
            ])
        )
        return
    
    keyboard = []
    for admin_id, added_at, added_by in admins:
        if admin_id != ADMIN_ID:
            user_info = db.get_user_info(admin_id)
            if user_info:
                username, first_name, last_name = user_info
                if first_name:
                    name = first_name
                    if last_name:
                        name += f" {last_name}"
                    if username:
                        name += f" (@{username})"
                elif username:
                    name = f"@{username}"
                else:
                    name = str(admin_id)
            else:
                name = str(admin_id)
            
            keyboard.append([InlineKeyboardButton(f"🗑️ {name}", callback_data=f'remove_admin_{admin_id}')])
    
    if not keyboard:
        await query.edit_message_text(
            "📭 Нет администраторов для удаления (кроме главного).",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_management')]
            ])
        )
        return
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='admin_management')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👑 *Выберите администратора для удаления:*\n\n"
        "Нажмите на администратора, чтобы лишить его прав.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def list_admins_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    admins = db.get_admins()
    
    if not admins:
        await query.edit_message_text(
            "📭 Список администраторов пуст.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_management')]
            ])
        )
        return
    
    text = "👑 *Список администраторов:*\n\n"
    for i, (admin_id, added_at, added_by) in enumerate(admins, 1):
        user_info = db.get_user_info(admin_id)
        
        if user_info:
            username, first_name, last_name = user_info
            if first_name:
                name = first_name
                if last_name:
                    name += f" {last_name}"
                if username:
                    name += f" (@{username})"
            elif username:
                name = f"@{username}"
            else:
                name = str(admin_id)
        else:
            name = str(admin_id)
        
        text += f"{i}. **{name}**\n"
        text += f"   🆔 `{admin_id}`\n"
        
        if isinstance(added_at, datetime):
            date_str = added_at.strftime('%d.%m.%Y')
            text += f"   📅 Назначен: {date_str}\n"
        
        if admin_id == ADMIN_ID:
            text += "   👑 *Главный администратор*\n"
        text += "\n"
    
    text += f"\n📊 *Всего:* {len(admins)} администраторов"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='admin_management')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def remove_admin_by_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    admin_id = int(query.data.split('_')[2])
    
    if admin_id == ADMIN_ID:
        await query.answer("Нельзя удалить главного администратора!", show_alert=True)
        return
    
    if db.remove_admin(admin_id):
        user_info = db.get_user_info(admin_id)
        if user_info:
            username, first_name, last_name = user_info
            if first_name:
                name = first_name
                if last_name:
                    name += f" {last_name}"
            else:
                name = str(admin_id)
        else:
            name = str(admin_id)
        
        await query.edit_message_text(
            f"✅ Администратор **{name}** лишен прав!\n"
            f"🆔 `{admin_id}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Вернуться", callback_data='admin_management')]
            ])
        )
        
        try:
            await query.bot.send_message(
                chat_id=admin_id,
                text="⚠️ *Внимание!*\n\n"
                     "Ваши права администратора были отозваны.\n\n"
                     "Если вы считаете, что это ошибка, свяжитесь с главным администратором.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить бывшего админа: {e}")
    else:
        await query.edit_message_text(
            "❌ Ошибка при удалении администратора.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_management')]
            ])
        )

# ========== ОБРАБОТКА СООБЩЕНИЙ ==========

async def handle_admin_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update):
        return
    
    state = context.user_data.get('admin_state')
    
    if state == 'waiting_category_name':
        category_name = update.message.text
        cursor = db.conn.cursor()
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
        db.conn.commit()
        
        context.user_data['admin_state'] = None
        await update.message.reply_text(
            f"✅ Категория '{category_name}' успешно добавлена!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 В админ панель", callback_data='admin')]
            ])
        )
    
    elif state == 'waiting_new_category_name':
        new_name = update.message.text
        category_id = context.user_data.get('editing_category_id')
        
        if category_id and db.update_category(category_id, new_name):
            await update.message.reply_text(
                f"✅ Название категории успешно изменено на '{new_name}'!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Вернуться к категории", callback_data=f'edit_cat_{category_id}')]
                ])
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка при изменении названия.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Попробовать снова", callback_data=f'edit_cat_{category_id}')]
                ])
            )
        
        context.user_data['admin_state'] = None
        context.user_data.pop('editing_category_id', None)
    
    elif state == 'waiting_new_category_description':
        new_description = update.message.text
        if new_description == '-':
            new_description = None
        
        category_id = context.user_data.get('editing_category_id')
        category = db.get_category(category_id)
        
        if category_id and db.update_category(category_id, category[1], new_description):
            await update.message.reply_text(
                f"✅ Описание категории успешно изменено!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Вернуться к категории", callback_data=f'edit_cat_{category_id}')]
                ])
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка при изменении описания.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Попробовать снова", callback_data=f'edit_cat_{category_id}')]
                ])
            )
        
        context.user_data['admin_state'] = None
        context.user_data.pop('editing_category_id', None)
    
    elif state == 'waiting_video':
        if update.message.video:
            video = update.message.video
            file_id = video.file_id
            duration = video.duration
            file_size = video.file_size
            
            if update.message.caption:
                title = update.message.caption
            else:
                title = f"Видео от {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            
            category_id = context.user_data.get('category_id')
            if category_id:
                db.add_video(
                    category_id=category_id,
                    title=title,
                    file_id=file_id,
                    duration=duration
                )
                
                context.user_data['admin_state'] = None
                context.user_data.pop('category_id', None)
                
                await update.message.reply_text(
                    f"✅ Видео успешно добавлено!\n\n"
                    f"📹 Название: {title}\n"
                    f"⏱️ Длительность: {duration // 60}:{duration % 60:02d}\n"
                    f"💾 Размер: {file_size // 1024 // 1024} MB\n\n"
                    f"Вы можете продолжить добавлять видео или вернуться в админ панель.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📤 Добавить еще видео", callback_data='admin_add_video')],
                        [InlineKeyboardButton("🔙 В админ панель", callback_data='admin')]
                    ])
                )
            else:
                await update.message.reply_text(
                    "❌ Ошибка: категория не выбрана. Попробуйте сначала.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 В админ панель", callback_data='admin')]
                    ])
                )
        else:
            await update.message.reply_text(
                "❌ Пожалуйста, отправьте видео файл.\n\n"
                "Поддерживаемые форматы: MP4, AVI, MOV.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Отмена", callback_data='admin')]
                ])
            )
    
    elif state == 'waiting_user_id_to_add':
        try:
            user_id = int(update.message.text.strip())
            if db.add_allowed_user(user_id, ADMIN_ID):
                await update.message.reply_text(
                    f"✅ Пользователь `{user_id}` успешно добавлен в белый список!",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Вернуться", callback_data='access_management')]
                    ])
                )
            else:
                await update.message.reply_text(
                    f"ℹ️ Пользователь `{user_id}` уже есть в белом списке.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Вернуться", callback_data='access_management')]
                    ])
                )
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат ID. Введите число.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Попробовать снова", callback_data='access_add')]
                ])
            )
        
        context.user_data['admin_state'] = None
    
    elif state == 'waiting_user_id_to_add_admin':
        try:
            user_id = int(update.message.text.strip())
            
            if db.is_admin(user_id):
                await update.message.reply_text(
                    f"ℹ️ Пользователь `{user_id}` уже является администратором.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Вернуться", callback_data='admin_management')]
                    ])
                )
                context.user_data['admin_state'] = None
                return
            
            if db.add_admin(user_id, ADMIN_ID):
                if not db.is_user_allowed(user_id):
                    db.add_allowed_user(user_id, ADMIN_ID)
                
                user_info = db.get_user_info(user_id)
                if user_info:
                    username, first_name, last_name = user_info
                    if first_name:
                        name = first_name
                        if last_name:
                            name += f" {last_name}"
                    else:
                        name = str(user_id)
                else:
                    name = str(user_id)
                
                await update.message.reply_text(
                    f"✅ Пользователь **{name}** назначен администратором!\n"
                    f"🆔 `{user_id}`",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Вернуться", callback_data='admin_management')]
                    ])
                )
                
                try:
                    await update.message.bot.send_message(
                        chat_id=user_id,
                        text="🎉 *Поздравляем!*\n\n"
                             "Вы назначены администратором бота.\n\n"
                             "Теперь вам доступна админ-панель.\n\n"
                             "Нажмите /start для начала работы.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logger.error(f"Не удалось уведомить нового админа: {e}")
            else:
                await update.message.reply_text(
                    "❌ Ошибка при назначении администратора.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Вернуться", callback_data='admin_management')]
                    ])
                )
        
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат ID. Введите число.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Попробовать снова", callback_data='admin_add_admin')]
                ])
            )
        
        context.user_data['admin_state'] = None
    
    else:
        await update.message.reply_text(
            "ℹ️ Админ режим активен. Используйте кнопки в админ панели.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔧 Открыть админ панель", callback_data='admin')]
            ])
        )

async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()

# ========== ЗАПУСК БОТА ==========

def main():
    application = Application.builder().token(TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    
    # Обработчики callback-запросов
    application.add_handler(CallbackQueryHandler(show_categories, pattern='^categories$'))
    application.add_handler(CallbackQueryHandler(show_videos, pattern='^cat_\\d+$'))
    application.add_handler(CallbackQueryHandler(play_video, pattern='^video_\\d+$'))
    application.add_handler(CallbackQueryHandler(info, pattern='^info$'))
    application.add_handler(CallbackQueryHandler(main_menu, pattern='^main$'))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin$'))
    application.add_handler(CallbackQueryHandler(admin_action, pattern='^admin_\\w+$'))
    application.add_handler(CallbackQueryHandler(select_category_for_video, pattern='^select_cat_\\d+$'))
    application.add_handler(CallbackQueryHandler(admin_edit_categories, pattern='^admin_edit_categories$'))
    application.add_handler(CallbackQueryHandler(edit_category, pattern='^edit_cat_\\d+$'))
    application.add_handler(CallbackQueryHandler(edit_category_name, pattern='^edit_cat_name_\\d+$'))
    application.add_handler(CallbackQueryHandler(edit_category_description, pattern='^edit_cat_desc_\\d+$'))
    application.add_handler(CallbackQueryHandler(delete_category, pattern='^delete_cat_\\d+$'))
    application.add_handler(CallbackQueryHandler(confirm_delete_category, pattern='^confirm_delete_cat_\\d+$'))
    application.add_handler(CallbackQueryHandler(no_action, pattern='^no_action$'))
    application.add_handler(CallbackQueryHandler(access_management, pattern='^access_management$'))
    application.add_handler(CallbackQueryHandler(add_user_panel, pattern='^access_add$'))
    application.add_handler(CallbackQueryHandler(remove_user_panel, pattern='^access_remove$'))
    application.add_handler(CallbackQueryHandler(list_users_panel, pattern='^access_list$'))
    application.add_handler(CallbackQueryHandler(remove_user_by_id, pattern='^remove_user_\\d+$'))
    
    # Обработчики для заявок
    application.add_handler(CallbackQueryHandler(request_access, pattern='^request_access$'))
    application.add_handler(CallbackQueryHandler(skip_message, pattern='^skip_message$'))
    application.add_handler(CallbackQueryHandler(help_access, pattern='^help_access$'))
    application.add_handler(CallbackQueryHandler(close, pattern='^close$'))
    application.add_handler(CallbackQueryHandler(admin_requests_panel, pattern='^admin_requests$'))
    application.add_handler(CallbackQueryHandler(next_request, pattern='^next_request$'))
    application.add_handler(CallbackQueryHandler(prev_request, pattern='^prev_request$'))
    application.add_handler(CallbackQueryHandler(approve_request, pattern='^approve_req_\\d+$'))
    application.add_handler(CallbackQueryHandler(reject_request, pattern='^reject_req_\\d+$'))
    
    # Обработчики для управления администраторами
    application.add_handler(CallbackQueryHandler(admin_management, pattern='^admin_management$'))
    application.add_handler(CallbackQueryHandler(add_admin_panel, pattern='^admin_add_admin$'))
    application.add_handler(CallbackQueryHandler(remove_admin_panel, pattern='^admin_remove_admin$'))
    application.add_handler(CallbackQueryHandler(list_admins_panel, pattern='^admin_list_admins$'))
    application.add_handler(CallbackQueryHandler(remove_admin_by_id, pattern='^remove_admin_\\d+$'))
    
    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_access_message))
    application.add_handler(MessageHandler(filters.TEXT & filters.User(user_id=ADMIN_ID), handle_admin_messages))
    application.add_handler(MessageHandler(filters.VIDEO & filters.User(user_id=ADMIN_ID), handle_admin_messages))
    
    logger.info("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()