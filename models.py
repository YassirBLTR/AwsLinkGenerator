from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

# Association table for many-to-many relationship between users and AWS keys
user_aws_key_association = Table(
    'user_aws_keys',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('aws_key_id', Integer, ForeignKey('aws_keys.id'), primary_key=True),
    Column('assigned_at', DateTime(timezone=True), server_default=func.now())
)

# Association table for many-to-many relationship between teams and AWS keys
team_aws_key_association = Table(
    'team_aws_keys',
    Base.metadata,
    Column('team_id', Integer, ForeignKey('teams.id'), primary_key=True),
    Column('aws_key_id', Integer, ForeignKey('aws_keys.id'), primary_key=True),
    Column('assigned_at', DateTime(timezone=True), server_default=func.now())
)

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # One-to-many relationship with users (team members)
    members = relationship("User", back_populates="team", foreign_keys="User.team_id")
    
    # One-to-one relationship with team leader
    leader_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    leader = relationship("User", foreign_keys=[leader_id], post_update=True)
    
    # Many-to-many relationship with AWS keys
    aws_keys = relationship("AWSKey", secondary=team_aws_key_association, back_populates="teams")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    is_team_leader = Column(Boolean, default=False)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Many-to-many relationship with AWS keys
    aws_keys = relationship("AWSKey", secondary=user_aws_key_association, back_populates="users")
    
    # Many-to-one relationship with team
    team = relationship("Team", back_populates="members", foreign_keys=[team_id])

class AWSKey(Base):
    __tablename__ = "aws_keys"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    access_key = Column(String, nullable=False)
    secret_key = Column(String, nullable=False)
    # Remove user_id foreign key as we now use many-to-many
    status = Column(String, default="unchecked")  # unchecked, active, invalid, expired, no_permissions
    last_checked = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Many-to-many relationship with users
    users = relationship("User", secondary=user_aws_key_association, back_populates="aws_keys")
    
    # Many-to-many relationship with teams
    teams = relationship("Team", secondary=team_aws_key_association, back_populates="aws_keys")
