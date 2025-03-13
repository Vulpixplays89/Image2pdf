import os
import logging
import time
from PIL import Image
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from pymongo import MongoClient
from threading import Thread
from flask import Flask

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Environment variables (Use os.getenv() for security instead of hardcoding)
TOKEN = "8082310597:AAFDZJTjw-dtJsCs5N82rxjcXNOdxAJGhQ4"
MONGO_URL = "mongodb+srv://textbot:textbot@cluster0.afoyw.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
ADMIN_ID = 6897739611


bot = telebot.TeleBot(TOKEN)

# MongoDB setup
mongo_client = MongoClient(MONGO_URL)
db = mongo_client["telegram_bot"]
users_collection = db["users"]

# Stores images, message IDs, and custom names per user
user_images = {}
user_messages = {}
pdf_custom_names = {}

# Flask server to keep bot alive
app = Flask(__name__)

@app.route('/')
def home():
    return "I am alive"

def run_http_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run_http_server).start()

# Start command
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username

    # Save user in database if not already registered
    if not users_collection.find_one({"user_id": user_id}):
        users_collection.insert_one({"user_id": user_id, "username": username})

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗿 Developer 🗿", url="https://t.me/botplays90")],
        [InlineKeyboardButton("📢 Channel 📢", url="https://t.me/join_hyponet")]
    ])

    bot.send_message(
        message.chat.id,
        f"👋 Hello {message.from_user.first_name}!\n\n"
        "📸 Send me images, and when you're done, send /convert to get a PDF.\n"
        "✨ I will combine them into a single PDF for you! 🚀",
        reply_markup=buttons
    )

# Handling image uploads
@bot.message_handler(content_types=['photo'])
def receive_image(message):
    user_id = message.from_user.id
    if user_id not in user_images:
        user_images[user_id] = []
        user_messages[user_id] = []

    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    # Save image locally
    file_name = f"{user_id}_{len(user_images[user_id])}.jpg"
    with open(file_name, "wb") as file:
        file.write(downloaded_file)

    # Convert to PIL image and store
    image = Image.open(file_name).convert('RGB')
    user_images[user_id].append(image)

    # Remove local file after processing
    os.remove(file_name)

    # Send status message and store message IDs for deletion
    status_msg = bot.send_message(message.chat.id, f"✅ {len(user_images[user_id])} image(s) added.\n"
                                                    "📌 Send more or use /convert to generate the PDF.")
    user_messages[user_id].extend([message.message_id, status_msg.message_id])

# Ask user for custom name
@bot.message_handler(commands=['convert'])
def ask_custom_name(message):
    user_id = message.from_user.id
    images = user_images.get(user_id)

    if not images:
        bot.send_message(message.chat.id, "❌ No images found! Please upload images first.")
        return

    # Show custom name option
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("✅ Yes"), KeyboardButton("❌ No"))

    bot.send_message(message.chat.id, "📝 Do you want a custom name for your PDF?", reply_markup=markup)
    bot.register_next_step_handler(message, handle_custom_name)

# Handle custom name response
def handle_custom_name(message):
    user_id = message.from_user.id

    if message.text == "✅ Yes":
        bot.send_message(message.chat.id, "🔤 Please send the custom name for your PDF (without .pdf extension).")
        bot.register_next_step_handler(message, set_custom_name)
    else:
        pdf_custom_names[user_id] = None  # Use default user_id name
        generate_pdf(message)

# Store custom name and proceed to generate PDF
def set_custom_name(message):
    user_id = message.from_user.id
    pdf_custom_names[user_id] = message.text.strip()
    generate_pdf(message)

# Convert images to PDF
def generate_pdf(message):
    user_id = message.from_user.id
    images = user_images.get(user_id)

    if not images:
        bot.send_message(message.chat.id, "❌ No images found! Please upload images first.")
        return

    try:
        # Progress message
        status_msg = bot.send_message(message.chat.id, "⏳ Generating PDF... 0%")

        # Generate PDF with either custom name or default user ID
        pdf_name = pdf_custom_names.get(user_id, f"{user_id}")
        pdf_path = f"{pdf_name}.pdf"
        images[0].save(pdf_path, save_all=True, append_images=images[1:])

        # Simulate progress updates
        for i in range(1, 6):
            time.sleep(0.5)
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_msg.message_id,
                text=f"⏳ Generating PDF... {i * 20}%"
            )

        # Send PDF
        with open(pdf_path, "rb") as pdf_file:
            bot.send_document(user_id, pdf_file, caption=f"✅ Here is your PDF: {pdf_name}.pdf 🎉")

        # Cleanup: Remove PDF and clear stored images/messages
        os.remove(pdf_path)
        del user_images[user_id]

        # Delete bot's progress message
        bot.delete_message(message.chat.id, status_msg.message_id)
        bot.delete_message(message.chat.id, message.message_id)  # Delete /convert command

        # Delete all stored user messages (images + status messages)
        if user_id in user_messages:
            for msg_id in user_messages[user_id]:
                try:
                    bot.delete_message(message.chat.id, msg_id)
                except Exception:
                    pass
            del user_messages[user_id]

    except Exception as e:
        logging.error(f"Error generating PDF: {e}")
        bot.send_message(message.chat.id, "❌ An error occurred while generating the PDF. Please try again.")

@bot.message_handler(commands=['users'])
def list_users(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ You are not authorized to use this command.")
        return

    users = users_collection.find()
    user_list = "\n".join(
        [f"🆔 ID: {user['user_id']}, 👤 Username: @{user.get('username', 'N/A')}" for user in users]
    ) or "⚠️ No users found."

    bot.send_message(message.chat.id, f"📋 **Registered Users:**\n\n{user_list}")

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ You are not authorized to use this command.")
        return

    if len(message.text.split()) < 2:
        bot.send_message(message.chat.id, "📢 **Usage:** `/broadcast Your message here`")
        return

    text = message.text.split(None, 1)[1]
    users = users_collection.find()

    sent_count, failed_count = 0, 0

    for user in users:
        try:
            bot.send_message(user['user_id'], f"📢 **Announcement:**\n\n{text}")
            sent_count += 1
        except Exception:
            failed_count += 1

    bot.send_message(
        message.chat.id,
        f"📊 **Broadcast Summary:**\n\n"
        f"✅ Sent: {sent_count} users\n"
        f"❌ Failed: {failed_count} users"
    )







# Keep bot alive
keep_alive()

while True:
    try:
        print("🚀 Bot is running...")
        bot.polling(none_stop=True, interval=3, timeout=30)
    except Exception as e:
        print(f"⚠️ Bot crashed due to: {e}")
        time.sleep(5)  # Wait 5 seconds before restarting
