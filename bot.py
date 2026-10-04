# -*- coding: utf-8 -*-
import subprocess
import sys
import os

# ✅ Otomatik eksik modül kurulumu
def auto_install(package):
    try:
        __import__(package)
    except ModuleNotFoundError:
        print(f"📦 Yükleniyor: {package} ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ Yüklendi: {package}")

for mod in ["telebot", "psutil", "requests", "flask"]:
    auto_install(mod)

import telebot
import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import sqlite3
import json
import logging
import signal
import threading
import re
import atexit
import requests
from flask import Flask
from threading import Thread

# --- Flask Keep-Alive Sunucusu ---
app = Flask('')

@app.route('/')
def home():
    return "I'm CHX HOSTING BOT"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    print("Flask Keep-Alive sunucusu başlatıldı.")

# --- Bot Yapılandırması ---
TOKEN = '8990096016:AAGz9axQNs_PVZKDuZ16_fKBiAizZuCBzMQ'
OWNER_ID = 8693437066
ADMIN_ID = 5223354199
YOUR_USERNAME = '@ibrahim_2126'
UPDATE_CHANNEL = 'https://t.me/tvgoizle'

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')

FREE_USER_LIMIT = 0
SUBSCRIBED_USER_LIMIT = 15
ADMIN_LIMIT = float('inf')
OWNER_LIMIT = float('inf')

os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

bot = telebot.TeleBot(TOKEN)

