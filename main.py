import os
import asyncio
import mimetypes
from urllib.parse import quote
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from aiohttp import web

# --- Configurations ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL"))
URL = os.environ.get("URL")

app = Client("simple_stream_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ဖိုင်နာမည်နဲ့ အမျိုးအစားကို အလိုအလျောက် စစ်ဆေးပေးမည့် Function
def get_filename_and_mime(message: Message):
    file_obj = message.document or message.video or message.audio
    if not file_obj:
        return "Unknown_Media.bin", "application/octet-stream"
        
    file_name = getattr(file_obj, "file_name", None)
    mime_type = getattr(file_obj, "mime_type", "application/octet-stream")
    
    # Telegram က ဖိုင်နာမည် မပေးခဲ့ရင် Extension ကို အလိုအလျောက် ခန့်မှန်းမည်
    if not file_name:
        ext = mimetypes.guess_extension(mime_type) or ".bin"
        file_name = f"Telegram_File_{message.id}{ext}"
        
    return file_name, mime_type

@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def get_file_and_link(client: Client, message: Message):
    try:
        # ၁။ Channel သို့ Copy ကူးခြင်း
        copied_msg = await message.copy(chat_id=BIN_CHANNEL)
        
        # ၂။ ဖိုင်နာမည်ကို စစ်ဆေးရယူခြင်း
        file_name, _ = get_filename_and_mime(message)

        # ၃။ Link ထုတ်ပေးခြင်း
        base_url = URL.rstrip('/') if URL else "https://your-bot-url.onrender.com"
        direct_link = f"{base_url}/download/{copied_msg.id}"
        
        # ၄။ စာပြန်ပို့ခြင်း
        reply_text = f"**File Name:** `{file_name}`\n\n**📥 Direct Download Link:**\n`{direct_link}`"
        await message.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        await message.reply_text(f"❌ **Error:** `{str(e)}`")

# --- Web Server (Download ဆွဲမည့်အပိုင်း) ---
async def hello(request):
    return web.Response(text="Bot is awake and running smoothly!")

async def download_file(request):
    file_message_id = request.match_info['message_id']
    try:
        # Channel ထဲမှ ဖိုင်ကို သွားရှာခြင်း
        msg = await app.get_messages(chat_id=BIN_CHANNEL, message_ids=int(file_message_id))
        file_obj = msg.document or msg.video or msg.audio
        
        if not file_obj:
            raise web.HTTPNotFound(text="File not found in message.")
            
        file_id = file_obj.file_id
        file_name, mime_type = get_filename_and_mime(msg)

        response = web.StreamResponse()
        
        # အရေးကြီးဆုံးပြင်ဆင်ချက်: Browser က ဖိုင်နာမည်ကို မှန်ကန်စွာဖတ်နိုင်ရန် Quote သုံးခြင်း
        safe_filename = quote(file_name)
        response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{safe_filename}"
        response.headers['Content-Type'] = mime_type
        
        await response.prepare(request)

        # Telegram မှတစ်ဆင့် User ဆီသို့ တိုက်ရိုက် Stream လွှတ်ပေးခြင်း
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

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(init_web())
    print("Bot is starting...")
    app.run()
