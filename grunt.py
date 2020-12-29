#!/usr/local/bin/python3
# note: on mac cannot change /usr/bin/ so use /usr/local/bin
# must do: pip3 install [--user] gitpython

# this is the grunt git-based run tool script: https://github.com/emer/grunt

import sys
import os
import time
from git import Repo
from distutils.dir_util import copy_tree
import subprocess
from subprocess import Popen, PIPE
import shutil
import json
from pathlib import Path
import getpass
from datetime import datetime, timezone
import csv

# maintains jobs from all servers, but uses the current default server
# for all commands -- use "server" command to set default server
# as name in grunt.server -- global default is in in ~/.grunt.defserver

# grunt servers is the dict of Server objs by name
grunt_servers = {}        
        
# grunt_def_server is default server name -- default is in ~/.grunt.defserver
grunt_def_server = ""

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

# grunt_jobid is the current jobid code: userid + jobnum
grunt_jobid = ""

# grunt_jobnum is the number for jobid
grunt_jobnum = 0

# grunt_proj_dir is ~/grunt/projs/projname -- holds global proj info (grunt.nextjob)
grunt_proj_dir = ""

# lists of different jobs -- updated with list_jobs() at start
jobs_active = []
jobs_done = []
jobs_delete = []
jobs_archive = []
jobs_header =     ["$JobId", "$Server", "$SlurmId", "$Status", "$SlurmStat", "$Submit", "$Start", "$End", "$Args", "$Message"]
jobs_header_sep = ["=======", "=======", "=======", "=======", "=======", "=======", "=======", "=======", "=======", "======="]

def open_servername(fnm):
    global grunt_def_server
    if os.path.isfile(fnm):
        with open(fnm, "r") as f:
            grunt_def_server = str(f.readline()).rstrip()
        # print("server is: " + grunt_def_server + " from: " + fnm)
        return True
    else:
        return False

def get_def_server():
    global grunt_def_server
    cf = "grunt.server"
    if open_servername(cf) and grunt_def_server in grunt_servers:
        print("server: " + grunt_def_server + " from: " + cf)
    else:
        df = os.path.join(str(Path.home()), ".grunt.defserver")
        if open_servername(df) and grunt_def_server in grunt_servers:
            print("server: " + grunt_def_server + " from: " + df)
        else:
            if len(grunt_servers) > 0:
                grunt_def_server = next(iter(grunt_servers))
                print("server: " + grunt_def_server + " first on list")
            else:
                print("Error: no servers found for this project")
                print("you must first create on server using: grunt.py newproj " + grunt_proj)
                print("and then create locally: grunt.py newproj " + grunt_proj + " username@server.at.univ.edu")
                exit(1)

def save_def_server(cnm):
    df = os.path.join(str(Path.home()), ".grunt.defserver")
    with open(df, "w") as f:
        f.write(cnm + "\n")

def save_server(cnm):
    df = "grunt.server"
    with open(df, "w") as f:
        f.write(cnm + "\n")

def prompt_server_name():
    cnm = str(input("Enter name of this server (just host name, no domain etc), saved in ~/.grunt.defserver: "))
    save_def_server(cnm)
    grunt_def_server = cnm

def prompt_def_server():
    cnm = str(input("Enter name of default server, saved in ~/.grunt.defserver: "))
    save_def_server(cnm)
    grunt_def_server = cnm

def get_newproj_server(on_server):
    global grunt_def_server
    cf = "grunt.server"
    if open_servername(cf):
        print("server: " + grunt_def_server + " from: " + cf)
    else:
        df = os.path.join(str(Path.home()), ".grunt.defserver")
        if open_servername(df):
            print("server: " + grunt_def_server + " from: " + df)
        else:
            if on_server:
                prompt_server_name()
            else
                prompt_def_server()

def init_servers():
    get_projname()  # allow override with grunt.projname file
    wc = os.path.join(grunt_root, "wc")
    global grunt_proj_dir
    grunt_proj_dir = os.path.join(grunt_root, "projs", grunt_proj)
    if not os.path.isdir(grunt_proj_dir):
        os.makedirs(grunt_proj_dir)
    maxjob = 0
    for f in os.listdir(wc):
        swc = os.path.join(wc, f, grunt_user, grunt_proj)
        if not os.path.isdir(swc):
            continue
        srv = Server(f)
        grunt_servers[f] = srv
        maxjob = max(maxjob, srv.old_jobnum)
    # legacy: get nextjob from server, now stored in projs directory
    jf = "nextjob.id"
    pjf = os.path.join(grunt_proj_dir, jf)
    if not os.path.isfile(pjf):
        ljf = "grunt.nextjob"
        if os.path.isfile(ljf):   # was local briefly
            shutil.copyfile(ljf, pjf)
            os.remove(ljf)
        else:
            with open(pjf, "w") as f:
                f.write(str(maxjob) + "\n")

