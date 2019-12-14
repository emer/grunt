# this is the inner-loop crun daemon that is spawned by crund.py for each project working directory
# it is passed the arg: ~/crun/wd/username/projname  to process

from git import Repo
import os
import subprocess
import sys
import re

# turn this on to see more verbose debug messages
crun_debug = False

# crun_wd is the working dir for project: ~/crun/wd/username/projname
crun_wd = ""

# crun_jobs is the jobs git working dir for project: ~/crun/wd/username/projname/jobs
crun_jobs = ""

# crun_jobs_repo is active git repo handle
crun_jobs_repo = 0

# crun_results_repo is active git repo handle
crun_results_repo = 0

# crun_shafn is the sha filename that we use to track what has been processed
crun_shafn = ""

def submit_job(job_file):
    print("Submitting submit job " + job_file)
    file_split = os.path.split(job_file)
    print(file_split)
    cdir = os.path.join(crun_jobs,file_split[0])
    os.chdir(cdir)

    try:
        result = subprocess.check_output(["sbatch",file_split[1]])
    except CalledProcessError:
        print("Failed to submit job script")
        exit(5)
    prog = re.compile('.*Submitted batch job (\d+).*')
    result = prog.match(str(result))
    f = open("crun.jobid", "a")
    f.write(str(result.group(1)))
    f.close()
    crun_jobs_repo.remotes.origin.push()
    crun_jobs_repo.git.add(os.path.join(file_split[0],"crun.jobid"))
    crun_jobs_repo.index.commit("Comitting jobid for job: " + str(file_split[1]))
    crun_jobs_repo.remotes.origin.push()
    print(result.group(1))
    
    return

def update_job(update_file):
    #TODO: implement
    return

def commit_jobs():
    commit = str(crun_jobs_repo.heads.master.commit)
    f = open(crun_shafn, "w")
    f.write(commit)
    f.close()
    crun_jobs_repo.git.add(crun_shafn)
    crun_jobs_repo.index.commit("Processed job submissions up to commit " + commit)
    crun_jobs_repo.remotes.origin.push()
    return
    
###################################################################
#  starts running here    
    
if len(sys.argv) != 2:
    print("usage: crund_sub.py ~/crun/wd/username/projname")
    print("  1 argument needed, but " + str(len(sys.argv) - 1) + " given")
    exit(1)
elif os.path.isdir(sys.argv[1]):
    crun_wd = sys.argv[1]
    crun_jobs = os.path.join(crun_wd,"jobs")
    try:
        crun_jobs_repo = Repo(crun_jobs)
    except Exception as e:
        print("The directory provided is not a valid crun jobs git working directory: " + crun_wd + "! " + str(e))
        exit(3)

    try:
        crun_results_repo = Repo(os.path.join(crun_wd,"results"))
    except Exception as e:
        print("The directory provided is not a valid crun jobs git working directory: " + crun_wd + "! " + str(e))
        exit(3)
else:
    print("The path given is not a valid directory")
    exit(2)

crun_shafn = os.path.join(crun_jobs,"last_processed_commit.sha")
    
crun_jobs_repo.remotes.origin.pull()

# Check if we have a valid commit sha1 hash as the last processed, so that we can pickup launching from there.

if os.path.isfile(crun_shafn):
    f = open(crun_shafn, "r")
    last_processed_commit_hash = f.readline()
    f.close()
    check_for_updates = True
    launched_job = False
    if crun_debug:
        print("Begin processing commits from hash: " + last_processed_commit_hash)
    last_to_head = last_processed_commit_hash + "..HEAD"
    most_recent_head = None
    for cm in crun_jobs_repo.iter_commits(rev=last_to_head):
        if most_recent_head == None:
            most_recent_head = cm
        if crun_debug:
            print("Processing commit " + str(cm))
        for f in cm.stats.files:
            if f.endswith("crun.sh"):
                submit_job(f)
                launched_job = True
            if f.endswith("update.now"):
                update_job(f)
                launched_job = True
    if launched_job:
        commit_jobs()
    exit(0)    
else:
    print(crun_jobs_repo.heads.master.commit)
    f = open(crun_shafn, "a")
    f.write(str(crun_jobs_repo.heads.master.commit))
    f.close()
    crun_jobs_repo.git.add(crun_shafn)
    crun_jobs_repo.index.commit("This is the first time to poll this project, so write latest commit as reference")
    crun_jobs_repo.remotes.origin.push()
    exit(0)


