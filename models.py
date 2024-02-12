from database import engine, Base, SessionLocal
from sqlalchemy.orm import sessionmaker, relationship

from sqlalchemy import Column, Integer, Float, String, Date, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.sql import func

from dotenv import load_dotenv
load_dotenv()
import os

from cloudinary.api import resources_by_tag

from datetime import datetime, date, timedelta

Session = sessionmaker(bind=engine)
session = Session()

##############################################################################
## SPS Tables ##

class Student(Base):
    __tablename__ = 'SPSStudent'

    StudentId = Column(Integer, primary_key=True, autoincrement=True)
    StudentNumber = Column(String(30), unique=True, nullable=False)
    FirstName = Column(String(50), nullable=False)
    LastName = Column(String(50), nullable=False)
    MiddleName = Column(String(50))
    Email = Column(String(50), unique=True, nullable=False)
    Password = Column(String(256), nullable=False)
    Gender = Column(Integer, nullable=True)
    DateOfBirth = Column(Date)
    PlaceOfBirth = Column(String(50))
    ResidentialAddress = Column(String(50))
    MobileNumber = Column(String(11))
    IsOfficer = Column(Boolean, default=False)
    Token = Column(String(128))
    TokenExpiration = Column(DateTime)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            'StudentId': self.StudentId,
            'StudentNumber': self.StudentNumber,
            'FirstName': self.FirstName,
            'LastName': self.LastName,
            'MiddleName': self.MiddleName,
            'Email': self.Email,
            'Gender': self.Gender,
            'DateOfBirth': self.DateOfBirth,
            'PlaceOfBirth': self.PlaceOfBirth,
            'ResidentialAddress': self.ResidentialAddress,
            'MobileNumber': self.MobileNumber,
            'IsOfficer': self.IsOfficer,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
class CourseEnrolled(Base):
    __tablename__ = 'SPSCourseEnrolled'

    CourseId = Column(Integer, ForeignKey('SPSCourse.CourseId', ondelete="CASCADE"), primary_key=True)
    StudentId = Column(Integer, ForeignKey('SPSStudent.StudentId', ondelete="CASCADE"), primary_key=True)
    DateEnrolled = Column(Date)
    Status = Column(Integer, nullable=False)
    CurriculumYear = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            'CourseId': self.CourseId,
            'StudentId': self.StudentId,
            'DateEnrolled': self.DateEnrolled.isoformat() if self.DateEnrolled else None,
            'Status': self.Status,
            'CurriculumYear': self.CurriculumYear,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
class Course(Base):
    __tablename__ = 'SPSCourse'

    CourseId = Column(Integer, primary_key=True, autoincrement=True)
    CourseCode = Column(String(10), unique=True)
    Name = Column(String(200))
    Description = Column(String(200))
    IsValidPUPQCCourses = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            'CourseId': self.CourseId,
            'CourseCode': self.CourseCode,
            'Name': self.Name,
            'Description': self.Description,
            'IsValidPUPQCCourses': self.IsValidPUPQCCourses,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
class StudentClassGrade(Base):
    __tablename__ = 'SPSStudentClassGrade'
    
    StudentId = Column(Integer, ForeignKey('SPSStudent.StudentId', ondelete="CASCADE"), primary_key=True)
    ClassId = Column(Integer, ForeignKey('SPSClass.ClassId', ondelete="CASCADE"), primary_key=True)
    Grade = Column(Float)
    Lister = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            'StudentId': self.StudentId,
            'ClassId': self.ClassId,
            'Grade': self.Grade,
            'Lister': self.Lister,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Class(Base):
    __tablename__ = 'SPSClass'

    ClassId = Column(Integer, primary_key=True, autoincrement=True)
    MetadataId = Column(Integer, ForeignKey('SPSMetadata.MetadataId', ondelete="CASCADE"))
    Section = Column(Integer)
    IsGradeFinalized = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            'ClassId': self.ClassId,
            'MetadataId': self.MetadataId,
            'Section': self.Section,
            'IsGradeFinalized': self.IsGradeFinalized,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Metadata(Base):
    __tablename__ = 'SPSMetadata'

    MetadataId = Column(Integer, primary_key=True, autoincrement=True)
    CourseId = Column(Integer, ForeignKey('SPSCourse.CourseId', ondelete="CASCADE"))
    Year = Column(Integer, nullable=False)
    Semester = Column(Integer, nullable=False)
    Batch = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            'MetadataId': self.MetadataId,
            'CourseId': self.CourseId,
            'Year': self.Year,
            'Semester': self.Semester,
            'Batch': self.Batch,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

