#!/usr/local/bin/python3

# this is the grunt git-based run tool user-script: https://github.com/emer/grunt
# it must be checked into your local source repository and handles any user commands
# including mandatory submit and results commands.
#
# script is run in the jobs path:
# ~/grunt/wc/server/username/projname/jobs/active/jobid/projname
#
# this sample version includes slurm status and cancel commands and is used for
# parallel batch submissions - zycyc test 191220

import sys
import os
import subprocess
from subprocess import Popen, PIPE
import glob
from datetime import datetime, timezone
import shutil
import re
import getpass

##############################################################
# key job parameters here, used in writing the job.sbatch

# max number of hours -- slurm will terminate if longer, so be generous
# 2d = 48, 3d = 72, 4d = 96, 5d = 120, 6d = 144, 7d = 168
hours = 48

# memory per task
mem = "4G"

# number of mpi "tasks" (procs in MPI terminology)
tasks = 1

# number of cpu cores (threads) per task
cpus_per_task = 4

# how to allocate tasks within compute nodes
# cpus_per_task * tasks_per_node <= total cores per node
tasks_per_node = 1

# qos is the queue name
qos = "oreillylab"

# qos short is short name for queue if name is cutoff
# qos_short = "oreillyl"

# in other cases, you might have to specify a partition
partition = "low"

# default array settings, settings of runniing the same job multiple times in parallel. E.g. 10 runs in parallel
array = "0-9"

# number of emergent runs per arrray job (MaxRuns)
runs = 1
##############################################################
# main vars

# grunt_jobpath is current full job path:
# ~/grunt/wc/server/username/projname/jobs/active/jobid/projname
grunt_jobpath = os.getcwd()

# grunt_user is user name (note: this is user *on the server*)
grunt_user = getpass.getuser()
# print("grunt_user: " + grunt_user)

# grunt_proj is the project name
grunt_proj = os.path.split(grunt_jobpath)[1]

##############################################################
# utility functions


def write_string(fnm, stval):
    with open(fnm, "w") as f:
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


# write_sbatch writes the job submission script: job.sbatch
def write_sbatch():
    args = " ".join(read_strings_strip("job.args"))
    f = open('job.sbatch', 'w')
    f.write("#!/bin/bash -l\n")  # -l = login session, sources your .bash_profile
    f.write("#SBATCH --mem-per-cpu=" + mem + "\n")  # zycyc, was mem
    f.write("#SBATCH --time=" + str(hours) + ":00:00\n")
    f.write("#SBATCH --ntasks=" + str(tasks) + "\n")
    f.write("#SBATCH --cpus-per-task=" + str(cpus_per_task) + "\n")
    f.write("#SBATCH --ntasks-per-node=" + str(tasks_per_node) + "\n")
    f.write("#SBATCH --array=" + array + "\n")
    # f.write("#SBATCH --qos=" + qos + "\n")
    f.write("#SBATCH --partition=" + partition + "\n")
    f.write("#SBATCH --output=job.out\n")
    f.write("#SBATCH --mail-type=FAIL\n")
    f.write("#SBATCH --mail-user=" + grunt_user + "\n")
    f.write("#SBATCH --output=job.%A_%a.out\n")
    f.write("#SBATCH --error=job.%A_%a.error\n")
    # these might be needed depending on environment in head node vs. compute nodes
    # f.write("#SBATCH --export=NONE\n")
    # f.write("unset SLURM_EXPORT_ENV\n")
    f.write("echo $SLURM_ARRAY_JOB_ID\n")
    f.write("\n\n")
    f.write("if [ \"$SLURM_ARRAY_TASK_ID\" == \"0\" ]; then\n")
    f.write("   go build -mod=mod\n")  # add anything here needed to prepare code. This part will only be executed by the first array job
    f.write("else\n")
    f.write("   wait_seconds=\"180\"\n")
    f.write("until test $((wait_seconds--)) -eq 0 -o -e \"job.start\" ; do sleep 1; done\n"
            )  # Wait for array job 0 to complete prepatory work before continuing
    f.write("fi\n")
    f.write("if [ ! -f \"job.start\" ]; then\n")
    f.write("   date -u '+%Y-%m-%d %T %Z' > job.start\n")
    f.write("fi\n")
    f.write("srun ./" + grunt_proj + " --nogui --run $SLURM_ARRAY_TASK_ID --runs $((SLURM_ARRAY_TASK_ID + " + str(runs) + ")) " +
            args + "\n")
    f.write("awk '(NR == 1) || (FNR > 1)' *epc.csv > " + grunt_proj + "_epcfull.csv\n")
    f.write("awk '(NR == 1) || (FNR > 1)' *run.csv > " + grunt_proj + "_runfull.csv\n")

    # Once job is complete, check which other array jobs are still pending or running
    f.write("squeue -j $SLURM_ARRAY_JOB_ID -o %T | grep -E \"(RUNNING|PENDING)\"\n")
    f.write("if [ \"`squeue -j $SLURM_ARRAY_JOB_ID -o %T | grep -c -E \"(RUNNING|PENDING)\"`\" == \"1\" ]; then\n")
    #This is the last array job still running
    f.write("   date -u '+%Y-%m-%d %T %Z' > job.end\n")
    f.write("else\n")
    f.write("   echo \"Not all other jobs have completed yet:\n\"")
    f.write("   squeue -j $SLURM_ARRAY_JOB_ID -o %T | grep -c -E \"(RUNNING|PENDING)\"\n")
    f.write("fi\n")
    f.flush()
    f.close()


