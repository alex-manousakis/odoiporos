# Estimate calculation v1

Entry: POST travels/<id>/calculate/. Requires visibility, change permission, a new/unapproved travel and no frozen calculation. Saves a new estimate revision, not an approval or actual settlement.

Ported rules: TravelP.pas calculateOutandOvernightDays, getDailyCompensation, getOvernightBudget, getKMAllowance; approval budget uplift/ceiling/minimum.

Days start at work start, with at most one previous departure day; work end is inclusive. A same-day allowance uses without_overnight except when returning after work end. Allowance requires route distance strictly greater than home limit. Mileage is rounded per expense using Decimal half-even and effective mileage rate or travel override. Ticket airport transfers are included in other expenses.

Estimate accommodation uses a per-night cap, matching the agreed daily itemized estimate. Actual receipt pooling and itemized settlement are separate and not implemented here. Friends accommodation contributes zero. Excluded nights are absent from the estimate.

Missing/overlapping rates, missing category coverage, review-flagged routes and mixed destination bands/territories block computation with a visible error. Mixed itineraries need an agreed allocation of days; the old last-route behavior is not copied.

Input amounts, rate records and relevant parameters are saved in the snapshot. Fingerprints detect later changes; old revisions are retained and shown as stale. Changing an unrelated rate may conservatively mark an estimate stale.

Validation: controlled domestic/foreign cases, same-day allowance, mileage, transfer costs, hotel caps, budget adjustment, missing/overlapping rates and authorization. Historical end-to-end agreement against printed Delphi examples remains to be checked before using amounts for official approvals or payments. This implementation does not claim to validate legislation.
