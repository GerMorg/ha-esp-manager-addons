from pathlib import Path
p=Path(__file__).with_name('main.py')
s=p.read_text()

# Fresh status is authoritative. Availability is useful for an immediate offline
# event, but can be absent after retained-topic cleanup while the device remains connected.
old="item['last_seen_age']=age;item['online']=explicit=='online' and age<=timeout;item['presence']='online' if item['online'] else 'offline';out.append(item)"
new="item['last_seen_age']=age;item['online']=age<=timeout;item['presence']='online' if item['online'] else 'offline';item['availability_state']=explicit or 'unknown';out.append(item)"
if old not in s:raise SystemExit('device list presence logic missing')
s=s.replace(old,new,1)
old_detail="item['last_seen_age']=age;item['online']=str(item.get('availability','')).lower()=='online' and age<=timeout;item['presence']='online' if item['online'] else 'offline';return item"
new_detail="item['last_seen_age']=age;item['online']=age<=timeout;item['presence']='online' if item['online'] else 'offline';item['availability_state']=str(item.get('availability','')).lower() or 'unknown';return item"
if old_detail not in s:raise SystemExit('device detail presence logic missing')
s=s.replace(old_detail,new_detail,1)

# Replace the main-page device renderer as a complete function instead of relying
# on an exact fragment that changed in earlier versions.
start=s.index('async function refreshDevices(){')
end=s.index('async function createP()',start)
main_refresh="""async function refreshDevices(){let ds=await api('api/devices');devices.innerHTML=ds.map(x=>`<div class=\"item\"><span style=\"color:${x.online?'#22c55e':'#ef4444'};font-size:18px\">●</span> <b>${x.device_id}</b> <b>${x.online?'Online':'Offline'}</b><br>${x.ip||''} ${x.ssid||''} RSSI ${x.rssi??'-'} | zuletzt vor ${x.last_seen_age}s</div>`).join('')||'Noch keine Geräte'}"""
s=s[:start]+main_refresh+s[end:]

s=s.replace('ESP Manager Dev 0.8.2-dev','ESP Manager Dev 0.8.3-dev').replace('ESP Manager Dev 0.8.2','ESP Manager Dev 0.8.3')
p.write_text(s)
