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

TARGETS = [
    "LegendxInfoChattingGc",
    "Num2inf0Bot"
]

WAIT_TIME = 40
PORT = int(os.environ.get("PORT", 8080))
# ==========================================

app = Client(
    name="userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

routes = web.RouteTableDef()
lock = asyncio.Lock()

# ---------------- FILTER ----------------

def deep_clean(data):
    remove_keys = [
        "developer",
        "requested_by",
        "command",
        "credit",
        "credits"
    ]

    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if k.lower() in remove_keys:
                continue
            cleaned[k] = deep_clean(v)
        return cleaned

    elif isinstance(data, list):
        return [deep_clean(i) for i in data]

    elif isinstance(data, str):
        # remove @username
        return re.sub(r"@\w+", "", data)

    return data


def extract_json(text):
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except:
        return None


def is_processing(text):
    t = text.lower()
    return any(k in t for k in ["searching", "processing", "please wait", "⏳"])


async def send_command(cmd):
    for target in TARGETS:
        try:
            msg = await app.send_message(target, cmd)
            return msg, target
        except FloodWait as f:
            await asyncio.sleep(f.value)
        except:
            continue
    raise Exception("No target accepted command")


async def collect_response(cmd):
    async with lock:
        sent, chat = await send_command(cmd)
        sent_id = sent.id

    start = time.time()

    while time.time() - start < WAIT_TIME:
        async for m in app.get_chat_history(chat, limit=200):
            if m.id <= sent_id:
                continue

            if not m.text:
                continue

            text = m.text.strip()

            if is_processing(text):
                continue

            # JSON case
            js = extract_json(text)
            if js:
                cleaned = deep_clean(js)
                return [{
                    "type": "json",
                    "data": cleaned
                }]

            # Plain text case
            cleaned_text = re.sub(r"@\w+", "", text)
            return [{
                "type": "text",
                "data": cleaned_text
            }]

        await asyncio.sleep(0.4)

    return None


# ---------------- API ROUTES ----------------

async def api_handler(req, cmd):
    q = req.query.get("number")
    if not q:
        return web.json_response({"error": "number missing"})

    data = await collect_response(f"/{cmd} {q}")

    if not data:
        return web.json_response({
            "query": q,
            "status": "timeout"
        })

    return web.json_response({
        "query": q,
        "status": "success",
        "responses": data
    })


@routes.get("/num")
async def num(req):
    return await api_handler(req, "num")


@routes.get("/aadhar")
async def aadhar(req):
    return await api_handler(req, "aadhar")


@routes.get("/family")
async def family(req):
    return await api_handler(req, "family")


@routes.get("/tg")
async def tg(req):
    return await api_handler(req, "tg")


# ---------------- BASIC UI ----------------

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rio Panel</title>
<style>
body{background:#000;color:#0ff;font-family:system-ui;padding:20px}
input,button{width:100%;padding:12px;margin-top:10px;border-radius:10px;border:none}
input{background:#111;color:#0ff}
button{background:#0ff;color:#000;font-weight:700}
pre{background:#111;padding:15px;margin-top:15px;white-space:pre-wrap}
</style>
</head>
<body>
<h2>⚡ Userbot Panel</h2>
<select id="type">
<option value="num">Number</option>
<option value="aadhar">Aadhar</option>
<option value="family">Family</option>
<option value="tg">Telegram</option>
</select>
<input id="q" placeholder="Enter value">
<button onclick="run()">Search</button>
<pre id="out">Waiting...</pre>
<script>
function run(){
let t=document.getElementById("type").value;
let q=document.getElementById("q").value;
if(!q)return;
document.getElementById("out").textContent="Loading...";
fetch(`/${t}?number=${encodeURIComponent(q)}`)
.then(r=>r.json())
.then(d=>document.getElementById("out").textContent=
JSON.stringify(d,null,2));
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
    await app.start()
    print("Telegram connected")

    webapp = web.Application()
    webapp.add_routes(routes)

    runner = web.AppRunner(webapp)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    print("Web running")

    while True:
        await asyncio.sleep(3600)

asyncio.run(main())
