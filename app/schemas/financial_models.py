
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional, Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator


class StrictModel(BaseModel):
    """Base model that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    @field_validator("*", mode="after")
    @classmethod
    def validate_money(cls, value):
        if isinstance(value, Decimal) and (not value.is_finite() or (cls.__name__ in {"FinancialProfile", "Bill", "SavingsGoal"} and abs(value) > Decimal("1000000000000")) or value != value.quantize(Decimal("0.01"))):
            raise ValueError("Amounts must be finite, at most 1 trillion, and have at most two decimal places.")
        return value


class ExpenseCategory(str, Enum):
    ESSENTIAL = "essential"
    DISCRETIONARY = "discretionary"
    SAVINGS = "savings"
    OTHER = "other"


class BillPriority(str, Enum):
    MANDATORY = "mandatory"
    IMPORTANT = "important"
    FLEXIBLE = "flexible"


class FinancialProfile(StrictModel):
    """A user's financial information for one planning period."""

    currency: Literal["INR"] = "INR"
    monthly_income: Decimal = Field(ge=0)
    opening_balance: Decimal = Field(default=Decimal("0"), ge=0)
    fixed_bills: Decimal = Field(ge=0)
    regular_spending: Decimal = Field(ge=0)
    planned_savings: Decimal = Field(default=Decimal("0"), ge=0)
    unexpected_expenses: Decimal = Field(default=Decimal("0"), ge=0)

    # User-approved maximum spending reduction.
    max_spending_cut: Decimal = Field(default=Decimal("0"), ge=0)

    # Optional minimum balance the plan should preserve.
    minimum_cash_buffer: Decimal = Field(default=Decimal("0"), ge=0)


class Transaction(StrictModel):
    """A positive spending transaction; income and transfers are separate inputs."""
    date: date
    description: str = Field(min_length=1, max_length=300)
    amount: Decimal = Field(gt=0, le=Decimal("1000000000000"))
    category: Literal["essential", "discretionary", "other"] = "other"


class Bill(StrictModel):
    """A bill with a due date and priority."""

    name: str = Field(min_length=1)
    amount: Decimal = Field(ge=0)
    due_date: date = Field(default_factory=date.today)
    priority: BillPriority = BillPriority.MANDATORY
    paid: bool = False

    @field_validator("due_date", mode="before")
    @classmethod
    def default_due_date(cls, v):
        if v is None or v == "":
            return date.today()
        return v

    @field_validator("priority", mode="before")
    @classmethod
    def default_priority(cls, v):
        if v is None or v == "":
            return BillPriority.MANDATORY
        return v

    @field_validator("paid", mode="before")
    @classmethod
    def default_paid(cls, v):
        if v is None or v == "":
            return False
        return bool(v)


class SavingsGoal(StrictModel):
    """A user's savings target."""

    name: str = Field(min_length=1)
    target_amount: Decimal = Field(gt=0)
    current_amount: Decimal = Field(default=Decimal("0"), ge=0)
    monthly_contribution: Decimal = Field(default=Decimal("0"), ge=0)
    target_date: Optional[date] = None

    @field_validator("current_amount", "monthly_contribution", mode="before")
    @classmethod
    def default_goal_amounts(cls, v):
        if v is None or v == "":
            return Decimal("0")
        return v


class BudgetSummary(StrictModel):
    """Deterministic budget calculation results."""

    total_income: Decimal
    total_outflows: Decimal
    projected_closing_balance: Decimal
    shortfall: Decimal
    is_feasible: bool


class BudgetAdjustment(StrictModel):
    """Changes proposed to the original budget."""

    spending_reduction: Decimal = Field(default=Decimal("0"), ge=0)
    savings_reduction: Decimal = Field(default=Decimal("0"), ge=0)
    reserve_used: Decimal = Field(default=Decimal("0"), ge=0)


class PlanningScenario(StrictModel):
    """One candidate plan for handling a financial situation."""

    scenario_id: str
    description: str
    adjustment: BudgetAdjustment
    projected_closing_balance: Decimal
    preserves_minimum_buffer: bool
    mandatory_bills_covered: bool
    tradeoffs: list[str] = Field(default_factory=list)


class VerificationReport(StrictModel):
    """Independent verification of a candidate plan."""

    approved: bool
    checks_passed: list[str] = Field(default_factory=list)
    discrepancies: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PlanningResult(StrictModel):
    """Final result returned by the planning workflow."""

    request_id: str
    status: str
    summary: str
    recommended_scenario: Optional[PlanningScenario] = None
    alternatives: list[PlanningScenario] = Field(default_factory=list)
    verification: Optional[VerificationReport] = None
    assumptions: list[str] = Field(default_factory=list)