def def_server():
    # returns default server, after first doing jobs pull so ready to go
    get_def_server()
    srv = grunt_servers[grunt_def_server]
    srv.pull_jobs()
    list_jobs()
    return srv
    
def open_projname(fnm):
    global grunt_proj
    if os.path.isfile(fnm):
        with open(fnm, "r") as f:
            grunt_proj = str(f.readline()).rstrip()
        return True
    else:
        return False

def get_projname():
    cf = "grunt.projname"
    if open_projname(cf):
        print("using alt projname: " + grunt_proj + " from: " + cf)
            
def new_jobid():
    global grunt_jobnum, grunt_jobid
    jf = "nextjob.id"
    pjf = os.path.join(grunt_proj_dir, jf)
    if os.path.isfile(pjf):
        with open(pjf, "r+") as f:
            grunt_jobnum = int(f.readline())
            f.seek(0)
            f.write(str(grunt_jobnum + 1) + "\n")
    else:
        grunt_jobnum = 1
        with open(pjf, "w") as f:
            f.write(str(grunt_jobnum + 1) + "\n")
    grunt_jobid = grunt_userid + str(int(grunt_jobnum)).zfill(6)
    print("grunt_jobid: " + grunt_jobid)

def pull_jobs_repo():
    for sname, srv in grunt_servers.items():
        srv.pull_jobs()

def pull_results_repo():
    for sname, srv in grunt_servers.items():
        srv.pull_results()

def write_csv(fnm, header, data):
    with open(fnm, 'w') as csvfile: 
        csvwriter = csv.writer(csvfile) 
        csvwriter.writerow(header) 
        csvwriter.writerows(data)

def read_csv(fnm, header):
    # reads list data from file -- if header is True then discards first row as header
    data = []
    with open(fnm) as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',')
        lc = 0
        for row in csvreader:
            if header and lc == 0:
                lc += 1
            else:
                data.append(row)
                lc += 1
    return data
    
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
    
def argslist():
    # argslist returns post-command args as newline separated string 
    # for use in command files
    return "\n".join(sys.argv[3:])

def jobid_fm_jobs_list(lst):
    return lst[0]
    
def read_job_info(jobid, pdir, sname):
    # returns a standard job record from given directory, with "done" or "active" status at start
    jdir = os.path.join(pdir, jobid, grunt_proj)
    jst = os.path.join(jdir, "job.start")
    jed = os.path.join(jdir, "job.end")
    jcan = os.path.join(jdir, "job.canceled")
    jslid = os.path.join(jdir, "job.slurmid")
    args = " ".join(read_strings_strip(os.path.join(jdir, "job.args")))
    slurmid = read_string(jslid)
    slurmstat = read_string(os.path.join(jdir, "job.status"))
    msg = read_string(os.path.join(jdir, "job.message"))
    sub = read_timestamp_to_local(os.path.join(jdir, "job.submit"))
    st = read_timestamp_to_local(jst)
    ed = read_timestamp_to_local(jed)
    if os.path.isfile(jcan):
        ed = read_timestamp_to_local(jcan)
        return ("done", [jobid, sname, slurmid, "Canceled", slurmstat, sub, st, ed, args, msg])
    elif os.path.isfile(jst) and os.path.isfile(jslid):
        if os.path.isfile(jed):
            return ("done", [jobid, sname, slurmid, "Done", slurmstat, sub, st, ed, args, msg])
        else:
            return ("active", [jobid, sname, slurmid, "Running", slurmstat, sub, st, "", args, msg])
    else:
        return ("active", [jobid, sname, "", "Pending", slurmstat, sub, st, ed, args, msg])
    
    
