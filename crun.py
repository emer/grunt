#!/usr/local/bin/python3
# note: on mac cannot change /usr/bin/ so use /usr/local/bin
# must do: pip3 install gitpython

import sys
import os
from git import Repo
from distutils.dir_util import copy_tree
import subprocess
from subprocess import Popen, PIPE
import shutil
import json
from pathlib import Path
import getpass

def open_clustername(fnm):
    global crun_clust
    if os.path.isfile(fnm):
        f = open(fnm, "r")
        crun_clust = str(f.readline())
        f.close()
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
            f = open(df, "w")
            f.write(cnm + "\n")
            f.close()
            
# crun_root is ~/crun
# you can symlink ~/crun somewhere else if you want but let's keep it simple
crun_root = os.path.join(str(Path.home()), "crun")
# print ("crun_root: " + crun_root)

# crun_clust is cluster name -- default is in ~.crun.defcluster
crun_clust = get_cluster()

# crun_user is user name
crun_user = getpass.getuser()
# print("crun_user: " + crun_user)
    
# crun_userid is short user name, used in jobid's
crun_userid = crun_user[:3]
# print("crun_userid: " + crun_userid)
    
# crun_cwd is current working dir path split
crun_cwd = os.path.split(os.getcwd())

# crun_proj is current project name = subir name of cwd
crun_proj = crun_cwd[-1]

# crun_wc is the working copy root
crun_wc = os.path.join(crun_root, "wc", crun_user, crun_proj)

# crun_jobs is the jobs git working dir for project
crun_jobs = os.path.join(crun_wc, "jobs")
# print("crun_jobs: " + crun_jobs)

# crun_jobs_repo is initialized in pull_jobs_repo() and is active git repo handle
crun_jobs_repo = 0

# crun_results is the results git working dir for project
crun_results = os.path.join(crun_wc, "results")
# print("crun_results: " + crun_results)

# crun_results_repo is initialized in pull_results_repo() and is active git repo handle
crun_results_repo = 0

# crun_jobid is the current jobid code: userid + jobnum
crun_jobid = ""

# crun_jobnum is the number for jobid
crun_jobnum = 0

def new_jobid():
    global crun_jobnum, crun_jobid
    jf = os.path.join(crun_jobs, "active", "nextjob.id")
    if os.path.isfile(jf):
        f = open(jf, "r+")
        crun_jobnum = int(f.readline())
        f.seek(0)
        f.write(str(crun_jobnum + 1) + "\n")
        f.close()
    else:
        crun_jobnum = 1
        f = open(jf, "w")
        f.write(str(crun_jobnum + 1) + "\n")
        f.close()
    crun_jobid = crun_userid + str(int(crun_jobnum)).zfill(6)
    print("crun_jobid: " + crun_jobid)

def pull_jobs_repo():
    global crun_jobs_repo
    # does git pull on jobs repository activates crun_jobs_repo
    assert_repo()
    try:
        crun_jobs_repo = Repo(crun_jobs)
    except Exception as e:
        print("The directory is not a valid crun jobs git working directory: " + crun_jobs + "! " + str(e))
        exit(3)
    # print(crun_jobs_repo)
    try:
        crun_jobs_repo.remotes.origin.pull()
    except git.exc.GitCommandError as e:
        print("Could not execute a git pull on jobs repository " + crun_jobs + str(e))

def copy_to_jobs(new_job):
    # copies current git-controlled files to new_job dir in jobs wc
    p = subprocess.check_output(["git","ls-files"], universal_newlines=True)
    os.makedirs(new_job)
    for f in p.splitlines():
        jf = os.path.join(new_job,f)
        shutil.copyfile(f, jf)
        crun_jobs_repo.git.add(jf)
                          
def add_new_git_dir(repo, path):
    # add a new dir to git and initialize with a placeholder
    os.mkdir(path)
    tmpfn = os.path.join(path, "placeholder")
    f = open(tmpfn, "a")
    f.write("placeholder")
    f.close()
    repo.git.add(path)  # i think git doesn't care about dirs
    repo.git.add(tmpfn)  # i think git doesn't care about dirs

def set_remote(repo, remote_url):
    origin = repo.create_remote('origin', remote_url)
    assert origin.exists()
    origin.fetch()
    repo.create_head('master', origin.refs.master).set_tracking_branch(origin.refs.master).checkout()
    
def assert_repo():
    if os.path.isdir(crun_wc):
        return
    print("Error: the working git repository not found for this project at: " + crun_wc)
    print("you must first create on server using: crun.py newproj " + crun_proj)
    print("and then create locally: crun.py newproj " + crun_proj + " username@server.at.univ.edu")
    exit(1)

