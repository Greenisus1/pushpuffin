#!/usr/bin/env python3
"""Pushpuffin: reviewed new-file uploads via the user's real GitHub CLI login."""
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import queue
import re
import shutil
import subprocess
import threading
from urllib.parse import quote

VERSION='1.1.0'
MAX_FILE=2*1024*1024
MAX_TOTAL=10*1024*1024
MAX_FILES=200
STORE_URL='https://github.com/Greenisus1/pi-app-store'
SECRET_NAMES={'.env','.netrc','.npmrc','.pypirc','credentials','credentials.json','id_rsa','id_ed25519','id_dsa','id_ecdsa'}
SECRET_SUFFIXES={'.pem','.key','.p12','.pfx','.keystore'}


def gh_environment():
    env=os.environ.copy()
    for k in ['GH_TOKEN','GITHUB_TOKEN','GH_ENTERPRISE_TOKEN','GITHUB_ENTERPRISE_TOKEN','GH_HOST','GH_REPO','GH_DEBUG']:
        env.pop(k,None)
    env['GH_PROMPT_DISABLED']='1'
    return env


def validate_repo(repo):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}',repo):
        raise ValueError('Use owner/repository, not a URL.')
    if repo.split('/')[1] in {'.','..'}:raise ValueError('Invalid repository.')
    return repo


def remote_prefix(value):
    if not value:return ''
    if '\\' in value or value.startswith('/') or any(ord(c)<32 for c in value):raise ValueError('Use a relative repository folder.')
    parts=value.split('/')
    if any(x in {'','.','..','.git'} for x in parts):raise ValueError('Invalid repository folder.')
    return '/'.join(parts)


def safe_name(path):
    for part in PurePosixPath(path).parts:
        low=part.lower()
        if low in SECRET_NAMES or low.startswith('.env.') or Path(low).suffix in SECRET_SUFFIXES:
            raise ValueError('Potential secret file blocked: '+path)
        if part=='.git' or any(ord(c)<32 for c in part):raise ValueError('Unsafe path: '+path)


def stage_files(paths,prefix=''):
    prefix=remote_prefix(prefix)
    entries={};total=0
    def add(p,relative):
        nonlocal total
        if p.is_symlink() or not p.is_file():raise ValueError('Symlinks and special files are not uploaded: '+str(p))
        safe_name(relative)
        destination='/'.join(filter(None,[prefix,relative]))
        if destination in entries:raise ValueError('Duplicate destination: '+destination)
        with p.open('rb') as f:data=f.read(MAX_FILE+1)
        if len(data)>MAX_FILE:raise ValueError('File exceeds 2 MiB: '+relative)
        total+=len(data)
        if total>MAX_TOTAL or len(entries)>=MAX_FILES:raise ValueError('Limit: 200 files / 10 MiB total.')
        entries[destination]=data
    for chosen in paths:
        p=Path(chosen).absolute()
        if p.is_symlink():raise ValueError('Symlink selection is not supported.')
        if p.is_dir():
            for root,dirs,files in os.walk(p,followlinks=False):
                dirs[:]=sorted(d for d in dirs if d!='.git')
                for d in dirs:
                    if (Path(root)/d).is_symlink():raise ValueError('Folder contains symlink: '+d)
                for name in sorted(files):
                    f=Path(root)/name;add(f,PurePosixPath(p.name,*f.relative_to(p).parts).as_posix())
        else:add(p,p.name)
    if not entries:raise ValueError('No files selected. Empty folders are not stored by GitHub.')
    return tuple(sorted(entries.items()))


def store_installed(home=None):
    home=Path(home or Path.home())
    program=home/'.local/share/pi-app-store/program/appstore.py'
    if not program.is_file():return False
    # Verify the installed launcher's target, not just its name.
    for wrapper in [home/'.local/bin/AppStore',Path('/usr/local/bin/AppStore')]:
        try:
            text=wrapper.read_text()
            if str(program) in text and 'python3' in text:return True
        except (OSError,UnicodeError):pass
    return False


