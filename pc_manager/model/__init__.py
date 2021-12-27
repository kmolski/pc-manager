from os import getenv

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

DATABASE_URL = getenv(
    "PC_MANAGER_DATABASE_URL", "postgresql://localhost:5432/pc_manager"
)

engine = create_engine(DATABASE_URL)
db_session = scoped_session(sessionmaker(bind=engine))

Base = declarative_base()
Base.query = db_session.query_property()


def init_db():
    from . import credential, machine, hardware_features, software_platform

    Base.metadata.create_all(bind=engine)
