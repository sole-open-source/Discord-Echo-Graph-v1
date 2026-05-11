from src import discord_models as models

from sqlalchemy.orm import Session

def get_all_ready_docs(session : Session):
    docs_records = session.query(models.DiscordChannelChronologicalSummary).filter(
        models.DiscordChannelChronologicalSummary.status == "ready"
    )
    pass