# this is the grunt git-based run daemon sub-script: https://github.com/emer/grunt
# this is the inner-loop grunt daemon that is spawned by grund.py for each project working directory
# it is passed the arg: ~/grunt/wc/server/username/projname to process

from git import Repo
import os
import sys
import subprocess
from subprocess import Popen, PIPE
import shutil
import glob
from datetime import datetime, timezone
import csv

# turn this on to see more verbose debug messages
grunt_debug = False

# grunt_wc is the working dir for project: ~/grunt/wc/server/username/projname
grunt_wc = ""

# grunt_jobs is the jobs git working dir for project: ~/grunt/wc/server/username/projname/jobs
grunt_jobs = ""

# grunt_jobs_repo is active git repo handle
grunt_jobs_repo = 0

# grunt_results is the jobs git working dir for project: ~/grunt/wc/server/username/projname/results
grunt_results = ""

# grunt_results_repo is active git repo handle
grunt_results_repo = 0

# grunt_jobs_shafn is the sha filename that we use to track what has been processed
grunt_jobs_shafn = ""

# grunt_jobid is the current jobid code
grunt_jobid = ""

# grunt_job is current job file relative to grunt_jobs
# set by master update loop
grunt_job = ""

# grunt_jobdir is current job directory relative to grunt_jobs
# e.g., active/jobid/projname
# set by get_command
grunt_jobdir = ""

# grunt_jobpath is current full job path: grunt_jobs/grunt_jobdir
# set by get_command
grunt_jobpath = ""

# grunt_jobfnm is current job filename -- grcmd.*
# set by get_command
grunt_jobfnm = ""

# grunt_cmd is current command -- part after grcmd.
# set by get_command
grunt_cmd = ""

# last_commit_done_hash is the git hash for the last jobs commit that
# has at least started to be processed
last_commit_done_hash = ""

# cur_commit_hash is the git hash for the current repo head that we
# are currently processing -- this will be last_commit_done_hash
# next time through
cur_commit_hash = ""

# get_command gets job file paths based on a job_file which is relative to project 
# returns True if is a valid command file, otherwise False
def get_command(job_file):
    global grunt_jobdir, grunt_jobpath, grunt_jobid, grunt_jobfnm, grunt_cmd
    file_split = os.path.split(job_file)
    fnm = file_split[1]
    prefix = "grcmd."
    if not fnm.startswith(prefix):
        return False
    grunt_jobfnm = fnm
    grunt_cmd = fnm[len(prefix):]
    grunt_jobdir = file_split[0]
    grunt_jobpath = os.path.join(grunt_jobs, grunt_jobdir)
    grunt_jobid = os.path.split(grunt_jobdir)[1]
    return True

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

def utc_to_local(utc_dt):
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=None)    

def timestamp_local(dt):
    # returns a string of datetime object in local time -- for printing
    return utc_to_local(dt).strftime("%Y-%m-%d %H:%M:%S %Z")

def timestamp_fmt(dt):
    # returns a string of datetime object formatted in standard timestamp format
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")

def parse_timestamp(dtstr):
    # returns a datetime object from timestamp-formatted string, None if not properly formatted
    try:
        dt = datetime.strptime(dtstr, "%Y-%m-%d %H:%M:%S %Z")
    except ValueError as ve:
        # print(str(ve))
        return None
    return dt

def timestamp():
    return timestamp_fmt(datetime.now(timezone.utc))

def read_timestamp(fnm):
    # read timestamp from file -- returns None if file does not exist or timestamp format is invalid
    if not os.path.isfile(fnm):
        return None
    return parse_timestamp(read_string(fnm))

def read_timestamp_to_local(fnm):
    # read timestamp from file -- if can be converted to local time, then do that, else return string
    if not os.path.isfile(fnm):
        return ""
    dstr = read_string(fnm)
    dt = parse_timestamp(dstr)
    if dt == None:
        return dstr
    return timestamp_local(dt)
    

def write_status(fnm):
    # writes current status in a status file: timestamp, jobs commit
    with open(fnm,"w") as f:
        f.write("time: " + timestamp() + "\n")
        f.write("commit_done: " + last_commit_done_hash + "\n")
        f.write("commit_cur: " + cur_commit_hash + "\n")
       
file_list_header = ["File", "Size", "Modified"]
    
def list_files(ldir):
    # returns a list of files in directory with fields as in file_list_header
    fls = os.listdir(ldir)
    flist = []
    for f in fls:
        fp = os.path.join(ldir, f)
        if not os.path.isfile(fp):
            continue
        if f[0] == '.' or f.startswith("job.") or f.startswith("grcmd.") or f == "grunter.py":
            continue
        mtime = timestamp_fmt(datetime.fromtimestamp(os.path.getmtime(fp), timezone.utc))
        sz = os.path.getsize(fp)
        flist.append([f, sz, mtime])
    flist.sort()
    return flist

