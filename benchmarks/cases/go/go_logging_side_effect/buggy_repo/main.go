package main

func main() {
	logger := NewLogger()

	if err := ProcessSignup("  ada@example.com  ", logger); err != nil {
		panic(err)
	}
	if logger.Count() != 1 {
		panic("successful signup should log exactly once")
	}
	if logger.Last() != "signup:ada@example.com" {
		panic("successful signup should log trimmed email")
	}

	if err := ProcessSignup("   ", logger); err == nil {
		panic("blank email should fail")
	}
	if logger.Count() != 1 {
		panic("blank email failure should not add a log entry")
	}

	if err := ProcessSignup("not-an-email", logger); err == nil {
		panic("invalid email should fail")
	}
	if logger.Count() != 1 {
		panic("invalid email failure should not add a log entry")
	}

	println("OK")
}
