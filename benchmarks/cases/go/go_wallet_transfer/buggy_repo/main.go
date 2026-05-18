package main

func main() {
	alice := NewWallet("Alice", 100)
	bob := NewWallet("Bob", 50)
	log := NewAuditLog()

	if err := TransferMoney(&alice, &bob, 30, &log); err != nil {
		panic(err)
	}

	if alice.Balance != 70 {
		panic("sender balance should decrease after valid transfer")
	}

	if bob.Balance != 80 {
		panic("receiver balance should increase after valid transfer")
	}

	if log.Count() != 1 {
		panic("successful transfer should be logged exactly once")
	}

	if err := TransferMoney(&alice, &bob, 999, &log); err == nil {
		panic("overdraft transfer should fail")
	}

	if alice.Balance != 70 || bob.Balance != 80 {
		panic("failed overdraft transfer must not change balances")
	}

	if log.Count() != 1 {
		panic("failed transfer must not be logged")
	}

	if err := TransferMoney(&alice, &bob, 0, &log); err == nil {
		panic("zero transfer should fail")
	}

	if err := TransferMoney(&alice, &bob, -10, &log); err == nil {
		panic("negative transfer should fail")
	}

	if alice.Balance != 70 || bob.Balance != 80 {
		panic("failed invalid amount transfer must not change balances")
	}

	if log.Count() != 1 {
		panic("failed invalid amount transfer must not be logged")
	}

	if err := TransferMoney(&alice, &alice, 10, &log); err == nil {
		panic("self-transfer should fail")
	}

	if alice.Balance != 70 || bob.Balance != 80 {
		panic("failed self-transfer must not change balances")
	}

	if log.Count() != 1 {
		panic("failed self-transfer must not be logged")
	}

	println("OK")
}