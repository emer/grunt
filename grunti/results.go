// Copyright (c) 2020, The Emergent Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package main

import (
	"log"

	"github.com/emer/etable/etable"
	"github.com/emer/etable/etensor"
	"github.com/goki/gi/gi"
	"github.com/goki/ki/ki"
	"github.com/goki/ki/kit"
)

// Result has info for one loaded result, in form of an etable.Table
type Result struct {
	JobId string        `desc:"job id for results"`
	Path  string        `width:"60" desc:"path to data"`
	Table *etable.Table `desc:"result data"`
}

// OpenCSV opens data of generic CSV format (any delim, auto-detected)
func (r *Result) OpenCSV() error {
	err := r.Table.OpenCSV(gi.FileName(r.Path), etable.Tab) // todo auto-detect
	if err != nil {
		log.Println(err)
	}
	return err
}

// TableWithJobId returns a copy of the Table with a new column JobId with the JobId
// used for aggregating data across multiple results
func (r *Result) TableWithJobId() *etable.Table {
	if r.Table == nil {
		return nil
	}
	dt := r.Table.Clone()
	jc := etensor.NewString([]int{dt.Rows}, nil, nil)
	dt.AddCol(jc, "JobId")
	for i := range jc.Values {
		jc.Values[i] = r.JobId
	}
	return dt
}

// Results is a list (slice) of results
type Results []*Result

var KiT_Results = kit.Types.AddType(&Results{}, ResultsProps)

// Add adds given file path to CSV (TSV) data to results
func (rs *Results) Add(jobid, fpath string) *Result {
	r := &Result{JobId: jobid, Path: fpath}
	r.Table = &etable.Table{}
	r.OpenCSV()
	*rs = append(*rs, r)
	return r
}

// Reload reloads all the data for any results with Use set
func (rs *Results) Reload() {
	for _, r := range *rs {
		r.OpenCSV()
	}
}

var ResultsProps = ki.Props{
	"ToolBar": ki.PropSlice{
		{"Reload", ki.Props{
			"desc": "reload all data from files",
			"icon": "update",
		}},
	},
}
