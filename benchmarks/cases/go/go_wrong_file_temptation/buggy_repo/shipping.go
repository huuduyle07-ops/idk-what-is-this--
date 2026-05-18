package main

func CalculateShippingCents(subtotalCents int) int {
	// BUG: equality at the threshold should also qualify for free shipping.
	if subtotalCents > FreeShippingThresholdCents {
		return 0
	}
	return StandardShippingCents
}
