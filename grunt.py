#!/usr/local/bin/python3
# note: on mac cannot change /usr/bin/ so use /usr/local/bin
# must do: pip3 install [--user] gitpython

# this is the grunt git-based run tool script: https://github.com/emer/grunt

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
import datetime
import csv

def open_servername(fnm):
    global grunt_clust
    if os.path.isfile(fnm):
        with open(fnm, "r") as f:
            grunt_clust = str(f.readline()).rstrip()
        print("server is: " + grunt_clust + " from: " + fnm)
        return True
    else:
        return False

def get_server():
    cf = "grunt.server"
    if not open_servername(cf):
        df = os.path.join(str(Path.home()), ".grunt.defserver")
        if not open_servername(df):
            cnm = str(input("enter name of default server to use: "))
            with open(df, "w") as f:
                f.write(cnm + "\n")
            
# grunt_clust is server name -- default is in ~.grunt.defserver
grunt_clust = ""
get_server()

# grunt_root is ~/grunt
# you can symlink ~/grunt somewhere else if you want but let's keep it simple
grunt_root = os.path.join(str(Path.home()), "grunt")
# print ("grunt_root: " + grunt_root)

# grunt_user is user name
grunt_user = getpass.getuser()
# print("grunt_user: " + grunt_user)
    
# grunt_userid is short user name, used in jobid's
grunt_userid = grunt_user[:3]
# print("grunt_userid: " + grunt_userid)
    
# grunt_cwd is current working dir path split
grunt_cwd = os.path.split(os.getcwd())

# grunt_proj is current project name = subir name of cwd
grunt_proj = grunt_cwd[-1]

# grunt_wc is the working copy root
grunt_wc = os.path.join(grunt_root, "wc", grunt_clust, grunt_user, grunt_proj)

# grunt_jobs is the jobs git working dir for project
grunt_jobs = os.path.join(grunt_wc, "jobs")
# print("grunt_jobs: " + grunt_jobs)

# grunt_jobs_repo is initialized in pull_jobs_repo() and is active git repo handle
grunt_jobs_repo = 0

# grunt_results is the results git working dir for project
grunt_results = os.path.join(grunt_wc, "results")
# print("grunt_results: " + grunt_results)

# grunt_results_repo is initialized in pull_results_repo() and is active git repo handle
grunt_results_repo = 0

# grunt_jobid is the current jobid code: userid + jobnum
grunt_jobid = ""

# grunt_jobnum is the number for jobid
grunt_jobnum = 0

# lists of different jobs -- updated with active_jobs_list at start
jobs_pending = []
jobs_running = []
jobs_done = []
jobs_header =     ["JobId", "SlurmId", "Status", "SlurmStat", "Submit", "Start", "End", "Args"]
jobs_header_sep = ["=======", "=======", "=======", "=======", "=======", "=======", "=======", "======="]

def new_jobid():
    global grunt_jobnum, grunt_jobid
    jf = os.path.join(grunt_jobs, "active", "nextjob.id")
    if os.path.isfile(jf):
        with open(jf, "r+") as f:
            grunt_jobnum = int(f.readline())
            f.seek(0)
            f.write(str(grunt_jobnum + 1) + "\n")
    else:
        grunt_jobnum = 1
        with open(jf, "w") as f:
            f.write(str(grunt_jobnum + 1) + "\n")
    grunt_jobid = grunt_userid + str(int(grunt_jobnum)).zfill(6)
    print("grunt_jobid: " + grunt_jobid)

def pull_jobs_repo():
    global grunt_jobs_repo
    # does git pull on jobs repository activates grunt_jobs_repo
    assert_repo()
    try:
        grunt_jobs_repo = Repo(grunt_jobs)
    except Exception as e:
        print("The directory is not a valid grunt jobs git working directory: " + grunt_jobs + "! " + str(e))
        exit(3)
    # print(grunt_jobs_repo)
    try:
        grunt_jobs_repo.remotes.origin.pull()
    except git.exc.GitCommandError as e:
        print("Could not execute a git pull on jobs repository " + grunt_jobs + str(e))

