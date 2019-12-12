#!/usr/bin/python3

import sys
import os
from git import Repo
from distutils.dir_util import copy_tree
import subprocess
from subprocess import Popen, PIPE
import shutil
import json
from pathlib import Path
import crun_lib

global crun_config

def copy_code_files_to_jobs_dir(job_dir):
    #TODO: figure out how this gracefully failes when current directory is not a git directory
    p = subprocess.run(["git","ls-files"], capture_output=True, text=True)
    os.mkdir(os.path.join(job_dir,project_name))
    job_dir = os.path.join(job_dir,project_name)
    for f in p.stdout.splitlines():
        shutil.copyfile(f, os.path.join(job_dir,f))
        crun_lib.crun_jobs_repo.git.add(os.path.join(os.path.join(job_dir,f)))
                          

def get_next_job_id():
    global crun_nextjob
    f = open(os.path.join(crun_project_jobs_dir,"active/nextjob.id"), "r+")
    crun_nextjob = int(f.readline())
    f.seek(0)
    f.write(str(crun_nextjob + 1) + "\n")
    print(crun_nextjob)

def get_sbatch_setting(setting):
    return crun_lib.crun_config["default_sbatch_settings"][setting]

def generate_crun_sh(job_dir):
    f = open(os.path.join(job_dir,'crun.sh'), 'w+')
    f.write("#!/bin/bash\n")
    f.write("#SBATCH --mem=" + get_sbatch_setting("mem") + "\n")
    f.write("#SBATCH --time=" + get_sbatch_setting("time") + "\n")
    f.write("#SBATCH -c " + get_sbatch_setting("cpu") + "\n")
    f.write("#SBATCH -J \"" + project_name + " - " + str(crun_nextjob) + "\"\n")
    f.write("\n\n")
    f.write("cd " + project_name + "\n")
    f.write("go build\n")
    f.write("./" + project_name + " tmp\n")
    f.flush()
    f.close()
    
    crun_lib.crun_jobs_repo.git.add(os.path.join(job_dir,'crun.sh'))





crun_lib.load_json_config()
dirs = os.path.split(os.getcwd())
project_name = dirs[-1]

crun_project_jobs_dir = os.path.join(crun_lib.crun_config["crun_root_dir"],"working_dir",crun_lib.crun_config["crun_current_user"],project_name,"jobs")
print(crun_project_jobs_dir)
    
if len(sys.argv) < 2:
    print("No command was given!")
    exit(1)

if (sys.argv[1] == "submit"):
    crun_lib.load_jobs_repo(crun_project_jobs_dir)
    
    get_next_job_id()
    new_job_dir = os.path.join(crun_project_jobs_dir,"active",crun_lib.job_number_to_jobid(crun_nextjob))
    #TODO: catch exceptions on dir creation
    os.mkdir(new_job_dir)
    copy_code_files_to_jobs_dir(new_job_dir)
    generate_crun_sh(new_job_dir)
    crun_lib.crun_jobs_repo.index.commit("Comitting launch of jobid: " + str(crun_nextjob))
    crun_lib.crun_jobs_repo.remotes.origin.push()
    exit(0)
elif (sys.argv[1] == "cancel"):
    exit(0)
elif (sys.argv[1] == "nuke"):
    exit(0)
elif (sys.argv[1] == "archive"):
    exit(0)
elif(sys.argv[1] == "delete"):
    exit(0)
elif(sys.argv[1] == "update"):
    crun_lib.load_jobs_repo(crun_project_jobs_dir)
    if len(sys.argv) < 3:
        print("Updating all running jobs with the default or current update.now file")
        #TODO: implement
    elif len(sys.argv) == 3:
        crun_jobid = crun_lib.job_number_to_jobid(sys.argv[2])
        current_job_dir = os.path.join(crun_project_jobs_dir,"active",crun_jobid)
        print(current_job_dir)
        if (os.path.isfile(os.path.join(current_job_dir,"update.now"))):
            f = open(os.path.join(current_job_dir,"update.now"),"a")
            f.write("#")
            f.flush()
            f.close()
        else:
            #Updating the default files
            f = open(os.path.join(current_job_dir,"update.now"),"a")
            for l in crun_lib.crun_config["default_result_files"]:
                f.write(l + "\n")
            f.flush()
            f.close()
        crun_lib.crun_jobs_repo.git.add(os.path.join(current_job_dir,"update.now"))
        crun_lib.crun_jobs_repo.index.commit("Updating files for job " + crun_jobid)
        crun_lib.crun_jobs_repo.remotes.origin.push()
            
    else:
        None
        
    exit(0)
else:
    print("No valid command was given")
    


