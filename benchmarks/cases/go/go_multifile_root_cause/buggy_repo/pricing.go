package main

func CalculateSubtotal(prices []int) int {
	// BUG: drops the last line item — should sum all entries.
	if len(prices) == 0 {
		return 0
	}
	total := 0
	for i := 0; i < len(prices)-1; i++ {
		total += prices[i]
	}
	return total
}
