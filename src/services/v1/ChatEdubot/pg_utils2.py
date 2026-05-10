
from sqlalchemy.engine import Engine
from sqlalchemy import text, MetaData, Table, inspect
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from collections import defaultdict, deque
from pathlib import Path
from typing import List, Dict, Set, Tuple


class PostgresSchemaExporter:
    def __init__(self, engine: Engine, schema_name: str = "public"):
        self.engine = engine
        self.schema_name = schema_name
        self.inspector = inspect(engine)

    # ---------- Utilidades básicas ----------

    def get_tables_name(self) -> List[str]:
        return sorted(self.inspector.get_table_names(schema=self.schema_name))

    def get_table_ddl(self, table_name: str) -> str:
        metadata = MetaData()
        table = Table(table_name, metadata, autoload_with=self.engine, schema=self.schema_name)
        ddl = CreateTable(table).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
        return str(ddl).strip()

    def get_foreign_keys(self) -> Dict[str, Set[str]]:
        """
        Devuelve un dict {tabla: set(tablas_referenciadas)}.
        Self-references se ignoran para no romper el orden topológico.
        """
        deps: Dict[str, Set[str]] = defaultdict(set)
        for table in self.get_tables_name():
            deps[table]  # asegurar que la tabla aparezca aunque no tenga FKs
            for fk in self.inspector.get_foreign_keys(table, schema=self.schema_name):
                referred = fk.get("referred_table")
                if referred and referred != table:
                    deps[table].add(referred)
        return deps

    # ---------- Agrupación con orden topológico ----------

    def topological_layers(self) -> List[List[str]]:
        """
        Divide las tablas en 'capas' donde cada capa solo depende de capas anteriores.
        Capa 0 = tablas sin FKs (o solo con FKs cíclicas/auto-referenciales).
        """
        deps = self.get_foreign_keys()
        remaining = {t: set(d) for t, d in deps.items()}
        layers: List[List[str]] = []

        while remaining:
            # tablas cuyas dependencias ya están resueltas
            ready = sorted([t for t, d in remaining.items() if not d])

            if not ready:
                # Hay un ciclo: rompemos eligiendo la tabla con menos dependencias
                # (caso típico: ciclos como contract <-> docx)
                victim = min(remaining, key=lambda t: len(remaining[t]))
                ready = [victim]

            layers.append(ready)
            for t in ready:
                remaining.pop(t, None)
            for d in remaining.values():
                d.difference_update(ready)

        return layers

    def group_tables(self, max_per_group: int = 25) -> List[List[str]]:
        """
        Genera grupos de tablas listos para enviar:
          - Respeta el orden topológico (las FKs se resuelven hacia atrás).
          - Agrupa por módulo (prefijo antes del primer '_').
          - Limita el tamaño de cada grupo a `max_per_group`.
        """
        layers = self.topological_layers()
        ordered_tables = [t for layer in layers for t in layer]

        # Agrupar por módulo manteniendo el orden topológico
        groups: List[List[str]] = []
        current: List[str] = []
        current_module = None

        for table in ordered_tables:
            module = table.split("_", 1)[0]
            same_module = (module == current_module)

            # Si cambia de módulo y ya hay contenido, o si excede el tamaño máximo,
            # cerramos el grupo actual.
            if current and (
                len(current) >= max_per_group
                or (not same_module and len(current) >= max_per_group // 2)
            ):
                groups.append(current)
                current = []

            current.append(table)
            current_module = module

        if current:
            groups.append(current)

        return groups

    # ---------- Exportación ----------

    def export_grouped(self, output_dir: Path, max_per_group: int = 25) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        groups = self.group_tables(max_per_group=max_per_group)
        deps = self.get_foreign_keys()

        # Resumen general
        summary_lines = [f"# Resumen de agrupación\n", f"Total de tablas: {sum(len(g) for g in groups)}\n",
                         f"Total de grupos: {len(groups)}\n"]

        for i, group in enumerate(groups, start=1):
            modules = sorted({t.split('_', 1)[0] for t in group})
            summary_lines.append(f"\n## Grupo {i:02d} ({len(group)} tablas) — módulos: {', '.join(modules)}")
            for t in group:
                summary_lines.append(f"- {t}")

            # Generar archivo del grupo
            ddl_blocks = []
            ddl_blocks.append(f"-- ============================================")
            ddl_blocks.append(f"-- GRUPO {i:02d} de {len(groups)}")
            ddl_blocks.append(f"-- Tablas: {len(group)}")
            ddl_blocks.append(f"-- Módulos: {', '.join(modules)}")

            # Verificar dependencias externas (FKs hacia tablas que NO están en este grupo
            # ni en grupos anteriores)
            already_seen = {tbl for g in groups[:i] for tbl in g}  # incluye este grupo
            external_refs = set()
            for t in group:
                for ref in deps.get(t, set()):
                    if ref not in already_seen:
                        external_refs.add(ref)

            if external_refs:
                ddl_blocks.append(f"-- ⚠️  FKs pendientes (tablas referenciadas en grupos posteriores):")
                for ref in sorted(external_refs):
                    ddl_blocks.append(f"--   - {ref}")
            ddl_blocks.append(f"-- ============================================\n")

            for t in group:
                ddl_blocks.append(self.get_table_ddl(t))
                ddl_blocks.append("")

            (output_dir / f"grupo_{i:02d}.sql").write_text("\n".join(ddl_blocks), encoding="utf-8")

        (output_dir / "RESUMEN.md").write_text("\n".join(summary_lines), encoding="utf-8")


if __name__ == "__main__":
    from sqlalchemy import create_engine

    conn_string = "postgresql+psycopg2://postgres:postgres@localhost:5432/originabotdb"
    engine = create_engine(conn_string)

    exporter = PostgresSchemaExporter(engine=engine)

    dir_root = Path(__file__).resolve().parent
    output_dir = dir_root / "schema_grupos"

    # Ajusta max_per_group según prefieras grupos más grandes o más pequeños.
    # 25-30 suele ser un buen balance.
    exporter.export_grouped(output_dir=output_dir, max_per_group=25)

    print(f"Esquema exportado en: {output_dir}")

