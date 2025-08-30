#!/usr/bin/env python3
# magisort_web.py (v2)
import hashlib
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Iterable, Optional, Tuple

import requests
from flask import Flask, request, jsonify, render_template_string, send_from_directory

# -------------------- Config --------------------
DB_PATH = "magisort.db"
DEFAULT_PILES = 12
DEFAULT_VBINS = 1024
DEFAULT_SALT = "2025-v1"
HTTP_TIMEOUT = 15

SCRY_NAMED_URL = "https://api.scryfall.com/cards/named"
SCRY_SETNUM_URL = "https://api.scryfall.com/cards/{code}/{number}"
SCRY_AUTOCOMPLETE_URL = "https://api.scryfall.com/cards/autocomplete"

app = Flask(__name__)
# If you previously hit 403, uncomment the line below:
app.config["TRUSTED_HOSTS"] = ["localhost", "127.0.0.1", "::1"]

# -------------------- Hashing / Piles --------------------
def norm(s: str) -> str:
    return "".join(c.lower() for c in s if c.isalnum() or c.isspace()).strip()

def h32(payload: str) -> int:
    return int(hashlib.blake2s(payload.encode("utf-8"), digest_size=4).hexdigest(), 16)

def canonical_colors(colors: Iterable[str]) -> str:
    return "".join(sorted(colors)) if colors else "C"

def compute_pile_index(*, name: str, mana_value: float, colors: Iterable[str], type_line: str,
                       K: int, virtual_bins: int, salt: str) -> int:
    name_n = norm(name)
    type_n = norm(type_line)
    colors_n = canonical_colors(colors)

    h_name  = h32(f"{salt}|name:{name_n}")
    h_type  = h32(f"{salt}|type:{type_n}")
    h_color = h32(f"{salt}|color:{colors_n}")
    h_mv    = h32(f"{salt}|mv:{int(mana_value) if mana_value is not None else -1}")

    h = (h_name ^ (h_type << 1) ^ (h_color << 2) ^ (h_mv << 3)) & 0xFFFFFFFF
    vbin = h % virtual_bins
    return vbin % K

# -------------------- DB --------------------
SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  set_code TEXT,
  collector_number TEXT,
  scryfall_id TEXT,
  colors TEXT,
  mana_value REAL,
  type_line TEXT,
  pile_index INTEGER NOT NULL,
  image_url TEXT,
  added_at TEXT NOT NULL
);
"""

def open_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _col_exists(conn, table: str, column: str) -> bool:
    r = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in r)

def init_db_if_needed():
    first_time = not Path(DB_PATH).exists()
    conn = open_db()
    with conn:
        conn.executescript(SCHEMA_SQL)
        # Migration: add image_url if missing (for older DBs)
        if not _col_exists(conn, "cards", "image_url"):
            conn.execute("ALTER TABLE cards ADD COLUMN image_url TEXT")
        if first_time or conn.execute("SELECT 1 FROM meta WHERE key='piles'").fetchone() is None:
            set_meta(conn, "piles", str(DEFAULT_PILES))
            set_meta(conn, "virtual_bins", str(DEFAULT_VBINS))
            set_meta(conn, "salt", DEFAULT_SALT)
            set_meta(conn, "created_at", datetime.utcnow().isoformat(timespec="seconds") + "Z")
    conn.close()

def get_meta(conn, key: str, default: Optional[str] = None) -> Optional[str]:
    r = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default

def set_meta(conn, key: str, value: str):
    conn.execute(
        "INSERT INTO meta(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value)
    )

def read_config(conn) -> Tuple[int, int, str]:
    piles = int(get_meta(conn, "piles", str(DEFAULT_PILES)))
    vbins = int(get_meta(conn, "virtual_bins", str(DEFAULT_VBINS)))
    salt  = get_meta(conn, "salt", DEFAULT_SALT)
    return piles, vbins, salt

def insert_card(conn, card: dict, pile_index: int, image_url: Optional[str]) -> int:
    name = card.get("name")
    set_code = card.get("set")
    collector_number = card.get("collector_number")
    scryfall_id = card.get("id")
    colors = canonical_colors(card.get("color_identity") or card.get("colors") or [])
    mana_value = card.get("cmc", card.get("mana_value"))
    type_line = card.get("type_line")
    added_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    cur = conn.execute(
        """INSERT INTO cards
           (name, set_code, collector_number, scryfall_id, colors, mana_value, type_line, pile_index, image_url, added_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (name, set_code, str(collector_number) if collector_number is not None else None,
         scryfall_id, colors, mana_value, type_line, pile_index, image_url, added_at)
    )
    return cur.lastrowid

