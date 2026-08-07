from pathlib import Path
p=Path(__file__).with_name('main.py')
s=p.read_text()
old="""async function newF(){await api(`api/projects/${project}/files`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:newfile.value})});newfile.value='';refreshFiles()}"""
new="""async function newF(){
 if(!project){alert('Bitte zuerst ein Projekt öffnen.');return}
 let path=(newfile.value||'').trim();
 if(!path){alert('Bitte einen Dateipfad eingeben, zum Beispiel src/sensor.cpp.');return}
 if(!path.startsWith('src/')&&!path.startsWith('include/')&&!path.startsWith('lib/')){path='src/'+path}
 try{
  await api(`api/projects/${project}/files`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:path})});
  newfile.value='';await refreshFiles();await openF(path);
 }catch(e){alert('Datei konnte nicht angelegt werden: '+e.message)}
}"""
if old not in s: raise SystemExit('newF block not found')
s=s.replace(old,new)
# Add WiFi design information panel in the project UI without changing existing features.
needle='<h3>Programmdateien</h3>'
replace='''<details><summary>WLAN-Verhalten des Geräte-Agenten</summary><p class="muted">Erstinstallation: Wenn kein bekanntes WLAN erreichbar ist, öffnet der ESP den Access Point <code>ESPManager-&lt;Gerätename&gt;</code>. Verbinde dich damit und öffne bei Bedarf <code>192.168.4.1</code>. Im normalen Betrieb ist für zehn Minuten nach jedem Start ein Konfigurationsportal über die lokale IP erreichbar. Bei längerem WLAN-Ausfall öffnet der ESP automatisch erneut den Fallback-Access-Point. Das Geräteprogramm läuft dabei weiter.</p></details><h3>Programmdateien</h3>'''
if needle not in s: raise SystemExit('program files heading not found')
s=s.replace(needle,replace,1)

# Keep agent dependencies automatic and independent from the user's expert library list.
old_dep = "if m['libraries']:text+='lib_deps =\\n'+'\\n'.join('  '+x for x in m['libraries'])+'\\n'"
new_dep = "required_libs=['tzapu/WiFiManager@^2.0.17','knolleary/PubSubClient@^2.8','bblanchon/ArduinoJson@^7.2.1'];all_libs=required_libs+[x for x in m['libraries'] if x not in required_libs];text+='lib_deps =\\n'+'\\n'.join('  '+x for x in all_libs)+'\\n'"
if old_dep not in s: raise SystemExit('render_pio dependency block not found')
s=s.replace(old_dep,new_dep)
p.write_text(s)
