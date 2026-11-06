from django.contrib import admin
from .models import (SchoolClass, Subject, Teacher, TeachingAssignment, Student, Enrollment,
                     Topic, LearningResource, AssessmentComponent, Assessment, Score,
                     TopicScore, Intervention, AnalyticsSetting, AnalysisResult, AuditLog)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "school_class", "roll_no", "academic_year", "is_active")
    list_filter = ("school_class", "academic_year")


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "school_class", "component", "date", "max_marks")
    list_filter = ("school_class", "subject", "component")


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ("student", "assessment", "marks_obtained", "entered_by", "updated_at")
    list_filter = ("assessment__subject", "assessment__school_class")

    def save_model(self, request, obj, form, change):
        if not obj.entered_by_id:
            obj.entered_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "action", "model_name", "object_id")
    readonly_fields = [f.name for f in AuditLog._meta.fields]


for m in (SchoolClass, Subject, Teacher, TeachingAssignment, Student, Topic, LearningResource,
          AssessmentComponent, TopicScore, Intervention, AnalyticsSetting, AnalysisResult):
    admin.site.register(m)