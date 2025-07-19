# Contribuindo para o MegaEmu Modern

Obrigado por considerar contribuir para o MegaEmu Modern! Este documento fornece diretrizes para contribuições.

## 📋 Índice

- [Código de Conduta](#código-de-conduta)
- [Como Contribuir](#como-contribuir)
- [Configuração do Ambiente](#configuração-do-ambiente)
- [Padrões de Código](#padrões-de-código)
- [Processo de Pull Request](#processo-de-pull-request)
- [Reportando Bugs](#reportando-bugs)
- [Sugerindo Melhorias](#sugerindo-melhorias)
- [Documentação](#documentação)

## 📜 Código de Conduta

Este projeto adere ao [Contributor Covenant](https://www.contributor-covenant.org/). Ao participar, você deve seguir este código de conduta.

### Nossos Compromissos

- Usar linguagem acolhedora e inclusiva
- Respeitar diferentes pontos de vista e experiências
- Aceitar críticas construtivas graciosamente
- Focar no que é melhor para a comunidade
- Mostrar empatia com outros membros da comunidade

## 🤝 Como Contribuir

### Tipos de Contribuições

1. **Correção de Bugs** 🐛
   - Identifique e corrija problemas existentes
   - Adicione testes para prevenir regressões

2. **Novas Funcionalidades** ✨
   - Implemente recursos solicitados
   - Proponha e desenvolva novas ideias

3. **Melhorias de Performance** ⚡
   - Otimize consultas de banco de dados
   - Melhore algoritmos existentes
   - Reduza uso de memória

4. **Documentação** 📚
   - Melhore documentação existente
   - Adicione exemplos de uso
   - Traduza documentação

5. **Testes** 🧪
   - Adicione testes unitários
   - Melhore cobertura de testes
   - Crie testes de integração

## 🛠️ Configuração do Ambiente

### Pré-requisitos

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Git

### Setup Inicial

```bash
# 1. Fork o repositório no GitHub

# 2. Clone seu fork
git clone https://github.com/SEU_USERNAME/megaemu-modern.git
cd megaemu-modern

# 3. Adicione o repositório original como upstream
git remote add upstream https://github.com/ORIGINAL_OWNER/megaemu-modern.git

# 4. Configure o ambiente
cp backend/.env.example backend/.env
# Edite backend/.env conforme necessário

# 5. Inicie os serviços
docker-compose up -d

# 6. Instale dependências de desenvolvimento
make install
```

### Verificação da Instalação

```bash
# Execute os testes
make test

# Verifique o linting
make lint

# Acesse a aplicação
# API: http://localhost:8000
# Frontend: http://localhost:3000
```

## 📝 Padrões de Código

### Backend (Python)

#### Estilo de Código
- **PEP 8** como base
- **Black** para formatação automática
- **isort** para organização de imports
- **flake8** para linting
- **mypy** para type checking

#### Estrutura de Arquivos
```python
# Ordem de imports
# 1. Standard library
import os
import sys
from typing import Optional

# 2. Third-party
from fastapi import FastAPI
from sqlalchemy import Column

# 3. Local imports
from app.core.config import settings
from app.models.base import Base
```

#### Convenções de Nomenclatura
```python
# Classes: PascalCase
class UserService:
    pass

# Funções e variáveis: snake_case
def get_user_by_id(user_id: int) -> Optional[User]:
    pass

# Constantes: UPPER_SNAKE_CASE
MAX_RETRY_ATTEMPTS = 3

# Arquivos: snake_case
# user_service.py, rom_processor.py
```

#### Documentação de Código
```python
def process_rom_file(file_path: str, system_id: int) -> RomProcessResult:
    """
    Processa um arquivo ROM e extrai metadados.
    
    Args:
        file_path: Caminho para o arquivo ROM
        system_id: ID do sistema de videogame
        
    Returns:
        Resultado do processamento com metadados extraídos
        
    Raises:
        FileNotFoundError: Se o arquivo não for encontrado
        InvalidRomError: Se o arquivo não for um ROM válido
    """
    pass
```

### Frontend (React/TypeScript)

#### Estrutura de Componentes
```typescript
// ComponentName.tsx
import React from 'react';
import { Box, Typography } from '@mui/material';

interface ComponentNameProps {
  title: string;
  onAction?: () => void;
}

export const ComponentName: React.FC<ComponentNameProps> = ({
  title,
  onAction
}) => {
  return (
    <Box>
      <Typography variant="h6">{title}</Typography>
    </Box>
  );
};
```

#### Hooks Customizados
```typescript
// useRomData.ts
import { useQuery } from '@tanstack/react-query';
import { romService } from '../services/romService';

export const useRomData = (romId: string) => {
  return useQuery({
    queryKey: ['rom', romId],
    queryFn: () => romService.getRom(romId),
    enabled: !!romId
  });
};
```

### Banco de Dados

#### Migrações
```python
# Sempre criar migrações descritivas
alembic revision --autogenerate -m "add_rom_metadata_table"

# Testar migrações
alembic upgrade head
alembic downgrade -1
```

#### Modelos SQLAlchemy
```python
class Rom(Base):
    __tablename__ = "roms"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    file_hash = Column(String(64), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    system = relationship("System", back_populates="roms")
    
    def __repr__(self):
        return f"<Rom(id={self.id}, name='{self.name}')>"
```

## 🔄 Processo de Pull Request

### 1. Preparação

```bash
# Sincronize com upstream
git fetch upstream
git checkout main
git merge upstream/main

# Crie uma branch para sua feature
git checkout -b feature/nome-da-feature
# ou
git checkout -b fix/nome-do-bug
```

### 2. Desenvolvimento

```bash
# Faça suas alterações
# ...

# Execute testes frequentemente
make test

# Verifique o código
make lint
make format

# Commit suas alterações
git add .
git commit -m "feat: adiciona funcionalidade X"
```

### 3. Convenções de Commit

Usamos [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Tipos de commit
feat: nova funcionalidade
fix: correção de bug
docs: alterações na documentação
style: formatação, ponto e vírgula, etc
refactor: refatoração de código
test: adição ou correção de testes
chore: tarefas de manutenção

# Exemplos
git commit -m "feat: adiciona endpoint para busca de ROMs"
git commit -m "fix: corrige validação de arquivo ROM"
git commit -m "docs: atualiza README com instruções de deploy"
git commit -m "test: adiciona testes para RomService"
```

### 4. Submissão

```bash
# Push para seu fork
git push origin feature/nome-da-feature

# Abra um Pull Request no GitHub
```

### 5. Template de Pull Request

```markdown
## Descrição
Descreva brevemente as alterações realizadas.

## Tipo de Mudança
- [ ] Bug fix (correção que resolve um problema)
- [ ] Nova funcionalidade (mudança que adiciona funcionalidade)
- [ ] Breaking change (correção ou funcionalidade que quebra compatibilidade)
- [ ] Documentação

## Como Testar
1. Passo 1
2. Passo 2
3. Passo 3

## Checklist
- [ ] Meu código segue os padrões do projeto
- [ ] Realizei uma auto-revisão do código
- [ ] Comentei partes complexas do código
- [ ] Fiz alterações correspondentes na documentação
- [ ] Minhas alterações não geram novos warnings
- [ ] Adicionei testes que provam que minha correção/funcionalidade funciona
- [ ] Testes novos e existentes passam localmente
```

## 🐛 Reportando Bugs

### Antes de Reportar

1. **Verifique se já existe** uma issue similar
2. **Reproduza o bug** em ambiente limpo
3. **Colete informações** do sistema

### Template de Bug Report

```markdown
**Descrição do Bug**
Descrição clara e concisa do problema.

**Passos para Reproduzir**
1. Vá para '...'
2. Clique em '....'
3. Role para baixo até '....'
4. Veja o erro

**Comportamento Esperado**
Descrição do que deveria acontecer.

**Screenshots**
Se aplicável, adicione screenshots.

**Ambiente:**
 - OS: [e.g. Windows 11, Ubuntu 22.04]
 - Browser: [e.g. Chrome 120, Firefox 121]
 - Versão: [e.g. 1.0.0]

**Informações Adicionais**
Qualquer contexto adicional sobre o problema.
```

## 💡 Sugerindo Melhorias

### Template de Feature Request

```markdown
**Sua sugestão está relacionada a um problema?**
Descrição clara do problema. Ex: Fico frustrado quando [...]

**Descreva a solução que você gostaria**
Descrição clara e concisa do que você quer que aconteça.

**Descreva alternativas consideradas**
Descrição de soluções ou funcionalidades alternativas.

**Contexto Adicional**
Qualquer contexto ou screenshots sobre a sugestão.
```

## 📚 Documentação

### Tipos de Documentação

1. **README.md** - Visão geral e setup
2. **API Documentation** - Endpoints e schemas
3. **Code Comments** - Explicações inline
4. **Architecture Docs** - Decisões de design
5. **User Guides** - Tutoriais de uso

### Padrões de Documentação

```markdown
# Use títulos descritivos

## Organize com hierarquia clara

### Inclua exemplos práticos

```bash
# Comandos devem ser copiáveis
make install
```

**Destaque informações importantes**

> Use blockquotes para dicas

- Use listas para passos
- Mantenha parágrafos concisos
```

## 🧪 Testes

### Estrutura de Testes

```python
# tests/test_rom_service.py
import pytest
from app.services.rom_service import RomService

class TestRomService:
    def test_process_valid_rom(self):
        # Arrange
        service = RomService()
        rom_path = "test_files/valid_rom.zip"
        
        # Act
        result = service.process_rom(rom_path)
        
        # Assert
        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.name == "Expected ROM Name"
    
    def test_process_invalid_rom(self):
        service = RomService()
        
        with pytest.raises(InvalidRomError):
            service.process_rom("invalid_file.txt")
```

### Executando Testes

```bash
# Todos os testes
make test

# Testes específicos
pytest tests/test_rom_service.py

# Com cobertura
pytest --cov=app tests/

# Testes de integração
pytest tests/integration/
```

## 🏷️ Versionamento

Usamos [Semantic Versioning](https://semver.org/):

- **MAJOR**: Mudanças incompatíveis na API
- **MINOR**: Funcionalidades compatíveis
- **PATCH**: Correções de bugs compatíveis

Exemplo: `1.2.3`

## 📞 Suporte

- **Issues**: Para bugs e sugestões
- **Discussions**: Para perguntas gerais
- **Discord**: [Link do servidor] (se disponível)
- **Email**: maintainer@megaemu.com

## 🙏 Reconhecimentos

Todos os contribuidores são listados no arquivo [CONTRIBUTORS.md](CONTRIBUTORS.md).

---

**Obrigado por contribuir para o MegaEmu Modern!** 🎮✨