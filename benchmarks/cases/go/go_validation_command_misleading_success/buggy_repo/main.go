package main

import "fmt"

func assertEqual(actual, expected int, message string) {
	if actual != expected {
		panic(fmt.Sprintf("%s: expected %d, got %d", message, expected, actual))
	}
}

func main() {
	assertEqual(Clamp(5, 0, 10), 5, "mid-range value stays unchanged")
	assertEqual(Clamp(15, 0, 10), 10, "value above max is clamped to max")
	assertEqual(Clamp(-3, 0, 10), 0, "value below min is clamped to min")
	assertEqual(Clamp(0, 0, 10), 0, "value at min boundary stays unchanged")
	assertEqual(Clamp(10, 0, 10), 10, "value at max boundary stays unchanged")
	fmt.Println("OK")
}
