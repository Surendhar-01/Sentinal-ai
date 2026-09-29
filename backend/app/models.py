from datetime import datetime
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class User(Base):
    __tablename__="users"
    id: Mapped[int]=mapped_column(primary_key=True)
    username: Mapped[str]=mapped_column(String(80),unique=True,index=True)
    password_hash: Mapped[str]=mapped_column(String(255))
    role: Mapped[str]=mapped_column(String(30),default="analyst")

class Document(Base):
    __tablename__="documents"
    id: Mapped[int]=mapped_column(primary_key=True)
    filename: Mapped[str]=mapped_column(String(255))
    content_type: Mapped[str]=mapped_column(String(100),default="application/octet-stream")
    size: Mapped[int]=mapped_column(Integer,default=0)
    status: Mapped[str]=mapped_column(String(30),default="pending")
    chunk_count: Mapped[int]=mapped_column(Integer,default=0)
    embedding_provider: Mapped[str]=mapped_column(String(80),default="hash")
    source_metadata: Mapped[str]=mapped_column(Text,default="{}")
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class Chunk(Base):
    __tablename__="chunks"
    id: Mapped[int]=mapped_column(primary_key=True)
    document_id: Mapped[int]=mapped_column(ForeignKey("documents.id"),index=True)
    page: Mapped[int]=mapped_column(Integer,default=1)
    position: Mapped[int]=mapped_column(Integer)
    text: Mapped[str]=mapped_column(Text)
    embedding: Mapped[str]=mapped_column(Text)

class AuditEvent(Base):
    __tablename__="audit_events"
    id: Mapped[int]=mapped_column(primary_key=True)
    actor: Mapped[str]=mapped_column(String(80))
    action: Mapped[str]=mapped_column(String(120))
    target: Mapped[str]=mapped_column(String(255),default="")
    detail: Mapped[str]=mapped_column(Text,default="{}")
    timestamp: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)

class Approval(Base):
    __tablename__="approvals"
    id: Mapped[int]=mapped_column(primary_key=True)
    execution_id: Mapped[int]=mapped_column(ForeignKey("executions.id"),nullable=True,index=True)
    title: Mapped[str]=mapped_column(String(255))
    risk: Mapped[str]=mapped_column(String(20),default="high")
    status: Mapped[str]=mapped_column(String(20),default="pending")
    requested_by: Mapped[str]=mapped_column(String(80),default="Tool Agent")
    rationale: Mapped[str]=mapped_column(Text,default="")
    recommendation: Mapped[str]=mapped_column(Text,default="")
    explanation: Mapped[str]=mapped_column(Text,default="")
    supporting_evidence: Mapped[str]=mapped_column(Text,default="[]")
    agents_involved: Mapped[str]=mapped_column(Text,default="[]")
    requested_action: Mapped[str]=mapped_column(Text,default="")
    reviewer: Mapped[str]=mapped_column(String(80),default="")
    decision_note: Mapped[str]=mapped_column(Text,default="")
    decided_at: Mapped[datetime]=mapped_column(DateTime,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class Execution(Base):
    __tablename__="executions"
    id: Mapped[int]=mapped_column(primary_key=True)
    query: Mapped[str]=mapped_column(Text)
    status: Mapped[str]=mapped_column(String(30),default="QUEUED")
    requested_by: Mapped[str]=mapped_column(String(80))
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    completed_at: Mapped[datetime]=mapped_column(DateTime,nullable=True)

class AgentTask(Base):
    __tablename__="agent_tasks"
    id: Mapped[int]=mapped_column(primary_key=True)
    execution_id: Mapped[int]=mapped_column(ForeignKey("executions.id"),index=True)
    sequence: Mapped[int]=mapped_column(Integer)
    agent: Mapped[str]=mapped_column(String(80))
    description: Mapped[str]=mapped_column(Text)
    status: Mapped[str]=mapped_column(String(30),default="QUEUED")
    start_time: Mapped[datetime]=mapped_column(DateTime,nullable=True)
    end_time: Mapped[datetime]=mapped_column(DateTime,nullable=True)
    output: Mapped[str]=mapped_column(Text,default="")
    evidence: Mapped[str]=mapped_column(Text,default="[]")
    tool_name: Mapped[str]=mapped_column(String(100),default="")

class Finding(Base):
    __tablename__="findings"
    id: Mapped[int]=mapped_column(primary_key=True)
    execution_id: Mapped[int]=mapped_column(ForeignKey("executions.id"),index=True)
    statement: Mapped[str]=mapped_column(Text)
    verification_status: Mapped[str]=mapped_column(String(40),default="UNSUPPORTED")
    confidence: Mapped[float]=mapped_column(Float,default=0.0)
    supporting_evidence: Mapped[str]=mapped_column(Text,default="[]")
    contradictory_evidence: Mapped[str]=mapped_column(Text,default="[]")
    human_review_recommended: Mapped[int]=mapped_column(Integer,default=0)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class EvidenceItem(Base):
    __tablename__="evidence_items"
    id: Mapped[int]=mapped_column(primary_key=True)
    execution_id: Mapped[int]=mapped_column(ForeignKey("executions.id"),nullable=True,index=True)
    document_id: Mapped[int]=mapped_column(ForeignKey("documents.id"),nullable=True,index=True)
    title: Mapped[str]=mapped_column(String(255))
    excerpt: Mapped[str]=mapped_column(Text)
    reference: Mapped[str]=mapped_column(String(255),default="")
    added_by: Mapped[str]=mapped_column(String(80),default="")
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
