package main

// ProcessOrder is the public service-layer entry point. It delegates the
// actual arithmetic to CalculateSubtotal in pricing.go — that helper owns
// the summation rule. The defect is in pricing.go, not here.
func ProcessOrder(lineItemPrices []int) int {
	return CalculateSubtotal(lineItemPrices)
}
