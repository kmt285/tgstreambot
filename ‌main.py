import os
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
import asyncio

# --- Configurations ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL"))
# Render ရဲ့ URL (ဥပမာ- https://my-bot.onrender.com)
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
    # 1. Forward the message to the BIN channel to get a reliable file ID
    try:
        forwarded_msg = await message.forward(chat_id=BIN_CHANNEL)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        forwarded_msg = await message.forward(chat_id=BIN_CHANNEL)
    except Exception as e:
        await message.reply_text(f"Error forwarding file: {e}")
        return

    # 2. Extract unique file ID from the forwarded message
    if forwarded_msg.document:
        file_id = forwarded_msg.document.file_id
        file_name = forwarded_msg.document.file_name
    elif forwarded_msg.video:
        file_id = forwarded_msg.video.file_id
        file_name = forwarded_msg.video.file_name # or provide a default
    elif forwarded_msg.audio:
        file_id = forwarded_msg.audio.file_id
        file_name = forwarded_msg.audio.file_name # or provide a default
    else:
        # Fallback if somehow not a document, video, or audio
        await message.reply_text("This file type is not supported.")
        return

    # 3. Construct the direct download link
    # We use the message_id from the *forwarded* message in the BIN channel
    direct_link = f"{URL}/download/{forwarded_msg.id}"

    # 4. Reply with the link
    reply_text = f"**File:** `{file_name}`\n\n**Direct Link:**\n`{direct_link}`"
    await message.reply_text(reply_text, parse_mode="markdown")

# --- Simple web server to keep the service alive on Render ---
from aiohttp import web

async def hello(request):
    return web.Response(text="Bot is running!")

# Direct download endpoint
async def download_file(request):
    file_message_id = request.match_info['message_id']
    
    # We need to get the actual file from the message_id in the BIN channel
    try:
        # We need a client instance to get the message
        # We can use the app instance directly as it's already started
        msg = await app.get_messages(chat_id=BIN_CHANNEL, message_ids=int(file_message_id))
        
        # Determine the file type to get correct file_id and attributes
        file_obj = msg.document or msg.video or msg.audio
        if not file_obj:
            raise web.HTTPNotFound(text="File not found in message.")
            
        file_id = file_obj.file_id
        file_name = getattr(file_obj, 'file_name', f"file_{file_message_id}")

        # Construct the response headers for downloading
        # This is the tricky part - we're streaming from TG
        response = web.StreamResponse()
        response.headers['Content-Disposition'] = f'attachment; filename="{file_name}"'
        response.headers['Content-Type'] = 'application/octet-stream' # Generic binary data
        
        await response.prepare(request)

        # Stream the media from TG and write to the response
        async for chunk in app.stream_media(file_id):
            await response.write(chunk)
            
        await response.write_eof()
        return response

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid message ID format.")
    except Exception as e:
        print(f"Error during download: {e}")
        raise web.HTTPInternalServerError(text=str(e))

async def init_web():
    web_app = web.Application()
    web_app.router.add_get('/', hello)
    web_app.router.add_get('/download/{message_id}', download_file)
    
    runner = web.AppRunner(web_app)
    await runner.setup()
    
    # Render assigns a PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

# --- Main Run Block ---
if __name__ == "__main__":
    # Run the web server in the background
    loop = asyncio.get_event_loop()
    loop.create_task(init_web())
    
    print("Bot is starting...")
    # Start the Pyrogram client
    app.run()
