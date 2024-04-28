from fastapi import FastAPI, HTTPException, Depends, APIRouter, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

from sqlalchemy import inspect, func, and_, desc, asc
from sqlalchemy.orm import Session

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Flowable, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER, TA_RIGHT

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.date import DateTrigger

from database import engine, SessionLocal, Base

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Union
from datetime import datetime, date, timedelta
from collections import defaultdict

from dotenv import load_dotenv # for .env file
load_dotenv()

import pandas as pd
import time
import string
import random
import os
import requests
import cloudinary
import cloudinary.uploader
import asyncio
import aiohttp
import requests
import glob
from pytz import timezone

from urllib.parse import urlparse
from passlib.context import CryptContext
from cloudinary.api import resources_by_tag, delete_resources_by_tag, delete_folder

from services import send_verification_code_email, send_pass_code_queue_email, send_pass_code_manual_email, \
    send_coc_status_email, send_partylist_status_email, send_appeal_response_email, send_pass_code_student_organization_officer_email, \
    send_eligible_students_email, setup_smtp_server

from models import Student, Announcement, Rule, Guideline, Election, SavedPosition, CreatedElectionPosition, Code, \
                    PartyList, CoC, InsertDataQueues, Candidates, RatingsTracker, VotingsTracker, ElectionAnalytics, ElectionWinners, \
                    Certifications, CreatedAdminSignatory, StudentOrganization, OrganizationOfficer, OrganizationMember, ElectionAppeals, \
                    Comelec, Eligibles, VotingReceipt, CertificationsSigned, CourseEnrolled, Course, StudentClassGrade, Class, Metadata, \
                    IncidentReport
#################################################################
""" Settings """

tags_metadata = [
    {
        "name": "Student",
        "description": "Manage students.",
    },
    {
        "name": "Election",
        "description": "Manage elections.",
    },
    {
        "name": "Announcement",
        "description": "Manage announcements.",
    },
    {
        "name": "Rule",
        "description": "Manage rules.",
    },
    {
        "name": "Guideline",
        "description": "Manage guidelines.",
    },

    {
        "name": "Organization Election",
        "description": "Manage organization elections.",
    },
    {
        "name": "CoC",
        "description": "Manage CoCs."
    },
    {
        "name": "Code",
        "description": "Manage codes.",
    },
    {
        "name": "Party List",
        "description": "Manage party lists.",
    }
]

app = FastAPI(
    title="API for Student Goverment Election",
    description="This is the API for the Student Government Election. (Default API's are for comelec e.g (Election APIs))",
    version="v1",
    docs_url="/",
    redoc_url="/redoc",
    openapi_tags=tags_metadata
)

router = APIRouter(prefix="/api/v1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=['https://sge-voting-v93v4.ondigitalocean.app', 'https://sge-ems-6uaae.ondigitalocean.app', 'https://sge-portal-9lnv2.ondigitalocean.app', 'https://sgeportal.cloud', os.getenv('ELECTION_MANAGEMENT_SYSTEM'), os.getenv('COMELEC_PORTAL'), os.getenv('VOTING_SYSTEM')], # Must change to appropriate frontend URL (local or production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
#################################################################
""" Initial Setup """

def create_tables():
    Base.metadata.create_all(bind=engine)

create_tables()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def manila_now():
    return datetime.now(timezone('Asia/Manila'))

# Create anbd start the scheduler
scheduler = BackgroundScheduler()
scheduler.add_jobstore(SQLAlchemyJobStore(url='sqlite:///jobs.sqlite'), 'default')

###########################################################################
# Cached directory variables
CachedImagesDirectory = "cached/images"
CachedImagesDirectoryElection = f'{CachedImagesDirectory}/election'

# On server startup
@app.on_event("startup")
def start_up():
    scheduler.start()

    # Make cached images directory
    if not os.path.exists(CachedImagesDirectory):
        os.makedirs(CachedImagesDirectory)

    # Make for election
    if not os.path.exists(CachedImagesDirectoryElection):
        os.makedirs(CachedImagesDirectoryElection)

async def download_image(url, filename):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.read()

    with open(filename, "wb") as f:
        f.write(data)

from urllib.parse import unquote

@router.get("/get/cached/elections/{image_path}", tags=["Cached"])
async def get_image(image_path: str):
    # Decode the image path
    return FileResponse(f'{CachedImagesDirectoryElection}/{unquote(image_path)}')

@router.get("/get/time/now", tags=["Time"])
def get_time_now():
    # Get the current date/time in UTC
    now_utc = datetime.now(timezone('UTC'))

    # Convert to Asia/Manila timezone
    now_asia_manila = now_utc.astimezone(timezone('Asia/Manila'))

    return {"time_now": manila_now()}

def create_student_set_as_comelec():
    db = SessionLocal()
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    desired_comelec_student_number = "2024-0001-COM-0"
    
    # Check if the student already exists
    existing_student = db.query(Student).filter(Student.StudentNumber == desired_comelec_student_number).first()

    if existing_student:
        return

    # Create a student
    student = Student(
        StudentId=98765,
        StudentNumber=desired_comelec_student_number,
        FirstName="John",
        LastName="Doe",
        MiddleName="",
        Email="student1.sge@gmail.com",
        Password=pwd_context.hash('123'),
        Gender=1,
        ResidentialAddress="Quezon City",
        MobileNumber="09123457125",
        IsOfficer=False,
        created_at="2024-01-17 23:53:29.417",
        updated_at="2024-01-17 23:53:29.417")
    
    db.add(student)
    db.commit()

    # check if the student is already in comelec
    existing_comelec = db.query(Comelec).filter(Comelec.StudentNumber == desired_comelec_student_number).first()

    if existing_comelec:
        return

    # Add the student to comelec 
    comelec = Comelec(
        StudentNumber=str(student.StudentNumber),
        ComelecPassword=pwd_context.hash('123'),
        Position="President",
        created_at="2024-01-17 23:53:29.417",
        updated_at="2024-01-17 23:53:29.417")
        
    db.add(comelec)
    db.commit()

create_student_set_as_comelec()        

############################################################################# 

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# Store the expiration time and access token
EXPIRES_AT = 0
ACCESS_TOKEN = ""
REFRESH_TOKEN = ""

"""def get_initial_tokens(db: Session = Depends(get_db)):
    # Redirect the user to the OAuth server to log in
    auth_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": "http://localhost:8000/callback",  #
        "scope": "files.readwrite offline_access",
    }
    response = requests.get(auth_url, params=params)
    return response.url

def callback(code, db: Session = Depends(get_db)):
    # The user has logged in and authorized your app, and the OAuth server has redirected them back to your app
    # Now you can exchange the authorization code for an access token and refresh token
    token_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": "http://localhost:8000/callback",  # Use your actual redirect URI
    }
    response = requests.post(token_url, data=payload)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to get tokens")

    # Save the refresh token to the database
    db.add(AzureToken(access_token=response.json()["access_token"], expires_at=time.time() + response.json()["expires_in"], refresh_token=response.json()["refresh_token"]))
    db.commit()

def get_access_token(db: Session = Depends(get_db)):
    global REFRESH_TOKEN

    # Load the stored tokens and expiration time from the database
    token = db.query(AzureToken).first()

    if token is None:
        # No token in the database, need to get a new one
        EXPIRES_AT = 0
        ACCESS_TOKEN = ""
    else:
        EXPIRES_AT = token.expires_at
        ACCESS_TOKEN = token.access_token
        REFRESH_TOKEN = token.refresh_token  # Load the refresh token from the database

    # Check if the access token is expired or near to expire
    if time.time() > EXPIRES_AT:  # refresh
        token_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"

        payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
            "grant_type": "refresh_token",
            "scope": "files.readwrite",
        }

        response = requests.post(token_url, data=payload)

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get access token")

        # Update the stored refresh token and expiration time with the new ones
        REFRESH_TOKEN = response.json()["refresh_token"]
        EXPIRES_AT = time.time() + response.json()["expires_in"]
        ACCESS_TOKEN = response.json()["access_token"]

        # Save the updated tokens and expiration time to the database
        if token is None:
            # No existing token, create a new one
            db.add(AzureToken(access_token=ACCESS_TOKEN, expires_at=EXPIRES_AT, refresh_token=REFRESH_TOKEN))
        else:
            # Update the existing token
            token.access_token = ACCESS_TOKEN
            token.expires_at = EXPIRES_AT
            token.refresh_token = REFRESH_TOKEN  # Save the new refresh token to the database
            token.token_updates += 1  # Increment the token_updates value

        db.commit()

    return ACCESS_TOKEN, REFRESH_TOKEN
"""

""" All about students APIs """

class SaveStudentData(BaseModel):
    student_number: str
    course: str
    first_name: str
    middle_name: str
    last_name: str
    email: str
    year: str
    semester: str
    year_enrolled: str

def validate_columns(df, expected_columns):
    if not set(expected_columns).issubset(df.columns):
        missing_columns = list(set(expected_columns) - set(df.columns))
        return False, {"message": f"Upload failed. The following required columns are missing: {missing_columns}"}
    return True, {}

def process_data(df):
    # Make a copy of the DataFrame before removing duplicates
    df_before = df.copy()

    # Convert 'YearEnrolled' to string
    df['YearEnrolled'] = df['YearEnrolled'].apply(lambda x: str(int(x)) if pd.notnull(x) else x)

    # Remove duplicate entries based on 'EmailAddress'
    df.sort_values(by=['EmailAddress'], inplace=True)
    df.drop_duplicates(subset=['EmailAddress'], keep='first', inplace=True)

    # Remove duplicate entries based on 'StudentNumber'
    df.sort_values(by=['StudentNumber'], inplace=True)
    df.drop_duplicates(subset=['StudentNumber'], keep='first', inplace=True)

    # Replace 'nan' with an empty string
    df.fillna('', inplace=True)
    
    # Get the removed duplicates by finding rows in df_before that aren't in df
    removed_duplicates = df_before.loc[df_before.index.difference(df.index)]

    # Drop additional columns from removed_duplicates
    removed_duplicates = removed_duplicates[['StudentNumber', 'FirstName', 'MiddleName', 'LastName', 'EmailAddress']]

    return df, removed_duplicates

""" ** GET Methods: All about students APIs ** """

@router.get("/student/all", tags=["Student"])
def get_All_Students(db: Session = Depends(get_db)):
    try:
        students = db.query(Student).order_by(Student.StudentId).all()
        return {"students": [student.to_dict() for student in students]}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all students from the database"})
    
@router.get("/student/all/arranged", tags=["Student"])
def get_All_Students_Arranged(db: Session = Depends(get_db)):
    try:
        # Arrange by course, last name, first name, middle name???
        
        # Iterate over all students and get course by student number 
        students = db.query(Student).order_by(Student.StudentId).all()
        students_arranged = []
        
        for student in students:
            student_course = get_Student_Course_by_studnumber(student.StudentNumber, db)
            students_arranged.append([student.StudentNumber, student_course, student.LastName, student.FirstName, student.MiddleName])

        return {"students": students_arranged}

    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all students from the database"})
    
@router.get("/student/eligible/all/{election_id}", tags=["Student"])
def get_All_Eligible_Students(election_id: int, db: Session = Depends(get_db)):
    # Make a dictionary for all course_code
    course_code_dict = {}
    
    # Get all course code
    courses = db.query(Course).all()

    for course in courses:
        course_code_dict[course.CourseCode] = []

    # Get all students in eligible table where election id is equal to the given election id
    eligibles = db.query(Eligibles).filter(Eligibles.ElectionId == election_id).all()

    for eligible in eligibles:
        student_course = get_Student_Course_by_studnumber(eligible.StudentNumber, db)
        student = db.query(Student).filter(Student.StudentNumber == eligible.StudentNumber).first()

        # Get the year of the student
        student_metadata = get_Student_Metadata_by_studnumber(student.StudentNumber)

        if "CourseCode" in student_metadata:
            student_year = student_metadata["Year"]

        # Get the section of the student
        student_section = get_Student_Section_by_studnumber(student.StudentNumber)

        # If the student's course is in the dictionary, append the student to the list
        if student_course in course_code_dict:
            student_info = {
                "StudentNumber": eligible.StudentNumber,
                "LastName": student.LastName,
                "FirstName": student.FirstName,
                "MiddleName": student.MiddleName if student.MiddleName else '',
                "Year": student_year if "CourseCode" in student_metadata else '',
                "Section": student_section if student_section else ''
            }
            course_code_dict[student_course].append(student_info)

    return {"students": course_code_dict}
    
@router.get("/student/fullname/{student_number}", tags=["Student"])
def get_Student_By_Student_Number(student_number: str, db: Session = Depends(get_db)):
    try:
        student = db.query(Student).filter(Student.StudentNumber == student_number).first()
        
        # Get the full name of the student check for middle name
        full_name = student.FirstName + ' ' + (student.MiddleName + ' ' if student.MiddleName else '') + student.LastName

        return {"full_name": full_name}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching the student from the database"})
    
@router.get("/student/insert/data/queues/all", tags=["Student"])
def get_All_Insert_Data_Queues(db: Session = Depends(get_db)):
    try:
        queues = db.query(InsertDataQueues).order_by(InsertDataQueues.QueueId).all()
        return {"queues": [queue.to_dict() for queue in queues]}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all queues from the database"})

""" Method """ 
def get_Student_Course_by_studnumber(student_number: str, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.StudentNumber == student_number).first()

    if not student:
        return {"error": f"Student with student number {student_number} not found."}
    
    student_id = student.StudentId

    student_course = db.query(Course).\
        join(CourseEnrolled, Course.CourseId == CourseEnrolled.CourseId).\
        filter(CourseEnrolled.StudentId == student_id).first()
    
    if not student_course:
        return False
    
    db.close()

    return student_course.CourseCode

@router.get("/student/get/course/{student_number}", tags=["Student"])  
def get_Student_Course(student_number: str, db: Session = Depends(get_db)):
    student_course = get_Student_Course_by_studnumber(student_number, db)

    return {"course": student_course}

""" Method """
def get_Student_Metadata_by_studnumber(student_number: str):
    db = SessionLocal()

    student = db.query(Student).filter(Student.StudentNumber == student_number).first()

    if not student:
        db.close()
        return {"error": f"Student with student number {student_number} not found."}
    
    student_id = student.StudentId

    student_metadata = db.query(Metadata).\
        join(Class, Metadata.MetadataId == Class.MetadataId).\
        join(StudentClassGrade, Class.ClassId == StudentClassGrade.ClassId).\
        filter(StudentClassGrade.StudentId == student_id).first()
    
    if not student_metadata:
        db.close()
        return {"error": f"No metadata found for student with student number {student_number}."}
    
    # Get the course code
    student_course = db.query(Course).filter(Course.CourseId == student_metadata.CourseId).first()

    if not student_course:
        db.close()
        return {"error": f"No course found for student with student number {student_number}."}

    db.close()
    
    return {
        "MetadataId": student_metadata.MetadataId,
        "CourseId": student_metadata.CourseId,
        "CourseCode": student_course.CourseCode if student_course else '',
        "Year": student_metadata.Year,
        "Semester": student_metadata.Semester,
        "Batch": student_metadata.Batch,
        "created_at": student_metadata.created_at,
        "updated_at": student_metadata.updated_at
    }

@router.get("/student/get/metadata/{student_number}", tags=["Student"])
def get_Student_Metadata(student_number: str, db: Session = Depends(get_db)):
    student_metadata = get_Student_Metadata_by_studnumber(student_number)

    return {"metadata": student_metadata}

""" Method """
def get_Student_Section_by_studnumber(student_number: str):
    db = SessionLocal()

    student = db.query(Student).filter(Student.StudentNumber == student_number).first()

    if not student:
        db.close()
        return {"error": f"Student with student number {student_number} not found."}
    
    student_id = student.StudentId

    student_section = db.query(Class).\
        join(StudentClassGrade, Class.ClassId == StudentClassGrade.ClassId).\
        filter(StudentClassGrade.StudentId == student_id).first()
    
    if not student_section:
        db.close()
        return False
    
    db.close()

    return student_section.Section

@router.get("/student/get/section/{student_number}", tags=["Student"])
def get_Student_Section(student_number: str, db: Session = Depends(get_db)):
    student_section = get_Student_Section_by_studnumber(student_number)

    return {"section": student_section}

""" Method """
def get_Student_Status_In_CourseEnrolled(student_number: str):
    db = SessionLocal()
    student = db.query(Student).filter(Student.StudentNumber == student_number).first()

    if not student:
        return f"Student with student number {student_number} not found."
    
    student_id = student.StudentId

    student_status = db.query(CourseEnrolled).filter(CourseEnrolled.StudentId == student_id).first()
    
    if not student_status:
        return False
    
    db.close()

    return student_status.Status

@router.get("/student/get/course-enrolled/status/{student_number}", tags=["Student"])
def get_Student_Status(student_number: str, db: Session = Depends(get_db)):
    student_status = get_Student_Status_In_CourseEnrolled(student_number)

    return {"status": student_status}

""" Method """
def get_Student_Class_Grade_by_studnumber(student_number: str):
    db = SessionLocal()

    student = db.query(Student).filter(Student.StudentNumber == student_number).first()

    if not student:
        db.close()
        return f"Student with student number {student_number} not found."
    
    student_id = student.StudentId

    student_grade = db.query(StudentClassGrade).\
        filter(StudentClassGrade.StudentId == student_id).first()
    
    if not student_grade:
        db.close()
        return False
    
    db.close()

    return student_grade.Grade

@router.get("/student/get/grade/{student_number}", tags=["Student"])
def get_Student_Class_Grade(student_number: str, db: Session = Depends(get_db)):
    student_grade = get_Student_Class_Grade_by_studnumber(student_number)
    
    return {"grade": student_grade}
    
""" ** POST Methods: All about students APIs ** """
# Create a queue
queue = asyncio.Queue()

# Define a worker function
async def insert_data_email_worker():
    while True:
        db = SessionLocal()

        # Get a task from the queue
        task = await queue.get()

        # Process the task
        queue_id, student_number, student_email, pass_code = task
        send_pass_code_queue_email(student_number, student_email, pass_code, queue_id)

        # Indicate that the task is done
        queue.task_done()

# Start the worker in the background
asyncio.create_task(insert_data_email_worker())
    
@router.post("/student/insert/data/manual", tags=["Student"])
def student_Insert_Data_Manual(data: SaveStudentData, db: Session = Depends(get_db)):
    # Check if a student with the given StudentNumber already exists
    existing_student = db.query(Student).filter(Student.StudentNumber == data.student_number).first()
    existing_email = db.query(Student).filter(Student.EmailAddress == data.email).first()

    if existing_student:
        return {"error": f"Student with student number {data.student_number} already exists."}
    
    if existing_email:
        return {"error": f"Student with email address {data.email} already exists."}
    
    # Insert the data into the database
    student = Student(
        StudentNumber=data.student_number,
        FirstName=data.first_name,
        MiddleName=data.middle_name,
        LastName=data.last_name,
        EmailAddress=data.email,
        Year=data.year,
        Course=data.course,
        CurrentSemesterEnrolled=data.semester,
        YearEnrolled=data.year_enrolled,
        IsOfficer=False
    )
    db.add(student)
    db.commit()

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # Generate a unique code and add it to the database
    while True:
        # Generate a random code
        pass_value = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

        # Hash the password
        hashed_password = pwd_context.hash(pass_value)

        # Check if the code already exists in the database
        existing_code = db.query(StudentPassword).filter(StudentPassword.Password == hashed_password).first()

        # If the code doesn't exist in the database, insert it and break the loop
        if not existing_code:
            new_pass = StudentPassword(StudentNumber=data.student_number, 
                            Password=hashed_password,
                            created_at=manila_now(),
                            updated_at=manila_now())
            db.add(new_pass)
            db.commit()

            send_pass_code_manual_email(data.student_number, data.email, pass_value)
            break

    return {"message": f"Student {data.student_number} was inserted successfully."}

@router.post("/student/insert/data/attachment", tags=["Student"])
async def student_Insert_Data_Attachment(files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    responses = []
    elements = []
    styleSheet = getSampleStyleSheet()

    inserted_student_count = 0
    incomplete_student_column_count = 0

    for file in files:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file.file, encoding='ISO-8859-1')
        elif file.filename.endswith('.xlsx'):
            df = pd.read_excel(file.file, engine='openpyxl')
        else:
            responses.append({"file": file.filename, "message": "Upload failed. The file format is not supported."})
            continue

        # Define the expected columns
        expected_columns = ['StudentNumber', 'FirstName', 'MiddleName', 'LastName', 'EmailAddress', 
                            'Year', 'Course', 'CurrentSemesterEnrolled', 'YearEnrolled', 'IsOfficer']

        # Check if all expected columns exist in the DataFrame
        valid, response = validate_columns(df, expected_columns)
        if not valid:
            responses.append({"file": file.filename, "unexpected_columns": response})
            continue

        # Process the data
        df, removed_duplicates = process_data(df)

        existing_students = {student.StudentNumber for student in db.query(Student).all()}
        existing_emails = {student.EmailAddress for student in db.query(Student).all()}

        # Insert the data into the database
        inserted_students = []
        not_inserted_students_due_to_uniqueness = []  # List to store students not inserted
        incomplete_student_column = []

        # Create a new queue in the InsertDataQueues table
        new_queue = InsertDataQueues(QueueName=file.filename, 
                                   ToEmailTotal=0, 
                                   EmailSent=0, 
                                   EmailFailed=0,
                                   Status="Pending",
                                   created_at=manila_now(),
                                   updated_at=manila_now())
        db.add(new_queue)
        db.flush() # Flush the session to get the QueueId

        for index, row in df.iterrows():
           
            # If the student number and email do not exist and all fields are not empty
            if str(row['StudentNumber']) not in existing_students and str(row['EmailAddress']) not in existing_emails and all(row[field] != '' for field in ['FirstName', 'LastName', 'EmailAddress', 'Year', 'Course', 'CurrentSemesterEnrolled', 'YearEnrolled', 'IsOfficer']):
                student = Student(
                    StudentNumber=row['StudentNumber'],
                    FirstName=row['FirstName'],
                    MiddleName=row.get('MiddleName', ''),  # Use .get() to make MiddleName optional
                    LastName=row['LastName'],
                    EmailAddress=row['EmailAddress'],
                    Year=row['Year'],
                    Course=row['Course'],
                    CurrentSemesterEnrolled=row['CurrentSemesterEnrolled'],
                    YearEnrolled=row['YearEnrolled'],
                    IsOfficer=row['IsOfficer']
                )
                inserted_student_count += 1
                db.add(student)
                inserted_students.append([row['StudentNumber'], row['FirstName'], row.get('MiddleName', ''), row['LastName'], row['EmailAddress']])

                pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

                # Generate a unique code and add it to the database
                while True:
                    # Generate a random code
                    pass_value = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

                    # Hash the password
                    hashed_password = pwd_context.hash(pass_value)

                    # Check if the code already exists in the database
                    existing_code = db.query(StudentPassword).filter(StudentPassword.Password == hashed_password).first()

                    # If the code doesn't exist in the database, insert it and break the loop
                    if not existing_code:
                        new_pass = StudentPassword(StudentNumber=row['StudentNumber'], 
                                        Password=hashed_password,
                                        created_at=manila_now(),
                                        updated_at=manila_now())
                        db.add(new_pass)
                        db.commit()

                        # Add the email task to the queue
                        new_queue.ToEmailTotal += 1
                        await queue.put((new_queue.QueueId, row['StudentNumber'], row['EmailAddress'], pass_value))
                        break

                # Commit every 100 students
                if inserted_student_count % 100 == 0:
                    db.commit()
            
            # If the student number or email already exists
            elif str(row['StudentNumber']) in existing_students or str(row['EmailAddress']) in existing_emails:
                not_inserted_students_due_to_uniqueness.append([row['StudentNumber'], row['FirstName'], row.get('MiddleName', ''), row['LastName'], row['EmailAddress']])
            
            # If there are missing fields
            else:
                incomplete_student_column_count += 1
                incomplete_student_column.append([row['StudentNumber'], row['FirstName'], row.get('MiddleName', ''), row['LastName'], row['EmailAddress']])

        # Commit any remaining students
        if inserted_student_count % 100 != 0:
            db.commit()

        if inserted_student_count == 0 and incomplete_student_column_count == 0:
            responses.append({"no_new_students": f"All students in ({file.filename}) were already inserted. No changes applied."})
        else:
            # If there are inserted students but no incomplete student columns
            if inserted_student_count > 0 and incomplete_student_column_count <= 0:
                responses.append({"file": file.filename, "message": "Upload successful, inserted students: " + str(inserted_student_count)})
            
            # If there are inserted students and incomplete student columns
            elif inserted_student_count > 0 and incomplete_student_column_count > 0:
                responses.append({"file": file.filename, "message": "Upload successful, inserted students: " + str(inserted_student_count) + ", incomplete student columns: " + str(incomplete_student_column_count)})
            
            # If there are no inserted students but there are incomplete student columns
            elif inserted_student_count <= 0 and incomplete_student_column_count > 0:
                responses.append({"file": file.filename, "message": "No new students were inserted, incomplete student columns: " + str(incomplete_student_column_count)})
            
        # Add a table to the PDF for each file
        if inserted_student_count > 0 or incomplete_student_column_count > 0:
            elements.append(Paragraph(f"<para align=center><b>{file.filename}</b></para>", styleSheet["BodyText"]))
            elements.append(Spacer(1, 12))

            if inserted_students:
                elements.append(Paragraph(f"Number of inserted students: {len(inserted_students)}"))
                elements.append(Spacer(1, 12))
                table = Table([["Student Number", "First Name", "Middle Name", "Last Name", "Email"]] + inserted_students)
                table.setStyle(TableStyle([
                    ('GRID', (0,0), (-1,-1), 1, colors.black),
                    ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
                    ('FONTSIZE', (0,0), (-1,-1), 10),
                ]))
                elements.append(table)

            if not_inserted_students_due_to_uniqueness:
                elements.append(Spacer(1, 12))
                elements.append(Paragraph(f"Number of not inserted students due to student number or email exists already: {len(not_inserted_students_due_to_uniqueness)}"))
                elements.append(Spacer(1, 12))
                table = Table([["Student Number", "First Name", "Middle Name", "Last Name", "Email"]] + not_inserted_students_due_to_uniqueness)
                table.setStyle(TableStyle([
                    ('GRID', (0,0), (-1,-1), 1, colors.black),
                    ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
                    ('FONTSIZE', (0,0), (-1,-1), 10),
                ]))
                elements.append(table)

            if incomplete_student_column:
                elements.append(Spacer(1, 12))
                elements.append(Paragraph(f"Number of not inserted students due to incomplete column value(s): {len(incomplete_student_column)}"))
                elements.append(Spacer(1, 12))
                table = Table([["Student Number", "First Name", "Middle Name", "Last Name", "Email"]] + incomplete_student_column)
                table.setStyle(TableStyle([
                    ('GRID', (0,0), (-1,-1), 1, colors.black),
                    ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
                    ('FONTSIZE', (0,0), (-1,-1), 10),
                ]))
                elements.append(table)

            elements.append(Spacer(1, 12))

            if not removed_duplicates.empty:
                elements.append(Paragraph(f"Number of removed duplicates: {len(removed_duplicates.values.tolist())}"))
                elements.append(Spacer(1, 12))
                table = Table([["Student Number", "First Name", "Middle Name", "Last Name", "Email"]] + removed_duplicates.values.tolist())
                table.setStyle(TableStyle([
                    ('GRID', (0,0), (-1,-1), 1, colors.black),
                    ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
                    ('FONTSIZE', (0,0), (-1,-1), 10),
                ]))
                elements.append(table)

    if inserted_student_count > 0 or incomplete_student_column_count > 0:
        # Save the PDF to a temporary file
        now = manila_now()
        pdf_name = f"Report_{now.strftime('%Y%m%d_%H%M%S')}.pdf"
        doc = SimpleDocTemplate(pdf_name, pagesize=letter)
        doc.build(elements)

        # Upload to cloudinary
        upload_result = cloudinary.uploader.upload(pdf_name, 
                                            resource_type = "raw", 
                                            public_id = f"InsertData/Reports/{pdf_name}",
                                            tags=[pdf_name])
        
        # Delete the local file
        os.remove(pdf_name)

    # Return the responses and a URL to download the PDF
        return JSONResponse({
            "responses": responses,
            "pdf_url": upload_result['secure_url']
        })
    else:
        # Return the responses only if no PDF was generated
        return JSONResponse({
                    "responses": responses,
                })
    
class LoginData(BaseModel):
    StudentNumber: str
    Password: str

@router.post("/student/voting/login", tags=["Student"])
def student_Voting_Login(data: LoginData, db: Session = Depends(get_db)):
    StudentNumber = data.StudentNumber
    Password = data.Password

    # get the student in eligibles table
    student = db.query(Eligibles).filter(Eligibles.StudentNumber == StudentNumber).first()
    if not student:
        return {"error": "Student not found."}
    
    # Loop over students in eligibles table and check each password
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    for student in db.query(Eligibles).filter(Eligibles.StudentNumber == StudentNumber).all():
        if pwd_context.verify(Password, student.VotingPassword):
            student_id = db.query(Student).filter(Student.StudentNumber == StudentNumber).first()
            student_id = student_id.StudentId
            
            return {"message": True,
                    "student_id": student_id}

    return {"error": "Incorrect password."}

@router.post("/student/election-management/login", tags=["Student"])
def student_Election_Management_Login(data: LoginData, db: Session = Depends(get_db)):
    StudentNumber = data.StudentNumber
    Password = data.Password

    student = db.query(Student).filter(Student.StudentNumber == StudentNumber).first()
    if not student:
        return {"error": "Student not found."}
    
    # Attempt to login as comelec first before student organization officer
    comelec = db.query(Comelec).filter(Comelec.StudentNumber == StudentNumber).first()

    if comelec:
        # Check if the password matches
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        if not pwd_context.verify(Password, comelec.ComelecPassword):
            return {"error": "Incorrect password."}
        
        return {"message": True, "user_role": "comelec", "student_id": student.StudentId}
    
    # Attempt to login as student organization officer
    officer = db.query(OrganizationOfficer).filter(OrganizationOfficer.StudentNumber == StudentNumber).first()

    if officer:
        # Check if the password matches
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        if not pwd_context.verify(Password, officer.OfficerPassword):
            return {"error": "Incorrect password."}
        
        return {"message": True, "user_role": "officer"}
    
    return {"error": "Cannot found credentials"}

#################################################################
""" Student's Metadatas APIs """
@router.get("/courses/all", tags=["Student Metadata"])
def get_All_Courses(db: Session = Depends(get_db)):
    courses = db.query(Course).order_by(Course.CourseId).all()
    return {"courses": [course.to_dict() for course in courses]}

@router.get("/courses/{course_id}", tags=["Student Metadata"])
def get_Course(course_id: int, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.CourseId == course_id).first()
    return {"course": course.to_dict()}

#################################################################
""" Student Organization Table APIs """
class Officer(BaseModel):
    student_number: str
    position: str
    image: str

class Member(BaseModel):
    student_number: str

class StudentOrganizationData(BaseModel):
    organization_logo: str
    organization_name: str
    organization_requirements: str
    organization_adviser_image: str
    organization_adviser_name: str
    organization_vision: str
    organization_mission: str
    officers: List[Officer]
    members: List[Member]

""" ** GET Methods: All about Student Organizations APIs ** """
@router.get("/student/organization/all", tags=["Student Organization"])
def get_All_Student_Organization(db: Session = Depends(get_db)):
    student_organizations = db.query(StudentOrganization).order_by(StudentOrganization.StudentOrganizationId).all()
    return {"student_organizations": [student_organization.to_dict() for student_organization in student_organizations]}

@router.get("/student/organization/{student_organization_id}", tags=["Student Organization"])
def get_Student_Organization(student_organization_id: int, db: Session = Depends(get_db)):
    student_organization = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == student_organization_id).first()

    if not student_organization:
        return {"error": f"Student organization with id {student_organization_id} not found."}
    
    student_organization = student_organization.to_dict()

    # Get the organization logo and adviser image in cloudinary using secure url
    student_organization["OrganizationLogo"] = student_organization["OrganizationLogo"]
    student_organization["AdviserImage"] = student_organization["AdviserImage"]

    # Get officers
    officers = db.query(OrganizationOfficer).filter(OrganizationOfficer.StudentOrganizationId == student_organization_id).all()

    student_organization["officers"] = [officer.to_dict() for officer in officers]

    # Attach student's data to officers base on student number
    for officer in student_organization["officers"]:
        student = db.query(Student).filter(Student.StudentNumber == officer["StudentNumber"]).first()
        student_metadata = get_Student_Metadata_by_studnumber(student.StudentNumber)

        if "CourseCode" in student_metadata:
            student_year = student_metadata["Year"]

        # Get the section of the student
        student_section = get_Student_Section_by_studnumber(student.StudentNumber)

        officer["FirstName"] = student.FirstName
        officer["MiddleName"] = student.MiddleName if student.MiddleName else ''
        officer["LastName"] = student.LastName
        officer["CourseCode"] = student_metadata["CourseCode"] if "CourseCode" in student_metadata else ''
        officer["Year"] = student_year if "Year" in student_metadata else ''
        officer["Section"] = student_section if student_section else ''

    # Get members
    members = db.query(OrganizationMember).filter(OrganizationMember.StudentOrganizationId == student_organization_id).all()
    student_organization["members"] = [member.to_dict() for member in members]

    # Attach student's data to members base on student number
    for member in student_organization["members"]:
        student = db.query(Student).filter(Student.StudentNumber == member["StudentNumber"]).first()
        student_metadata = get_Student_Metadata_by_studnumber(student.StudentNumber)

        if "CourseCode" in student_metadata:
            student_year = student_metadata["Year"]

        # Get the section of the student
        student_section = get_Student_Section_by_studnumber(student.StudentNumber)

        member["FirstName"] = student.FirstName
        member["MiddleName"] = student.MiddleName if student.MiddleName else ''
        member["LastName"] = student.LastName
        member["CourseCode"] = student_metadata["CourseCode"] if "CourseCode" in student_metadata else ''
        member["Year"] = student_year if "Year" in student_metadata else ''
        member["Section"] = student_section if student_section else ''

    return {"student_organization": student_organization}

