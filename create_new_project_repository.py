#!/bin/python3
import sys
import os
import crun_lib
from git import Repo


def touch_file(filename):
    f = open(filename, "a")
    f.write("placeholder")
    f.close()

if len(sys.argv) != 2:
    print("usage: create_new_project_repository.py project_name")
    print("  1 argument needed, but " + str(len(sys.argv) - 1) + " given")
    exit(1)

project_name = sys.argv[1]
print("Creating new project file structure for project name: " + project_name)



crun_lib.setup_crun_root()
crun_lib.verify_crun_directory_structure()

print(crun_lib.crun_root_path)

bare_repo_jobs = Repo.init(os.path.join(crun_lib.crun_root_path,"barebone_repository",crun_lib.crun_current_username,project_name,"jobs"), bare=True)
bare_repo_results = Repo.init(os.path.join(crun_lib.crun_root_path,"barebone_repository",crun_lib.crun_current_username,project_name,"results"), bare=True)

working_repo_jobs_dir = os.path.join(crun_lib.crun_root_path,"working_dir",crun_lib.crun_current_username,project_name,"jobs")
working_repo_results_dir = os.path.join(crun_lib.crun_root_path,"working_dir",crun_lib.crun_current_username,project_name,"results")
working_repo_jobs = Repo.clone_from(os.path.join(crun_lib.crun_root_path,"barebone_repository",crun_lib.crun_current_username,project_name,"jobs"),
                                    working_repo_jobs_dir)
working_repo_results = Repo.clone_from(os.path.join(crun_lib.crun_root_path,"barebone_repository",crun_lib.crun_current_username,project_name,"results"),
                                    working_repo_results_dir)



os.mkdir(os.path.join(working_repo_jobs_dir,"active"))
os.mkdir(os.path.join(working_repo_jobs_dir,"archive"))
os.mkdir(os.path.join(working_repo_jobs_dir,"delete"))
touch_file(os.path.join(working_repo_jobs_dir,"active","placeholder"))
touch_file(os.path.join(working_repo_jobs_dir,"archive","placeholder"))
touch_file(os.path.join(working_repo_jobs_dir,"delete","placeholder"))
           
working_repo_jobs.git.add(os.path.join(working_repo_jobs_dir,"active"))
working_repo_jobs.git.add(os.path.join(working_repo_jobs_dir,"archive"))
working_repo_jobs.git.add(os.path.join(working_repo_jobs_dir,"delete"))
working_repo_jobs.git.add(os.path.join(working_repo_jobs_dir,"active","placeholder"))
working_repo_jobs.git.add(os.path.join(working_repo_jobs_dir,"archive","placeholder"))
working_repo_jobs.git.add(os.path.join(working_repo_jobs_dir,"delete","placeholder"))
working_repo_jobs.index.commit("This is the initial commit for the " + project_name + " project")
working_repo_jobs.remotes.origin.push()

os.mkdir(os.path.join(working_repo_results_dir,"active"))
os.mkdir(os.path.join(working_repo_results_dir,"archive"))
os.mkdir(os.path.join(working_repo_results_dir,"delete"))
           
working_repo_results.git.add(os.path.join(working_repo_results_dir,"active"))
working_repo_results.git.add(os.path.join(working_repo_results_dir,"archive"))
working_repo_results.git.add(os.path.join(working_repo_results_dir,"delete"))
working_repo_results.index.commit("This is the initial commit for the " + project_name + " project")
working_repo_results.remotes.origin.push()



