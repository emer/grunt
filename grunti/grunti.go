// Copyright (c) 2020, The Emergent Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

// grunti provides a graphical interface for grunt client:
// git-based-run-tool.
package main

import (
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/emer/etable/eplot"
	"github.com/emer/etable/etable"
	"github.com/emer/etable/etview"
	_ "github.com/emer/etable/etview" // include to get gui views
	"github.com/goki/gi/gi"
	"github.com/goki/gi/gimain"
	"github.com/goki/gi/giv"
	"github.com/goki/ki/dirs"
	"github.com/goki/ki/ki"
	"github.com/goki/ki/kit"
)

func main() {
	gimain.Main(func() { // this starts gui -- requires valid OpenGL display connection (e.g., X11)
		guirun()
	})
}

func guirun() {
	win := TheGrunt.Config()
	win.StartEventLoop()
}

// Grunt interfaces with grunt commands
type Grunt struct {
	StatMsg  string            `desc:"last status message"`
	Params   Params            `desc:"params per project, saved as grunti.pars"`
	ResList  Results           `desc:"list of loaded results"`
	Active   *etable.Table     `desc:"jobs table"`
	Done     *etable.Table     `desc:"jobs table"`
	ActView  *etview.TableView `desc:"table view"`
	DoneView *etview.TableView `desc:"table view"`
	OutView  *giv.TextView     `desc:"text view"`
	OutBuf   *giv.TextBuf      `desc:"text buf"`
	ResView  *giv.TableView    `desc:"results table"`
	Plot     *eplot.Plot2D     `desc:"plot"`
	AggRes   *etable.Table     `desc:"aggregated results from multiple"`

	StatLabel *gi.Label    `view:"-" desc:"status label"`
	Win       *gi.Window   `view:"-" desc:"main GUI window"`
	ToolBar   *gi.ToolBar  `view:"-" desc:"the master toolbar"`
	TabView   *gi.TabView  `view:"-" desc:"the tab view"`
	CmdMu     sync.Mutex   `view:"-" desc:"command mutex"`
	UpdtMu    sync.Mutex   `view:"-" desc:"update mutex"`
	InUpdt    bool         `inactive:"+" desc:"true if currently in update loop"`
	Timeout   time.Time    `view:"-" desc:"timout for auto updater"`
	NextCmd   string       `view:"-" desc:"next command to run after current update has timed out"`
	UpdtTick  *time.Ticker `view:"-" desc:"update ticker"`
}

var KiT_Grunt = kit.Types.AddType(&Grunt{}, GruntProps)

// TheGrunt is the overall state for this grunt
var TheGrunt Grunt

// New makes new tables
func (gr *Grunt) New() {
	gr.Params.Defaults()
	gr.Params.Open()
	gr.Active = &etable.Table{}
	gr.Done = &etable.Table{}
	gr.ResList = make(Results, 0)
	gr.ResList = append(gr.ResList, &Result{}) // dummy
}

// OpenJobs opens existing job files
func (gr *Grunt) OpenJobs() {
	gr.Active.OpenCSV("jobs.active", etable.Comma)
	gr.Done.OpenCSV("jobs.done", etable.Comma)
}

// UpdateViews updates the table views
func (gr *Grunt) UpdateViews() {
	gr.ActView.UpdateTable()
	gr.DoneView.UpdateTable()
}

// Update is the main update -- opens jobs and updates views, under lock
func (gr *Grunt) Update() {
	gr.UpdtMu.Lock()
	defer gr.UpdtMu.Unlock()

	gr.UpdateLocked()
}

// UpdateLocked does the update under existing lock
func (gr *Grunt) UpdateLocked() {
	if !gr.Win.IsVisible() {
		return
	}
	gr.RunGruntCmd("jobs", nil)
	out, _ := gr.RunGruntCmd("pull", nil)
	gr.OutBuf.SetText(out)

	gr.OpenJobs()
	gr.UpdateViews()
}

