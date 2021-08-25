// Code generated by "stringer -type=Tables"; DO NOT EDIT.

package main

import (
	"errors"
	"strconv"
)

var _ = errors.New("dummy error")

func _() {
	// An "invalid array index" compiler error signifies that the constant values have changed.
	// Re-run the stringer command to generate them again.
	var x [1]struct{}
	_ = x[Active-0]
	_ = x[Done-1]
	_ = x[Archive-2]
	_ = x[Delete-3]
	_ = x[TablesN-4]
}

const _Tables_name = "ActiveDoneArchiveDeleteTablesN"

var _Tables_index = [...]uint8{0, 6, 10, 17, 23, 30}

func (i Tables) String() string {
	if i < 0 || i >= Tables(len(_Tables_index)-1) {
		return "Tables(" + strconv.FormatInt(int64(i), 10) + ")"
	}
	return _Tables_name[_Tables_index[i]:_Tables_index[i+1]]
}

func (i *Tables) FromString(s string) error {
	for j := 0; j < len(_Tables_index)-1; j++ {
		if s == _Tables_name[_Tables_index[j]:_Tables_index[j+1]] {
			*i = Tables(j)
			return nil
		}
	}
	return errors.New("String: " + s + " is not a valid option for type: Tables")
}