class GHClient:
    def __init__(self,runner=None):self.runner=runner or subprocess.run
    def command(self,args,payload=None):
        proc=self.runner(['gh',*args],input=None if payload is None else json.dumps(payload),text=True,capture_output=True,env=gh_environment(),timeout=90)
        if proc.returncode:
            # Do not print arbitrary stderr, which may contain credentials/private content.
            raise RuntimeError('GitHub CLI request failed. Check gh auth status, network, permissions and branch rules in your terminal.')
        try:return json.loads(proc.stdout)
        except ValueError:raise RuntimeError('GitHub CLI returned an unexpected response.')
    def identity(self):return self.command(['api','--hostname','github.com','user'])['login']
    def repo(self,repo):return self.command(['api','--hostname','github.com','repos/'+validate_repo(repo)])
    def tree_paths(self,repo,branch):
        ref=self.command(['api','--hostname','github.com',f'repos/{repo}/branches/'+quote(branch,safe='')])
        commit=ref['commit']['sha']
        tree=self.command(['api','--hostname','github.com',f'repos/{repo}/git/trees/{commit}?recursive=1'])
        if tree.get('truncated'):raise ValueError('Repository tree is too large to check safely.')
        return {x['path']:x['type'] for x in tree['tree']},commit
    def prepare(self,repo,branch,entries):
        validate_repo(repo)
        if not branch or len(branch)>255 or any(ord(x)<32 for x in branch):raise ValueError('Choose an existing branch.')
        identity=self.identity();info=self.repo(repo)
        if not info.get('permissions',{}).get('push'):raise ValueError('Current GitHub login lacks push access.')
        existing,commit=self.tree_paths(repo,branch)
        for path,data in entries:
            if path in existing:raise ValueError('Existing destination blocked: '+path)
            for parent in PurePosixPath(path).parents:
                if str(parent) in existing and existing[str(parent)]!='tree':raise ValueError('A parent path is an existing file: '+str(parent))
        return {'identity':identity,'repo':info['full_name'],'private':info['private'],'branch':branch,'commit':commit,'count':len(entries),'total':sum(len(d) for p,d in entries)}
    def upload(self,review,entries,progress=lambda *a:None,cancel=None):
        # Recheck destination identity and branch state before any write.
        now=self.prepare(review['repo'],review['branch'],entries)
        if any(now[k]!=review[k] for k in ['identity','repo','private','branch','commit']):raise ValueError('Remote changed since review. Review again.')
        completed=[]
        for path,data in entries:
            if cancel and cancel.is_set():return completed
            payload={'message':'Upload '+path+' with Pushpuffin','content':base64.b64encode(data).decode('ascii'),'branch':review['branch']}
            try:
                response=self.command(['api','--hostname','github.com','--method','PUT',f"repos/{review['repo']}/contents/{quote(path,safe='/')}",'--input','-'],payload)
                expected=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
                if response.get('content',{}).get('sha')!=expected:raise RuntimeError('Server result could not be verified.')
            except Exception as e:
                raise RuntimeError(f'Stopped at {path}. {len(completed)} earlier files committed. Current file outcome may be uncertain; check GitHub before retrying. '+str(e))
            completed.append(path);progress(len(completed),len(entries),path)
        return completed


