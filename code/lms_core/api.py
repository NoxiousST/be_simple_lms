# lms_core/api.py
from typing import List

from django.contrib.auth import get_user
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError
from django.db.models.signals import post_save
from django.dispatch import receiver
from ninja import NinjaAPI, UploadedFile, File, Form, Router
from ninja.errors import HttpError
from ninja.responses import Response
from lms_core.schema import (
    CourseSchemaOut, CourseMemberOut, CourseSchemaIn, RegisterSchemaIn,
    CourseContentMini, CourseContentFull, CourseCommentOut, CourseCommentIn, BatchEnrollSchema, CommentModerationIn,
    UserActivityOut, CourseAnalyticsOut, UserProfileIn, UserProfileOut, AnnouncementOut, AnnouncementIn, FeedbackOut,
    FeedbackIn
)
from lms_core.models import Course, CourseMember, CourseContent, Comment, UserProfile, CourseAnnouncement, \
    CourseFeedback
from ninja_simple_jwt.auth.views.api import mobile_auth_router
from ninja_simple_jwt.auth.ninja_auth import HttpJwtAuth
from ninja.pagination import paginate, PageNumberPagination
from django.contrib.auth.models import User

apiv1 = NinjaAPI()
apiAuth = HttpJwtAuth()
auth_router = Router()

apiv1.add_router("/auth/", mobile_auth_router)
apiv1.add_router("/auth/", auth_router)

###############################################################################################
# ███████╗██╗███╗   ██╗ ██████╗ ██╗     ███████╗    ████████╗ █████╗ ███████╗██╗  ██╗███████╗ #
# ██╔════╝██║████╗  ██║██╔════╝ ██║     ██╔════╝    ╚══██╔══╝██╔══██╗██╔════╝██║ ██╔╝██╔════╝ #
# ███████╗██║██╔██╗ ██║██║  ███╗██║     █████╗         ██║   ███████║███████╗█████╔╝ ███████╗ #
# ╚════██║██║██║╚██╗██║██║   ██║██║     ██╔══╝         ██║   ██╔══██║╚════██║██╔═██╗ ╚════██║ #
# ███████║██║██║ ╚████║╚██████╔╝███████╗███████╗       ██║   ██║  ██║███████║██║  ██╗███████║ #
# ╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚══════╝       ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝ #
###############################################################################################

################################
# Single Task - 1
# Register
################################
@auth_router.post("/register", response={201: dict, 400: dict})
def register_user(request, payload: RegisterSchemaIn):
    try:
        User.objects.create(
            username=payload.username,
            password=make_password(payload.password),
            email=payload.email,
            first_name=payload.first_name,
            last_name=payload.last_name
        )
        return 201, {"message": "User registered successfully."}
    except IntegrityError:
        return 400, {"error": "Username or email already exists."}

################################
# Single Task - 2
# Batch Enroll Students
################################
@apiv1.post("/courses/{course_id}/batch-enroll", auth=apiAuth, response={200: dict, 403: dict, 404: dict})
def batch_enroll_students(request, course_id: int, payload: BatchEnrollSchema):
    try:
        course = Course.objects.get(id=course_id)
        if course.teacher.id != request.user.id:
            raise HttpError(403, "You are not the teacher of this course.")

        enrolled = []
        for student_id in payload.student_ids:
            if not User.objects.filter(id=student_id).exists():
                continue

            _, created = CourseMember.objects.get_or_create(
                course_id=course,
                user_id=student_id,
                defaults={"roles": "std"}
            )
            if created:
                enrolled.append(student_id)

        return {
            "message": f"{len(enrolled)} students enrolled.",
            "enrolled_student_ids": enrolled
        }

    except Course.DoesNotExist:
        raise HttpError(404, "Course not found")


@apiv1.get("/contents/{content_id}/comments", auth=apiAuth, response=List[CourseCommentOut])
def get_approved_comments(request, content_id: int):
    return Comment.objects.filter(content_id=content_id, is_approved=True)


@apiv1.get("/comments/moderation-list", auth=apiAuth, response=List[CourseCommentOut])
def comments_for_moderation(request):
    # Ambil semua komentar yang dapat dimoderasi di course yang dimiliki oleh teacher
    return Comment.objects.filter(
        content_id__course_id__teacher=request.user.id
    ).select_related("content_id", "member_id", "member_id__user_id")


