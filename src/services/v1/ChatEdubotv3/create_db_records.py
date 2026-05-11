
if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src import settings
    from src import chatedubot_models as models

    
    engine = create_engine(settings.DB_EDUCHAT_CONN_STRING)
    MySession = sessionmaker(bind=engine)
    session = MySession()

    id = 1
    discord_user_id=123
    discord_name="el thomas"

    user_id=1

    new_user_record = models.User(
        id=id,
        discord_user_id=discord_user_id,
        discord_name=discord_name
    )

    new_chat_record = models.UserChat(
        id=id,
        user_id=user_id,

    )

    session.add(new_user_record)
    session.add(new_chat_record)
    session.commit()




"""
python3 -m src.services.v1.ChatEdubotv3.create_db_records


"""


    