# grunti

`grunti` is a GUI interface to the grunt client, providing table views of jobs in the different status (pending, running, done), and actions performed on selected jobs.

Where appropriate, actions will auto-update for 30 seconds -- the `Update` button will be ghosted.  You may need to manually do `Update` after this period if the command is still being processed on the server.

During a `Submit` action, a `Status` will be sent to check on the status of the new job after the 30 second update window -- again you may need to check for `Status` after that point too.

Mouse over toolbar buttons to see more details about each action, which corresponds directly to the `grunt` action of the same name.

It is important to remember that local info depends on an `Update` to reflect current `git` state, and furthermore that job status and results require explicit `Status` and `Results` "pings" to the server to get the latest info committed into the `git` repository, after which the `Update` will make it visible in grunti.

In short, typically start by pressing `Status` to make sure things are updated!

# Plotting Results

CSV / tabular results can be loaded using `Open...` button next to Results, and plotted using the Plot button.  If multiple results are selected for Plot, it will set the JobId to the LegendCol, to plot each job separately.