def list_jobs():
    # generates lists of jobs from server with statuses
    global jobs_active, jobs_done, jobs_delete, jobs_archive
    jobs_active = []
    jobs_done = []
    jobs_delete = []
    jobs_archive = []
    jdirs = ["active", "archive", "delete"]
    for sname, srv in grunt_servers.items():
        for jd in jdirs:
            jdir = os.path.join(srv.jobs, jd)
            for jobid in os.listdir(jdir):
                if not jobid.startswith(grunt_userid):
                    continue
                (st, jr) = read_job_info(jobid, jdir, sname)
                if jd == "active":
                    if st == "active":
                        jobs_active.append(jr)
                    else: # done
                        jobs_done.append(jr)
                elif jd == "archive":
                    jobs_archive.append(jr)
                elif jd == "delete":
                    jobs_delete.append(jr)
    jobs_active.sort(key=jobid_fm_jobs_list)
    jobs_done.sort(key=jobid_fm_jobs_list)
    jobs_archive.sort(key=jobid_fm_jobs_list)
    jobs_delete.sort(key=jobid_fm_jobs_list)
    write_csv("jobs.active", jobs_header, jobs_active) 
    write_csv("jobs.done", jobs_header, jobs_done) 
    write_csv("jobs.archive", jobs_header, jobs_archive) 
    write_csv("jobs.delete", jobs_header, jobs_delete) 

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

def find_job_impl(jid, jlist):
    # find given job id in job list -- return None if not found
    # job id can be either full len 9 id, or just a number
    if len(jid) == 9:
        for jr in jlist:
            if jr[0] == jid:
                return jr
        return None
    if int(jid[0]) > 0:
        jid = '0' + jid
    for jr in jlist:
        if jr[0].endswith(jid):
            return jr
    return None
    
def find_job(jid):
    # find given job id in jobs_active, jobs_done -- returns None if not found -- see also find_other_job
    jr = find_job_impl(jid, jobs_active)
    if not jr is None:
        return jr
    jr = find_job_impl(jid, jobs_done)
    if not jr is None:
        return jr
    return None
    
def find_other_job(jid):
    # find given job id in jobs_delete, jobs_archive -- returns name of list as first rval
    jr = find_job_impl(jid, jobs_archive)
    if not jr is None:
        return ("archive", jr)
    jr = find_job_impl(jid, jobs_delete)
    if not jr is None:
        return ("delete", jr)
    return None
    
def glob_job_args(jl):
    # this gets a list of jobids that expands ranges of the form [job00000]1..300
    njl = jl.copy()
    for i in range(len(jl)):
        j = njl[i]
        ddi = j.index("..") if ".." in j else None
        if ddi == None:
            jr = find_job(j)
            if jr is None:
                jr = find_other_job(j)
                if jr is None:
                    del njl[i]
                    continue
                else:
                    jr = jr[1]
            njl[i] = jr[0] # get official one
            continue
        sts = j[:ddi]
        eds = j[ddi+2:]
        if eds[0] == ".": # allow for ... as go people might do that..
            eds = eds[1:]
        st = int(sts[3:])
        ed = int(eds)
        first = True
        for jn in range(st, ed+1):
            jns = sts[:len(sts)-len(eds)] + str(jn).zfill(len(eds))
            if find_job(jns) is None:
                if find_other_job(jns) is None:
                    continue
            if first:
                njl[i] = jns
                first = False
            else:
                njl.append(jns)

    return njl

def jobids(jdir):
    # returns the list of jobid's in given directory
    fls = os.listdir(jdir)
    jids = []
    for f in fls:
        fp = os.path.join(jdir, f)
        if not os.path.isdir(fp):
            continue
        if f[:3] != grunt_userid:
            continue
        jids.append(f)
    jids.sort()
    return jids

file_list_header = ["File", "Size", "Modified"]
file_list_sep = ["===============", "================", "======================="]
    
def list_files(ldir):
    # returns a list of files in directory with fields as in file_list_header
    fls = os.listdir(ldir)
    flist = []
    for f in fls:
        fp = os.path.join(ldir, f)
        if not os.path.isfile(fp):
            continue
        if f[0] == '.':
            continue
        mtime = timestamp_fmt(datetime.fromtimestamp(os.path.getmtime(fp), timezone.utc))
        sz = os.path.getsize(fp)
        flist.append([f, sz, mtime])
    flist.sort()
    return flist
    
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
    wc = os.path.join(grunt_root, "wc", grunt_def_server, grunt_user, projnm)
    
    if os.path.isdir(wc):
        return

    bb = os.path.join(grunt_root, "bb", grunt_def_server, grunt_user, projnm)
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
        remote_url = remote + ":grunt/bb/" + grunt_def_server + "/" + user + "/" + projnm
        jobs_wc_repo = Repo.init(wc_jobs)
        res_wc_repo = Repo.init(wc_res)
        set_remote(jobs_wc_repo, remote_url + "/jobs")
        set_remote(res_wc_repo, remote_url + "/results")

        
