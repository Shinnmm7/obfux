import io
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, Form, File
from fastapi.responses import HTMLResponse, StreamingResponse
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
    # Securely reads the token from Railway's Environment Variables
    bot_token = os.getenv("BOT_TOKEN", "")
    
    if bot_token:
        asyncio.create_task(bot.start(bot_token))
    else:
        print("⚠️ Bot token not set. Website will work, but bot will not start.")
    yield
    await bot.close()

app = FastAPI(title="Nebula Obfuscator", lifespan=lifespan)

# INLINE HTML: No templates folder needed!
HTML_CONTENT = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Nebula Obfuscator</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', sans-serif; }
        body { background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); color: white; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .container { background: rgba(20, 20, 40, 0.85); padding: 40px; border-radius: 20px; box-shadow: 0 0 40px rgba(138, 43, 226, 0.3); width: 90%; max-width: 600px; backdrop-filter: blur(10px); }
        h1 { text-align: center; margin-bottom: 30px; background: linear-gradient(90deg, #8a2be2, #00d4ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2.5em; }
        .drop-zone { border: 2px dashed #8a2be2; padding: 40px; text-align: center; border-radius: 15px; cursor: pointer; transition: all 0.3s; }
        .drop-zone:hover, .drop-zone.drag { background: rgba(138, 43, 226, 0.2); border-color: #00d4ff; }
        select, button { width: 100%; padding: 15px; margin-top: 20px; border-radius: 10px; border: none; font-size: 1em; cursor: pointer; }
        select { background: #1a1a2e; color: white; }
        button { background: linear-gradient(90deg, #8a2be2, #00d4ff); color: white; font-weight: bold; transition: transform 0.2s; }
        button:hover { transform: translateY(-2px); }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        #status { text-align: center; margin-top: 20px; color: #00d4ff; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ Nebula Obfuscator</h1>
        <form id="form" action="/obfuscate" method="POST" enctype="multipart/form-data">
            <div class="drop-zone" id="dropZone">
                <p>📁 Drop your .lua file here or click to browse</p>
                <input type="file" name="file" id="file" accept=".lua,.txt" hidden>
            </div>
            <select name="strength">
                <option value="light">🟢 Light (fast, variable rename only)</option>
                <option value="medium">🟡 Medium (+ junk code)</option>
                <option value="strong" selected>🔴 Strong (full protection)</option>
            </select>
            <button type="submit" id="btn">🚀 Obfuscate</button>
            <div id="status"></div>
        </form>
    </div>
    <script>
        const dz = document.getElementById('dropZone');
        const fi = document.getElementById('file');
        dz.onclick = () => fi.click();
        dz.ondragover = e => { e.preventDefault(); dz.classList.add('drag'); };
        dz.ondragleave = () => dz.classList.remove('drag');
        dz.ondrop = e => { e.preventDefault(); dz.classList.remove('drag'); fi.files = e.dataTransfer.files; dz.querySelector('p').textContent = '✅ ' + fi.files[0].name; };
        fi.onchange = () => dz.querySelector('p').textContent = '✅ ' + fi.files[0].name;
        
        document.getElementById('form').onsubmit = async e => {
            e.preventDefault();
            const btn = document.getElementById('btn');
            const status = document.getElementById('status');
            btn.disabled = true; status.textContent = '⏳ Obfuscating...';
            const fd = new FormData(e.target);
            const res = await fetch('/obfuscate', { method: 'POST', body: fd });
            if (!res.ok) { status.textContent = '❌ ' + await res.text(); btn.disabled = false; return; }
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = 'obfuscated.lua'; a.click();
            status.textContent = '✅ Done! File downloaded.';
            btn.disabled = false;
        };
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse(content=HTML_CONTENT)

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
