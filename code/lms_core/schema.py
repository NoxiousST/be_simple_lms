from ninja import Schema
from typing import Optional, List
from datetime import datetime, date

from django.contrib.auth.models import User

class UserOut(Schema):
    id: int
    email: str
    first_name: str
    last_name: str


class CourseSchemaOut(Schema):
    id: int
    name: str
    description: str
    price: int
    image : Optional[str]
    teacher: UserOut
    created_at: datetime
    updated_at: datetime

class CourseMemberOut(Schema):
    id: int 
    course_id: CourseSchemaOut
    user_id: UserOut
    roles: str
    # created_at: datetime


class CourseSchemaIn(Schema):
    name: str
    description: str
    price: int


class CourseContentMini(Schema):
    id: int
    name: str
    description: str
    course_id: CourseSchemaOut
    created_at: datetime
    updated_at: datetime


class CourseContentFull(Schema):
    id: int
    name: str
    description: str
    video_url: Optional[str]
    file_attachment: Optional[str]
    course_id: CourseSchemaOut
    created_at: datetime
    updated_at: datetime

class CourseCommentOut(Schema):
    id: int
    content_id: CourseContentMini
    member_id: CourseMemberOut
    comment: str
    created_at: datetime
    updated_at: datetime

class CourseCommentIn(Schema):
    comment: str

from pydantic import BaseModel, EmailStr, constr

class RegisterSchemaIn(BaseModel):
    username: constr(min_length=3)
    password: constr(min_length=6)
    email: EmailStr
    first_name: str
    last_name: str

class BatchEnrollSchema(BaseModel):
    student_ids: List[int]

class CommentModerationIn(BaseModel):
    is_approved: bool

class UserActivityOut(BaseModel):
    courses_joined: int
    courses_created: int
    comments_written: int
    contents_completed: int = 0

class CourseAnalyticsOut(BaseModel):
    members: int
    contents: int
    comments: int
    feedbacks: int = 0

###

class CourseSummary(BaseModel):
    id: int
    name: str

class UserProfileOut(BaseModel):
    first_name: str
    last_name: str
    email: str
    handphone: Optional[str]
    deskripsi: Optional[str]
    foto_profil: Optional[str]
    courses_joined: List[CourseSummary]
    courses_created: List[CourseSummary]

class UserProfileIn(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    handphone: Optional[str]
    deskripsi: Optional[str]


class AnnouncementIn(BaseModel):
    title: str
    message: str
    show_at: date

class AnnouncementOut(Schema):
    id: int
    course_id: int
    title: str
    message: str
    show_at: date
    created_at: str

class FeedbackIn(BaseModel):
    message: str

class FeedbackOut(BaseModel):
    id: int
    course_id: int
    user_id: int
    message: str
    created_at: datetime
    updated_at: datetime