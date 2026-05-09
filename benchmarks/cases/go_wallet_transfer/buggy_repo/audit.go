package main

import "fmt"

type AuditLog struct {
	Entries []string
}

func NewAuditLog() AuditLog {
	return AuditLog{
		Entries: []string{},
	}
}

func (l *AuditLog) RecordTransfer(from string, to string, amount int) {
	entry := fmt.Sprintf("%s -> %s: %d", from, to, amount)
	l.Entries = append(l.Entries, entry)
}

func (l *AuditLog) Count() int {
	return len(l.Entries)
}