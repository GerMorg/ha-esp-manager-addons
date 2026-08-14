from pathlib import Path
p=Path(__file__).with_name('patch_v082.py')
s=p.read_text()
old="""if old_card not in s:raise SystemExit('main device card renderer missing')
s=s.replace(old_card,new_card,1)"""
new="""if old_card in s:
 s=s.replace(old_card,new_card,1)
else:
 print('Hinweis: Hauptseiten-Gerätekarte hat eine abweichende Formatierung; Backend und Hardwareseite werden trotzdem gepatcht.')"""
if old not in s:raise SystemExit('patch_v082 guard block not found')
p.write_text(s.replace(old,new,1))