def launch(_test_hook=None):
    import tkinter as tk
    from tkinter import ttk,messagebox
    import sys
    sys.path.insert(0, str(Path.home()/".local/share/filefinderplus"))
    from filefinderplus import BrowserFrame
    if not store_installed():
        root=tk.Tk();root.withdraw();messagebox.showerror('App Store required','Install the Pi App Store for this user first:\n'+STORE_URL+'\nPushpuffin will not auto-install it.');root.destroy();return 2
    if not shutil.which('gh'):
        print('Install the real GitHub CLI, then run gh auth login in your own terminal.');return 2
    root=tk.Tk();root.title('Pushpuffin');root.geometry('1120x760');root.minsize(920,650);ttk.Style().theme_use('clam')
    top=ttk.Frame(root,padding=12);top.pack(fill='x')
    ttk.Label(top,text='Pushpuffin',font=('DejaVu Sans',20,'bold')).pack(anchor='w')
    ttk.Label(top,text='New files only. Review the GitHub account, visibility and every path before uploading.').pack(anchor='w',pady=6)
    form=ttk.Frame(top);form.pack(fill='x')
    vars={}
    for column,(name,value) in enumerate([('Repository',''),('Branch','main'),('Destination folder','')]):
        ttk.Label(form,text=name).grid(row=0,column=column,sticky='w');vars[name]=tk.StringVar(value=value)
        ttk.Entry(form,textvariable=vars[name],width=34).grid(row=1,column=column,sticky='ew',padx=(0,8));form.columnconfigure(column,weight=1)
    actions=ttk.Frame(top);actions.pack(fill='x',pady=(10,0))
    status=tk.StringVar(value='Login: run gh auth login in your terminal. No passwords or tokens are collected here.')
    ttk.Label(top,textvariable=status,wraplength=1000).pack(anchor='w',pady=6)
    browser=BrowserFrame(root,select_only=True);browser.frame.pack(fill='both',expand=True)
    events=queue.Queue();cancel=threading.Event();busy=[False]
    def login_info():messagebox.showinfo('Real GitHub CLI login','In your own terminal run:\ngh auth login --hostname github.com\n\nUse GitHub CLI browser/device login. Then return here. This app never asks for or saves a password/token.',parent=root)
    def review():
        if busy[0]:return
        try:
            entries=stage_files(browser.selected_paths(),vars['Destination folder'].get())
            repo=vars['Repository'].get().strip();branch=vars['Branch'].get().strip()
        except Exception as e:messagebox.showerror('Cannot stage files',str(e),parent=root);return
        busy[0]=True;status.set('Checking your CLI account and destination. Nothing uploaded.')
        def worker():
            try:events.put(('review',(GHClient().prepare(repo,branch,entries),entries)))
            except Exception as e:events.put(('error',str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def show_review(info,entries):
        win=tk.Toplevel(root);win.title('Review upload');win.geometry('820x620');win.transient(root);win.grab_set()
        ttk.Label(win,text=f"Account: {info['identity']}\nRepository: {info['repo']} ({'PRIVATE' if info['private'] else 'PUBLIC'})\nBranch: {info['branch']}\n{info['count']} files / {info['total']} bytes",padding=12).pack(anchor='w')
        ttk.Label(win,text='Public repositories expose these bytes to everyone. Check file contents for secrets.\nOne commit per file; failures can leave a partial upload. Existing files are never overwritten.',padding=12,wraplength=780).pack(anchor='w')
        listing=tk.Text(win,wrap='none',font=('DejaVu Sans Mono',10));listing.pack(fill='both',expand=True,padx=12)
        listing.insert('1.0','\n'.join(f'{p}  ({len(d)} bytes)' for p,d in entries));listing.configure(state='disabled')
        controls=ttk.Frame(win,padding=12);controls.pack(fill='x')
        def abandon():busy[0]=False;status.set('Upload cancelled. Nothing uploaded.');win.destroy()
        def commit():
            win.destroy();cancel.clear();status.set('Uploading reviewed files...')
            def worker():
                try:
                    done=GHClient().upload(info,entries,lambda n,t,p:events.put(('progress',f'{n}/{t} committed: {p}')),cancel)
                    events.put(('done',f'{len(done)}/{len(entries)} files committed.'+(' Stopped by you.' if cancel.is_set() else '')))
                except Exception as e:events.put(('error',str(e)))
            threading.Thread(target=worker,daemon=True).start()
        ttk.Button(controls,text='Cancel',command=abandon).pack(side='left')
        ttk.Button(controls,text='Upload these reviewed files',command=commit).pack(side='right')
        win.protocol('WM_DELETE_WINDOW',abandon)
    ttk.Button(actions,text='How to log in',command=login_info).pack(side='left')
    ttk.Button(actions,text='Review selected files/folders',command=review).pack(side='left',padx=8)
    ttk.Button(actions,text='Stop after current file',command=lambda:cancel.set()).pack(side='left')
    def poll():
        try:
            while True:
                kind,value=events.get_nowait()
                if kind=='review':show_review(*value)
                elif kind=='progress':status.set(value)
                elif kind in {'error','done'}:
                    busy[0]=False;status.set(value)
                    (messagebox.showerror if kind=='error' else messagebox.showinfo)('Pushpuffin',value,parent=root)
        except queue.Empty:pass
        root.after(100,poll)
    def close():
        if busy[0]:messagebox.showinfo('Task running','Stop after current file, then wait for the result before closing.',parent=root);return
        root.destroy()
    root.protocol('WM_DELETE_WINDOW',close);poll()
    if _test_hook is not None:_test_hook(root,browser,vars,review)
    root.mainloop();return 0


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--gui',action='store_true');p.add_argument('--version',action='store_true');a=p.parse_args()
    if a.version:print(VERSION);return 0
    try:
        if a.gui:return launch()
        from pushpuffin_terminal import launch as terminal_launch
        return terminal_launch()
    except ImportError:print('Install FileFinder+ 1.1.0 first. For optional --gui install python3-tk and use desktop/VNC.');return 2
    except Exception as e:print('Cannot start Pushpuffin: '+str(e));return 2

if __name__=='__main__':raise SystemExit(main())
