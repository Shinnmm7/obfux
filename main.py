import io
import asyncio
import os
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI, UploadFile, Form, File, HTTPException
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
async def obfuscate_cmd(interaction: discord.Interaction, file: discord.Attachment,
                        strength: Literal["strong", "roblox"] = "strong"):
    await interaction.response.defer(ephemeral=True)
    
    if not file.filename.endswith((".lua", ".luau", ".txt")):
        await interaction.followup.send("❌ Please provide a `.lua`, `.luau`, or `.txt` file.", ephemeral=True)
        return
    
    try:
        content = await file.read()
        
        # Handle potential encoding issues
        try:
            source_code = content.decode('utf-8')
        except UnicodeDecodeError:
            await interaction.followup.send(
                "❌ **Encoding Error**: The file is not valid UTF-8. Please save it as UTF-8 and try again.", 
                ephemeral=True
            )
            return

        obfuscated_code = await asyncio.to_thread(obfuscate, source_code, strength)
        
        new_file = discord.File(
            io.BytesIO(obfuscated_code.encode('utf-8')), 
            filename=f"obf_{file.filename}"
        )
        await interaction.followup.send("✅ Obfuscation complete!", file=new_file, ephemeral=True)
        
    except ValueError as e:
        # This catches the specific "Lua syntax error" from the obfuscator
        error_msg = str(e)
        await interaction.followup.send(
            f"❌ **Cannot obfuscate file**.\n\n"
            f"🔍 **Parser Details**: `{error_msg}`\n\n"
            f"💡 Check the script syntax and the selected mode's supported features.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ **Unexpected Error**: {str(e)}", ephemeral=True)

# ==========================================
# FASTAPI WEB SERVER SETUP
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting Discord Bot in background...")
    bot_token = os.getenv("BOT_TOKEN", "")
    
    if bot_token:
        asyncio.create_task(bot.start(bot_token))
    else:
        print("⚠️ Bot token not set. Website will work, but bot will not start.")
    yield
    await bot.close()

app = FastAPI(title="Nebula Obfuscator", lifespan=lifespan)

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
        footer { margin-top: 20px; font-size: 0.8em; overflow-wrap: anywhere; }
        footer a { color: #b8a1ff; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ Nebula Obfuscator</h1>
        <form id="form" action="/obfuscate" method="POST" enctype="multipart/form-data">
            <div class="drop-zone" id="dropZone">
                <p>📁 Drop your .lua or .luau file here or click to browse</p>
                <input type="file" name="file" id="file" accept=".lua,.luau,.txt" hidden>
            </div>
            <select name="strength">
                <option value="light">🟢 Light (remove comments and whitespace)</option>
                <option value="medium">🟡 Medium (encoded source)</option>
                <option value="strong" selected>🔴 Strong (encoded, shuffled chunks)</option>
                <option value="roblox">🟣 Roblox Luau (VM-based)</option>
            </select>
            <p>Medium and strong require Lua load or loadstring. Obfuscation cannot keep client-side code secret.</p>
            <p>Roblox mode supports a subset of Luau, up to 64 KiB. Type annotations and interpolated strings are unsupported. Debug information and some environment behavior can change.</p>
            <button type="submit" id="btn">🚀 Obfuscate</button>
            <div id="status"></div>
        </form>
        <footer>Based on Prometheus by Elias Oelschner, <a href="https://github.com/prometheus-lua/Prometheus">https://github.com/prometheus-lua/Prometheus</a></footer>
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
            a.href = url; a.download = fd.get('strength') === 'roblox' ? 'obfuscated.luau' : 'obfuscated.lua'; a.click();
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
    try:
        source = content.decode("utf-8")
        result = await asyncio.to_thread(obfuscate, source, strength)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be valid UTF-8") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    
    buffer = io.BytesIO(result.encode("utf-8"))
    return StreamingResponse(
        buffer,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="obf_{file.filename}"'}
    )
