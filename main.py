import os
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode  # ဒီအချက်လေး အသစ်ပါလာပါတယ်
import asyncio

# --- Configurations ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL"))
URL = os.environ.get("URL")

# --- Initialize Client ---
app = Client(
    "simple_stream_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- Event Handler for Incoming Messages ---
@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def get_file_and_link(client: Client, message: Message):
    try:
        # ၁။ ဖိုင်ကို Channel ထဲ သိမ်းရန် Forward လုပ်ခြင်း
        forwarded_msg = await message.forward(chat_id=BIN_CHANNEL)
        
        # ၂။ ဖိုင်နာမည်ကို လုံခြုံစွာ ရယူခြင်း (နာမည်မရှိရင် Error မတက်အောင်)
        file_name = "Unknown_File"
        if message.document and getattr(message.document, 'file_name', None):
            file_name = message.document.file_name
        elif message.video and getattr(message.video, 'file_name', None):
            file_name = message.video.file_name
        elif message.audio and getattr(message.audio, 'file_name', None):
            file_name = message.audio.file_name

        # ၃။ Download Link တည်ဆောက်ခြင်း
        # (URL ထည့်ဖို့မေ့နေခဲ့ရင်တောင် Error မတက်အောင် ကာကွယ်ထားပါတယ်)
        base_url = URL.rstrip('/') if URL else "https://your-bot-url.onrender.com"
        direct_link = f"{base_url}/download/{forwarded_msg.id}"
        
        # ၄။ User ဆီ Link ပြန်ပို့ပေးခြင်း
        reply_text = f"**File Name:** `{file_name}`\n\n**📥 Direct Download Link:**\n`{direct_link}`"
        
        await message.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        # Error တက်ခဲ့ရင် အသံတိတ်မနေဘဲ Telegram ကနေ အကြောင်းကြားပေးပါမယ်
        await message.reply_text(f"❌ **Error ဖြစ်နေပါသည်:** `{str(e)}`")
        print(f"Error in get_file_and_link: {e}")

# --- Simple web server to keep the service alive on Render ---
from aiohttp import web

async def hello(request):
    return web.Response(text="Bot is running!")

async def download_file(request):
    file_message_id = request.match_info['message_id']
    try:
        msg = await app.get_messages(chat_id=BIN_CHANNEL, message_ids=int(file_message_id))
        file_obj = msg.document or msg.video or msg.audio
        
        if not file_obj:
            raise web.HTTPNotFound(text="File not found in message.")
            
        file_id = file_obj.file_id
        file_name = getattr(file_obj, 'file_name', f"file_{file_message_id}")

        response = web.StreamResponse()
        response.headers['Content-Disposition'] = f'attachment; filename="{file_name}"'
        response.headers['Content-Type'] = 'application/octet-stream'
        
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

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(init_web())
    print("Bot is starting...")
    app.run()
