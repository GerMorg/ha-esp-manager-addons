from pathlib import Path
p=Path(__file__).with_name('main.py')
s=p.read_text()

# Under Home Assistant Ingress the hardware page needs a trailing slash so
# relative manifest.json resolves to /usb/<project>/manifest.json.
s=s.replace('href=\\"usb/${x.name}\\"', 'href=\\"usb/${x.name}/\\"')
s=s.replace("@app.get('/usb/{project}',response_class=HTMLResponse)", "@app.get('/usb/{project}/',response_class=HTMLResponse)")

# Add a visible manifest preflight result before the installer is used.
s=s.replace("<esp-web-install-button manifest='manifest.json'></esp-web-install-button>",
"<div id='manifestState'>Manifest wird geprüft ...</div><esp-web-install-button manifest='manifest.json'></esp-web-install-button>")
s=s.replace("setInterval(refreshStatus,5000);refreshStatus();</script>",
"async function checkManifest(){try{let r=await fetch('manifest.json',{cache:'no-store'});if(!r.ok)throw Error(await r.text());let m=await r.json();manifestState.textContent='Bereit: '+m.name+' '+m.version+' / '+m.builds[0].chipFamily}catch(e){manifestState.textContent='Manifest-Fehler: '+e.message}}setInterval(refreshStatus,5000);refreshStatus();checkManifest();</script>")

p.write_text(s)
