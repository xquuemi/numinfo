import os
import asyncio
import time
import json
import re
from aiohttp import web
from pyrogram import Client
from pyrogram.errors import FloodWait

# ================= CONFIG =================
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]
PORT = int(os.environ.get("PORT", 8080))

TARGETS = [
    "DT_USERTONUMBOT",
    "Num2inf0Bot"
]

WAIT_TIME = 35
# ==========================================

app = Client(
    name="railway_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

routes = web.RouteTableDef()
lock = asyncio.Lock()

# ---------------- HELPERS ----------------

def is_processing(text):
    t = text.lower()
    return any(k in t for k in ["searching", "processing", "please wait", "⏳"])

def extract_json(text):
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except:
        return None

def looks_final(text):
    keys = ["name", "mobile", "father", "address", "circle", "id"]
    t = text.lower()
    return any(k in t for k in keys)

async def send_to_targets(message):
    for target in TARGETS:
        try:
            print(f"Sending to {target}: {message}")
            msg = await app.send_message(target, message)
            return msg, target
        except FloodWait as f:
            await asyncio.sleep(f.value)
        except Exception as e:
            print("Target failed:", target, e)
            continue
    raise Exception("All targets failed")

async def collect_response(message):
    async with lock:
        sent, chat = await send_to_targets(message)
        sent_id = sent.id

    start = time.time()
    seen = set()

    while time.time() - start < WAIT_TIME:
        async for m in app.get_chat_history(chat, limit=150):
            if m.id <= sent_id or m.id in seen:
                continue
            seen.add(m.id)

            if not m.text:
                continue

            text = m.text.strip()

            if is_processing(text):
                continue

            js = extract_json(text)
            if js:
                return [{"type": "json", "data": js}]

            if looks_final(text):
                return [{"type": "text", "data": text}]

        await asyncio.sleep(1)

    return None

# ---------------- API ----------------

async def api_handler(req, cmd):
    q = req.query.get("number")
    mode = req.query.get("mode", "command")

    if not q:
        return web.json_response({"error": "number missing"})

    message = f"/{cmd} {q}" if mode == "command" else q

    try:
        data = await collect_response(message)
    except Exception as e:
        return web.json_response({"error": str(e)})

    if not data:
        return web.json_response({"query": q, "status": "timeout"})

    return web.json_response({
        "query": q,
        "status": "success",
        "responses": data
    })

@routes.get("/num")
async def num(req): return await api_handler(req, "num")

@routes.get("/aadhar")
async def aadhar(req): return await api_handler(req, "aadhar")

@routes.get("/family")
async def family(req): return await api_handler(req, "family")

@routes.get("/tg")
async def tg(req): return await api_handler(req, "tg")

# ---------------- HTML UI ----------------

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Railway Userbot</title>
<style>
body{margin:0;background:#020617;color:#fff;font-family:system-ui}
.wrap{max-width:420px;margin:auto;padding:16px}
h1{text-align:center;color:#22d3ee}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.btn{padding:14px;border-radius:14px;background:#000;border:1px solid #22d3ee;color:#22d3ee;text-align:center;font-weight:700}
.btn.active{background:#22d3ee;color:#000}
input,button{width:100%;margin-top:12px;padding:14px;border-radius:14px;border:none}
input{background:#000;color:#22d3ee;border:1px solid #22d3ee}
button{background:linear-gradient(90deg,#22d3ee,#3b82f6);font-weight:800}
.out{margin-top:14px;background:#000;padding:14px;border-radius:14px;border:1px solid #22d3ee44;white-space:pre-wrap;font-size:13px}
</style>
</head>
<body>
<div class="wrap">
<h1>⚡ USERBOT PANEL</h1>

<div class="grid">
<div class="btn active" onclick="setType('num',this)">📞 Number</div>
<div class="btn" onclick="setType('aadhar',this)">🪪 Aadhaar</div>
<div class="btn" onclick="setType('family',this)">👨‍👩‍👧 Family</div>
<div class="btn" onclick="setType('tg',this)">💬 Telegram</div>
</div>

<input id="q" placeholder="Enter value">
<button onclick="run()">RUN SEARCH</button>

<div class="out" id="out">Waiting…</div>
</div>

<script>
let TYPE="num";
function setType(t,el){
TYPE=t;
document.querySelectorAll('.btn').forEach(b=>b.classList.remove('active'));
el.classList.add('active');
}
function run(){
const q=document.getElementById("q").value;
if(!q)return;
fetch(`/${TYPE}?number=${encodeURIComponent(q)}`)
.then(r=>r.json())
.then(d=>document.getElementById("out").textContent=JSON.stringify(d,null,2))
.catch(()=>document.getElementById("out").textContent="ERROR");
}
</script>
</body>
</html>
"""

@routes.get("/")
async def index(_):
    return web.Response(text=INDEX_HTML, content_type="text/html")

# ---------------- MAIN ----------------

async def main():
    try:
        await app.start()
        print("Telegram connected")
    except Exception as e:
        print("Telegram login failed:", e)
        return

    webapp = web.Application()
    webapp.add_routes(routes)

    runner = web.AppRunner(webapp)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    print("Web running on port", PORT)

    while True:
        await asyncio.sleep(3600)

asyncio.run(main())
