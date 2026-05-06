from config import engine, Base

from models import Atendimento, AnaliseIA, ScoreQualidade, ValidacaoHumana

def create_database():
    print("Conectando ao banco de dados e criando tabelas...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Tabelas criadas com sucesso!")
    except Exception as e:
        print(f"Erro ao criar tabelas: {e}")

if __name__ == "__main__":
    create_database()