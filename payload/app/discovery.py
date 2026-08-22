from pathlib import Path
import json,re,yaml
TYPES={'sensor','binary_sensor','switch','number','cover'}
ID=re.compile(r'^[a-z0-9_]+$')
def load(path:Path):
 if not path.exists(): return []
 data=yaml.safe_load(path.read_text()) or []
 if not isinstance(data,list): raise ValueError('Discovery-Konfiguration muss eine Liste sein')
 return validate(data)
def validate(items):
 seen=set();out=[]
 for raw in items:
  x=dict(raw);typ=x.get('type');oid=x.get('id')
  if typ not in TYPES: raise ValueError(f'Ungültiger Typ: {typ}')
  if not isinstance(oid,str) or not ID.match(oid): raise ValueError(f'Ungültige ID: {oid}')
  uid=x.get('unique_id') or oid
  if uid in seen: raise ValueError(f'Doppelte unique_id: {uid}')
  seen.add(uid);x['unique_id']=uid;x.setdefault('name',oid.replace('_',' ').title())
  if typ=='number':
   x.setdefault('min',0);x.setdefault('max',100);x.setdefault('step',1)
  out.append(x)
 return out
def save(path:Path,items):
 items=validate(items);path.write_text(yaml.safe_dump(items,sort_keys=False,allow_unicode=True));return items
def cpp(s): return json.dumps(str(s),ensure_ascii=False)
def generate(items,out:Path):
 items=validate(items);lines=['#pragma once','#include <ESPManager.h>','inline void ESPManagerRegisterGenerated(){']
 for x in items:
  common=f'{cpp(x["id"])},{cpp(x["name"])},{cpp(x["unique_id"])}'
  t=x['type']
  if t=='sensor': lines.append(f'  ESPManager.registerSensor({common},{cpp(x.get("unit",""))},{cpp(x.get("device_class",""))},{cpp(x.get("state_class","measurement"))},{cpp(x.get("value_template",""))});')
  elif t=='binary_sensor': lines.append(f'  ESPManager.registerBinarySensor({common},{cpp(x.get("device_class",""))});')
  elif t=='switch': lines.append(f'  ESPManager.registerSwitch({common});')
  elif t=='number': lines.append(f'  ESPManager.registerNumber({common},{float(x["min"])},{float(x["max"])},{float(x["step"])},{cpp(x.get("unit",""))});')
  elif t=='cover': lines.append(f'  ESPManager.registerCover({common},{str(bool(x.get("position",True))).lower()});')
 lines+=['}',''];out.parent.mkdir(parents=True,exist_ok=True);out.write_text('\n'.join(lines));return out
