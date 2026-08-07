from pathlib import Path

p = Path(__file__).with_name('main.py')
s = p.read_text()

old = "return HTMLResponse(page.replaceAll('PROJECT',clean(project)))"
new = "return HTMLResponse(page.replace('PROJECT', clean(project)))"
if old not in s:
    raise SystemExit('Expected Python replaceAll regression was not found')
s = s.replace(old, new, 1)

p.write_text(s)