# -------------------- Scryfall helpers --------------------
def fetch_card_scryfall(name: Optional[str]=None, set_code: Optional[str]=None, number: Optional[str]=None) -> dict:
    if set_code and number:
        url = SCRY_SETNUM_URL.format(code=set_code.lower(), number=str(number))
        r = requests.get(url, timeout=HTTP_TIMEOUT)
    else:
        if not name:
            raise ValueError("Provide name or set+number")
        r = requests.get(SCRY_NAMED_URL, params={"fuzzy": name}, timeout=HTTP_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"Scryfall error {r.status_code}: {r.text}")
    data = r.json()
    if data.get("object") == "error":
        raise RuntimeError(data.get("details", "Scryfall error"))
    return data

def autocomplete_names(prefix: str) -> list[str]:
    if not prefix.strip():
        return []
    r = requests.get(SCRY_AUTOCOMPLETE_URL, params={"q": prefix, "include_extras": "true"}, timeout=HTTP_TIMEOUT)
    if r.status_code != 200:
        return []
    return r.json().get("data", [])[:20]

def extract_image_url(card: dict) -> Optional[str]:
    if "image_uris" in card and card["image_uris"]:
        return card["image_uris"].get("normal") or card["image_uris"].get("large")
    faces = card.get("card_faces") or []
    for f in faces:
        if f.get("image_uris"):
            return f["image_uris"].get("normal") or f["image_uris"].get("large")
    return None

def card_key_fields(card: dict) -> Tuple[str, float, Iterable[str], str]:
    name = card.get("name", "").split(" // ")[0]
    mv = card.get("cmc", card.get("mana_value"))
    colors = card.get("color_identity") or card.get("colors") or []
    type_line = card.get("type_line", "")
    return name, mv, colors, type_line

