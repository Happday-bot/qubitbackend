strings = "mongodb+srv://myAtlasDBUser:myatlas-001@myatlasclusteredu.luufxwg.mongodb.net/?retryWrites=true&w=majority&appName=myAtlasClusterEDU"

import uvicorn
from pymongo import MongoClient
from fastapi import FastAPI, HTTPException, Depends, Request, Response, Cookie, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from session_ws import router as ws_router
from session_ws import notify_force_logout
from datetime import datetime, timedelta, timezone
from typing import Optional
import random
import string
import zlib
from fastapi.responses import JSONResponse
from bson.objectid import ObjectId
from scrape import extract_medium_metadata_from_url
from backendmodel import *

app = FastAPI()

# Create a single, global client (thread-safe — reuse per process)
_client = MongoClient(strings, serverSelectionTimeoutMS=5000)  # short timeout for quick failure
db = _client["qubit"]
students = db["students"]
quantum_registration = db["quantum_registration"]
feedback = db["feedback"]
gallery = db["gallery"]
events = db["events"]
user_sessions = db["user_sessions"]
blogs = db["blogs"]


# Define the schema validation
student_schema = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["college_email", "password", "service"],
        "properties": {
            "college_email": {"bsonType": "string"},
            "password": {"bsonType": "string"},
            "service": {"enum": ["member", "core"]},
            "full_name": {"bsonType": "string"},
            "phone": {"bsonType": "string"},
            "joined_on": {"bsonType": "string"},
            "gender": {"bsonType": "string"},
            "position": {"bsonType": "string"},
            "institution": {"bsonType": "string"},
            "has_knowledge": {"bsonType": "string"},
            "tools_known": {"bsonType": "string"},
            "interests": {"bsonType": "string"},
            "motivation": {"bsonType": "string"},
            "advocate": {"bsonType": "string"}
        }
    }
}


quantum_registration_schema = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["full_name", "email", "password"],
        "properties": {
            "full_name": {"bsonType": "string"},
            "email": {"bsonType": "string"},
            "password": {"bsonType": "string"},
            "phone": {"bsonType": "string"},
            "gender": {"bsonType": "string"},
            "position": {"bsonType": "string"},
            "institution": {"bsonType": "string"},
            "has_knowledge": {"bsonType": "string"},
            "tools_known": {"bsonType": "string"},
            "interests": {"bsonType": "string"},
            "motivation": {"bsonType": "string"},
            "advocate": {"bsonType": "string"},
            "applied_on": {"bsonType": "string"}
        }
    }
}


feedback_schema = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "email", "message"],
        "properties": {
            "name": {"bsonType": "string"},
            "email": {"bsonType": "string"},
            "message": {"bsonType": "string"}
        }
    }
}


gallery_schema = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["image_data"],
        "properties": {
            "alt": {"bsonType": "string"},
            "caption": {"bsonType": "string"},
            "image_data": {"bsonType": "string"}
        }
    }
}


events_schema = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["title", "date", "time", "venue"],
        "properties": {
            "title": {"bsonType": "string"},
            "description": {"bsonType": "string"},
            "date": {"bsonType": "string"},
            "time": {"bsonType": "string"},
            "venue": {"bsonType": "string"},
            "type": {"bsonType": "string"},
            "status": {"enum": ["upcoming", "ongoing", "completed"]},
            "registration_open": {"bsonType": "string"},
            "registration_close": {"bsonType": "string"},
            "poster_data": {"bsonType": "binData"},
            "link": {"bsonType": "string"}
        }
    }
}

user_sessions_schema = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "session_id", "state"],
        "properties": {
            "user_id": {"bsonType": "int"},
            "session_id": {"bsonType": "string"},
            "state": {"bsonType": "int", "minimum": 0, "maximum": 1}
        }
    }
}

blogs_schema = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["title", "author_name"],
        "properties": {
            "title": {"bsonType": "string"},
            "subtitle": {"bsonType": "string"},
            "description": {"bsonType": "string"},
            "author_name": {"bsonType": "string"},
            "author_profile": {"bsonType": "string"},
            "twitter_handle": {"bsonType": "string"},
            "published_date": {"bsonType": "string"},
            "reading_time": {"bsonType": "string"},
            "cover_image": {"bsonType": "string"},
            "canonical_url": {"bsonType": "string"},
            "favicon": {"bsonType": "string"},
            "platform": {"bsonType": "string"},
            "twitter_card": {"bsonType": "string"},
            "tags": {"bsonType": "string"}
        }
    }
}



SECRET_KEY = "your_super_secure_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 1

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://happday-bot.github.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)

