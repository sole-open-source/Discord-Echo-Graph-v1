from sqlalchemy.engine import Engine
from sqlalchemy import text, MetaData, Table
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from typing import List

class PostgresUtils:
    def __init__(self, engine : Engine):
        self.engine = engine

    def get_tables_name(self, schema_name : str = 'public') -> List[str]:
        with self.engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = '{schema_name}'
                ORDER BY table_name;
            """))
            tables = [row[0] for row in result]
        return tables

        
    def get_table_schema(self, table_name : str) -> str:
        try:
            metadata =MetaData()
            table = Table(table_name, metadata, autoload_with=self.engine)
            ddl = CreateTable(table).compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True}
            )
            return str(ddl)
        except Exception as e:
            raise f"{e}"
        




if __name__=="__main__":
    from sqlalchemy import create_engine
    from pathlib import Path

    conn_string = "postgresql+psycopg2://postgres:postgres@localhost:5432/originabotdb"
    engine = create_engine(conn_string)

    dir_root = Path(__file__).resolve().parent
    # print(dir_root)

    postgrs_utils = PostgresUtils(engine=engine)

    # table_names = postgrs_utils.get_tables_name()

    # db_schema = []
    # for name in table_names:
    #     schema = postgrs_utils.get_table_schema(table_name=name)
    #     db_schema.append(schema)
    # db_schema = "\n\n".join(db_schema)

    
    # path = dir_root / "originabotdb.md"
    # with open(path, 'w', encoding='utf-8') as f:
    #     f.write(db_schema)

    # schema = postgrs_utils.get_table_schema(table_name='minifarm_project')
    # print(schema)



    import json

    path = dir_root / "originabot.json"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(data.keys())

    for k in data.keys():
        v = data[k]
        data[k] = set(v)

    tables_name = postgrs_utils.get_tables_name()
    print(f"len {len(tables_name)}")
    for name in tables_name:
        y = False
        for k in data.keys():
            x = data[k]
            y = (name in x)
            if y is True:
                break
        if (y is False):
            print(name)

    




"""
python3 -m src.services.v1.ChatEdubot.pg_utils


"""
