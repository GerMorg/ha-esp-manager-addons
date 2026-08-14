from pathlib import Path
p=Path(__file__).with_name('patch_v083.py')
s=p.read_text()
old='''main_refresh="""async function refreshDevices(){let ds=await api('api/devices');devices.innerHTML=ds.map(x=>`<div class=\\"item\\"><span style=\\"color:${x.online?'#22c55e':'#ef4444'};font-size:18px\\">●</span> <b>${x.device_id}</b> <b>${x.online?'Online':'Offline'}</b><br>${x.ip||''} ${x.ssid||''} RSSI ${x.rssi??'-'} | zuletzt vor ${x.last_seen_age}s</div>`).join('')||'Noch keine Geräte'}"""'''
new='''main_refresh="""async function refreshDevices(){{let ds=await api('api/devices');devices.innerHTML=ds.map(x=>`<div class=\\"item\\"><span style=\\"color:${{x.online?'#22c55e':'#ef4444'}};font-size:18px\\">●</span> <b>${{x.device_id}}</b> <b>${{x.online?'Online':'Offline'}}</b><br>${{x.ip||''}} ${{x.ssid||''}} RSSI ${{x.rssi??'-'}} | zuletzt vor ${{x.last_seen_age}}s</div>`).join('')||'Noch keine Geräte'}}"""'''
if old not in s:
 raise SystemExit('patch_v083 main_refresh block not found')
p.write_text(s.replace(old,new,1))
