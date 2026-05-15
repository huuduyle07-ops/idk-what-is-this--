package main

import (
	"errors"
	"strings"
)

func ProcessSignup(email string, logger *Logger) error {
	// BUG: records the event before validation and before trimming the email.
	logger.Record("signup:" + email)

	if strings.TrimSpace(email) == "" {
		return errors.New("email is required")
	}
	if !strings.Contains(email, "@") {
		return errors.New("email must contain @")
	}
	return nil
}
