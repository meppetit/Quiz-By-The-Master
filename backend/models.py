import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def utcnow():
    return datetime.now(timezone.utc)


class Participant(Base):
    __tablename__ = "participants"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    phone = Column(String(30), nullable=False, unique=True, index=True)
    school = Column(String(255))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class QuestionSet(Base):
    __tablename__ = "question_sets"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    questions = relationship("Question", back_populates="question_set")


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    set_id = Column(Integer, ForeignKey("question_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    options = Column(JSONB, nullable=False)
    correct_option = Column(String(4), nullable=False)
    category = Column(String(80))
    order_index = Column(Integer, nullable=False, default=0)
    question_set = relationship("QuestionSet", back_populates="questions")


class Attempt(Base):
    __tablename__ = "attempts"
    id = Column(Integer, primary_key=True)
    token = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True, default=uuid.uuid4)
    participant_id = Column(Integer, ForeignKey("participants.id", ondelete="CASCADE"), nullable=False, unique=True)
    set_id = Column(Integer, ForeignKey("question_sets.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at = Column(DateTime(timezone=True))
    time_taken_seconds = Column(Integer)
    score = Column(Integer)


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question"),)
    id = Column(Integer, primary_key=True)
    attempt_id = Column(Integer, ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    selected_option = Column(String(4), nullable=False)
    is_correct = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
