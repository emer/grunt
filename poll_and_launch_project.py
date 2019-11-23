#!/usr/bin/python3

from git import Repo
import os
import subprocess
import sys
import re


def submit_job(job_file):
    print("Submitting submit job " + job_file)
    file_split = os.path.split(job_file)
    print(file_split)
    os.chdir(os.path.join(repo_dir,file_split[0]))

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
    repo.remotes.origin.push()
    repo.git.add(os.path.join(file_split[0],"crun.jobid"))
    repo.index.commit("Comitting jobid for job: " + str(file_split[1]))
    repo.remotes.origin.push()
    print(result.group(1))
    
    return

def commit_last_processed_commit():
    f = open(os.path.join(repo_dir,"last_processed_commit.sha"), "w")
    f.write(str(repo.heads.master.commit))
    f.close()
    repo.git.add(os.path.join(repo_dir,"last_processed_commit.sha"))
    repo.index.commit("Processed job submissions up to commit " + str(repo.heads.master.commit))
    repo.remotes.origin.push()
    return

if len(sys.argv) != 2:
    print("usage: project_poll_and_launch.py /path/to/project/working_dir")
    print("  1 argument needed, but " + str(len(sys.argv) - 1) + " given")
    exit(1)
elif os.path.isdir(sys.argv[1]):
    repo_dir = sys.argv[1]
    try:
        repo = Repo(repo_dir)
    except Exception as e:
        print("The directory provided is not a valid git working directory: " + repo_dir + "! " + str(e))
        exit(3)
else:
    print("The path given is not a valid directory")
    exit(2)

repo.remotes.origin.pull()

#Check if we have a valid commit sha1 hash as the last processed, so that we can pickup launching from there.

if os.path.isfile(os.path.join(repo_dir,"last_processed_commit.sha")):
    f = open(os.path.join(repo_dir,"last_processed_commit.sha"), "r")
    last_processed_commit_hash = f.readline()
    check_for_updates = True
    launched_job = False
    print("Begin processing commits from hash: " + last_processed_commit_hash)
    last_to_head = last_processed_commit_hash + "..HEAD"
    most_recent_head = None
    for cm in repo.iter_commits(rev=last_to_head):
        if most_recent_head == None:
            most_recent_head = cm
        print("Processing commit " + str(cm))
        for f in cm.stats.files:
            if "submit.sh" in f:
                submit_job(f)
                launched_job = True
    if launched_job:
        commit_last_processed_commit()
        None
    exit(0)    
        
else:
    print(repo.heads.master.commit)
    f = open(os.path.join(repo_dir,"last_processed_commit.sha"), "a")
    f.write(str(repo.heads.master.commit))
    f.close()
    repo.git.add(os.path.join(repo_dir,"last_processed_commit.sha"))
    repo.index.commit("This is the first time to poll this project, so write latest commit has as reference")
    repo.remotes.origin.push()
    exit(0)


