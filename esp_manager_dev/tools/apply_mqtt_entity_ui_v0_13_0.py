#!/usr/bin/env python3
from pathlib import Path
import re, sys

root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
main=root/'esp_manager_dev/app/main.py'
if not main.exists(): raise SystemExit('esp_manager_dev/app/main.py fehlt')
s=main.read_text()
if 'MQTT_ENTITY_UI_V0130' in s:
 print('MQTT-Entitätenverwaltung ist bereits integriert');raise SystemExit(0)

# Imports needed by the standalone UI and HTML middleware.
s=s.replace('import hashlib, io, json, secrets, shutil, subprocess, threading, time, zipfile',
            'import hashlib, html, io, json, secrets, shutil, subprocess, threading, time, zipfile',1)
if 'from starlette.responses import Response' not in s:
 anchor='from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile'
 if anchor not in s: raise SystemExit('FastAPI-Importanker fehlt')
 s=s.replace(anchor,anchor+'\nfrom starlette.responses import Response',1)

helper=r'''
# MQTT_ENTITY_UI_V0130
MQTT_ENTITY_TYPES={"sensor","binary_sensor","switch","number","cover"}
def _cpp(v):return str(v or "").replace("\\","\\\\").replace('"','\\"').replace("\n","\\n")
def validate_mqtt_entities(items):
 if not isinstance(items,list):raise HTTPException(400,"entities muss eine Liste sein")
 if len(items)>32:raise HTTPException(400,"Maximal 32 Entitäten")
 out=[];ids=set();uids=set()
 for raw in items:
  if not isinstance(raw,dict):raise HTTPException(400,"Ungültige Entität")
  typ=str(raw.get("type","")).strip();eid=clean(str(raw.get("id","")));name=str(raw.get("name","")).strip();uid=str(raw.get("unique_id","")).strip()
  if typ not in MQTT_ENTITY_TYPES:raise HTTPException(400,f"Ungültiger Typ: {typ}")
  if not name or not uid:raise HTTPException(400,"Name und unique_id sind erforderlich")
  if eid in ids or uid in uids:raise HTTPException(400,"ID und unique_id müssen eindeutig sein")
  ids.add(eid);uids.add(uid)
  e={"type":typ,"id":eid,"name":name,"unique_id":uid}
  for k in ("unit","device_class","state_class","value_template"):e[k]=str(raw.get(k,"")).strip()
  if typ=="number":
   try:e.update(min=float(raw.get("min",0)),max=float(raw.get("max",100)),step=float(raw.get("step",1)))
   except Exception:raise HTTPException(400,"Number-Grenzen müssen Zahlen sein")
   if e["min"]>=e["max"] or e["step"]<=0:raise HTTPException(400,"Ungültige Number-Grenzen")
  if typ=="cover":e["position_supported"]=bool(raw.get("position_supported",True))
  out.append(e)
 return out
def render_mqtt_entities(p,m):
 es=validate_mqtt_entities(m.get("mqtt_entities",[]));inc=p/'include';inc.mkdir(parents=True,exist_ok=True)
 lines=["#pragma once","// Automatisch vom ESP Manager erzeugt. Nicht manuell bearbeiten.","inline void espManagerRegisterConfiguredEntities(ESPManagerClass& manager){"]
 for e in es:
  a=lambda k:_cpp(e.get(k,""));common=f'"{a("id")}","{a("name")}","{a("unique_id")}"'
  if e["type"]=="sensor":lines.append(f'  manager.registerSensor({common},"{a("unit")}","{a("device_class")}","{a("state_class") or "measurement"}","{a("value_template")}");')
  elif e["type"]=="binary_sensor":lines.append(f'  manager.registerBinarySensor({common},"{a("device_class")}");')
  elif e["type"]=="switch":lines.append(f'  manager.registerSwitch({common});')
  elif e["type"]=="number":lines.append(f'  manager.registerNumber({common},{e["min"]},{e["max"]},{e["step"]},"{a("unit")}");')
  elif e["type"]=="cover":lines.append(f'  manager.registerCover({common},{str(e.get("position_supported",True)).lower()});')
 lines.append("}");(inc/'ESPManagerEntities.h').write_text("\n".join(lines)+"\n")
 cpp=p/'lib'/'ESPManager'/'src'/'ESPManager.cpp'
 if not cpp.exists():return
 text=cpp.read_text()
 include='#include <ESPManagerEntities.h>\n'
 if include not in text:
  pos=text.find('\n',text.find('#include'))
  if pos<0:raise HTTPException(500,"ESPManager.cpp-Includeanker fehlt")
  text=text[:pos+1]+include+text[pos+1:]
 if 'espManagerRegisterConfiguredEntities(*this);' not in text:
  text,n=re.subn(r'(void\s+ESPManagerClass::begin\s*\(\s*\)\s*\{)',r'\1espManagerRegisterConfiguredEntities(*this);',text,count=1)
  if n!=1:raise HTTPException(500,"ESPManager.begin-Anker fehlt")
 cpp.write_text(text)
'''
# Insert helpers before copy_agent and extend copy_agent to generate header and patch copied agent.
match=re.search(r'(?m)^def copy_agent\s*\(p\):[^\n]*$',s)
if not match: raise SystemExit('copy_agent-Funktion nicht gefunden')
old=match.group(0)
new=helper+'\n'+old+'; render_mqtt_entities(p,yaml.safe_load((p/"espmanager.yaml").read_text()) or {})'
s=s[:match.start()]+new+s[match.end():]

