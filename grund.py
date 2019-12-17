#!/usr/local/bin/python3
# run this as: 
# nohup python gruntd.py

# this is the grunt git-based run daemon script: https://github.com/emer/grunt
# this is the outer-loop grunt daemon that polls all grunt working repositories
# and calls ./grund_sub.py to handle each case

import getpass
import os
import time
import subprocess
from pathlib import Path

def open_servername(fnm):
    global grunt_clust
    if os.path.isfile(fnm):
        with open(fnm, "r") as f:
            grunt_clust = str(f.readline()).rstrip()
        print("server is: " + grunt_clust + " from: " + fnm)
        return True
    else:
        return False

def get_server():
    cf = "grunt.server"
    if not open_servername(cf):
        df = os.path.join(str(Path.home()), ".grunt.defserver")
        if not open_servername(df):
            cnm = str(input("enter name of default server to use: "))
            with open(df, "w") as f:
                f.write(cnm + "\n")
            
# grunt_clust is server name -- default is in ~.grunt.defserver
grunt_clust = ""
get_server()
            
# grunt_root is ~/grunt
# you can symlink ~/grunt somewhere else if you want but let's keep it simple
grunt_root = os.path.join(str(Path.home()), "grunt")
print ("grunt_root: " + grunt_root)

# grunt_user is user name
grunt_user = getpass.getuser()
print("grunt_user: " + grunt_user)
    
# grunt_wc is the working directory path
grunt_wc = os.path.join(grunt_root, "wc", grunt_clust, grunt_user)
print("grunt_wc: " + grunt_wc)

while True:
    for f in os.listdir(grunt_wc):
        grunt_proj = os.path.join(grunt_wc,f)
        if os.path.isdir(grunt_proj):
            subprocess.call(["python3","./gruntd_sub.py", grunt_proj])
    time.sleep(10)
    
