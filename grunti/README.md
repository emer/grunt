# grunti

`grunti` is a GUI interface to the grunt client, providing table views of jobs in the different status (pending, running, done), and actions performed on selected jobs.

`grunti` only shows the state of the *local* git repositories -- grunt depends on a `git pull` via the `Update` action to grab the latest `git` state that might have been updated from the server.

Furthermore, current job status and results require explicit `Status` and `Results` "pings" to tell the server to commit the latest info to the `git` repository, after which the `Update` will make it visible locally in grunti.

In short, typically start by pressing `Status` to make sure things are updated!

Where appropriate, actions will auto-update for 15 seconds -- the `Update` button will be ghosted.  You may need to manually do `Update` after this period if the command is still being processed on the server and the commit / push has not happened yet there.

During a `Submit` action, a `Status` will be sent to check on the status of the new job after the update window -- again you may need to check for `Status` after that point too.

Mouse over toolbar buttons to see more details about each action, which corresponds directly to the `grunt` action of the same name.

# Params

See `Params` tab for various default params that can be modified to save retyping commonly-used settings, or to tweak the auto update times etc.  `SubmitArgs` and `OpenResultsCont` are auto-saved each time.

# Plotting Results

CSV / tabular results can be loaded using `Open...` button next to Results, and plotted using the `Plot` button. 

The `Results` tab shows the list of currently open results.

* Press the `Reload` button to reload after `Results` (`Open...` loads them, but if you do `Results` later then you need to `Reload` to update existing results tables -- due to the uncertainty in when the git pull actually gets the new results, this is not automated.)

* Select jobs to determine what is plotted with the `Plot` button.  If multiple results are selected for Plot, it will set the `LegendCol` to `JobId`, to plot each job separately.