# --- Veri Yapıları ---
bot_scripts = {}
user_subscriptions = {}
user_files = {}
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}
bot_locked = False
pending_broadcast = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Veritabanı İşlemleri ---
def init_db():
    logger.info(f"Veritabanı başlatılıyor: {DATABASE_PATH}")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (user_id INTEGER PRIMARY KEY, expiry TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_files (user_id INTEGER, file_name TEXT, file_type TEXT, PRIMARY KEY (user_id, file_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS active_users (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''')
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
        if ADMIN_ID != OWNER_ID:
             c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (ADMIN_ID,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"❌ Veritabanı başlatma hatası: {e}", exc_info=True)

def load_data():
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT user_id, expiry FROM subscriptions')
        for user_id, expiry in c.fetchall():
            try:
                user_subscriptions[user_id] = {'expiry': datetime.fromisoformat(expiry)}
            except ValueError:
                pass
        c.execute('SELECT user_id, file_name, file_type FROM user_files')
        for user_id, file_name, file_type in c.fetchall():
            if user_id not in user_files:
                user_files[user_id] = []
            user_files[user_id].append((file_name, file_type))
        c.execute('SELECT user_id FROM active_users')
        active_users.update(user_id for (user_id,) in c.fetchall())
        c.execute('SELECT user_id FROM admins')
        admin_ids.update(user_id for (user_id,) in c.fetchall())
        conn.close()
    except Exception as e:
        logger.error(f"❌ Veri yükleme hatası: {e}", exc_info=True)

def add_user_to_db(user_id):
    active_users.add(user_id)
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Kullanıcı ekleme hatası: {e}")

def add_admin_db(user_id):
    admin_ids.add(user_id)
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Admin ekleme hatası: {e}")

def remove_admin_db(user_id):
    if user_id in admin_ids and user_id not in (OWNER_ID, ADMIN_ID):
        admin_ids.remove(user_id)
        try:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            c.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Admin silme hatası: {e}")
    return False

def save_subscription(user_id, expiry_date):
    user_subscriptions[user_id] = {'expiry': expiry_date}
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO subscriptions (user_id, expiry) VALUES (?, ?)', (user_id, expiry_date.isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Abonelik kaydetme hatası: {e}")

def remove_subscription_db(user_id):
    if user_id in user_subscriptions:
        del user_subscriptions[user_id]
        try:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            c.execute('DELETE FROM subscriptions WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Abonelik silme hatası: {e}")

init_db()
load_data()

# --- Yardımcı Fonksiyonlar ---
def get_user_folder(user_id):
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    if user_id in admin_ids:
        markup.add(
            types.KeyboardButton("📢 Updates Channel"),
            types.KeyboardButton("📤 Upload File"), types.KeyboardButton("📂 Check Files"),
            types.KeyboardButton("⚡ Bot Speed"), types.KeyboardButton("📊 Statistics"),
            types.KeyboardButton("💳 Subscriptions"), types.KeyboardButton("📢 Broadcast"),
            types.KeyboardButton("🔒 Lock Bot" if not bot_locked else "🔓 Unlock Bot"), types.KeyboardButton("🟢 Running All Code"),
            types.KeyboardButton("👑 Admin Panel"), types.KeyboardButton("📞 Contact Owner")
        )
    else:
        markup.add(
            types.KeyboardButton("📢 Updates Channel"),
            types.KeyboardButton("📤 Upload File"), types.KeyboardButton("📂 Check Files"),
            types.KeyboardButton("⚡ Bot Speed"), types.KeyboardButton("📊 Statistics"),
            types.KeyboardButton("📞 Contact Owner")
        )
    return markup

# --- Mantıksal Fonksiyonlar (_logic) ---
def _logic_send_welcome(message):
    add_user_to_db(message.from_user.id)
    if bot_locked and message.from_user.id not in admin_ids:
        bot.reply_to(message, "🔒 Bot bakımdadır. Lütfen daha sonra tekrar deneyin.")
        return
    text = f"👋 Merhaba `{message.from_user.first_name}`!\n\n🤖 **CHX Hosting Bot**'a hoş geldiniz. Botlarınızı kesintisiz olarak buradan çalıştırabilirsiniz."
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=get_main_keyboard(message.from_user.id))

def _logic_bot_speed(message):
    start_time = time.time()
    msg = bot.send_message(message.chat.id, "⚡ Hız ölçülüyor...")
    latency = round((time.time() - start_time) * 1000)
    bot.edit_message_text(f"⚡ **Bot Tepki Süresi:** `{latency} ms`", message.chat.id, msg.message_id, parse_mode='Markdown')

def _logic_statistics(message):
    total_users = len(active_users)
    active_subs = sum(1 for s in user_subscriptions.values() if s['expiry'] > datetime.now())
    cpu_usage = psutil.cpu_percent()
    ram_usage = psutil.virtual_memory().percent
    text = (f"📊 **Bot İstatistikleri**\n\n"
            f"👤 Toplam Kullanıcı: `{total_users}`\n"
            f"⭐ Aktif Abonelik: `{active_subs}`\n"
            f"💻 CPU Kullanımı: `%{cpu_usage}`\n"
            f"🧠 RAM Kullanımı: `%{ram_usage}`")
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

def _logic_toggle_lock_bot(message):
    global bot_locked
    if message.from_user.id not in admin_ids:
        return
    bot_locked = not bot_locked
    status = "kilitlendi 🔒" if bot_locked else "açıldı 🔓"
    bot.send_message(message.chat.id, f"⚙️ Bot erişimi {status}.", reply_markup=get_main_keyboard(message.from_user.id))

def _logic_admin_panel(message):
    if message.from_user.id not in admin_ids:
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Admin Ekle", callback_data="admin_add"),
        types.InlineKeyboardButton("➖ Admin Çıkar", callback_data="admin_remove"),
        types.InlineKeyboardButton("📋 Admin Listesi", callback_data="admin_list")
    )
    bot.send_message(message.chat.id, "👑 **Admin Yönetim Paneli**", reply_markup=markup, parse_mode='Markdown')

def _logic_subscriptions_panel(message):
    if message.from_user.id not in admin_ids:
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Abone Ekle", callback_data="sub_add"),
        types.InlineKeyboardButton("➖ Abone Çıkar", callback_data="sub_remove"),
        types.InlineKeyboardButton("🔍 Abone Kontrol", callback_data="sub_check")
    )
    bot.send_message(message.chat.id, "💳 **Abonelik Yönetim Paneli**", reply_markup=markup, parse_mode='Markdown')

def _logic_broadcast_init(message):
    if message.from_user.id not in admin_ids:
        return
    msg = bot.send_message(message.chat.id, "📢 Tüm kullanıcılara gönderilecek mesajı yazın (İptal için /cancel):")
    bot.register_next_step_handler(msg, process_broadcast_message)

def _logic_run_all_scripts(call):
    if call.from_user.id not in admin_ids:
        bot.answer_callback_query(call.id, "Yetkiniz yok.", show_alert=True)
        return
    bot.answer_callback_query(call.id, "Tüm kodlar kontrol ediliyor...", show_alert=True)

# --- Bot Mesaj Yakalayıcıları (Message Handlers) ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    _logic_send_welcome(message)

@bot.message_handler(func=lambda message: True)
def handle_text_buttons(message):
    txt = message.text
    u_id = message.from_user.id
    
    if bot_locked and u_id not in admin_ids:
        bot.reply_to(message, "🔒 Bot kilitlidir.")
        return

    if txt == "📢 Updates Channel":
        bot.reply_to(message, f"📢 Güncelleme kanalımız: {UPDATE_CHANNEL}")
    elif txt == "⚡ Bot Speed":
        _logic_bot_speed(message)
    elif txt == "📊 Statistics":
        _logic_statistics(message)
    elif txt == "📞 Contact Owner":
        bot.reply_to(message, f"👑 Sahibim: {YOUR_USERNAME}")
    elif txt in ["🔒 Lock Bot", "🔓 Unlock Bot"]:
        _logic_toggle_lock_bot(message)
    elif txt == "👑 Admin Panel":
        _logic_admin_panel(message)
    elif txt == "💳 Subscriptions":
        _logic_subscriptions_panel(message)
    elif txt == "📢 Broadcast":
        _logic_broadcast_init(message)
    elif txt == "📤 Upload File":
        bot.reply_to(message, "📂 Lütfen çalıştırmak istediğiniz Python (`.py`) dosyasını yükleyin.")
    elif txt == "📂 Check Files":
        files = user_files.get(u_id, [])
        if not files:
            bot.reply_to(message, "📂 Henüz yüklenmiş bir dosyanız bulunmuyor.")
        else:
            file_list = "\n".join([f"• `{f[0]}` ({f[1]})" for f in files])
            bot.reply_to(message, f"📂 **Dosyalarınız:**\n{file_list}", parse_mode='Markdown')

# --- Callback Query Yakalayıcıları ---
@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    data = call.data
    
    if data.startswith('logs_'):
        logs_bot_callback(call)
    elif data == 'admin_add':
        add_admin_init_callback(call)
    elif data == 'admin_remove':
        remove_admin_init_callback(call)
    elif data == 'admin_list':
        list_admins_callback(call)
    elif data == 'sub_add':
        add_subscription_init_callback(call)
    elif data == 'sub_remove':
        remove_subscription_init_callback(call)
    elif data == 'sub_check':
        check_subscription_init_callback(call)
    elif data.startswith('confirm_broadcast_'):
        handle_confirm_broadcast(call)
    elif data == 'cancel_broadcast':
        handle_cancel_broadcast(call)

# --- Admin & Abonelik Yönlendirmeleri ---
def add_admin_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "👤 Admin yapılacak kullanıcının Telegram ID'sini gönderin:")
    bot.register_next_step_handler(msg, process_add_admin)

def process_add_admin(message):
    try:
        new_admin_id = int(message.text.strip())
        add_admin_db(new_admin_id)
        bot.reply_to(message, f"✅ `{new_admin_id}` ID'si Admin olarak eklendi.", parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, "❌ Geçersiz ID. Sadece sayı giriniz.")

def remove_admin_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "👤 Silinecek Admin ID'sini gönderin:")
    bot.register_next_step_handler(msg, process_remove_admin)

def process_remove_admin(message):
    try:
        target_admin_id = int(message.text.strip())
        if remove_admin_db(target_admin_id):
            bot.reply_to(message, f"✅ Admin `{target_admin_id}` kaldırıldı.", parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ Admin silinemedi veya bu ID ana kuruculardan birine ait.")
    except ValueError:
        bot.reply_to(message, "❌ Geçersiz ID.")

def list_admins_callback(call):
    bot.answer_callback_query(call.id)
    admin_list_str = "\n".join([f"• `{a_id}`" for a_id in admin_ids])
    bot.send_message(call.message.chat.id, f"👑 **Admin Listesi:**\n{admin_list_str}", parse_mode='Markdown')

def add_subscription_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "💳 Kullanıcı ID ve gün sayısını girin (Örn: `123456789 30`):")
    bot.register_next_step_handler(msg, process_add_subscription)

def process_add_subscription(message):
    try:
        parts = message.text.strip().split()
        target_user = int(parts[0])
        days = int(parts[1])
        expiry_date = datetime.now() + timedelta(days=days)
        save_subscription(target_user, expiry_date)
        bot.reply_to(message, f"✅ `{target_user}` ID'li kullanıcıya {days} günlük abonelik tanımlandı.", parse_mode='Markdown')
    except Exception:
        bot.reply_to(message, "❌ Format hatalı! Örnek format: `123456789 30`", parse_mode='Markdown')

def remove_subscription_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "💳 Aboneliği iptal edilecek Kullanıcı ID'sini girin:")
    bot.register_next_step_handler(msg, process_remove_subscription)

def process_remove_subscription(message):
    try:
        target_user = int(message.text.strip())
        remove_subscription_db(target_user)
        bot.reply_to(message, f"✅ `{target_user}` ID'li kullanıcının aboneliği silindi.", parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, "❌ Geçersiz ID.")

def check_subscription_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "🔍 Sorgulanacak Kullanıcı ID'sini girin:")
    bot.register_next_step_handler(msg, process_check_subscription)

def process_check_subscription(message):
    try:
        target_user = int(message.text.strip())
        sub = user_subscriptions.get(target_user)
        if sub and sub['expiry'] > datetime.now():
            days_left = (sub['expiry'] - datetime.now()).days
            bot.reply_to(message, f"⭐ Kullanıcı: `{target_user}`\nKalan Süre: {days_left} gün ({sub['expiry'].strftime('%Y-%m-%d')})", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"🆓 Kullanıcı `{target_user}` aktif bir VIP aboneliğe sahip değil.", parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, "❌ Geçersiz ID.")

# --- Yayın (Broadcast) Mantığı ---
def process_broadcast_message(message):
    if message.text == '/cancel':
        bot.reply_to(message, "❌ Yayın iptal edildi.")
        return
    admin_id = message.from_user.id
    pending_broadcast[admin_id] = message

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Gönderimi Onayla", callback_data=f"confirm_broadcast_{admin_id}"),
        types.InlineKeyboardButton("❌ İptal Et", callback_data="cancel_broadcast")
    )
    bot.reply_to(message, f"📢 Broadcast Önizleme:\n\n{message.text}\n\nToplam `{len(active_users)}` kullanıcıya gönderilecek. Onaylıyor musunuz?", reply_markup=markup, parse_mode='Markdown')

def handle_confirm_broadcast(call):
    admin_id = call.from_user.id
    msg_to_send = pending_broadcast.get(admin_id)
    if not msg_to_send:
        bot.answer_callback_query(call.id, "Yayın süresi doldu.", show_alert=True)
        return

    bot.answer_callback_query(call.id, "🚀 Gönderim başlatılıyor...")
    bot.edit_message_text("🚀 Yayın yapılıyor...", call.message.chat.id, call.message.message_id)

    success_count = 0
    fail_count = 0

    for u_id in list(active_users):
        try:
            bot.copy_message(u_id, msg_to_send.chat.id, msg_to_send.message_id)
            success_count += 1
            time.sleep(0.05)
        except Exception:
            fail_count += 1

    del pending_broadcast[admin_id]
    bot.send_message(call.message.chat.id, f"✅ **Yayın Tamamlandı!**\n\n🟢 Başarılı: `{success_count}`\n🔴 Başarısız: `{fail_count}`", parse_mode='Markdown')

def handle_cancel_broadcast(call):
    admin_id = call.from_user.id
    if admin_id in pending_broadcast:
        del pending_broadcast[admin_id]
    bot.answer_callback_query(call.id, "Yayın iptal edildi.")
    bot.edit_message_text("❌ Yayın iptal edildi.", call.message.chat.id, call.message.message_id)

def logs_bot_callback(call):
    try:
        _, script_owner_id_str, file_name = call.data.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        if not (call.from_user.id == script_owner_id or call.from_user.id in admin_ids):
            bot.answer_callback_query(call.id, "⚠️ Yetkiniz yok.", show_alert=True)
            return

        user_folder = get_user_folder(script_owner_id)
        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")

        if not os.path.exists(log_path):
            bot.answer_callback_query(call.id, "📜 Log bulunamadı.", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            log_data = f.read()

        if not log_data.strip():
            bot.send_message(call.message.chat.id, f"📜 Loglar boş: `{file_name}`", parse_mode='Markdown')
            return

        if len(log_data) > 4000:
            log_data = log_data[-4000:] + "\n... (son 4000 karakter)"

        bot.send_message(call.message.chat.id, f"📜 **Loglar (`{file_name}`):**\n```\n{log_data}\n```", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Log okuma hatası: {e}")

# --- Güvenli Başlatıcı Döngüsü (Çökmeleri Önler) ---
if __name__ == '__main__':
    keep_alive()
    logger.info("Bot pollinge başlatılıyor...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"⚠️ Polling bağlantı hatası: {e}. 5 saniye sonra tekrar deneniyor...")
            time.sleep(5)
