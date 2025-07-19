#!/usr/bin/env python3
"""Script para testar autenticação diretamente."""

import asyncio
import sys
from pathlib import Path

# Adiciona o diretório do projeto ao path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import AsyncSessionLocal
from app.services.user import UserService
from app.core.security import verify_password

import pytest

@pytest.mark.asyncio
async def test_auth():
    """Testa autenticação do usuário admin."""
    try:
        # Conecta ao banco
        async with AsyncSessionLocal() as db:
            user_service = UserService(db)
            
            # Busca usuário
            print("Buscando usuário admin...")
            user = await user_service.get_by_email_or_username(db, identifier="admin")
            
            if not user:
                print("❌ Usuário admin não encontrado")
                return
            
            print(f"✅ Usuário encontrado: {user.username} ({user.email})")
            print(f"   Status: {user.status}")
            print(f"   Ativo: {user.is_active}")
            print(f"   Hash da senha: {user.hashed_password[:50]}...")
            
            # Testa verificação de senha
            print("\nTestando verificação de senha...")
            password_ok = verify_password("admin123", user.hashed_password)
            print(f"   Senha 'admin123' válida: {password_ok}")
            
            if password_ok:
                print("✅ Autenticação funcionando corretamente")
            else:
                print("❌ Problema na verificação de senha")
                
    except Exception as e:
        print(f"❌ Erro durante teste: {e}")
        import traceback
        traceback.print_exc()