# add job files adds all files named job.* in current dir
def add_job_files(jobid):
    os.chdir(grunt_jobpath)
    flist = list_files("./")
    write_csv("job.list", file_list_header, flist)
    jobfiles = "\n".join(glob.glob("job.*"))
    grunt_jobs_repo.remotes.origin.push()
    for f in jobfiles.splitlines():
        grunt_jobs_repo.git.add(os.path.join(grunt_jobdir, f))

# call the grunter user-script with command
def call_grunter(grcmd):
    print("Calling grunter for job: " + grunt_jobdir + " cmd: " + grcmd, flush=True)
    os.chdir(grunt_jobpath)
    if (not os.path.isfile("grunter.py")):
        print("Error: grunter.py script not found -- MUST be present!", flush=True)
        return
    try:
        subprocess.run(["python3","grunter.py", grcmd])
    except subprocess.SubprocessError as e:
        print("grunter.py script error: " + str(e), flush=True)
        return
    add_job_files(grunt_jobid)
        
def results_job():
    os.chdir(grunt_jobpath)
    jfn = os.path.join(grunt_jobpath, grunt_jobfnm)
    ts = read_timestamp(jfn)
    rdir = os.path.join(grunt_results,grunt_jobdir)
    if not os.path.isdir(rdir):
        os.makedirs(rdir)
    if ts == None: # not a timestamp -- must be files!
        fnms = read_strings_strip(jfn)
        for f in fnms:
            if len(f) == 0:  # why is it even doing this?
                continue
            rf = os.path.join(rdir,f)
            try:
                shutil.copyfile(f, rf)
            except OSError as e:
                print("copy err: " + str(e), flush=True)
            print("added results: " + rf, flush=True)
            grunt_results_repo.git.add(os.path.join(grunt_jobdir,f))
    else:
        if (not os.path.isfile("grunter.py")):
            print("Error: grunter.py script not found -- MUST be present!", flush=True)
            return
        p = ""
        try:
            p = subprocess.check_output(["python3", "grunter.py", "results"], universal_newlines=True)
        except subprocess.SubprocessError as e:
            print("grunter results error: " + str(e), flush=True)
            return
        for f in p.splitlines():
            if len(f) == 0:  # why is it even doing this?
                continue
            rf = os.path.join(rdir,f)
            try:
                shutil.copyfile(f, rf)
            except OSError as e:
                print("copy err: " + str(e), flush=True)
            print("added results: " + rf, flush=True)
            grunt_results_repo.git.add(os.path.join(grunt_jobdir,f))
    add_job_files(grunt_jobid)

def delete_job():
    jdir = os.path.split(grunt_jobdir)[0]
    sli = grunt_jobdir.index("/")
    deldir = "delete" + jdir[sli:]
    os.chdir(grunt_jobs)
    try:
        subprocess.run(["git", "mv", jdir, deldir])
    except subprocess.SubprocessError as e:
        print("git mv error: " + str(e), flush=True)
    os.chdir(grunt_results)
    try:
        subprocess.run(["git", "rm", "-r", "-f", jdir])
    except subprocess.SubprocessError as e:
        print("git rm error: " + str(e), flush=True)
    shutil.rmtree(jdir, ignore_errors=True, onerror=None)

def archive_job():
    jdir = os.path.split(grunt_jobdir)[0]
    sli = grunt_jobdir.index("/")
    deldir = "archive" + jdir[sli:]
    os.chdir(grunt_jobs)
    try:
        subprocess.run(["git", "mv", jdir, deldir])
    except subprocess.SubprocessError as e:
        print("git mv error: " + str(e), flush=True)
    os.chdir(grunt_results)
    try:
        subprocess.run(["git", "mv", jdir, deldir])
    except subprocess.SubprocessError as e:
        print("git mv error: " + str(e), flush=True)

def nuke_job():
    jdir = os.path.split(grunt_jobdir)[0]
    os.chdir(grunt_jobs)
    try:
        subprocess.run(["git", "rm", "-r", "-f", jdir])
    except subprocess.SubprocessError as e:
        print("git rm error: " + str(e), flush=True)
    shutil.rmtree(jdir, ignore_errors=True, onerror=None)
    os.chdir(grunt_results)
    try:
        subprocess.run(["git", "rm", "-r", "-f", jdir])
    except subprocess.SubprocessError as e:
        print("git rm error: " + str(e), flush=True)
    shutil.rmtree(jdir, ignore_errors=True, onerror=None)

