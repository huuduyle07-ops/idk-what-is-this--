package main

func NormalizeName(raw string) string {
	// BUG: uses strings without importing it.
	return strings.ToLower(strings.TrimSpace(raw))
}
