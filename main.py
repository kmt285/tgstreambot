import os
import asyncio
import mimetypes
from urllib.parse import quote
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from aiohttp import web
import aiohttp

# --- Configurations ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL"))
URL = os.environ.get("URL")

app = Client("simple_stream_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- 🛠️ 1. Auto-Sync Channel Peer (The Magic Fix) ---
async def sync_channel_peer():
    """Server Restart ဖြစ်တိုင်း Channel ကို မေ့သွားခြင်းမှ ကာကွယ်ရန်"""
    await asyncio.sleep(3) # Server တက်ပြီး ၃ စက္ကန့် စောင့်မည်
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": BIN_CHANNEL, "text": "🔄 Server Synced!"}
        
        async with aiohttp.ClientSession() as session:
            # Channel ထဲသို့ စာပို့၍ မှတ်ဉာဏ်နှိုးခြင်း
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                if data.get("ok"):
                    msg_id = data["result"]["message_id"]
                    # ပို့ထားသောစာကို ချက်ချင်း ပြန်ဖျက်ခြင်း
                    del_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
                    del_payload = {"chat_id": BIN_CHANNEL, "message_id": msg_id}
                    await session.post(del_url, json=del_payload)
                    print("✅ Channel Sync Complete! PeerIdInvalid prevented.")
                else:
                    print(f"⚠️ Sync Failed: {data}")
    except Exception as e:
        print(f"Error syncing channel: {e}")

# --- 2. File Extractor ---
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
        direct_link = f"{base_url}/download/{copied_msg.id}"
        
        reply_text = f"**File Name:** `{file_name}`\n\n**📥 Direct Download Link:**\n`{direct_link}`"
        await message.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        await message.reply_text(f"❌ **Error:** `{str(e)}`")

# --- 4. Web Server (Download Endpoint) ---
async def hello(request):
    return web.Response(text="Bot is awake and running smoothly!")

async def download_file(request):
    file_message_id = request.match_info['message_id']
    try:
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
    web_app.router.add_get('/download/{message_id}', download_file)
    
    runner = web.AppRunner(web_app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

# --- 5. Main Run Block ---
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(init_web())
    loop.create_task(sync_channel_peer()) # 👈 Auto-Sync ကို ဒီနေရာမှာ စတင်ခိုင်းထားပါတယ်
    print("Bot is starting...")
    app.run()