@router.get("/student/organization/get_by_election_id/{election_id}", tags=["Student Organization"])
def get_Student_Organization_By_Election(election_id: int, db: Session = Depends(get_db)):
    # Get the student organization id by election id
    student_organization_id = db.query(Election).filter(Election.ElectionId == election_id).first().StudentOrganizationId
    
    if not student_organization_id:
        return {"error": f"Student organization with election id {election_id} not found."}

    student_organization = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == student_organization_id).first()

    if not student_organization:
        return {"error": f"Student organization with id {student_organization_id} not found."}
    
    student_organization = student_organization.to_dict()

    return {"student_organization": student_organization}

""" ** POST Methods: All about Student Organizations APIs ** """
# Create a queue
student_officer_temp_password_queue = asyncio.Queue()

# Define a worker function
async def student_officer_temp_password_queue_worker():
    while True:
        db = SessionLocal()

        # Get a task from the queue
        task = await student_officer_temp_password_queue.get()

        # Process the task
        student_number, student_email, pass_code = task
        send_pass_code_student_organization_officer_email(student_number, student_email, pass_code)

        # Indicate that the task is done
        student_officer_temp_password_queue.task_done()

# Start the worker in the background
asyncio.create_task(student_officer_temp_password_queue_worker())

@router.post("/student/organization/create", tags=["Student Organization"])
async def student_Organization_Create(data: StudentOrganizationData, db: Session = Depends(get_db)):
    # Check if the organization already exists
    existing_organization = db.query(StudentOrganization).filter(StudentOrganization.OrganizationName == data.organization_name).first()
    if existing_organization:
        return JSONResponse(status_code=400, content={"detail": "Organization name already exists."})
    
    organization = StudentOrganization(
        OrganizationLogo='',
        OrganizationName=data.organization_name,
        OrganizationMemberRequirements=data.organization_requirements,
        AdviserImage='',
        AdviserName=data.organization_adviser_name,
        Vision=data.organization_vision,
        Mission=data.organization_mission,
        created_at=manila_now(),
        updated_at=manila_now()
    )

    db.add(organization)
    db.commit()

    organization_logo_tag = 'OrganizationLogo' + str(organization.StudentOrganizationId)
    adviser_image_tag = 'AdviserImage' + str(organization.StudentOrganizationId)

    # Upload the organization logo to cloudinary
    upload_result1 = cloudinary.uploader.upload(data.organization_logo,
                                        public_id = f"StudentOrganization/{data.organization_name + str(organization.StudentOrganizationId)}/Logo",
                                        tags=[organization_logo_tag])
    
    # Upload the organization adviser image to cloudinary
    upload_result2 = cloudinary.uploader.upload(data.organization_adviser_image,
                                        public_id = f"StudentOrganization/{data.organization_name + str(organization.StudentOrganizationId)}/Adviser",
                                        tags=[adviser_image_tag])
    
    organization.OrganizationLogo = upload_result1['secure_url']
    organization.AdviserImage = upload_result2['secure_url']

    db.commit()
            
    # Create the officers
    for officer in data.officers:
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        # Generate a random code
        pass_value = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

        # Hash the password
        hashed_password = pwd_context.hash(pass_value)

        # Get the email address of the student
        student = db.query(Student).filter(Student.StudentNumber == officer.student_number).first()
        student_email = student.Email

        new_officer = OrganizationOfficer(
            StudentOrganizationId=organization.StudentOrganizationId,
            StudentNumber=officer.student_number,
            Position=officer.position,
            OfficerPassword=hashed_password,
            Image='',
            created_at=manila_now(),
            updated_at=manila_now()
        )

        await student_officer_temp_password_queue.put((officer.student_number, student_email, pass_value))

        db.add(new_officer)
        db.commit()

        officer_image_tag = 'OrganizationOfficer' + str(new_officer.OrganizationOfficerId)

        # uplaod the officer image to cloudinary
        upload_result3 = cloudinary.uploader.upload(officer.image,
                                        public_id = f"StudentOrganization/{data.organization_name + str(organization.StudentOrganizationId)}/Officers/{officer.student_number}",
                                        tags=[officer_image_tag])

        new_officer.Image = upload_result3['secure_url']
        db.commit()

    # Create the members
    for member in data.members:
        new_member = OrganizationMember(
            StudentOrganizationId=organization.StudentOrganizationId,
            StudentNumber=member.student_number,
            created_at=manila_now(),
            updated_at=manila_now()
        )
        db.add(new_member)
        db.commit()

    return {"message": "Organization created successfully."}

#################################################################
""" Organization Officer Table APIs """

""" ** GET Methods: All about Organization Officers APIs ** """
@router.get("/organization/officer/all", tags=["Organization Officer"])
def get_All_Organization_Officer(db: Session = Depends(get_db)):
    try:
        officers = db.query(OrganizationOfficer).order_by(OrganizationOfficer.OrganizationOfficerId).all()
        return {"officers": [officer.to_dict() for officer in officers]}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all organization officers from the database"})
    
@router.get("/organization/officer/existing/{student_number}", tags=["Organization Officer"])
def get_Organization_Officer_By_Student_Number(student_number: str, db: Session = Depends(get_db)):
    try:
        officer = db.query(OrganizationOfficer).filter(OrganizationOfficer.StudentNumber == student_number).first()
        
        if not officer:
            return {"response": False}
        
        return {"response": True}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching the organization officer from the database"})
    
@router.get("/organization/officer/{student_organization_id}", tags=["Organization Officer"])
def get_Organization_Officer_By_Student_Organization_Id(student_organization_id: int, db: Session = Depends(get_db)):
    try:
        officers = db.query(OrganizationOfficer).filter(OrganizationOfficer.StudentOrganizationId == student_organization_id).order_by(OrganizationOfficer.OrganizationOfficerId).all()
        return {"officers": [officer.to_dict() for officer in officers]}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all organization officers from the database"})

""" ** POST Methods: All about Organization Officers APIs ** """

#################################################################
""" Organization Member Table APIs """