//////////////////////////////////////////////////////////////////////////////
//  Auto-updater

// StartAutoUpdt starts the auto-update ticker to run until timeout
func (gr *Grunt) StartAutoUpdt() {
	gr.UpdtMu.Lock()
	defer gr.UpdtMu.Unlock()

	gr.Timeout = time.Now().Add(time.Duration(gr.Params.UpdtTotalSec) * time.Second)

	if gr.UpdtTick == nil {
		gr.UpdtTick = time.NewTicker(time.Duration(gr.Params.UpdtIntervalSec) * time.Second)
		go gr.TickerUpdate()
	}
}

// InAutoUpdt returns true if currently doing AutoUpdt
func (gr *Grunt) InAutoUpdt() bool {
	return time.Now().Before(gr.Timeout)
}

// TickerUpdate is the update function from the ticker
func (gr *Grunt) TickerUpdate() {
	for {
		<-gr.UpdtTick.C
		gr.UpdtMu.Lock()
		if gr.InAutoUpdt() {
			gr.StatusMsg("updating...")
			gr.UpdateLocked()
			gr.StatusMsg("updated: " + time.Now().Format("15:04:05"))
		} else {
			if gr.NextCmd != "" {
				gr.UpdtMu.Unlock()
				gr.RunNextCmd()
				continue
			}
			gr.ToolBar.UpdateActions()
		}
		gr.UpdtMu.Unlock()
	}
}

// RunNextCmd runs the NextCmd
func (gr *Grunt) RunNextCmd() {
	if gr.NextCmd == "" {
		return
	}
	cmd := gr.NextCmd
	gr.NextCmd = ""
	switch cmd {
	case "status":
		gr.RunGruntUpdt("status", nil) // all jobs
	}
}

//////////////////////////////////////////////////////////////////////////////
//  Commands

// RunGruntCmd runs given grunt command with given args, returning resulting
// output and error.
// This is the basic impl -- see RunGrunt and RunGruntUpdt.
func (gr *Grunt) RunGruntCmd(grcmd string, args []string) ([]byte, error) {
	gr.CmdMu.Lock()
	defer gr.CmdMu.Unlock()

	margs := make([]string, 0, len(args)+1)
	margs = append(margs, grcmd)
	margs = append(margs, args...)
	cmd := exec.Command("grunt", margs...)
	out, err := cmd.CombinedOutput()
	return out, err
}

// RunGrunt runs given grunt command with given args, returning resulting
// output and error, showing command in status and sending output to
// Output tab.  This is the version for user-initiated commands.
func (gr *Grunt) RunGrunt(grcmd string, args []string) ([]byte, error) {
	cmstr := grcmd + " " + strings.Join(args, " ")
	gr.StatusMsg(cmstr)
	out, err := gr.RunGruntCmd(grcmd, args)
	if err != nil {
		msg := append([]byte(err.Error()), []byte("\n")...)
		msg = append(msg, out...)
		gr.OutBuf.SetText(msg)
	} else {
		gr.OutBuf.SetText(out)
	}
	return out, err
}

// RunGruntUpdt runs given grunt command with given args, returning resulting
// output and error, showing command in status and sending output to
// Output tab.  Then it activates an Update loop until timeout.
// This is the version for user-initiated commands.
func (gr *Grunt) RunGruntUpdt(grcmd string, args []string) ([]byte, error) {
	out, err := gr.RunGrunt(grcmd, args)
	if err == nil {
		gr.StartAutoUpdt()
	}
	return out, err
}

// Status pings server for current job status
func (gr *Grunt) Status() {
	av := gr.ActiveView()
	if av == gr.ActView || av == nil {
		gr.RunGruntUpdt("status", nil)
	} else {
		gr.RunGruntUpdt("status", gr.SelectedJobs(false))
	}
}

