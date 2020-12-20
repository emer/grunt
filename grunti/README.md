# grunti

`grunti` is a GUI interface to the grunt client, providing table views of jobs in the different status (pending, running, done), and actions performed on selected jobs.

# Install

Do the standard `go get` to automatically build and install it in your `~/go/bin` (or wherever `GOPATH` points):

```sh
$ go get github.com/emer/grunt/grunti
```

**You must run grunti, like grunt, from your project directory** that has the simulation or other task that you're running.  Thus, `~/go/bin` must be on your `PATH` so you can just run `grunti&` to run it.

# Usage

`grunti` only shows the state of the *local* git repositories -- grunt depends on a `git pull` via the `Pull` action to grab the latest `git` state that might have been updated from the server.

Furthermore, current job status and results require explicit `Status` and `Results` "pings" to tell the server to commit the latest info to the `git` repository, after which the `Pull` will make it visible locally in grunti.

In short, typically start by pressing `Status` to make sure things are updated!  This will only ping the current `Server` -- set that as needed.

Where appropriate, actions will auto-pull for 15 seconds -- the `Pull` button will be ghosted.  You may need to manually do `Pull` after this period if the command is still being processed on the server and the commit / push has not happened yet there.

During a `Submit` action, a `Status` will be sent to check on the status of the new job after the pull window -- again you may need to check for `Status` after that point too.

Mouse over toolbar buttons to see more details about each action, which corresponds directly to the `grunt` action of the same name.

# Params

See `Params` tab for various default params that can be modified to save retyping commonly-used settings, including the full set of Plot parameters, or to tweak the auto pull times etc.  `SubmitArgs` and `OpenResultsCont` are auto-saved each time.

Use `Copy From Plot` toolbar action to grab the current Plot params if you've changed them, so they become the new default.  Otherwise, it always overwrites any plot params based on the defaults *only if* the `XAxisCol` has been set in the Plot params (otherwise it assumes they haven't been set).

In other words, after you get your plot looking good, go to the `Params` tab, and click `Copy From Plot` so those settings will be avail next time.

# Plotting Results

CSV / tabular results can be loaded using `Open...` button next to Results, and plotted using the `Plot` button. 

The `Results` tab shows the list of currently open results.

* Press the `Reload` button to reload after `Results` (`Open...` loads them, but if you do `Results` later then you need to `Reload` to update existing results tables -- due to the uncertainty in when the git pull actually gets the new results, this is not automated.)

* Select jobs to determine what is plotted with the `Plot` button.  If multiple results are selected for Plot, it will set the `LegendCol` to `JobId`, to plot each job separately.


