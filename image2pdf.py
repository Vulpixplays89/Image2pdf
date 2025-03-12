import os
import logging as botplays90
from PIL import Image
from pyrogram import Client, filters
from flask import Flask
from threading import Thread
from pymongo import MongoClient



# Configure botplays90
botplays90.basicConfig(level=botplays90.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Bot credentials
TOKEN = "7947805886:AAGAHB2rxrvI8Z2eocdRtry0dtcNUwcIiyc"
API_ID = "26222466"
API_HASH = "9f70e2ce80e3676b56265d4510561aef"

# Initialize Pyrogram bot
bot_app = Client(
    "pdf_bot",
    bot_token=TOKEN,
    api_hash=API_HASH,
    api_id=API_ID
)


# MongoDB Setup
MONGO_URL = "mongodb+srv://fileshare:fileshare@fileshare.ixlhi.mongodb.net/?retryWrites=true&w=majority&appName=fileshare"
mongo_client = MongoClient(MONGO_URL)
db = mongo_client["telegram_bot"]
users_collection = db["users"]

ADMIN_ID = 6897739611


botplays90.info("Bot Started!")
LIST = {}  # Stores images per user
MESSAGES = {}  # Stores message IDs for deletion

# Flask Web Server for Keep-Alive (Useful for Replit, Heroku)
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "I am alive"

def run_http_server():
    flask_app.run(host='0.0.0.0', port=8080)

def botplays_90():
    t = Thread(target=run_http_server)
    t.start()
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@bot_app.on_message(filters.command(['start']))
def start(client, message):
    user_id = message.from_user.id
    username = message.from_user.username

    # Save user to MongoDB if not already registered
    if not users_collection.find_one({"user_id": user_id}):
        users_collection.insert_one({"user_id": user_id, "username": username})

    # Inline buttons
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗿Developer🗿", url="https://t.me/botplays90")],
        [InlineKeyboardButton("📢Channel📢", url="https://t.me/join_hyponet")]
    ])

    message.reply_text(
        f"Hello {message.from_user.first_name}, I am an Image to PDF bot.\n\n"
        "Send me images, and when you're done, send /convert to get a PDF.",
        reply_markup=buttons
    )


@bot_app.on_message(filters.private & filters.photo)
async def pdf(client, message):
    user_id = message.from_user.id

    if not isinstance(LIST.get(user_id), list):
        LIST[user_id] = []

    try:
        file_id = str(message.photo.file_id)
        ms = await message.reply_text("Processing image ...")
        file = await client.download_media(file_id)

        image = Image.open(file)
        img = image.convert('RGB')
        LIST[user_id].append(img)

        status_msg = await ms.edit(
            f"{len(LIST[user_id])} image(s) added. Send more or use /convert to generate the PDF."
        )

        # Store messages for later deletion
        MESSAGES.setdefault(user_id, []).extend([message.id, ms.id, status_msg.id])
        os.remove(file)  # Delete the downloaded image after processing
    except Exception as e:
        botplays90.error(f"Error processing image: {e}")
        await message.reply_text("❌ Failed to process the image. Please try again.")
@bot_app.on_message(filters.command(['users']) & filters.user(ADMIN_ID))
def list_users(client, message):
    users = users_collection.find()
    user_list = "\n".join(
        [f"ID: {user['user_id']}, Username: @{user.get('username', 'N/A')}" for user in users]
    )

    if not user_list:
        user_list = "No users found."

    message.reply_text(f"**Registered Users:**\n\n{user_list}")


@bot_app.on_message(filters.command(['broadcast']) & filters.user(ADMIN_ID))
async def broadcast_message(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /broadcast Your message here")
        return

    text = message.text.split(None, 1)[1]
    users = users_collection.find()

    sent_count = 0
    failed_count = 0

    for user in users:
        user_id = user['user_id']
        try:
            await client.send_message(user_id, text)
            sent_count += 1
        except Exception:
            failed_count += 1

    await message.reply_text(
        f"📢 **Broadcast Summary:**\n"
        f"✅ Successfully sent to {sent_count} users.\n"
        f"❌ Failed to send to {failed_count} users."
    )




@bot_app.on_message(filters.command(['convert']))
async def done(client, message):
    user_id = message.from_user.id
    images = LIST.get(user_id)

    if not images:
        await message.reply_text("❌ No images found! Please upload images first.")
        return

    try:
        path = f"{user_id}.pdf"
        images[0].save(path, save_all=True, append_images=images[1:])
        await client.send_document(user_id, open(path, "rb"), caption="Here is your PDF!")

        os.remove(path)  # Delete the generated PDF after sending

        # Delete all messages related to image uploads and processing
        if user_id in MESSAGES:
            for msg_id in MESSAGES[user_id]:
                try:
                    await client.delete_messages(user_id, msg_id)
                except Exception as e:
                    botplays90.warning(f"Failed to delete message {msg_id}: {e}")

            del MESSAGES[user_id]

        # Delete the /convert command message
        try:
            await client.delete_messages(user_id, message.id)
        except Exception as e:
            botplays90.warning(f"Failed to delete /convert message: {e}")

        del LIST[user_id]  # Clear user data after PDF is created
    except Exception as e:
        botplays90.error(f"Error generating or sending PDF: {e}")
        await message.reply_text("❌ An error occurred while generating the PDF. Please try again.")

# Start Flask Keep-Alive Server
botplays_90()

# Start Pyrogram Bot
bot_app.run()