def submit():
    if os.path.isfile('job.sbatch'):
        print("Error: job.sbatch exists -- attempt to submit job twice!")
        return
    write_sbatch()
    try:
        result = subprocess.check_output(["sbatch", "job.sbatch"])
    except subprocess.CalledProcessError:
        print("Failed to submit job.sbatch script")
        return
    prog = re.compile('.*Submitted batch job (\d+).*')
    result = prog.match(str(result))
    slurmid = result.group(1)
    write_string("job.slurmid", slurmid)
    print("submitted successfully -- slurm job id: " + slurmid)


def results():
    # important: update this to include any results you want to add to results repo
    print("\n".join(glob.glob('*_epcfull.*sv')))
    print("\n".join(glob.glob('*_runfull.*sv')))


def status():
    slid = read_string("job.slurmid")
    stat = "NOSLURMID"
    if slid == "" or slid == None:
        print("No slurm id found -- maybe didn't submit properly?")
    else:
        print("slurm id to stat: ", slid)
        result = ""
        try:
            result = subprocess.check_output(["squeue", "-j", slid, "-o", "%T"], universal_newlines=True)
        except subprocess.CalledProcessError:
            print("Failed to stat job")
        res = result.splitlines()
        if len(res) == 2:
            stat = res[1].rstrip()
        elif len(res) > 2:
            stati = {}
            for status in res:
                if status == "STATE":
                    continue
                if status in stati.keys():
                    stati[status] = stati[status] + 1
                else:
                    stati[status] = 1
            stat = ""
            for status in stati:
                stat = stat + status + str(stati[status]) + " "
        else:
            stat = "NOTFOUND"
    print("status: " + stat)
    write_string("job.status", stat)


def cancel():
    write_string("job.canceled", timestamp())
    slid = read_string("job.slurmid")
    if slid == "" or slid == None:
        print("No slurm id found -- maybe didn't submit properly?")
        return
    print("canceling slurm id: ", slid)
    try:
        result = subprocess.check_output(["scancel", slid])
    except subprocess.CalledProcessError:
        print("Failed to cancel job")
        return


# custom command to get info on cluster
def queue():
    result = ""
    try:
        result = subprocess.check_output(["sinfo"], universal_newlines=True)
    except subprocess.CalledProcessError:
        print("Failed to run sinfo")
    res = result.splitlines()
    ts = timestamp_local(datetime.now(timezone.utc))
    qout = ["queue at: " + ts + "\n", "sinfo on: " + qos + "\n"]
    for r in res:
        if qos in r:  # filter by qos
            qout.append(r)

    qout.append("\nsqueue -p " + qos + "\n")
    try:
        result = subprocess.check_output(["squeue", "-p", qos], universal_newlines=True)
    except subprocess.CalledProcessError:
        print("Failed to run squeue")
    res = result.splitlines()
    for r in res:
        if qos_short in r:  # doesn't fit full qos
            qout.append(r)

    qout.append("\nsqueue -u " + grunt_user + "\n")
    try:
        result = subprocess.check_output(["squeue", "-u", grunt_user], universal_newlines=True)
    except subprocess.CalledProcessError:
        print("Failed to run squeue")
    res = result.splitlines()
    for r in res:
        if qos_short in r:  # doesn't fit full qos
            qout.append(r)

    write_string("job.queue", "\n".join(qout))


if len(sys.argv) < 2 or sys.argv[1] == "help":
    print("\ngrunter.py is the git-based run tool extended run script\n")
    print("supports the following commands:\n")
    print("submit\t submit job to slurm")
    print("results\t list job results")
    print("status\t get current slurm status")
    print("cancel\t tell slurm to cancel job")
    print()
    exit(0)

cmd = sys.argv[1]

if cmd == "submit":
    submit()
elif cmd == "results":
    results()
elif cmd == "status":
    status()
elif cmd == "cancel":
    cancel()
elif cmd == "queue":
    queue()
else:
    print("grunter.py: error: cmd not recognized: " + cmd)
    exit(1)
exit(0)
