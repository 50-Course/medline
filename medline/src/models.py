from typing import Optional

from sqlalchemy import String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import Column

Base = declarative_base()


class Product(Base):
    __tablename__ = "products"


class Merchant(Base):
    __tablename__ = "merchants"


class Location(Base):
    __tablename__ = "location"
