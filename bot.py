import os
import base64
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Ortam değişkenleri
GITHUB_TOKEN = os.getenv("GH_PAT", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY", "").strip()

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN ortam değişkeni bulunamadı veya boş!")

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

# /start Komutu için Fonksiyon ve Butonlar
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Buton dizilimi
    keyboard = [
        [
            InlineKeyboardButton("📂 Repo'ya Git", url=f"https://github.com/{GITHUB_REPO}"),
            InlineKeyboardButton("⚡ Actions Takibi", url=f"https://github.com/{GITHUB_REPO}/actions")
        ],
        [
            InlineKeyboardButton("ℹ️ Nasıl Kullanılır?", callback_data="help_info")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        "👋 **Merhaba! Max Medya Botuna Hoş Geldiniz.**\n\n"
        "Çalıştırmak istediğiniz Python (`.py`) veya script dosyasını bu sohbete **belge/dosya** olarak göndermeniz yeterlidir.\n\n"
        "• Dosyanız şifrelenip GitHub Actions üzerinde gizlice çalıştırılacaktır."
    )
    
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

# Belge/Dosya gönderildiğinde çalışan fonksiyon
async def handle_hidden_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    
    if not document:
        return

    await update.message.reply_text("📥 Kod alındı, şifreleniyor ve GitHub Actions'a iletiliyor...")

    file = await context.bot.get_file(document.file_id)
    file_bytes = await file.download_as_bytearray()
    
    b64_code = base64.b64encode(file_bytes).decode('utf-8')

    url = f"https://api.github.com/repos/{GITHUB_REPO}/dispatches"

    data = {
        "event_type": "run-hidden-code",
        "client_payload": {
            "file_name": document.file_name,
            "b64_code": b64_code
        }
    }

    res = requests.post(url, json=data, headers=headers)

    if res.status_code == 204:
        await update.message.reply_text(
            f"🚀 **`{document.file_name}` tamamen gizli modda tetiklendi!**\n\n"
            f"• Repoda hiçbir commit/dosya oluşmadı.\n"
            f"• Kod reponun dosya ağacında görünmeyecek.\n"
            f"• GitHub Actions sunucusunda yayın/çalıştırma başlatıldı."
        )
    else:
        await update.message.reply_text(f"❌ Tetikleme hatası ({res.status_code}):\n{res.text}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Handler (İşleyici) Ekleme
    app.add_handler(CommandHandler("start", start_command)) # /start komutu için
    app.add_handler(MessageHandler(filters.Document.ALL, handle_hidden_code)) # Dosyalar için
    
    app.run_polling()