# ---------- Token Utility Functions ----------
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict):
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        service = payload.get("rol")
        return {"user_id": user_id, "service": service}
    except JWTError:
        return None

def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token = authorization[7:]
    decoded = verify_token(token)
    if not decoded:
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    return decoded["user_id"]

def generate_session_id(length=8):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

# ---------- Login ----------
@app.post("/login")
async def login_user(request: LoginRequest, response: Response):
    college_email = request.college_email
    password = request.password
    if not college_email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    session = generate_session_id()

    # Step 1: Verify user
    user = students.find_one({"college_email": college_email, "password": password})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id = user["_id"]
    service = user.get("service", "member")

    # Step 2: Check existing session
    session_doc = user_sessions.find_one({"user_id": user_id})

    if not session_doc:
        # No session yet → insert new
        user_sessions.insert_one({"user_id": user_id, "session_id": session, "state": 1})
    elif session_doc.get("state", 0) == 0:
        # Previous session logged out → update with new session
        user_sessions.update_one(
            {"user_id": user_id},
            {"$set": {"session_id": session, "state": 1}}
        )
    else:
        # Active session exists → force logout
        await notify_force_logout(user_id)
        user_sessions.update_one(
            {"user_id": user_id},
            {"$set": {"session_id": session, "state": 1}}
        )
    print(f"User {user_id} is sent to user in token as {str(user_id)}")
    token_payload = {"sub": str(user_id), "rol": str(service)}
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="Strict",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/refresh"
    )

    return {"access_token": access_token, "service": service}

# ---------- Refresh Token ----------
@app.post("/refresh")
def refresh_token(request: Request, refresh_token: Optional[str] = Cookie(None)):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")
    decoded = verify_token(refresh_token)
    if not decoded:
        raise HTTPException(status_code=403, detail="Invalid refresh token")
    user_id = decoded["user_id"]
    service = decoded["service"]
    new_access_token = create_access_token({"sub": str(user_id), "rol": str(service)})
    return {"access_token": new_access_token}

# ---------- Get Student Profile ----------
@app.get("/student/{user_id}")
def get_student_profile(user_id: str, current_user: str = Depends(get_current_user)):
    if current_user != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    student = students.find_one(
        {"_id": ObjectId(user_id)},
        {"full_name": 1, "college_email": 1, "phone": 1, "institution": 1, "position": 1}
    )

    if student:
        return {
            "full_name": student.get("full_name"),
            "college_email": student.get("college_email"),
            "phone": student.get("phone"),
            "institution": student.get("institution"),
            "position": student.get("position")
        }
    else:
        raise HTTPException(status_code=404, detail="Student not found")
    


# ---------- Update Student Profile ----------
@app.put("/student/{user_id}")
def update_student_profile(user_id: str, updated: StudentUpdate, current_user: str = Depends(get_current_user)):
    if current_user != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    result = students.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "full_name": updated.full_name,
            "college_email": updated.college_email,
            "phone": updated.phone,
            "institution": updated.institution,
            "position": updated.position
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")

    return {"message": "Profile updated successfully"}

# ---------- Logout ----------
@app.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key="refresh_token",
        path="/refresh",
        samesite="Strict"
    )
    return {"message": "Logged out successfully"}

# ---------- Quantum Registration ----------
@app.post("/quantum/register")
def register_user(data: QuantumRegistrationRequest):
    try:
        doc = {
            "full_name": data.fullName,
            "email": data.email,
            "password": data.password,
            "phone": data.phone,
            "gender": data.gender,
            "position": data.position,
            "institution": data.institution,
            "has_knowledge": data.hasKnowledge,
            "tools_known": data.toolsKnown,
            "interests": data.interests,
            "motivation": data.motivation,
            "advocate": data.advocate,
            "applied_on": datetime.now().isoformat()
        }
        quantum_registration.insert_one(doc)
        return {"message": "✅ Registered successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ Registration failed: {str(e)}")

# ---------- Feedback ----------
@app.post("/feedback")
def submit_feedback(feedback_data: FeedbackRequest):
    try:
        feedback.insert_one({
            "name": feedback_data.name,
            "email": feedback_data.email,
            "message": feedback_data.message
        })
        return {"message": "✅ Feedback submitted successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Server error while saving feedback.")

@app.get("/feedback/messages")
def get_feedback_messages():
    messages = [{"id": str(f["_id"]), "message": f["message"]} for f in feedback.find()]
    return {"messages": messages}

