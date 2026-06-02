package main

// Clamp returns value clamped to [minVal, maxVal].
func Clamp(value, minVal, maxVal int) int {
	if value > maxVal {
		return maxVal
	}
	// BUG: missing lower-bound check — values below minVal pass through unclamped
	return value
}
