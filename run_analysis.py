"""Runs the analysis for the demo class (Grade 9-D, Mathematics) and prints the results.

Run from the project folder:   python run_analysis.py
"""
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from core.models import Intervention, SchoolClass, Subject  # noqa: E402
from core import services  # noqa: E402

school_class = SchoolClass.objects.get(grade=9, section="D")
maths = Subject.objects.get(name="Mathematics")

print(f"ANALYSIS: {school_class} - {maths}\n")
for obj, result in services.refresh_analysis(school_class, maths):
    slope = "-" if obj.slope is None else f"{obj.slope:+.1f}"
    print(f"{obj.student.full_name:16} {obj.get_status_display():18} slope {slope:>6}  tests {obj.n_assessments}")
    print(f"    {result['reason']}")
    weak = services.weak_topics(obj.student, maths) if obj.n_assessments else []
    if weak and obj.status != "STABLE":
        print("    Weak topics:", ", ".join(f"{t.name} ({p:.0f}%)" for t, p in weak))

print("\nINTERVENTIONS")
for iv in Intervention.objects.filter(student__enrollments__school_class=school_class):
    r = services.intervention_recovery(iv)
    if r["ready"]:
        print(f"{iv.student.full_name}: before {r['pre']:.1f}% -> after {r['post']:.1f}% "
              f"(change {r['change']:+.1f}, class change {r['class_change']:+.1f}, "
              f"adjusted {r['adjusted']:+.1f})")
        print("    " + r["label"])
    else:
        print(f"{iv.student.full_name}: {r['message']}")