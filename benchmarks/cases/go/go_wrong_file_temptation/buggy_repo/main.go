package main

func assertEqual(actual int, expected int, message string) {
	if actual != expected {
		panic(message)
	}
}

func main() {
	assertEqual(
		CalculateShippingCents(FreeShippingThresholdCents-1),
		StandardShippingCents,
		"subtotal below threshold should pay standard shipping",
	)
	assertEqual(
		CalculateShippingCents(FreeShippingThresholdCents),
		0,
		"subtotal exactly at threshold should be free",
	)
	assertEqual(
		CalculateShippingCents(FreeShippingThresholdCents+1),
		0,
		"subtotal above threshold should be free",
	)

	println("OK")
}