class Server(object):
    """
    Server has everything for one server
    """
    
    def __init__(self, srv):
        self.name = srv
        self.wc = os.path.join(grunt_root, "wc", self.name, grunt_user, grunt_proj)
        self.jobs = os.path.join(self.wc, "jobs")
        self.active = os.path.join(self.jobs, "active")
        self.results = os.path.join(self.wc, "results")
        self.jobs_repo = 0
        self.results_repo = 0
        self.jobs_repo_open = False
        self.results_repo_open = False
        self.old_jobnum = 0
        jf = os.path.join(self.active, "nextjob.id")
        if os.path.isfile(jf):
            with open(jf, "r") as f:
                self.old_jobnum = int(f.readline())
        
    def open_jobs(self):
        # opens jobs repository if not otherwise
        if self.jobs_repo_open:
            return
        try:
            self.jobs_repo = Repo(self.jobs)
        except Exception as e:
            print("The directory is not a valid grunt jobs git working directory: " + self.jobs + "! " + str(e))
            exit(3)
        self.jobs_repo_open = True
        # print(self.jobs_repo)
        
    def pull_jobs(self):
        # does git pull on jobs repository 
        self.open_jobs()
        try:
            self.jobs_repo.remotes.origin.pull()
        except git.exc.GitCommandError as e:
            print("Could not execute a git pull on jobs repository " + self.jobs + str(e))
        
    def open_results(self):
        # opens results repository if not otherwise
        if self.results_repo_open:
            return
        try:
            self.results_repo = Repo(self.results)
        except Exception as e:
            print("The directory is not a valid grunt results git working directory: " + self.results + "! " + str(e))
            exit(3)
        self.results_repo_open = True
        # print(self.results_repo)
        
    def pull_results(self):
        # does git pull on results repository 
        self.open_results()
        try:
            self.results_repo.remotes.origin.pull()
        except git.exc.GitCommandError as e:
            print("Could not execute a git pull on results repository " + self.results + str(e))
        glog = self.results_repo.head.reference.log()
        ts = timestamp_local(datetime.fromtimestamp(glog[-1].time[0], timezone.utc))
        print("From pull   at: " + timestamp_local(datetime.now(timezone.utc)))    
        print("Last commit at: " + ts)
    
    def copy_grunter_to_jobs(self, jobid):
        # copies grunter to jobs
        self.open_jobs()
        f = "grunter.py"
        jf = os.path.join(self.active, jobid, grunt_proj, f)
        try:
            shutil.copyfile(f, jf)
        except Exception as e:
            pass
        self.jobs_repo.git.add(jf)
    
    def copy_to_jobs(self, new_job):
        # copies current git-controlled files to new_job dir in jobs wc
        p = subprocess.check_output(["git","ls-files"], universal_newlines=True)
        os.makedirs(new_job)
        gotGrunter = False
        for f in p.splitlines():
            if f == "grunter.py":
                gotGrunter = True
            dirnm = os.path.dirname(f)
            if dirnm:
                jd = os.path.join(new_job,dirnm)
                os.makedirs(jd)
            jf = os.path.join(new_job,f)
            shutil.copyfile(f, jf)
            self.jobs_repo.git.add(jf)
        if not gotGrunter:
            f = "grunter.py"
            jf = os.path.join(new_job, f)
            shutil.copyfile(f, jf)
            self.jobs_repo.git.add(jf)

    def print_job_out(self, jdir, jobid):
        job_out = os.path.join(self.jobs, jdir, jobid, grunt_proj, "job.out")
        print("output from job: %s" % (job_out))
        out = read_strings(job_out)
        print("".join(out))
        print()
            
    def print_job_list(self, jdir, jobid):
        job_ls = os.path.join(self.jobs, jdir, jobid, grunt_proj, "job.list")
        fl = read_csv(job_ls, True)
        for row in fl:
            row[1] = "{:,}".format(int(row[1])).rjust(16)
            row[2] = timestamp_local(parse_timestamp(row[2]))
        fl.insert(0, file_list_header)
        fl.insert(1, file_list_sep)
        s = [[str(e) for e in row] for row in fl]
        lens = [max(1,max(map(len, col))) for col in zip(*s)]
        fmt = '\t'.join('{{:{}s}}'.format(x) for x in lens)
        table = [fmt.format(*row) for row in s]
        print("files from job: %s" % (job_ls))
        print('\n'.join(table))
        print()
            
    def print_job_file(self, jobid, jobfile):
        job_dir = os.path.join(self.active, jobid, grunt_proj)
        fn = os.path.join(job_dir, jobfile)
        fc = read_strings_strip(fn)
        print("job: " + jobid + " file: " + fn)
        for r in fc:
            print(r)
        
    def diff_jobs(self, jdir1, jobid1, jdir2, jobid2):
        job1 = os.path.join(self.jobs, jdir1, jobid1, grunt_proj)
        job2 = os.path.join(self.jobs, jdir2, jobid2, grunt_proj)
        subprocess.run(["diff","-uw","-x", "job.*", "-x", "grcmd.*", job1, job2])
            
    def diff_job(self, jdir, jobid):
        job = os.path.join(self.jobs, jdir, jobid, grunt_proj)
        subprocess.run(["diff","-uw", "-x", "job.*", "-x", "jobs.*", "-x", "grcmd.*", "-x", "gresults", "-x", ".*", "./", job])
            
    def done_job_needs_results(self, jobid):
        # if job.end is later than grcmd.results (or it doesn't even exist), then needs results
        jobdir = os.path.join(self.active, jobid, grunt_proj)
        updtcmd = os.path.join(jobdir, "grcmd.results")
        if not os.path.isfile(updtcmd):
            return True
        updtime = read_timestamp(updtcmd)
        if updtime == None:
            return True
        job_end = os.path.join(jobdir, "job.end")
        endtime = read_timestamp(job_end)
        if endtime == None:
            write_string(job_end, timestamp()) # rewrite to avoid 
            return True
        if endtime > updtime:
            print("endtime: " + timestamp_fmt(endtime) + " > updtime: " + timestamp_fmt(updtime))
            return True
        return False
            
    def link_results(self, jobid):
        res = os.path.join(self.results, "active", jobid, grunt_proj)
        dst = os.path.join("gresults", jobid)
        if not os.path.isdir("gresults"):
            os.makedirs("gresults")
        if not os.path.islink(dst):
            os.symlink(res, dst, target_is_directory=False)
            print("linked: " + res + " -> " + dst)
            
    def unlink_results(self, jobid):
        dst = os.path.join("gresults", jobid)
        if not os.path.isdir("gresults"):
            return
        if os.path.islink(dst):
            os.unlink(dst)
            print("unlinked: " + dst)
        else:
            print("job was not linked: %s" % (dst))
        
    def write_cmd(self, jobid, cmd, cmdstr):
        self.open_jobs()
        self.copy_grunter_to_jobs(jobid)
        job_dir = os.path.join(self.active, jobid, grunt_proj)
        cmdfn = os.path.join(job_dir, "grcmd." + cmd)
        with open(cmdfn,"w") as f:
            f.write(cmdstr + "\n")
        self.jobs_repo.git.add(cmdfn)
        print("job: " + jobid + " command: " + cmd + " = " + cmdstr)
        
    def commit_cmd(self, cmd):
        self.open_jobs()
        self.jobs_repo.index.commit("Command: " + cmd)
        self.jobs_repo.remotes.origin.push()
    
    def write_commit_cmd(self, jobid, cmd, cmdstr):
        self.write_cmd(jobid, cmd, cmdstr)
        self.commit_cmd(cmd)
    
    def clean_jobs(self):
        self.open_jobs()
        print("cleaned  jobs dir: " + self.jobs)
        self.jobs_repo.git.clean("-xfd")
        
        