// Results pings server for current job results
func (gr *Grunt) Results() {
	av := gr.ActiveView()
	if av == gr.ActView || av == nil {
		gr.RunGruntUpdt("results", nil)
	} else {
		gr.RunGruntUpdt("results", gr.SelectedJobs(false))
	}
	gr.TabView.SelectTabByName("Output") // see grunt output
}

// OpenResults opens results for selected jobs, for file name that contains given string,
// and has given extension (csv = comma separated, tsv = tab separated)
func (gr *Grunt) OpenResults(fileContains, ext string) {
	gr.Params.SaveOpenResultsCont(fileContains)
	jobs := gr.SelectedJobs(true) // need
	if len(jobs) == 0 {
		return
	}
	for _, jb := range jobs {
		fnm := filepath.Join("gresults", jb)
		fls := dirs.ExtFileNames(fnm, []string{ext})
		for _, fl := range fls {
			if strings.Contains(fl, fileContains) {
				if len(gr.ResList) == 1 && gr.ResList[0].JobId == "" { // remove blank
					gr.ResList = gr.ResList[:0]
				}
				gr.ResList.Recycle(jb, filepath.Join(fnm, fl))
			}
		}
	}
	gr.TabView.SelectTabByName("Results")
	gr.ResView.Update()
}

// PlotResults plots selected (or all if none selected) opened Results
// if multiple selected, they are merged into a single table and plotted by JobId
func (gr *Grunt) PlotResults() {
	sel := gr.ResView.SelectedIdxsList(false)
	// fmt.Printf("sel: %v\n", sel)
	if len(sel) == 0 {
		if len(gr.ResList) == 0 {
			gr.StatusMsg("Plot: no results to plot")
			return
		}
		for i := range gr.ResList {
			sel = append(sel, i)
		}
	}
	if len(sel) == 1 {
		dt := gr.ResList[sel[0]].Table
		if dt == nil {
			gr.StatusMsg("Plot: nil table")
			return
		}
		gr.Plot.Params.LegendCol = ""
		gr.Plot.SetTable(dt)
	} else {
		gr.AggRes = nil // reset
		for i := range sel {
			r := gr.ResList[sel[i]]
			// fmt.Printf("job: %d  %s\n", i, r.JobId)
			dt := r.TableWithJobId()
			if dt == nil {
				continue
			}
			if gr.AggRes == nil {
				gr.AggRes = dt
			} else {
				gr.AggRes.AppendRows(dt)
			}
		}
		gr.Plot.Params.LegendCol = "JobId"
		gr.Plot.SetTable(gr.AggRes)
	}
	if gr.Plot.Params.XAxisCol == "" {
		gr.Plot.Params.XAxisCol = gr.Params.XAxis
	}
	for _, cp := range gr.Plot.Cols {
		if cp.Col != gr.Plot.Params.XAxisCol {
			cp.Range = gr.Params.DefRange
		}
	}
	gr.TabView.SelectTabByName("Plot")
	gr.Plot.Update()
}

// Submit submits a new job, with optional space-separated args and a message
// describing the job
func (gr *Grunt) Submit(args, message string) {
	gr.Params.SaveSubmitArgs(args)
	argv := strings.Fields(args)
	argv = append(argv, "-m")
	argv = append(argv, message)
	gr.RunGruntUpdt("submit", argv)
	gr.ToolBar.UpdateActions()
	gr.NextCmd = "status"
	gr.TabView.SelectTabByName("Active")
}

// Output shows output of selected job in Output tab
func (gr *Grunt) Output() {
	jobs := gr.SelectedJobs(true) // need
	if len(jobs) == 0 {
		return
	}
	gr.RunGrunt("out", jobs)
}

// List shows list of files associated with job(s) in Output tab
func (gr *Grunt) List() {
	jobs := gr.SelectedJobs(true) // need
	if len(jobs) == 0 {
		return
	}
	gr.RunGrunt("ls", jobs)
}