################################
# Single Task - 3
# Content Comment Moderation
################################
@apiv1.post("/comments/{comment_id}/moderate", auth=apiAuth, response={200: dict, 403: dict, 404: dict})
def moderate_comment(request, comment_id: int, payload: CommentModerationIn):
    try:
        comment = Comment.objects.select_related('content_id__course_id__teacher').get(id=comment_id)

        if comment.content_id.course_id.teacher.id != request.user.id:
            raise HttpError(403, "You are not authorized to moderate this comment")

        comment.is_approved = payload.is_approved
        comment.save()

        return {
            "message": "Comment moderation updated.",
            "comment_id": comment.id,
            "course_id": comment.content_id.course_id.id,
            "is_approved": comment.is_approved
        }

    except Comment.DoesNotExist:
        raise HttpError(404, "Comment not found")


################################
# Single Task - 4
# User Activity Dashboard
################################
@apiv1.get("/user/activity", auth=apiAuth, response=UserActivityOut)
def user_activity_dashboard(request):
    user = User.objects.get(id=request.user.id)
    return {
        "courses_joined": CourseMember.objects.filter(user_id=user, roles="std").count(),
        "courses_created": Course.objects.filter(teacher=user).count(),
        "comments_written": Comment.objects.filter(member_id__user_id=user).count(),
        "contents_completed": 0
    }


################################
# Single Task - 5
# Course Analytics
################################
@apiv1.get("/courses/{course_id}/analytics", auth=apiAuth, response={200: CourseAnalyticsOut, 403: dict, 404: dict})
def course_analytics(request, course_id: int):
    try:
        course = Course.objects.get(id=course_id)
        if course.teacher.id != request.user.id:
            raise HttpError(403, "You are not authorized to view this course analytics")

        return {
            "members": CourseMember.objects.filter(course_id=course).count(),
            "contents": CourseContent.objects.filter(course_id=course).count(),
            "comments": Comment.objects.filter(content_id__course_id=course).count(),
            "feedbacks": CourseFeedback.objects.filter(course_id=course).count(),
        }

    except Course.DoesNotExist:
        raise HttpError(404, "Course not found")




##########################################################################################
# ██████╗  █████╗ ██╗  ██╗███████╗████████╗    ████████╗ █████╗ ███████╗██╗  ██╗███████╗ #
# ██╔══██╗██╔══██╗██║ ██╔╝██╔════╝╚══██╔══╝    ╚══██╔══╝██╔══██╗██╔════╝██║ ██╔╝██╔════╝ #
# ██████╔╝███████║█████╔╝ █████╗     ██║          ██║   ███████║███████╗█████╔╝ ███████╗ #
# ██╔═══╝ ██╔══██║██╔═██╗ ██╔══╝     ██║          ██║   ██╔══██║╚════██║██╔═██╗ ╚════██║ #
# ██║     ██║  ██║██║  ██╗███████╗   ██║          ██║   ██║  ██║███████║██║  ██╗███████║ #
# ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝          ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝ #
##########################################################################################

###########################################
# Paket Task - 1
# [Fitur +2] Manajemen Profil Pengguna
###########################################

# [Endpoint] Show Profile
@apiv1.get("/users/{user_id}/profile", response={200: UserProfileOut, 404: dict})
def show_profile(request, user_id: int):
    try:
        user = User.objects.select_related('profile').prefetch_related(
            'coursemember_set__course_id',
            'course_set'
        ).get(id=user_id)
    except User.DoesNotExist:
        return 404, {"error": "User not found"}

    profile = user.profile if hasattr(user, 'profile') else None
    return {
        **{field: getattr(user, field) for field in ['first_name', 'last_name', 'email']},
        **{field: getattr(profile, field) if profile else None
           for field in ['handphone', 'deskripsi']},
        "foto_profil": profile.foto_profil.url if profile and profile.foto_profil else None,
        "courses_joined": [{"id": cm.course_id.id, "name": cm.course_id.name}
                           for cm in user.coursemember_set.filter(roles="std")],
        "courses_created": [{"id": c.id, "name": c.name}
                            for c in user.course_set.all()],
    }

# [Endpoint] Edit Profil
@apiv1.put("/users/me/edit", auth=apiAuth, response={200: dict, 400: dict})
def edit_profile(request, payload: UserProfileIn):
    user = User.objects.get(id=request.user.id)
    profile, _ = UserProfile.objects.get_or_create(user=user)

    # Update user fields
    user_fields = ["first_name", "last_name", "email"]
    [setattr(user, f, getattr(payload, f)) for f in user_fields if getattr(payload, f) is not None]

    # Update profile fields
    profile_fields = ["handphone", "deskripsi"]
    [setattr(profile, f, getattr(payload, f)) for f in profile_fields if getattr(payload, f) is not None]

    user.save()
    profile.save()

    return {"message": "Profile updated successfully."}




#########################################################
# Paket Task - 2
# [Fitur +4] Course Announcements
#########################################################