##########################################################    
# Running starts here

if len(sys.argv) < 2 or sys.argv[1] == "help":
    print("\ngrunt.py is the git-based run tool client script\n")
    print("usage: pass commands with args as follows:")
    print("\t <jobid..> can include space-separated list and job000011..22 range expressions")
    print("\t end number is *inclusive*!\n")

    print("uses grunt.server for submit, gets updates from it automatically -- use 'server' to set\n")
    print("server\t name \t sets default server to given server name\n")

    print("submit\t [args] -m 'message' \t submits git controlled files in current dir to jobs working dir:")
    print("\t ~/grunt/wc/username/projdir/jobs/active/jobid -- also saves option args to job.args")
    print("\t which grunter.py script uses for passing args to job -- must pass message as last arg!")
    print("\t git commit triggers update of server git repo, and grund daemon then submits the new job.")
    print("\t you *must* have grunter.py script in the project dir to manage actual submission!")
    print("\t see example in https://github.com/emer/grunt repository.\n")

    print("jobs\t [active|done|archive|delete] \t shows lists of all jobs, or specific subset")
    print("\t (active = running, pending) -- ONLY reflects the last status results:")
    print("\t do status to get latest job status from server, then jobs again in ~10 sec\n")

    print("status\t [jobid] \t pings the server to check status and update job status files")
    print("\t on all active (running and pending) jobs if no job specified -- use jobs to see results\n")

    print("results\t <jobid..> \t push current job results to results git repository")
    print("\t the specific files to get are returned by the result() function in grunter.py")
    print("\t with no jobid it gets results on all running jobs.")
    print("\t automatically does link on jobs to make easy to access from orig source.\n")

    print("files\t jobid [files..] \t push given files for given job to results git repository")
    print("\t automatically does link on jobs to make easy to access from orig source.\n")

    print("pull\t grab any updates to jobs and results repos (done for any cmd)\n")

    print("out\t <jobid..> \t displays the job.out output for given job(s)\n")

    print("ls\t <jobid..> \t displays the job.list file list for given job(s)\n")

    print("message\t jobid 'message' \t write a new job.message for given job\n")

    print("diff\t <jobid1> [jobid2] \t displays the diffs between either given job and current")
    print("\t directory, or between two jobs directories\n")

    print("link\t <jobid..> \t make symbolic links into local gresults/jobid for job results")
    print("\t this makes it easier to access the results -- this happens automatically in results cmd\n")

    print("cancel\t <jobid..> \t cancel job on server\n")

    print("nuke\t <jobid..> \t deletes given job directory (jobs and results) -- use carefully!")
    print("\t useful for mistakes etc -- better to use delete for no-longer-relevant but valid jobs\n")

    print("delete\t <jobid..> \t moves job directory from active to delete subdir, deletes results")
    print("\t useful for removing clutter of no-longer-relevant jobs, while retaining a record just in case\n")

    print("archive\t <jobid..> \t moves job directory from active to archive subdir")
    print("\t useful for removing clutter from active, and preserving important but non-current results\n")

    print("clean\t cleans the job git directory -- if any strange ghost jobs appear in listing, do this")
    print("\t this deletes any files that are present locally but not remotely -- should be safe for jobs")
    print("\t except if in the process of running a command, so just wait until all current activity is done\n")

    print("queue\t calls queue command in grunter.py, prints resulting job.queue file\n")
    
    print("newproj\t <projname> [remote-url] \t creates new project repositories -- for use on both server")
    print("\t and client -- on client you should specify the remote-url arg which should be:")
    print("\t just your username and server name on server: username@server.my.university.edu\n")

    print("newproj-server\t <projname> \t calls: newproj projname on server -- use in existing proj")
    print("\t to create a new project\n")
    exit(0)

