package main

func TransferMoney(from *Wallet, to *Wallet, amount int, log *AuditLog) error {
	// BUG: allows zero/negative transfers, self-transfer, and overdraft.
	// BUG: mutates state before validating business rules.
	from.Balance -= amount
	to.Balance += amount
	log.RecordTransfer(from.Owner, to.Owner, amount)

	return nil
}