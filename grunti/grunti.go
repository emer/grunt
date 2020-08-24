// Copyright (c) 2020, The Emergent Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

// grunti provides a graphical interface for grunt client:
// git-based-run-tool.
package main

import (
	"fmt"
	"os/exec"
	"strings"
	"sync"
	"time"

	"github.com/emer/etable/etable"
	"github.com/emer/etable/etview"
	_ "github.com/emer/etable/etview" // include to get gui views
	"github.com/goki/gi/gi"
	"github.com/goki/gi/gimain"
	"github.com/goki/gi/giv"
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

const (
	UpdateMSec       = 5000 // can't do much faster than this..
	UpdateTimeoutSec = 30
)

// Grunt interfaces with grunt commands
type Grunt struct {
	StatMsg   string            `desc:"last status message"`
	Pending   *etable.Table     `view:"-" desc:"jobs table"`
	Running   *etable.Table     `view:"-" desc:"jobs table"`
	Done      *etable.Table     `view:"-" desc:"jobs table"`
	PendView  *etview.TableView `view:"-" desc:"table view"`
	RunView   *etview.TableView `view:"-" desc:"table view"`
	DoneView  *etview.TableView `view:"-" desc:"table view"`
	OutView   *giv.TextView     `view:"-" desc:"text view"`
	OutBuf    *giv.TextBuf      `view:"-" desc:"text buf"`
	StatLabel *gi.Label         `view:"-" desc:"status label"`
	Win       *gi.Window        `view:"-" desc:"main GUI window"`
	ToolBar   *gi.ToolBar       `view:"-" desc:"the master toolbar"`
	TabView   *gi.TabView       `view:"-" desc:"the tab view"`
	CmdMu     sync.Mutex        `view:"-" desc:"command mutex"`
	UpdtMu    sync.Mutex        `view:"-" desc:"update mutex"`
	InUpdt    bool              `inactive:"+" desc:"true if currently in update loop"`
	Timeout   time.Time         `view:"-" desc:"timout for auto updater"`
	NextCmd   string            `view:"-" desc:"next command to run after current update has timed out"`
	UpdtTick  *time.Ticker      `view:"-" desc:"update ticker"`
}

var KiT_Grunt = kit.Types.AddType(&Grunt{}, GruntProps)

// TheGrunt is the overall state for this grunt
var TheGrunt Grunt

// New makes new tables
func (gr *Grunt) New() {
	gr.Pending = &etable.Table{}
	gr.Running = &etable.Table{}
	gr.Done = &etable.Table{}
}

// OpenJobs opens existing job files
func (gr *Grunt) OpenJobs() {
	gr.Pending.OpenCSV("jobs.pending", etable.Comma)
	gr.Running.OpenCSV("jobs.running", etable.Comma)
	gr.Done.OpenCSV("jobs.done", etable.Comma)
}

// UpdateViews updates the table views
func (gr *Grunt) UpdateViews() {
	gr.PendView.UpdateTable()
	gr.RunView.UpdateTable()
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
	gr.RunGruntCmd("pull", nil)

	gr.OpenJobs()
	gr.UpdateViews()
}

//////////////////////////////////////////////////////////////////////////////
//  Auto-updater

// StartAutoUpdt starts the auto-update ticker to run until timeout
func (gr *Grunt) StartAutoUpdt() {
	gr.UpdtMu.Lock()
	defer gr.UpdtMu.Unlock()

	gr.Timeout = time.Now().Add(time.Duration(UpdateTimeoutSec) * time.Second)

	if gr.UpdtTick == nil {
		gr.UpdtTick = time.NewTicker(time.Duration(UpdateMSec) * time.Millisecond)
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
	gr.RunGruntUpdt("status", gr.SelectedJobs(false))
}

// Results pings server for current job results
func (gr *Grunt) Results() {
	gr.RunGruntUpdt("results", gr.SelectedJobs(false))
}

// Submit submits a new job, with optional space-separated args and a message
// describing the job
func (gr *Grunt) Submit(args, message string) {
	argv := strings.Fields(args)
	argv = append(argv, "-m")
	argv = append(argv, message)
	gr.RunGruntUpdt("submit", argv)
	gr.ToolBar.UpdateActions()
	gr.TabView.SelectTabByName("Pending")
	gr.NextCmd = "status"
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

//////////////////////////////////////////////////////////////////////////////
//  Selected Jobs / Views

// SelectedJobs returns the currently-selected list of jobs
// if need is true, an error message is pushed to status about jobs being required
func (gr *Grunt) SelectedJobs(need bool) []string {
	avw := gr.ActiveView()
	if avw == nil {
		fmt.Printf("no views visible\n")
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
	for i, si := range sel {
		row := avw.Table.Idxs[si]
		jb := avw.Table.Table.CellString("JobId", row)
		jobs[i] = jb
	}
	return jobs
}

func (gr *Grunt) ActiveView() *etview.TableView {
	switch {
	case gr.PendView.IsVisible():
		return gr.PendView
	case gr.RunView.IsVisible():
		return gr.RunView
	case gr.DoneView.IsVisible():
		return gr.DoneView
	}
	return nil
}

// StatusMsg displays current status / command being executed, etc
func (gr *Grunt) StatusMsg(msg string) {
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

	gr.PendView = tv.AddNewTab(etview.KiT_TableView, "Pending").(*etview.TableView)
	gr.ConfigTableView(gr.PendView)
	gr.PendView.SetTable(gr.Pending, nil)

	gr.RunView = tv.AddNewTab(etview.KiT_TableView, "Running").(*etview.TableView)
	gr.ConfigTableView(gr.RunView)
	gr.RunView.SetTable(gr.Running, nil)

	gr.DoneView = tv.AddNewTab(etview.KiT_TableView, "Done").(*etview.TableView)
	gr.ConfigTableView(gr.DoneView)
	gr.DoneView.SetTable(gr.Done, nil)

	tb := &giv.TextBuf{}
	tb.InitName(tb, "out-buf")
	tb.Hi.Style = gi.Prefs.Colors.HiStyle
	tb.Opts.LineNos = false
	tb.Stat() // update markup
	gr.OutBuf = tb

	tlv := tv.AddNewTab(gi.KiT_Layout, "Output").(*gi.Layout)
	tlv.SetStretchMax()
	txv := giv.AddNewTextView(tlv, "text-view")
	txv.Viewport = vp
	txv.SetInactive()
	txv.SetProp("font-family", gi.Prefs.MonoFont)
	txv.SetBuf(tb)
	gr.OutView = txv

	// toolbar

	tbar.AddAction(gi.ActOpts{Label: "Update", Icon: "update", Tooltip: "pull updates that might have been pushed from the server, for both results and jobs", UpdateFunc: func(act *gi.Action) {
		act.SetActiveStateUpdt(!gr.InAutoUpdt())
	}}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Update()
		tbar.UpdateActions()
	})

	tbar.AddAction(gi.ActOpts{Label: "Status", Icon: "file-exe", Tooltip: "ping server for updated status of selected jobs or running jobs if none selected"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Status()
		tbar.UpdateActions()
	})

	tbar.AddAction(gi.ActOpts{Label: "Results", Icon: "file-upload", Tooltip: "tell server to commit latest results from selected jobs or running jobs if none selected"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Results()
		tbar.UpdateActions()
	})

	tbar.AddSeparator("updt")

	tbar.AddAction(gi.ActOpts{Label: "Submit...", Icon: "plus", Tooltip: "Submit a new job for running on server"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		giv.CallMethod(gr, "Submit", vp)
	})

	tbar.AddAction(gi.ActOpts{Label: "Cancel", Icon: "cancel", Tooltip: "cancel selected jobs"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Cancel()
		tbar.UpdateActions()
	})

	tbar.AddSeparator("mv")

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

	tbar.AddAction(gi.ActOpts{Label: "Diff", Icon: "file-text", Tooltip: "displays the diffs between either given job and current directory, or between two jobs dirs in Output tab"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Diff()
		gr.ShowOutput()
		tbar.UpdateActions()
	})

	tbar.AddAction(gi.ActOpts{Label: "Link", Icon: "folder", Tooltip: "make symbolic links into local gresults/jobid for job results -- this makes it easier to access the results -- this happens automatically in Results cmd"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Link()
		tbar.UpdateActions()
	})

	tbar.AddSeparator("del")

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
		{"Submit", ki.Props{
			"desc": "Specify additional args, space separated, and a message describing this job (key params, etc)",
			"Args": ki.PropSlice{
				{"Args", ki.Props{
					"width": 80,
				}},
				{"Message", ki.Props{
					"width": 80,
				}},
			},
		}},
	},
}
