from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src import settings
from src.chatedubot_models import ModelsProvider, Base
from sqlalchemy.orm import Session


MODELS = [
    ModelsProvider(
        model_name="openai/gpt-oss-120b",
        model_provider="groq",
        pricing_input_tokens=0.0,   # placeholder — actualizar con precio real
        pricing_output_tokens=0.0,  # placeholder — actualizar con precio real
    ),
]


def seed(session):
    for model in MODELS:
        exists = session.query(ModelsProvider).filter_by(model_name=model.model_name).first()
        if exists:
            print(f"[skip] {model.model_name} ya existe")
            continue
        session.add(model)
        print(f"[add]  {model.model_name}")
    session.commit()
    print("done")


if __name__ == "__main__":
    engine = create_engine(settings.DB_EDUCHAT_CONN_STRING)
    Session = sessionmaker(bind=engine)
    session = Session()
    seed(session)
    session.close()


"""
python3 -m src.services.v1.ChatEdubotv3.seed_models_provider


"""