// Files gets specific files as listed (space separated) into results, for files that are
// not automatically copied by grunter.py script
func (gr *Grunt) Files(files string) {
	jobs := gr.SelectedJobs(true) // need
	if len(jobs) == 0 {
		return
	}
	if len(jobs) != 1 {
		gr.StatusMsg(`<span style="color:red">Error: Must have exactly 1 job selected, rest of args are file names!</span>`)
		return
	}
	jobs = append(jobs, strings.Fields(files)...)
	gr.RunGruntUpdt("files", jobs)
	gr.TabView.SelectTabByName("Output") // see grunt output
}

// Diff displays the diffs between either given job and current directory, or between two jobs dirs
// in Output tab
func (gr *Grunt) Diff() {
	jobs := gr.SelectedJobs(true) // need
	if len(jobs) == 0 {
		return
	}
	gr.RunGrunt("diff", jobs)
}

// Link make symbolic links into local gresults/jobid for job results
// this makes it easier to access the results -- this happens automatically in results cmd
func (gr *Grunt) Link() {
	jobs := gr.SelectedJobs(true) // need
	if len(jobs) == 0 {
		return
	}
	gr.RunGrunt("link", jobs)
}

// Cancel cancels given job(s) on server
func (gr *Grunt) Cancel() {
	jobs := gr.SelectedJobs(true) // need
	if len(jobs) == 0 {
		return
	}
	gr.RunGruntUpdt("cancel", jobs)
}

// Nuke deletes given job directory (jobs and results) -- use carefully!
// useful for mistakes etc -- better to use delete for no-longer-relevant but valid jobs
func (gr *Grunt) Nuke() {
	jobs := gr.SelectedJobs(true) // need
	if len(jobs) == 0 {
		return
	}
	gr.RunGruntUpdt("nuke", jobs)
}

// Delete moves job directory from active to delete subdir, deletes results
// useful for removing clutter of no-longer-relevant jobs, while retaining a record just in case
func (gr *Grunt) Delete() {
	jobs := gr.SelectedJobs(true) // need
	if len(jobs) == 0 {
		return
	}
	gr.RunGruntUpdt("delete", jobs)
}

// Archive moves job directory from active to archive subdir
// useful for removing clutter from active, and preserving important but non-current results
func (gr *Grunt) Archive() {
	jobs := gr.SelectedJobs(true) // need
	if len(jobs) == 0 {
		return
	}
	gr.RunGruntUpdt("archive", jobs)
}

// MiscCmd runs a misc command that is passed through to grunter.py
func (gr *Grunt) MiscCmd(cmd string) {
	gr.RunGrunt(cmd, gr.SelectedJobs(true))
}

//////////////////////////////////////////////////////////////////////////////
//  Selected Jobs / Views

// SelectedJobs returns the currently-selected list of jobs
// if need is true, an error message is pushed to status about jobs being required
func (gr *Grunt) SelectedJobs(need bool) []string {
	avw := gr.ActiveView()
	if avw == nil {
		gr.StatusMsg("Could not get jobs -- no job views visible")
		return nil
	}
	sel := avw.SelectedIdxsList(false) // ascending
	ns := len(sel)
	if ns == 0 {
		if need {
			gr.StatusMsg(`<span style="color:red">Error: job(s) must be selected for this action!</span>`)
		}
		return nil
	}
	jobs := make([]string, ns)
	ilen := avw.Table.Len()
	for i, si := range sel {
		if si >= ilen {
			continue
		}
		row := avw.Table.Idxs[si]
		if !avw.Table.Table.IsValidRow(row) {
			continue
		}
		jb := avw.Table.Table.CellString("JobId", row)
		jobs[i] = jb
	}
	return jobs
}

func (gr *Grunt) ActiveView() *etview.TableView {
	switch {
	case gr.ActView.IsVisible():
		return gr.ActView
	case gr.DoneView.IsVisible():
		return gr.DoneView
	}
	return nil
}

