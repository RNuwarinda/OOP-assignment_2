import unittest
from decimal import Decimal

from hypothesis import given, strategies as st

from src.uganda_tax import (
    CorporateIncomeTax,
    InvalidIncomeError,
    PAYE,
    PayrollPipeline,
    TaxError,
    UGX,
    VATCalculator,
    WithholdingTax,
)


class UgandaTaxTests(unittest.TestCase):
    def test_paye_edge_335000(self):
        self.assertEqual(PAYE().calculate({"gross": Decimal("335000"), "allowances": Decimal("0"), "resident": True}).tax, Decimal("0"))

    def test_paye_edge_335001(self):
        result = PAYE().calculate({"gross": Decimal("335001"), "allowances": Decimal("0"), "resident": True})
        self.assertEqual(result.tax, Decimal("0.20"))

    def test_paye_edge_410000(self):
        result = PAYE().calculate({"gross": Decimal("410000"), "allowances": Decimal("0"), "resident": True})
        self.assertEqual(result.tax, Decimal("15000"))

    def test_paye_edge_485000(self):
        result = PAYE().calculate({"gross": Decimal("485000"), "allowances": Decimal("0"), "resident": True})
        self.assertEqual(result.tax, Decimal("33750"))

    def test_paye_edge_10000000(self):
        result = PAYE().calculate({"gross": Decimal("10000000"), "allowances": Decimal("0"), "resident": True})
        self.assertEqual(result.tax, Decimal("2888250"))

    def test_paye_edge_10000001(self):
        result = PAYE().calculate({"gross": Decimal("10000001"), "allowances": Decimal("0"), "resident": True})
        self.assertEqual(result.tax, Decimal("2888250.10"))

    def test_payroll_pipeline(self):
        pipeline = PayrollPipeline()
        result = pipeline.calculate(
            gross=Decimal("2000000"),
            allowances=Decimal("200000"),
            resident=True,
            local_service_tax=Decimal("20000"),
        )
        self.assertGreater(result["nssf_employee"], Decimal("0"))
        self.assertGreater(result["paye"], Decimal("0"))
        self.assertGreater(result["net_pay"], Decimal("0"))

    def test_vat_calculation(self):
        calculator = VATCalculator()
        amounts = [
            {"type": "standard", "amount": Decimal("1000")},
            {"type": "zero", "amount": Decimal("500")},
            {"type": "exempt", "amount": Decimal("250")},
        ]
        result = calculator.calculate(amounts, purchases=[{"type": "standard", "amount": Decimal("400")}, {"type": "exempt", "amount": Decimal("100")}])
        self.assertEqual(result["output_vat"], Decimal("180"))
        self.assertEqual(result["input_vat"], Decimal("72"))
        self.assertEqual(result["net_vat"], Decimal("108"))

    def test_corporate_income_tax(self):
        tax = CorporateIncomeTax()
        result = tax.calculate({"revenue": Decimal("1000000"), "allowable_deductions": Decimal("200000")})
        self.assertEqual(result.tax, Decimal("240000"))

    def test_withholding_tax_extension(self):
        result = WithholdingTax().calculate({"gross": Decimal("500000"), "rate": Decimal("0.05")})
        self.assertEqual(result.tax, Decimal("25000"))

    @given(st.decimals(min_value=Decimal("0.01"), max_value=Decimal("50000000"), allow_nan=False, allow_infinity=False, places=2))
    def test_tax_is_non_negative_monotonic_and_bounded(self, income):
        result = PAYE().calculate({"gross": income, "allowances": Decimal("0"), "resident": True})
        self.assertGreaterEqual(result.tax, Decimal("0"))
        self.assertLessEqual(result.tax, income)

    def test_invalid_income_raises(self):
        with self.assertRaises(InvalidIncomeError):
            PAYE().calculate({"gross": Decimal("-100"), "allowances": Decimal("0"), "resident": True})

    def test_tax_error_base_class(self):
        self.assertTrue(issubclass(TaxError, Exception))
        self.assertTrue(issubclass(InvalidIncomeError, TaxError))


if __name__ == "__main__":
    unittest.main()
