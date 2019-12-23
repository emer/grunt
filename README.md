# grunt

`grunt` is a git-based run tool, which provides a general-purpose distributed file system with version control (i.e., git) with the infrastructure to run commands on a remote machine, by pushing files to a git repository, and having the remote machine running the daemon (`grund`) polling for updates and running the commands.

The remote machine (e.g., a compute server) hosts the git repository, which is accessed via ssh, and everything is done in user-space, so no root access is required anywhere. Everything is written in python3.

The central principles are:

* There are different **projects**, which are typically named by the name of the current working directory on your laptop (*client*) where you run the `grunt` commands -- these have the code you want to run on the *server*.  These projects can be anywhere, but the code you want to run *must be added to a git repository* (e.g., hosted on `github.com` or anywhere) -- the list of files copied up to the server is provided by the git list for the current directory.  If you have a `grunt.projnm` file in the current dir, its contents determines the project name instead.

* Each project has its own grunt git repositories, on the server and client, and the client configures the server's bare repositories as the ssh remote origin for the local working copies.  All repositories live under `~/grunt/`.

* The primary function is to submit and manage **jobs**, by copying all the relevant source code (and anything else in the local git as shown by `git ls-files`) to a uniquely-named `jobid` directory under the `jobs` repository, and passing the `submit` command to the local `grunter.py` script ("extensible runner" -- this script is always copied whether it is under git control or not).  Typically this submit command submits a job to the server's `slurm` queue, but it can do anything you want.  As the job runs, it can produce **results** files, which can be pushed to a separate, parallel `results` repository, that can be pulled down to the client.

* The client `grunt.py` script communicates *core* commands to the `grund.py` daemon by pushing a `grcmd.<cmdname>` file.  Often the contents is just a timestamp, but could also be details needed for the command.  Other *user* commands are passed on to the user's `grunter.py` script, to support open-ended commands.  The core commands manage the full lifecycle of job and result management.

* The `grunter.py` script ("extensible runner") in your local project source dir must support at least two commands: `submit` and `results` -- see the default version in the grunt source repo.  Submit starts the job on the server (e.g., generates a slurm sbatch file and calls `sbatch` on it), and `results` outputs a list of files (one per line) that should be copied over to the `results` repository (make sure no other debugging info is output for that command!).  The sample version also supports slurm `cancel` and `status` commands.

* Any file named `job.*` is added to the `jobs` repository and pushed for every command -- use this to retrieve job state information (e.g., send slurm output to `job.out`, etc).  `job.submit`, `job.start` and `job.end` files are used conventionally to record timestamp for each such event.  `job.args` contains args for the job submission.

# Install

On both client and server (cluster) you first clone the repo wherever you want:

```bash
$ git clone https://github.com/emer/grunt.git
```

and install `gitpython` package -- use the `--user` option on the server as you typically don't have sudo write ability.

```bash
$ pip3 install --user gitpython
```

## Client side

* Ensure that `grunt.py` is on your executable path (e.g., make a symbolic link to the git source copy in your own `~/bin` dir if that is on your `$PATH` -- you can name it just `grunt` to make it easier to type.)

```bash
$ ln -s ~/emer/grunt/grunt.py ~/bin/grunt
```

## Server side

* It is easiest to run directly from the git source repo -- you don't need to run command from your project dirs.

* To run daemon, do:

```bash
$ nohup python3 grund.py &
```

or however you run python3 on server.  The `grund_sub.py` script must be in the same directory -- it is called for each project polling operation.  The `nohup` keeps it running in the background, and you can look at `nohup.out` to see what's going on:

```bash
$ tail -f nohup.out
```

There is a `grund.lock` lockfile that is created at startup, and checked before running, to prevent running multiple daemons at the same time, **which is very bad and leads to all manner of badness!!**.  If restarting grund after a crash or system downtime (there is no other way that the daemon normally terminates), start with the restart arg which will clear the lock file and the nohup.out file. Then start the daemon as usual:

```bash
$ nohup python3 grund.py restart &
```

## SSH

The system uses ssh between client and server to sync the git repositories, so you need good direct ssh access.

That there are handy ssh config options that will keep an ssh channel authenticated if you have an existing ssh session open:

```bash
~/.ssh/config:
Host blogin01.rc* login.rc*
ControlMaster auto
ControlPath ~/.ssh/sockets/%r@%h:%p
```

where `blogin01.rc*` is the start of server host names that you want to do this for.

If you don't have a `sockets` directory in .ssh create one

Then you can do `screen` locally on your client, ssh into your server, and then kill that terminal window -- the screen keeps that session running in the background indefinitely.  use `screen -R` to reconnect to an existing screen session when you need to reconnect the master ssh connection.

# Projects

Each project has its own git repositories on the server, and working copies on the client (and server), that contain all the files for a given project.  These repositories are (wc = working copy):

* `~/grunt/wc/server/username/projname/jobs`  -- contains the source code for each job and output as it runs -- this is where jobs are executed on server side.