cmd = sys.argv[1]    

if (cmd == "newproj"):
    if len(sys.argv) < 3:
        print("newproj command requires name of project")
        exit(1)
    projnm = sys.argv[2]
    remote = ""
    if len(sys.argv) == 4:
        remote = sys.argv[3]
    on_server = (remote == "")
    get_newproj_server(on_server)
    init_repos(projnm, remote)
    exit(0)

# always list jobs regardless
init_servers()
list_jobs()

if (cmd == "submit"):
    srv = def_server()
    narg = len(sys.argv)
    if narg < 4:
        print("Error: must at least pass -m 'message' args to submit -- very important to document each job!")
        exit(1)
    if sys.argv[narg-2] != "-m":
        print("Error: the -m 'message' args must be at end of args list -- very important to document each job!")
        exit(1)
    message = sys.argv[narg-1]
    if (not os.path.isfile("grunter.py")):
        print("Error: grunter.py grunt extensible runner script needed to submit on server -- configure as needed!")
        exit(1)
    new_jobid()
    new_job = os.path.join(srv.active, grunt_jobid, grunt_proj) # add proj subdir so build works
    srv.copy_to_jobs(new_job)
    os.chdir(new_job)
    write_string("job.submit", timestamp())
    srv.jobs_repo.git.add(os.path.join(new_job,'job.submit'))
    write_string("job.message", message)
    srv.jobs_repo.git.add(os.path.join(new_job,'job.message'))
    with open("job.args","w") as f:
        for i in range(2, narg-2):
            arg = sys.argv[i]
            f.write(arg + "\n")
    srv.jobs_repo.git.add(os.path.join(new_job,'job.args'))
    srv.write_cmd(grunt_jobid, cmd, timestamp())
    srv.jobs_repo.index.commit("Submit job: " + grunt_jobid + " " + message)
    srv.jobs_repo.remotes.origin.push()
elif (cmd == "server"):
    if len(sys.argv) < 3:
        print("Error: must pass server name")
        exit(1)
    save_server(sys.argv[2])
