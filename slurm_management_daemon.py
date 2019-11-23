import getpass
import os
from os import listdir
import time
import subprocess


username = getpass.getuser()
curr_dir = os.getcwd()
dirs = os.path.split(curr_dir)

if (dirs[1] != "code"):
    print("Not launched from a valid crun tree")
    exit(1)
print(dirs)
print(username)

crun_root = dirs[0]

while True:
    for f in listdir(os.path.join(crun_root,"working_dir",username)):
        print(f)
        project_dir = os.path.join(crun_root,"working_dir",username,f)
        if os.path.isdir(project_dir):
            
            print("Polling " + project_dir)
            subprocess.call(["python3","poll_and_launch_project.py",project_dir])
    time.sleep(10)
    
