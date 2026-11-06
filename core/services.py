"""Connects the database to the analytics module (core/analytics.py)."""
from statistics import mean

from . import analytics
from .models import (AnalysisResult, AnalyticsSetting, Assessment, Enrollment,
                     Score, TopicScore)


def trajectory_scores(student, subject):
    """A student's scores for the trend: unit tests and terminal exams only, oldest first."""
    return list(
        Score.objects.filter(student=student, assessment__subject=subject,
                             assessment__component__used_for_trajectory=True)
        .select_related("assessment").order_by("assessment__date", "assessment_id"))


def refresh_analysis(school_class, subject):
    """Re-run the analysis for every active student in a class and save the results."""
    setting = AnalyticsSetting.load()
    rows = []
    enrollments = Enrollment.objects.filter(school_class=school_class, is_active=True)
    for enrollment in enrollments.select_related("student"):
        student = enrollment.student
        values = [s.percentage for s in trajectory_scores(student, subject)]
        result = analytics.classify_with_settings(values, setting)
        obj, _ = AnalysisResult.objects.update_or_create(
            student=student, subject=subject,
            defaults={"n_assessments": result["n"], "slope": result["slope"],
                      "ewma_previous": result["ewma_previous"],
                      "latest_percent": result["latest"], "status": result["status"]})
        rows.append((obj, result))
    return rows


def weak_topics(student, subject, last_n=3, threshold=50.0):
    """Topics where the student's average over their last few tests is below the threshold."""
    recent = [s.id for s in trajectory_scores(student, subject)][-last_n:]
    per_topic = {}
    for ts in TopicScore.objects.filter(score_id__in=recent).select_related("topic"):
        per_topic.setdefault(ts.topic, []).append(ts.percentage)
    averages = [(topic, mean(p)) for topic, p in per_topic.items()]
    return sorted([a for a in averages if a[1] < threshold], key=lambda a: a[1])


def intervention_recovery(intervention):
    """Class-adjusted recovery for one intervention (see analytics.recovery)."""
    setting = AnalyticsSetting.load()
    enrollment = (Enrollment.objects.filter(student=intervention.student, is_active=True)
                  .select_related("school_class").first())
    if enrollment is None:
        return {"ready": False, "message": "The student has no active class."}
    assessments = list(
        Assessment.objects.filter(school_class=enrollment.school_class,
                                  subject=intervention.subject,
                                  component__used_for_trajectory=True).order_by("date", "id"))
    mine, class_means, start_index = [], [], 0
    for a in assessments:
        own = Score.objects.filter(student=intervention.student, assessment=a).first()
        if own is None:
            continue
        mine.append(own.percentage)
        class_means.append(mean(s.percentage for s in Score.objects.filter(assessment=a)))
        if a.date < intervention.start_date:
            start_index = len(mine)          # assessments before the start date
    return analytics.recovery(mine, class_means, start_index, setting.recovery_window)