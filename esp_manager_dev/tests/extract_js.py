import ast
from pathlib import Path
tree=ast.parse(Path('app/main.py').read_text());values={}
for node in tree.body:
 if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('APP_JS','HARDWARE'):
  values[node.targets[0].id]=ast.literal_eval(node.value)
Path('/tmp/app.js').write_text(values['APP_JS'])
h=values['HARDWARE'];start=h.index('<script>')+8;end=h.index('</script>',start);Path('/tmp/hardware.js').write_text(h[start:end])
