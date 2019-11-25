import getpass
import os
from os import listdir
import time
import subprocess
import crun_lib


crun_lib.setup_crun_root()
crun_lib.verify_crun_directory_structure()

while True:
    for f in listdir(os.path.join(crun_lib.crun_root_path,"working_dir",crun_lib.crun_current_username)):
        print(f)
        project_dir = os.path.join(crun_lib.crun_root_path,"working_dir",crun_lib.crun_current_username,f)
        if os.path.isdir(project_dir):
            
            print("Polling " + project_dir)
            subprocess.call(["python3","poll_and_launch_project.py",project_dir])
    time.sleep(10)
    