def pull_results_repo():
    global grunt_results_repo
    # does git pull on results repository activates grunt_results_repo
    assert_repo()
    try:
        grunt_results_repo = Repo(grunt_results)
    except Exception as e:
        print("The directory is not a valid grunt results git working directory: " + grunt_results + "! " + str(e))
        exit(3)
    # print(grunt_results_repo)
    try:
        grunt_results_repo.remotes.origin.pull()
    except git.exc.GitCommandError as e:
        print("Could not execute a git pull on results repository " + grunt_results + str(e))

def copy_to_jobs(new_job):
    # copies current git-controlled files to new_job dir in jobs wc
    p = subprocess.check_output(["git","ls-files"], universal_newlines=True)
    os.makedirs(new_job)
    for f in p.splitlines():
        jf = os.path.join(new_job,f)
        shutil.copyfile(f, jf)
        grunt_jobs_repo.git.add(jf)

def print_job_out(jobid):
    job_out = os.path.join(grunt_jobs, "active", jobid, grunt_proj, "job.out")
    print("\njob.out: " + job_out + "\n")
    out = read_strings(job_out)
    print("".join(out))
        
def link_results(jobid):
    res = os.path.join(grunt_results, "active", jobid, grunt_proj)
    dst = os.path.join("gresults", jobid)
    if not os.path.isdir("gresults"):
        os.makedirs("gresults")
    if not os.path.islink(dst):
        os.symlink(res, dst, target_is_directory=False)
        print("\nlinked: " + res + " -> " + dst + "\n")
        
def unlink_results(jobid):
    res = os.path.join(grunt_results, "active", jobid, grunt_proj)
    dst = os.path.join("gresults", jobid)
    if not os.path.isdir("gresults"):
        return
    if os.path.islink(dst):
        os.unlink(dst)
        print("\nunlinked: " + dst + "\n")
        
def write_cmd(jobid, cmd, cmdstr):
    job_dir = os.path.join(grunt_jobs, "active", jobid, grunt_proj)
    cmdfn = os.path.join(job_dir, "grcmd." + cmd)
    with open(cmdfn,"w") as f:
        f.write(cmdstr + "\n")
    grunt_jobs_repo.git.add(cmdfn)
    print("job: " + jobid + " command: " + cmd + " = " + cmdstr)
    
def commit_cmd(cmd):
    grunt_jobs_repo.index.commit("Command: " + cmd)
    grunt_jobs_repo.remotes.origin.push()

def write_commit_cmd(jobid, cmd, cmdstr):
    write_cmd(jobid, cmd, cmdstr)
    commit_cmd(cmd)

def write_csv(fnm, header, data):
    with open(fnm, 'w') as csvfile: 
        csvwriter = csv.writer(csvfile) 
        csvwriter.writerow(header) 
        csvwriter.writerows(data)

def write_string(fnm, stval):
    with open(fnm,"w") as f:
        f.write(stval + "\n")

def read_string(fnm):
    # reads a single string from file and strips any newlines -- returns "" if no file
    if not os.path.isfile(fnm):
        return ""
    with open(fnm, "r") as f:
        val = str(f.readline()).rstrip()
    return val

def read_strings(fnm):
    # reads multiple strings from file, result is list and strings still have \n at end
    if not os.path.isfile(fnm):
        return []
    with open(fnm, "r") as f:
        val = f.readlines()
    return val

def read_strings_strip(fnm):
    # reads multiple strings from file, result is list of strings with no \n at end
    if not os.path.isfile(fnm):
        return []
    with open(fnm, "r") as f:
        val = f.readlines()
        for i, v in enumerate(val):
            val[i] = v.rstrip()
    return val

def timestamp():
    return str(datetime.datetime.now())

# argslist returns post-command args as newline separated string 
# for use in command files
def argslist():
    return "\n".join(sys.argv[3:])

def jobid_fm_jobs_list(lst):
    return lst[0]
    
