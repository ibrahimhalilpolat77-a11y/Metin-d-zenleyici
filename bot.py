import os
import base64
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

GITHUB_TOKEN = os.getenv("GH_PAT")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY")  # GitHub Actions ortamında otomatik çekilir (kullanici/repo)

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

async def handle_hidden_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    
    if not document:
        return

    await update.message.reply_text("📥 Kod alındı, şifreleniyor ve GitHub Actions'a iletiliyor...")

    # Telegram'dan gelen dosyayı indiriyoruz
    file = await context.bot.get_file(document.file_id)
    file_bytes = await file.download_as_bytearray()
    
    # Kodu Base64 ile şifreliyoruz (GitHub commit/log kısımlarında kod görünmez)
    b64_code = base64.b64encode(file_bytes).decode('utf-8')

    url = f"https://api.github.com/repos/{GITHUB_REPO}/dispatches"

    # Commit atmadan, şifreli veriyi payload içinde gönderiyoruz
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
    app.add_handler(MessageHandler(filters.Document.ALL, handle_hidden_code))
    app.run_polling()
