# grunt

`grunt` is a git-based run tool, which provides a general-purpose distributed file system with version control (i.e., git) with the infrastructure to run commands on a remote machine, by pushing files to a git repository, and having the remote machine running the daemon (`grund`) polling for updates and running the commands.

The remote machine (e.g., a compute server) hosts the git repository, which is accessed via ssh, and everything is done in user-space, so no root access is required anywhere. The core tools are written in python3.

See [grunti](https://github.com/emer/grunt/tree/master/grunti) directory for a GUI interface written in Go, which makes usage considerably simpler than the command line.

# Cheat sheet of commands

## Server

Start server daemon:
```bash
$ nohup python3 grund.py &
```

Monitor server output:
```bash
$ tail -f nohup.out
```

Reset after server killed / dies:
```bash
$ python3 grund.py reset
```

Create new project on server:
```bash
$ python3 grunt.py newproj <projname>
```

## Client

```bash
$ grunt newproj <projname> <username@server.at.university.edu>
```

See [windows](#windows) for windows setup below.

type `grunt help` to see docs for all the commands:

```
usage: pass commands with args as follows:
	 <jobid..> can include space-separated list and [job0000]11..22 range expressions
	 end number is *inclusive*!  prefix is optional

uses grunt.server for commands, but lists jobs for all servers -- use server to set

server	 name 	 sets server to given server name -- will be used for all commands

submit	 [args] -m 'message' 	 submits git controlled files in current dir to jobs working dir:
	 ~/gruntdat/wc/username/projdir/jobs/active/jobid -- also saves option args to job.args
	 which grunter.py script uses for passing args to job -- must pass message as last arg!
	 git commit triggers update of server git repo, and grund daemon then submits the new job.
	 you *must* have grunter.py script in the project dir to manage actual submission!
	 see example in https://github.com/emer/grunt repository.

jobs	 [active|done|archive|delete] 	 shows lists of all jobs, or specific subset
	 (active = running, pending) -- ONLY reflects the last status results:
	 do status to get latest job status from server, then jobs again in ~10 sec

status	 [jobid] 	 pings the server to check status and update job status files
	 on all active (running and pending) jobs if no job specified -- use jobs to see results

results	 <jobid..> 	 push current job results to results git repository
	 the specific files to get are returned by the result() function in grunter.py
	 with no jobid it gets results on all running jobs.
	 automatically does link on jobs to make easy to access from orig source.

files	 jobid [files..] 	 push given files for given job to results git repository
	 automatically does link on jobs to make easy to access from orig source.

pull	 grab any updates to jobs and results repos (done for any cmd)

out	 <jobid..> 	 displays the job.out output for given job(s)

ls	 <jobid..> 	 displays the job.list file list for given job(s)

message	 jobid 'message' 	 write a new job.message for given job

diff	 <jobid1> [jobid2] 	 displays the diffs between either given job and current
	 directory, or between two jobs directories

link	 <jobid..> 	 make symbolic links into local gresults/jobid for job results
	 this makes it easier to access the results -- this happens automatically in results cmd

cancel	 <jobid..> 	 cancel job on server

nuke	 <jobid..> 	 deletes given job directory (jobs and results) -- use carefully!
	 useful for mistakes etc -- better to use delete for no-longer-relevant but valid jobs

delete	 <jobid..> 	 moves job directory from active to delete subdir, deletes results
	 useful for removing clutter of no-longer-relevant jobs, while retaining a record just in case

archive	 <jobid..> 	 moves job directory from active to archive subdir
	 useful for removing clutter from active, and preserving important but non-current results

clean	 cleans the job git directory -- if any strange ghost jobs appear in listing, do this
	 this deletes any files that are present locally but not remotely -- should be safe for jobs
	 except if in the process of running a command, so just wait until all current activity is done

queue	 calls queue command in grunter.py, prints resulting job.queue file

newproj	 <projname> [remote-url] 	 creates new project repositories -- for use on both server
	 and client -- on client you should specify the remote-url arg which should be:
	 just your username and server name on server: username@server.my.university.edu

newproj-server	 <projname> 	 calls: newproj projname on server -- use in existing proj
	 to create a new project
```

# Overview

* There are different **projects**, which are typically named by the name of the current working directory on your laptop (*client*) where you run the `grunt` commands -- these have the code you want to run on the *server*.  These projects can be anywhere, but the code you want to run *must be added to a git repository* (e.g., hosted on `github.com` or anywhere) -- the list of files copied up to the server is provided by the git list for the current directory.  This allows misc other temp result, doc, etc files to exist in the directory.  It also means that you should put any other files that are not essential for running the simulation in other directories.
    + If you have a `grunt.projname` file in the current dir, its contents determines the project name instead.

* Each project has its own grunt git repositories ( *entirely separate from your "local" e.g., github repository* ), on the server and client, and the client configures the server's bare repositories as the ssh remote origin for the local working copies.  Repositories on server live under `~/gruntsrv/` and client on `~/gruntdat/` -- *do not put this grunt code in those locations!* -- we recommend `~/emer/grunt`.  There are two repositories per project:
    + `jobs` contains all the job running and status files.  On the server, it is also where results are typically saved (log files etc), but they are not added to git.
    + `results` contains the (subset of) job result files that you care about, which *are* added to git to make available for download (via `git pull`).  results is separate because it can be much larger than jobs -- you can regenerate a new results repo if it gets too big, while jobs should remain very small and can keep track of all jobs over time.

* The primary function is to submit and manage **jobs**, by copying all the relevant source code (and anything else in the local git as shown by `git ls-files`) to a uniquely-named `jobid` directory under the `jobs` repository, and passing the `submit` command to the local `grunter.py` script (-er = "extensible runner" -- this script is always copied whether it is under git control or not).  Typically this submit command submits a job to the server's `slurm` queue, but it can do anything you want.  As the job runs, it can produce **results** files, which can be pushed to the separate, parallel `results` repository, that can be pulled down to the client.

* The client `grunt.py` script communicates *core* commands to the `grund.py` daemon by pushing a `grcmd.<cmdname>` file.  Often the contents is just a timestamp, but could also be details needed for the command.  Other *user* commands are passed on to the user's `grunter.py` script, to support open-ended commands.  The core commands manage the full lifecycle of job and result management.

* The `grunter.py` script in your local project source dir must support at least two commands: `submit` and `results` -- see the default version in the grunt source repo.  Submit starts the job on the server (e.g., generates a slurm sbatch file and calls `sbatch` on it), and `results` outputs a list of files (one per line) that should be copied over to the `results` repository (make sure no other debugging info is output for that command!).  The sample version also supports slurm `cancel` and `status` commands.

* Any file named `job.*` is added to the `jobs` repository and pushed for every command -- use this to retrieve job state information (e.g., send slurm output to `job.out`, etc).  `job.submit`, `job.start` and `job.end` files are used conventionally to record timestamps for each such event.  `job.args` contains args for the job submission.

# Install

On both client and server (cluster) you first clone this grunt repo wherever you want (e.g., `~/emer/grunt`).

```bash
$ mkdir ~/emer
$ cd ~/emer
$ git clone https://github.com/emer/grunt.git
$ cd ~
```

and then install `gitpython` package like this (use the `--user` option on the server as you typically don't have sudo write ability):

```bash
$ pip3 install --user gitpython
```

## Client side

* Ensure that `grunt.py` is on your executable path (e.g., make a symbolic link to the git source copy in your own `~/bin` dir if that is on your `$PATH` -- you can name it just `grunt` to make it easier to type.)

The `Makefile` has a command for this:

```bash
$ make link
```

or you can do it manually like this:

```bash
$ ln -s ~/emer/grunt/grunt.py ~/bin/grunt
```

## Server side

* Before starting server for very first time, create a [project](#Projects) -- this creates various directories and sets the server name etc.

* It is easiest to run directly from the git source repo -- you don't need to run command from your project dirs.

* To run daemon, do:

```bash
$ nohup python3 grund.py &
```

or however you run python3 on server.  The `grund_sub.py` script must be in the same directory -- it is called for each project polling operation.  The `nohup` keeps it running in the background, and you can look at `nohup.out` to see what's going on:

```bash
$ tail -f nohup.out
```

There is a `grund.lock` lockfile that is created at startup, and checked before running, to prevent running multiple daemons at the same time, **which is very bad and leads to all manner of badness!!**. If you get this message, first check if any grund servers are running, e.g.:

```bash
$ ps -guaxww | grep grund
```

If this shows that no jobs are running (i.e., for restarting grund after a crash or system downtime -- there is no other way that the daemon normally terminates), run the `reset` command which will clear the lock file and the `nohup.out` file, and reset each repo to track the current repo head (i.e., any prior commands will be ignored -- you will have to resubmit). 

```bash
$ python3 grund.py reset
```

Then start the daemon as shown above (nohup..)

## SSH

The system uses ssh between client and server to sync the git repositories, so you need good direct ssh access.

*If you can just directly ssh into the server from your client without entering a password, you're good -- no further steps required!*

### Configuring SSH to not require further authentication every time

If your system is configured to require a two-factor-authentication or something like that at each login, the following are handy ssh config options that will keep an ssh channel authenticated if you have an existing ssh session open.  The strategy here is to keep one such ssh channel permanently open, and then all the other ones can piggyback on top of that.

```bash
~/.ssh/config:
Host blogin01.rc* login.rc*
ControlMaster auto
ControlPath ~/.ssh/sockets/%r@%h:%p
```

where `blogin01.rc*` is the start of server host names that you want to do this for.

If you don't have a `sockets` directory in .ssh create one using `mkdir`.

Then you can do `screen` locally on your client, ssh into your server, and then kill that terminal window -- the screen keeps that session running in the background indefinitely.  use `screen -R` to reconnect to an existing screen session when you need to reconnect the master ssh connection.

# Projects

Each project has its own git repositories on the server, and working copies on the client (and server), that contain all the files for a given project.  These repositories are, on the client (wc = working copy):

* `~/gruntdat/wc/server/username/projname/jobs` -- contains the source code for each job, job control commands (`grcmd.*`), job state output files (`job.*`) and job output as it runs -- this is where jobs are executed on server side.

* `~/gruntdat/wc/server/username/projname/results` -- specified output files are copied over to this repository from the jobs dir, and you can `git pull` there to get the results back from server.

The `server` is the name of the server, which must be the first part of the hostname without the domain (e.g., for `hpc.myunit.university.edu` it is `hpc`), is prompted when you create your first project, and then stored in `~/.grunt.defserver` -- if you have a `grunt.server` file in the current directory, the contents of that will override that.  On the server, the repositories are in `~/gruntsrv/` -- the use of different names allows the client and server to be the same system (you can just run it on your laptop to use the git job tracking).

The `projname` is the directory name where you execute the `grunt.py submit` job -- i.e., the directory for your simulation -- if you have a `grunt.projname` file in the current directory, the contents of that will override that.

## New Project

The server hosts the "remote" git repository for your client, and thus you must first create the project repository on the server, and then when you create it on the client it links into that remote repository.

* To initialize a new project on the **server**, run this command (where `grunt.py` code is, typically `~/emer/grunt`):

```bash
$ python3 grunt.py newproj <projname>
```

* Once that completes, then on the **client**, do:

```bash
$ grunt newproj <projname> <username@server.at.university.edu>
```

where the 3rd arg there is your user name and server -- you must be able to ssh with that combination and get into the server.

If this step fails (e.g., due to a typo etc), you will have to go to `~/gruntdat/wc/server/username` and remove the `<projname>` directory there before retrying.

After you've created your first project, you can trigger remote project creation in an *existing* project on the client using:

```bash
$ grunt newproj-server <projname>
```

## Copy and Configure your `grunter.py` script

For each project, you must have a working `grunter.py` python script that actually submits the job on the cluster.  For your first project, you should copy this from the grunt directory:

```bash
$ cp ~/emer/grunt/grunter.py .    # use actual path to emer repo
$ edit grunter.py   # use your actual editor here!
```

Take some time to read over the script -- the top has the key variables that you'll need to configure specifically for each project in terms of how many processors, how much memory, time etc.  These are used in the `write_sbatch()` function which *must be customized for your server* -- once you do this for your particular server, then you can usually just copy from another project.

You will have to read your server's documentation and edit the python code to generate an appropriate `sbatch` submission script depending on details of your server.  The example `grunter.py` file contains some tips and options that work across the two servers we use.

You can have the script `cd` into a subdirectory and run a project from there, to support multiple different executables or variations in the same repository, but *always run grunt from the root of the project* because it gets the project name from the directory name (and even if you put `grunt.projname` in the subdirectory to fix that issue, the jobs.* files etc will not be coordinated if you run grunt from different directories -- it might work but could get confusing at least).

Also, if there are any "external" resources that your job needs (e.g., large shared databases of image files), you should just write a command in your sbatch script to make a symbolic link to the relevant directory ( *on the server* ), and then have your project refer "locally" to that symlinked directory -- you can also manually create the same symlink on your client, so the code will run the same in both places, and others can use it too, without baking in a specific path in the code.

# Details

## Standard job.* files

All job relevant output files are named `job.` and generically all `job.*` files are committed back to jobs.  Here are some standard job file names, for standard slurm-based `grunter.py` workflow.

* `grunt.py` `submit` command:
    + `job.message` -- the message passed in mandatory `-m 'message'`
    + `job.submit` -- timestamp when job was submitted
    + `job.args` -- extra args (one per line) excluding final `-m 'message'` args -- the sample `grunter.py` script uses the contents of this file to pass args to the actual job.

* `grunter.py` `submit` command:
    + `job.sbatch` -- slurm sbatch file for running job
    + `job.slurmid` -- slurm job id number
    + `job.start` -- timestamp when job actually starts (by `job.sbatch`)
    + `job.end` -- timestamp when job completes (also `job.sbatch`)

* `job.list` -- csv list of files in dir (excluding all `job.*`,  `grcmd.*` files) updated by any command touching a given job (e.g., `status` or `update`) -- you can look at this with `grunt ls` to see what other files you might want to grab with `results`

* `job.canceled` -- timestamp when job canceled by `grunter.py` `cancel` command

# Best Practices

Here are some tips for effective use of this tool:

* As in `git`, **it is essential to always use good -m messages** for each job `submit` -- a critical benefit of this tool is providing a record of each simulation run, and your goals and mental state at the point of submission are the best clues as to what this job was about, when you come back to it in a few days or weeks and have forgotten everything..

* Because absolutely everything is backed by the `git` revision history, it is safe to `delete` (and even `nuke`) jobs, so you should use `delete` liberally to clean up `active` jobs, to keep your current state reflecting only the best results.  Anything that is used in a publication or is otherwise old but important, should be `archived`.

## Recommended github project repository structure

Because the grunt system is always copying all the files the current directory into the `jobs` directory for each `submit` command, including everything in subdirectories, it is a good idea to keep your other project-related files in other directories (e.g., good results you want to keep and analyze further, result plots, etc).  Just keep the core source code needed to run the job in the project directory.  Here's the template organization we use:

```bash
myproj
  papers
     paper1
        paper1.tex
     ...
  figs
     fig_myfinalpubfig1.svg
     ...
  results
     myresult-data.log
     ...
  sims
      myproj-v1     # more descriptive names might be even better..
         myproj.go  # only code goes in here, plus grunter.py and anything else needed to run
         params.go
         ...
      myproj-v2
```

# Troubleshooting

* Use `grunt clean` if you end up with "ghost" jobs in Active list after deleting / nuking / archiving.  This does a `git clean` on the jobs git repo to remove any local files not in repo -- usually this fixes any issues. More rarely, you may need to do something manually in the local repo or even in the server one if something wasn't deleted properly.

* If you get mysterious git error messages, try running `git ls-files` and `git-status` etc to get more information and fix the issues -- the scripts just call git commands so you can use the command-line tool to better diagnose what is going on.  This may require you to ssh to the cluster and do `git status` etc commands on the `~/gruntdat/wc` directories.  In general you shouldn't touch the `bb` back-end barebones repositories -- use the wc working copy versions to update those.

* If grunt pull isn't working check the list of results files in grunter.py that should be pulled.

# Windows

As usual, Microsoft Windows is different -- here's some tips for configuring the client to work on windows.

* First, strongly recommend using the `PowerShell`-- search for that in the  `Microsoft Store` app -- type `store` in the windows taskbar search prompt -- this provides a much better command-line interface than the standard Command Prompt.

* Install `git` from here: https://git-scm.com/download/win

* Install Python from the main Python distribution: https://www.python.org/downloads/windows/ -- *do not under any circumstances install from the Microsoft Store app!* while that is very convenient, it creates symbolic links to access the python executables, which is incompatible with go exec.Command, preventing use of `gopy`.

    The standard python install does not create a `python3.exe` which grunt looks for -- follow instructions here:
https://stackoverflow.com/questions/39910730/python3-is-not-recognized-as-an-internal-or-external-command-operable-program/41492852
(just make a copy of python.exe to python3.exe in the relevant installed location).

* Then install gitpython package in python, using this command in powershell:

```bash
$ pip3 install gitpython
```

* Build `grunti` (e.g., `go build` in `grunti` directory) -- assuming that works, then do `go install` to install it into the go `bin` path -- in powershell, you can just type `which grunti` to see where that is -- if nothing comes up then probably that location is not on your path, in which case you need to add it.  Here's information about Go paths: https://pkg.go.dev/cmd/go#hdr-GOPATH_environment_variable -- we'll refer to the `GOPATH/bin` path as `GOBIN` from here on out.

    + Open `Control Panel`, search for `env`, click on the option to edit system environment variables, edit the `Path` variable, and ensure that the appropriate `GOBIN` path is on it.

* Create a `grunt.bat` file in the `GOBIN` path, replacing the paths here with those where your relevant programs are located -- e.g., use `which python3` to find where that is, and the location where you have the `emer\grunt` code:

```bat
"C:\Program Files\Python37\python" C:\GoModules\src\github.com\emer\grunt\grunt.py %*
```

* Test your `grunt` command by going to your project directory where you want to run simulations, and type `grunt` -- it should give you the standard usage info.  If not, you may encounter for example an error in the paths, or perhaps you haven't installed the `git` module.