""" ** GET Methods: All about Organization Members APIs ** """
@router.get("/organization/member/all", tags=["Organization Member"])
def get_All_Organization_Member(db: Session = Depends(get_db)):
    try:
        members = db.query(OrganizationMember).order_by(OrganizationMember.OrganizationMemberId).all()
        return {"members": [member.to_dict() for member in members]}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all organization members from the database"})
    
@router.get("/organization/member/existing/{student_number}", tags=["Organization Member"])
def get_Organization_Member_By_Student_Number(student_number: str, db: Session = Depends(get_db)):
    try:
        member = db.query(OrganizationMember).filter(OrganizationMember.StudentNumber == student_number).first()
        
        if not member:
            return {"response": False}
        
        return {"response": True}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching the organization member from the database"})
    
#################################################################
""" Election Table APIs """

class ElectionInfoData(BaseModel):
    election_name: str
    election_type: int
    school_year: str
    semester: str
    election_start: datetime
    election_end: datetime
    filing_coc_start: datetime
    filing_coc_end: datetime
    campaign_start: datetime
    campaign_end: datetime
    voting_start: datetime
    voting_end: datetime
    appeal_start: datetime
    appeal_end: datetime
    created_by: str

class CreatedPositionData(BaseModel):
    value: str
    quantity: str

class CreateElectionData(BaseModel):
    positions: List[CreatedPositionData]
    election_info: ElectionInfoData

class SaveReusablePositionData(BaseModel):
    name: str

class ElectionDelete(BaseModel):
    id: int

""" ** GET Methods: All about election APIs ** """
@router.get("/election/all", tags=["Election"])
async def get_All_Election(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    elections = db.query(Election).order_by(Election.ElectionId).all()
    elections_with_creator = []

    for i, election in enumerate(elections):
        creator = db.query(Student).filter(Student.StudentNumber == election.CreatedBy).first()
        election_dict = election.to_dict(i+1)
        election_dict["CreatedByName"] = (creator.FirstName + ' ' + (creator.MiddleName + ' ' if creator.MiddleName else '') + creator.LastName) if creator else ""

        # Get the StudentOrganizationName of the election from the StudentOrganization table
        student_organization = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == election.StudentOrganizationId).first()
        election_dict["StudentOrganizationName"] = student_organization.OrganizationName if student_organization else ""
        
        # Get the organization logo using secure_url from cloudinary stored in OrganizationLogo column
        election_dict["OrganizationLogo"] = student_organization.OrganizationLogo

        # Get the OrganizationMemberRequirement of the election from the StudentOrganization table
        student_organization = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == election.StudentOrganizationId).first()
        election_dict["OrganizationMemberRequirement"] = student_organization.OrganizationMemberRequirements if student_organization else ""

        # Get the number of candidates in the election
        candidates = db.query(Candidates).filter(Candidates.ElectionId == election.ElectionId).all()
        election_dict["NumberOfCandidates"] = len(candidates)
        
        # Get the number of partylists in the election who is approved
        partylists = db.query(PartyList).filter(PartyList.ElectionId == election.ElectionId, PartyList.Status == 'Approved').all()
        election_dict["NumberOfPartylists"] = len(partylists)

        # Get the number of positions in the election
        positions = db.query(CreatedElectionPosition).filter(CreatedElectionPosition.ElectionId == election.ElectionId).all()
        election_dict["NumberOfPositions"] = len(positions)
        
        # Get the CreatedElectionPositions of the election then append it to the election_dict
        election_dict["Positions"] = [position.to_dict(i+1) for i, position in enumerate(positions)]

        # Determine what election period
        now = manila_now()
        election_dict["ElectionPeriod"] = "Pre-Election"

        if now < election.CampaignStart.replace(tzinfo=timezone('Asia/Manila')):
            election_dict["ElectionPeriod"] = "Filing Period"

        if now < election.VotingStart.replace(tzinfo=timezone('Asia/Manila')):
            election_dict["ElectionPeriod"] = "Campaign Period"

        if now < election.AppealStart.replace(tzinfo=timezone('Asia/Manila')):
            election_dict["ElectionPeriod"] = "Voting Period"

        else:
            election_dict["ElectionPeriod"] = "Post-Election"
        
        elections_with_creator.append(election_dict)

    return {"elections": elections_with_creator}

@router.get("/election/all/organization/{student_organization_id}", tags=["Election"])
async def get_All_Election_By_Student_Organization_Id(student_organization_id: int, db: Session = Depends(get_db)):
    elections = db.query(Election).filter(Election.StudentOrganizationId == student_organization_id).order_by(Election.ElectionId).all()
    elections_with_creator = []

    for i, election in enumerate(elections):
        creator = db.query(Student).filter(Student.StudentNumber == election.CreatedBy).first()
        election_dict = election.to_dict(i+1)
        election_dict["CreatedByName"] = (creator.FirstName + ' ' + (creator.MiddleName + ' ' if creator.MiddleName else '') + creator.LastName) if creator else ""

        # Get the StudentOrganizationName of the election from the StudentOrganization table
        student_organization = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == election.StudentOrganizationId).first()
        election_dict["StudentOrganizationName"] = student_organization.OrganizationName if student_organization else ""
        
        # Get the organization logo using secure_url from cloudinary stored in OrganizationLogo column
        election_dict["OrganizationLogo"] = student_organization.OrganizationLogo

        # Get the OrganizationMemberRequirement of the election from the StudentOrganization table
        student_organization = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == election.StudentOrganizationId).first()
        election_dict["OrganizationMemberRequirement"] = student_organization.OrganizationMemberRequirements if student_organization else ""

        # Get the number of candidates in the election
        candidates = db.query(Candidates).filter(Candidates.ElectionId == election.ElectionId).all()
        election_dict["NumberOfCandidates"] = len(candidates)
        
        # Get the number of partylists in the election who is approved
        partylists = db.query(PartyList).filter(PartyList.ElectionId == election.ElectionId, PartyList.Status == 'Approved').all()
        election_dict["NumberOfPartylists"] = len(partylists)

        # Get the number of positions in the election
        positions = db.query(CreatedElectionPosition).filter(CreatedElectionPosition.ElectionId == election.ElectionId).all()
        election_dict["NumberOfPositions"] = len(positions)
        
        # Get the CreatedElectionPositions of the election then append it to the election_dict
        election_dict["Positions"] = [position.to_dict(i+1) for i, position in enumerate(positions)]

        # Determine what election period
        now = manila_now()
        if now < election.CoCFilingStart.replace(tzinfo=timezone('Asia/Manila')):
            election_dict["ElectionPeriod"] = "Pre-Election"

        if now > election.CoCFilingStart.replace(tzinfo=timezone('Asia/Manila')):
            election_dict["ElectionPeriod"] = "Filing Period"

        if now > election.CampaignStart.replace(tzinfo=timezone('Asia/Manila')):
            election_dict["ElectionPeriod"] = "Campaign Period"

        if now > election.VotingStart.replace(tzinfo=timezone('Asia/Manila')):
            election_dict["ElectionPeriod"] = "Voting Period"

        if now > election.AppealStart.replace(tzinfo=timezone('Asia/Manila')):
            election_dict["ElectionPeriod"] = "Appeal Period"

        if now > election.AppealEnd.replace(tzinfo=timezone('Asia/Manila')):
            election_dict["ElectionPeriod"] = "Post-Election"

        elections_with_creator.append(election_dict)

    return {"elections": elections_with_creator}

@router.get("/election/all/is-student-voted", tags=["Election"])
def get_All_Election_Is_Student_Voted(student_number: str, db: Session = Depends(get_db)):
    # Get the student's course
    student = db.query(Student).filter(Student.StudentNumber == student_number).first()
    student_course = get_Student_Course_by_studnumber(student_number, db)

    # Check if the student has voted in the election
    elections = db.query(Election).order_by(Election.ElectionId).all()
    elections_with_creator = []
    atleast_one_available_election = False

    now = manila_now()

    for i, election in enumerate(elections):
        creator = db.query(Student).filter(Student.StudentNumber == election.CreatedBy).first()
        election_dict = election.to_dict(i+1)
        election_dict["CreatedByName"] = (creator.FirstName + ' ' + (creator.MiddleName + ' ' if creator.MiddleName else '') + creator.LastName) if creator else ""
        
        # Return the OrganizationMemberRequirement of the election from the StudentOrganization table
        student_organization = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == election.StudentOrganizationId).first()
        election_dict["OrganizationMemberRequirement"] = student_organization.OrganizationMemberRequirements if student_organization else ""

        # Get the organization logo using secure_url from cloudinary stored in OrganizationLogo column
        election_dict["OrganizationLogo"] = student_organization.OrganizationLogo

        # Check if voting period is over
        if now >= election.VotingEnd.replace(tzinfo=timezone('Asia/Manila')):
            election_dict["IsVotingPeriodOver"] = True
        else:
            election_dict["IsVotingPeriodOver"] = False

        # Get the student in eligibles table with corresponding student number and election id
        is_eligible = db.query(Eligibles).filter(Eligibles.StudentNumber == student_number, Eligibles.ElectionId == election.ElectionId).first()

        if not is_eligible:
            election_dict["IsStudentEligible"] = False
        else:
            election_dict["IsStudentEligible"] = True

        # Check if the student's course matches the OrganizationMemberRequirement and it's within the voting period
        if student_course == election_dict["OrganizationMemberRequirement"] and is_eligible and now > election.VotingStart.replace(tzinfo=timezone('Asia/Manila')) and now < election.VotingEnd.replace(tzinfo=timezone('Asia/Manila')):
            atleast_one_available_election = True

        # Check if the student has voted in the election
        student_voted = db.query(VotingsTracker).filter(VotingsTracker.ElectionId == election.ElectionId, VotingsTracker.VoterStudentNumber == student_number).first()
        election_dict["IsStudentVoted"] = True if student_voted else False

        # Get the CreatedElectionPositions of the election then append it to the election_dict
        positions = db.query(CreatedElectionPosition).filter(CreatedElectionPosition.ElectionId == election.ElectionId).all()
        election_dict["Positions"] = [position.to_dict(i+1) for i, position in enumerate(positions)]

        elections_with_creator.append(election_dict)

    return {"elections": {"AtleastOneAvailableElection": atleast_one_available_election, "data": elections_with_creator}}
    
@router.get("/election/view/{id}", tags=["Election"])
def get_Election_By_Id(id: int, db: Session = Depends(get_db)):
    try:
        election = db.query(Election).get(id)

        if not election:
            return JSONResponse(status_code=404, content={"detail": "Election not found"})
        
        student_organization = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == election.StudentOrganizationId).first()
        
        # Get the student organization logo using secure_url from cloudinary stored in OrganizationLogo column
        organization_logo = student_organization.OrganizationLogo

        NumberOfCandidates = db.query(Candidates).filter(Candidates.ElectionId == election.ElectionId).count()
        NumberOfPartylists = db.query(PartyList).filter(PartyList.ElectionId == election.ElectionId, PartyList.Status == 'Approved').count()
        NumberOfPositions = db.query(CreatedElectionPosition).filter(CreatedElectionPosition.ElectionId == election.ElectionId).count()

        # See if the voting period is ongoing or over
        now = manila_now()
        is_voting_over = now > election.VotingEnd.replace(tzinfo=timezone('Asia/Manila'))

        positions = db.query(CreatedElectionPosition).filter(CreatedElectionPosition.ElectionId == id).order_by(CreatedElectionPosition.CreatedElectionPositionId).all()
        student_organization_name = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == election.StudentOrganizationId).first().OrganizationName

        organiztion_member_requirement = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == election.StudentOrganizationId).first().OrganizationMemberRequirements

        election_count = db.query(Election).count()
        return {"election": election.to_dict(election_count),
                "is_voting_period_over": is_voting_over,
                "organization_logo": organization_logo,
                "number_of_candidates": NumberOfCandidates,
                "number_of_partylists": NumberOfPartylists,
                "number_of_positions": NumberOfPositions,
                "student_organization_name": student_organization_name,
                "organization_member_requirement": organiztion_member_requirement,
                "positions": [position.to_dict(i+1) for i, position in enumerate(positions)]
                }
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching election from the database"})

@router.get("/election/position/reusable/all", tags=["Election"])    
def get_All_Election_Position_Reusable(db: Session = Depends(get_db)):
    try:
        positions = db.query(SavedPosition).order_by(SavedPosition.SavedPositionId).all()
        return {"positions": [position.to_dict() for position in positions]}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all positions from the database"})

@router.get("/election/{id}/approved/coc/all", tags=["Election"])
def get_All_Approved_Candidates_CoC_By_Election_Id(id: int, db: Session = Depends(get_db)):
    try:
        cocs = db.query(CoC).filter(CoC.ElectionId == id, CoC.Status == "Approved").order_by(CoC.CoCId).all()

        # Get the student row from student table using the student number in the coc
        cocs_with_student = []
        for i, coc in enumerate(cocs):
            student = db.query(Student).filter(Student.StudentNumber == coc.StudentNumber).first()
            coc_dict = coc.to_dict(i+1)
            coc_dict["Student"] = student.to_dict() if student else {}

            # Get the party list name from partylist table using the partylist id in the coc
            if coc.PartyListId:
                partylist = db.query(PartyList).filter(PartyList.PartyListId == coc.PartyListId).first()
                coc_dict["PartyListName"] = partylist.PartyListName if partylist else ""

            # Get the display photo from cloudinary using secure_url stored in DisplayPhoto column
            coc_dict["DisplayPhoto"] = coc.DisplayPhoto

            cocs_with_student.append(coc_dict)

        return {"cocs": cocs_with_student}

    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all approved coc from the database"})
    

""" ** POST Methods: All about election APIs ** """
# Create a queue
send_eligible_students_email_queue = asyncio.Queue()

# Define a worker function
async def send_eligible_students_email_worker():
    while True:
        # Get a task from the queue
        task = await send_eligible_students_email_queue.get()

        # Process the task
        student_number, student_email, pass_code = task

        # Run the send_eligible_students_email function in a separate thread
        await asyncio.to_thread(send_eligible_students_email, student_number, student_email, pass_code)

        # Indicate that the task is done
        send_eligible_students_email_queue.task_done()

# Set up the SMTP server
#server = setup_smtp_server()

# Start multiple workers in the background
for _ in range(3):  # Adjust the number of workers based on your resources
    asyncio.create_task(send_eligible_students_email_worker())

print(manila_now())

def fetch_all_student_statuses():
    db = SessionLocal()
    # Join Student and CourseEnrolled tables and fetch all student statuses
    students = db.query(Student.StudentNumber, CourseEnrolled.Status)\
        .join(CourseEnrolled, CourseEnrolled.StudentId == Student.StudentId)\
        .all()
    db.close()
    return dict(students)

@router.get("/election/get-all/student-statuses", tags=["Election"])
def get_all_student_statuses():
    return fetch_all_student_statuses()

def fetch_all_student_courses():
    db = SessionLocal()
    # Join Student, Course, and CourseEnrolled tables and fetch all student courses
    students = db.query(Student.StudentNumber, Course.CourseCode)\
        .join(CourseEnrolled, CourseEnrolled.StudentId == Student.StudentId)\
        .join(Course, Course.CourseId == CourseEnrolled.CourseId)\
        .all()
    db.close()
    return dict(students)

@router.get("/election/get-all/student-courses", tags=["Election"])
def get_all_student_courses():
    return fetch_all_student_courses()

@router.get("/election/students-status-0", tags=["Election"])
def get_students_status_0(db: Session = Depends(get_db)):
    # Count how many students have status 0 and course is BSIT
    students = db.query(Student.StudentNumber)\
        .join(CourseEnrolled, CourseEnrolled.StudentId == Student.StudentId)\
        .filter(CourseEnrolled.Status == 0, CourseEnrolled.CourseId == 7)\
        .all()
    
    return {"students": [student.StudentNumber for student in students], "count": len(students)}

@router.post("/election/create", tags=["Election"])
async def save_election(election_data: CreateElectionData, db: Session = Depends(get_db)):
    new_election = Election(ElectionName=election_data.election_info.election_name,
                            StudentOrganizationId=election_data.election_info.election_type,
                            ElectionStatus="Active",
                            SchoolYear=election_data.election_info.school_year,
                            Semester=election_data.election_info.semester,
                            CreatedBy=election_data.election_info.created_by,
                            ElectionStart=election_data.election_info.election_start,
                            ElectionEnd=election_data.election_info.election_end,
                            CoCFilingStart=election_data.election_info.filing_coc_start,
                            CoCFilingEnd=election_data.election_info.filing_coc_end,
                            CampaignStart=election_data.election_info.campaign_start,
                            CampaignEnd=election_data.election_info.campaign_end,
                            VotingStart=election_data.election_info.voting_start,
                            VotingEnd=election_data.election_info.voting_end,
                            AppealStart=election_data.election_info.appeal_start,
                            AppealEnd=election_data.election_info.appeal_end,
                            created_at=manila_now(), 
                            updated_at=manila_now())
    db.add(new_election)
    db.commit()

    new_election_analytics = ElectionAnalytics(ElectionId=new_election.ElectionId,
                                                AbstainCount=0,
                                                VotesCount=0,
                                                created_at=manila_now(), 
                                                updated_at=manila_now())
    db.add(new_election_analytics)
    db.commit()

    for position in election_data.positions:
        new_position = CreatedElectionPosition(ElectionId=new_election.ElectionId,
                                                PositionName=position.value,
                                                PositionQuantity=position.quantity,
                                                created_at=manila_now(), 
                                                updated_at=manila_now())
        db.add(new_position)
        db.commit()

    # Insert students to eligibles table if matches with student organization member requirement or if the student org requirement is any course
    student_organization = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == new_election.StudentOrganizationId).first()
    
    student_emails_to_find = ["iammeliodas123@gmail.com", 
                              "iammeliodas12345@gmail.com", 
                              "iammeliodas123456@gmail.com",
                              "student2.sge@gmail.com",
                              "student3.sge@gmail.com"]

    if student_organization.OrganizationMemberRequirements == "Any":
        students = db.query(Student).all()
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        new_eligibles = []

        # Get all student statuses at once
        student_statuses = fetch_all_student_statuses()

        for student in students:
            # Use the dictionary to check the student's status
            if student_statuses.get(student.StudentNumber) == 0:

                pass_value = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
                hashed_password = pwd_context.hash(pass_value)
                student_email = student.Email

                new_eligible = Eligibles(ElectionId=new_election.ElectionId,
                                        StudentNumber=student.StudentNumber,
                                        HasVotedOrAbstained=False,
                                        VotingPassword=hashed_password,
                                        created_at=manila_now(), 
                                        updated_at=manila_now())
                new_eligibles.append(new_eligible)

                #await send_eligible_students_email_queue.put((student.StudentNumber, student_email, pass_value))
                send_eligible_students_email_queue.put_nowait((student.StudentNumber, student_email, pass_value))

        db.add_all(new_eligibles)
        db.commit()
    
    # If the student organization member requirement is not any course, insert students to eligibles table if matches with student organization member requirement
    else:
        students = db.query(Student).all()
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        new_eligibles = []

        # Get all student statuses and courses at once
        student_statuses = fetch_all_student_statuses()
        student_courses = fetch_all_student_courses()

        for student in students:
            # Use the dictionaries to check the student's status and course
            if student_statuses.get(student.StudentNumber) == 0 and \
            student_courses.get(student.StudentNumber) == student_organization.OrganizationMemberRequirements:

                pass_value = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
                hashed_password = pwd_context.hash(pass_value)
                student_email = student.Email

                new_eligible = Eligibles(ElectionId=new_election.ElectionId,
                                        StudentNumber=student.StudentNumber,
                                        HasVotedOrAbstained=False,
                                        VotingPassword=hashed_password,
                                        created_at=manila_now(), 
                                        updated_at=manila_now())
                new_eligibles.append(new_eligible)

                #await send_eligible_students_email_queue.put((student.StudentNumber, student_email, pass_value))
                send_eligible_students_email_queue.put_nowait((student.StudentNumber, student_email, pass_value))

        db.add_all(new_eligibles)
        db.commit()

    # Schedule the get_winners function to run at election.VotingEnd
    try:
        trigger = DateTrigger(run_date=new_election.VotingEnd, timezone=timezone('Asia/Manila'))
        scheduler.add_job(gather_winners_by_election_id, trigger=trigger, id=f'gather_winners_{new_election.ElectionId}', args=[new_election.ElectionId])
        print("Scheduled!")
    except Exception as e:
        print(f"Error while scheduling: {e}")

    return {"message": "Election created successfully",
            "election_id": new_election.ElectionId,}