# active_jobs_list generates lists of active jobs with statuses    
def active_jobs_list():
    global jobs_pending, jobs_running, jobs_done
    act = os.path.join(grunt_jobs, "active")
    for jobid in os.listdir(act):
        if not jobid.startswith(grunt_userid):
            continue
        jdir = os.path.join(act, jobid, grunt_proj)
        jsub = os.path.join(jdir, "job.submit")
        jst = os.path.join(jdir, "job.start")
        jed = os.path.join(jdir, "job.end")
        jcan = os.path.join(jdir, "job.canceled")
        jstat= os.path.join(jdir, "job.status")
        slid = os.path.join(jdir, "job.slurmid")
        args = " ".join(read_strings_strip(os.path.join(jdir, "job.args")))
        slurmid = read_string(slid)
        slurmstat = read_string(jstat)
        sub = read_string(jsub)
        st = read_string(jst)
        ed = read_string(jed)
        if os.path.isfile(jcan):
            ed = read_string(jcan)
            jobs_done.append([jobid, slurmid, "Canceled", slurmstat, sub, st, ed, args])
        elif os.path.isfile(jst) and os.path.isfile(slid):
            if os.path.isfile(jed):
                jobs_done.append([jobid, slurmid, "Done", slurmstat, sub, st, ed, args])
            else:
                jobs_running.append([jobid, slurmid, "Running", slurmstat, sub, st, "", args])
        else:
            jobs_pending.append([jobid, "", "Pending", slurmstat, sub, st, ed, args])
    jobs_pending.sort(key=jobid_fm_jobs_list)
    jobs_running.sort(key=jobid_fm_jobs_list)
    jobs_done.sort(key=jobid_fm_jobs_list)
    write_csv("jobs.pending", jobs_header, jobs_pending) 
    write_csv("jobs.running", jobs_header, jobs_running) 
    write_csv("jobs.done", jobs_header, jobs_done) 

# active_jobs_list generates lists of active jobs with statuses    
def print_jobs(jobs_list, desc):
    print("\n################################\n#  " + desc)
    jl = jobs_list.copy()
    jl.insert(0, jobs_header)
    jl.insert(1, jobs_header_sep)
    s = [[str(e) for e in row] for row in jl]
    lens = [max(1,max(map(len, col))) for col in zip(*s)]
    fmt = '\t'.join('{{:{}s}}'.format(x) for x in lens)
    table = [fmt.format(*row) for row in s]
    print('\n'.join(table))
    print()
    
#########################################
# repo mgmt
          
def add_new_git_dir(repo, path):
    # add a new dir to git and initialize with a placeholder
    os.mkdir(path)
    tmpfn = os.path.join(path, "placeholder")
    with open(tmpfn, "a") as f:
        f.write("placeholder")
    repo.git.add(path)  # i think git doesn't care about dirs
    repo.git.add(tmpfn)  # i think git doesn't care about dirs

def set_remote(repo, remote_url):
    print("attempting to set remote url: " + remote_url)
    origin = repo.create_remote('origin', remote_url)
    assert origin.exists()
    origin.fetch()
    repo.create_head('master', origin.refs.master).set_tracking_branch(origin.refs.master).checkout()
    
def assert_repo():
    if os.path.isdir(grunt_wc):
        return
    print("Error: the working git repository not found for this project at: " + grunt_wc)
    print("you must first create on server using: grunt.py newproj " + grunt_proj)
    print("and then create locally: grunt.py newproj " + grunt_proj + " username@server.at.univ.edu")
    exit(1)

def init_repos(projnm, remote):
    # creates repositories for given project name
    # remote is remote origin username -- must create on server first
    # before creating locally!
    wc = os.path.join(grunt_root, "wc", grunt_clust, grunt_user, projnm)
    
    if os.path.isdir(wc):
        return

    bb = os.path.join(grunt_root, "bb", grunt_clust, grunt_user, projnm)
    bb_jobs = os.path.join(bb, "jobs")
    wc_jobs = os.path.join(wc, "jobs")
    bb_res = os.path.join(bb, "results")
    wc_res = os.path.join(wc, "results")

    print("grunt creating new working repo: " + wc)

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
        remote_url = remote + ":grunt/bb/" + grunt_clust + "/" + user + "/" + projnm
        jobs_wc_repo = Repo.init(wc_jobs)
        res_wc_repo = Repo.init(wc_res)
        set_remote(jobs_wc_repo, remote_url + "/jobs")
        set_remote(res_wc_repo, remote_url + "/results")
    
