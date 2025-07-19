#!/usr/bin/env python3
"""Script para verificar usuários no banco de dados."""

from app.database import get_db_session
from app.models import User

def check_users():
    """Verifica usuários existentes no banco de dados."""
    try:
        with get_db_session() as db:
            # Conta total de usuários
            count = db.query(User).count()
            print(f'Total de usuários: {count}')
            
            if count > 0:
                # Lista primeiros 5 usuários
                users = db.query(User).limit(5).all()
                print('Usuários encontrados:')
                for user in users:
                    print(f'  ID: {user.id}, Username: {user.username}, Email: {user.email}, Ativo: {user.is_active}')
            else:
                print('Nenhum usuário encontrado no banco de dados.')
                print('É necessário criar um usuário inicial para testar a autenticação.')
                
    except Exception as e:
        print(f'Erro ao verificar usuários: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_users()