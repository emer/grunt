# crun

General purpose cluster run framework -- scripts that automate running jobs on a cluster

# Install

On both client and server (cluster) you first clone the repo wherever you want:

```bash
git clone https://github.com/emer/crun.git
```

and install gitpython package -- use the `--user` option on the cluster as you typically don't have sudo write ability.

```bash
pip3 install --user gitpython
```

## Client side

* Ensure that `crun.py` is on your executable path (e.g., make a symbolic link to it in your own ~/bin dir)


## Server side

* You can run directly from git repo -- you don't need to run command from your project dirs.

* To run daemon, do:

```bash
nohup python3 crund.py
```
or however you run python3 on server.  `crund_sub.py` script must be in the same directory -- it is called for each project polling operation.  The `nohup` keeps it running in the background, and you can look at nohup.out to see what's going on:

```bash
tail -f nohup.out
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

Then you can do `screen` locally on your client, ssh into your server, and then kill the terminal -- the screen keeps that session running in the background indefinitely.  use `screen -R` to reconnect to an existing screen session.

# New projects

Each project has its own github repositories on the server, and working copies on the client (and server), that contain all the files for a given project.  These repositories are (wc = working copy):

* `~/crun/wc/cluster/username/projname/jobs`  -- contains the source code for each job and output as it runs -- this is where jobs are executed on server side (cluster).

* `~/crun/wc/cluster/username/projname/results` -- specified output files are copied over to this repository from the jobs dir, and you can `git pull` there to get the results back from server.

The `cluster` is the name of the cluster, which is prompted when you create your first project, and then stored in `~/.crun.defcluster` -- if you have a `crun.cluster` file in the current directory it will override that.

The `projname` is the directory name where you execute the `crun.py submit` job -- i.e., the directory for your simulation.

The server has the "remote" git repository for your client, and thus you must first create the project repository on the server, and then when you create it on the client it links into that remote repository.

* To initialize a new project on the server, run this command (can be done anywhere):

```bash
crun.py newproj projname
```

* Once that completes, then on the client, do:

```bash
crun.py newproj projname username@server.at.university.edu
```

where the 3rd arg there is your user name and server -- you should be able to ssh with that combination and get into the server.

# Usage

type `crun.py help` to see docs for all the commands.

# `crunsub.py`

There must be a `crunsub.py` script in your source project directory, checked into git, that in turn creates a `crun.sh` script that is executed when you submit your job.  See examples in `crun` repository.

Jobs are submitted using `slurm` and these are `sbatch` scripts.

# `crunres.py`

There must also be a `crunres.py` script, the output of which is a list of files that will be captured into the results repository, one on each line.  This allows complete flexibility in terms of what is captured.  There is an example in the repository.

# Design

* per project you have separate `clustname/username/projname/jobs` and `clustname/username/projname/results` repos, which have working copies at: `~/crun/wc/clustname/username/projname/jobs/` with `[active|deleted|archived]/jobid/` subdirs under it, and `~/crun/wc/clustname/username/projname/results/` with same sub-structure.  keeping the two repos separate allows jobs one to be monitored by server daemon for input from user, and other is strictly pushed by server and will have more frequent updating etc -- can even cleanup / rebuild results repo while keeping the full jobs history which should be much smaller, etc.

* we need `clustname` to allow client to run same project on different clusters.  the default cluster name is in `~/.crun.defcluster` and loaded and set in crun.py script at startup, and used unless you have a `crun.cluster` file in your project dir, with the name of the cluster in it.

* `jobid` starts with user initials: `rco000314` (probably don't need more than 1m jobs per project?) to facilitate ability to grab jobs from other users and keep job id unique.

* grabbing another users's files involves checking out their `otheruser_projname_jobs` git repo into your own `~/crun/otheruser/...` working copy (hence need to keep `username` in path), which you can then browse.  you can also just follow their results files and use that directly (e.g., import data directly from there), which would be the simplest way to go (similar to current behavior).  OR you can do a `grab` command to copy over the jobs and results for a specific jobid -- this goes into your own repo and works just as if you had then created the job, except it retains the link to the original user's dir (make a `source.job` file with full path to original user's job).  when you request current data update it grabs from original user's active job output, but checks into your copy of results tree.. :)

* job actually runs in server working copy of `projname/jobs/active/jobid` directory, but update command causes specified results files to be copied over to `projname/results/jobid` and checked in there -- this allows for lots of other output to accumulate in jobs side but you can clearly see what is checked in over in results. in any case, this is needed to have separate repos -- this means a duplication of files but server-side it should be ok.  archive and delete commands can remove any non-checked-in files, so this would only be for active jobs.

* have one client script, `crun` that has different command forms, e.g., `crun submit | cancel | archive` etc -- easier to maintain one script.  user only ever does things in current *source* dir, e.g., `~/ccngit/projname/sims/version` which is a normal github-backed repo of the project source files. `crun` manages the repos behind the scenes.  similar to current clusterrun.

* `crun archive` does a git mv from `~/crun/wc/cluster/username/projname/jobs/active/jobid` to `.../archive/jobid` and likewise for `crun delete` (both also do same for results repo).  if we do this client-side, and server has extra files in jobs dir where it ran, which it will, then it might barf when it does its `git pull`.  maybe there is a git `--force` option to make this work?  need to figure this out -- that would be an easy way to delete all irrelevant files.  otherwise, we'd need to have it write a `archive.job` file and then the server would do it, and you'd have to remember to do a git pull locally..

* `crun nuke` removes jobid directory entirely, but I really don't think we'll need to actually purge from git history -- it is enough to just remove the files so they aren't there cluttering up your space.

* keep design fully "stateful" as much as possible -- avoid overwriting same files, so a basic `git pull` will get everything that is needed.  daemon can iterate over all new directories / files in the pull and do everything there, without risk of overwriting, and no need to check through history of checkins.  do everything with simple text files and no need for data tables etc -- keep it super simple.  file system / dir structure has all the info.

* all job relevant output files are named `job.` and generically all `job.*` files are committed back to jobs.
    + `job.slurmid` -- generated by the submit_job in `crund_sub.py`
    + `job.start` -- should be generated by `crun.sh` script (in turn generated by `crunsub.py`) and contains `date` output when job started. 
    + `job.end` -- likewise has job end timestamp.

* crun command files are all `crcmd.*`:
    + `crcmd.cancel` -- cancel job
    + `crcmd.update` -- update files to results
    
* e.g., to cancel a job, checkin a file named `CANCEL.job` (can write the date into that file for future reference) -- then everyone can just look for that file to see if and when it was cancelled.  in general don't need ALLCAPS for filenames but for CANCEL it might make sense so you can quickly see that job was cancelled.

* main job file is `crun.sh` -- server daemon just does slurm `sbatch crun.sh` or something like that, and checks back in a file named `job.slurmid` that contains the slurm job id for that master job.
    + need to figure out how to ensure that subsequent slurm jobs are all canceled if master one is cancelled -- then client script just needs to do `scancel  < crun.jobid` to stop everything.
    + `crunsub.py` script must exist in current dir to create the job sumbission script -- that way we can write various *other* scripts that write useful crun.sh scripts -- keep this all *client* side so server is super simple and generic, and all logic is handled with these client scripts.  has been a pita to keep server side daemon script updated, so this fixes that.

* to trigger update of data files, checkin `crcmd.update` file that optionally has a list of files to update (one per line), or it runs `crunres.py` to get a list based on the project.  The daemon then just does git add, git commit / push on those files into the results repo.  if we end up committing this file multiple times before the daemon gets around to it, it might not be such a big deal -- usu going to be the same files and probably you can be patient enough to not spam yourself..

* to make new server git repos, could have an "outer loop" daemon that just does this in response to checking in a command file in a shared repo, or just have people ssh into server and run a simple command to make it (start with latter and add former if deemed worth it).  One issue is that the client-side config should all be done at same time too, so it would be more convenient to have a single client side command that does everything, automatically..

* write a simple Go library that shows all the active jobid's in a given project and operates on selected item -- import data, cancel etc.  just like current interface, except script does all the work -- GUI just calls script.  will also add script commands into gide (easy!) so you can do it all in there too..

