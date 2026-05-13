
from typing import Literal, TypedDict, List

from langchain_core.tools import StructuredTool, BaseTool
from pydantic import BaseModel, Field

from sqlalchemy.engine import Engine
from typing import List, Dict
from sqlalchemy import text, MetaData, Table
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

from src.logging_config import get_logger
logger = get_logger(module_name="postgres", DIR="toolkit")


class PostgresToolKit:
    def __init__(self, engine : Engine, originabotdb_json : Dict[str, List[str]], top_n : int = 15, schema_name : str = 'public'):
        self.engine = engine
        self.schema_name = schema_name
        self.top_n = top_n
        self.originabotdb_json = originabotdb_json
    
    # ---  Helper methods

    def _get_db_tables_names(self) -> str:
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(
                    f"""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = '{self.schema_name}'
                    ORDER BY table_name
                    """
                ))
                rows = result.fetchall()
                response = f"Hay {len(rows)} tablas en la base de datos:\n\n"
                for row in rows:
                    response += f"{row[0]}\n"
                return response
        except Exception as e:
            return f"Error: {e}"
        
    
    def _get_table_schema(self, table_name: str) -> str:
        try:
            metadata = MetaData()
            # Intenta cargar la tabla. Si falla, SQLAlchemy lanzará error.
            table = Table(table_name, metadata, autoload_with=self.engine)
            
            ddl = CreateTable(table).compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True}
            )
            return str(ddl)
        except Exception as e:
            return f"Error obteniendo esquema de la tabla '{table_name}': {str(e)}"
    
    def _get_tables_schemas(self, tables_names : List[str]) -> str:
        try:
            schemas = ""
            for name in tables_names:
                schemas += f"{self._get_table_schema(name)}"
                schemas += "\n\n"
            return schemas
        except Exception as e:
            return f"- Error: {e} \n\n"
        
    
    def _query_data_base(self, query: str) -> str:
        try:
            # Se recomienda usar bloques try/except para conexiones DB
            with self.engine.connect() as conn:
                result = conn.execute(text(query))
                rows = result.fetchall()
            
            if len(rows) > self.top_n:
                response = f"Hay {len(rows)} registros en la respuesta de la consulta. Se ha limitado a los primeros {self.top_n} registros: \n\n {rows[:self.top_n]}"
                return response
            else:
                response = f"Hay {len(rows)} registros en la respuesta de la consulta: \n\n {rows}"
                return response
        except Exception as e:
            return f"Error ejecutando query SQL: {str(e)}"
    

    
    def _get_tables_name_by_modules(self, modules : List[str]):
        try:
            response = []
            for m in modules:
                tables = self.originabotdb_json.get(m, False)
                if not tables:
                    return f"Error, el modulo {m} no es un modulo valido de la base de datos. Modulos validos: {self.originabotdb_json.keys()}"
                tables = "\n".join(tables)
                response.append(f"tablas del modulo {m}: \n")
                response.append(tables)
                response.append("\n\n")
            return "\n".join(response)
        except Exception as e:
            return f"Error: {str(e)}"

        


    # --- args_schema

    class TablesSchemas(BaseModel):
        tables_names: List[str] = Field(
            description=(
                "Nombres exactos de las tablas cuyo esquema se quiere inspeccionar. "
                "Usa los nombres devueltos por `get_tables_name_by_modules` — no adivines nombres. "
                "Incluye todas las tablas que vayas a referenciar o JOINear en la consulta SQL."
            )
        )

    class QueryDataBaseArgs(BaseModel):
        query: str = Field(
            description=(
                "Consulta SQL de solo lectura (SELECT) válida para PostgreSQL. "
                "No se permiten INSERT, UPDATE, DELETE ni DDL. "
                "Escribe la consulta solo después de haber inspeccionado los esquemas con `get_tables_schemas` "
                "para conocer los nombres exactos de columnas, tipos y relaciones foráneas. "
                "Si necesitas paginar resultados, usa LIMIT y OFFSET."
            )
        )

    class TablesByModules(BaseModel):
        modules: List[str] = Field(
            description=(
                "Lista de módulos cuyos nombres de tablas se quieren obtener. "
                "Debe contener uno o más de los 24 módulos válidos de la base de datos: "
                "'contabilidad', 'contratos', 'originacion', 'proyectos', 'inversiones', "
                "'validaciones', 'dataroom', 'epc_ingenieria', 'operador_red', 'gobierno', "
                "'monitoreo', 'visitas_campo', 'autenticacion_usuarios', 'tareas_programadas', "
                "'auditoria_logs', 'geografico', 'whatsapp', 'filtros', 'reportes', "
                "'proxied_links', 'jwt_config', 'genai', 'legal_validation', 'migraciones'. "
                "Elige los módulos que, según la descripción de la base de datos en el system prompt, "
                "tengan más probabilidad de contener las tablas relevantes para responder la consulta."
            )
        )



    # --- return

    def get_tools(self) -> List[BaseTool]:
        tools = [
            # StructuredTool.from_function(
            #     name="get_db_tables_names",
            #     description="Retorna el nombre de todas las tablas de la base de datos del usuario",
            #     func=self._get_db_tables_names
            #     # No needs args
            # ),
            StructuredTool.from_function(
                name="get_tables_schemas",
                description=(
                    "Devuelve el DDL (CREATE TABLE) de las tablas indicadas, con columnas, tipos de datos, "
                    "claves primarias, claves foráneas y restricciones. "
                    "Llama a esta herramienta como SEGUNDO PASO, después de obtener los nombres exactos "
                    "de tablas con `get_tables_name_by_modules`. Inspecciona los esquemas para entender "
                    "relaciones y columnas antes de escribir cualquier consulta SQL."
                ),
                func=self._get_tables_schemas,
                args_schema=self.TablesSchemas
            ),
            StructuredTool.from_function(
                name="query_data_base",
                description=(
                    "Ejecuta una consulta SQL de solo lectura (SELECT) contra la base de datos PostgreSQL "
                    "y devuelve los resultados. "
                    "Llama a esta herramienta como TERCER PASO, después de inspeccionar los esquemas. "
                    f"Los resultados están limitados a {self.top_n} filas; si hay más registros, "
                    "pagina usando LIMIT y OFFSET en llamadas sucesivas. "
                    "Solo se permiten SELECT — nunca emitas INSERT, UPDATE, DELETE ni DDL."
                ),
                func=self._query_data_base,
                args_schema=self.QueryDataBaseArgs
            ),
            # StructuredTool.from_function(
            #     name="get_tables_name_by_modules",
            #     description=(
            #         "Devuelve los nombres exactos de las tablas de la base de datos que pertenecen "
            #         "a los módulos indicados. "
            #         "Llama a esta herramienta como PRIMER PASO antes de cualquier consulta: "
            #         "lee la descripción de la base de datos en el system prompt, identifica los módulos "
            #         "relevantes y usa esta herramienta para obtener los nombres de tabla correctos "
            #         "antes de llamar a `get_tables_schemas`."
            #     ),
            #     func=self._get_tables_name_by_modules,
            #     args_schema=self.TablesByModules
            # )
        ]

        return tools
    



    

if __name__=="__main__":
    from sqlalchemy import create_engine
    from pathlib import Path
    import json

    conn_string = "postgresql+psycopg2://postgres:postgres@localhost:5432/originabotdb"
    engine = create_engine(conn_string)


    dir_root = Path(__file__).resolve().parent
    path = dir_root / "originabot.json"

    with open(path, "r", encoding="utf-8") as f:
        originabotdb_json = json.load(f)

    pg_tools = PostgresToolKit(engine=engine, originabotdb_json=originabotdb_json)
    tools = pg_tools.get_tools()

    get_tables_name_by_modules = tools[2]

    modules = ["contabilidad", "contratos"]
    x = get_tables_name_by_modules.invoke({"modules":modules})
    print(x)


