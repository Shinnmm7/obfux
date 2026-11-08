import io
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, Form, Request, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import discord
from discord.ext import commands
from obfuscator import obfuscate

# ==========================================
# DISCORD BOT SETUP
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Discord Bot is online as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

@bot.tree.command(name="obf", description="Obfuscate a Lua script")
async def obfuscate_cmd(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(ephemeral=True)
    if not file.filename.endswith((".lua", ".txt")):
        await interaction.followup.send("❌ Please provide a `.lua` or `.txt` file.", ephemeral=True)
        return
    
    try:
        content = await file.read()
        source_code = content.decode('utf-8')
        obfuscated_code = obfuscate(source_code, strength="strong")
        
        new_file = discord.File(
            io.BytesIO(obfuscated_code.encode('utf-8')), 
            filename=f"obf_{file.filename}"
        )
        await interaction.followup.send("✅ Obfuscation complete!", file=new_file, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

# ==========================================
# FASTAPI WEB SERVER SETUP
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting Discord Bot in background...")
    # ⚠️ REPLACE THIS WITH YOUR REAL BOT TOKEN ⚠️
    bot_token = "YOUR_BOT_TOKEN_HERE"
    
    if bot_token != "YOUR_BOT_TOKEN_HERE":
        asyncio.create_task(bot.start(bot_token))
    else:
        print("⚠️ Bot token not set. Website will work, but bot will not start.")
    yield
    await bot.close()

app = FastAPI(title="Nebula Obfuscator", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # FIX: 'request' MUST be the first argument in newer Starlette versions
    return templates.TemplateResponse(request, "index.html")

@app.post("/obfuscate")
async def obfuscate_endpoint(file: UploadFile = File(...), strength: str = Form("strong")):
    content = await file.read()
    source = content.decode("utf-8")
    result = obfuscate(source, strength)
    
    buffer = io.BytesIO(result.encode("utf-8"))
    return StreamingResponse(
        buffer,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="obf_{file.filename}"'}
    )
