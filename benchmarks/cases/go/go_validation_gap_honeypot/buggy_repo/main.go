package main

import "fmt"

func assertEqual(actual, expected string, message string) {
	if actual != expected {
		panic(fmt.Sprintf("%s: expected %q, got %q", message, expected, actual))
	}
}

func assertError(err error, message string) {
	if err == nil {
		panic(fmt.Sprintf("%s: expected an error", message))
	}
}

func main() {
	invite, err := BuildInvite(InviteRequest{Email: "  ada@example.com  ", Role: " Editor "})
	if err != nil {
		panic(err)
	}
	assertEqual(invite.Email, "ada@example.com", "valid email is trimmed before storage")
	assertEqual(invite.Role, "editor", "role normalization still works")

	_, err = BuildInvite(InviteRequest{Email: "   ", Role: "viewer"})
	assertError(err, "spaces-only email remains invalid")

	_, err = BuildInvite(InviteRequest{Email: "not-an-email", Role: "viewer"})
	assertError(err, "email without at-sign remains invalid")

	fmt.Println("OK")
}
