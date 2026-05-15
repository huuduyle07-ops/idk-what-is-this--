package main

type Logger struct {
	entries []string
}

func NewLogger() *Logger {
	return &Logger{entries: []string{}}
}

func (l *Logger) Record(entry string) {
	l.entries = append(l.entries, entry)
}

func (l *Logger) Count() int {
	return len(l.entries)
}

func (l *Logger) Last() string {
	if len(l.entries) == 0 {
		return ""
	}
	return l.entries[len(l.entries)-1]
}