// StatusMsg displays current status / command being executed, etc
func (gr *Grunt) StatusMsg(msg string) {
	gr.StatMsg = msg
	gr.StatLabel.SetText(msg)
}

// ShowOutput selects the Output tab
func (gr *Grunt) ShowOutput() {
	gr.TabView.SelectTabByName("Output")
}

//////////////////////////////////////////////////////////////////////////////
//  Config GUI

// ConfigTableView configures given tableview
func (gr *Grunt) ConfigTableView(tv *etview.TableView) {
	tv.SetProp("inactive", true)
	tv.SetInactive()
	tv.InactMultiSel = true
	tv.WidgetSig.ConnectOnly(tv.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		if sig != int64(gi.WidgetSelected) {
			return
		}
		sels := gr.SelectedJobs(false)
		if len(sels) == 0 {
			gr.StatusMsg("no jobs selected")
		} else {
			seltxt := strings.Join(sels, " ")
			gr.StatusMsg("jobs selected: " + seltxt)
		}
	})
}

// Config configures grunt gui
func (gr *Grunt) Config() *gi.Window {
	gr.New()
	gr.OpenJobs()

	width := 1600
	height := 1200

	gi.SetAppName("grunti")
	gi.SetAppAbout(`grunti provides an interface to the git-based run tool, grunt. See <a href="https://github.com/emer/grunt">grunt on GitHub</a>.</p>`)

	win := gi.NewMainWindow("grunti", "Grunti", width, height)
	gr.Win = win

	vp := win.WinViewport2D()
	updt := vp.UpdateStart()

	mfr := win.SetMainFrame()

	tbar := gi.AddNewToolBar(mfr, "tbar")
	tbar.SetStretchMaxWidth()
	gr.ToolBar = tbar

	tv := gi.AddNewTabView(mfr, "tv")
	gr.TabView = tv

	gr.StatLabel = gi.AddNewLabel(mfr, "status", "Status...")
	gr.StatLabel.SetStretchMaxWidth()
	gr.StatLabel.Redrawable = true

	gr.ActView = tv.AddNewTab(etview.KiT_TableView, "Active").(*etview.TableView)
	gr.ConfigTableView(gr.ActView)
	gr.ActView.SetTable(gr.Active, nil)

	gr.DoneView = tv.AddNewTab(etview.KiT_TableView, "Done").(*etview.TableView)
	gr.ConfigTableView(gr.DoneView)
	gr.DoneView.SetTable(gr.Done, nil)

	tb := &giv.TextBuf{}
	tb.InitName(tb, "out-buf")
	tb.Hi.Style = gi.Prefs.Colors.HiStyle
	tb.Opts.LineNos = false
	tb.Stat() // update markup
	gr.OutBuf = tb

	prv := tv.AddNewTab(giv.KiT_StructView, "Params").(*giv.StructView)
	prv.SetStretchMax()
	prv.Viewport = vp
	prv.SetStruct(&gr.Params)

	tlv := tv.AddNewTab(gi.KiT_Layout, "Output").(*gi.Layout)
	tlv.SetStretchMax()
	txv := giv.AddNewTextView(tlv, "text-view")
	txv.Viewport = vp
	txv.SetInactive()
	txv.SetProp("font-family", gi.Prefs.MonoFont)
	txv.SetBuf(tb)
	gr.OutView = txv

	rsv := tv.AddNewTab(giv.KiT_TableView, "Results").(*giv.TableView)
	rsv.SetStretchMax()
	rsv.Viewport = vp
	rsv.SetSlice(&gr.ResList)
	gr.ResView = rsv

	plt := tv.AddNewTab(eplot.KiT_Plot2D, "Plot").(*eplot.Plot2D)
	plt.SetStretchMax()
	gr.Plot = plt
	gr.Plot.Params.XAxisCol = gr.Params.XAxis

	// toolbar

	tbar.AddAction(gi.ActOpts{Label: "Update", Icon: "update", Tooltip: "pull updates that might have been pushed from the server, for both results and jobs", UpdateFunc: func(act *gi.Action) {
		act.SetActiveStateUpdt(!gr.InAutoUpdt())
	}}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Update()
		tbar.UpdateActions()
	})

	tbar.AddAction(gi.ActOpts{Label: "Status", Icon: "file-exe", Tooltip: "ping server for updated status of all Active jobs (regardless of current selection), or selected jobs if Done tab is selected"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Status()
		tbar.UpdateActions()
	})

	tbar.AddSeparator("res-sep")

	tbar.AddAction(gi.ActOpts{Label: "Results", Icon: "file-upload", Tooltip: "tell server to commit latest results from all Active jobs (regardless of current selection), or selected jobs if Done tab selected"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Results()
		tbar.UpdateActions()
	})

	tbar.AddAction(gi.ActOpts{Label: "Open...", Icon: "file-open", Tooltip: "open results from selected job(s), according to file names containing given string -- results must be linked into gresults (auto by Results, see Link cmd)"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		giv.CallMethod(gr, "OpenResults", vp)
	})

	tbar.AddAction(gi.ActOpts{Label: "Plot", Icon: "image", Tooltip: "plot selected (or all if none selected) opened Results in Results tab -- if multiple selected, they are merged into a single table and plotted by JobId"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.PlotResults()
	})

	tbar.AddSeparator("job-sep")

	tbar.AddAction(gi.ActOpts{Label: "Submit...", Icon: "plus", Tooltip: "Submit a new job for running on server"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		giv.CallMethod(gr, "Submit", vp)
	})

	tbar.AddAction(gi.ActOpts{Label: "Cancel", Icon: "cancel", Tooltip: "cancel selected jobs"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gi.PromptDialog(vp, gi.DlgOpts{Title: "Cancel: Confirm", Prompt: "Are you <i>sure</i> you want to cancel job(s)?"}, gi.AddOk, gi.AddCancel,
			vp.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
				if sig == int64(gi.DialogAccepted) {
					gr.Cancel()
					tbar.UpdateActions()
				}
			})
	})

	tbar.AddSeparator("file-sep")

	tbar.AddAction(gi.ActOpts{Label: "Out", Icon: "info", Tooltip: "show output of selected job in Output tab"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Output()
		gr.ShowOutput()
		tbar.UpdateActions()
	})

	tbar.AddAction(gi.ActOpts{Label: "List", Icon: "file-text", Tooltip: "shows list of files associated with job(s) in Output tab"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.List()
		gr.ShowOutput()
		tbar.UpdateActions()
	})

	tbar.AddAction(gi.ActOpts{Label: "Files", Icon: "file-download", Tooltip: "gets specific files as listed (space separated) into results, for files that are not automatically copied by grunter.py script -- use List to see list of files on server"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		giv.CallMethod(gr, "Files", vp)
	})

	tbar.AddAction(gi.ActOpts{Label: "Diff", Icon: "file-text", Tooltip: "displays the diffs between either given job and current directory, or between two jobs dirs in Output tab"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Diff()
		gr.ShowOutput()
		tbar.UpdateActions()
	})

	tbar.AddAction(gi.ActOpts{Label: "Link", Icon: "folder", Tooltip: "make symbolic links into local gresults/jobid for job results -- this makes it easier to access the results -- this happens automatically in Results cmd"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Link()
		tbar.UpdateActions()
	})

	tbar.AddAction(gi.ActOpts{Label: "Misc", Icon: "run", Tooltip: "run a misc command that is supported by local grunter.py file"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		giv.CallMethod(gr, "MiscCmd", vp)
	})

	tbar.AddSeparator("del-sep")

	tbar.AddAction(gi.ActOpts{Label: "Nuke!", Icon: "cancel", Tooltip: "deletes given job directory (jobs and results) -- use carefully: could result in permanent loss of non-comitted data!  useful for mistakes etc -- better to use delete for no-longer-relevant but valid jobs"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gi.PromptDialog(vp, gi.DlgOpts{Title: "Nuke: Confirm", Prompt: "Are you <i>sure</i> you want to nuke job(s) -- this could result in permanent deletion of non-committed files!"}, gi.AddOk, gi.AddCancel,
			vp.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
				if sig == int64(gi.DialogAccepted) {
					gr.Nuke()
					tbar.UpdateActions()
				}
			})
	})

	tbar.AddAction(gi.ActOpts{Label: "Delete", Icon: "cut", Tooltip: "moves job directory from active to delete subdir, deletes results -- useful for removing clutter of no-longer-relevant jobs, while retaining a record just in case"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gi.PromptDialog(vp, gi.DlgOpts{Title: "Delete: Confirm", Prompt: "Are you <i>sure</i> you want to delete job(s)?"}, gi.AddOk, gi.AddCancel,
			vp.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
				if sig == int64(gi.DialogAccepted) {
					gr.Delete()
					tbar.UpdateActions()
				}
			})
	})

	tbar.AddAction(gi.ActOpts{Label: "Archive", Icon: "file-archive", Tooltip: "moves job directory from active to archive subdir -- useful for removing clutter from active, and preserving important but non-current results"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gi.PromptDialog(vp, gi.DlgOpts{Title: "Archive: Confirm", Prompt: "Are you <i>sure</i> you want to archive job(s)?"}, gi.AddOk, gi.AddCancel,
			vp.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
				if sig == int64(gi.DialogAccepted) {
					gr.Archive()
					tbar.UpdateActions()
				}
			})
	})

	tbar.AddSeparator("help")

	tbar.AddAction(gi.ActOpts{Label: "README", Icon: "file-markdown", Tooltip: "Opens your browser on the README file that contains help info."}, win.This(),
		func(recv, send ki.Ki, sig int64, data interface{}) {
			gi.OpenURL("https://github.com/emer/grunt/blob/master/grunti/README.md")
		})

	vp.UpdateEndNoSig(updt)

	// main menu
	appnm := gi.AppName()
	mmen := win.MainMenu
	mmen.ConfigMenus([]string{appnm, "File", "Edit", "Window"})

	amen := win.MainMenu.ChildByName(appnm, 0).(*gi.Action)
	amen.Menu.AddAppMenu(win)

	emen := win.MainMenu.ChildByName("Edit", 1).(*gi.Action)
	emen.Menu.AddCopyCutPaste(win)

	win.MainMenuUpdated()

	return win
}