elif (cmd == "message"):
    if len(sys.argv) != 4:
        print("Error: must pass exactly 2 args: jobid and new message to write")
        exit(1)
    jb = sys.argv[2]
    jr = find_job(jb)
    if jr is None:
        print("diff: job not found:", jb)
        exit(1)
    ts = grunt_servers[jr[1]]
    ts.pull_jobs()
    msg = sys.argv[3]
    jdir = os.path.join(ts.active, jb, grunt_proj)
    jmsg = os.path.join(jdir, "job.message")
    write_string(jmsg, msg)
    ts.jobs_repo.index.commit("Update message: " + jb + " " + msg)
    ts.jobs_repo.remotes.origin.push()
elif (cmd == "jobs"):
    srv = def_server() # pull jobs, update list
    if len(sys.argv) < 3:
        print_jobs(jobs_done, "Done Jobs")
        print_jobs(jobs_active, "Active Jobs")
    else:
        if sys.argv[2] == "done":
            print_jobs(jobs_done, "Done Jobs")
        elif sys.argv[2] == "archive":
            print_jobs(jobs_archive, "Archive Jobs")
        elif sys.argv[2] == "delete":
            print_jobs(jobs_delete, "Delete Jobs")
        else:
            print_jobs(jobs_active, "Active Jobs")
elif (cmd == "status"):
    slist = {}
    if len(sys.argv) == 2:
        # special support to use active jobs on default server
        for jb in jobs_active:
            grunt_jobid = jb[0]
            sname = jb[1]
            ts = grunt_servers[sname]
            slist[sname] = ts
            ts.write_cmd(grunt_jobid, cmd, timestamp())
    else:           
        job_args = glob_job_args(sys.argv[2:])
        for jb in job_args:
            grunt_jobid = jb
            jr = find_job(jb)
            if jr is None:
                print("skipping non-active job: %s" % (jb))
                continue
            sname = jr[1]
            ts = grunt_servers[sname]
            slist[sname] = ts
            ts.write_cmd(grunt_jobid, cmd, timestamp())
    for sname, ts in slist.items():
        ts.commit_cmd(cmd)
elif (cmd == "out"):
    if len(sys.argv) < 3:
        print(cmd + " requires jobs.. args")
        exit(1)
    job_args = glob_job_args(sys.argv[2:])
    for jb in job_args:
        grunt_jobid = jb
        jdir = "active"
        jr = find_job(jb)
        if jr is None:
            jr = find_other_job(jb)
            if jr is None:
                continue
            jdir = jr[0]
            jr = jr[1]
        ts = grunt_servers[jr[1]]
        ts.print_job_out(jdir, grunt_jobid)
elif (cmd == "ls" or cmd == "list"):
    if len(sys.argv) < 3:
        print(cmd + " requires jobs.. args")
        exit(1)
    job_args = glob_job_args(sys.argv[2:])
    for jb in job_args:
        grunt_jobid = jb
        jdir = "active"
        jr = find_job(jb)
        if jr is None:
            jr = find_other_job(jb)
            if jr is None:
                continue
            jdir = jr[0]
            jr = jr[1]
        ts = grunt_servers[jr[1]]
        ts.print_job_list(jdir, grunt_jobid)
elif (cmd == "diff"):
    if len(sys.argv) < 3:
        print(cmd + " requires jobs.. args")
        exit(1)
    jb = sys.argv[2]
    jdir = "active"
    jr = find_job(jb)
    if jr is None:
        jr = find_other_job(jb)
        if jr is None:
            print("diff: job not found:", jb)
            exit(1)
        else:
            jdir = jr[0]
            jr = jr[1]
    ts = grunt_servers[jr[1]]
    if len(sys.argv) == 4:
        jb2 = sys.argv[3]
        jr2 = find_job(jb2)
        jdir2 = "active"
        if jr2 is None:
            jr2 = find_other_job(jb2)
            if jr2 is None:
                print("diff: job not found:", jb2)
                exit(1)
            else:
                jdir2 = jr2[0]
                jr2 = jr2[1]
        ts.diff_jobs(jdir, jb, jdir2, jb2)
    else:
        ts.diff_job(jdir, jb)
elif cmd == "nuke" or cmd == "archive" or cmd == "delete":
    if len(sys.argv) < 3:
        print(cmd + " requires jobs.. args")
        exit(1)
    slist = {}
    job_args = glob_job_args(sys.argv[2:])
    for jb in job_args:
        grunt_jobid = jb
        jr = find_job(jb)
        if jr is None:
            print("skipping non-active job: %s" % (jb))
            continue
        sname = jr[1]
        ts = grunt_servers[sname]
        slist[sname] = ts
        ts.write_cmd(grunt_jobid, cmd, timestamp())
        ts.unlink_results(grunt_jobid) # remove from local results
    for sname, ts in slist.items():
        ts.commit_cmd(cmd)
