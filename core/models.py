from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


# ---------- People and classes ----------

class SchoolClass(models.Model):
    grade = models.PositiveSmallIntegerField(choices=[(9, "Grade 9"), (10, "Grade 10")])
    section = models.CharField(max_length=2)

    class Meta:
        unique_together = ("grade", "section")
        ordering = ["grade", "section"]
        verbose_name_plural = "School classes"

    def __str__(self):
        return f"Grade {self.grade}-{self.section}"


class Subject(models.Model):
    name = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Teacher(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)

    def __str__(self):
        return self.full_name


class TeachingAssignment(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("teacher", "school_class", "subject")

    def __str__(self):
        return f"{self.teacher} - {self.subject} - {self.school_class}"


class Student(models.Model):
    full_name = models.CharField(max_length=100)

    def __str__(self):
        return self.full_name


class Enrollment(models.Model):
    """Which class a student belongs to in a given academic year."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="enrollments")
    school_class = models.ForeignKey(SchoolClass, on_delete=models.PROTECT, related_name="enrollments")
    academic_year = models.CharField(max_length=9, default="2083", help_text="Academic year in BS, e.g. 2083")
    roll_no = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("school_class", "academic_year", "roll_no"), ("student", "academic_year")]
        ordering = ["school_class", "roll_no"]

    def __str__(self):
        return f"{self.student.full_name} - {self.school_class} (roll {self.roll_no})"


# ---------- Curriculum ----------

class Topic(models.Model):
    """A textbook unit or chapter, e.g. 'Unit 3: Algebra'."""
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="topics")
    grade = models.PositiveSmallIntegerField(choices=[(9, "Grade 9"), (10, "Grade 10")])
    name = models.CharField(max_length=120)

    class Meta:
        unique_together = ("subject", "grade", "name")
        ordering = ["subject", "grade", "name"]

    def __str__(self):
        return f"{self.name} ({self.subject}, Grade {self.grade})"


class LearningResource(models.Model):
    TYPES = [("Video", "Video"), ("PDF", "PDF"), ("Link", "Link")]
    title = models.CharField(max_length=200)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="resources")
    resource_type = models.CharField(max_length=10, choices=TYPES)
    url = models.URLField(blank=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.title


# ---------- Assessment data ----------

class AssessmentComponent(models.Model):
    """The four CDC internal-assessment components (25 marks in total)."""
    name = models.CharField(max_length=60, unique=True)
    cdc_max_marks = models.PositiveSmallIntegerField()
    used_for_trajectory = models.BooleanField(
        default=False,
        help_text="True only for repeated achievement measures (unit tests, terminal exams). "
                  "Participation and behavior are reported separately.")

    def __str__(self):
        return f"{self.name} (max {self.cdc_max_marks})"


class Assessment(models.Model):
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    component = models.ForeignKey(AssessmentComponent, on_delete=models.PROTECT)
    name = models.CharField(max_length=100, help_text="e.g. Unit Test 2")
    date = models.DateField()
    max_marks = models.FloatField(validators=[MinValueValidator(1)], help_text="Full marks of this assessment")
    topics = models.ManyToManyField(Topic, blank=True, help_text="Units or chapters covered")

    class Meta:
        ordering = ["school_class", "subject", "date"]

    def __str__(self):
        return f"{self.name} - {self.subject} - {self.school_class} ({self.date})"


class Score(models.Model):
    """One student's marks in one assessment. Percentage is calculated, never typed."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="scores")
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="scores")
    marks_obtained = models.FloatField(validators=[MinValueValidator(0)])
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "assessment")

    def clean(self):
        if self.assessment_id and self.marks_obtained is not None \
                and self.marks_obtained > self.assessment.max_marks:
            raise ValidationError(f"Marks cannot be more than {self.assessment.max_marks}.")

    @property
    def percentage(self):
        return self.marks_obtained / self.assessment.max_marks * 100

    def __str__(self):
        return f"{self.student.full_name}: {self.marks_obtained}/{self.assessment.max_marks}"


class TopicScore(models.Model):
    """Marks a student earned on one topic inside an assessment (used to find weak topics)."""
    score = models.ForeignKey(Score, on_delete=models.CASCADE, related_name="topic_scores")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    marks_obtained = models.FloatField(validators=[MinValueValidator(0)])
    max_marks = models.FloatField(validators=[MinValueValidator(0.5)])

    class Meta:
        unique_together = ("score", "topic")

    def clean(self):
        if self.marks_obtained is not None and self.max_marks is not None \
                and self.marks_obtained > self.max_marks:
            raise ValidationError("Topic marks cannot be more than the topic's full marks.")

    @property
    def percentage(self):
        return self.marks_obtained / self.max_marks * 100

    def __str__(self):
        return f"{self.score.student.full_name} - {self.topic.name}: {self.percentage:.0f}%"


# ---------- Support actions and analysis ----------

class Intervention(models.Model):
    TYPES = [
        ("Extra class", "Extra class"),
        ("Worksheet", "Worksheet"),
        ("Peer tutoring", "Peer tutoring"),
        ("Parent meeting", "Parent meeting"),
    ]
    STATUS = [("Ongoing", "Ongoing"), ("Completed", "Completed")]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="interventions")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True)
    intervention_type = models.CharField(max_length=20, choices=TYPES)
    start_date = models.DateField(help_text="Assessments on or after this date count as 'after'")
    review_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default="Ongoing")
    notes = models.TextField(blank=True)
    resources = models.ManyToManyField(LearningResource, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.full_name} - {self.intervention_type}"


class AnalyticsSetting(models.Model):
    """One row of adjustable thresholds for the analytics (editable in the admin panel)."""
    ewma_alpha = models.FloatField(default=0.3, help_text="EWMA smoothing factor")
    min_assessments = models.PositiveSmallIntegerField(default=4, help_text="Below this: 'Insufficient data'")
    slope_tolerance = models.FloatField(default=1.0, help_text="Percentage points per assessment")
    baseline_margin = models.FloatField(default=3.0, help_text="Points the latest score must be below the previous EWMA")
    low_score_threshold = models.FloatField(default=40.0, help_text="Percent below which a flat record is 'Persistently low'")
    recovery_window = models.PositiveSmallIntegerField(default=2, help_text="Assessments counted before and after an intervention")

    class Meta:
        verbose_name = "Analytics setting"
        verbose_name_plural = "Analytics settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Analytics settings"


class AnalysisResult(models.Model):
    """Latest analysis for one student in one subject."""
    STATUS = [
        ("INSUFFICIENT", "Insufficient data"),
        ("STABLE", "Stable"),
        ("NEEDS_ATTENTION", "Needs attention"),
        ("PERSISTENTLY_LOW", "Persistently low"),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="analyses")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    n_assessments = models.PositiveSmallIntegerField()
    slope = models.FloatField(null=True, blank=True, help_text="Theil-Sen slope, percentage points per assessment")
    ewma_previous = models.FloatField(null=True, blank=True, help_text="EWMA before the latest score")
    latest_percent = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "subject")

    def __str__(self):
        return f"{self.student.full_name} - {self.subject}: {self.get_status_display()}"


class AuditLog(models.Model):
    """Who changed what, and when (for marks and interventions)."""
    ACTIONS = [("CREATE", "Create"), ("UPDATE", "Update"), ("DELETE", "Delete")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=10, choices=ACTIONS)
    model_name = models.CharField(max_length=60)
    object_id = models.CharField(max_length=40)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.action} {self.model_name} #{self.object_id}"