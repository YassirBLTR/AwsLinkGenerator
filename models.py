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

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Many-to-many relationship with AWS keys
    aws_keys = relationship("AWSKey", secondary=user_aws_key_association, back_populates="users")

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
