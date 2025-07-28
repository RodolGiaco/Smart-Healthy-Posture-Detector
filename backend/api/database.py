# api/database.py

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# 1) URL de conexión (ajusta si es necesario)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/shpd_db"
)

# 2) Crea el engine de SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    echo=False,   # True para ver las consultas SQL en consola
    future=True   # activa la API 2.0 de SQLAlchemy
)

# 3) Fabrica de sesiones
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# 4) Base declarativa para tus modelos
Base = declarative_base()

# 5) Dependencia de FastAPI para inyectar sesión en cada request
def get_db() -> Generator[Session, None, None]:
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
