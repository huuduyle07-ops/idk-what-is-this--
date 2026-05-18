package main

import "fmt"

func requireEqual(actual string, expected string, message string) {
	if actual != expected {
		panic(fmt.Sprintf("%s: expected %q, got %q", message, expected, actual))
	}
}

func main() {
	requireEqual(NormalizeName("  Alice  "), "alice", "should trim and lowercase")
	requireEqual(NormalizeName("\tBOB\n"), "bob", "should trim tabs/newlines and lowercase")
	requireEqual(NormalizeName("charlie"), "charlie", "already normalized name should stay same")

	fmt.Println("OK")
}
