package main

func assertEqual(actual int, expected int, message string) {
	if actual != expected {
		panic(message)
	}
}

func main() {
	// The symptom shows up here, where ProcessOrder is called. The bug is
	// NOT in main.go or service.go — it's in the helper they delegate to.
	assertEqual(
		ProcessOrder([]int{10, 20, 30}),
		60,
		"ProcessOrder([10, 20, 30]) should equal 60",
	)
	assertEqual(
		ProcessOrder([]int{5}),
		5,
		"ProcessOrder([5]) should equal 5",
	)
	assertEqual(
		ProcessOrder([]int{}),
		0,
		"ProcessOrder([]) should equal 0",
	)

	println("OK")
}