##############################################################################
## SGE tables ## 

"""class Student(Base):
    __tablename__ = "SGEStudent"
    
    StudentId = Column(Integer, primary_key=True)
    StudentNumber = Column(String(15), unique=True)
    FirstName = Column(String)
    MiddleName = Column(String, nullable=True)
    LastName = Column(String)
    EmailAddress = Column(String, unique=True)
    Year = Column(String)
    Course = Column(String)
    CurrentSemesterEnrolled = Column(String)
    YearEnrolled = Column(String)
    IsOfficer = Column(Boolean)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "StudentId": self.StudentId,
            "StudentNumber": self.StudentNumber,
            "FirstName": self.FirstName,
            "MiddleName": self.MiddleName,
            "LastName": self.LastName,
            "EmailAddress": self.EmailAddress,
            "Year": self.Year,
            "Course": self.Course,
            "CurrentSemesterEnrolled": self.CurrentSemesterEnrolled,
            "YearEnrolled": self.YearEnrolled,
            "IsOfficer": self.IsOfficer,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }"""
    
class Election(Base):
    __tablename__ = "SGEElection"
    
    ElectionId = Column(Integer, primary_key=True)
    ElectionName = Column(String)
    StudentOrganizationId = Column(Integer, ForeignKey('SGEStudentOrganization.StudentOrganizationId'))
    ElectionStatus = Column(String)
    SchoolYear = Column(String)
    Semester = Column(String)
    CreatedBy = Column(String, ForeignKey('SPSStudent.StudentNumber'))

    ElectionStart = Column(DateTime)
    ElectionEnd = Column(DateTime)
    CoCFilingStart = Column(DateTime)
    CoCFilingEnd = Column(DateTime)
    CampaignStart = Column(DateTime)
    CampaignEnd = Column(DateTime)
    VotingStart = Column(DateTime)
    VotingEnd = Column(DateTime)
    AppealStart = Column(DateTime)
    AppealEnd = Column(DateTime)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self, row=None):
        return {
            "ElectionId": self.ElectionId,
            "count": row,
            "ElectionName": self.ElectionName,
            "StudentOrganizationId": self.StudentOrganizationId,
            "ElectionStatus": self.ElectionStatus,
            "SchoolYear": self.SchoolYear,
            "Semester": self.Semester,
            "CreatedBy": self.CreatedBy,

            "ElectionStart": self.ElectionStart.isoformat() if self.ElectionStart else None,
            "ElectionEnd": self.ElectionEnd.isoformat() if self.ElectionEnd else None,
            "CoCFilingStart": self.CoCFilingStart.isoformat() if self.CoCFilingStart else None,
            "CoCFilingEnd": self.CoCFilingEnd.isoformat() if self.CoCFilingEnd else None,
            "CampaignStart": self.CampaignStart.isoformat() if self.CampaignStart else None,
            "CampaignEnd": self.CampaignEnd.isoformat() if self.CampaignEnd else None,
            "VotingStart": self.VotingStart.isoformat() if self.VotingStart else None,
            "VotingEnd": self.VotingEnd.isoformat() if self.VotingEnd else None,
            "AppealStart": self.AppealStart.isoformat() if self.AppealStart else None,
            "AppealEnd": self.AppealEnd.isoformat() if self.AppealEnd else None,
            
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
class CreatedElectionPosition(Base):
    __tablename__ = "SGECreatedElectionPosition"
    
    CreatedElectionPositionId = Column(Integer, primary_key=True)
    ElectionId = Column(Integer, ForeignKey('SGEElection.ElectionId'))
    PositionName = Column(String)
    PositionQuantity = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self, row=None):
        return {
            "CreatedElectionPositionId": self.CreatedElectionPositionId,
            "count": row,
            "ElectionId": self.ElectionId,
            "PositionName": self.PositionName,
            "PositionQuantity": self.PositionQuantity,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
class SavedPosition(Base):
    __tablename__ = "SGESavedPosition"
    
    SavedPositionId = Column(Integer, primary_key=True)
    PositionName = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "SavedPositionId": self.SavedPositionId,
            "PositionName": self.PositionName,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
class Announcement(Base):
    __tablename__ = "SGEAnnouncement"
    
    AnnouncementId = Column(Integer, primary_key=True)
    AnnouncementType = Column(String)
    AnnouncementTitle = Column(String)
    AnnouncementBody = Column(Text)
    AttachmentType = Column(String)
    AttachmentImage = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self, row=None, include_images=False):
        data = {
            "AnnouncementId": self.AnnouncementId,
            "count": row,
            "type": "announcement",
            "AnnouncementType": self.AnnouncementType,
            "AnnouncementTitle": self.AnnouncementTitle,
            "AnnouncementBody": self.AnnouncementBody,
            "AttachmentType": self.AttachmentType,
            "AttachmentImage": self.AttachmentImage,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

        tag_name = self.AttachmentImage
        if tag_name and include_images:
            response = resources_by_tag(tag_name)
            data['images'] = [{"url": resource['secure_url'], "name": resource['public_id'].split('/')[-1]} for resource in response['resources']]
        else:
            data['images'] = []

        return data


class Rule(Base):
    __tablename__ = "SGERules"
    
    RuleId = Column(Integer, primary_key=True)
    RuleTitle = Column(String)
    RuleBody = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self, row=None):
        return {
            "RuleId": self.RuleId,
            "count": row,
            "type": "rule",
            "RuleTitle": self.RuleTitle,
            "RuleBody": self.RuleBody,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class Guideline(Base):
    __tablename__ = "SGEGuidelines"
    
    GuideId = Column(Integer, primary_key=True)
    GuidelineTitle = Column(String)
    GuidelineBody = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self, row=None):
        return {
            "GuideId": self.GuideId,
            "count": row,
            "type": "guideline",
            "GuidelineTitle": self.GuidelineTitle,
            "GuidelineBody": self.GuidelineBody,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
class Certifications(Base):
    __tablename__ = "SGECertifications"
    
    CertificationId = Column(Integer, primary_key=True)
    Title = Column(String)
    ElectionId = Column(Integer, ForeignKey('SGEElection.ElectionId'))
    StudentNumber = Column(String(15), ForeignKey('SPSStudent.StudentNumber'))
    Date = Column(Date)
    AdminSignatoryQuantity = Column(String)
    AssetId = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "CertificationId": self.CertificationId,
            "Title": self.Title,
            "ElectionId": self.ElectionId,
            "StudentNumber": self.StudentNumber,
            "Date": self.Date.isoformat() if self.Date else None,
            "AdminSignatoryQuantity": self.AdminSignatoryQuantity,
            "AssetId": self.AssetId,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
class CreatedAdminSignatory(Base):
    __tablename__ = "SGECreatedAdminSignatory"
    
    CreatedAdminSignatoryId = Column(Integer, primary_key=True)
    CertificationId = Column(Integer, ForeignKey('SGECertifications.CertificationId'))
    SignatoryName = Column(String)
    SignatoryPosition = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "CreatedAdminSignatory": self.CreatedAdminSignatoryId,
            "CertificationId": self.CertificationId,
            "SignatoryName": self.SignatoryName,
            "SignatoryPosition": self.SignatoryPosition,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class Code(Base):
    __tablename__ = "SGECode"

    CodeId = Column(Integer, primary_key=True)
    StudentNumber = Column(String(15), ForeignKey('SPSStudent.StudentNumber'))
    CodeValue = Column(Text)
    CodeType = Column(String)
    CodeExpirationDate = Column(DateTime)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "CodeId": self.CodeId,
            "StudentNumber": self.StudentNumber,
            "CodeValue": self.CodeValue,
            "CodeType": self.CodeType,
            "CodeExpirationDate": self.CodeExpirationDate.isoformat() if self.CodeExpirationDate else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
class InsertDataQueues(Base):
    __tablename__ = "SGEInsertDataQueues"

    QueueId = Column(Integer, primary_key=True)
    QueueName = Column(String)
    ToEmailTotal = Column(Integer)
    EmailSent = Column(Integer)
    EmailFailed = Column(Integer)
    Status = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "QueueId": self.QueueId,
            "QueueName": self.QueueName,
            "ToEmailTotal": self.ToEmailTotal,
            "EmailSent": self.EmailSent,
            "EmailFailed": self.EmailFailed,
            "Status": self.Status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
class StudentOrganization(Base):
    __tablename__ = "SGEStudentOrganization"
    
    StudentOrganizationId = Column(Integer, primary_key=True)
    OrganizationLogo = Column(String)
    OrganizationName = Column(String)
    OrganizationMemberRequirements = Column(String)
    AdviserImage = Column(String)
    AdviserName = Column(String)
    Vision = Column(String, nullable=True)
    Mission = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "StudentOrganizationId": self.StudentOrganizationId,
            "OrganizationLogo": self.OrganizationLogo,
            "OrganizationName": self.OrganizationName,
            "OrganizationMemberRequirements": self.OrganizationMemberRequirements,
            "AdviserImage": self.AdviserImage,
            "AdviserName": self.AdviserName,
            "Vision": self.Vision,
            "Mission": self.Mission,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class OrganizationOfficer(Base):
    __tablename__ = "SGEOrganizationOfficer"

    OrganizationOfficerId = Column(Integer, primary_key=True)
    StudentOrganizationId = Column(Integer, ForeignKey('SGEStudentOrganization.StudentOrganizationId'))
    StudentNumber = Column(String(15), ForeignKey('SPSStudent.StudentNumber'), unique=True)
    OfficerPassword = Column(Text)
    Image = Column(String)
    Position = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "OrganizationOfficerId": self.OrganizationOfficerId,
            "StudentOrganizationId": self.StudentOrganizationId,
            "StudentNumber": self.StudentNumber,
            "Image": self.Image,
            "Position": self.Position,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class OrganizationMember(Base):
    __tablename__ = "SGEOrganizationMember"

    OrganizationMemberId = Column(Integer, primary_key=True)
    StudentOrganizationId = Column(Integer, ForeignKey('SGEStudentOrganization.StudentOrganizationId'))
    StudentNumber = Column(String(15), ForeignKey('SPSStudent.StudentNumber'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "OrganizationMemberId": self.OrganizationMemberId,
            "StudentOrganizationId": self.StudentOrganizationId,
            "StudentNumber": self.StudentNumber,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
class ElectionAppeals(Base):
    __tablename__ = "SGEElectionAppeals"

    ElectionAppealsId = Column(Integer, primary_key=True)
    StudentNumber = Column(String(15), ForeignKey('SPSStudent.StudentNumber'))
    AppealDetails = Column(Text)
    AppealEmailSubject = Column(String, nullable=True)
    AppealResponse = Column(Text, nullable=True)
    AppealStatus = Column(String, default="Pending")
    AttachmentAssetId = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "ElectionAppealsId": self.ElectionAppealsId,
            "StudentNumber": self.StudentNumber,
            "AppealDetails": self.AppealDetails,
            "AppealEmailSubject": self.AppealEmailSubject,
            "AppealResponse": self.AppealResponse,
            "AppealStatus": self.AppealStatus,
            "AttachmentAssetId": self.AttachmentAssetId,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

#########################################################
""" Comelec Portal Table Models """
class Comelec(Base):
    __tablename__ = "SGEComelec"

    ComelecId = Column(Integer, primary_key=True)
    StudentNumber = Column(String(15), ForeignKey('SPSStudent.StudentNumber'), unique=True)
    ComelecPassword = Column(Text)
    Position = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class CoC(Base):
    __tablename__ = "SGECoC"

    CoCId = Column(Integer, primary_key=True)
    ElectionId = Column(Integer, ForeignKey('SGEElection.ElectionId'))
    StudentNumber = Column(String(15), ForeignKey('SPSStudent.StudentNumber'))
    VerificationCode = Column(String)
    Motto = Column(String, nullable=True)
    Platform = Column(Text)
    PoliticalAffiliation = Column(String)
    PartyListId = Column(Integer, ForeignKey('SGEPartyList.PartyListId'), nullable=True)
    SelectedPositionName = Column(String)
    DisplayPhoto = Column(String)
    CertificationOfGrades = Column(String)
    Status = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self, row=None):
        return {
            "CoCId": self.CoCId,
            "count": row,
            "ElectionId": self.ElectionId,
            "StudentNumber": self.StudentNumber,
            "VerificationCode": self.VerificationCode,
            "Motto": self.Motto,
            "Platform": self.Platform,
            "PoliticalAffiliation": self.PoliticalAffiliation,
            "PartyListId": self.PartyListId,
            "SelectedPositionName": self.SelectedPositionName,
            "DisplayPhoto": self.DisplayPhoto,
            "CertificationOfGrades": self.CertificationOfGrades,
            "Status": self.Status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class PartyList(Base):
    __tablename__ = "SGEPartyList"

    PartyListId = Column(Integer, primary_key=True)
    ElectionId = Column(Integer, ForeignKey('SGEElection.ElectionId'))
    PartyListName = Column(String)
    Description = Column(String)
    Platforms = Column(String)
    EmailAddress = Column(String)
    CellphoneNumber = Column(String)
    Vision = Column(String)
    Mission = Column(String)
    ImageAttachment = Column(String, nullable=True)
    VideoAttachment = Column(String, nullable=True)
    Status = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self, row=None):
        return {
            "PartyListId": self.PartyListId,
            "count": row,
            "ElectionId": self.ElectionId,
            "PartyListName": self.PartyListName,
            "Description": self.Description,
            "Platforms": self.Platforms,
            "EmailAddress": self.EmailAddress,
            "CellphoneNumber": self.CellphoneNumber,
            "Vision": self.Vision,
            "Mission": self.Mission,
            "ImageAttachment": self.ImageAttachment,
            "VideoAttachment": self.VideoAttachment,
            "Status": self.Status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
class Candidates(Base):
    __tablename__ = "SGECandidates"

    CandidateId = Column(Integer, primary_key=True)
    StudentNumber = Column(String(15), ForeignKey('SPSStudent.StudentNumber'))
    ElectionId = Column(Integer, ForeignKey('SGEElection.ElectionId'))
    PartyListId = Column(Integer, ForeignKey('SGEPartyList.PartyListId'), nullable=True)
    SelectedPositionName = Column(String)
    DisplayPhoto = Column(String)
    Votes = Column(Integer, default=0)
    TimesAbstained = Column(Integer, default=0)
    Rating = Column(Integer, default=0)
    TimesRated = Column(Integer, default=0)
    OneStar = Column(Integer, default=0)
    TwoStar = Column(Integer, default=0)
    ThreeStar = Column(Integer, default=0)
    FourStar = Column(Integer, default=0)
    FiveStar = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self, row=None):
        return {
            "CandidateId": self.CandidateId,
            "StudentNumber": self.StudentNumber,
            "ElectionId": self.ElectionId,
            "PartyListId": self.PartyListId,
            "SelectedPositionName": self.SelectedPositionName,
            "DisplayPhoto": self.DisplayPhoto,
            "Rating": self.Rating,
            "TimesRated": self.TimesRated,
            "Votes": self.Votes,
            "TimesAbstained": self.TimesAbstained,
            "OneStar": self.OneStar,
            "TwoStar": self.TwoStar,
            "ThreeStar": self.ThreeStar,
            "FourStar": self.FourStar,
            "FiveStar": self.FiveStar,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
class RatingsTracker(Base):
    __tablename__ = "SGERatingsTracker"

    RatingsTrackerId = Column(Integer, primary_key=True)
    StudentNumber = Column(String(15), ForeignKey('SPSStudent.StudentNumber'))
    ElectionId = Column(Integer, ForeignKey('SGEElection.ElectionId'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "RatingsTrackerId": self.RatingsTrackerId,
            "StudentNumber": self.StudentNumber,
            "ElectionId": self.ElectionId,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
class VotingsTracker(Base):
    __tablename__ = "SGEVotingsTracker"

    VotingsTrackerId = Column(Integer, primary_key=True)
    VoterStudentNumber = Column(String(15), ForeignKey('SPSStudent.StudentNumber'))
    VotedCandidateId = Column(Integer, ForeignKey('SGECandidates.CandidateId'))
    CourseId = Column(Integer)
    ElectionId = Column(Integer, ForeignKey('SGEElection.ElectionId'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "VotingsTrackerId": self.VotingsTrackerId,
            "VoterStudentNumber": self.VoterStudentNumber,
            "VotedCandidateId": self.VotedCandidateId,
            "CourseId": self.CourseId,
            "ElectionId": self.ElectionId,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
class ElectionAnalytics(Base):
    __tablename__ = "SGEElectionAnalytics"

    ElectionAnalyticsId = Column(Integer, primary_key=True)
    ElectionId = Column(Integer, ForeignKey('SGEElection.ElectionId'))
    AbstainCount = Column(Integer, default=0)
    VotesCount = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "ElectionAnalyticsId": self.ElectionAnalyticsId,
            "ElectionId": self.ElectionId,
            "AbstainCount": self.AbstainCount,
            "VotesCount": self.VotesCount,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
class ElectionWinners(Base):
    __tablename__ = "SGEElectionWinners"

    ElectionWinnersId = Column(Integer, primary_key=True)
    ElectionId = Column(Integer, ForeignKey('SGEElection.ElectionId'))
    StudentNumber = Column(String(15), ForeignKey('SPSStudent.StudentNumber'))
    SelectedPositionName = Column(String)
    Votes = Column(Integer, default=0)
    IsTied = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "ElectionWinnersId": self.ElectionWinnersId,
            "ElectionId": self.ElectionId,
            "StudentNumber": self.StudentNumber,
            "SelectedPositionName": self.SelectedPositionName,
            "Votes": self.Votes,
            "IsTied": self.IsTied,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
class Eligibles(Base):
    __tablename__ = "SGEEligibles"

    EligibleId = Column(Integer, primary_key=True)
    StudentNumber = Column(String(15), ForeignKey('SPSStudent.StudentNumber')) # Not unique since a student can be eligible for multiple elections
    ElectionId = Column(Integer, ForeignKey('SGEElection.ElectionId'))
    HasVotedOrAbstained = Column(Boolean, default=False)
    VotingPassword = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "EligibleId": self.EligibleId,
            "StudentNumber": self.StudentNumber,
            "ElectionId": self.ElectionId,
            "IsVotedOrAbstained": self.HasVotedOrAbstained,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
class VotingReceipt(Base):
    __tablename__ = "SGEVotingReceipt"

    VotingReceiptId = Column(Integer, primary_key=True)
    ElectionId = Column(Integer, ForeignKey('SGEElection.ElectionId'))
    StudentNumber = Column(String(15), ForeignKey('SPSStudent.StudentNumber'))
    ReceiptPDF = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "VotingReceiptId": self.VotingReceiptId,
            "ElectionId": self.ElectionId,
            "StudentNumber": self.StudentNumber,
            "ReceiptPDF": self.ReceiptPDF,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
class CertificationsSigned(Base):
    __tablename__ = "SGECertificationsSigned2"

    CertificationsSignedId = Column(Integer, primary_key=True)
    CertificationTitle = Column(String)
    DateUploaded = Column(Date)
    FileURL = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "CertificationsSignedId": self.CertificationsSignedId,
            "CertificationTitle": self.CertificationTitle,
            "DateUploaded": self.DateUploaded.isoformat() if self.DateUploaded else None,
            "FileURL": self.FileURL,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
##################################################################
# Insert datas to tables
db = SessionLocal()
ADD_SAMPLE_DATA = os.getenv("ADD_SAMPLE_DATA")

if ADD_SAMPLE_DATA == "True" and False:
    from data.student import student_data
    from data.course import course_data
    from data.courseEnrolled import course_enrolled_data
    from data.metadata import metadata_data
    from data.classes import class_data
    from data.studentClassGrade import student_class_grade_data

    def create_student():
        for student in student_data:
            existing_student = db.query(Student).filter(Student.StudentNumber == student["StudentNumber"]).first()

            if existing_student:
                continue

            new_student = Student(**student)

            db.add(new_student)
            db.commit()
            db.close()

    def create_course():
        for course in course_data:
            existing_course = db.query(Course).filter(Course.CourseCode == course["CourseCode"]).first()

            if existing_course:
                continue

            new_course = Course(**course)

            db.add(new_course)
            db.commit()
            db.close()

    def create_course_enrolled():
        for course_enrolled in course_enrolled_data:
            existing_course_enrolled = db.query(CourseEnrolled).filter(CourseEnrolled.StudentId == course_enrolled["StudentId"]).first()

            if existing_course_enrolled:
                continue

            new_course_enrolled = CourseEnrolled(**course_enrolled)

            db.add(new_course_enrolled)
            db.commit()
            db.close()

    def create_metadata():
        for metadata in metadata_data:
            existing_metadata = db.query(Metadata).filter(Metadata.MetadataId == metadata["MetadataId"]).first()

            if existing_metadata:
                continue

            new_metadata = Metadata(**metadata)

            db.add(new_metadata)
            db.commit()
            db.close()

    def create_class():
        for class_ in class_data:
            existing_class = db.query(Class).filter(Class.ClassId == class_["ClassId"]).first()

            if existing_class:
                continue

            new_class = Class(**class_)

            db.add(new_class)
            db.commit()
            db.close()

    def create_student_class_grade():
        for student_class_grade in student_class_grade_data:
            existing_student_class_grade = db.query(StudentClassGrade).filter(StudentClassGrade.StudentId == student_class_grade["StudentId"]).first()

            if existing_student_class_grade:
                continue

            new_student_class_grade = StudentClassGrade(**student_class_grade)

            db.add(new_student_class_grade)
            db.commit()
            db.close()
##################################################################
# Call methods for creating data
if ADD_SAMPLE_DATA == "True" and False:   
    create_student()
    
    create_course()
    create_course_enrolled()
    create_metadata()
    create_class()
    create_student_class_grade()