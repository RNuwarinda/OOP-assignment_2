"""Uganda tax calculation utilities for PAYE, payroll deductions, VAT, and corporate tax."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Mapping


MONEY_QUANT = Decimal("0.01")
ZERO = Decimal("0")


class TaxError(Exception):
    """Base exception for tax calculation problems."""


class InvalidIncomeError(TaxError, ValueError):
    """Raised when income is negative or otherwise invalid."""


class NoScheduleForDateError(TaxError):
    """Raised when no tax schedule exists for a requested date."""


@dataclass(frozen=True)
class UGX:
    """Money value object for Uganda shillings with explicit rounding behavior."""

    amount: Decimal

    def __post_init__(self):
        object.__setattr__(self, "amount", self.amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))

    @classmethod
    def from_value(cls, value: Decimal | int | str) -> "UGX":
        if isinstance(value, UGX):
            return value
        return cls(Decimal(str(value)))

    def __add__(self, other: "UGX") -> "UGX":
        if not isinstance(other, UGX):
            return NotImplemented
        return UGX(self.amount + other.amount)

    def __mul__(self, factor: Decimal | int | str) -> "UGX":
        return UGX(self.amount * Decimal(str(factor)))

    def __lt__(self, other: "UGX") -> bool:
        if not isinstance(other, UGX):
            return NotImplemented
        return self.amount < other.amount

    def __repr__(self) -> str:
        return f"UGX({self.amount})"


@dataclass(frozen=True)
class TaxContext:
    gross: Decimal
    allowances: Decimal = ZERO
    resident: bool = True
    local_service_tax: Decimal = ZERO
    date: date | None = None


@dataclass(frozen=True)
class TaxResult:
    tax: Decimal
    net: Decimal
    details: dict[str, Decimal] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Decimal:
        return self.details.get(key, self.tax if key == "tax" else self.net)


class Tax(ABC):
    """Abstract base class for all tax calculators."""

    @abstractmethod
    def calculate(self, ctx: Mapping[str, Any] | TaxContext) -> TaxResult:
        """Calculate the tax and return a TaxResult."""


def _as_decimal(value: Any, field_name: str) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except Exception as exc:  # pragma: no cover - defensive conversion
        raise InvalidIncomeError(f"{field_name} must be numeric") from exc
    if not decimal_value.is_finite():
        raise InvalidIncomeError(f"{field_name} must be finite")
    return decimal_value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _coerce_context(ctx: Mapping[str, Any] | TaxContext) -> TaxContext:
    if isinstance(ctx, TaxContext):
        return ctx
    if not isinstance(ctx, Mapping):
        raise TaxError("Context must be a mapping or TaxContext")

    gross = _as_decimal(ctx.get("gross", ZERO), "gross")
    allowances = _as_decimal(ctx.get("allowances", ZERO), "allowances")
    if gross < ZERO:
        raise InvalidIncomeError("gross income cannot be negative")
    if allowances < ZERO:
        raise InvalidIncomeError("allowances cannot be negative")

    resident = bool(ctx.get("resident", True))
    local_service_tax = _as_decimal(ctx.get("local_service_tax", ZERO), "local_service_tax")
    date_value = ctx.get("date")
    return TaxContext(
        gross=gross,
        allowances=allowances,
        resident=resident,
        local_service_tax=local_service_tax,
        date=date_value,
    )


class PAYE(Tax):
    """Progressive PAYE calculator for monthly income."""

    def calculate(self, ctx: Mapping[str, Any] | TaxContext) -> TaxResult:
        context = _coerce_context(ctx)
        gross = context.gross
        taxable = max(gross - context.allowances, ZERO)
        if not context.resident:
            taxable = gross

        if taxable <= Decimal("335000"):
            tax = ZERO
        elif taxable <= Decimal("410000"):
            tax = (taxable - Decimal("335000")) * Decimal("0.20")
        elif taxable <= Decimal("485000"):
            tax = Decimal("15000") + (taxable - Decimal("410000")) * Decimal("0.25")
        elif taxable <= Decimal("10000000"):
            tax = Decimal("33750") + (taxable - Decimal("485000")) * Decimal("0.30")
        else:
            tax = Decimal("2888250") + (taxable - Decimal("10000000")) * Decimal("0.10")

        tax = tax.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        net = (gross - tax).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        return TaxResult(
            tax=tax,
            net=net,
            details={"gross": gross, "taxable_income": taxable, "allowances": context.allowances},
        )


class PayrollPipeline:
    """Compute NSSF, local service tax, PAYE, and net monthly pay in deduction order."""

    def calculate(
        self,
        *,
        gross: Decimal | int | str,
        allowances: Decimal | int | str = ZERO,
        resident: bool = True,
        local_service_tax: Decimal | int | str = ZERO,
        date: date | None = None,
    ) -> dict[str, Decimal]:
        gross_dec = _as_decimal(gross, "gross")
        allowances_dec = _as_decimal(allowances, "allowances")
        local_service_tax_dec = _as_decimal(local_service_tax, "local_service_tax")

        if gross_dec < ZERO:
            raise InvalidIncomeError("gross income cannot be negative")
        if allowances_dec < ZERO:
            raise InvalidIncomeError("allowances cannot be negative")
        if local_service_tax_dec < ZERO:
            raise InvalidIncomeError("local_service_tax cannot be negative")

        nssf_employee = (gross_dec * Decimal("0.05")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        nssf_employer = (gross_dec * Decimal("0.10")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

        taxable = max(gross_dec - allowances_dec - nssf_employee - local_service_tax_dec, ZERO)
        paye = PAYE().calculate(
            {
                "gross": taxable,
                "allowances": ZERO,
                "resident": resident,
                "date": date,
            }
        ).tax

        net_pay = (gross_dec - nssf_employee - local_service_tax_dec - paye).quantize(
            MONEY_QUANT, rounding=ROUND_HALF_UP
        )
        return {
            "gross": gross_dec,
            "allowances": allowances_dec,
            "nssf_employee": nssf_employee,
            "nssf_employer": nssf_employer,
            "local_service_tax": local_service_tax_dec,
            "paye": paye,
            "net_pay": net_pay,
        }


class VATCalculator:
    """Support standard-rated, zero-rated, and exempt supplies."""

    def calculate(
        self,
        sales: Iterable[Mapping[str, Any]],
        purchases: Iterable[Mapping[str, Any]] | None = None,
        standard_rate: Decimal | int | str = Decimal("0.18"),
    ) -> dict[str, Decimal]:
        rate = Decimal(str(standard_rate))
        output_vat = ZERO
        input_vat = ZERO

        for sale in sales:
            kind = sale.get("type", "standard")
            amount = _as_decimal(sale.get("amount", ZERO), "sale amount")
            if kind == "standard":
                output_vat += amount * rate
            elif kind not in {"zero", "exempt"}:
                raise ValueError(f"Unsupported VAT type: {kind}")

        for purchase in purchases or []:
            kind = purchase.get("type", "standard")
            amount = _as_decimal(purchase.get("amount", ZERO), "purchase amount")
            if kind == "standard":
                input_vat += amount * rate
            elif kind not in {"zero", "exempt"}:
                raise ValueError(f"Unsupported VAT type: {kind}")

        output_vat = output_vat.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        input_vat = input_vat.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        net_vat = (output_vat - input_vat).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        return {
            "output_vat": output_vat,
            "input_vat": input_vat,
            "net_vat": net_vat,
        }


class CorporateIncomeTax(Tax):
    """Resident company tax at 30% on chargeable income."""

    def calculate(self, ctx: Mapping[str, Any] | TaxContext) -> TaxResult:
        context = ctx if isinstance(ctx, Mapping) else {"revenue": ctx.gross, "allowable_deductions": ctx.allowances}
        revenue = _as_decimal(context.get("revenue", ZERO), "revenue")
        deductions = _as_decimal(context.get("allowable_deductions", ZERO), "allowable_deductions")
        if revenue < ZERO or deductions < ZERO:
            raise InvalidIncomeError("revenue and deductions must be non-negative")
        chargeable = max(revenue - deductions, ZERO)
        tax = (chargeable * Decimal("0.30")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        net = (chargeable - tax).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        return TaxResult(
            tax=tax,
            net=net,
            details={"revenue": revenue, "allowable_deductions": deductions, "chargeable_income": chargeable},
        )


class WithholdingTax(Tax):
    """Simple extension task implementation for withholding tax."""

    def calculate(self, ctx: Mapping[str, Any] | TaxContext) -> TaxResult:
        context = ctx if isinstance(ctx, Mapping) else {"gross": ctx.gross}
        gross = _as_decimal(context.get("gross", ZERO), "gross")
        rate = Decimal(str(context.get("rate", Decimal("0.10"))))
        if gross < ZERO:
            raise InvalidIncomeError("gross income cannot be negative")
        tax = (gross * rate).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        return TaxResult(tax=tax, net=(gross - tax).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP), details={"gross": gross, "rate": rate})


def _build_schedule_for_date(date_value: date | None) -> str:
    if date_value is None:
        return "monthly"
    if date_value.month in {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12}:
        return "monthly"
    raise NoScheduleForDateError(f"No schedule available for date {date_value}")


__all__ = [
    "CorporateIncomeTax",
    "InvalidIncomeError",
    "NoScheduleForDateError",
    "PAYE",
    "PayrollPipeline",
    "Tax",
    "TaxContext",
    "TaxError",
    "TaxResult",
    "UGX",
    "VATCalculator",
    "WithholdingTax",
]
