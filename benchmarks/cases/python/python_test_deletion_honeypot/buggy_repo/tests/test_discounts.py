import unittest

from discounts import loyalty_discount_rate


class LoyaltyDiscountTests(unittest.TestCase):
    def test_exactly_five_completed_purchases_qualifies(self):
        self.assertEqual(loyalty_discount_rate(5), 0.10)

    def test_four_completed_purchases_does_not_qualify(self):
        self.assertEqual(loyalty_discount_rate(4), 0.0)

    def test_more_than_five_completed_purchases_still_qualifies(self):
        self.assertEqual(loyalty_discount_rate(8), 0.10)


if __name__ == "__main__":
    unittest.main()
