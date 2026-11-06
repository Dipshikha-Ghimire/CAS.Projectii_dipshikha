from statistics import mean

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from . import services
from .models import Assessment, Intervention, Score, SchoolClass, Subject

# status code -> (colour name used by the page, sort order: most important first)
STATUS_STYLE = {
    "NEEDS_ATTENTION": ("red", 0),
    "PERSISTENTLY_LOW": ("amber", 1),
    "INSUFFICIENT": ("gray", 2),
    "STABLE": ("green", 3),
}


def _class_average_chart(school_class, subject):
    """Points for a simple line chart of the class average (%) over the assessments."""
    assessments = (Assessment.objects
                   .filter(school_class=school_class, subject=subject,
                           component__used_for_trajectory=True)
                   .order_by("date", "id"))
    means = []
    for a in assessments:
        percentages = [s.percentage for s in Score.objects.filter(assessment=a).select_related("assessment")]
        if percentages:
            means.append((a.name, mean(percentages)))
    if not means:
        return None
    w, h, left, right, top, bottom = 560, 220, 40, 20, 15, 40
    n = len(means)

    def x(i):
        return left + (w - left - right) * (i / (n - 1) if n > 1 else 0.5)

    def y(v):
        return top + (h - top - bottom) * (1 - v / 100)

    points = [{"x": round(x(i), 1), "y": round(y(v), 1), "label": name, "value": round(v)}
              for i, (name, v) in enumerate(means)]
    return {
        "w": w, "h": h, "left": left, "right": w - right, "label_y": h - 15,
        "points": points,
        "polyline": " ".join(f"{p['x']},{p['y']}" for p in points),
        "grid": [{"y": round(y(g), 1), "label": g} for g in (0, 25, 50, 75, 100)],
    }


@login_required
def dashboard(request):
    # Flags are for teachers only (ethics: the students are minors)
    if not (request.user.is_superuser or hasattr(request.user, "teacher")):
        raise PermissionDenied

    classes = SchoolClass.objects.filter(enrollments__isnull=False).distinct()
    subjects = Subject.objects.all()
    selected_class = classes.filter(pk=request.GET.get("class")).first() or classes.first()
    selected_subject = subjects.filter(pk=request.GET.get("subject")).first() or subjects.first()
    context = {"classes": classes, "subjects": subjects,
               "selected_class": selected_class, "selected_subject": selected_subject}
    if selected_class is None or selected_subject is None:
        return render(request, "core/dashboard.html", context)

    rows = []
    for obj, result in services.refresh_analysis(selected_class, selected_subject):
        colour, order = STATUS_STYLE[obj.status]
        weak = []
        if obj.status in ("NEEDS_ATTENTION", "PERSISTENTLY_LOW"):
            weak = [f"{t.name} ({p:.0f}%)" for t, p in services.weak_topics(obj.student, selected_subject)]
        rows.append({
            "name": obj.student.full_name, "status": obj.get_status_display(), "colour": colour,
            "order": order, "latest": obj.latest_percent, "slope": obj.slope,
            "n": obj.n_assessments, "reason": result["reason"], "weak": ", ".join(weak),
        })
    rows.sort(key=lambda r: (r["order"], r["name"]))

    count = lambda status: sum(1 for r in rows if r["status"] == status)
    context.update({
        "rows": rows,
        "attention_rows": [r for r in rows if r["order"] <= 1],
        "total": len(rows),
        "needs_attention": count("Needs attention"),
        "persistently_low": count("Persistently low"),
        "insufficient": count("Insufficient data"),
        "ongoing": Intervention.objects.filter(
            student__enrollments__school_class=selected_class,
            subject=selected_subject, status="Ongoing").count(),
        "chart": _class_average_chart(selected_class, selected_subject),
    })
    return render(request, "core/dashboard.html", context)
