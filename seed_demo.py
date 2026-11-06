"""Creates synthetic (fake) test data in a demo class, Grade 9-D, for testing the analytics.

Run from the project folder:   python seed_demo.py
Safe to run again: it deletes and recreates only the demo class's data.
"""
import os
from datetime import date, timedelta

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from core.models import (Assessment, AssessmentComponent, Enrollment, Intervention,  # noqa: E402
                         SchoolClass, Score, Student, Subject, Topic, TopicScore)

# (name, pattern, overall % in each unit test, index of weak topic or None)
STUDENTS = [
    ("Demo Student 01", "Steady high",                 [78, 80, 76, 79, 81, 80], None),
    ("Demo Student 02", "Improving",                   [45, 48, 52, 57, 61, 66], None),
    ("Demo Student 03", "Declining",                   [82, 78, 73, 67, 60, 52], 0),
    ("Demo Student 04", "Persistently low (flat)",     [31, 33, 29, 32, 30, 31], 1),
    ("Demo Student 05", "One bad day, then recovers",  [70, 72, 71, 73, 40, 72], None),
    ("Demo Student 06", "Insufficient data (3 tests)", [62, 60, 64],             None),
    ("Demo Student 07", "Declined, then intervention", [72, 66, 58, 50, 58, 67], 2),
    ("Demo Student 08", "Stable middle",               [55, 57, 54, 56, 55, 56], None),
]
TOPICS = [("Algebra", 8), ("Fractions and Ratio", 6), ("Geometry", 6)]   # topic, marks (total 20)
FIRST_TEST = date(2026, 9, 7)
FULL_MARKS = 20


def half(x):
    return round(x * 2) / 2


school_class, _ = SchoolClass.objects.get_or_create(grade=9, section="D")
maths = Subject.objects.get(name="Mathematics")
component = AssessmentComponent.objects.get(name="Terminal Performance")

# clear the old demo data
Student.objects.filter(enrollments__school_class=school_class).delete()
Assessment.objects.filter(school_class=school_class).delete()

topics = []
for name, _marks in TOPICS:
    topic, _ = Topic.objects.get_or_create(subject=maths, grade=9, name=name)
    topics.append(topic)

n_tests = max(len(s[2]) for s in STUDENTS)
assessments = []
for i in range(n_tests):
    a = Assessment.objects.create(
        school_class=school_class, subject=maths, component=component,
        name=f"Unit Test {i + 1}", date=FIRST_TEST + timedelta(days=7 * i), max_marks=FULL_MARKS)
    a.topics.set(topics)
    assessments.append(a)

students = {}
for roll, (name, pattern, percents, weak) in enumerate(STUDENTS, start=1):
    student = Student.objects.create(full_name=name)
    Enrollment.objects.create(student=student, school_class=school_class, roll_no=roll)
    students[name] = student
    for assessment, pct in zip(assessments, percents):
        marks = []
        for t_index, (_tname, t_max) in enumerate(TOPICS):
            if weak is None:
                t_pct = pct
            elif t_index == weak:
                t_pct = max(0, pct - 15)
            else:
                t_pct = min(100, pct + 7)
            marks.append(min(t_max, half(t_max * t_pct / 100)))
        score = Score.objects.create(student=student, assessment=assessment, marks_obtained=sum(marks))
        for topic, (_tname, t_max), m in zip(topics, TOPICS, marks):
            TopicScore.objects.create(score=score, topic=topic, marks_obtained=m, max_marks=t_max)

# Student 07 had an extra class (geometry) after the 4th test
Intervention.objects.create(
    student=students["Demo Student 07"], subject=maths, topic=topics[2],
    intervention_type="Extra class", start_date=date(2026, 10, 1), status="Ongoing",
    notes="Synthetic example: extra geometry class after Unit Test 4.")

print("Demo data created in", school_class)
print(f"{'Student':16} {'Pattern':30} Overall % per test")
for name, pattern, percents, _ in STUDENTS:
    print(f"{name:16} {pattern:30} {percents}")
print("Students:", Student.objects.filter(enrollments__school_class=school_class).count(),
      "| Assessments:", Assessment.objects.filter(school_class=school_class).count(),
      "| Scores:", Score.objects.filter(assessment__school_class=school_class).count())