@router.post("/election/position/reusable/save", tags=["Election"])
async def save_Election_Position_Reusable(data: SaveReusablePositionData, db: Session = Depends(get_db)):
    capitalized_first_letter = data.name.capitalize()
    new_position = SavedPosition(PositionName=capitalized_first_letter,
                                            created_at=manila_now(),
                                            updated_at=manila_now())
    db.add(new_position)
    db.commit()

    return {"message": f"Position {capitalized_first_letter} is now re-usable."}

@router.delete("/election/position/reusable/delete", tags=["Election"])
def delete_Election_Position_Reusable(data: SaveReusablePositionData, db: Session = Depends(get_db)):
    capitalized_first_letter = data.name.capitalize()
    position = db.query(SavedPosition).filter(SavedPosition.PositionName == capitalized_first_letter).first()

    if not position:
        return {"error": "Position not found"}

    db.delete(position)
    db.commit()

    return {"message": f"Position {capitalized_first_letter} is not re-usable anymore."}

def delete_rows(db: Session, table, election_id: int):
    rows = db.query(table).filter(table.ElectionId == election_id).all()
    for row in rows:
        db.delete(row)
    db.commit()

@router.post("/election/delete", tags=["Election"])
def delete_Election(data: ElectionDelete, db: Session = Depends(get_db)):
    election = db.query(Election).filter(Election.ElectionId == data.id).first()
    if not election:
        return {"error": "Election not found"}

    # DELETE ALL REFERENCED ROWS with the election id
    tables = [CreatedElectionPosition, CoC, ElectionAnalytics, Candidates, PartyList, RatingsTracker, VotingsTracker, Eligibles, ElectionWinners]
    for table in tables:
        delete_rows(db, table, data.id)

    # FINALLY DELETE ELECTION with the election id
    db.delete(election)
    db.commit()

    return {"message": f"Election {election.ElectionName} was deleted successfully."}

#################################################################
""" Announcement Table APIs """

class AnnouncementDeleteData(BaseModel):
    id: int

""" ** GET Methods: Announcement Table APIs ** """

@router.get("/announcement/all", tags=["Announcement"])
def get_All_Announcement(include_images: Optional[bool] = False, db: Session = Depends(get_db)):
    try:
        # Get by descending order
        announcements = db.query(Announcement).order_by(desc(Announcement.AnnouncementId)).all()
        return {"announcements": [announcement.to_dict(i+1, include_images=include_images) for i, announcement in enumerate(announcements)]} # Return the row number as well
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all announcements from the database"})
    
@router.get("/announcement/ascending/all", tags=["Announcement"])
def get_All_Announcement(include_images: Optional[bool] = False, db: Session = Depends(get_db)):
    try:
        # Get by descending order
        announcements = db.query(Announcement).order_by(asc(Announcement.AnnouncementId)).all()
        return {"announcements": [announcement.to_dict(i+1, include_images=include_images) for i, announcement in enumerate(announcements)]} # Return the row number as well
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all announcements from the database"})
    
@router.get("/announcement/{type}", tags=["Announcement"])
def get_Announcement_By_Type(type: str, include_images: Optional[bool] = False, db: Session = Depends(get_db)):
    try:
        announcements = db.query(Announcement).filter(Announcement.AnnouncementType == type).order_by(desc(Announcement.AnnouncementId)).all()
        return {"announcements": [announcement.to_dict(i+1, include_images=include_images) for i, announcement in enumerate(announcements)]}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching announcements from the database"})
    
@router.get("/announcement/get/{id}", tags=["Announcement"])
def get_Announcement_By_Id(id: int, include_images: Optional[bool] = False, db: Session = Depends(get_db)):
    try:
        announcement = db.query(Announcement).get(id)

        if not announcement:
            return JSONResponse(status_code=404, content={"detail": "Announcement not found"})

        return {"announcement": announcement.to_dict(include_images=include_images)}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching announcement from the database"})
    
@router.get("/announcement/get/attachment/{id}", tags=["Announcement"])
def get_Announcement_Attachment_By_Id(id: int, db: Session = Depends(get_db)):
    try:
        announcement = db.query(Announcement).get(id)

        if not announcement:
            return JSONResponse(status_code=404, content={"detail": "Announcement not found"})

        tag_name = announcement.AttachmentImage

        if tag_name:
            try:
                # Search for images with the tag using the Admin API
                response = resources_by_tag(tag_name)

                # Get the URLs and file names of the images
                images = [{"url": resource['secure_url'], 
                        "name": resource['public_id'].split('/')[-1]} for resource in response['resources']]

                return {"images": images}
            except Exception as e:
                print(f"Error fetching image from Cloudinary: {e}")
                return {"images": []}
        
        return {"images": []}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching announcement attachment from the database"})
        
@router.get("/announcement/count/latest", tags=["Announcement"])
def get_Announcement_Latest_Count(db: Session = Depends(get_db)):
    try:
        count = db.query(Announcement).count()
        return {"count": count}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching latest announcement count from the table Announcement"})
    
""" ** POST Methods: Announcement Table APIs ** """

@router.post("/announcement/save", tags=["Announcement"])
async def save_Announcement(type_select: str = Form(...), title_input: str = Form(...), body_input: str = Form(...), 
                            type_of_attachment: Optional[str] = Form(None), attachment_images: List[UploadFile] = File(None), 
                            db: Session = Depends(get_db)):
    
    # Create a new announcement with an empty string as the initial AttachmentImage
    new_announcement = Announcement(
        AnnouncementType=type_select, 
        AnnouncementTitle=title_input, 
        AnnouncementBody=body_input,
        AttachmentType=type_of_attachment,
        AttachmentImage='',  # Initialize with an empty string
        created_at=manila_now(), 
        updated_at=manila_now()
    )

    db.add(new_announcement)
    db.commit()

    try:
        if attachment_images:
            # Use the ID of the new announcement as the subfolder name under 'Announcements'            
            folder_name = f"Announcements/announcement_{new_announcement.AnnouncementId}"

            for attachment_image in attachment_images:
                contents = await attachment_image.read()
                filename = attachment_image.filename

                # Upload file to Cloudinary with the folder name in the public ID
                response = cloudinary.uploader.upload(contents, public_id=f"{folder_name}/{filename}", tags=[f'announcement_{new_announcement.AnnouncementId}'])

                # Store the URL in the AttachmentImage column
                new_announcement.AttachmentImage = f'announcement_{new_announcement.AnnouncementId}'
                db.commit()
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while uploading attachment to Cloudinary"})

    return {
        "id": new_announcement.AnnouncementId,
        "type": new_announcement.AnnouncementType,
        "title": new_announcement.AnnouncementTitle,
        "body": new_announcement.AnnouncementBody,
        "attachment_type": new_announcement.AttachmentType,
        "attachment_image": new_announcement.AttachmentImage,
    }

@router.put("/announcement/update", tags=["Announcement"])
async def update_Announcement(id_input: int = Form(...), type_select: str = Form(...), title_input: str = Form(...), body_input: str = Form(...), 
                            type_of_attachment: Optional[str] = Form(None), attachment_images: List[UploadFile] = File(None),
                            new_files: List[UploadFile] = File(None), removed_files: List[UploadFile] = File(None),
                            db: Session = Depends(get_db), attachments_modified: bool = Form(False)):
    
    try:
        original_announcement = db.query(Announcement).get(id_input)

        if not original_announcement:
            return {"error": "Announcement not found"}

        # Use the ID of the announcement as the tag
        tag_name = original_announcement.AttachmentImage if original_announcement.AttachmentImage else "announcement_" + str(original_announcement.AnnouncementId)
        folder_name = f"Announcements/{tag_name}"

        if removed_files and attachments_modified:
            # Check for removed files
            for removed_file in removed_files:
                # This is a removed file, delete it from Cloudinary
                file_path = f"{folder_name}/{removed_file.filename}"
                cloudinary.uploader.destroy(file_path)

        uploaded_files = []

        if new_files and attachments_modified:
            # Check for new files
            for new_file in new_files:
                # This is a new file, upload it to Cloudinary
                contents = await new_file.read()
                filename = new_file.filename

                # Upload file to Cloudinary with the folder name in the public ID
                response = cloudinary.uploader.upload(contents, public_id=f"{folder_name}/{filename}", tags=[tag_name])

                # Add the name and URL of the uploaded file to the list
                uploaded_files.append({
                    'name': filename,
                    'url': response['url']
                })

            original_announcement.AttachmentImage = tag_name

        if type_of_attachment == 'None' and original_announcement.AttachmentImage:
            # Delete all images with the tag
            delete_resources_by_tag(tag_name)

            # Delete the folder in Cloudinary
            delete_folder(folder_name)

            original_announcement.AttachmentImage = ''

        # Update the announcement in the database
        original_announcement.AnnouncementType = type_select
        original_announcement.AnnouncementTitle = title_input
        original_announcement.AnnouncementBody = body_input
        original_announcement.AttachmentType = type_of_attachment
        original_announcement.updated_at = manila_now()

        db.commit()
        
        return {
            "id": original_announcement.AnnouncementId,
            "type": original_announcement.AnnouncementType,
            "title": original_announcement.AnnouncementTitle,
            "body": original_announcement.AnnouncementBody,
            "attachment_type": original_announcement.AttachmentType if original_announcement.AttachmentType else 'None',
            "attachment_image": original_announcement.AttachmentImage if original_announcement.AttachmentImage else '',
            "uploaded_files": uploaded_files,  
        }
    
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while updating announcement in the table Announcement"})

@router.delete("/announcement/delete", tags=["Announcement"])
def delete_Announcement(announcement_data: AnnouncementDeleteData, db: Session = Depends(get_db)):
    try:
        announcement = db.query(Announcement).get(announcement_data.id)

        if not announcement:
            return {"error": "Announcement not found"}

        if announcement.AttachmentImage:
            folder_name = f"Announcements/announcement_{announcement.AnnouncementId}"
            tag_name = f'announcement_{announcement.AnnouncementId}'

            # Delete all images with the tag
            response = delete_resources_by_tag(tag_name)

            # Check if the request was successful
            if 'result' in response and response['result'] != 'ok':
                return JSONResponse(status_code=500, content={"detail": "Failed to delete images"})

            # Delete the folder in Cloudinary
            response = delete_folder(folder_name)

            # Check if the request was successful
            if 'result' in response and response['result'] != 'ok':
                return JSONResponse(status_code=500, content={"detail": "Failed to delete folder"})
        
        db.delete(announcement)
        db.commit()
        
        return {"detail": "Announcement id " + str(announcement_data.id) + " was successfully deleted)"}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while deleting announcement from the table Announcement"})
  
    
#################################################################
""" Rule Table APIs """

class RuleSaveData(BaseModel):
    title: str
    body: str

class RuleUpdateData(BaseModel):
    id: int
    title: str
    body: str

class RuleDeleteData(BaseModel):
    id: int

""" ** GET Methods: Rule Table APIs ** """

@router.get("/rule/all", tags=["Rule"])
def get_All_Rules(db: Session = Depends(get_db)):
    try:
        rules = db.query(Rule).order_by(Rule.RuleId).all()
        return {"rules": [rule.to_dict(i+1) for i, rule in enumerate(rules)]}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all rules from the database"})

@router.get("/rule/count/latest", tags=["Rule"])
def get_Rule_Latest_Count(db: Session = Depends(get_db)):
    try:
        count = db.query(Rule).count()
        return {"count": count}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching latest rule count from the table Rule"})

""" ** POST Methods: Rule Table APIs ** """

@router.post("/rule/save", tags=["Rule"])
def save_Rule(rule_data: RuleSaveData, db: Session = Depends(get_db)):
    try:
        new_rule = Rule(RuleTitle=rule_data.title, 
                        RuleBody=rule_data.body, 
                        created_at=manila_now(), 
                        updated_at=manila_now())
        db.add(new_rule)
        db.commit()
        return {"id": new_rule.RuleId,
                "type": "rule",
                "title": new_rule.RuleTitle,
                "body": new_rule.RuleBody,
                "created_at": new_rule.created_at.isoformat() if new_rule.created_at else None,
                "updated_at": new_rule.updated_at.isoformat() if new_rule.updated_at else None
                }
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while creating new rule in the table Rule"})
    
@router.put("/rule/update", tags=["Rule"])
def update_Rule(rule_data: RuleUpdateData, db: Session = Depends(get_db)):
    try:
        rule = db.query(Rule).get(rule_data.id)
        
        # If the rule does not exist, return a 404 error
        if not rule:
            return JSONResponse(status_code=404, content={"detail": "Rule not found"})
        
        # Update the rule's title and body
        rule.RuleTitle = rule_data.title
        rule.RuleBody = rule_data.body
        rule.updated_at = manila_now()
        
        db.commit()

        return {"id": rule.RuleId,
                "type": "rule",
                "title": rule.RuleTitle,
                "body": rule.RuleBody,
                "created_at": rule.created_at.isoformat() if rule.created_at else None,
                "updated_at": rule.updated_at.isoformat() if rule.updated_at else None
                }
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while updating rule in the table Rule"})
    
@router.delete("/rule/delete", tags=["Rule"])
def delete_Rule(rule_data: RuleDeleteData, db: Session = Depends(get_db)):
    try:
        rule = db.query(Rule).get(rule_data.id)
        
        # If the rule does not exist, return a 404 error
        if not rule:
            return JSONResponse(status_code=404, content={"detail": "Rule not found"})
        
        db.delete(rule)
        db.commit()

        return {"detail": "Rule id " + str(rule_data.id) + " was successfully deleted"}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while deleting rule from the table Rule"})


#################################################################
""" Guideline Table APIs """

class GuidelineSaveData(BaseModel):
    title: str
    body: str

class GuidelineUpdateData(BaseModel):
    id: int
    title: str
    body: str

class GuidelineDeleteData(BaseModel):
    id: int

""" ** GET Methods: Guideline Table APIs ** """

@router.get("/guideline/all", tags=["Guideline"])
def get_All_Guidelines(db: Session = Depends(get_db)):
    try:
        guidelines = db.query(Guideline).order_by(Guideline.GuideId).all()
        return {"guidelines": [guideline.to_dict(i+1) for i, guideline in enumerate(guidelines)]}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all guidelines from the database"})

@router.get("/guideline/count/latest", tags=["Guideline"])
def get_Guideline_Latest_Count(db: Session = Depends(get_db)):
    try:
        count = db.query(Guideline).count()
        return {"count": count}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching latest guideline count from the table Guideline"})
    
""" ** POST Methods: Guideline Table APIs ** """

@router.post("/guideline/save", tags=["Guideline"])
def save_Guideline(guideline_data: GuidelineSaveData, db: Session = Depends(get_db)):
    try:
        new_guideline = Guideline(GuidelineTitle=guideline_data.title, 
                                GuidelineBody=guideline_data.body, 
                                created_at=manila_now(), 
                                updated_at=manila_now())
        db.add(new_guideline)
        db.commit()
        return {"id": new_guideline.GuideId,
                "type": "guideline",
                "title": new_guideline.GuidelineTitle,
                "body": new_guideline.GuidelineBody,
                "created_at": new_guideline.created_at.isoformat() if new_guideline.created_at else None,
                "updated_at": new_guideline.updated_at.isoformat() if new_guideline.updated_at else None
                }
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while creating new guideline in the table Guideline"})
    
@router.put("/guideline/update", tags=["Guideline"])
def update_Guideline(guideline_data: GuidelineUpdateData, db: Session = Depends(get_db)):
    try:
        guideline = db.query(Guideline).get(guideline_data.id)
        
        # If the guideline does not exist, return a 404 error
        if not guideline:
            return JSONResponse(status_code=404, content={"detail": "Guideline not found"})
        
        # Update the guideline's title and body
        guideline.GuidelineTitle = guideline_data.title
        guideline.GuidelineBody = guideline_data.body
        guideline.updated_at = manila_now()
        
        db.commit()

        return {"id": guideline.GuideId,
                "type": "guideline",
                "title": guideline.GuidelineTitle,
                "body": guideline.GuidelineBody,
                "created_at": guideline.created_at.isoformat() if guideline.created_at else None,
                "updated_at": guideline.updated_at.isoformat() if guideline.updated_at else None
                }
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while updating guideline in the table Guideline"})
    
@router.delete("/guideline/delete", tags=["Guideline"])
def delete_Guideline(guideline_data: GuidelineDeleteData, db: Session = Depends(get_db)):
    try:
        guideline = db.query(Guideline).get(guideline_data.id)
        
        # If the guideline does not exist, return a 404 error
        if not guideline:
            return JSONResponse(status_code=404, content={"detail": "Guideline not found"})
        
        db.delete(guideline)
        db.commit()
        
        return {"detail": "Guideline id " + str(guideline_data.id) + " was successfully deleted)"}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while deleting guideline from the table Guideline"})
    
#################################################################
""" Certifications Table APIs """

class SignatoryData(BaseModel):
    name: str
    position: str

class CertificationData(BaseModel):
    title: str
    election_id: int
    date: date
    quantity: str
    signatories: List[SignatoryData]

""" ** GET Methods: Certifications Table APIs ** """
@router.get("/certification/all", tags=["Certification"])
def get_All_Certification(db: Session = Depends(get_db)):
    try:
        certifications = db.query(Certifications).order_by(Certifications.CertificationId).all()
        certifications_with_election = []

        for i, certification in enumerate(certifications):
            election = db.query(Election).filter(Election.ElectionId == certification.ElectionId).first()
            certification_dict = certification.to_dict()
            certification_dict["ElectionName"] = election.ElectionName if election else ""

            certifications_with_election.append(certification_dict)

        return {"certifications": certifications_with_election}
    
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all certifications from the database"})

def remove_file(path: str):
    os.remove(path)

@router.get("/certification/preview/{id}", tags=["Certification"])
def preview_Certification(id: int, db: Session = Depends(get_db)):
    certification = db.query(Certifications).get(id)

    if not certification:
        return JSONResponse(status_code=404, content={"detail": "Certification not found"})

    try:
        if certification.AssetId:
            pdf_certificate = certification.AssetId

            return {"pdf": pdf_certificate}
        else:
            print("No resources found")
            return {"pdf": ''}
    except Exception as e:
        print(f"Error fetching pdf from Cloudinary: {e}")
        return {"pdf": ''}

