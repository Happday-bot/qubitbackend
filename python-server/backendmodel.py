from pydantic import BaseModel


# ---------- Request Model ----------
class LoginRequest(BaseModel):
    college_email: str
    password: str

class FeedbackRequest(BaseModel):
    name: str
    email: str
    message: str

class GalleryUploadRequest(BaseModel):
    alt: str
    caption: str
    image_data: str  # base64 string

class EventRequest(BaseModel):
    title: str
    description: str
    date: str
    time: str
    venue: str
    type: str
    registrationOpen: str
    registrationClose: str
    posterPath: str  # base64 string
    link: str

class EventUpdateRequest(BaseModel):
    id: int
    title: str
    description: str
    date: str
    time: str
    venue: str
    type: str
    registrationOpen: str
    registrationClose: str
    posterPath: str  # base64 string (already compressed in frontend)
    link: str


class QuantumRegistrationRequest(BaseModel):
    fullName: str
    email: str
    phone: str
    password :str
    gender: str
    position: str
    institution: str    
    hasKnowledge: str
    toolsKnown: str
    interests: str
    motivation: str
    advocate:str

class StudentUpdate(BaseModel):
    full_name: str
    college_email: str
    phone: str
    institution: str
    position: str

class BlogUrl(BaseModel):
    url: str
