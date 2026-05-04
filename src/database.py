from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
from src import settings
from typing import Generator

# # Setup database engine and session for FastAPI dependency injection
# _engine = create_engine(
#     f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASS}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
# )
# _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


# def get_db() -> Generator[Session, None, None]:
#     db = _SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


class DatabaseError(Exception):
    """Excepción base para errores de base de datos"""
    pass


class CrudHelper:
    def __init__(self, conn_string, model):
        self.engine = create_engine(conn_string)
        self.model = model

    @contextmanager
    def session_scope(self):
        """
        Context manager para manejar sesiones de base de datos de forma segura
        """
        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            raise DatabaseError(f"Error en base de datos: {str(e)}") from e
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_database(self) -> None:
        """
        Crea todas las tablas en la base de datos
        """
        try:
            # with self.engine.connect() as conn:
            #     conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            #     conn.commit()
            self.model.Base.metadata.create_all(self.engine)
        except SQLAlchemyError as e:
            raise DatabaseError(f"No se pudo crear la base de datos: {str(e)}") from e


if __name__ == "__main__":
    from src import settings
    from src import chatedubot_models
    crud = CrudHelper(conn_string=settings.DB_EDUCHAT_CONN_STRING, model=chatedubot_models)
    crud.create_database()

"""
python3 -m src.database


"""