def init_repos(projnm, remote):
    # creates repositories for given project name
    # remote is remote origin username -- must create on cluster first
    # before creating locally!
    wc = os.path.join(crun_root, "wc", crun_clust, crun_user, projnm)
    
    if os.path.isdir(wc):
        return

    bb = os.path.join(crun_root, "bb", crun_clust, crun_user, projnm)
    bb_jobs = os.path.join(bb, "jobs")
    wc_jobs = os.path.join(wc, "jobs")
    bb_res = os.path.join(bb, "results")
    wc_res = os.path.join(wc, "results")

    print("crun creating new working repo: " + wc)

    if remote == "":
        jobs_bb_repo = Repo.init(bb_jobs, bare=True)
        res_bb_repo = Repo.init(bb_res, bare=True)
        jobs_wc_repo = Repo.clone_from(bb_jobs, wc_jobs)
        res_wc_repo = Repo.clone_from(bb_res, wc_res)
        add_new_git_dir(jobs_wc_repo, os.path.join(wc_jobs,"active"))
        add_new_git_dir(jobs_wc_repo, os.path.join(wc_jobs,"delete"))
        add_new_git_dir(jobs_wc_repo, os.path.join(wc_jobs,"archive"))
        
        jobs_wc_repo.index.commit("Initial commit for " + projnm + " project")
        jobs_wc_repo.remotes.origin.push()
        
        add_new_git_dir(res_wc_repo, os.path.join(wc_res,"active"))
        add_new_git_dir(res_wc_repo, os.path.join(wc_res,"delete"))
        add_new_git_dir(res_wc_repo, os.path.join(wc_res,"archive"))
        
        res_wc_repo.index.commit("Initial commit for " + projnm + " project")
        res_wc_repo.remotes.origin.push()
    else:
        user = remote.split("@")[0]
        remote_url = remote + ":crun/bb/" + user + "/" + projnm
        jobs_wc_repo = Repo.init(wc_jobs)
        res_wc_repo = Repo.init(wc_res)
        set_remote(jobs_wc_repo, remote_url + "/jobs")
        set_remote(res_wc_repo, remote_url + "/results")
    
##########################################################    
# Running starts here

if len(sys.argv) < 2 or sys.argv[1] == "help":
    print("\ncrun is the cluster run client script for running and mananging jobs via git\n")
    print("usage: pass commands with args as follows\n")
    print("submit\t [args] submits git controlled files in current dir to jobs working dir:")
    print("\t ~/crun/wc/username/projdir/jobs/active/jobid -- also saves option args to job.args")
    print("\t which you can refer to later for notes about the job or use in your scripts.")
    print("\t git commit triggers update of server git repo, and crund daemon then submits the new job.")
    print("\t you *must* have a crunsub.py script in the project dir that will create a crun.sh that the")
    print("\t server will run to run the job under slurm (i.e., with #SBATCH lines) -- see example in")
    print("\t crun github source repository.\n")
    print("update\t trigger server to checkin current job results to results git repository\n")
    print("newproj\t <projname> [remote-url] creates new project repositories -- for use on both server \n")
    print("\t and client -- on client you should specify the remote-url arg which should be: \n")
    print("\t just your username and server name on cluster: username@cluster.my.university.edu\n")
    exit(1)

if (sys.argv[1] == "submit"):
    pull_jobs_repo()
    new_jobid()
    new_job = os.path.join(crun_jobs, "active", crun_jobid, crun_proj) # add proj subdir so build works
    copy_to_jobs(new_job)
    os.chdir(new_job)
    if len(sys.argv) > 2:
        f = open("job.args","a")
        f.write(sys.argv[2] + "\n")
        # todo: for loop
        f.flush()
        f.close()
        crun_jobs_repo.git.add(os.path.join(new_job,'job.args'))
    if (not os.path.isfile("crunsub.py")):
        print("Error: crunsub.py submission creation script not found -- MUST be present and checked into git!")
        exit(1)
    p = subprocess.run(["python3","./crunsub.py",crun_proj,crun_jobid])
    if (not os.path.isfile("crun.sh")):
        print("Error: crunsub.py submission creation script did not create a crun.sh file!")
        exit(1)
    crun_jobs_repo.git.add(os.path.join(new_job,'crun.sh'))
    crun_jobs_repo.index.commit("Committing launch of job: " + crun_jobid)
    crun_jobs_repo.remotes.origin.push()
    exit(0)
elif (sys.argv[1] == "cancel"):
    exit(0)
elif (sys.argv[1] == "nuke"):
    exit(0)
elif (sys.argv[1] == "archive"):
    exit(0)
elif (sys.argv[1] == "delete"):
    exit(0)
elif (sys.argv[1] == "update"):
    pull_jobs_repo()
    if len(sys.argv) < 3:
        print("Updating all running jobs")
        # TODO: implement
        # hmm. this is a bit tricky as we don't know what is running really.
    elif len(sys.argv) == 3:
        crun_jobid = sys.argv[2]
        job_dir = os.path.join(crun_jobs, "active", crun_jobid, crun_proj)
        print(job_dir)
        updt = os.path.join(job_dir,"update.now")
        f = open(updt,"a")
        f.write("#") # could be a timestamp
        f.flush()
        f.close()
        crun_jobs_repo.git.add(updt)
        crun_jobs_repo.index.commit("Updating files for job " + crun_jobid)
        crun_jobs_repo.remotes.origin.push()
    else:
        None
    exit(0)
elif (sys.argv[1] == "newproj"):
    if len(sys.argv) < 3:
        print("newproj command requires name of project")
        exit(1)
    projnm = sys.argv[2]
    remote_url = ""
    if len(sys.argv) == 4:
        remote = sys.argv[3]
    init_repos(projnm, remote)
    exit(0)
else:
    print("No valid command was given")
    