@router.get("/certification/download/{id}", tags=["Certification"])
def download_Certification(id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    certification = db.query(Certifications).get(id)

    if not certification:
        return JSONResponse(status_code=404, content={"detail": "Certification not found"})

    try:
        if certification.AssetId:
            pdf_certificate = certification.AssetId

            # Download the pdf
            pdf = requests.get(pdf_certificate)

            # Save the pdf with student number as filename
            filename = f"{certification.StudentNumber}.pdf"
            with open(filename, 'wb') as f:
                f.write(pdf.content)

            # Schedule the file to be deleted after the response is sent
            background_tasks.add_task(remove_file, filename)

            # Return the pdf
            return FileResponse(filename, media_type="application/pdf", filename=filename)
        else:
            print("No resources found")
            return {"pdf": ''}
    except Exception as e:
        print(f"Error fetching pdf from Cloudinary: {e}")
        return {"pdf": ''}
    
@router.get("/certification/signed/all", tags=["Certification"])
def get_All_Signed_Certification(db: Session = Depends(get_db)):
    certifications_signed = db.query(CertificationsSigned).all()

    return {"certifications_signed": [certification_signed.to_dict() for i, certification_signed in enumerate(certifications_signed)]}

@router.get("/certification/signed/preview/{id}", tags=["Certification"])
def preview_Signed_Certification(id: int, db: Session = Depends(get_db)):
    certification_signed = db.query(CertificationsSigned).get(id)

    if not certification_signed:
        return JSONResponse(status_code=404, content={"detail": "Certification not found"})

    return {"pdf": certification_signed.FileURL}

@router.get("/certification/signed/download/{id}", tags=["Certification"])
def download_Signed_Certification(id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    certification_signed = db.query(CertificationsSigned).get(id)

    if not certification_signed:
        return JSONResponse(status_code=404, content={"detail": "Certification not found"})

    # Download the pdf
    pdf = requests.get(certification_signed.FileURL)

    # Save the pdf with student number as filename
    filename = f"{certification_signed.CertificationTitle}.pdf"
    with open(filename, 'wb') as f:
        f.write(pdf.content)

    # Schedule the file to be deleted after the response is sent
    background_tasks.add_task(remove_file, filename)

    # Return the pdf
    return FileResponse(filename, media_type="application/pdf", filename=filename)

""" ** POST Methods: Certifications Table APIs ** """
class SignatureLine(Flowable):
    def __init__(self, width):
        Flowable.__init__(self)
        self.width = width

    def draw(self):
        self.canv.line(self.width, 0, 0, 0)  # Start from the right and extend to the left

@router.post("/certification/create", tags=["Certification"])
def create_Certification(certification_data: CertificationData, db: Session = Depends(get_db)):
    # Fetch the election winners from the ElectionWinners table using the election id and must not tied
    election_winners = db.query(ElectionWinners).filter(ElectionWinners.ElectionId == certification_data.election_id).filter(ElectionWinners.IsTied == False).all()

    # Iterate over each election winner
    for winner in election_winners:
        # Fetch the student from the Student table
        student = db.query(Student).filter(Student.StudentNumber == winner.StudentNumber).first()

        # Get student full name and consider the middle name
        winner_full_name = f"{student.FirstName} {student.MiddleName} {student.LastName}" if student.MiddleName else f"{student.FirstName} {student.LastName}"

        # Get student selected position
        winner_position = winner.SelectedPositionName

        new_certification = Certifications(Title=certification_data.title,
                                            ElectionId=certification_data.election_id,
                                            StudentNumber=student.StudentNumber,
                                            Date=certification_data.date,
                                            AdminSignatoryQuantity=certification_data.quantity,
                                            AssetId='', # Initialize first
                                            created_at=manila_now(),
                                            updated_at=manila_now())
        db.add(new_certification)
        db.commit()

        for signatory in certification_data.signatories:
            new_signatory = CreatedAdminSignatory(CertificationId=new_certification.CertificationId,
                                        SignatoryName=signatory.name,
                                        SignatoryPosition=signatory.position,
                                        created_at=manila_now(),
                                        updated_at=manila_now())
            db.add(new_signatory)
            db.commit()

        # Create the PDF
        now = manila_now()
        pdf_name = f"Report_{now.strftime('%Y%m%d_%H%M%S')}.pdf"
        doc = SimpleDocTemplate(pdf_name, pagesize=letter, topMargin=36)

        # Get the default style sheet
        styles = getSampleStyleSheet()

        # Create a list to hold the PDF elements
        elements = []

        # Styles
        styles.add(ParagraphStyle(name="SchoolStyle", fontName="Times-Roman", fontSize=18, alignment=TA_CENTER, spaceAfter=10))
        styles.add(ParagraphStyle(name="BranchStyle", fontSize=16, alignment=TA_CENTER, spaceAfter=18))
        styles.add(ParagraphStyle(name="TitleStyle", fontName="Times-Roman", bold=True, fontSize=24, alignment=TA_CENTER, spaceAfter=26))
        styles.add(ParagraphStyle(name="ParagraphStyle", fontName="Times-Roman", fontSize=12, alignment=TA_JUSTIFY, spaceAfter=6, leading=12, firstLineIndent=36))
        styles.add(ParagraphStyle(name="ParagraphStyle2", fontName="Times-Roman", fontSize=12, alignment=TA_LEFT, spaceAfter=6, leading=12))

        # Add the logo
        logo = Image("puplogo.png", width=80, height=80)  # Adjust the path and size as needed
        elements.append(logo)
        elements.append(Spacer(1, 12))

        school = Paragraph("Polytechnic University of the Philippines", styles["SchoolStyle"])
        elements.append(school)
        elements.append(Spacer(1, 2))

        branch = Paragraph("QUEZON CITY CAMPUS", styles["BranchStyle"])
        elements.append(branch)
        elements.append(Spacer(1, 12))

        date = Paragraph('<para align="right">' + certification_data.date.strftime("%B %d, %Y") + '</para>', styles["Normal"])
        elements.append(date)
        elements.append(Spacer(1, 24))

        title = Paragraph("<b>OATH OF OFFICE</b>", styles["TitleStyle"])
        elements.append(title)
        elements.append(Spacer(1, 12))

        # Add the first part of the content (justified)
        text = f'''
        \tI, <b>{winner_full_name}</b>, having been elected as <b>{winner_position}</b> of
        the Supreme Student Council of the Polytechnic University of
        the Philippines, Quezon City do solemnly swear that:
        '''
        paragraph = Paragraph(text, styles["ParagraphStyle"])
        elements.append(paragraph)
        elements.append(Spacer(1, 12))

        # Add the second part of the content
        text = f'''
            I will maintain allegiance to the Republic of the Philippines<br/>
            I will abide by laws of the Supreme Student Council and the<br/>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Polytechnic University Of The Philippines;<br/>
            I will perform my duties and responsibilities as <b>{winner_position}</b>,<br/>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;and conduct myself as a true professional according to<br/>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;best of my duty knowledge and discretion.<br/>

            So help me God.
            '''
        paragraph = Paragraph(text, styles["ParagraphStyle2"])
        paragraph_table = Table([[paragraph]], colWidths=[300], hAlign='CENTER')  # Adjust the column width as needed
        elements.append(paragraph_table)
        elements.append(Spacer(1, 28))

        # Add signature of the current winner and his position
        signature_line = SignatureLine(130)  # Adjust the width as needed
        signature_name = Paragraph('<para align="center">' + winner_full_name + '<br/>' + winner_position + '</para>', styles["Normal"])
        signature_table = Table([[signature_line], [signature_name]], colWidths=[140], hAlign='RIGHT')  # Adjust the column width as needed
        elements.append(signature_table)
        elements.append(Spacer(1, 28))

        # Add the signatures (right-aligned with a line for the signature)
        for i, signatory in enumerate(certification_data.signatories):
            # Signature line and name
            signature_line = SignatureLine(130)  # Adjust the width as needed
            signature_name = Paragraph('<para align="center">' + signatory.name + '<br/>' + signatory.position + '</para>', styles["Normal"])
            signature_table = Table([[signature_line], [signature_name]], colWidths=[140], hAlign='RIGHT')  # Adjust the column width as needed
            elements.append(signature_table)
            elements.append(Spacer(1, 28))

        # Build the PDF
        doc.build(elements)

        # Upload to cloudinary
        upload_result = cloudinary.uploader.upload(pdf_name, 
                               resource_type = "raw", 
                               public_id = f"Directory/Certifications/{pdf_name}",
                               tags=[f'certification_{new_certification.CertificationId}'])
        
        new_certification.AssetId = upload_result['secure_url']
        db.commit()

        # Delete the local file
        os.remove(pdf_name)

    # Return the responses and a URL to download the PDF
    return JSONResponse({
        "message": "Certifications created successfully"
    })

@router.post("/certification/signed/upload", tags=["Certification"])
async def upload_Signed_Certification(files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    if not os.path.exists('temp'):
        os.makedirs('temp')

    for file in files:
        # Save the file to a temporary location
        temp_file = f"temp/{file.filename}"
        with open(temp_file, "wb") as buffer:
            buffer.write(await file.read())

        # Create a new row in the CertificationsSigned table
        new_certification = CertificationsSigned(CertificationTitle=file.filename,
                                                 DateUploaded=manila_now(),
                                                 created_at=manila_now(),
                                                 updated_at=manila_now())  # Add other fields as needed
        db.add(new_certification)
        db.commit()

        # Upload the file to Cloudinary
        upload_result = cloudinary.uploader.upload(temp_file, 
                               resource_type = "raw", 
                               public_id = f"Directory/Certifications/Signed/{file.filename}",
                               tags=[f'certification_signed_{new_certification.CertificationsSignedId}'])
        
        # Associate the upload_result to the row of the file created in the table
        new_certification.FileURL = upload_result['secure_url']
        db.commit()

        # Delete the temporary file
        os.remove(temp_file)

    return {"response": "success"}

@router.delete("/certification/signed/delete/{certificate_id}", tags=["Certification"])
def delete_Signed_Certification(certificate_id: int, db: Session = Depends(get_db)):
    certification = db.query(CertificationsSigned).get(certificate_id)

    if not certification:
        return JSONResponse(status_code=404, content={"detail": "Certification not found"})

    # The public ID is the last component of the path, without the file extension
    public_id = "Directory/Certifications/Signed/" + certification.CertificationTitle

    # Delete the file from Cloudinary
    cloudinary.uploader.destroy(public_id, resource_type="raw")

    # Delete the row from the table
    db.delete(certification)
    db.commit()
    return {"detail": "Certification id " + str(certificate_id) + " was successfully deleted"}

#################################################################
## Organizations APIs ## 
class OrganizationName(BaseModel):
    name: str

""" Organization Election Table APIs """

""" ** GET Methods: All about orgnanization election APIs ** """

""" ** POST Methods: All about orgnanization election APIs ** """

#################################################################
## CoC APIs ## 

""" CoC Table APIs """

""" ** GET Methods: CoC Table APIs ** """
@router.get("/coc/all", tags=["CoC"])
def get_All_CoC(db: Session = Depends(get_db)):
    try:
        coc = db.query(CoC).order_by(CoC.CoCId).all()
        coc_dict = [coc.to_dict(i+1) for i, coc in enumerate(coc)]

        # Include the election name using the election id in the CoC dictionary
        for coc in coc_dict:
            if coc["ElectionId"]:
                election = db.query(Election).filter(Election.ElectionId == coc["ElectionId"]).first()
                coc["ElectionName"] = election.ElectionName if election else None

                # Get the studentorganizationname from studentorganization table using the election table's studentorganizationid to look at studentorganizationname
                student_organization = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == election.StudentOrganizationId).first()
                coc["StudentOrganizationName"] = student_organization.OrganizationName if student_organization else None

        return {"coc": coc_dict}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all CoCs from the database"})
    
@router.get("/coc/{id}", tags=["CoC"])
def get_CoC_By_Id(id: int, db: Session = Depends(get_db)):
    try:
        coc = db.query(CoC).get(id)

        if not coc:
            return JSONResponse(status_code=404, content={"detail": "CoC not found"})
        
        # Get the student from the Student table using the student number in the CoC table
        student = db.query(Student).filter(Student.StudentNumber == coc.StudentNumber).first()
       
        # Include student details in the CoC dictionary
        coc_dict = coc.to_dict()

        # Include the election name using the election id in the CoC dictionary
        if coc.ElectionId:
            election = db.query(Election).filter(Election.ElectionId == coc.ElectionId).first()
            coc_dict["ElectionName"] = election.ElectionName if election else None

            student_organization = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == election.StudentOrganizationId).first()
            coc_dict["StudentOrganizationName"] = student_organization.OrganizationName if student_organization else None

        # Include the party list name using the party list id in the CoC dictionary
        if coc.PartyListId:
            party_list = db.query(PartyList).filter(PartyList.PartyListId == coc.PartyListId).first()
            coc_dict["PartyListName"] = party_list.PartyListName if party_list else None

        # Include image URLs in the CoC dictionary using the secure URL from Cloudinary
        coc_dict["DisplayPhoto"] = coc.DisplayPhoto
        coc_dict["CertificationOfGrades"] = coc.CertificationOfGrades

        coc_dict["Student"] = student.to_dict() if student else None
        student_metadata = get_Student_Metadata_by_studnumber(student.StudentNumber)

        if "CourseCode" in student_metadata:
            coc_dict["Student"]["CourseCode"] = student_metadata["CourseCode"]
            coc_dict["Student"]["Year"] = student_metadata["Year"]
            coc_dict["Student"]["Semester"] = student_metadata["Semester"]

        student_section = get_Student_Section_by_studnumber(student.StudentNumber)

        if student_section:
            coc_dict["Student"]["Section"] = student_section

        coc_dict["Student"]["ClassGrade"] = get_Student_Class_Grade_by_studnumber(student.StudentNumber)
        
        return {"coc": coc_dict}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching CoC from the database"})

""" ** POST Methods: All about CoC Table APIs ** """
@router.post("/coc/submit", tags=["CoC"])
async def save_CoC(election_id: int = Form(...), student_number: str = Form(...),
                   verification_code: str = Form(...), motto: Optional[str] = Form(None), platforms: Optional[str] = Form(...),
                   political_affiliation: str = Form(...), party_list: Optional[str] = Form(None),
                   position: str = Form(...), display_photo: str = Form(...),
                   display_photo_file_name : str = Form(...), certification_of_grades_file_name: str = Form(...),
                   certification_of_grades: str = Form(...), db: Session = Depends(get_db)):

    # Check if current datetime is within the filing period of the election
    election = db.query(Election).filter(Election.ElectionId == election_id).first()
    
    if manila_now() > election.CoCFilingEnd.replace(tzinfo=timezone('Asia/Manila')):
        return JSONResponse(status_code=400, content={"error": "Filing period for this election has ended."})
    
    # Check if the student exists in IncidentReport table
    student_id = db.query(Student).filter(Student.StudentNumber == student_number).first().StudentId
    incident_report = db.query(IncidentReport).filter(IncidentReport.StudentId == student_id).first()
    if incident_report:
        return JSONResponse(status_code=400, content={"error": "You are not allowed to file a CoC due to an incident report associated with you."})
    
    # Check if the student is not graduated/continuing
    student_graduated_code = get_Student_Status_In_CourseEnrolled(student_number)
    # (0 - Not Graduated/Continuing ||  1 - Graduated  ||  2 - Drop  ||  3 - Transfer Course || 4 - Transfer School)
    if student_graduated_code != 0:
        return JSONResponse(status_code=400, content={"error": "You are not allowed to file a CoC because you are not a continuing student."})
    
    # Check if the student exists in the database
    student = db.query(Student).filter(Student.StudentNumber == student_number).first()
    if not student:
        return JSONResponse(status_code=404, content={"error": "Student number does not exist."})
    
    # Check if the student is in eligibles table with election id
    eligible = db.query(Eligibles).filter(Eligibles.ElectionId == election_id, Eligibles.StudentNumber == student_number).first()
    if not eligible:
        return JSONResponse(status_code=400, content={"error": "You are not eligible to file a CoC for this election."})

    # Check if verification code is correct in code table and is not expired
    code = db.query(Code).filter(Code.StudentNumber == student_number, Code.CodeType == 'Verification', Code.CodeValue == verification_code).first()
    if not code:
        return JSONResponse(status_code=400, content={"error": "Verification code is invalid."})
    
    # Check if the student has already filed a CoC for this election and not rejected
    coc = db.query(CoC).filter(CoC.ElectionId == election_id, CoC.StudentNumber == student_number, CoC.Status != 'Rejected').first()
    if coc:
        return JSONResponse(status_code=400, content={"error": "You have already filed a CoC for this election."})
    
    # Get the partylist id if the student is running under a partylist base on the partylist name
    get_party_list = db.query(PartyList).filter(PartyList.PartyListName == party_list).first()

    if get_party_list:
        party_list = get_party_list.PartyListId

    # Check if the student applied for a partylist and the number of candidates in position (base on position quantity) is already full
    # To limit the number of candidates in a position if the student is running under a partylist
    if party_list:
        # Get the number of candidates in the position
        get_position = db.query(CoC).filter(CoC.ElectionId == election_id, CoC.PartyListId == party_list, CoC.SelectedPositionName == position).count()

        # Get the position quantity in the CreatedElectionPosition table
        get_position_quantity = db.query(CreatedElectionPosition).filter(CreatedElectionPosition.ElectionId == election_id, CreatedElectionPosition.PositionName == position).first()

        if get_position >= int(get_position_quantity.PositionQuantity):
            return JSONResponse(status_code=400, content={"error": "The number of candidates on this party list for this position is already full."})
    
    new_coc = CoC(ElectionId=election_id,
                    StudentNumber=student_number,
                    VerificationCode=verification_code,
                    Motto=motto,
                    Platform=platforms,
                    PoliticalAffiliation=political_affiliation,
                    PartyListId=party_list,
                    SelectedPositionName=position,
                    DisplayPhoto='',
                    CertificationOfGrades='',
                    Status='Pending',
                    created_at=manila_now(),
                    updated_at=manila_now())
    db.add(new_coc)
    db.flush() # Flush the session to get the ID of the new CoC

    if display_photo:
        # Remove the prefix of the base64 string and keep only the data
        base64_data = display_photo.split(',')[1]
        
        # Use the ID of the new CoC as the subfolder name under 'CoCs'            
        folder_name = f"CoCs/coc_{new_coc.CoCId}"
        tag_name = f'coc_display_photo_{new_coc.CoCId}'

        # Upload file to Cloudinary with the folder name in the public ID
        response_display_photo = cloudinary.uploader.upload("data:image/jpeg;base64," + base64_data, public_id=f"{folder_name}/display_photo/{display_photo_file_name}", tags=[tag_name])

        # Store the tag in the DisplayPhoto column
        new_coc.DisplayPhoto = response_display_photo['secure_url']

    if certification_of_grades:
        # Remove the prefix of the base64 string and keep only the data
        base64_data = certification_of_grades.split(',')[1]
        
        # Use the ID of the new CoC as the subfolder name under 'CoCs'            
        folder_name = f"CoCs/coc_{new_coc.CoCId}"
        tag_name = f'coc_cert_grades_{new_coc.CoCId}'

        # Upload file to Cloudinary with the folder name in the public ID
        response_certification_grades = cloudinary.uploader.upload("data:image/jpeg;base64," + base64_data, public_id=f"{folder_name}/cert_grades/{certification_of_grades_file_name}", tags=[tag_name])

        # Store the tag in the CertificationOfGrades column
        new_coc.CertificationOfGrades = response_certification_grades['secure_url']

    db.commit()

    return {
        "id": new_coc.CoCId,
        "election_id": new_coc.ElectionId,
        "student_number": new_coc.StudentNumber,
        "verification_code": new_coc.VerificationCode,
        "motto": new_coc.Motto,
        "political_affiliation": new_coc.PoliticalAffiliation,
        "party_list_id": new_coc.PartyListId,
        "position": new_coc.SelectedPositionName,
        "display_photo": new_coc.DisplayPhoto,
        "certification_of_grades": new_coc.CertificationOfGrades,
    }

# Create a queue
queue_email_coc_status = asyncio.Queue()

# Define a worker function
async def email_coc_status_wroker():
    while True:
        # Get a task from the queue
        task = await queue_email_coc_status.get()

        # Process the task
        student_number, student_email, status, position_name, election_name, reject_reason = task
        send_coc_status_email(student_number, student_email, status, position_name, election_name, reject_reason)

        # Indicate that the task is done
        queue_email_coc_status.task_done()

asyncio.create_task(email_coc_status_wroker())
    
@router.put("/coc/{id}/accept", tags=["CoC"])
async def accept_CoC(id: int, db: Session = Depends(get_db)):
    try:
        coc = db.query(CoC).get(id)
        reject_reason = '' # None because the CoC is accepted, just initialize

        if not coc:
            return JSONResponse(status_code=404, content={"detail": "CoC not found"})

        coc.Status = 'Approved'
        coc.updated_at = manila_now()

        db.commit()

        # Put to the Candidates table
        new_candidate = Candidates(StudentNumber=coc.StudentNumber,
                                    ElectionId=coc.ElectionId,
                                    PartyListId=coc.PartyListId,
                                    SelectedPositionName=coc.SelectedPositionName,
                                    DisplayPhoto=coc.DisplayPhoto,
                                    created_at=manila_now(),
                                    updated_at=manila_now())
        
        db.add(new_candidate)
        db.commit()

        # Get the student from the Student table using the student number in the CoC table
        student = db.query(Student).filter(Student.StudentNumber == coc.StudentNumber).first()

        # Get the election from the Election table using the election id in the CoC table
        election = db.query(Election).filter(Election.ElectionId == coc.ElectionId).first()

        await queue_email_coc_status.put((student.StudentNumber, student.Email, 'Approved', coc.SelectedPositionName, election.ElectionName, reject_reason))

        return {"detail": "CoC id " + str(id) + " was successfully approved"}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while approving CoC in the table CoC"})
    
@router.put("/coc/{id}/reject", tags=["CoC"])
async def reject_CoC(id: int, reject_reason: str = Form(...), db: Session = Depends(get_db)):
    try:
        coc = db.query(CoC).get(id)

        if not coc:
            return JSONResponse(status_code=404, content={"detail": "CoC not found"})

        coc.Status = 'Rejected'
        coc.updated_at = manila_now()

        # Remove political affiliation and party list id
        coc.PoliticalAffiliation = 'Independent'
        coc.PartyListId = None

        db.commit()

        # Get the student from the Student table using the student number in the CoC table
        student = db.query(Student).filter(Student.StudentNumber == coc.StudentNumber).first()

        # Get the election from the Election table using the election id in the CoC table
        election = db.query(Election).filter(Election.ElectionId == coc.ElectionId).first()

        await queue_email_coc_status.put((student.StudentNumber, student.Email, 'Rejected', coc.SelectedPositionName, election.ElectionName, reject_reason))

        return {"detail": "CoC id " + str(id) + " was successfully rejected"}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while rejecting CoC in the table CoC"})


#################################################################
## Code APIs ## 

""" Code Table APIs """
class CodeForStudent(BaseModel):
    election_id: int
    student_number: str
    code_type: str

""" ** POST Methods: All about Code Table APIs ** """
@router.post("/code/coc/verification/generate", tags=["Code"])
def generate_Coc_Verification_Code(code_for_student:CodeForStudent, db: Session = Depends(get_db)):
    # Check if the student exists in the database
    student = db.query(Student).filter(Student.StudentNumber == code_for_student.student_number).first()
    if not student:
        return JSONResponse(status_code=404, content={"error": "Student number does not exist."})

    # Check if the student is in eligibles table
    eligible = db.query(Eligibles).filter(Eligibles.StudentNumber == code_for_student.student_number).first()
    if not eligible:
        return JSONResponse(status_code=400, content={"error": "You are not eligible to file a CoC for this election."})

    # Check if a code already exists with same code type for this student
    existing_code_type = db.query(Code).filter(Code.StudentNumber == code_for_student.student_number, Code.CodeType == code_for_student.code_type).first()

    # Generate a random code
    code_value = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    if existing_code_type:
        # If a code already exists for this student, update it
        existing_code_type.CodeValue = code_value
        existing_code_type.CodeExpirationDate = manila_now() + timedelta(minutes=30)
        existing_code_type.updated_at = manila_now()
    else:
        # If no code exists for this student, create a new one
        new_code = Code(StudentNumber=code_for_student.student_number, 
                        CodeValue=code_value,
                        CodeType=code_for_student.code_type,
                        CodeExpirationDate=manila_now() + timedelta(minutes=30),
                        created_at=manila_now(),
                        updated_at=manila_now())
        db.add(new_code)

    # Commit the session to save the changes in the database
    db.commit()

    send_verification_code_email(student.StudentNumber, student.Email, code_value)

    # Return the new or updated code including the email address of the student
    return {
        "student_number": student.StudentNumber,
        "email_address": student.Email,
        "code_value": code_value,
        "code_type": code_for_student.code_type,
    }

@router.post("/code/ratings/verification/generate", tags=["Code"])
def generate_Ratings_Verification_Code(code_for_student:CodeForStudent, db: Session = Depends(get_db)):
    # Check if the student exists in the database
    student = db.query(Student).filter(Student.StudentNumber == code_for_student.student_number).first()

    if not student:
        return JSONResponse(status_code=404, content={"error": "Student number does not exist"})
    
    # Check if the student is in eligible table
    eligible = db.query(Eligibles).filter(Eligibles.StudentNumber == code_for_student.student_number).first()

    if not eligible:
        return JSONResponse(status_code=400, content={"error": "You are not eligible to submit ratings for this election"})
    
    # Check if the student number is in Code table
    code = db.query(Code).filter(Code.StudentNumber == code_for_student.student_number, Code.CodeType == code_for_student.code_type).first()

    if code:
        return JSONResponse(status_code=400, content={"error": "You have already generated a verification code"})

    # Check RatinsTracker table if the student has already submitted ratings
    ratings_tracker = db.query(RatingsTracker).filter(RatingsTracker.StudentNumber == code_for_student.student_number, RatingsTracker.ElectionId == code_for_student.election_id).first()

    if ratings_tracker:
        return JSONResponse(status_code=400, content={"error": "You have already submitted your ratings"})
    
    # Check if a code already exists with same code type for this student
    existing_code_type = db.query(Code).filter(Code.StudentNumber == code_for_student.student_number, Code.CodeType == code_for_student.code_type).first()

    # Generate a random code
    code_value = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    if existing_code_type:
        # If a code already exists for this student, update it
        existing_code_type.CodeValue = code_value
        existing_code_type.CodeExpirationDate = manila_now() + timedelta(minutes=30)
        existing_code_type.updated_at = manila_now()

    else:
        # If no code exists for this student, create a new one
        new_code = Code(StudentNumber=code_for_student.student_number, 
                        CodeValue=code_value,
                        CodeType=code_for_student.code_type,
                        CodeExpirationDate=manila_now() + timedelta(minutes=30),
                        created_at=manila_now(),
                        updated_at=manila_now())
        db.add(new_code)

    # Commit the session to save the changes in the database
    db.commit()

    send_verification_code_email(student.StudentNumber, student.Email, code_value)

    # Return the new or updated code including the email address of the student
    return {
        "student_number": student.StudentNumber,
        "email_address": student.Email,
        "code_value": code_value,
        "code_type": code_for_student.code_type,
    }

@router.post("/code/ratings/verify/{code}/{type}", tags=["Code"])
def verify_Ratings_Code(code: str, type: str, db: Session = Depends(get_db)):
    # Check if the code exists in the database
    code = db.query(Code).filter(Code.CodeValue == code, Code.CodeType == type).first()

    if not code:
        return JSONResponse(status_code=404, content={"error": "Code is invalid."})
    
    # remove the code from the database
    if code:
        db.delete(code)
        db.commit()

    # return true and a message if the code is valid
    return {
        "valid": True,
    }

#################################################################
## PartyList APIs ## 

""" PartyList Table APIs """

""" ** GET Methods: Partylist Table APIs ** """
@router.get("/partylist/all", tags=["Party List"])
def get_All_PartyList(db: Session = Depends(get_db)):
    try:
        partylists = db.query(PartyList).order_by(PartyList.PartyListId).all()

        # make a dictionary of partylists
        partylists = [partylist.to_dict(i+1) for i, partylist in enumerate(partylists)]

        # return the election name using the election id in the partylist dictionary
        for partylist in partylists:
            if partylist["ElectionId"]:
                election = db.query(Election).filter(Election.ElectionId == partylist["ElectionId"]).first()
                partylist["ElectionName"] = election.ElectionName if election else None

                # Get the studentorganizationname from studentorganization table using the election table's studentorganizationid to look at studentorganizationname
                student_organization = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == election.StudentOrganizationId).first()
                partylist["StudentOrganizationName"] = student_organization.OrganizationName if student_organization else None

        return {"partylists": partylists}
        
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all partylists from the database"})
    
