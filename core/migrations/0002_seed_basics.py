from django.db import migrations


def seed(apps, schema_editor):
    Component = apps.get_model("core", "AssessmentComponent")
    Subject = apps.get_model("core", "Subject")
    Setting = apps.get_model("core", "AnalyticsSetting")
    rows = [
        ("Participation", 4, False),
        ("Project Work", 6, False),
        ("Terminal Performance", 12, True),
        ("Behavioral Change", 3, False),
    ]
    for name, max_marks, traj in rows:
        Component.objects.get_or_create(
            name=name, defaults={"cdc_max_marks": max_marks, "used_for_trajectory": traj})
    for name in ("Mathematics", "Science"):
        Subject.objects.get_or_create(name=name)
    Setting.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]