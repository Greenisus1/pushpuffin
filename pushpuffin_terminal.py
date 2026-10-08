"""Terminal uploader. No write occurs before account/path review + confirmation."""
import sys
from pathlib import Path
import threading
from terminal_ui import run,safe

def session(ui,client=None,check_dependencies=True):
 import pushpuffin as p
 if check_dependencies:
  if not p.store_installed():ui.message('Install Pi App Store for this user first: '+p.STORE_URL);return
  if not p.shutil.which('gh'):ui.message('Install official gh CLI, then use gh auth login in your own terminal.');return
 sys.path.insert(0,str(Path.home()/'.local/share/filefinderplus'))
 from terminal_browser import pick_paths
 client=client or p.GHClient();paths=();repo='';branch='main';prefix=''
 while True:
  index=ui.menu('New files only / no stored passwords or tokens',['Pick files/folders ('+str(len(paths))+')','Repository: '+repo,'Branch: '+branch,'Destination folder: '+prefix,'Review and upload','CLI login help','Quit'])
  if index is None or index==6:return
  try:
   if index==0:paths=pick_paths(ui)
   elif index in (1,2,3):
    value=ui.prompt(['','owner/repository','Existing branch','Relative destination folder (blank = root)'][index])
    if value is not None:
     if index==1:repo=value.strip()
     elif index==2:branch=value.strip()
     else:prefix=value.strip()
   elif index==5:ui.message('Run gh auth login --hostname github.com in your own terminal.\nUse its browser/device login. Never paste tokens/passwords here.\nCLI token/host/repo environment overrides are ignored by Pushpuffin.')
   elif index==4:
    entries=p.stage_files(paths,prefix)
    ui.message('Next: live check of CLI account/repo/branch, no writes.\nIt may take time. Enter to check, then wait for the full review.')
    info=client.prepare(repo,branch,entries)
    ui.message('Account: '+info['identity']+'\nRepo: '+info['repo']+' / '+('PRIVATE' if info['private'] else 'PUBLIC - bytes visible to everyone')+'\nBranch: '+info['branch']+'\n'+str(info['count'])+' files / '+str(info['total'])+' bytes\n\n'+ '\n'.join(path+' ('+str(len(data))+' bytes)' for path,data in entries)+'\n\nCheck contents for secrets. Filenames screening is NOT a secret-content detector.\nOne commit per file. Failure/cancel can leave partial uploads.\nNo overwrites, deletes, repo creation or automatic retry.')
    if not ui.confirm('Upload these reviewed staged bytes to '+info['repo']+'/'+info['branch']+' as '+info['identity']+'?'):continue
    cancelled=threading.Event()
    def perform():
     print('Uploading reviewed files. Ctrl-C requests stop; current file may finish.')
     try:
      done=client.upload(info,entries,progress=lambda n,total,path:print(f'{n}/{total}: {safe(path)}'),cancel=cancelled)
      print('Committed:',len(done),'of',len(entries))
     except KeyboardInterrupt:cancelled.set();print('Interrupted. Current file outcome may be uncertain. Check GitHub before retrying; earlier commits remain.')
     except Exception as e:print(safe(str(e)))
     try:input('Enter to return: ')
     except (EOFError,KeyboardInterrupt):pass
    ui.external(perform)
  except Exception as e:ui.message(str(e))
def launch():return run('Pushpuffin 1.1.1',session)
