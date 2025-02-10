import logging, os
from telegram import *
from telegram.ext import *
from readwise import ReadWise
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
from flask import Flask
import threading

load_dotenv()

# الحصول على التوكين من env
BOT_TOKEN = os.getenv('BOT_TOKEN')
WISE = ReadWise(os.getenv('READWISE_TOKEN'))
ADMIN = int(os.getenv('ADMIN_USER_ID'))  # تحويل إلى int

# تشغيل سيرفر ويب لـ Health Check
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running!"

def run_web():
    app_web.run(host="0.0.0.0", port=8000)

threading.Thread(target=run_web, daemon=True).start()

# إعداد اللوجات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# دالة تقييد الوصول
def restricted(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ADMIN:  # تصحيح الشرط
            print(f"Unauthorized access denied for {user_id}.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# استخراج الروابط من الرسالة
def url_extracter(entities):
    for ent, txt in entities.items():
        if ent.type == MessageEntity.TEXT_LINK:
            return str(ent.url)
        elif ent.type == MessageEntity.URL:
            return str(txt)

@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot for integration with ReadWise API and Telegram.")

@restricted
async def send_to_readwise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from_who = str(update.message.forward_from_chat.username)
    telegram_link = f"https://t.me/{from_who}/{update.message.forward_from_message_id}"
    text = update.message.text_html if update.message.caption_html is None else update.message.caption_html
    post_link = url_extracter(update.message.parse_entities())

    WISE.highlight(
        text=text,
        title=from_who,
        source_url=telegram_link,
        highlight_url=post_link,
        note="from Telegram bot",
        highlighted_at=str(datetime.now().isoformat())
    )

    await update.message.reply_text(f"Message from {from_who} was highlighted.")

@restricted
async def prepare_reader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sending data to Readwise Reader...")
    return FORWARD

@restricted
async def send_to_reader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from_who = str(update.message.forward_from_chat.username)
    telegram_link = f"https://t.me/{from_who}/{update.message.forward_from_message_id}"
    text = update.message.text_html if update.message.caption_html is None else update.message.caption_html

    WISE.save(
        url=telegram_link,
        html=text,
        title=f"{from_who} {datetime.now().isoformat()}",
        summary=text[:128]
    )

    await update.message.reply_text("Working with Reader API...")
    return ConversationHandler.END

@restricted
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Oops...")
    return ConversationHandler.END

# تشغيل البوت
if __name__ == '__main__':
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler_reader = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^r$"), prepare_reader)],
        states={FORWARD: [MessageHandler((filters.TEXT | filters.Document.ALL | filters.PHOTO) & ~filters.COMMAND, send_to_reader)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler_reader)
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler((filters.TEXT | filters.Document.ALL | filters.PHOTO) & ~filters.COMMAND, send_to_readwise))

    # تشغيل البوت في Thread لمنع توقف Koyeb
    def run_bot():
        application.run_polling()

    threading.Thread(target=run_bot, daemon=True).start()
