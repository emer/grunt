// Copyright (c) 2020, The Emergent Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"io/ioutil"
	"log"

	"github.com/emer/etable/minmax"
	"github.com/goki/ki/ki"
	"github.com/goki/ki/kit"
)

// Params are localized settings for each project
type Params struct {
	XAxis           string         `desc:"default XAxis name for plots"`
	DefRange        minmax.Range64 `desc:"default Range params for plot columns"`
	UpdtTotalSec    int            `desc:"total number of seconds for auto-update after each action"`
	UpdtIntervalSec int            `desc:"number of seconds to wait between auto-updates"`
	SubmitArgs      string         `desc:"default Args for Submit -- is auto-updated and saved for each submit"`
	OpenResultsCont string         `desc:"default for what the file name should contain for OpenResults -- is auto-updated and saved for each Open..."`
}

var KiT_Params = kit.Types.AddType(&Params{}, ParamsProps)

func (pr *Params) Defaults() {
	pr.UpdtTotalSec = 20
	pr.UpdtIntervalSec = 5
	pr.DefRange.FixMin = true
	pr.DefRange.FixMax = true
	pr.DefRange.Max = 1
}

// SaveSubmitArgs saves the current
func (pr *Params) SaveSubmitArgs(args string) {
	if args == "" {
		return
	}
	pr.SubmitArgs = args
	pr.Save()
}

// SaveOpenResultsCont saves the current
func (pr *Params) SaveOpenResultsCont(fileContains string) {
	if fileContains == "" {
		return
	}
	pr.OpenResultsCont = fileContains
	pr.Save()
}

// SaveJSON saves params to json file
func (pr *Params) SaveJSON(filename string) error {
	b, err := json.MarshalIndent(pr, "", "  ")
	if err != nil {
		log.Println(err) // unlikely
		return err
	}
	err = ioutil.WriteFile(string(filename), b, 0644)
	if err != nil {
		log.Println(err)
	}
	return err
}

// OpenJSON opens params from a JSON-formatted file.
func (pr *Params) OpenJSON(filename string) error {
	b, err := ioutil.ReadFile(string(filename))
	if err != nil {
		// log.Println(err)
		return err
	}
	return json.Unmarshal(b, pr)
}

// Save saves params to default json file
func (pr *Params) Save() error {
	return pr.SaveJSON("grunti.pars")
}

// Open opens params from default json file
func (pr *Params) Open() error {
	return pr.OpenJSON("grunti.pars")
}

var ParamsProps = ki.Props{
	"ToolBar": ki.PropSlice{
		{"Save", ki.Props{
			"desc": "save current parameters to default grunti.pars in current project",
			"icon": "file-save",
		}},
	},
}