# -------------------- Routes: UI --------------------
INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>MagiSort (Web) — MTG Value-based Pile Sorter</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root { --bg:#0f1222; --panel:#171b34; --text:#eef1ff; --muted:#a8b0d6; --accent:#6aa2ff; }
    * { box-sizing: border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; }
    header { padding:16px 20px; background:linear-gradient(90deg, #121634, #1a2046); border-bottom:1px solid #2a2f55;}
    h1 { margin:0; font-size:18px; letter-spacing:0.5px; }
    .container { display:flex; gap:16px; padding:16px; }
    .left, .right { background:var(--panel); border:1px solid #2a2f55; border-radius:12px; padding:16px; }
    .left { flex: 1.6; min-width: 520px; }
    .right { flex: 1; min-width: 360px; }
    .row { display:flex; gap:8px; align-items:center; margin-bottom:8px; }
    input, select, button { background:#0f1330; color:var(--text); border:1px solid #2a2f55; border-radius:8px; padding:10px 12px; }
    button { background: var(--accent); color:#0b1024; border:none; font-weight:600; cursor:pointer; }
    button:disabled { opacity:0.6; cursor:not-allowed; }
    .grid { display:grid; grid-template-columns: 110px 1fr 70px 90px 70px 80px; gap:6px; padding:8px; }
    .grid.header { font-weight:700; color:var(--muted); }
    .rowitem { padding:8px 10px; border:1px solid #2a2f55; border-radius:8px; background:#101437; }
    .rowitem.clickable { cursor:pointer; color:#9ec0ff; }
    .stats { white-space:pre-wrap; background:#101437; border:1px solid #2a2f55; border-radius:8px; padding:12px; min-height:100px; }
    .suggest { position:relative; }
    .suggest-list { position:absolute; top:40px; left:0; right:0; background:#0f1330; border:1px solid #2a2f55; border-radius:8px; max-height:220px; overflow:auto; z-index:20; }
    .suggest-list div { padding:8px 10px; cursor:pointer; }
    .suggest-list div:hover { background:#1a1f47; }
    .preview { text-align:center; }
    .badge { display:inline-block; margin-top:8px; padding:6px 10px; border-radius:999px; background:#0f1330; border:1px solid #2a2f55; }
    .muted { color:var(--muted); font-size:12px; }
    .del { background:#ff6a6a; color:#240b0b; border:none; padding:8px 10px; border-radius:8px; cursor:pointer; }
    img.card { width: 100%; max-width: 360px; border-radius:12px; border:1px solid #2a2f55; }
    @media (max-width: 1020px) { .container { flex-direction: column; } .left, .right { min-width: auto; } }
  </style>
</head>
<body>
<header><h1>MagiSort (Web) — MTG Value-based Pile Sorter</h1></header>
<div class="container">
  <div class="left">
    <div class="row">
      <div class="suggest" style="flex:1">
        <input id="name" placeholder="Type a card name…" autocomplete="off">
        <div id="suggestions" class="suggest-list" style="display:none;"></div>
      </div>
      <input id="set" placeholder="SET (opt)" style="width:110px">
      <input id="num" placeholder="No. (opt)" style="width:110px">
      <button id="addBtn" onclick="addCard()">Add Card</button>
    </div>

    <div class="row">
      <label>View pile:</label>
      <select id="pileSel" onchange="loadPile()"></select>
      <button onclick="refreshStats()">Refresh Stats</button>
    </div>

    <div class="stats" id="statsBox">Loading…</div>

    <div style="margin-top:12px;">
      <div class="grid header">
        <div>ID</div><div>Name</div><div>Set</div><div>Number</div><div>MV</div><div>Colors</div>
      </div>
      <div id="listBox"></div>
    </div>
  </div>

  <div class="right">
    <div class="preview">
      <div class="muted">Card Preview</div>
      <img id="cardImg" class="card" alt="" />
      <div class="badge" id="pileBadge">Pile: -</div>
    </div>
    <div style="margin-top:12px;">
      <div class="stats" id="infoBox">Select a card to preview.</div>
      <div style="margin-top:8px; text-align:right;">
        <button class="del" id="removeBtn" onclick="removeSelected()" disabled>Remove Selected</button>
      </div>
    </div>
  </div>
</div>

<script>
let selectedId = null;
let selectedPile = 0;
let suggestTimer = null;

async function api(path, opts={}) {
  const res = await fetch(path, Object.assign({headers:{'Content-Type':'application/json'}}, opts));
  let payload = null;
  try { payload = await res.json(); } catch(e) { payload = { error: 'Non-JSON response' }; }
  if (!res.ok) {
    const msg = (payload && payload.error) ? payload.error : ('HTTP ' + res.status);
    throw new Error(msg);
  }
  return payload;
}

function setSuggestions(items){
  const box = document.getElementById('suggestions');
  box.innerHTML = '';
  if (!items || items.length === 0) { box.style.display='none'; return; }
  items.forEach(n=>{
    const div = document.createElement('div');
    div.textContent = n;
    div.onclick = ()=>{
      document.getElementById('name').value = n;
      box.style.display='none';
    };
    box.appendChild(div);
  });
  box.style.display='block';
}

document.getElementById('name').addEventListener('input', (e)=>{
  clearTimeout(suggestTimer);
  const q = e.target.value.trim();
  if (!q) { setSuggestions([]); return; }
  suggestTimer = setTimeout(async ()=>{
    try{
      const data = await api('/api/autocomplete?q=' + encodeURIComponent(q));
      setSuggestions(data.suggestions || []);
    }catch(_){ setSuggestions([]); }
  }, 180);
});

async function init() {
  await refreshStats();
  await populatePileSelect();
  await loadPile();
}
async function refreshStats(){
  const s = await api('/api/stats');
  document.getElementById('statsBox').textContent =
    `Total cards: ${s.total}\nPiles: ${s.piles} | Virtual bins: ${s.virtual_bins} | Salt: ${s.salt}\n\nPer-pile counts:\n` +
    s.per_pile.map(([i,c])=>`  Pile ${i}: ${c}`).join('\\n') +
    `\\n\\nSelected pile ${selectedPile} color mix: ${s.color_mix[selectedPile] || '-'}`;
}
async function populatePileSelect(){
  const s = await api('/api/stats');
  const sel = document.getElementById('pileSel');
  sel.innerHTML = '';
  for (let i=0;i<s.piles;i++){
    const opt = document.createElement('option');
    opt.value = i; opt.textContent = i;
    sel.appendChild(opt);
  }
  sel.value = selectedPile;
}
async function loadPile(){
  const val = document.getElementById('pileSel').value;
  selectedPile = parseInt(val || '0');
  const data = await api('/api/list?pile=' + selectedPile);
  const box = document.getElementById('listBox');
  box.innerHTML = '';
  data.cards.forEach(row=>{
    const wrap = document.createElement('div');
    wrap.className = 'grid';
    wrap.style.alignItems = 'center';
    wrap.onclick = ()=>preview(row.id); // whole row clickable
    wrap.innerHTML = `
      <div class="rowitem">${row.id}</div>
      <div class="rowitem clickable">${row.name}</div>
      <div class="rowitem">${(row.set||'').toUpperCase()}</div>
      <div class="rowitem">${row.collector_number||''}</div>
      <div class="rowitem">${row.mana_value ?? ''}</div>
      <div class="rowitem">${row.colors || 'C'}</div>
    `;
    box.appendChild(wrap);
  });
  document.getElementById('pileBadge').textContent = 'Pile: -';
  document.getElementById('cardImg').src = '';
  document.getElementById('infoBox').textContent = 'Select a card to preview.';
  selectedId = null;
  document.getElementById('removeBtn').disabled = true;
  await refreshStats();
}

async function addCard(){
  const name = document.getElementById('name').value.trim();
  const setc = document.getElementById('set').value.trim();
  const num  = document.getElementById('num').value.trim();
  if (!name && !(setc && num)){ alert('Type a card name or provide set + number.'); return; }
  document.getElementById('addBtn').disabled = true;
  try{
    const body = JSON.stringify({ name: name || null, set: setc || null, number: num || null });
    const res = await api('/api/add', { method:'POST', body });
    alert(`Added [${res.id}] ${res.name} → Pile ${res.pile}`);
    document.getElementById('name').value=''; document.getElementById('set').value=''; document.getElementById('num').value='';
    await loadPile();
  }catch(e){
    alert('Add failed: ' + e.message);
    // Still reload – in case insert succeeded but response failed
    try { await loadPile(); } catch(_) {}
  }finally{
    document.getElementById('addBtn').disabled = false;
  }
}

async function preview(id){
  try{
    const res = await api('/api/preview/' + id);
    selectedId = id;
    document.getElementById('removeBtn').disabled = false;
    document.getElementById('cardImg').src = res.image_url || '';
    document.getElementById('pileBadge').textContent = 'Pile: ' + res.pile;
    document.getElementById('infoBox').textContent =
      `Name: ${res.name}
Set: ${(res.set||'-').toUpperCase()}  No: ${res.collector_number||'-'}
Mana Value: ${res.mana_value}
Colors: ${res.colors||'C'}
Type: ${res.type_line}
Scryfall ID: ${res.scryfall_id}`;
  }catch(e){
    alert('Preview failed: ' + e.message);
  }
}

async function removeSelected(){
  if (!selectedId){ alert('Select a card first.'); return; }
  if (!confirm('Remove card id ' + selectedId + '?')) return;
  try{
    await api('/api/remove', { method:'POST', body: JSON.stringify({ id: selectedId }) });
    await loadPile();
  }catch(e){
    alert('Remove failed: ' + e.message);
  }
}

init();
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

# -------------------- Routes: API --------------------
@app.route("/api/autocomplete")
def api_autocomplete():
    q = request.args.get("q", "").strip()
    try:
        return jsonify({"suggestions": autocomplete_names(q)})
    except Exception as e:
        return jsonify({"suggestions": [], "error": str(e)}), 200

@app.route("/api/add", methods=["POST"])
def api_add():
    try:
        data = request.get_json(force=True, silent=True) or {}
        name  = data.get("name")
        setc  = data.get("set")
        num   = data.get("number")
        if not name and not (setc and num):
            return jsonify({"error": "Require name or set+number"}), 400

        card = fetch_card_scryfall(name=name, set_code=setc, number=num)
        nm, mv, colors, type_line = card_key_fields(card)
        img_url = extract_image_url(card)  # capture now; no need to re-fetch later
        conn = open_db()
        piles, vbins, salt = read_config(conn)
        pile = compute_pile_index(name=nm, mana_value=mv, colors=colors, type_line=type_line,
                                  K=piles, virtual_bins=vbins, salt=salt)
        with conn:
            rowid = insert_card(conn, card, pile, img_url)
        return jsonify({
            "id": rowid,
            "name": card.get("name"),
            "set": card.get("set"),
            "collector_number": card.get("collector_number"),
            "scryfall_id": card.get("id"),
            "pile": pile
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/remove", methods=["POST"])
def api_remove():
    try:
        data = request.get_json(force=True, silent=True) or {}
        cid = data.get("id")
        if not cid:
            return jsonify({"error": "Missing id"}), 400
        conn = open_db()
        with conn:
            cur = conn.execute("DELETE FROM cards WHERE id=?", (cid,))
            ok = cur.rowcount > 0
        return jsonify({"removed": ok}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/list")
def api_list():
    try:
        pile = int(request.args.get("pile", "0"))
    except ValueError:
        pile = 0
    conn = open_db()
    rows = conn.execute(
        "SELECT id, name, set_code AS set, collector_number, mana_value, colors, type_line "
        "FROM cards WHERE pile_index = ? ORDER BY name COLLATE NOCASE",
        (pile,)
    ).fetchall()
    cards = [{
        "id": r["id"], "name": r["name"], "set": r["set"],
        "collector_number": r["collector_number"], "mana_value": r["mana_value"],
        "colors": r["colors"], "type_line": r["type_line"]
    } for r in rows]
    return jsonify({"cards": cards}), 200

@app.route("/api/preview/<int:cid>")
def api_preview(cid: int):
    try:
        conn = open_db()
        r = conn.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
        if not r:
            return jsonify({"error": "Not found"}), 404
        # No external re-fetch — use stored fields for speed & reliability
        return jsonify({
            "id": r["id"],
            "name": r["name"],
            "set": r["set_code"],
            "collector_number": r["collector_number"],
            "scryfall_id": r["scryfall_id"],
            "mana_value": r["mana_value"],
            "colors": r["colors"] or "C",
            "type_line": r["type_line"],
            "pile": r["pile_index"],
            "image_url": r["image_url"]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/stats")
def api_stats():
    try:
        conn = open_db()
        piles, vbins, salt = read_config(conn)
        total = conn.execute("SELECT COUNT(*) AS c FROM cards").fetchone()["c"]
        per = []
        cmix = {}
        for i in range(piles):
            c = conn.execute("SELECT COUNT(*) AS c FROM cards WHERE pile_index=?", (i,)).fetchone()["c"]
            per.append((i, c))
            rows = conn.execute(
                "SELECT colors, COUNT(*) AS c FROM cards WHERE pile_index=? GROUP BY colors ORDER BY c DESC",
                (i,)
            ).fetchall()
            cmix[i] = ", ".join(f"{(rr['colors'] or 'C')}:{rr['c']}" for rr in rows) or "-"
        return jsonify({"total": total, "piles": piles, "virtual_bins": vbins, "salt": salt,
                        "per_pile": per, "color_mix": cmix}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download-db")
def download_db():
    return send_from_directory(".", DB_PATH, as_attachment=True)

# -------------------- Main --------------------
if __name__ == "__main__":
    init_db_if_needed()
    app.run(host="127.0.0.1", port=5000, debug=True)