@app.delete("/feedback/{feedback_id}")
def delete_feedback(feedback_id: str):
    result = feedback.delete_one({"_id": ObjectId(feedback_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return {"message": "✅ Feedback deleted successfully"}

# ---------- Gallery ----------
@app.post("/gallery/upload")
def upload_gallery_image(payload: GalleryUploadRequest):
    try:
        compressed = zlib.compress(payload.image_data.encode('utf-8'))
        gallery.insert_one({
            "alt": payload.alt,
            "caption": payload.caption,
            "image_data": compressed
        })
        return {"message": "✅ Image uploaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="❌ Failed to upload image.")

@app.get("/gallery/all")
def get_all_gallery_items():
    results = []
    for r in gallery.find():
        decompressed = zlib.decompress(r["image_data"]).decode('utf-8')
        results.append({
            "id": str(r["_id"]),
            "alt": r.get("alt"),
            "caption": r.get("caption"),
            "image_data": decompressed
        })
    return results

# ---------- Events ----------
@app.post("/events/add")
def add_event(event: EventRequest):
    try:
        compressed = zlib.compress(event.posterPath.encode('utf-8'))
        events.insert_one({
            "title": event.title,
            "description": event.description,
            "date": event.date,
            "time": event.time,
            "venue": event.venue,
            "type": event.type,
            "registration_open": event.registrationOpen,
            "registration_close": event.registrationClose,
            "poster_data": compressed,
            "link": event.link
        })
        return {"message": "✅ Event added successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add event: {str(e)}")

@app.get("/events/all")
def get_events():
    events_list = []
    for r in events.find():
        poster = zlib.decompress(r["poster_data"]).decode('utf-8')
        events_list.append({
            "id": str(r["_id"]),
            "title": r.get("title"),
            "description": r.get("description"),
            "date": r.get("date"),
            "time": r.get("time"),
            "venue": r.get("venue"),
            "type": r.get("type"),
            "registrationOpen": r.get("registration_open"),
            "registrationClose": r.get("registration_close"),
            "posterPath": poster,
            "link": r.get("link")
        })
    return events_list

@app.put("/events/update")
def update_event(event: EventUpdateRequest):
    try:
        compressed_image = zlib.compress(event.get("posterPath").encode('utf-8'))
        result = events.update_one(
            {"_id": ObjectId(event.get("id"))},
            {"$set": {
                "title": event.get("title"),
                "description": event.get("description"),
                "date": event.get("date"),
                "time": event.get("time"),
                "venue": event.get("venue"),
                "type": event.get("type"),
                "registration_open": event.get("registrationOpen"),
                "registration_close": event.get("registrationClose"),
                "poster_data": compressed_image,
                "link": event.get("link")
            }}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Event not found")
        return {"message": "✅ Event updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@app.delete("/events/{event_id}")
def delete_event(event_id: str):
    result = events.delete_one({"_id": ObjectId(event_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"message": "✅ Event deleted."}

# ---------- Get Applications ----------
@app.get("/applications")
def get_applications():
    rows = quantum_registration.find()
    return [
        {
            "id": str(r["_id"]),
            "name": r.get("full_name"),
            "email": r.get("email"),
            "has_knowledge": r.get("has_knowledge"),
            "contact": r.get("phone"),
            "tools": r.get("tools_known"),
            "intrest": r.get("interests"),
            "motivation": r.get("motivation"),
            "advocate": r.get("advocate"),
            "appliedOn": r.get("applied_on"),
            "institution": r.get("institution")
        } for r in rows
    ]

# ---------- Get Members ----------
@app.get("/members")
def get_members():
    rows = students.find()
    return [
        {
            "id": str(r["_id"]),
            "name": r.get("full_name"),
            "email": r.get("college_email"),
            "contact": r.get("phone"),
            "joinedOn": r.get("joined_on"),
            "tools": r.get("tools_known"),
            "intrests": r.get("interests"),
            "institution": r.get("institution")
        } for r in rows
    ]

# ---------- Reject Application ----------
@app.delete("/applications/{app_id}")
def reject_application(app_id: str):
    result = quantum_registration.delete_one({"_id": ObjectId(app_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"message": "Application rejected."}

# ---------- Remove Member ----------
@app.delete("/members/{member_id}")
def remove_member(member_id: str):
    result = students.delete_one({"_id": ObjectId(member_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"message": "Member removed."}

# ---------- Approve Application ----------
@app.post("/approve")
def approve_application(app_data: dict):
    app_id = app_data.get("id")
    reg = quantum_registration.find_one({"_id": ObjectId(app_id)})
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found")

    # Insert into students collection
    students.insert_one({
        "full_name": reg.get("full_name"),
        "college_email": reg.get("email"),
        "password": reg.get("password"),
        "phone": reg.get("phone"),
        "gender": reg.get("gender"),
        "position": reg.get("position"),
        "institution": reg.get("institution"),
        "has_knowledge": reg.get("has_knowledge"),
        "tools_known": reg.get("tools_known"),
        "interests": reg.get("interests"),
        "motivation": reg.get("motivation"),
        "advocate": reg.get("advocate"),
        "service": "member",
        "joined_on": datetime.now().isoformat()
    })

    # Remove from registration
    quantum_registration.delete_one({"_id": ObjectId(app_id)})

    return {"message": f"Application for {reg.get('full_name')} approved and added to members list."}

# ---------- Get All Events ----------
@app.get("/events")
def get_all_events():
    rows = events.find()
    result = {"upcoming": [], "ongoing": [], "completed": []}
    now = datetime.now()

    for r in rows:
        event_id = str(r["_id"])
        title = r.get("title")
        description = r.get("description")
        date_str = r.get("date")
        time_str = r.get("time")
        venue = r.get("venue")
        type_ = r.get("type")
        status = r.get("status", "upcoming")
        poster_data = r.get("poster_data")
        registrationOpen = r.get("registration_open")
        registrationClose = r.get("registration_close")
        link = r.get("link")

        # Combine date and time
        try:
            event_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except:
            event_datetime = datetime.strptime(date_str, "%Y-%m-%d")

        # Compute new status
        if event_datetime.date() > now.date():
            new_status = "upcoming"
        elif event_datetime.date() == now.date():
            new_status = "ongoing"
        else:
            new_status = "completed"

        # Update status if changed
        if new_status != status:
            events.update_one({"_id": r["_id"]}, {"$set": {"status": new_status}})
            status = new_status

        result[status].append({
            "id": event_id,
            "title": title,
            "description": description,
            "date": date_str,
            "time": time_str,
            "venue": venue,
            "type": type_,
            "posterPath": zlib.decompress(poster_data).decode("utf-8"),
            "registrationOpen": registrationOpen,
            "registrationClose": registrationClose,
            "link": link
        })

    return JSONResponse(content=result, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.get("/blogs/all")
def get_all_blogs():
    rows = blogs.find().sort("published_date", -1)  # descending order
    blog_list = []
    for r in rows:
        blog_list.append({
            "id": str(r["_id"]),
            "title": r.get("title"),
            "subtitle": r.get("subtitle"),
            "description": r.get("description"),
            "author_name": r.get("author_name"),
            "author_profile": r.get("author_profile"),
            "twitter_handle": r.get("twitter_handle"),
            "published_date": r.get("published_date"),
            "reading_time": r.get("reading_time"),
            "cover_image": r.get("cover_image"),
            "canonical_url": r.get("canonical_url"),
            "favicon": r.get("favicon"),
            "platform": r.get("platform"),
            "twitter_card": r.get("twitter_card"),
            "tags": r.get("tags")
        })
    return {"blogs": blog_list}

# ---------- Scrape and Save Blog ----------
@app.post("/scrape")
def scrape_and_save_blog(data: BlogUrl):
    try:
        metadata = extract_medium_metadata_from_url(data.url)
        blogs.insert_one({
            "title": metadata.get("title"),
            "subtitle": metadata.get("subtitle"),
            "description": metadata.get("description"),
            "author_name": metadata.get("author_name"),
            "author_profile": metadata.get("author_profile"),
            "twitter_handle": metadata.get("twitter_handle"),
            "published_date": metadata.get("published_date"),
            "reading_time": metadata.get("reading_time"),
            "cover_image": metadata.get("cover_image"),
            "canonical_url": metadata.get("canonical_url"),
            "favicon": metadata.get("favicon"),
            "platform": metadata.get("platform"),
            "twitter_card": metadata.get("twitter_card"),
            "tags": metadata.get("tags")
        })
        return {"success": True, "message": "Blog saved successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to scrape or save blog: {str(e)}")

# ---------- Get All Students ----------
@app.get("/students")
def get_all_students():
    try:
        rows = list(students.find())
        students_list = []
        for r in rows:
            student = r.copy()
            student["id"] = str(student.pop("_id"))  # Convert _id to string for JSON
            students_list.append(student)
        return {"count": len(students_list), "students": students_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    

# # ---------- Run Uvicorn ----------
# if __name__ == "__main__":

#     uvicorn.run("mongobackend:app", host="localhost", port=8000, reload=True,proxy_headers=True)
