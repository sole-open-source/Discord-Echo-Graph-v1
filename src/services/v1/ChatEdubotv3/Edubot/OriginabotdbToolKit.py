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
        to_do : str = Field(description="Tareas para el sub agente de analisis de datos, este agente tiene acceso a la base de datos del usuario")


    # --- return

    def get_tools(self) -> List[BaseTool]:
        return [
            StructuredTool.from_function(
                name="invoke_Originabotdb_subagent",
                description="Funcion para invokar un subagente este sub agente tiene la capacidad de conectarse a la base de datos del usuario y hacer queries sql y exportar datos de la base de datos en .csv",
                func=self._invoke_data_analyst_subagent,
                args_schema=self.DataAnalystSubAgent
            )
        ]
    
    