@router.get("/partylist/approved/all", tags=["Party List"])
def get_All_Approved_PartyList(db: Session = Depends(get_db)):
    try:
        partylists = db.query(PartyList).filter(PartyList.Status == 'Approved').order_by(PartyList.PartyListId).all()
        return {"partylists": [partylist.to_dict(i+1) for i, partylist in enumerate(partylists)]}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all approved partylists from the database"})


@router.get("/partylist/election/{id}/approved/all", tags=["Party List"])
def get_All_Approved_PartyList_By_Election_Id(id: int, db: Session = Depends(get_db)):
    try:
        partylists = db.query(PartyList).filter(PartyList.ElectionId == id, PartyList.Status == 'Approved').order_by(PartyList.PartyListId).all()
        return {"partylists": [partylist.to_dict(i+1) for i, partylist in enumerate(partylists)]}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all approved partylists from the database"})
    
@router.get("/partylist/{id}/candidates/all", tags=["Party List"])
def get_All_Candidates_By_PartyList_Id(id: int, db: Session = Depends(get_db)):
    try:
        # Get all candidates in the CoC table that are approved and are running under this partylist ordered by position
        partylist_candidates = db.query(CoC).join(
            CreatedElectionPosition,
            CreatedElectionPosition.ElectionId == CoC.ElectionId
        ).join(
            Student,
            CoC.StudentNumber == Student.StudentNumber
        ).filter(
            CoC.PartyListId == id, 
            CoC.Status == 'Approved'
        ).order_by(
            CreatedElectionPosition.CreatedElectionPositionId,
            asc(func.concat(Student.FirstName, ' ', Student.MiddleName, ' ', Student.LastName))
        ).all()
        
        partylist_candidates_dict = []
        # Include the student full name in student table by student number in the CoC table
        for i, coc in enumerate(partylist_candidates):
            student = db.query(Student).filter(Student.StudentNumber == coc.StudentNumber).first()
            partylist_candidates_dict.append(coc.to_dict(i+1))

            # Get candidate Rating and TimesRated via student number in Candidates table
            candidate = db.query(Candidates).filter(Candidates.StudentNumber == coc.StudentNumber, Candidates.ElectionId == coc.ElectionId).first()
            partylist_candidates_dict[i]["Rating"] = candidate.Rating if candidate else None
            partylist_candidates_dict[i]["TimesRated"] = candidate.TimesRated if candidate else None

            partylist_candidates_dict[i]["Student"] = student.to_dict() if student else None

            # Get the student metadata from the student metadata table using the student number in the CoC table
            student_metadata = get_Student_Metadata_by_studnumber(coc.StudentNumber)

            if "CourseCode" in student_metadata:
                partylist_candidates_dict[i]["Student"]["CourseCode"] = student_metadata["CourseCode"]
                partylist_candidates_dict[i]["Student"]["Year"] = student_metadata["Year"]
                partylist_candidates_dict[i]["Student"]["Semester"] = student_metadata["Semester"]

            student_section = get_Student_Section_by_studnumber(coc.StudentNumber)

            if student_section:
                partylist_candidates_dict[i]["Student"]["Section"] = student_section

        # Include the display photo using secure URL from Cloudinary
        for coc in partylist_candidates_dict:
            coc["DisplayPhoto"] = coc["DisplayPhoto"]

        return {"candidates": partylist_candidates_dict}

    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all candidates from the database"})
    
@router.get("/partylist/{id}", tags=["Party List"])
def get_PartyList_By_Id(id: int, db: Session = Depends(get_db)):
    try:
        partylist = db.query(PartyList).get(id)

        if not partylist:
            return JSONResponse(status_code=404, content={"detail": "Partylist not found"})
        
        # Include image URL from cloudinary
        partylist.ImageAttachment = partylist.ImageAttachment

        # Include the election name using the election id in the partylist dictionary
        if partylist.ElectionId:
            election_name = db.query(Election).filter(Election.ElectionId == partylist.ElectionId).first()
            
        partylist_dict = partylist.to_dict()
        partylist_dict["ElectionName"] = election_name.ElectionName if election_name else None

        return {"partylist": partylist_dict}

    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching partylist from the database"})
    
# check if partylist is not yet claimed by name
@router.get("/partylist/is-taken/{name}", tags=["Party List"])
def get_PartyList_By_Name(name: str, db: Session = Depends(get_db)):
    try:
        # Ignore case
        partylist = db.query(PartyList).filter(func.lower(PartyList.PartyListName) == func.lower(name)).first()

        if not partylist:
            return False

        return True
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching partylist from the database"})

# get partylists by election id
@router.get("/partylist/election/{election_id}", tags=["Party List"])
def get_PartyList_By_Election_Id(election_id: int, db: Session = Depends(get_db)):
    try:
        partylists = db.query(PartyList).filter(PartyList.ElectionId == election_id).order_by(PartyList.PartyListId).all()

        # make a dictionary of partylists
        partylists = [partylist.to_dict(i+1) for i, partylist in enumerate(partylists)]

        # return the election name using the election id in the partylist dictionary
        for partylist in partylists:
            if partylist["ElectionId"]:
                election = db.query(Election).filter(Election.ElectionId == partylist["ElectionId"]).first()
                partylist["ElectionName"] = election.ElectionName if election else None

                # Get the studentorganizationname from studentorganization table using the election table's studentorganizationid to look at studentorganizationname
                student_organization = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == election.StudentOrganizationId).first()
                partylist["StudentOrganizationName"] = student_organization.OrganizationName if student_organization else None

        return {"partylists": partylists}
        
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all partylists from the database"})


""" ** POST Methods: All about Partylist Table APIs ** """

@router.post("/partylist/submit", tags=["Party List"])
async def save_PartyList(election_id: int = Form(...), party_name: str = Form(...), 
                         email_address: str = Form(...), cellphone_number: str = Form(...), 
                         description: str = Form(...), mission: str = Form(...),
                         vision: str = Form(...), platforms: str = Form(...),
                         image_attachment: Optional[str] = Form(None), image_file_name: Optional[str] = Form(None),
                         video_attachment: Optional[str] = Form(None),
                         db: Session = Depends(get_db)):
    
    # Check if current datetime is within the filing period of the election
    election = db.query(Election).filter(Election.ElectionId == election_id).first()

    if manila_now() > election.CoCFilingEnd.replace(tzinfo=timezone('Asia/Manila')):
        return JSONResponse(status_code=400, content={"error": "Filing period for this election has ended."})
    
    new_partylist = PartyList(ElectionId=election_id,
                            PartyListName=party_name, 
                            EmailAddress=email_address,
                            CellphoneNumber=cellphone_number, 
                            Description=description,
                            Mission=mission,
                            Vision=vision,
                            Platforms=platforms,
                            ImageAttachment='' if image_attachment else None,  # Initialize with an empty string
                            VideoAttachment=video_attachment,
                            Status='Pending',
                            created_at=manila_now(), 
                            updated_at=manila_now())
    db.add(new_partylist)
    db.commit()

    if image_attachment:
        # Remove the prefix of the base64 string and keep only the data
        base64_data = image_attachment.split(',')[1]
        
        # Use the ID of the new partylist as the subfolder name under 'Partylists'            
        folder_name = f"Partylists/partylist_{new_partylist.PartyListId}"

        # Upload file to Cloudinary with the folder name in the public ID
        response_image = cloudinary.uploader.upload("data:image/jpeg;base64," + base64_data, public_id=f"{folder_name}/{image_file_name}", tags=[f'partylist_{new_partylist.PartyListId}'])

        # Store the tag in the ImageAttachment column
        new_partylist.ImageAttachment = response_image['secure_url']
        db.commit()

    return {
        "id": new_partylist.PartyListId,
        "party_name": new_partylist.PartyListName,
        "email_address": new_partylist.EmailAddress,
        "cellphone_number": new_partylist.CellphoneNumber,
        "description": new_partylist.Description,
        "mission": new_partylist.Mission,
        "vision": new_partylist.Vision,
        "platforms": new_partylist.Platforms,
        "image_attachment": new_partylist.ImageAttachment,
        "video_attachment": new_partylist.VideoAttachment,
    }

# Create a queue
queue_email_partylist_status = asyncio.Queue()

# Define a worker function
async def email_partylist_status_wroker():
    while True:
        # Get a task from the queue
        task = await queue_email_partylist_status.get()

        # Process the task
        party_email, status, partylist_name, election_name, reject_reason = task
        send_partylist_status_email(party_email, status, partylist_name, election_name, reject_reason)

        # Indicate that the task is done
        queue_email_partylist_status.task_done()

asyncio.create_task(email_partylist_status_wroker())

@router.put("/partylist/{id}/accept", tags=["Party List"])
async def accept_PartyList(id: int, db: Session = Depends(get_db)):
    try:
        partylist = db.query(PartyList).get(id)
        reject_reason = '' # None because the Partylist is accepted, just initialize

        if not partylist:
            return JSONResponse(status_code=404, content={"detail": "Partylist not found"})

        partylist.Status = 'Approved'
        partylist.updated_at = manila_now()

        db.commit()

        # Get the election from the Election table using the election id in the CoC table
        election = db.query(Election).filter(Election.ElectionId == partylist.ElectionId).first()

        await queue_email_partylist_status.put((partylist.EmailAddress, 'Approved', partylist.PartyListName, election.ElectionName, reject_reason))

        return {"detail": "Partylist id " + str(id) + " was successfully approved"}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while approving partylist in the table PartyList"})
    
@router.put("/partylist/{id}/reject", tags=["Party List"])
async def reject_PartyList(id: int, reject_reason: str = Form(...), db: Session = Depends(get_db)):
    try:
        partylist = db.query(PartyList).get(id)

        if not partylist:
            return JSONResponse(status_code=404, content={"detail": "Partylist not found"})

        partylist.Status = 'Rejected'
        partylist.updated_at = manila_now()

        db.commit()

        # Get the election from the Election table using the election id in the CoC table
        election = db.query(Election).filter(Election.ElectionId == partylist.ElectionId).first()

        await queue_email_partylist_status.put((partylist.EmailAddress, 'Rejected', partylist.PartyListName, election.ElectionName, reject_reason))

        return {"detail": "Partylist id " + str(id) + " was successfully rejected"}
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while rejecting partylist in the table PartyList"})
    
#################################################################
## Candidates APIs ## 

""" Candidates Table APIs """
class Rating(BaseModel):
    candidate_student_number: str
    rating: int = Field(0)

class RatingList(BaseModel):
    election_id: int
    rater_student_number: str
    ratings: List[Rating]

""" ** GET Methods: Candidates Table APIs ** """
@router.get("/candidates/all", tags=["Candidates"])
def get_All_Candidates(db: Session = Depends(get_db)):
    try:
        candidates = db.query(Candidates).order_by(Candidates.CandidateId).all()

        # Get the student row from student table using the student number in the candidate
        candidates_with_student = []
        for i, candidate in enumerate(candidates):
            student = db.query(Student).filter(Student.StudentNumber == candidate.StudentNumber).first()
            candidate_dict = candidate.to_dict(i+1)
            candidate_dict["Student"] = student.to_dict() if student else {}

            # Get the party list name from partylist table using the partylist id in the candidate
            if candidate.PartyListId:
                partylist = db.query(PartyList).filter(PartyList.PartyListId == candidate.PartyListId).first()
                candidate_dict["PartyListName"] = partylist.PartyListName if partylist else ""

            # Get the motto from coc table using the student number in the candidate
            if candidate.StudentNumber:
                coc = db.query(CoC).filter(CoC.StudentNumber == candidate.StudentNumber, CoC.ElectionId == candidate.ElectionId).first()
                candidate_dict["Motto"] = coc.Motto if coc else ""

            # Get the display photo using secure URL from Cloudinary
            candidate_dict["DisplayPhoto"] = candidate.DisplayPhoto
            
            candidates_with_student.append(candidate_dict)

        return {"candidates": candidates_with_student}

    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all candidates from the database"})
    
@router.get("/candidates/election/{id}/all", tags=["Candidates"])
def get_All_Candidates_By_Election_Id(id: int, db: Session = Depends(get_db)):
    try:
        candidates = db.query(Candidates).filter(Candidates.ElectionId == id).order_by(Candidates.CandidateId).all()

        # Get the student row from student table using the student number in the candidate
        candidates_with_student = []
        for i, candidate in enumerate(candidates):
            student = db.query(Student).filter(Student.StudentNumber == candidate.StudentNumber).first()
            candidate_dict = candidate.to_dict(i+1)
            candidate_dict["Student"] = student.to_dict() if student else {}

            # Get the student's course
            if student:
                student_metadata = get_Student_Metadata_by_studnumber(student.StudentNumber)
                student_section = get_Student_Section_by_studnumber(student.StudentNumber)

                if "CourseCode" in student_metadata:
                    candidate_dict["Student"]["CourseCode"] = student_metadata["CourseCode"]
                    candidate_dict["Student"]["Year"] = student_metadata["Year"]
                    candidate_dict["Student"]["Semester"] = student_metadata["Semester"]

                if student_section:
                    candidate_dict["Student"]["Section"] = student_section

            # Get the party list name from partylist table using the partylist id in the candidate
            if candidate.PartyListId:
                partylist = db.query(PartyList).filter(PartyList.PartyListId == candidate.PartyListId).first()
                candidate_dict["PartyListName"] = partylist.PartyListName if partylist else ""

            # Get the motto from coc table using the student number in the candidate
            if candidate.StudentNumber:
                coc = db.query(CoC).filter(CoC.StudentNumber == candidate.StudentNumber, CoC.ElectionId == candidate.ElectionId).first()
                candidate_dict["Motto"] = coc.Motto if coc else ""

            # Get the display photo using secure URL from Cloudinary
            candidate_dict["DisplayPhoto"] = candidate.DisplayPhoto
            
            candidates_with_student.append(candidate_dict)

        return {"candidates": candidates_with_student}

    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all candidates from the database"})
    
