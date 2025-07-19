-- =============================================================================
-- SCRIPT DE INICIALIZAÇÃO DO BANCO DE DADOS - MEGAEMU MODERN
-- =============================================================================
-- Este script é executado automaticamente quando o container PostgreSQL é criado

-- =============================================================================
-- CONFIGURAÇÕES INICIAIS
-- =============================================================================

-- Definir timezone padrão
SET timezone = 'UTC';

-- Habilitar extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "unaccent";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- =============================================================================
-- COMENTÁRIOS SOBRE EXTENSÕES
-- =============================================================================

-- uuid-ossp: Geração de UUIDs
-- pg_trgm: Busca de texto com trigrams (para busca fuzzy)
-- unaccent: Remoção de acentos para busca
-- btree_gin: Índices GIN para tipos básicos
-- btree_gist: Índices GiST para tipos básicos

-- =============================================================================
-- CONFIGURAÇÕES DE PERFORMANCE
-- =============================================================================

-- Configurações específicas para o banco MegaEmu Modern
ALTER DATABASE megaemu_modern SET shared_preload_libraries = 'pg_stat_statements';
ALTER DATABASE megaemu_modern SET log_statement = 'mod';
ALTER DATABASE megaemu_modern SET log_min_duration_statement = 1000;
ALTER DATABASE megaemu_modern SET log_checkpoints = on;
ALTER DATABASE megaemu_modern SET log_connections = on;
ALTER DATABASE megaemu_modern SET log_disconnections = on;
ALTER DATABASE megaemu_modern SET log_lock_waits = on;

-- =============================================================================
-- FUNÇÕES AUXILIARES
-- =============================================================================

-- Função para busca de texto sem acentos
CREATE OR REPLACE FUNCTION unaccent_lower(text)
RETURNS text AS
$$
SELECT lower(unaccent($1));
$$
LANGUAGE SQL IMMUTABLE;

-- Função para calcular similaridade de texto
CREATE OR REPLACE FUNCTION text_similarity(text, text)
RETURNS float AS
$$
SELECT similarity($1, $2);
$$
LANGUAGE SQL IMMUTABLE;

-- Função para gerar slug a partir de texto
CREATE OR REPLACE FUNCTION generate_slug(input_text text)
RETURNS text AS
$$
DECLARE
    slug text;
BEGIN
    -- Converter para minúsculas e remover acentos
    slug := lower(unaccent(input_text));
    
    -- Substituir espaços e caracteres especiais por hífens
    slug := regexp_replace(slug, '[^a-z0-9]+', '-', 'g');
    
    -- Remover hífens do início e fim
    slug := trim(both '-' from slug);
    
    -- Limitar tamanho
    slug := left(slug, 100);
    
    RETURN slug;
END;
$$
LANGUAGE plpgsql IMMUTABLE;

-- Função para atualizar timestamp de modificação
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS
$$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$
LANGUAGE plpgsql;

-- Função para validar email
CREATE OR REPLACE FUNCTION is_valid_email(email text)
RETURNS boolean AS
$$
BEGIN
    RETURN email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$';
END;
$$
LANGUAGE plpgsql IMMUTABLE;

-- Função para calcular hash de arquivo
CREATE OR REPLACE FUNCTION calculate_file_hash(file_path text)
RETURNS text AS
$$
BEGIN
    -- Esta função seria implementada com uma extensão específica
    -- Por enquanto, retorna NULL
    RETURN NULL;
END;
$$
LANGUAGE plpgsql;

-- =============================================================================
-- TIPOS CUSTOMIZADOS
-- =============================================================================

-- Enum para status de tarefas
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_status') THEN
        CREATE TYPE task_status AS ENUM (
            'pending',
            'running',
            'completed',
            'failed',
            'cancelled',
            'retrying'
        );
    END IF;
END$$;

-- Enum para prioridade de tarefas
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_priority') THEN
        CREATE TYPE task_priority AS ENUM (
            'low',
            'normal',
            'high',
            'urgent'
        );
    END IF;
END$$;

-- Enum para tipos de usuário
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM (
            'user',
            'moderator',
            'admin',
            'superuser'
        );
    END IF;
END$$;

-- Enum para status de ROM
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'rom_status') THEN
        CREATE TYPE rom_status AS ENUM (
            'pending',
            'verified',
            'corrupted',
            'missing',
            'duplicate'
        );
    END IF;
END$$;

-- =============================================================================
-- CONFIGURAÇÕES DE ÍNDICES
-- =============================================================================

-- Configurar parâmetros para busca de texto
SET pg_trgm.similarity_threshold = 0.3;
SET pg_trgm.word_similarity_threshold = 0.6;

-- =============================================================================
-- COMENTÁRIOS FINAIS
-- =============================================================================

-- Este script prepara o banco de dados com:
-- 1. Extensões necessárias para funcionalidades avançadas
-- 2. Funções auxiliares para operações comuns
-- 3. Tipos customizados para enums
-- 4. Configurações de performance e logging

-- As tabelas serão criadas pelas migrações do Alembic

-- =============================================================================
-- LOG DE INICIALIZAÇÃO
-- =============================================================================

-- Registrar que a inicialização foi concluída
DO $$
BEGIN
    RAISE NOTICE 'MegaEmu Modern: Banco de dados inicializado com sucesso!';
    RAISE NOTICE 'Extensões habilitadas: uuid-ossp, pg_trgm, unaccent, btree_gin, btree_gist';
    RAISE NOTICE 'Funções auxiliares criadas: unaccent_lower, text_similarity, generate_slug, update_modified_column, is_valid_email';
    RAISE NOTICE 'Tipos customizados criados: task_status, task_priority, user_role, rom_status';
END$$;