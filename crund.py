#!/usr/local/bin/python3
# run this as: 
# nohup python crund.py

# this is the outer-loop crun daemon that polls all crun working repositories

import getpass
import os
import time
import subprocess
from pathlib import Path

def open_clustername(fnm):
    global crun_clust
    if os.path.isfile(fnm):
        with open(fnm, "r") as f:
            crun_clust = str(f.readline()).rstrip()
        print("cluster is: " + crun_clust + " from: " + fnm)
        return True
    else:
        return False

def get_cluster():
    cf = "crun.cluster"
    if not open_clustername(cf):
        df = os.path.join(str(Path.home()), ".crun.defcluster")
        if not open_clustername(df):
            cnm = str(input("enter name of default cluster to use: "))
            with open(df, "w") as f:
                f.write(cnm + "\n")
            
# crun_clust is cluster name -- default is in ~.crun.defcluster
crun_clust = ""
get_cluster()
            
# crun_root is ~/crun
# you can symlink ~/crun somewhere else if you want but let's keep it simple
crun_root = os.path.join(str(Path.home()), "crun")
print ("crun_root: " + crun_root)

# crun_user is user name
crun_user = getpass.getuser()
print("crun_user: " + crun_user)
    
# crun_wc is the working directory path
crun_wc = os.path.join(crun_root, "wc", crun_clust, crun_user)
print("crun_wc: " + crun_wc)

while True:
    for f in os.listdir(crun_wc):
        crun_proj = os.path.join(crun_wc,f)
        if os.path.isdir(crun_proj):
            subprocess.call(["python3","./crund_sub.py", crun_proj])
    time.sleep(10)
    
