#!/usr/bin/env python3
"""Script para testar login diretamente via HTTP."""

import asyncio
import aiohttp
import json

import pytest

@pytest.mark.asyncio
async def test_login():
    """Testa login via HTTP."""
    url = "http://localhost:8000/api/v1/auth/login"
    data = {
        "username": "admin",
        "password": "admin123"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as response:
                print(f"Status: {response.status}")
                print(f"Headers: {dict(response.headers)}")
                
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ Login bem-sucedido: {json.dumps(result, indent=2)}")
                else:
                    text = await response.text()
                    print(f"❌ Erro no login: {text}")
                    
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")
        import traceback
        traceback.print_exc()