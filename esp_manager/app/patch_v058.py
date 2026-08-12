from pathlib import Path

p = Path(__file__).with_name('main.py')
s = p.read_text()

# Home Assistant Ingress may not preserve the add-on prefix when following the
# automatic slash redirect. Serve both URL forms directly, without a 307.
old_route = "@app.get('/usb/{project}/',response_class=HTMLResponse)\ndef usb_test_page(project):"
new_route = "@app.get('/usb/{project}',response_class=HTMLResponse,include_in_schema=False)\n@app.get('/usb/{project}/',response_class=HTMLResponse)\ndef usb_test_page(project):"
if old_route not in s:
    raise SystemExit('Expected trailing-slash USB route was not found')
s = s.replace(old_route, new_route, 1)

# Keep project links on the no-slash form now that both forms are handled.
s = s.replace('href=\\"usb/${x.name}/\\"', 'href=\\"usb/${x.name}\\"')

# Use an explicit project-relative manifest URL generated from the current
# browser path, independent of whether the page URL ends in a slash.
s = s.replace("<esp-web-install-button manifest='manifest.json'></esp-web-install-button>",
              "<esp-web-install-button id='installer'></esp-web-install-button>")
s = s.replace("async function checkManifest(){try{let r=await fetch('manifest.json',{cache:'no-store'});",
              "async function checkManifest(){try{let base=location.pathname.endsWith('/')?location.pathname:location.pathname+'/';let manifestUrl=base+'manifest.json';installer.setAttribute('manifest',manifestUrl);let r=await fetch(manifestUrl,{cache:'no-store'});")

p.write_text(s)
