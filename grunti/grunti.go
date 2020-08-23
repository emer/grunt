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

// LogPrec is precision for saving float values in logs
const LogPrec = 4

// Grunt interfaces with grunt commands
type Grunt struct {
	Pending  *etable.Table     `view:"-" desc:"jobs table"`
	Running  *etable.Table     `view:"-" desc:"jobs table"`
	Done     *etable.Table     `view:"-" desc:"jobs table"`
	PendView *etview.TableView `view:"-" desc:"table view"`
	RunView  *etview.TableView `view:"-" desc:"table view"`
	DoneView *etview.TableView `view:"-" desc:"table view"`
	OutView  *giv.TextView     `view:"-" desc:"text view"`
	OutBuf   *giv.TextBuf      `view:"-" desc:"text buf"`
	Win      *gi.Window        `view:"-" desc:"main GUI window"`
	ToolBar  *gi.ToolBar       `view:"-" desc:"the master toolbar"`
	Mu       sync.Mutex        `view:"-" desc:"update mutex"`
	UpdtTick *time.Ticker      `view:"-" desc:"update ticker"`
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
	if !gr.Win.IsVisible() {
		return
	}

	// each locks
	gr.RunGruntCmd("jobs", nil)
	gr.RunGruntCmd("pull", nil)

	gr.Mu.Lock()
	defer gr.Mu.Unlock()
	gr.OpenJobs()
	gr.UpdateViews()
}

//////////////////////////////////////////////////////////////////////////////
//  Auto-updater

// StartTicker starts the ticker if it has not yet been started -- returns false if already
// Note: this is a bit invasive..
func (gr *Grunt) StartTicker() bool {
	if gr.UpdtTick != nil {
		return false
	}
	gr.UpdtTick = time.NewTicker(time.Duration(5000) * time.Millisecond)
	go gr.TickerUpdate()
	return true
}

// TickerUpdate is the update function from the ticker
func (gr *Grunt) TickerUpdate() {
	for {
		<-gr.UpdtTick.C
		gr.Update()
	}
}

//////////////////////////////////////////////////////////////////////////////
//  Commands

func (gr *Grunt) RunGruntCmd(grcmd string, args []string) error {
	// gr.StartTicker() // make sure -- only runs if not already
	gr.Mu.Lock()
	defer gr.Mu.Unlock()

	margs := make([]string, 0, len(args)+1)
	margs = append(margs, grcmd)
	margs = append(margs, args...)
	cmd := exec.Command("grunt", margs...)
	out, err := cmd.CombinedOutput()
	// fmt.Printf("%s\n", out)
	gr.OutBuf.SetText(out)
	return err
}

// Status pings server for current job status
func (gr *Grunt) Status() {
	gr.RunGruntCmd("status", gr.SelectedJobs())
}

// Results pings server for current job results
func (gr *Grunt) Results() {
	gr.RunGruntCmd("results", gr.SelectedJobs())
}

// Submit submits a new job, with optional space-separated args and a message
// describing the job
func (gr *Grunt) Submit(args, message string) {
	argv := strings.Fields(args)
	argv = append(argv, "-m")
	argv = append(argv, message)
	gr.RunGruntCmd("submit", argv)
}

// Cancel cancels given job
func (gr *Grunt) Cancel() {
	jobs := gr.SelectedJobs()
	if len(jobs) == 0 {
		fmt.Printf("no jobs selected to cancel!\n")
		return
	}
	gr.RunGruntCmd("cancel", jobs)
}

// Output shows output of selected job
func (gr *Grunt) Output() {
	jobs := gr.SelectedJobs()
	if len(jobs) == 0 {
		fmt.Printf("no jobs selected to output!\n")
		return
	}
	gr.RunGruntCmd("out", jobs)
}

//////////////////////////////////////////////////////////////////////////////
//  Selected Jobs / Views

func (gr *Grunt) SelectedJobs() []string {
	avw := gr.ActiveView()
	if avw == nil {
		fmt.Printf("no views visible\n")
		return nil
	}
	sel := avw.SelectedIdxsList(false) // ascending
	ns := len(sel)
	if ns == 0 {
		return nil
	}
	fmt.Printf("sel: %v\n", sel)
	jobs := make([]string, ns)
	for i, si := range sel {
		row := avw.Table.Idxs[si]
		jb := avw.Table.Table.CellString("JobId", row)
		jobs[i] = jb
	}
	fmt.Printf("sel jobs: %v\n", jobs)
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

//////////////////////////////////////////////////////////////////////////////
//  Config GUI

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

	gr.PendView = tv.AddNewTab(etview.KiT_TableView, "Pending").(*etview.TableView)
	gr.PendView.SetProp("inactive", true)
	gr.PendView.SetInactive()
	gr.PendView.SetTable(gr.Pending, nil)

	gr.RunView = tv.AddNewTab(etview.KiT_TableView, "Running").(*etview.TableView)
	gr.RunView.SetProp("inactive", true)
	gr.RunView.SetInactive()
	gr.RunView.SetTable(gr.Running, nil)

	gr.DoneView = tv.AddNewTab(etview.KiT_TableView, "Done").(*etview.TableView)
	gr.DoneView.SetProp("inactive", true)
	gr.DoneView.SetInactive()
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

	tbar.AddAction(gi.ActOpts{Label: "Update", Icon: "update", Tooltip: "pull updates that might have been pushed from the server, for both results and jobs"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Update()
	})

	tbar.AddAction(gi.ActOpts{Label: "Status", Icon: "file-exe", Tooltip: "ping server for updated status of selected jobs or running jobs if none selected"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Status()
	})

	tbar.AddAction(gi.ActOpts{Label: "Results", Icon: "file-upload", Tooltip: "tell server to commit latest results from selected jobs or running jobs if none selected"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Results()
	})

	tbar.AddSeparator("updt")

	tbar.AddAction(gi.ActOpts{Label: "Submit", Icon: "plus", Tooltip: "Submit a new job for running on server"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		giv.CallMethod(gr, "Submit", vp)
	})

	tbar.AddAction(gi.ActOpts{Label: "Cancel", Icon: "cancel", Tooltip: "cancel selected jobs"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Cancel()
	})

	tbar.AddSeparator("mv")

	tbar.AddAction(gi.ActOpts{Label: "Out", Icon: "file-text", Tooltip: "show output of selected job in Output tab"}, win.This(), func(recv, send ki.Ki, sig int64, data interface{}) {
		gr.Output()
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
			"Desc": "Specify additional args, space separated, and a message describing this job (key params, etc)",
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
