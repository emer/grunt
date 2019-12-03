import os
import getpass
import inspect

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
