from app.database import engine
from sqlalchemy import text

def verify_tables():
    """Verifica as tabelas criadas no banco de dados."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result]
            
            print(f"Tabelas criadas no banco de dados ({len(tables)} total):")
            for table in sorted(tables):
                print(f"  - {table}")
                
            # Verificar algumas tabelas específicas
            expected_tables = ['systems', 'roms', 'games', 'users', 'tasks']
            missing_tables = [t for t in expected_tables if t not in tables]
            
            if missing_tables:
                print(f"\nTabelas esperadas não encontradas: {missing_tables}")
            else:
                print("\n✅ Todas as tabelas principais foram criadas com sucesso!")
                
    except Exception as e:
        print(f"Erro ao verificar tabelas: {e}")

if __name__ == "__main__":
    verify_tables()