var GruntProps = ki.Props{
	"CallMethods": ki.PropSlice{
		{"OpenResults", ki.Props{
			"desc": "opens results for selected jobs, for file name that contains given string, and has given extension (e.g., .csv = comma separated, .tsv = tab separated)",
			"Args": ki.PropSlice{
				{"Filename Contains", ki.Props{
					"width":         60,
					"default-field": "Params.OpenResultsCont",
				}},
				{"Ext", ki.Props{
					"default": ".tsv",
					"width":   60,
				}},
			},
		}},
		{"Submit", ki.Props{
			"desc": "Specify additional args, space separated, and a message describing this job (key params, etc)",
			"Args": ki.PropSlice{
				{"Args", ki.Props{
					"default-field": "Params.SubmitArgs",
					"width":         80,
				}},
				{"Message", ki.Props{
					"width": 80,
				}},
			},
		}},
		{"Files", ki.Props{
			"desc": "gets specific files as listed (space separated) into results, for files that are not automatically copied by grunter.py script -- use List to see list of files on server",
			"Args": ki.PropSlice{
				{"Files", ki.Props{
					"width": 80,
				}},
			},
		}},
		{"MiscCmd", ki.Props{
			"desc": "This runs a custom command, supported in this project's grunter.py script.  Selected jobs will be passed as args, if any",
			"Args": ki.PropSlice{
				{"Command", ki.Props{
					"width": 20,
				}},
			},
		}},
	},
}
