from datetime import datetime, time, timezone as dt_timezone
from zoneinfo import ZoneInfo
from django.db import migrations, models

FIELDS = ("departure_at", "return_at", "work_starts_at", "work_ends_at")


def preserve_local_dates(apps, schema_editor):
    Travel = apps.get_model("core", "Travel")
    alias = schema_editor.connection.alias
    for travel in Travel.objects.using(alias).all().iterator():
        values = {}
        for name in FIELDS:
            value = getattr(travel, name)
            if value.tzinfo is None:
                value = value.replace(tzinfo=dt_timezone.utc)
            local_date = value.astimezone(ZoneInfo("Europe/Athens")).date()
            # SQL cast to DATE must preserve the Athens day, including UTC day boundaries.
            values[name] = datetime.combine(local_date, time.min, tzinfo=dt_timezone.utc)
        Travel.objects.using(alias).filter(pk=travel.pk).update(**values)


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [
        migrations.RemoveConstraint(model_name="travel", name="travel_date_order"),
        migrations.RemoveConstraint(model_name="travel", name="travel_work_date_order"),
        migrations.RunPython(preserve_local_dates, migrations.RunPython.noop),
        *[migrations.AlterField(model_name="travel", name=name, field=models.DateField()) for name in FIELDS],
        migrations.AddConstraint(model_name="travel", constraint=models.CheckConstraint(condition=models.Q(return_at__gte=models.F("departure_at")), name="travel_date_order")),
        migrations.AddConstraint(model_name="travel", constraint=models.CheckConstraint(condition=models.Q(work_ends_at__gte=models.F("work_starts_at")), name="travel_work_date_order")),
    ]