@router.get("/candidates/election/per-position/{id}/all", tags=["Candidates"])
def get_All_Candidates_By_Election_Id_Per_Position(id: int, db: Session = Depends(get_db)):
    try:
        # Get the candidates and order by CreatedElectionPositionId
        candidates = db.query(Candidates).join(
            CreatedElectionPosition,
            and_(
                Candidates.SelectedPositionName == CreatedElectionPosition.PositionName,
                Candidates.ElectionId == id
            )
        ).join(
            Student,
            Candidates.StudentNumber == Student.StudentNumber
        ).order_by(
            CreatedElectionPosition.CreatedElectionPositionId,
            asc(func.concat(Student.FirstName, ' ', Student.MiddleName, ' ', Student.LastName))
        ).all()

        # Get the student row from student table using the student number in the candidate
        candidates_grouped_by_position = {}
        for i, candidate in enumerate(candidates):
            student = db.query(Student).filter(Student.StudentNumber == candidate.StudentNumber).first()
            candidate_dict = candidate.to_dict(i+1)
            candidate_dict["Student"] = student.to_dict() if student else {}

            # Get the student's course
            if student:
                student_metadata = get_Student_Metadata_by_studnumber(student.StudentNumber)
                student_section = get_Student_Section_by_studnumber(student.StudentNumber)

                if "CourseCode" in student_metadata:
                    candidate_dict["Student"]["CourseCode"] = student_metadata["CourseCode"]
                    candidate_dict["Student"]["Year"] = student_metadata["Year"]
                    candidate_dict["Student"]["Semester"] = student_metadata["Semester"]

                if student_section:
                    candidate_dict["Student"]["Section"] = student_section

            # Get the party list name from partylist table using the partylist id in the candidate
            if candidate.PartyListId:
                partylist = db.query(PartyList).filter(PartyList.PartyListId == candidate.PartyListId).first()
                candidate_dict["PartyListName"] = partylist.PartyListName if partylist else ""

            # Get the motto from coc table using the student number in the candidate
            if candidate.StudentNumber:
                coc = db.query(CoC).filter(CoC.StudentNumber == candidate.StudentNumber, CoC.ElectionId == candidate.ElectionId).first()
                candidate_dict["Motto"] = coc.Motto if coc else ""
                candidate_dict["Platform"] = coc.Platform if coc else ""

            # Get the display photo using secure URL from Cloudinary
            candidate_dict["DisplayPhoto"] = candidate.DisplayPhoto
            
            #candidate_dict["DisplayPhoto"] = ""

            # Group by SelectedPositionName
            position_name = candidate.SelectedPositionName

            # Get the PositionQuantity from CreatedElectionPosition table
            created_election_position = db.query(CreatedElectionPosition).filter(and_(CreatedElectionPosition.ElectionId == id, CreatedElectionPosition.PositionName == position_name)).first()
            candidate_dict["PositionQuantity"] = created_election_position.PositionQuantity 

            if position_name not in candidates_grouped_by_position:
                candidates_grouped_by_position[position_name] = []
                

            candidates_grouped_by_position[position_name].append(candidate_dict)

        return {"candidates": candidates_grouped_by_position}

    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all candidates from the database"})

""" ** POST Methods: All about Candidates Table APIs ** """
@router.post("/candidates/ratings/submit", tags=["Candidates"])
def save_Candidate_Ratings(rating_list: RatingList, db: Session = Depends(get_db)):

    # Check if campaign period has not yet ended
    election = db.query(Election).filter(Election.ElectionId == rating_list.election_id).first()

    # check for ended campaign period only 
    if manila_now() > election.CampaignEnd.replace(tzinfo=timezone('Asia/Manila')):
        return JSONResponse(status_code=400, content={"error": "Rating/Campaign period for this election has ended."})

    # Check if the student has already rated this election
    existing_rating = db.query(RatingsTracker).filter(RatingsTracker.StudentNumber == rating_list.rater_student_number, RatingsTracker.ElectionId == rating_list.election_id).first()

    if existing_rating:
        return JSONResponse(status_code=400, content={"error": "You have already rated this election"})

    for rating in rating_list.ratings:
        # Check if the student exists in the database
        student = db.query(Student).filter(Student.StudentNumber == rating.candidate_student_number).first()

        if not student:
            return JSONResponse(status_code=404, content={"error": "Student number does not exist"})

        # Check if the election exists in the database
        election = db.query(Election).filter(Election.ElectionId == rating_list.election_id).first()

        if not election:
            return JSONResponse(status_code=404, content={"error": "Election does not exist"})

        # Update the ratings of the candidate in the Candidates table
        candidate = db.query(Candidates).filter(Candidates.StudentNumber == rating.candidate_student_number, Candidates.ElectionId == rating_list.election_id).first()

        if not candidate:
            return JSONResponse(status_code=404, content={"error": "Candidate does not exist"})

        # Increment the number of ratings of the candidate by ratings received
        candidate.Rating += rating.rating

        # Determine how much is star is given (One start, two, three, four, five)
        if rating.rating == 1:
            candidate.OneStar += 1
        elif rating.rating == 2:
            candidate.TwoStar += 1
        elif rating.rating == 3:
            candidate.ThreeStar += 1
        elif rating.rating == 4:
            candidate.FourStar += 1
        elif rating.rating == 5:
            candidate.FiveStar += 1

        # Increment the number of times rated of the candidate
        if rating.rating > 0:
            candidate.TimesRated += 1
            
        candidate.updated_at = manila_now()

        db.commit()

    # Add a new record in the RatingsTracker table
    new_rating = RatingsTracker(StudentNumber=rating_list.rater_student_number,
                                        ElectionId=rating_list.election_id,
                                        created_at=manila_now(),
                                        updated_at=manila_now())

    db.add(new_rating)
    db.commit()

    return {"response": "success"}

#################################################################
## VotingsTracker APIs ## 

class Votes(BaseModel):
    candidate_student_number: str
    #position: Optional[str] = None

class VotesList(BaseModel):
    election_id: int
    voter_student_number: str
    votes: List[Votes]
    abstainList: List[str]


""" VotingsTracker Table APIs """

""" ** GET Methods: VotingsTracker Table APIs ** """

@router.get("/votings/election/{id}/{position_name}/results", tags=["Votings"])
def get_Results_By_Election_Id_And_Position_Name(id: int, position_name: str, db: Session = Depends(get_db)):
    try:
        # Rank the candidates by votes received
        candidates = db.query(Candidates).filter(Candidates.ElectionId == id, Candidates.SelectedPositionName == position_name).order_by(Candidates.Votes.desc()).all()

        # Calculate the total number of votes
        total_votes = sum(candidate.Votes for candidate in candidates)

        # Calculate the ranking, votes, and percentage of votes for each candidate
        results = []
        for i, candidate in enumerate(candidates):
            # Get the first name middle name if it exist and last name of candidate by studentnumber from student table
            student = db.query(Student).filter(Student.StudentNumber == candidate.StudentNumber).first()
            full_name = student.FirstName + " " + student.MiddleName + " " + student.LastName if student.MiddleName else student.FirstName + " " + student.LastName

            # Get the candidate photo using secure URL from Cloudinary
            display_photo_url = candidate.DisplayPhoto

            # Get candidate partylist
            partylist = db.query(PartyList).filter(PartyList.PartyListId == candidate.PartyListId).first()
            partylist_name = partylist.PartyListName if partylist else ""

            results.append({
                'rank': i + 1,
                'candidate_student_number': candidate.StudentNumber,
                'full_name': full_name,
                'partylist_name': partylist_name,
                'display_photo': display_photo_url,
                'votes': candidate.Votes,
                'times_abstained': candidate.TimesAbstained,
                'percentage': (candidate.Votes / total_votes) * 100 if total_votes > 0 else 0,
            })

        # Get total votes of position from all candidates
        total_votes_position = sum(candidate.Votes for candidate in db.query(Candidates).filter(Candidates.ElectionId == id, Candidates.SelectedPositionName == position_name).all())

        # Get total abstain count of position from one candidate unique by position since they are all the same
        total_abstain_count = db.query(Candidates).filter(Candidates.ElectionId == id, Candidates.SelectedPositionName == position_name).first().TimesAbstained
       
        # Get all eligible voters for this election from eligibles table
        total_eligible_voters = db.query(Eligibles).filter(Eligibles.ElectionId == id).count()

        # Get the studentorganization logo
        student_organization = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == db.query(Election).filter(Election.ElectionId == id).first().StudentOrganizationId).first()

        # Get the studentorganization logo using secure URL from Cloudinary
        student_organization_logo_url = student_organization.OrganizationLogo

        # Return the VotingEnd
        voting_end = db.query(Election).filter(Election.ElectionId == id).first().VotingEnd

        return {
            "results": results,
            "total_votes_position": total_votes_position,
            "total_abstain_count": total_abstain_count,
            "total_eligible_voters": total_eligible_voters,
            "student_organization_logo": student_organization_logo_url,
            "voting_end": voting_end,
        }
    except:
        return JSONResponse(status_code=500, content={"detail": "Error while fetching all candidates from the database"})

""" ** POST Methods: All about VotingsTracker Table APIs ** """

@router.post("/votings/submit", tags=["Votings"])
def save_Votes(votes_list: VotesList, db: Session = Depends(get_db)):
    # Check if voting period has not yet ended
    election = db.query(Election).filter(Election.ElectionId == votes_list.election_id).first()

    # check for ended voting period only 
    if manila_now() > election.VotingEnd.replace(tzinfo=timezone('Asia/Manila')):
        return JSONResponse(status_code=400, content={"error": "Voting period for this election has ended."})

    # Check if the student has already voted this election
    existing_vote = db.query(VotingsTracker).filter(VotingsTracker.VoterStudentNumber == votes_list.voter_student_number, VotingsTracker.ElectionId == votes_list.election_id).first()

    if existing_vote:
        return JSONResponse(status_code=400, content={"error": "You have already voted for this election."})
    
    election_analytics = db.query(ElectionAnalytics).filter(ElectionAnalytics.ElectionId == votes_list.election_id).first()

    for abstain in votes_list.abstainList:
        # abstain list contains list of positions
        # +1 all candidates who's position is in the abstain list and corresponding election id
        candidates = db.query(Candidates).filter(Candidates.SelectedPositionName == abstain, Candidates.ElectionId == votes_list.election_id).all()

        for candidate in candidates:
            candidate.TimesAbstained += 1
            candidate.updated_at = manila_now()

            db.commit()

    for vote in votes_list.votes:
        if vote.candidate_student_number == 'abstain':

            # +1 the abstaincount in ElectionAnalytics table
            election_analytics.AbstainCount += 1
            election_analytics.updated_at = manila_now()
            
        else:
            # Get the candidate id via candidate student number
            candidate = db.query(Candidates).filter(Candidates.StudentNumber == vote.candidate_student_number, Candidates.ElectionId == votes_list.election_id).first()
            
            # Increment the number of votes of the candidate by votes received
            candidate.Votes += 1
            candidate.updated_at = manila_now()

        db.commit()

    for vote in votes_list.votes:
        if vote.candidate_student_number != 'abstain':
            # Get the course id via voter student number then get the course id in the course table via course code
            get_course_of_voter = get_Student_Course_by_studnumber(votes_list.voter_student_number, db)
            get_course_id = db.query(Course).filter(Course.CourseCode == get_course_of_voter).first()

            candidate = db.query(Candidates).filter(Candidates.StudentNumber == vote.candidate_student_number, Candidates.ElectionId == votes_list.election_id).first()

            # Add a new record in the VotingsTracker table per candidate voted
            new_vote = VotingsTracker(VoterStudentNumber=votes_list.voter_student_number,
                                        VotedCandidateId=candidate.CandidateId,
                                        CourseId=get_course_id.CourseId,
                                        ElectionId=votes_list.election_id,
                                        created_at=manila_now(),
                                        updated_at=manila_now())
            
            db.add(new_vote)
            
            # +1 the vote count in ElectionAnalytics table
            election_analytics = db.query(ElectionAnalytics).filter(ElectionAnalytics.ElectionId == votes_list.election_id).first()
            election_analytics.VotesCount += 1
            election_analytics.updated_at = manila_now()
            
            db.commit()

    # Add a new record in the VotingReceipt table
    new_voting_receipt = VotingReceipt(ElectionId=votes_list.election_id,
                                        StudentNumber=votes_list.voter_student_number,
                                        ReceiptPDF="",
                                        created_at=manila_now(),
                                        updated_at=manila_now())
    
    db.add(new_voting_receipt)
    db.commit()

    election = db.query(Election).filter(Election.ElectionId == votes_list.election_id).first()

    # Create the PDF
    now = manila_now()
    pdf_name = f"Report_{now.strftime('%Y%m%d_%H%M%S')}.pdf"
    doc = SimpleDocTemplate(pdf_name, pagesize=letter, topMargin=36)

    # Get the default style sheet
    styles = getSampleStyleSheet()

    # Create a list to hold the PDF elements
    elements = []

    styles.add(ParagraphStyle(name="TitleStyleCenter", fontName="Times-Roman", fontSize=12, alignment=TA_CENTER, spaceAfter=6, leading=12))

    styles.add(ParagraphStyle(name="TitleStyleLeft", fontName="Times-Roman", fontSize=12, alignment=TA_LEFT, spaceAfter=6, leading=12))
    styles.add(ParagraphStyle(name="TitleStyleRight", fontName="Times-Roman", fontSize=12, alignment=TA_RIGHT, spaceAfter=6, leading=12))
    
    styles.add(ParagraphStyle(name="JustifyContent", fontName="Times-Roman", fontSize=12, alignment=TA_JUSTIFY, spaceAfter=6, leading=12))

    # Add the logo
    logo = Image("puplogo.png", width=80, height=80)  # Adjust the path and size as needed
    elements.append(logo)
    elements.append(Spacer(1, 18))

    # Add the title
    elements.append(Paragraph("<b>STUDENT ELECTION OFFICIAL RECEIPT</b>", styles['TitleStyleCenter']))
    elements.append(Spacer(1, 18))

    # Create a list of lists for the table data
    data = [
        [Paragraph(f"<b>Student Number:</b> {votes_list.voter_student_number}", styles['TitleStyleLeft']), 
        Paragraph(f"<b>Date Voted:</b> {now.strftime('%B %d, %Y %I:%M %p')}", styles['TitleStyleRight'])],
        [Paragraph(f"<b>Election Name:</b> {election.ElectionName}", styles['TitleStyleLeft']), 
        Paragraph(f"<b>Receipt Id:</b> {new_voting_receipt.VotingReceiptId}", styles['TitleStyleRight'])]
    ]

    # Create a table with the data
    t = Table(data)

    # Create a table style
    table_style = TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),  # Set left padding to 0 for all cells
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),  # Set right padding to 0 for all cells
    ])

    # Apply the table style to the table
    t.setStyle(table_style)

    # Add the table to the elements
    elements.append(t)
    elements.append(Spacer(1, 18))

    elements.append(Paragraph(f"Note: This receipt serves as confirmation that your vote in the {election.ElectionName} has been successfully cast. Please keep this receipt for your records.", styles['JustifyContent']))
    elements.append(Spacer(1, 18))

    # Group votes by position
    votes_by_position = defaultdict(list)
    for vote in votes_list.votes:
        if vote.candidate_student_number != 'abstain':
            candidate = db.query(Candidates).filter(Candidates.StudentNumber == vote.candidate_student_number, Candidates.ElectionId == votes_list.election_id).first()
 
            # Get full name
            student = db.query(Student).filter(Student.StudentNumber == vote.candidate_student_number).first()
            full_name = student.FirstName + " " + student.MiddleName + " " + student.LastName if student.MiddleName else student.FirstName + " " + student.LastName

            votes_by_position[candidate.SelectedPositionName].append(candidate.StudentNumber + ": " + full_name)

    # Loop through the votes list
    for position, candidates in votes_by_position.items():
        elements.append(Paragraph(f"<b>Voted for position {position}:</b>", styles['TitleStyleLeft']))
        for candidate in candidates:
            elements.append(Paragraph(f"{candidate}", styles['TitleStyleLeft']))
            elements.append(Spacer(1, 12))

    # Group abstains by position
    abstains_by_position = defaultdict(list)
    for abstain in votes_list.abstainList:
        candidates = db.query(Candidates).filter(Candidates.SelectedPositionName == abstain, Candidates.ElectionId == votes_list.election_id).all()

        for candidate in candidates:
            abstains_by_position[candidate.SelectedPositionName].append(candidate.SelectedPositionName)

    # Check if there are no abstains in abstain_by_position
    if not abstains_by_position:
        elements.append(Paragraph(f"<b>Abstained list:</b> None", styles['TitleStyleLeft']))
    else:
        # Loop through the abstain list
        elements.append(Paragraph(f"<b>Abstained list:</b>", styles['TitleStyleLeft']))
        for position, abstains in abstains_by_position.items():
            for abstain in abstains:
                elements.append(Paragraph(f"{abstain}", styles['TitleStyleLeft']))


    elements.append(Spacer(1, 16))
    elements.append(Paragraph(f"Thank you for participating in the democratic process of our institution!", styles['TitleStyleLeft']))

    # Build the PDF
    doc.build(elements)

    # Upload the PDF to cloudinary
    upload_result = cloudinary.uploader.upload(pdf_name, public_id=f"Votings/voting_{votes_list.voter_student_number}_{now.strftime('%Y%m%d_%H%M%S')}", 
                                            tags=[f'voting_{votes_list.voter_student_number}'])
    
    new_voting_receipt.ReceiptPDF = upload_result['secure_url']
    db.commit()

    # Delete the local file
    os.remove(pdf_name)

    return {"response": "success",
            "upload_result": upload_result['secure_url']}

#################################################################
## ElectionWinners APIs ## 

""" ElectionWinners Table APIs """