def to_announcement_out(a: CourseAnnouncement) -> AnnouncementOut:
    return AnnouncementOut(
        **{f.name: getattr(a, f.name) for f in a._meta.fields if f.name != 'course'},
        course_id=a.course_id,
        created_at=a.created_at.isoformat()
    )

@apiv1.post("/courses/{course_id}/announcements", auth=apiAuth, response={201: AnnouncementOut, 403: dict, 404: dict})
def create_announcement(request, course_id: int, payload: AnnouncementIn):
    try:
        course = Course.objects.get(id=course_id)
        if course.teacher.id != request.user.id:
            raise HttpError(403, "Unauthorized to create announcements")

        announcement = CourseAnnouncement.objects.create(
            course=course,
            **payload.model_dump()
        )
        return 201, to_announcement_out(announcement)

    except Course.DoesNotExist:
        raise HttpError(404, "Course not found")

@apiv1.get("/courses/{course_id}/announcements", auth=apiAuth, response=List[AnnouncementOut])
def show_announcements(request, course_id: int):
    return [to_announcement_out(a) for a in
            CourseAnnouncement.objects.filter(course_id=course_id)]

# [Endpoint] Edit announcement
@apiv1.put("/announcements/{announcement_id}", auth=apiAuth, response={200: AnnouncementOut, 403: dict, 404: dict})
def edit_announcement(request, announcement_id: int, payload: AnnouncementIn):
    try:
        announcement = CourseAnnouncement.objects.select_related('course__teacher').get(id=announcement_id)
        if announcement.course.teacher.id != request.user.id:
            raise HttpError(403, "Unauthorized to edit announcement")

        for field, value in payload.dict().items():
            setattr(announcement, field, value)
        announcement.save()

        return to_announcement_out(announcement)

    except CourseAnnouncement.DoesNotExist:
        raise HttpError(404, "Announcement not found")

# [Endpoint] Delete announcement
@apiv1.delete("/announcements/{announcement_id}", auth=apiAuth, response={200: dict, 403: dict, 404: dict})
def delete_announcement(request, announcement_id: int):
    try:
        announcement = CourseAnnouncement.objects.select_related('course__teacher').get(id=announcement_id)
        if announcement.course.teacher.id != request.user.id:
            raise HttpError(403, "Unauthorized to delete announcement")

        announcement.delete()
        return {"message": "Announcement deleted successfully"}

    except CourseAnnouncement.DoesNotExist:
        raise HttpError(404, "Announcement not found")


###########################################
# Paket Task - 3
# [Fitur +4] Course Feedback
###########################################

# [Endpoint] Add Feedback
@apiv1.post("/courses/{course_id}/feedback", auth=apiAuth, response={201: FeedbackOut, 404: dict})
def add_feedback(request, course_id: int, payload: FeedbackIn):
    try:
        course = Course.objects.get(id=course_id)
        feedback = CourseFeedback.objects.create(
            course=course,
            user=User.objects.get(id=request.user.id),
            message=payload.message
        )
        return 201, FeedbackOut.from_orm(feedback)  # Use Django Ninja's ORM conversion

    except Course.DoesNotExist:
        raise HttpError(404, "Course not found")

# [Endpoint] Show Feedback
@apiv1.get("/courses/{course_id}/feedback", response=list[FeedbackOut])
def show_feedback(request, course_id: int):
    return FeedbackOut.from_queryset(CourseFeedback.objects.filter(course_id=course_id))

# [Endpoint] Edit Feedback
@apiv1.put("/feedback/{feedback_id}", auth=apiAuth, response={200: FeedbackOut, 403: dict, 404: dict})
def edit_feedback(request, feedback_id: int, payload: FeedbackIn):
    try:
        feedback = CourseFeedback.objects.get(id=feedback_id)
        if feedback.user.id != request.user.id:
            raise HttpError(403, "Unauthorized to edit feedback")

        feedback.message = payload.message
        feedback.save()
        return FeedbackOut.from_orm(feedback)

    except CourseFeedback.DoesNotExist:
        raise HttpError(404, "Feedback not found")

# [Endpoint] Delete Feedback
@apiv1.delete("/feedback/{feedback_id}", auth=apiAuth, response={200: dict, 403: dict, 404: dict})
def delete_feedback(request, feedback_id: int):
    try:
        feedback = CourseFeedback.objects.get(id=feedback_id)
        if feedback.user.id != request.user.id:
            raise HttpError(403, "Unauthorized to delete feedback")

        feedback.delete()
        return {"message": "Feedback deleted successfully"}

    except CourseFeedback.DoesNotExist:
        raise HttpError(404, "Feedback not found")


