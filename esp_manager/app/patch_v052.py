from pathlib import Path
p=Path(__file__).with_name('main.py')
s=p.read_text()
old="""async function importP(){let n=prompt('Projektname');if(!n)return;let fd=new FormData();fd.append('name',n);fd.append('archive',imp.files[0]);await api('api/projects/import',{method:'POST',body:fd});refresh()}refresh()"""
new="""async function importP(){
 if(!imp.files[0]){alert('Bitte zuerst eine exportierte ZIP-Datei auswählen.');return}
 let suggested=imp.files[0].name.replace(/-export\\.zip$/i,'_import').replace(/\\.zip$/i,'_import');
 let n=prompt('Neuer Projektname',suggested);
 if(!n)return;
 try{
  let fd=new FormData();fd.append('name',n);fd.append('archive',imp.files[0]);
  let result=await api('api/projects/import',{method:'POST',body:fd});
  imp.value='';await refresh();await openP(result.name);
  alert('Projekt '+result.name+' wurde erfolgreich importiert.');
 }catch(e){alert('Import fehlgeschlagen: '+e.message)}
}refresh()"""
if old not in s:
    raise SystemExit('Expected importP JavaScript block not found')
s=s.replace(old,new)
old2="""async def import_project(name:str=Form(...),archive:UploadFile=File(...)):
 name=clean(name);dst=PROJECTS/name
 if dst.exists():raise HTTPException(409,'Projekt existiert')
 try:z=zipfile.ZipFile(io.BytesIO(await archive.read()))
 except Exception:raise HTTPException(400,'Ungültiges ZIP')
 dst.mkdir(parents=True)
 for it in z.infolist():
  if not it.is_dir() and '..' not in Path(it.filename).parts:
   out=dst/it.filename;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read(it))
 if not (dst/'espmanager.yaml').exists():shutil.rmtree(dst);raise HTTPException(400,'Kein ESP-Manager-Projekt')
 m=ensure_defaults(yaml.safe_load((dst/'espmanager.yaml').read_text()));m['name']=name;m['ota_token']=secrets.token_urlsafe(32);(dst/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False));copy_agent(dst);render_pio(dst,m);return public(m)"""
new2="""async def import_project(name:str=Form(...),archive:UploadFile=File(...)):
 name=clean(name);dst=PROJECTS/name
 if dst.exists():raise HTTPException(409,'Ein Projekt mit diesem Namen existiert bereits. Bitte einen anderen Namen verwenden.')
 raw=await archive.read()
 if not raw:raise HTTPException(400,'Die ausgewählte ZIP-Datei ist leer.')
 try:
  z=zipfile.ZipFile(io.BytesIO(raw));bad=z.testzip()
  if bad:raise HTTPException(400,f'ZIP-Datei ist beschädigt: {bad}')
 except HTTPException:raise
 except Exception as exc:raise HTTPException(400,f'Ungültige ZIP-Datei: {exc}')
 tmp=PROJECTS/f'.import-{name}-{time.time_ns()}'
 try:
  tmp.mkdir(parents=True)
  for it in z.infolist():
   if it.is_dir():continue
   parts=Path(it.filename).parts
   if '..' in parts or Path(it.filename).is_absolute():continue
   out=tmp/it.filename;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read(it))
  metafile=tmp/'espmanager.yaml'
  if not metafile.exists():raise HTTPException(400,'Kein ESP-Manager-Projekt: espmanager.yaml fehlt im ZIP-Hauptverzeichnis.')
  m=ensure_defaults(yaml.safe_load(metafile.read_text()) or {})
  m['name']=name;m['display_name']=name.replace('_',' ').title();m['ota_token']=secrets.token_urlsafe(32)
  metafile.write_text(yaml.safe_dump(m,sort_keys=False));copy_agent(tmp);render_pio(tmp,m);tmp.rename(dst)
  return public(m)
 except Exception:
  shutil.rmtree(tmp,ignore_errors=True)
  raise"""
if old2 not in s:
    raise SystemExit('Expected import_project endpoint not found')
s=s.replace(old2,new2)
p.write_text(s)