def newproj_server():
    jfn = os.path.join(grunt_jobpath, grunt_jobfnm)
    projnm = read_string(jfn)
    if projnm == None:
        print("Error: newproj-server: no valid project name found in: " + grunt_jobfnm, flush=True)
        return
    print("running grunt.py newproj " + projnm, flush=True)
    try:
        subprocess.run(["python3", "grunt.py", "newproj", projnm])
    except subprocess.SubprocessError as e:
        print("newproj error: " + str(e), flush=True)
    
def commit_jobs():
    jstat = os.path.join(grunt_jobs, "grund_status.txt")
    write_status(jstat)
    grunt_jobs_repo.git.add(jstat)
    grunt_jobs_repo.index.commit("GRUND: processed from: " + last_commit_done_hash + " to: " + cur_commit_hash)
    grunt_jobs_repo.remotes.origin.push()
    
def commit_results():
    rstat = os.path.join(grunt_results, "grund_status.txt")
    write_status(rstat)
    grunt_results_repo.git.add(rstat)
    grunt_results_repo.index.commit("GRUND: processed from: " + last_commit_done_hash + " to: " + cur_commit_hash)
    grunt_results_repo.remotes.origin.push()

###################################################################
#  starts running here    
    
if len(sys.argv) != 2:
    print("usage: grund_sub.py ~/grunt/wc/server/username/projname", flush=True)
    print("  1 argument needed, but " + str(len(sys.argv) - 1) + " given", flush=True)
    exit(1)
elif os.path.isdir(sys.argv[1]):
    grunt_wc = sys.argv[1]
    grunt_jobs = os.path.join(grunt_wc,"jobs")
    try:
        grunt_jobs_repo = Repo(grunt_jobs)
    except Exception as e:
        print("The directory provided is not a valid grunt jobs git working directory: " + grunt_wc + "! " + str(e), flush=True)
        exit(3)

    grunt_results = os.path.join(grunt_wc,"results")
    try:
        grunt_results_repo = Repo(grunt_results)
    except Exception as e:
        print("The directory provided is not a valid grunt jobs git working directory: " + grunt_wc + "! " + str(e), flush=True)
        exit(3)
else:
    print("The path given is not a valid directory", flush=True)
    exit(2)

grunt_jobs_shafn = os.path.join(grunt_jobs,"last_commit_done.sha")

try:
    grunt_jobs_repo.remotes.origin.pull()
    grunt_results_repo.remotes.origin.pull()
except Exception as e:
    print("git pull errors! " + str(e), flush=True)
    exit(4)

# Check if we have a valid commit sha1 hash as the last processed, so that we can pickup launching from there.

if os.path.isfile(grunt_jobs_shafn):
    with open(grunt_jobs_shafn, "r") as f:
        last_commit_done_hash = f.readline()
    # update immediately to the current hash so even if we crash
    # commands are not repeated!
    cur_commit_hash = str(grunt_jobs_repo.heads.master.commit)
    with open(grunt_jobs_shafn, "w") as f:
        f.write(cur_commit_hash)
    check_for_updates = True
    com_jobs = False
    com_results = False
    if grunt_debug:
        print("Begin processing commits from hash: " + last_commit_done_hash, flush=True)
    last_to_head = last_commit_done_hash + "..HEAD"
    most_recent_head = None
    for cm in grunt_jobs_repo.iter_commits(rev=last_to_head):
        if most_recent_head == None:
            most_recent_head = cm
        if cm.message.startswith("GRUND:"): # skip our own -- key
            continue
        if grunt_debug:
            print("Processing commit " + str(cm), flush=True)
        for f in cm.stats.files:
            if not get_command(f):
                continue
            print("\ngrund command: " + grunt_cmd + " in: " + grunt_jobdir + " at: " + timestamp(), flush=True)
            com_jobs = True
            if grunt_cmd == "results":
                results_job()
                com_results = True
            elif grunt_cmd == "nuke":
                nuke_job()
                com_results = True
            elif grunt_cmd == "archive":
                archive_job()
                com_results = True
            elif grunt_cmd == "delete":
                delete_job()
                com_results = True
            elif grunt_cmd == "newproj-server":
                newproj_server()
            else:
                call_grunter(grunt_cmd)
                com_results = True # often for adding new results
    if com_jobs:            
        commit_jobs()
    if com_results:
        commit_results()
    exit(0)    
else:
    cur_commit_hash = str(grunt_jobs_repo.heads.master.commit)
    last_commit_done_hash = cur_commit_hash
    print(cur_commit_hash)
    with open(grunt_jobs_shafn, "w") as f:
        f.write(cur_commit_hash)
    commit_jobs()
    commit_results()
    exit(0)


