"""Domain models. Initial migration applied; see docs/domain-design.md."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class ImportedModel(models.Model):
    legacy_id = models.PositiveIntegerField(null=True, blank=True, unique=True)

    class Meta:
        abstract = True


class NamedReference(ImportedModel):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class Department(NamedReference):
    name_genitive = models.CharField(max_length=100, blank=True)


class EmployeeCategory(NamedReference):
    pass


class Speciality(NamedReference):
    pass


class Position(NamedReference):
    name_genitive = models.CharField(max_length=100, blank=True)


class TravelReason(NamedReference):
    pass


class Employee(ImportedModel):
    # Authentication is independent of the employee register.
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=20, blank=True)
    first_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    display_name = models.CharField(max_length=150)
    name_genitive = models.CharField(max_length=150, blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True)
    speciality = models.ForeignKey(Speciality, on_delete=models.PROTECT, null=True, blank=True)
    position = models.ForeignKey(Position, on_delete=models.PROTECT, null=True, blank=True)
    email = models.EmailField(blank=True)
    iban = models.CharField(max_length=50, blank=True)
    car_plate = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.display_name


class EmployeeCategoryHistory(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="category_history")
    category = models.ForeignKey(EmployeeCategory, on_delete=models.PROTECT)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    def clean(self):
        super().clean()
        if self.valid_to and self.valid_from and self.valid_to < self.valid_from:
            raise ValidationError({"valid_to": "End date precedes start date."})
        if self.employee_id and self.valid_from:
            overlaps = type(self).objects.filter(employee_id=self.employee_id).exclude(pk=self.pk)
            overlaps = overlaps.filter(models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=self.valid_from))
            if self.valid_to:
                overlaps = overlaps.filter(valid_from__lte=self.valid_to)
            if overlaps.exists():
                raise ValidationError("Employee category intervals must not overlap.")

    class Meta:
        constraints = [models.CheckConstraint(
            condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=models.F("valid_from")),
            name="employee_category_valid_dates",
        )]
        ordering = ["valid_from"]


class TransportMode(NamedReference):
    code = models.CharField(max_length=20)
    has_mileage_cost = models.BooleanField(default=False)
    has_ticket_cost = models.BooleanField(default=False)


class AccommodationType(NamedReference):
    code = models.CharField(max_length=20)
    has_cost = models.BooleanField(default=True)
    requires_declaration = models.BooleanField(default=False)


def money(**kwargs):
    return models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)], **kwargs)


def distance(**kwargs):
    return models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)], **kwargs)


class Route(NamedReference):
    short_description = models.CharField(max_length=100, blank=True)
    origin = models.CharField(max_length=100)
    destination = models.CharField(max_length=150)
    distance_km = distance(default=0)
    is_abroad = models.BooleanField(default=False)
    has_daily_allowance = models.BooleanField(default=True)
    # Destination attributes are NOT single flags here: legacy stores per-stop lists.
    requires_review = models.BooleanField(default=False)
    notes = models.TextField(blank=True)


class RouteStop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    sequence = models.PositiveSmallIntegerField()
    city = models.CharField(max_length=100)
    is_abroad = models.BooleanField(default=False)
    is_expensive = models.BooleanField(default=False)
    is_island = models.BooleanField(default=False)
    compensation_band = models.PositiveSmallIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["route", "sequence"], name="unique_route_stop")]
        ordering = ["sequence"]


class EffectiveRate(ImportedModel):
    valid_from = models.DateField()
    valid_to = models.DateField()

    class Meta:
        abstract = True
        constraints = [models.CheckConstraint(condition=models.Q(valid_to__gte=models.F("valid_from")), name="%(class)s_valid_dates")]


class DailyAllowanceRate(EffectiveRate):
    category = models.ForeignKey(EmployeeCategory, on_delete=models.PROTECT)
    is_abroad = models.BooleanField(default=False)
    without_overnight = money()
    band_1 = money()
    band_2 = money()
    band_3 = money()


class AccommodationRate(EffectiveRate):
    category = models.ForeignKey(EmployeeCategory, on_delete=models.PROTECT)
    is_abroad = models.BooleanField(default=False)
    minimum_distance_km = distance()
    standard_limit = money()
    expensive_city_limit = money()
    island_limit = money()


class MileageRate(EffectiveRate):
    amount_per_km = models.DecimalField(max_digits=8, decimal_places=4, validators=[MinValueValidator(0)])


class TravelStatus(NamedReference):
    # Keep legacy statuses until transitions are fully mapped.
    pass


class Travel(ImportedModel):
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="travels")
    route = models.ForeignKey(Route, on_delete=models.PROTECT, related_name="travels")
    applied_category = models.ForeignKey(EmployeeCategory, on_delete=models.PROTECT, null=True, blank=True)
    category_review_required = models.BooleanField(default=False)
    number = models.CharField(max_length=30, blank=True)
    status = models.ForeignKey(TravelStatus, on_delete=models.PROTECT)
    reason = models.ForeignKey(TravelReason, on_delete=models.PROTECT, null=True, blank=True)
    purpose = models.TextField(blank=True)
    actions_description = models.TextField(blank=True)
    departure_at = models.DateField()
    return_at = models.DateField()
    work_starts_at = models.DateField()
    work_ends_at = models.DateField()
    protocol_number = models.CharField(max_length=50, blank=True)
    protocol_date = models.DateField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    mileage_override = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True, validators=[MinValueValidator(0)])
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(return_at__gte=models.F("departure_at")), name="travel_date_order"),
            models.CheckConstraint(condition=models.Q(work_ends_at__gte=models.F("work_starts_at")), name="travel_work_date_order"),
        ]


class TravelExpense(ImportedModel):
    class Kind(models.TextChoices):
        TICKET = "ticket", "Ticket"
        MILEAGE = "mileage", "Mileage"
        OTHER = "other", "Other"

    travel = models.ForeignKey(Travel, on_delete=models.CASCADE, related_name="expenses")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    transport = models.ForeignKey(TransportMode, on_delete=models.PROTECT, null=True, blank=True)
    description = models.CharField(max_length=200, blank=True)
    estimated_amount = money(null=True, blank=True)
    estimated_transfer_cost = money(null=True, blank=True)
    actual_amount = money(null=True, blank=True)
    estimated_distance_km = distance(null=True, blank=True)
    actual_distance_km = distance(null=True, blank=True)
    applied_mileage_rate = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True, validators=[MinValueValidator(0)])
    receipt_reference = models.CharField(max_length=100, blank=True)
    is_cancelled = models.BooleanField(default=False)
    notes = models.TextField(blank=True)


class AccommodationReceipt(models.Model):
    class Breakdown(models.TextChoices):
        TOTAL = "total", "Total for covered nights"
        PER_NIGHT = "per_night", "Itemized per night"

    travel = models.ForeignKey(Travel, on_delete=models.PROTECT, related_name="accommodation_receipts")
    reference = models.CharField(max_length=100, blank=True)
    issued_on = models.DateField(null=True, blank=True)
    breakdown = models.CharField(max_length=12, choices=Breakdown.choices)
    claimed_amount = money()
    allowed_amount = money(null=True, blank=True)
    deduction_reason = models.TextField(blank=True)


class OvernightStay(ImportedModel):
    travel = models.ForeignKey(Travel, on_delete=models.CASCADE, related_name="overnights")
    date = models.DateField()
    stop = models.ForeignKey(RouteStop, on_delete=models.PROTECT)
    receipt = models.ForeignKey(AccommodationReceipt, on_delete=models.PROTECT, null=True, blank=True, related_name="nights")
    accommodation_type = models.ForeignKey(AccommodationType, on_delete=models.PROTECT)
    city = models.CharField(max_length=100)
    is_abroad = models.BooleanField(default=False)
    is_expensive = models.BooleanField(default=False)
    is_island = models.BooleanField(default=False)
    compensation_band = models.PositiveSmallIntegerField(default=1)
    estimated_cost = money(null=True, blank=True)
    actual_cost = money(null=True, blank=True)
    applied_limit = money(null=True, blank=True)

    def clean(self):
        super().clean()
        if self.travel_id and self.stop_id and self.stop.route_id != self.travel.route_id:
            raise ValidationError({"stop": "Select a stop belonging to the travel route."})
        if self.receipt_id and self.travel_id and self.receipt.travel_id != self.travel_id:
            raise ValidationError({"receipt": "Receipt belongs to another travel."})


class CalculationSnapshot(models.Model):
    class Stage(models.TextChoices):
        ESTIMATE = "estimate", "Estimate"
        ACTUAL = "actual", "Actual"

    travel = models.ForeignKey(Travel, on_delete=models.PROTECT, related_name="calculations")
    stage = models.CharField(max_length=10, choices=Stage.choices)
    revision = models.PositiveIntegerField()
    calculated_at = models.DateTimeField(auto_now_add=True)
    calculated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    algorithm_version = models.CharField(max_length=30)
    # Preserve employee/category, rates, input lines and rounding decisions.
    inputs = models.JSONField()
    daily_domestic = money()
    daily_abroad = money()
    mileage = money()
    tickets = money()
    other = money()
    claimed_accommodation = money()
    allowed_accommodation = money()
    total = money()
    document_budget = money(null=True, blank=True)
    frozen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["travel", "stage", "revision"], name="unique_calculation_revision")]


class SettlementPeriod(models.Model):
    name = models.CharField(max_length=100)
    starts_on = models.DateField()
    ends_on = models.DateField()
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(ends_on__gte=models.F("starts_on")), name="settlement_date_order")]


class SettlementItem(models.Model):
    period = models.ForeignKey(SettlementPeriod, on_delete=models.PROTECT, related_name="items")
    calculation = models.OneToOneField(CalculationSnapshot, on_delete=models.PROTECT, related_name="settlement_item")

    def clean(self):
        super().clean()
        if self.period_id and self.period.closed_at:
            raise ValidationError("Closed settlement periods cannot be edited.")
        if self.calculation_id:
            if self.calculation.stage != CalculationSnapshot.Stage.ACTUAL or not self.calculation.frozen_at:
                raise ValidationError("Settlement requires a frozen actual calculation.")


class TravelAttachment(models.Model):
    travel = models.ForeignKey(Travel, on_delete=models.CASCADE, related_name="attachments")
    original_name = models.CharField(max_length=255)
    file = models.FileField(upload_to="travel_attachments/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)


class UserAccess(models.Model):
    class Scope(models.TextChoices):
        OWN = "own", "Ίδιες μετακινήσεις"
        DEPARTMENT = "department", "Επιλεγμένες μονάδες"
        ALL = "all", "Όλες οι μονάδες"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="travel_access")
    scope = models.CharField(max_length=12, choices=Scope.choices, default=Scope.OWN)
    departments = models.ManyToManyField(Department, blank=True)
