from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import io
from obfuscator import obfuscate

app = FastAPI(title="Luraph-Style Obfuscator")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/obfuscate")
async def obfuscate_endpoint(
    file: UploadFile = File(...),
    strength: str = Form("strong")
):
    content = await file.read()
    source = content.decode("utf-8")
    
    result = obfuscate(source, strength)
    
    buffer = io.BytesIO(result.encode("utf-8"))
    return StreamingResponse(
        buffer,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="obf_{file.filename}"'}
    )

# Run: uvicorn main:main --host 0.0.0.0 --port 8000
