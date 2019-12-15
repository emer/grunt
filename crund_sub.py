# this is the inner-loop crun daemon that is spawned by crund.py for each project working directory
# it is passed the arg: ~/crun/wc/username/projname  to process

from git import Repo
import os
import subprocess
from subprocess import Popen, PIPE
import sys
import re
import shutil
import glob

# turn this on to see more verbose debug messages
crun_debug = False

# crun_wc is the working dir for project: ~/crun/wc/cluster/username/projname
crun_wc = ""

# crun_jobs is the jobs git working dir for project: ~/crun/wc/cluster/username/projname/jobs
crun_jobs = ""

# crun_jobs_repo is active git repo handle
crun_jobs_repo = 0

# crun_results is the jobs git working dir for project: ~/crun/wc/cluster/username/projname/results
crun_results = ""

# crun_results_repo is active git repo handle
crun_results_repo = 0

# crun_jobs_shafn is the sha filename that we use to track what has been processed
crun_jobs_shafn = ""

# crun_jobid is the current jobid code
crun_jobid = ""

# crun_job is current job file relative to crun_jobs
# set by master update loop
crun_job = ""

# crun_jobdir is current job directory relative to crun_jobs
# e.g., active/jobid/projname
# set by get_paths
crun_jobdir = ""

# crun_jobpath is current full job path: crun_jobs/crun_jobdir
# set by get_paths
crun_jobpath = ""

# crun_jobfnm is current job filename, e.g., crun.sh
# set by get_paths
crun_jobfnm = ""

# get_paths gets job file paths based on a job_file which is relative to 
# project 
def get_paths(job_file)
    global crun_jobdir, crun_jobpath, crun_jobfnm, crun_jobid
    file_split = os.path.split(job_file)
    crun_jobdir = file_split[0]
    crun_jobpath = os.path.join(crun_jobs, crun_jobdir)
    crun_jobfnm = file_split[1]
    crun_jobid = os.path.split(crun_jobdir)[1]

# add job files adds all files named job.* in current dir
def add_job_files(jobid):
    jobfiles := "\n".join(glob.glob("job.*")
    crun_jobs_repo.remotes.origin.push()
    for f in jobfiles.splitlines():
        crun_jobs_repo.git.add(f)
    crun_jobs_repo.index.commit("Comitting job files for job: " + jobid)
    crun_jobs_repo.remotes.origin.push()

def write_job_file(fname, content):
    f = open("job.slurmid", "w")
    f.write(str(result.group(1)))
    f.flush()
    f.close()

def submit_job():
    print("Submitting submit job: " + crun_job)
    os.chdir(crun_jobpath)
    try:
        result = subprocess.check_output(["sbatch",crun_jobfnm])
    except CalledProcessError:
        print("Failed to submit job script")
        exit(5)
    prog = re.compile('.*Submitted batch job (\d+).*')
    result = prog.match(str(result))
    slurmid = result.group(1)
    write_job_file("job.slurmid", slurmid)
    print("Slurm job id: " + slurmid)
    add_job_files(crun_jobid)
    return

def update_job():
    print("Updating job: " + crun_job)
    os.chdir(crun_jobpath)
    if (not os.path.isfile("crunres.py")):
        print("Error: crunres.py results listing script not found -- MUST be present and checked into git!")
        return
    p = subprocess.check_output(["python3", "crunres.py"], universal_newlines=True)
    rdir = os.path.join(crun_results,crun_jobdir)
    os.makedirs(rdir)
    # print("rdir: " + rdir)
    for f in p.splitlines():
        rf = os.path.join(rdir,f)
        shutil.copyfile(f, rf)
        print("added results: " + rf)
        crun_results_repo.git.add(os.path.join(crun_jobdir,f))
    add_job_files(crun_jobid)
    return

def commit_jobs():
    commit = str(crun_jobs_repo.heads.master.commit)
    f = open(crun_jobs_shafn, "w")
    f.write(commit)
    f.close()
    crun_jobs_repo.git.add(crun_jobs_shafn)
    crun_jobs_repo.index.commit("Processed job submissions up to commit " + commit)
    crun_jobs_repo.remotes.origin.push()
    return
    
def commit_results():
    commit = str(crun_results_repo.heads.master.commit)
    f = open(crun_results_shafn, "w")
    f.write(commit)
    f.close()
    crun_results_repo.git.add(crun_results_shafn)
    crun_results_repo.index.commit("Processed job results up to commit " + commit)
    crun_results_repo.remotes.origin.push()
    return
    
###################################################################
#  starts running here    
    
if len(sys.argv) != 2:
    print("usage: crund_sub.py ~/crun/wc/cluster/username/projname")
    print("  1 argument needed, but " + str(len(sys.argv) - 1) + " given")
    exit(1)
elif os.path.isdir(sys.argv[1]):
    crun_wc = sys.argv[1]
    crun_jobs = os.path.join(crun_wc,"jobs")
    try:
        crun_jobs_repo = Repo(crun_jobs)
    except Exception as e:
        print("The directory provided is not a valid crun jobs git working directory: " + crun_wc + "! " + str(e))
        exit(3)

    crun_results = os.path.join(crun_wc,"results")
    try:
        crun_results_repo = Repo(crun_results)
    except Exception as e:
        print("The directory provided is not a valid crun jobs git working directory: " + crun_wc + "! " + str(e))
        exit(3)
else:
    print("The path given is not a valid directory")
    exit(2)

crun_jobs_shafn = os.path.join(crun_jobs,"last_processed_commit.sha")
crun_results_shafn = os.path.join(crun_results,"last_processed_commit.sha")
    
crun_jobs_repo.remotes.origin.pull()
crun_results_repo.remotes.origin.pull()

# Check if we have a valid commit sha1 hash as the last processed, so that we can pickup launching from there.

if os.path.isfile(crun_jobs_shafn):
    f = open(crun_jobs_shafn, "r")
    last_processed_commit_hash = f.readline()
    f.close()
    check_for_updates = True
    com_jobs = False
    com_results = False
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
            get_paths(f)
            if crun_jobfnm == "crun.sh":
                submit_job()
                com_jobs = True
            if crun_jobfnm == "crcmd.update":
                update_job()
                com_results = True
                com_jobs = True
    if com_jobs:
        commit_jobs()
    if com_results:
        commit_results()
    exit(0)    
else:
    print(crun_jobs_repo.heads.master.commit)
    f = open(crun_jobs_shafn, "a")
    f.write(str(crun_jobs_repo.heads.master.commit))
    f.close()
    crun_jobs_repo.git.add(crun_jobs_shafn)
    crun_jobs_repo.index.commit("This is the first time to poll this project, so write latest commit as reference")
    crun_jobs_repo.remotes.origin.push()
    print(crun_jobs_repo.heads.master.commit)

    f = open(crun_results_shafn, "a")
    f.write(str(crun_results_repo.heads.master.commit))
    f.close()
    crun_results_repo.git.add(crun_results_shafn)
    crun_results_repo.index.commit("This is the first time to poll this project, so write latest commit as reference")
    crun_results_repo.remotes.origin.push()
    exit(0)


