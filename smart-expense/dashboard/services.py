from decimal import Decimal

from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce

from budgets.models import Budget
from categories.models import Category
from transactions.models import Transaction
from transactions.services import totals

MONEY_FIELD = DecimalField(max_digits=12, decimal_places=2)



MONEY_FIELD = DecimalField(max_digits=12, decimal_places=2)


def get_dashboard_data(user):
    """
    Build the financial summary, latest transactions and budget indicators
    for one authenticated user.
    """

    # Restrict every transaction query to the authenticated user.
    transactions = (
        Transaction.objects.filter(owner=user)
        .select_related("category")
    )

    # Calculate all-time income, expenses and balance.
    financial_summary = totals(transactions)

    # Aggregate budget spending in one database query instead of
    # calculating spent separately for every budget.
    budgets = (
        Budget.objects.filter(owner=user)
        .select_related("category")
        .annotate(
            dashboard_spent=Coalesce(
                Sum(
                    "category__transactions__amount",
                    filter=Q(
                        category__transactions__owner=user,
                        category__transactions__kind=Category.EXPENSE,
                        category__transactions__date__gte=F("start_date"),
                        category__transactions__date__lte=F("end_date"),
                    ),
                ),
                Value(Decimal("0.00"), output_field=MONEY_FIELD),
                output_field=MONEY_FIELD,
            )
        )
    )

    budget_summaries = []

    for budget in budgets:
        spent = budget.dashboard_spent

        # Calculate the displayed progress percentage.
        progress = (
            spent / budget.limit * Decimal("100")
        ).quantize(Decimal("0.1"))

        # Determine budget status using the exact spending amount.
        if spent > budget.limit:
            status = "Exceeded"
        elif (
            spent * Decimal("100")
            >= budget.limit * Decimal(budget.threshold)
        ):
            status = "Warning"
        else:
            status = "On track"

        budget_summaries.append(
            {
                "category": budget.category.name,
                "start_date": budget.start_date,
                "end_date": budget.end_date,
                "spent": spent,
                "limit": budget.limit,
                "threshold": budget.threshold,
                "progress": progress,
                "progress_bar": min(
                    progress,
                    Decimal("100"),
                ),
                "status": status,
            }
        )

    return {
        **financial_summary,
        "recent": transactions[:10],
        "budgets": budget_summaries,
    }

