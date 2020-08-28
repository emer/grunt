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
	JobId string        `inactive:"+" desc:"job id for results"`
	Path  string        `inactive:"+" width:"60" desc:"path to data"`
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

// Add adds given job and file path to CSV (TSV) data to results.
func (rs *Results) Add(jobid, path string) *Result {
	r := &Result{JobId: jobid, Path: path}
	r.Table = &etable.Table{}
	r.OpenCSV()
	*rs = append(*rs, r)
	return r
}

// Recycle returns existing Result, or adds if not.
func (rs *Results) Recycle(jobid, path string) *Result {
	r := rs.FindJobPath(jobid, path)
	if r != nil {
		r.OpenCSV()
		return r
	}
	return rs.Add(jobid, path)
}

// FindJobPath finds a result for given job and path -- returns nil if not found
func (rs *Results) FindJobPath(jobid, path string) *Result {
	for _, r := range *rs {
		if r.JobId == jobid && r.Path == path {
			return r
		}
	}
	return nil
}

// Reload reloads all the data for any results with Use set
func (rs *Results) Reload() {
	for _, r := range *rs {
		r.OpenCSV()
	}
}

// Reset resets all loaded data
func (rs *Results) Reset() {
	*rs = make(Results, 0)
}

var ResultsProps = ki.Props{
	"ToolBar": ki.PropSlice{
		{"Reload", ki.Props{
			"desc": "reload all data from files",
			"icon": "update",
		}},
		{"Reset", ki.Props{
			"desc": "reset all data -- use Open... to open new ones",
			"icon": "minus",
		}},
	},
}
