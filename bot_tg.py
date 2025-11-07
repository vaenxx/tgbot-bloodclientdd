import sqlite3
import uuid
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = ''

def init_db():
    conn = sqlite3.connect('bloodclient.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS keys
                      (key TEXT PRIMARY KEY, expiry_date TEXT, login TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins
                      (user_id TEXT PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                      (user_id TEXT PRIMARY KEY, key TEXT)''')
    conn.commit()
    conn.close()

def generate_key(days):
    key = str(uuid.uuid4())
    expiry_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect('bloodclient.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO keys (key, expiry_date) VALUES (?, ?)", (key, expiry_date))
    conn.commit()
    conn.close()
    return key

def is_admin(user_id):
    conn = sqlite3.connect('bloodclient.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (str(user_id),))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_admin(user_id):
    conn = sqlite3.connect('bloodclient.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO admins (user_id) VALUES (?)", (str(user_id),))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

async def code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0] == 'ex1':
        user_id = update.message.from_user.id
        if add_admin(user_id):
            await update.message.reply_text("✅ Вы добавлены в список администраторов!")
        else:
            await update.message.reply_text("ℹ️ Вы уже администратор!")
    else:
        await update.message.reply_text("❗ Используйте: /code ex1")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("🚫 Только админ может использовать этого бота! Используйте /code ex1 для получения прав.")
        return

    keyboard = [
        [InlineKeyboardButton("💎 Создать ключ", callback_data='generate_key')],
        [InlineKeyboardButton("🗑️ Аннулировать ключ", callback_data='revoke_key')],
        [InlineKeyboardButton("📜 Список ключей", callback_data='list_keys')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔧 Выберите действие:", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.message.reply_text("🚫 Только админ может использовать эту команду! Используйте /code ex1.")
        return

    if query.data == 'generate_key':
        keyboard = [
            [InlineKeyboardButton("📅 30 дней", callback_data='generate_30')],
            [InlineKeyboardButton("📅 90 дней", callback_data='generate_90')],
            [InlineKeyboardButton("♾️ Навсегда (10000 дней)", callback_data='generate_10000')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("📆 Выберите срок действия ключа:", reply_markup=reply_markup)

    elif query.data.startswith('generate_'):
        days = int(query.data.split('_')[1])
        key = generate_key(days)
        await query.message.reply_text(f"🆕 Новый ключ: `{key}`\n⏳ Срок действия: {days} дней", parse_mode="Markdown")

    elif query.data == 'revoke_key':
        context.user_data['awaiting_key'] = True
        await query.message.reply_text("🗝️ Введите ключ для аннулирования:")

    elif query.data == 'list_keys':
        conn = sqlite3.connect('bloodclient.db')
        cursor = conn.cursor()
        cursor.execute("SELECT key, login, expiry_date FROM keys")
        keys = cursor.fetchall()
        conn.close()

        if not keys:
            await query.message.reply_text("📭 Ключи отсутствуют.")
            return

        response = "📜 *Список ключей:*\n\n"
        for key, login, expiry_date in keys:
            status = f"🔗 Привязан к {login}" if login else "❌ Не привязан"
            response += f"🔑 `{key}`\n{status}\n⏳ До: {expiry_date}\n\n"
        await query.message.reply_text(response, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("🚫 Только админ может использовать эту команду! Используйте /code ex1.")
        return

    if context.user_data.get('awaiting_key'):
        key = update.message.text
        conn = sqlite3.connect('bloodclient.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM keys WHERE key = ?", (key,))
        cursor.execute("UPDATE users SET key = NULL WHERE key = ?", (key,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"🗑️ Ключ `{key}` аннулирован.", parse_mode="Markdown")
        context.user_data['awaiting_key'] = False

def main():
    init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("code", code))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == "__main__":
    main()