##########################################################    
# Running starts here

if len(sys.argv) < 2 or sys.argv[1] == "help":
    print("\ngrunt.py is the git-based run tool client script\n")
    print("usage: pass commands with args as follows:\n")
    print("submit\t [args] submits git controlled files in current dir to jobs working dir:")
    print("\t ~/grunt/wc/username/projdir/jobs/active/jobid -- also saves option args to job.args")
    print("\t which grunter.py script uses for passing args to job -- use --notes='notes' for descriptive info.")
    print("\t git commit triggers update of server git repo, and grund daemon then submits the new job.")
    print("\t you *must* have grunter.py script in the project dir to manage actual submission!")
    print("\t see example in grunt github source repository.\n")
    print("jobs\t [active|done] shows lists of all jobs, or specific subset (active = running, pending)\n")
    print("status\t [jobid] pings the server to check status and update job status files")
    print("\t on all running and pending jobs if no job specified\n")
    print("out\t <jobid> displays the job.out job output for given job\n")
    print("update\t [jobid] [files...] checkin current job results to results git repository")
    print("\t with no files listed uses gruntres.py script to generate list, else uses files")
    print("\t with no jobid it does generic update on all running jobs")
    print("\t automatically does link on jobs to make easy to access from orig source\n")
    print("pull\t grab any updates to jobs and results repos (done for any cmd)\n")
    print("link\t <jobid...> make symbolic links into local gresults/jobid for job results")
    print("\t this makes it easier to access the results -- this happens automatically at update\n")
    print("nuke\t <jobid...> deletes given job directory (jobs and results) -- use carefully!")
    print("\t useful for mistakes etc -- better to use delete for no-longer-relevant but valid jobs\n")
    print("delete\t <jobid...> moves job directory from active to delete subdir")
    print("\t useful for removing clutter of no-longer-relevant jobs, while retaining a record just in case\n")
    print("archive\t <jobid...> moves job directory from active to archive subdir")
    print("\t useful for removing clutter from active, and preserving important but non-current results\n")
    print("newproj\t <projname> [remote-url] creates new project repositories -- for use on both server")
    print("\t and client -- on client you should specify the remote-url arg which should be:")
    print("\t just your username and server name on server: username@server.my.university.edu\n")
    exit(0)

cmd = sys.argv[1]    

# always pull except when making new proj    
if cmd != "newproj":
    pull_jobs_repo()
    active_jobs_list()

if (cmd == "submit"):
    if (not os.path.isfile("grunter.py")):
        print("Error: grunter.py grunt extensible runner script needed to submit on server -- configure as neede!")
        exit(1)
    new_jobid()
    new_job = os.path.join(grunt_jobs, "active", grunt_jobid, grunt_proj) # add proj subdir so build works
    copy_to_jobs(new_job)
    os.chdir(new_job)
    write_string("job.submit", timestamp())
    grunt_jobs_repo.git.add(os.path.join(new_job,'job.submit'))
    if len(sys.argv) > 2:
        with open("job.args","w") as f:
            for arg in sys.argv[2:]:
                f.write(arg + "\n")
        grunt_jobs_repo.git.add(os.path.join(new_job,'job.args'))
    write_cmd(grunt_jobid, cmd, timestamp())
    grunt_jobs_repo.index.commit("Submit job: " + grunt_jobid)
    grunt_jobs_repo.remotes.origin.push()
    exit(0)
