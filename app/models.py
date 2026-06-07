from datetime import datetime
from typing import List
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
  __tablename__ = "users"

  id: Mapped[int] = mapped_column(primary_key=True)
  username: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)
  hashed_password: Mapped[str] = mapped_column(nullable=False)

  # Establish a connection (join) to the Message table
  messages: Mapped[List["Message"]] = relationship("Message", back_populates="sender")


class Message(Base):
  __tablename__ = "messages"

  id: Mapped[int] = mapped_column(primary_key=True)
  content: Mapped[str] = mapped_column(nullable=False)
  created_at: Mapped[datetime] = mapped_column(server_default=func.now())
  updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

  # The Foreign key to link the message to a specfic user
  sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

  sender: Mapped["User"] = relationship("User", back_populates="messages")