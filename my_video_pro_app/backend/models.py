import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    jobs = relationship('Job', back_populates='user')

class Job(Base):
    __tablename__ = 'jobs'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    filename = Column(String(255))
    status = Column(String(50))
    upload_time = Column(DateTime, default=datetime.utcnow)
    video_path = Column(String(500))
    output_dir = Column(String(500))
    current_step = Column(String(50))
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship('User', back_populates='jobs')
    steps = relationship('JobStep', back_populates='job', cascade='all, delete-orphan')
    subtitles = relationship('Subtitle', back_populates='job', cascade='all, delete-orphan')
    audio_files = relationship('AudioFile', back_populates='job', cascade='all, delete-orphan')

class JobStep(Base):
    __tablename__ = 'job_steps'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey('jobs.id'))
    step_name = Column(String(100))
    status = Column(String(50))
    file_path = Column(String(500))
    error_message = Column(Text)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    job = relationship('Job', back_populates='steps')

class Subtitle(Base):
    __tablename__ = 'subtitles'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey('jobs.id'))
    type = Column(String(50))  # original, edited, marathi, hindi, etc.
    file_path = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    job = relationship('Job', back_populates='subtitles')

class AudioFile(Base):
    __tablename__ = 'audio_files'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey('jobs.id'))
    type = Column(String(50))  # original, cleaned, voice, etc.
    file_path = Column(String(500))
    voice_id = Column(String(100))
    label = Column(String(100))
    stability = Column(Float)
    clarity = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    job = relationship('Job', back_populates='audio_files')
