package main

import "fmt"

type Wallet struct {
	Owner   string
	Balance int
}

func NewWallet(owner string, balance int) Wallet {
	return Wallet{
		Owner:   owner,
		Balance: balance,
	}
}

func (w *Wallet) Deposit(amount int) error {
	if amount <= 0 {
		return fmt.Errorf("amount must be positive")
	}

	w.Balance += amount
	return nil
}

func (w *Wallet) Withdraw(amount int) error {
	if amount <= 0 {
		return fmt.Errorf("amount must be positive")
	}

	if amount > w.Balance {
		return fmt.Errorf("insufficient funds")
	}

	w.Balance -= amount
	return nil
}