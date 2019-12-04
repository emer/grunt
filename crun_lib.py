import os
import getpass
import inspect
import git
from git import Repo
from pathlib import Path
import json

def load_json_config():
    global crun_config
    with open(os.path.join(Path.home(),"crun_data",".config.json")) as json_file:
        crun_config = json.load(json_file)

def setup_crun_root():
    global crun_root_path
    global crun_current_username
    currentDirectory = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    dirs = os.path.split(currentDirectory)

    if (dirs[1] != "code"):
        print("Not launched from a valid crun tree")
        exit(1)

    crun_root_path = dirs[0]
    print ("Crun_root: " + crun_root_path)

    crun_current_username = getpass.getuser()
    print("Crun_user: " + crun_current_username)

    


def verify_crun_directory_structure():
    global crun_root_path
    global crun_current_username
    
    #Verify that structure was set-up correctly
    if ((not os.path.isdir(os.path.join(crun_root_path,"barebone_repository")))
        or (not os.path.isdir(os.path.join(crun_root_path,"working_dir")))
        or (not os.path.isdir(os.path.join(crun_root_path,"barebone_repository",crun_current_username)))
        or (not os.path.isdir(os.path.join(crun_root_path,"working_dir",crun_current_username))) ):
        print("Directory structure is wrong!")
        exit

def load_jobs_repo(crun_project_jobs_dir):
    global crun_jobs_repo
    try:
        crun_jobs_repo = Repo(crun_project_jobs_dir)
    except Exception as e:
        print("The directory provided is not a valid crun jobs git working directory: " + crun_project_jobs_dir + "! " + str(e))
        exit(3)
    print(crun_jobs_repo)
    try:
        crun_jobs_repo.remotes.origin.pull()
    except git.exc.GitCommandError as e:
        print("Could not execute a git pull on jobs repository " + crun_project_jobs_dir + str(e))


def job_number_to_jobid(number):
    global crun_config
    #TODO capture errors in case number is not a valid integer 
    return "job" + crun_config["crun_current_user_short"] + str(int(number)).zfill(6)