def gather_winners_by_election_id(election_id: int):
    db = SessionLocal()  # create a new session
    election = db.query(Election).filter(Election.ElectionId == election_id).first()

    # Check if winners for this election have already been added
    existing_winners = db.query(ElectionWinners).filter(ElectionWinners.ElectionId == election_id).first()
    if existing_winners is not None:
        print("Winners for this election have already been added.")
        return
    
    # Gather all candidates for a specific election
    all_candidates_for_election = db.query(Candidates).filter(Candidates.ElectionId == election.ElectionId).all()

    # Sort all candidates by votes in descending order
    all_candidates_for_election.sort(key=lambda candidate: candidate.Votes, reverse=True)

    # Count the number of candidates for each position
    num_candidates_per_position = defaultdict(int)
    for candidate in all_candidates_for_election:
        num_candidates_per_position[candidate.SelectedPositionName] += 1

    # Get the required number of winners for each position in the current election
    num_winners_per_position = {position.PositionName: int(position.PositionQuantity) for position in db.query(CreatedElectionPosition).filter(CreatedElectionPosition.ElectionId == election.ElectionId)}

    # Initialize a dictionary to store the candidates for each position
    candidates_per_position = defaultdict(list)
    for candidate in all_candidates_for_election:
        # Check if we have already selected the required number of candidates for this position
        if len(candidates_per_position[candidate.SelectedPositionName]) < num_winners_per_position[candidate.SelectedPositionName]:
            candidates_per_position[candidate.SelectedPositionName].append(candidate)
        elif len(candidates_per_position[candidate.SelectedPositionName]) == num_winners_per_position[candidate.SelectedPositionName] and candidates_per_position[candidate.SelectedPositionName][-1].Votes == candidate.Votes:
            # If there's a tie for the last spot, add the candidate to the list
            candidates_per_position[candidate.SelectedPositionName].append(candidate)

    # Get the organization based on the election id
    organization = db.query(StudentOrganization).filter_by(StudentOrganizationId=election.StudentOrganizationId).first()

    # Get the number of eligible voters in Eligibles by election id
    num_eligible_voters = db.query(Eligibles).filter_by(ElectionId=election.ElectionId).count()

    #if manila_now() > election.VotingEnd.replace(tzinfo=timezone('Asia/Manila')):
    # Store the winners in the ElectionWinners table
    print("Adding winners to the ElectionWinners table...")

    for position, candidates in candidates_per_position.items():
        # If there's exactly one candidate for this position, check if the candidate has achieved the required vote threshold

        print("Im heree")
        if num_candidates_per_position[position] == 1:
            # Calculate the vote threshold
            vote_threshold = (num_eligible_voters // 2) + 1  # 50% students + 1 vote constraint

            if candidates[0].Votes >= vote_threshold:
                winner = ElectionWinners(ElectionId=election.ElectionId, 
                                        StudentNumber=candidates[0].StudentNumber, 
                                        SelectedPositionName=position,
                                        Votes=candidates[0].Votes,
                                        IsTied=False,
                                        created_at=manila_now(),
                                        updated_at=manila_now())
                db.add(winner)
        else:  # There's more than one candidate for this position
            # The candidates with the highest votes win
            max_votes = max(candidate.Votes for candidate in candidates)

            if max_votes > 0:
                winners = [candidate for candidate in candidates if candidate.Votes == max_votes]

                # Check if there's a tie
                is_tied = len(winners) > num_winners_per_position[position]

                for winner_candidate in winners:
                    winner = ElectionWinners(ElectionId=election.ElectionId, 
                                            StudentNumber=winner_candidate.StudentNumber, 
                                            SelectedPositionName=position,
                                            Votes=winner_candidate.Votes,
                                            IsTied=is_tied,
                                            created_at=manila_now(),
                                            updated_at=manila_now())
                    db.add(winner)

        db.commit()

    # Create the new announcement for winners
    new_announcement = Announcement(
        AnnouncementType="results",
        AnnouncementTitle=f"Winners for the {election.ElectionName}",
        AnnouncementBody = f"We are thrilled to announce that the results of the {election.ElectionName} are now available! We extend our heartfelt gratitude to everyone who participated and made this event a success. For more detailed information about the election, please visit the {election.ElectionName} page.",
        AttachmentType="Banner",
        AttachmentImage="", # Initialize the AttachmentImage column with an empty string
        created_at=manila_now(),
        updated_at=manila_now()
    )
    db.add(new_announcement)
    db.commit()

    folder_name = f"Announcements/announcement_{new_announcement.AnnouncementId}"

    # Upload the image to cloudinary
    response = cloudinary.uploader.upload("winner-image.jpg", public_id=f"{folder_name}/winner-image.jpg", tags=[f'announcement_{new_announcement.AnnouncementId}'])

    # Store the URL in the AttachmentImage column
    new_announcement.AttachmentImage = "announcement_" + str(new_announcement.AnnouncementId)

    db.commit()

    # Remove students in eligibles table with election id since voting period has ended
    #db.query(Eligibles).filter(Eligibles.ElectionId == election.ElectionId).delete()
    #db.commit()


""" ** GET Methods: ElectionWinners Table APIs ** """
    
@router.get("/votings/get-winners/{election_id}", tags=["ElectionWinners"])
def get_Winners_By_Election_Id(election_id: int, db: Session = Depends(get_db)):
    election = db.query(Election).filter(Election.ElectionId == election_id).first()

    # Get all positions for this election
    positions = db.query(CreatedElectionPosition).filter(CreatedElectionPosition.ElectionId == election_id).all()

    winners = db.query(ElectionWinners).join(
        CreatedElectionPosition, 
        and_(
            ElectionWinners.SelectedPositionName == CreatedElectionPosition.PositionName,
            ElectionWinners.ElectionId == election_id
        )
    ).order_by(CreatedElectionPosition.CreatedElectionPositionId).all()    

    winners_dict = {}

    # Initialize the dictionary with all positions
    for position in positions:
        winners_dict[position.PositionName] = {"is_tied": False, "no_winner": True, "candidates": []}

    for i, winner in enumerate(winners):
        candidate = db.query(Candidates).filter(Candidates.StudentNumber == winner.StudentNumber, Candidates.ElectionId == election_id).first()
        student = db.query(Student).filter(Student.StudentNumber == winner.StudentNumber).first()

        full_name = student.FirstName + " " + student.MiddleName + " " + student.LastName if student.MiddleName else student.FirstName + " " + student.LastName
        candidate_partylist = db.query(PartyList).filter(PartyList.PartyListId == candidate.PartyListId).first()

        if candidate_partylist:
            candidate_partylist_name = candidate_partylist.PartyListName
        else:
            candidate_partylist_name = "Independent"

        # Get the display photo using secure URL from Cloudinary
        display_photo_url = candidate.DisplayPhoto

        winners_dict[winner.SelectedPositionName]["is_tied"] = winner.IsTied
        winners_dict[winner.SelectedPositionName]["no_winner"] = False

        candidate_dict = {
            "full_name": full_name,
            "votes": winner.Votes,
            "partylist": candidate_partylist_name,
            "display_photo": display_photo_url if display_photo_url else "",
        }
        winners_dict[winner.SelectedPositionName]["candidates"].append(candidate_dict)

        # Get the candidate times abstained
        candidate_dict["times_abstained"] = candidate.TimesAbstained

        # Get the percentage of votes of the candidate
        election_analytic = db.query(ElectionAnalytics).filter(ElectionAnalytics.ElectionId == election_id).first()
        candidate_dict["percentage"] = (winner.Votes / election_analytic.VotesCount) * 100 if election_analytic.VotesCount > 0 else 0

        # Get the candidate metadata
        candidate_metadata = get_Student_Metadata_by_studnumber(winner.StudentNumber)
        candidate_section = get_Student_Section_by_studnumber(winner.StudentNumber)

        if "CourseCode" in candidate_metadata:
            candidate_dict["course_code"] = candidate_metadata["CourseCode"]
            candidate_dict["year"] = candidate_metadata["Year"]
            candidate_dict["semester"] = candidate_metadata["Semester"]

        if candidate_section:
            candidate_dict["section"] = candidate_section

    # Count all eligibles for this election
    num_eligible_voters = db.query(Eligibles).filter(Eligibles.ElectionId == election_id).count()

    # Get the total of votes for this election
    election_analytics = db.query(ElectionAnalytics).filter(ElectionAnalytics.ElectionId == election_id).first()
    total_votes = election_analytics.VotesCount

    # Get the total of abstain for this election
    total_abstain = election_analytics.AbstainCount

    # Get active voters
    active_voters = db.query(VotingsTracker).filter(VotingsTracker.ElectionId == election_id).distinct(VotingsTracker.VoterStudentNumber).count()

    # Get inactive voters
    inactive_voters = num_eligible_voters - active_voters

    return { "num_eligible_voters": num_eligible_voters, 
            "total_votes": total_votes, 
            "total_abstain": total_abstain,
            "active_voters": active_voters,
            "inactive_voters": inactive_voters,
            "winners": winners_dict
            }

""" ** POST Methods: All about ElectionWinners Table APIs ** """


#################################################################
## ElectionAppeals APIs ## 
class ElectionAppealsData(BaseModel):
    student_number: str
    appeal_details: str
    attachment: Optional[str] = Form(None)

""" ElectionAppeals Table APIs """

""" ** GET Methods: ElectionAppeals Table APIs ** """
@router.get("/election-appeals/all", tags=["ElectionAppeals"])
def get_All_Election_Appeals(db: Session = Depends(get_db)):
    appeals = db.query(ElectionAppeals).order_by(ElectionAppeals.ElectionAppealsId).all()

    appeals_with_student = []
    for i, appeal in enumerate(appeals):
        student = db.query(Student).filter(Student.StudentNumber == appeal.StudentNumber).first()
        appeal_dict = appeal.to_dict()

        appeal_dict["Student"] = student.to_dict() if student else {}
        appeals_with_student.append(appeal_dict)

    return {"appeals": appeals_with_student}

@router.get("/election-appeals/{id}", tags=["ElectionAppeals"])
def get_Election_Appeals_By_Id(id: int, db: Session = Depends(get_db)):
    appeal = db.query(ElectionAppeals).get(id)

    if not appeal:
        return JSONResponse(status_code=404, content={"detail": "Appeal not found"})

    student = db.query(Student).filter(Student.StudentNumber == appeal.StudentNumber).first()
    appeal_dict = appeal.to_dict()

    # Get the attachment from cloudinary using the candidate.displayphoto asset id in cloudinary
    if appeal.AttachmentAssetId:
        appeal_dict["Attachment"] = appeal.AttachmentAssetId
        appeal_dict["AttachmentName"] = appeal.AttachmentAssetId.split("/")[-1]
    else:
        appeal_dict["Attachment"] = ""

    appeal_dict["Student"] = student.to_dict() if student else {}

    return {"appeal": appeal_dict}

""" ** POST Methods: All about ElectionAppeals Table APIs ** """
@router.post("/election-appeals/submit", tags=["ElectionAppeals"])
def save_Election_Appeals(election_appeals_data: ElectionAppealsData, db: Session = Depends(get_db)):
    # Check if the student number exists in the database
    student = db.query(Student).filter(Student.StudentNumber == election_appeals_data.student_number).first()

    if not student:
        return JSONResponse(status_code=404, content={"error": "Student number does not exist."})
    
    # Add a new record in the ElectionAppeals table
    new_appeal = ElectionAppeals(StudentNumber=election_appeals_data.student_number,
                                        AppealDetails=election_appeals_data.appeal_details,
                                        AppealStatus='Pending',
                                        created_at=manila_now(),
                                        updated_at=manila_now())
    
    db.add(new_appeal)
    db.commit()

    if election_appeals_data.attachment:
        response = cloudinary.uploader.upload(election_appeals_data.attachment, 
                                            public_id=f"Appeals/appeal_{new_appeal.ElectionAppealsId}",
                                            tags=[f'appeal_{new_appeal.ElectionAppealsId}'])
        
        new_appeal.AttachmentAssetId = response['secure_url']
        db.commit()

    return {"response": "success"}

class ElectionAppealsRespondData(BaseModel):
    id: int
    subject: str
    response: str

@router.post("/election-appeals/respond", tags=["ElectionAppeals"])
def save_Election_Appeals_Respond(data: ElectionAppealsRespondData, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Check if the appeal exists in the database
    appeal = db.query(ElectionAppeals).get(data.id)

    if not appeal:
        return JSONResponse(status_code=404, content={"error": "Appeal does not exist."})

    # Update the appeal status in the ElectionAppeals table
    appeal.AppealEmailSubject = data.subject
    appeal.AppealResponse = data.response
    appeal.AppealStatus = 'Responded'
    appeal.updated_at = manila_now()

    db.commit()

    # Get the email of student
    student = db.query(Student).filter(Student.StudentNumber == appeal.StudentNumber).first()
    student_email = student.Email

    background_tasks.add_task(send_appeal_response_email(student_email, data.subject, data.response, data.id))

    return {"response": "success"}

#################################################################
## SGEReports APIs ## 

""" SGEReports Table APIs """

""" ** GET Methods: SGEReports Table APIs ** """
@router.get("/reports/election/{id}", tags=["Reports"])
def get_Reports_By_Election_Id(id: int, db: Session = Depends(get_db)):
    election = db.query(Election).filter(Election.ElectionId == id).first()
    election_data = {}  # Changed from [] to {}

    student_organization = db.query(StudentOrganization).filter(StudentOrganization.StudentOrganizationId == election.StudentOrganizationId).first()
    
    # Get the studentorganization logo using secure URL from Cloudinary
    election_data["StudentOrganizationLogo"] = student_organization.OrganizationLogo

    election_data['StudentOrganizationName'] = student_organization.OrganizationName
    election_data['ElectionName'] = election.ElectionName
    election_data['Semester'] = election.Semester
    election_data['SchoolYear'] = election.SchoolYear
    election_data['CourseRequirement'] = student_organization.OrganizationMemberRequirements

    now = manila_now()
    if now < election.CoCFilingStart.replace(tzinfo=timezone('Asia/Manila')):
        election_data["ElectionPeriod"] = "Pre-Election"
    elif now >= election.CoCFilingStart.replace(tzinfo=timezone('Asia/Manila')) and now < election.CoCFilingEnd.replace(tzinfo=timezone('Asia/Manila')):
        election_data["ElectionPeriod"] = "Filing Period"
    elif now >= election.CampaignStart.replace(tzinfo=timezone('Asia/Manila')) and now < election.CampaignEnd.replace(tzinfo=timezone('Asia/Manila')):
        election_data["ElectionPeriod"] = "Campaign Period"
    elif now >= election.VotingStart.replace(tzinfo=timezone('Asia/Manila')) and now < election.VotingEnd.replace(tzinfo=timezone('Asia/Manila')):
        election_data["ElectionPeriod"] = "Voting Period"
    elif now >= election.AppealStart.replace(tzinfo=timezone('Asia/Manila')) and now < election.AppealEnd.replace(tzinfo=timezone('Asia/Manila')):
        election_data["ElectionPeriod"] = "Appeal Period"
    else:
        election_data["ElectionPeriod"] = "Post-Election"


    # Count all candidates for this election
    num_candidates = db.query(Candidates).filter(Candidates.ElectionId == id).count()
    election_data['NumberOfCandidates'] = num_candidates    

    # Count all partylists for this election which is approved
    num_partylists = db.query(PartyList).filter(PartyList.ElectionId == id, PartyList.Status == 'Approved').count()
    election_data['NumberOfPartylists'] = num_partylists

    # Count all voters population for this election
    num_voters = db.query(Eligibles).filter(Eligibles.ElectionId == id).count()
    election_data['NumberOfVoters'] = num_voters

    # Count all voters who voted for this election unique by student number
    active_voters = db.query(VotingsTracker).filter(VotingsTracker.ElectionId == id).distinct(VotingsTracker.VoterStudentNumber).count()
    election_data['NumberOfActiveVoters'] = active_voters
    
    # Count all voters who did not vote for this election
    inactive_voters = num_voters - active_voters
    election_data['NumberOfInactiveVoters'] = inactive_voters

    # Count each voters course distribution for this election
    # Insert all coursecode in course table as key
    course_distribution = {}
    courses = db.query(Course).all()
    for course in courses:
        course_distribution[course.CourseCode] = 0

    # Count all in votingstracker table with election id and determine the coursecode via course id unique by student number
    votes_per_course = db.query(VotingsTracker).filter(VotingsTracker.ElectionId == id).distinct(VotingsTracker.VoterStudentNumber).all()
    for vote in votes_per_course:
        # Increment coursecode count via course id
        course = db.query(Course).filter(Course.CourseId == vote.CourseId).first()
        course_distribution[course.CourseCode] += 1

    election_data['CourseDistribution'] = course_distribution

    # Count approved and rejected coc
    approved_coc = db.query(CoC).filter(CoC.ElectionId == id, CoC.Status == 'Approved').count()
    election_data['NumberOfApprovedCoC'] = approved_coc

    rejected_coc = db.query(CoC).filter(CoC.ElectionId == id, CoC.Status == 'Rejected').count()
    election_data['NumberOfRejectedCoC'] = rejected_coc

    # Count approved and rejected partylist
    approved_partylist = db.query(PartyList).filter(PartyList.ElectionId == id, PartyList.Status == 'Approved').count()
    election_data['NumberOfApprovedPartylist'] = approved_partylist

    rejected_partylist = db.query(PartyList).filter(PartyList.ElectionId == id, PartyList.Status == 'Rejected').count()
    election_data['NumberOfRejectedPartylist'] = rejected_partylist

    # Return all candidates, fullname, student number
    candidates = db.query(Candidates).filter(Candidates.ElectionId == id).order_by(Candidates.CandidateId).all()
    candidates_dict = []
    for candidate in candidates:
        student = db.query(Student).filter(Student.StudentNumber == candidate.StudentNumber).first()
        candidates_dict.append({
            "FullName": student.FirstName + " " + student.MiddleName + " " + student.LastName if student.MiddleName else student.FirstName + " " + student.LastName,
            "StudentNumber": student.StudentNumber,
        })

    election_data['Candidates'] = candidates_dict

    return {"election": election_data}

@router.get("/reports/election/{election_id}/candidate/{student_number}", tags=["Reports"])
def get_Reports_By_Election_Id_And_Candidate_StudentNumber(election_id: int, student_number: str, db: Session = Depends(get_db)):
    # Get the candidate info from coc
    coc = db.query(CoC).filter(CoC.ElectionId == election_id, CoC.StudentNumber == student_number).first()
    coc_dict = {}

    # Get the fullname of the candidate
    student = db.query(Student).filter(Student.StudentNumber == student_number).first()
    coc_dict["FullName"] = student.FirstName + " " + student.MiddleName + " " + student.LastName if student.MiddleName else student.FirstName + " " + student.LastName
    
    # Get the display photo using secure URL from Cloudinary
    coc_dict["DisplayPhoto"] = coc.DisplayPhoto

    # Get the position name of the candidate
    coc_dict["PositionName"] = coc.SelectedPositionName

    # Get the partylist name of the candidate
    partylist = db.query(PartyList).filter(PartyList.PartyListId == coc.PartyListId).first()
    
    if partylist:
        coc_dict["PartyListName"] = partylist.PartyListName
    else:
        coc_dict["PartyListName"] = "Independent"

    # Get candidate course, year and section
    course = ""
    year = ""
    section = ""

    get_student_metadata = get_Student_Metadata_by_studnumber(student_number)
    get_student_section = get_Student_Section_by_studnumber(student_number)

    if "CourseCode" in get_student_metadata:
        course = get_student_metadata["CourseCode"]
        year = get_student_metadata["Year"]

    if get_student_section:
        section = get_student_section

    coc_dict["CourseYearSection"] = f"{course} {year}-{section}"

    # Get the motto 
    coc_dict["Motto"] = coc.Motto

    # Get candidate platform
    coc_dict["Platform"] = coc.Platform

    # Get candidate votes 
    candidate = db.query(Candidates).filter(Candidates.ElectionId == election_id, Candidates.StudentNumber == student_number).first()
    coc_dict["Votes"] = candidate.Votes

    # Get candidate abstains
    coc_dict["Abstains"] = candidate.TimesAbstained

    # Get votes per course (Can be specified by VotingTrackers table but course is not included in the table Student and structure will change so keep this for now)
    candidate_id = candidate.CandidateId

    # loop in votingstracker to get the votes per course with corresponing election id and votedcandidate id unique by student number
    votes_per_course = db.query(VotingsTracker).filter(VotingsTracker.ElectionId == election_id, VotingsTracker.VotedCandidateId == candidate_id).distinct(VotingsTracker.VoterStudentNumber).all()
    
    # Make a dict and insert all coursecode in course table as key and initialize the value to 0
    course_dict = {}
    courses = db.query(Course).all()
    for course in courses:
        course_dict[course.CourseCode] = 0

    # Loop in votes_per_course and increment the value of coursecode key in course_dict
    for vote in votes_per_course:
        # Get the courscode via courseid
        course = db.query(Course).filter(Course.CourseId == vote.CourseId).first()
        course_code = course.CourseCode

        course_dict[course_code] += 1

    coc_dict["VotesPerCourse"] = course_dict

    # Get candidate ratings
    coc_dict["OneStar"] = candidate.OneStar
    coc_dict["TwoStar"] = candidate.TwoStar
    coc_dict["ThreeStar"] = candidate.ThreeStar
    coc_dict["FourStar"] = candidate.FourStar
    coc_dict["FiveStar"] = candidate.FiveStar
    
    return {"candidate": coc_dict}


#################################################################
app.include_router(router)