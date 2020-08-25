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
	XAxis    string         `desc:"default XAxis name for plots"`
	DefRange minmax.Range64 `desc:"default Range params for plot columns"`
}

var KiT_Params = kit.Types.AddType(&Params{}, ParamsProps)

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