elif (cmd == "pull"):
    srv = def_server()
    print("pulling current results from: " + srv.results)
    srv.pull_results()
elif (cmd == "clean"):
    srv = def_server()
    print("cleaning jobs dir: " + srv.jobs)
    srv.clean_jobs()
elif (cmd == "link"):
    if len(sys.argv) < 3:
        print(cmd + " requires jobs.. args")
        exit(1)
    job_args = glob_job_args(sys.argv[2:])
    for jb in job_args:
        grunt_jobid = jb
        jr = find_job(jb)
        if jr is None:
            print("skipping non-active job: %s" % (jb))
            continue
        sname = jr[1]
        ts = grunt_servers[sname]
        ts.link_results(grunt_jobid)
elif (cmd == "unlink"):
    if len(sys.argv) < 3:
        print(cmd + " requires jobs.. args")
        exit(1)
    job_args = glob_job_args(sys.argv[2:])
    for jb in job_args:
        grunt_jobid = jb
        jr = find_job(jb)
        if jr is None:
            jr = find_other_job(jb)
            if jr is None:
                continue  # shouldn't happen..
            jr = jr[1]
        sname = jr[1]
        ts = grunt_servers[sname]
        ts.unlink_results(grunt_jobid)
elif (cmd == "results"):
    slist = {}
    if len(sys.argv) < 3:
        # special support to use active jobs on default server
        for jb in jobs_active:
            grunt_jobid = jb[0]
            sname = jb[1]
            ts = grunt_servers[sname]
            slist[sname] = ts
            ts.write_cmd(grunt_jobid, cmd, timestamp())
            ts.link_results(grunt_jobid)
        for jb in jobs_done:
            grunt_jobid = jb[0]
            if jb[2] == "Canceled":
                continue
            sname = jb[1]
            ts = grunt_servers[sname]
            if ts.done_job_needs_results(grunt_jobid):
                slist[sname] = ts
                ts.write_cmd(grunt_jobid, cmd, timestamp())
                ts.link_results(grunt_jobid)
    else:
        job_args = glob_job_args(sys.argv[2:])
        for jb in job_args:
            grunt_jobid = jb
            jr = find_job(jb)
            if jr is None:
                print("skipping non-active job: %s" % (jb))
                continue
            sname = jr[1]
            ts = grunt_servers[sname]
            slist[sname] = ts
            ts.write_cmd(grunt_jobid, cmd, timestamp())
            ts.link_results(grunt_jobid)
    for sname, ts in slist.items():
        ts.commit_cmd(cmd)
elif (cmd == "files"):
    if len(sys.argv) < 4:
        print(cmd + " requires job and files.. args")
        exit(1)
    jb = sys.argv[2]
    grunt_jobid = jb
    jr = find_job(jb)
    if jr is None:
        print("files: job not found:", jb)
        exit(1)
    ts = grunt_servers[jr[1]]
    ts.write_commit_cmd(grunt_jobid, "results", argslist())
    ts.link_results(grunt_jobid)
elif (cmd == "queue"):
    if len(jobs_active) == 0:
        print("no active jobs -- can only run with active jobs")
        exit(1)
    jr = jobs_active[-1]
    grunt_jobid = jr[0]
    sname = jr[1]
    ts = grunt_servers[sname]
    ts.write_commit_cmd(grunt_jobid, "queue", timestamp())
    print("waiting for results...")
    time.sleep(15)
    ts.pull_jobs()
    ts.print_job_file(grunt_jobid, "job.queue")
elif (cmd == "newproj-server"):
    srv = def_server()
    if len(sys.argv) < 3:
        print("newproj command requires name of project")
        exit(1)
    grunt_jobid = jobids(srv.active)[-1] # get last job
    projnm = sys.argv[2]
    print("using jobid: " + grunt_jobid + " to create project: " + projnm + " on server")
    srv.write_commit_cmd(grunt_jobid, cmd, projnm)
else:
    # generic command -- just pass onto server
    slist = {}
    if len(sys.argv) < 3:
        print(cmd + " requires jobs.. args")
        exit(1)
    job_args = glob_job_args(sys.argv[2:])
    for jb in job_args:
        grunt_jobid = jb
        jr = find_job(jb)
        if jr is None:
            print("skipping non-active job: %s" % (jb))
            continue
        ts = grunt_servers[jr[1]]
        ts.write_cmd(grunt_jobid, cmd, timestamp())
    for sname, ts in slist.items():
        ts.commit_cmd(cmd)
    