* `~/grunt/wc/server/username/projname/results` -- specified output files are copied over to this repository from the jobs dir, and you can `git pull` there to get the results back from server.

The `server` is the name of the server, which is prompted when you create your first project, and then stored in `~/.grunt.defserver` -- if you have a `grunt.server` file in the current directory, the contents of that will override that.

The `projname` is the directory name where you execute the `grunt.py submit` job -- i.e., the directory for your simulation -- if you have a `grunt.projname` file in the current directory, the contents of that will override that.

The server has the "remote" git repository for your client, and thus you must first create the project repository on the server, and then when you create it on the client it links into that remote repository.

* To initialize a new project on the server, run this command (can be done anywhere):

```bash
$ python3 grunt.py newproj projname
```

* Once that completes, then on the client, do:

```bash
$ grunt newproj projname username@server.at.university.edu
```

where the 3rd arg there is your user name and server -- you should be able to ssh with that combination and get into the server.

After you've created your first project, you can trigger remote project creation in an existing project using:

```bash
$ grunt newproj-server projname
```

# Usage

type `grunt help` to see docs for all the commands:

```
usage: pass commands with args as follows:
	 <jobid..> can include space-separated list and job000011..22 range expressions
	 end number is *inclusive*!

submit	 [args] -m 'message' submits git controlled files in current dir to jobs working dir:
	 ~/grunt/wc/username/projdir/jobs/active/jobid -- also saves option args to job.args
	 which grunter.py script uses for passing args to job -- must pass message as last arg!
	 git commit triggers update of server git repo, and grund daemon then submits the new job.
	 you *must* have grunter.py script in the project dir to manage actual submission!
	 see example in https://github.com/emer/grunt repository.

jobs	 [active|done] shows lists of all jobs, or specific subset (active = running, pending)

status	 [jobid] pings the server to check status and update job status files
	 on all running and pending jobs if no job specified

update	 [jobid] [files..] push current job results to results git repository
	 with no files listed uses grunter.py results command on server for list.
	 with no jobid it does generic update on all running jobs.
	 automatically does link on jobs to make easy to access from orig source.

pull	 grab any updates to jobs and results repos (done for any cmd)

out	 <jobid..> displays the job.out output for given job(s)

ls	 <jobid..> displays the job.list file list for given job(s)

diff	 <jobid1> [jobid2] displays the diffs between either given job and current
	 directory, or between two jobs directories

link	 <jobid..> make symbolic links into local gresults/jobid for job results
	 this makes it easier to access the results -- this happens automatically at update

nuke	 <jobid..> deletes given job directory (jobs and results) -- use carefully!
	 useful for mistakes etc -- better to use delete for no-longer-relevant but valid jobs

delete	 <jobid..> moves job directory from active to delete subdir, deletes results
	 useful for removing clutter of no-longer-relevant jobs, while retaining a record just in case

archive	 <jobid..> moves job directory from active to archive subdir
	 useful for removing clutter from active, and preserving important but non-current results

newproj	 <projname> [remote-url] creates new project repositories -- for use on both server
	 and client -- on client you should specify the remote-url arg which should be:
	 just your username and server name on server: username@server.my.university.edu

newproj-server	 <projname> calls: newproj projname on server -- use in existing proj
	 to create a new project
```

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

* `job.list` -- csv list of files in dir (excluding all `job.*`,  `grcmd.*` files) updated by any command touching a given job (e.g., `status` or `update`) -- you can look at this with `grunt ls` to see what other files you might want to grab with `update`

* `job.canceled` -- timestamp when job canceled by `grunter.py` `cancel` command

# Best Practices

Here are some tips for effective use of this tool:

* As in `git`, **it is essential to always use good -m messages** for each job `submit` -- a critical benefit of this tool is providing a record of each simulation run, and your goals and mental state at the point of submission are the best clues as to what this job was about, when you come back to it in a few days or weeks and have forgotten everything..

* Because absolutely everything is backed by the `git` revision history, it is safe to `delete` (and even `nuke`) jobs, so you should use `delete` liberally to clean up `active` jobs, to keep your current state reflecting only the best results.  Anything that is used in a publication or is otherwise old but important, should be `archive`d.

# TODO

* how to gain access to other user's results?

* save git sha's for various key commands like submit, update, delete -- issue is circularity -- these would only be avail on subsequent commit after that one.

* undelete -- basically a git command that undoes the delete commit..

* if grund_sub is still processing one command and another is checked in, it can fail to notice apparently.  but critically it doesn't lose that job -- just need to push another one to get it to register.  

* daemon heartbeat timestamp to ensure that it is running -- like what we had in cluster run.  issue is that we don't have any fully general repo so we'd have to stick it in each jobs repo -- this suggests that maybe we do want to have a master 'grunt' project repo that is where all the general stuff goes, and is used for newproj-server.

* it might get kinda slow checking a bunch of different project repos on grund, esp with a slow filesystem.

