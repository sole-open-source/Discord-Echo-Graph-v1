from typing import List
from langchain_core.tools.base import BaseTool
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class OriginabotdbSubAgentToolKit:
    def __init__(self):
        pass

    # ---  Helper methods

    def _invoke_data_analyst_subagent(self, to_do : str) -> str:
        return f"{to_do}"
    
    # --- args_schema

    class DataAnalystSubAgent(BaseModel):
        to_do : str = Field(
            description=(
                "Instrucción completa y autocontenida para el subagente"
                "El subagente usará esta instrucción para identificar los módulos correctos de la base de datos, "
                "inspeccionar los esquemas de las tablas y construir la consulta SQL adecuada."
            )
        )


    # --- return

    def get_tools(self) -> List[BaseTool]:
        return [
            StructuredTool.from_function(
                name="invoke_Originabotdb_subagent",
                description=(
                    "Invoca un subagente ReAct especializado en consultar la base de datos PostgreSQL `originabotdb`. "
                    "Esta base de datos pertenece a una plataforma de gestión de proyectos de energía solar en Colombia "
                    "y contiene ~290 tablas organizadas en 24 módulos: contabilidad, contratos, originación, proyectos, "
                    "inversiones, validaciones, dataroom, epc_ingeniería, operador_red, gobierno, monitoreo, "
                    "visitas_campo, autenticación_usuarios, tareas_programadas, auditoría_logs, geográfico, "
                    "whatsapp, filtros, reportes, proxied_links, jwt_config, genai, legal_validation y migraciones. "
                    "El subagente puede explorar esquemas de tablas (columnas, tipos, claves foráneas) y ejecutar "
                    "consultas SELECT para recuperar datos estructurados. Solo puede leer datos — no ejecuta "
                    "INSERT, UPDATE, DELETE ni DDL."
                    "Úsalo cuando el usuario necesite información estructurada de la plataforma: proyectos, "
                    "contratos, estados de originación, datos contables, inversiones, reportes u otros datos "
                    "que residan en la base de datos relacional. "
                    "NO uses esta herramienta para preguntas sobre conversaciones de Discord "
                    "(usa `query_lightrag` o las herramientas de búsqueda de mensajes para eso)."
                ),
                func=self._invoke_data_analyst_subagent,
                args_schema=self.DataAnalystSubAgent
            )
        ]
    
    
