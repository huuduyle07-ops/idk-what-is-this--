package main

import (
	"errors"
	"strings"
)

type InviteRequest struct {
	Email string
	Role  string
}

type Invite struct {
	Email string
	Role  string
}

func BuildInvite(request InviteRequest) (Invite, error) {
	email := request.Email
	if email == "" || !strings.Contains(email, "@") {
		return Invite{}, errors.New("valid email required")
	}

	role := strings.ToLower(strings.TrimSpace(request.Role))
	if role != "viewer" && role != "editor" {
		return Invite{}, errors.New("unsupported role")
	}

	return Invite{Email: email, Role: role}, nil
}
