#!/usr/bin/env python3
"""Script para criar um usuário inicial para testes."""

from app.database import get_db_session
from app.models import User
from app.core.security import get_password_hash
from datetime import datetime

def create_initial_user():
    """Cria um usuário inicial para testes."""
    try:
        with get_db_session() as db:
            # Verifica se já existe algum usuário
            existing_user = db.query(User).first()
            if existing_user:
                print(f'Usuário já existe: {existing_user.username}')
                return
            
            # Dados do usuário inicial
            username = "admin"
            email = "admin@megaemu.com"
            password = "admin123"
            full_name = "Administrador"
            
            # Cria hash da senha
            hashed_password = get_password_hash(password)
            
            # Cria o usuário
            user = User(
                username=username,
                email=email,
                full_name=full_name,
                hashed_password=hashed_password,
                role="admin",
                status="active",
                email_verified=True,
                email_verified_at=datetime.utcnow()
            )
            
            db.add(user)
            db.commit()
            db.refresh(user)
            
            print(f'Usuário criado com sucesso!')
            print(f'Username: {username}')
            print(f'Email: {email}')
            print(f'Password: {password}')
            print(f'ID: {user.id}')
            print(f'Role: {user.role}')
            print(f'Status: {user.status}')
            
    except Exception as e:
        print(f'Erro ao criar usuário: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    create_initial_user()