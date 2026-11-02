"""Receipt-level reimbursement; amounts in the application's base currency."""
from decimal import Decimal, ROUND_HALF_EVEN


def reimbursable_amount(*, breakdown, claimed_amount, nightly_limits, nightly_costs=None):
    def amount(value):
        if isinstance(value, float):
            raise ValueError("Use Decimal or decimal strings, not floats.")
        value = Decimal(value)
        if not value.is_finite() or value < 0 or value != value.quantize(Decimal("0.01")):
            raise ValueError("Amounts must be nonnegative finite amounts with at most two decimal places.")
        return value

    claimed = amount(claimed_amount)
    limits = [amount(v) for v in nightly_limits]
    if not limits:
        raise ValueError("A receipt must cover at least one night.")
    if breakdown == "total":
        allowed = min(claimed, sum(limits, Decimal("0")))
    elif breakdown == "per_night":
        if nightly_costs is None:
            raise ValueError("Itemized receipt requires nightly costs.")
        costs = [amount(v) for v in nightly_costs]
        if len(costs) != len(limits) or sum(costs, Decimal("0")) != claimed:
            raise ValueError("Nightly costs must match covered nights and receipt total.")
        allowed = sum((min(cost, limit) for cost, limit in zip(costs, limits)), Decimal("0"))
    else:
        raise ValueError("Unknown receipt breakdown.")
    return allowed.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