elif (cmd == "jobs"):
    if len(sys.argv) < 3:
        print_jobs(jobs_done, "Done Jobs")
        print_jobs(jobs_pending, "Pending Jobs")
        print_jobs(jobs_running, "Running Jobs")
    else:
        if sys.argv[2] == "done":
            print_jobs(jobs_done, "Done Jobs")
        else:
            print_jobs(jobs_pending, "Pending Jobs")
            print_jobs(jobs_running, "Running Jobs")
    exit(0)
elif (cmd == "status"):
    # special support to use active jobs
    if len(sys.argv) == 2:
        for jb in jobs_pending:
            grunt_jobid = jb[0]
            write_cmd(grunt_jobid, cmd, timestamp())
        for jb in jobs_running:
            grunt_jobid = jb[0]
            write_cmd(grunt_jobid, cmd, timestamp())
        commit_cmd(cmd)
    else:           
        for jb in sys.argv[2:]:
            grunt_jobid = jb
            write_cmd(grunt_jobid, cmd, timestamp())
        commit_cmd(cmd)
    exit(0)
elif (cmd == "out"):
    if len(sys.argv) < 3:
        print(cmd + " requires jobs.. args")
        exit(1)
    for jb in sys.argv[2:]:
        grunt_jobid = jb
        print_job_out(grunt_jobid)
    exit(0)
elif (cmd == "nuke"):
    if len(sys.argv) < 3:
        print(cmd + " requires jobs.. args")
        exit(1)
    for jb in sys.argv[2:]:
        grunt_jobid = jb
        write_cmd(grunt_jobid, cmd, timestamp())
        unlink_results(grunt_jobid)
    commit_cmd(cmd)
    exit(0)
elif (cmd == "archive"):
    if len(sys.argv) < 3:
        print(cmd + " requires jobs.. args")
        exit(1)
    for jb in sys.argv[2:]:
        grunt_jobid = jb
        write_cmd(grunt_jobid, cmd, timestamp())
        unlink_results(grunt_jobid)
    commit_cmd(cmd)
    exit(0)
elif (cmd == "delete"):
    if len(sys.argv) < 3:
        print(cmd + " requires jobs.. args")
        exit(1)
    grunt_jobid = sys.argv[2]
    write_commit_cmd(grunt_jobid, cmd, timestamp())
    unlink_results(grunt_jobid)
elif (cmd == "pull"):
    print("pulling current results from: " + grunt_results)
    pull_results_repo()
    exit(0)
elif (cmd == "link"):
    if len(sys.argv) < 3:
        print(cmd + " requires jobs.. args")
        exit(1)
    for jb in sys.argv[2:]:
        grunt_jobid = jb
        link_results(grunt_jobid)
    exit(0)
elif (cmd == "update"):
    pull_jobs_repo()
    if len(sys.argv) < 3:
        for jb in jobs_running:
            grunt_jobid = jb[0]
            write_cmd(grunt_jobid, cmd, timestamp())
            link_results(grunt_jobid)
        # todo: go through jobs_done, look for case where job.end is later than grcmd.update
        # and update those -- should be pretty easy!
        commit_cmd(cmd)
    elif len(sys.argv) == 3:
        grunt_jobid = sys.argv[2]
        write_commit_cmd(grunt_jobid, "update", timestamp())
        link_results(grunt_jobid)
    else: # jobs, files
        grunt_jobid = sys.argv[2]
        write_commit_cmd(grunt_jobid, "update", argslist())
        link_results(grunt_jobid)
    exit(0)
elif (cmd == "newproj"):
    if len(sys.argv) < 3:
        print("newproj command requires name of project")
        exit(1)
    projnm = sys.argv[2]
    remote = ""
    if len(sys.argv) == 4:
        remote = sys.argv[3]
    init_repos(projnm, remote)
    exit(0)
else:
    # generic command -- just pass onto server
    if len(sys.argv) < 3:
        print(cmd + " requires jobs.. args")
        exit(1)
    for jb in sys.argv[2:]:
        grunt_jobid = jb
        write_cmd(grunt_jobid, cmd, timestamp())
    commit_cmd(cmd)
    exit(0)
    
