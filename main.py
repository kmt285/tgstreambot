import os
import asyncio
import mimetypes
from urllib.parse import quote
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from aiohttp import web
import aiohttp
import base64

# --- Configurations ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL"))
URL = os.environ.get("URL")

app = Client("simple_stream_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- 2. File Extractor ---
def encode_id(msg_id):
    raw_str = f"software_{msg_id}_hub" # ရှေ့နောက်မှာ စာသားလေးတွေ ခံထားပါမယ်
    return base64.urlsafe_b64encode(raw_str.encode()).decode().rstrip("=")

def decode_id(hash_str):
    padding = 4 - (len(hash_str) % 4)
    decoded_bytes = base64.urlsafe_b64decode(hash_str + ("=" * padding))
    return int(decoded_bytes.decode().split("_")[1])
    
def get_filename_and_mime(message: Message):
    file_obj = message.document or message.video or message.audio
    if not file_obj:
        return "Unknown_Media.bin", "application/octet-stream"
        
    file_name = getattr(file_obj, "file_name", None)
    mime_type = getattr(file_obj, "mime_type", "application/octet-stream")
    
    if not file_name:
        ext = mimetypes.guess_extension(mime_type) or ".bin"
        file_name = f"Telegram_File_{message.id}{ext}"
        
    return file_name, mime_type

# --- 3. Message Handler ---
@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def get_file_and_link(client: Client, message: Message):
    try:
        copied_msg = await message.copy(chat_id=BIN_CHANNEL)
        file_name, _ = get_filename_and_mime(message)
        
        base_url = URL.rstrip('/') if URL else "https://your-bot-url.onrender.com"
        hash_id = encode_id(copied_msg.id)
        direct_link = f"{base_url}/download/{hash_id}"
        
        reply_text = f"**File Name:** `{file_name}`\n\n**📥 Direct Download Link:**\n`{direct_link}`"
        await message.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        await message.reply_text(f"❌ **Error:** `{str(e)}`")

# --- 4. Web Server (Download Endpoint) ---
async def hello(request):
    return web.Response(text="Bot is awake and running smoothly!")

async def download_file(request):
    hash_str = request.match_info['hash_id']
    try:
        file_message_id = decode_id(hash_str)
        msg = await app.get_messages(chat_id=BIN_CHANNEL, message_ids=int(file_message_id))
        file_obj = msg.document or msg.video or msg.audio
        
        if not file_obj:
            raise web.HTTPNotFound(text="File not found in message.")
            
        file_id = file_obj.file_id
        file_name, mime_type = get_filename_and_mime(msg)

        response = web.StreamResponse()
        safe_filename = quote(file_name)
        response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{safe_filename}"
        response.headers['Content-Type'] = mime_type
        
        await response.prepare(request)

        async for chunk in app.stream_media(file_id):
            await response.write(chunk)
            
        await response.write_eof()
        return response

    except Exception as e:
        raise web.HTTPInternalServerError(text=str(e))

async def init_web():
    web_app = web.Application()
    web_app.router.add_get('/', hello)
    web_app.router.add_get('/download/{hash_id}', download_file)
    
    runner = web.AppRunner(web_app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

# --- 5. Main Run Block (Auto-Sync စနစ်သစ်) ---
async def main():
    print("Bot is starting...")
    await app.start() # 1. Bot ကို အရင်နှိုးမည်
    
    # 2. Web Server ကို စတင်မည်
    loop.create_task(init_web())
    
    # 3. 🔴 အရေးကြီးဆုံးအဆင့်: Pyrogram ကိုယ်တိုင် Channel ကို သွားမှတ်ခိုင်းမည်
    try:
        await app.get_chat(BIN_CHANNEL)
        print("✅ Channel Peer Cached Successfully! PeerIdInvalid will not happen.")
    except Exception as e:
        print(f"⚠️ get_chat failed, trying fallback... {e}")
        try:
            msg = await app.send_message(BIN_CHANNEL, "🔄 Syncing Peer...")
            await msg.delete()
            print("✅ Channel Peer Synced via fallback message!")
        except Exception as e2:
            print(f"❌ Ultimate Sync Failed: {e2}")

    # 4. Bot ကို ဆက်လက် အလုပ်လုပ်စေမည်
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