routes=r"""

@app.get("/api/projects/{project}/mqtt-entities")
def get_mqtt_entities(project:str):
 m=meta(project);return {"project":clean(project),"entities":m.get("mqtt_entities",[])}

@app.put("/api/projects/{project}/mqtt-entities")
async def put_mqtt_entities(project:str,request:Request):
 body=await request.json();items=body.get("entities",body) if isinstance(body,(dict,list)) else body
 entities=validate_mqtt_entities(items);m=meta(project);m["mqtt_entities"]=entities;save_meta(project,m);render_mqtt_entities(pdir(project),m)
 return {"ok":True,"count":len(entities),"entities":entities}

@app.get("/mqtt-discovery")
def mqtt_discovery_ui(project:str=""):
 names=sorted(p.name for p in PROJECTS.iterdir() if p.is_dir()) if PROJECTS.exists() else []
 selected=clean(project) if project else (names[0] if names else "")
 options="".join(f'<option value="{html.escape(n)}" '+('selected' if n==selected else '')+f'>{html.escape(n)}</option>' for n in names)
 page='''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MQTT Discovery</title><style>
:root{color-scheme:dark}body{font-family:system-ui;margin:0;background:#0f172a;color:#e2e8f0}main{max-width:1200px;margin:auto;padding:24px}h1{margin:0 0 8px}.bar,.card{background:#1e293b;border:1px solid #334155;border-radius:14px;padding:16px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}label{font-size:12px;color:#94a3b8}input,select,button{box-sizing:border-box;width:100%;padding:10px;border-radius:9px;border:1px solid #475569;background:#0f172a;color:#fff}button{cursor:pointer;background:#2563eb;border:0;font-weight:700}.secondary{background:#475569}.danger{background:#b91c1c}.actions{display:flex;gap:10px}.actions button{width:auto}.hidden{display:none}.status{min-height:24px;color:#7dd3fc}code{color:#93c5fd}</style></head><body><main>
<h1>MQTT-Discovery-Entitäten</h1><p>Entitäten grafisch definieren. Beim nächsten Build erzeugt ESP Manager die passenden <code>register…()</code>-Aufrufe.</p>
<div class="bar"><label>Projekt</label><select id="project">'''+options+'''</select></div><div id="list"></div>
<div class="actions"><button id="add">Entität hinzufügen</button><button id="save">Speichern</button><button class="secondary" onclick="history.back()">Zurück</button></div><p class="status" id="status"></p>
</main><script>
const types=['sensor','binary_sensor','switch','number','cover'];let entities=[];const $=s=>document.querySelector(s),list=$('#list');
function esc(v){return String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function card(e={},i=entities.length){return `<div class="card" data-i="${i}"><div class="grid"><div><label>Typ</label><select data-k="type">${types.map(t=>`<option ${e.type===t?'selected':''}>${t}</option>`).join('')}</select></div><div><label>Interne ID</label><input data-k="id" value="${esc(e.id)}"></div><div><label>Name in Home Assistant</label><input data-k="name" value="${esc(e.name)}"></div><div><label>unique_id</label><input data-k="unique_id" value="${esc(e.unique_id)}"></div><div><label>Einheit</label><input data-k="unit" value="${esc(e.unit)}"></div><div><label>Device class</label><input data-k="device_class" value="${esc(e.device_class)}"></div><div><label>State class</label><input data-k="state_class" value="${esc(e.state_class||'measurement')}"></div><div><label>Value template</label><input data-k="value_template" value="${esc(e.value_template)}"></div><div><label>Minimum</label><input type="number" data-k="min" value="${e.min??0}"></div><div><label>Maximum</label><input type="number" data-k="max" value="${e.max??100}"></div><div><label>Schritt</label><input type="number" data-k="step" value="${e.step??1}"></div><div><label>Cover mit Position</label><select data-k="position_supported"><option value="true" ${e.position_supported!==false?'selected':''}>Ja</option><option value="false" ${e.position_supported===false?'selected':''}>Nein</option></select></div></div><div class="actions" style="margin-top:12px"><button class="danger" data-del>Entfernen</button></div></div>`}
function render(){list.innerHTML=entities.map(card).join('')||'<div class="card">Noch keine Entitäten definiert.</div>'}
function read(){return [...list.querySelectorAll('.card[data-i]')].map(c=>{const o={};c.querySelectorAll('[data-k]').forEach(x=>o[x.dataset.k]=x.type==='number'?Number(x.value):x.dataset.k==='position_supported'?x.value==='true':x.value);return o})}
async function load(){const p=$('#project').value;if(!p){entities=[];render();return}const r=await fetch(`api/projects/${encodeURIComponent(p)}/mqtt-entities`);const d=await r.json();entities=d.entities||[];render();$('#status').textContent=`${entities.length} Entitäten geladen`}
list.onclick=e=>{if(e.target.dataset.del!==undefined){entities=read();entities.splice(Number(e.target.closest('.card').dataset.i),1);render()}}
$('#add').onclick=()=>{entities=read();entities.push({type:'sensor',state_class:'measurement',min:0,max:100,step:1,position_supported:true});render()}
$('#save').onclick=async()=>{const p=$('#project').value;const r=await fetch(`api/projects/${encodeURIComponent(p)}/mqtt-entities`,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({entities:read()})});const d=await r.json();if(!r.ok){$('#status').textContent=d.detail||'Speichern fehlgeschlagen';return}entities=d.entities;render();$('#status').textContent=`Gespeichert: ${d.count} Entitäten. Projekt jetzt neu kompilieren.`}
$('#project').onchange=load;load();
</script></body></html>'''
 return Response(page,media_type="text/html")

@app.middleware("http")
async def mqtt_discovery_navigation(request:Request,call_next):
 response=await call_next(request)
 if request.url.path=="/mqtt-discovery" or "text/html" not in response.headers.get("content-type",""):return response
 body=b"".join([chunk async for chunk in response.body_iterator])
 link=b'<a href="mqtt-discovery" style="position:fixed;right:18px;bottom:18px;z-index:9999;background:#2563eb;color:white;padding:10px 14px;border-radius:999px;text-decoration:none;font:600 14px system-ui">MQTT Discovery</a>'
 body=body.replace(b"</body>",link+b"</body>")
 headers={k:v for k,v in response.headers.items() if k.lower()!="content-length"}
 return Response(body,status_code=response.status_code,headers=headers,media_type="text/html")
"""
s += routes
main.write_text(s)

# Bump dev version only; stable remains unchanged.
config=root/'esp_manager_dev/config.yaml'
if config.exists():
 c=config.read_text()
 if re.search(r'(?m)^version:',c):c=re.sub(r'(?m)^version:\s*.*$','version: 0.13.0-dev',c,count=1)
 else:
  lines=c.splitlines();lines.insert(2,'version: 0.13.0-dev');c='\n'.join(lines)+'\n'
 config.write_text(c)
print('Grafische MQTT-Entitätenverwaltung 0.13.0-dev integriert')
