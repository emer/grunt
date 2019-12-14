#!/usr/local/bin/python3
# run this as: 
# nohup python crund.py

# this is the outer-loop crun daemon that polls all crun working repositories

import getpass
import os
from os import listdir
import time
import subprocess
from pathlib import Path

# crun_root is ~/crun
# you can symlink ~/crun somewhere else if you want but let's keep it simple
crun_root = os.path.join(str(Path.home()), "crun")
print ("crun_root: " + crun_root)

# crun_user is user name
crun_user = getpass.getuser()
print("crun_user: " + crun_user)
    
# crun_wd is the working directory path
crun_wd = os.path.join(crun_root, "wd", crun_user)
print("crun_wd: " + crun_wd)

while True:
    for f in listdir(crun_wd):
        # print(f)
        crun_proj = os.path.join(crun_wd,f)
        if os.path.isdir(crun_proj):
            # print("Polling " + crun_proj)
            subprocess.call(["python3","./crund_sub.py", crun_proj])
    time.sleep(10)
    
