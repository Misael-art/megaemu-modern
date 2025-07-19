"""Endpoints de gerenciamento de ROMs.

Fornece endpoints para:
- CRUD de ROMs
- Upload e download de arquivos
- Verificação e validação
- Extração de arquivos compactados
- Análise de checksums
- Organização e categorização
"""

from typing import List, Optional
from uuid import UUID
import os
from pathlib import Path

from fastapi import (
    APIRouter, 
    Depends, 
    HTTPException, 
    Query, 
    status, 
    UploadFile, 
    File,
    Form,
    BackgroundTasks
)
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, get_current_active_superuser
from app.core.config import get_settings
from app.models.user import User
from app.schemas.rom import (
    ROMResponse,
    ROMCreate,
    ROMUpdate,
    ROMList,
    ROMDetail,
    ROMStats,
    ROMVerification,
    ROMUploadResponse,
    ROMBatchOperation
)
from app.schemas.base import PaginatedResponse
from app.services.rom import ROMService, ROMVerificationService
from app.services.processing import FileService, MetadataService
from app.utils.validation_utils import (
    validate_pagination_params,
    validate_sort_params,
    validate_search_query,
    validate_file_extension,
    validate_file_size
)
from app.utils.file_utils import (
    get_file_hash,
    get_file_size,
    is_archive_file,
    extract_archive
)

router = APIRouter()
settings = get_settings()


@router.get("/", response_model=PaginatedResponse[ROMList])
async def list_roms(
    skip: int = Query(0, ge=0, description="Número de registros para pular"),
    limit: int = Query(50, ge=1, le=100, description="Número máximo de registros"),
    search: Optional[str] = Query(None, description="Busca por nome do arquivo ou jogo"),
    game_id: Optional[int] = Query(None, description="Filtrar por jogo"),
    system_id: Optional[int] = Query(None, description="Filtrar por sistema"),
    region: Optional[str] = Query(None, description="Filtrar por região"),
    language: Optional[str] = Query(None, description="Filtrar por idioma"),
    verified: Optional[bool] = Query(None, description="Filtrar por status de verificação"),
    has_file: Optional[bool] = Query(None, description="Filtrar ROMs com/sem arquivo"),
    file_format: Optional[str] = Query(None, description="Filtrar por formato do arquivo"),
    sort_by: str = Query("filename", description="Campo para ordenação"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Ordem da classificação"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista ROMs com filtros e paginação.
    
    Args:
        skip: Número de registros para pular
        limit: Limite de registros por página
        search: Termo de busca
        game_id: Filtro por jogo
        system_id: Filtro por sistema
        region: Filtro por região
        language: Filtro por idioma
        verified: Filtro por verificação
        has_file: Filtro por presença de arquivo
        file_format: Filtro por formato
        sort_by: Campo para ordenação
        sort_order: Ordem da classificação
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        PaginatedResponse[ROMList]: Lista paginada de ROMs
    """
    # Valida parâmetros
    validate_pagination_params(skip, limit)
    validate_sort_params(sort_by, ["filename", "file_size", "created_at", "verified_at"])
    
    if search:
        validate_search_query(search)
    
    rom_service = ROMService(db)
    
    # Filtros
    filters = {}
    if game_id:
        filters["game_id"] = game_id
    if system_id:
        filters["system_id"] = system_id
    if region:
        filters["region"] = region
    if language:
        filters["language"] = language
    if verified is not None:
        filters["verified"] = verified
    if has_file is not None:
        filters["has_file"] = has_file
    if file_format:
        filters["file_format"] = file_format
    
    # Busca ROMs
    roms, total = await rom_service.list_roms(
        skip=skip,
        limit=limit,
        search=search,
        filters=filters,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    return PaginatedResponse(
        items=[ROMList.model_validate(rom) for rom in roms],
        total=total,
        page=skip // limit + 1,
        per_page=limit,
        pages=(total + limit - 1) // limit
    )


@router.get("/stats")
async def get_roms_stats(
    system_id: Optional[int] = Query(None, description="Filtrar por sistema"),
    game_id: Optional[int] = Query(None, description="Filtrar por jogo"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna estatísticas gerais das ROMs.
    
    Args:
        system_id: Filtro por sistema
        game_id: Filtro por jogo
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        dict: Estatísticas das ROMs
    """
    rom_service = ROMService(db)
    stats = await rom_service.get_general_stats(system_id, game_id)
    return stats


@router.get("/formats")
async def list_formats(
    system_id: Optional[int] = Query(None, description="Filtrar por sistema"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista formatos únicos de ROMs.
    
    Args:
        system_id: Filtro por sistema
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        List[str]: Lista de formatos
    """
    rom_service = ROMService(db)
    formats = await rom_service.get_formats(system_id)
    return {"formats": formats}


@router.get("/regions")
async def list_regions(
    system_id: Optional[int] = Query(None, description="Filtrar por sistema"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista regiões únicas de ROMs.
    
    Args:
        system_id: Filtro por sistema
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        List[str]: Lista de regiões
    """
    rom_service = ROMService(db)
    regions = await rom_service.get_regions(system_id)
    return {"regions": regions}


@router.get("/languages")
async def list_languages(
    system_id: Optional[int] = Query(None, description="Filtrar por sistema"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista idiomas únicos de ROMs.
    
    Args:
        system_id: Filtro por sistema
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        List[str]: Lista de idiomas
    """
    rom_service = ROMService(db)
    languages = await rom_service.get_languages(system_id)
    return {"languages": languages}


@router.post("/upload", response_model=ROMUploadResponse)
async def upload_rom(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    game_id: Optional[int] = Form(None),
    region: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    auto_extract: bool = Form(True),
    auto_verify: bool = Form(True),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Faz upload de arquivo ROM.
    
    Args:
        background_tasks: Tarefas em background
        file: Arquivo ROM para upload
        game_id: ID do jogo associado
        region: Região da ROM
        language: Idioma da ROM
        version: Versão da ROM
        description: Descrição da ROM
        auto_extract: Se deve extrair arquivos compactados
        auto_verify: Se deve verificar automaticamente
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        ROMUploadResponse: Resultado do upload
        
    Raises:
        HTTPException: Se arquivo inválido ou erro no upload
    """
    # Validações do arquivo
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome do arquivo é obrigatório"
        )
    
    # Valida extensão
    file_ext = Path(file.filename).suffix.lower()
    validate_file_extension(file_ext, settings.ROM_EXTENSIONS)
    
    # Valida tamanho
    file_size = 0
    if hasattr(file, 'size') and file.size:
        file_size = file.size
        validate_file_size(file_size, settings.MAX_ROM_SIZE)
    
    # Verifica se jogo existe
    if game_id:
        from app.services.game import GameService
        game_service = GameService(db)
        game = await game_service.get_by_id(game_id)
        if not game:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Jogo não encontrado"
            )
    
    try:
        # Salva arquivo
        file_service = FileService()
        file_path = await file_service.save_rom_file(file, current_user.id)
        
        # Calcula hash e tamanho real
        file_hash = get_file_hash(file_path)
        actual_size = get_file_size(file_path)
        
        # Cria registro da ROM
        rom_service = ROMService(db)
        rom_data = {
            "filename": file.filename,
            "file_path": str(file_path),
            "file_size": actual_size,
            "file_hash": file_hash,
            "file_format": file_ext,
            "game_id": game_id,
            "region": region,
            "language": language,
            "version": version,
            "description": description,
            "uploaded_by": current_user.id
        }
        
        rom = await rom_service.create(rom_data)
        
        # Tarefas em background
        if auto_extract and is_archive_file(file_path):
            background_tasks.add_task(
                extract_and_process_archive,
                rom.id,
                file_path,
                current_user.id
            )
        
        if auto_verify:
            background_tasks.add_task(
                verify_rom_background,
                rom.id,
                current_user.id
            )
        
        return ROMUploadResponse(
            id=rom.id,
            filename=rom.filename,
            file_size=rom.file_size,
            file_hash=rom.file_hash,
            message="Upload realizado com sucesso",
            auto_extract=auto_extract and is_archive_file(file_path),
            auto_verify=auto_verify
        )
        
    except Exception as e:
        # Remove arquivo em caso de erro
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro no upload: {str(e)}"
        )


@router.get("/{rom_id}", response_model=ROMDetail)
async def get_rom(
    rom_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna dados detalhados de uma ROM específica.
    
    Args:
        rom_id: ID da ROM
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        ROMDetail: Dados detalhados da ROM
        
    Raises:
        HTTPException: Se ROM não encontrada
    """
    rom_service = ROMService(db)
    rom = await rom_service.get_detailed(rom_id)
    
    if not rom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ROM não encontrada"
        )
    
    return ROMDetail.model_validate(rom)


@router.get("/{rom_id}/download")
async def download_rom(
    rom_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Faz download de uma ROM específica.
    
    Args:
        rom_id: ID da ROM
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        FileResponse: Arquivo da ROM
        
    Raises:
        HTTPException: Se ROM não encontrada ou arquivo não existe
    """
    rom_service = ROMService(db)
    rom = await rom_service.get_by_id(rom_id)
    
    if not rom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ROM não encontrada"
        )
    
    if not rom.file_path or not os.path.exists(rom.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo da ROM não encontrado"
        )
    
    # Registra download
    await rom_service.register_download(rom_id, current_user.id)
    
    return FileResponse(
        path=rom.file_path,
        filename=rom.filename,
        media_type='application/octet-stream'
    )


@router.put("/{rom_id}", response_model=ROMResponse)
async def update_rom(
    rom_id: int,
    rom_update: ROMUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Atualiza dados de uma ROM específica.
    
    Args:
        rom_id: ID da ROM
        rom_update: Dados para atualização
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        ROMResponse: Dados atualizados da ROM
        
    Raises:
        HTTPException: Se ROM não encontrada ou sem permissão
    """
    rom_service = ROMService(db)
    
    # Verifica se ROM existe
    rom = await rom_service.get_by_id(rom_id)
    if not rom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ROM não encontrada"
        )
    
    # Verifica permissão (apenas o uploader ou superuser)
    if rom.uploaded_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para editar esta ROM"
        )
    
    # Validações
    update_data = rom_update.dict(exclude_unset=True)
    
    if "game_id" in update_data and update_data["game_id"]:
        # Verifica se jogo existe
        from app.services.game import GameService
        game_service = GameService(db)
        game = await game_service.get_by_id(update_data["game_id"])
        if not game:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Jogo não encontrado"
            )
    
    # Atualiza ROM
    update_data["updated_by"] = current_user.id
    updated_rom = await rom_service.update(rom_id, update_data)
    return ROMResponse.model_validate(updated_rom)


@router.delete("/{rom_id}")
async def delete_rom(
    rom_id: int,
    delete_file: bool = Query(True, description="Se deve deletar o arquivo físico"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Deleta uma ROM específica.
    
    Args:
        rom_id: ID da ROM
        delete_file: Se deve deletar arquivo físico
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        dict: Mensagem de confirmação
        
    Raises:
        HTTPException: Se ROM não encontrada ou sem permissão
    """
    rom_service = ROMService(db)
    
    # Verifica se ROM existe
    rom = await rom_service.get_by_id(rom_id)
    if not rom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ROM não encontrada"
        )
    
    # Verifica permissão (apenas o uploader ou superuser)
    if rom.uploaded_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para deletar esta ROM"
        )
    
    # Deleta arquivo físico se solicitado
    if delete_file and rom.file_path and os.path.exists(rom.file_path):
        try:
            os.remove(rom.file_path)
        except OSError as e:
            # Log do erro mas não falha a operação
            pass
    
    # Deleta registro
    await rom_service.delete(rom_id)
    
    return {"message": "ROM deletada com sucesso"}


# Endpoints de verificação

@router.post("/{rom_id}/verify", response_model=ROMVerification)
async def verify_rom(
    rom_id: int,
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Forçar nova verificação"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Verifica integridade de uma ROM específica.
    
    Args:
        rom_id: ID da ROM
        background_tasks: Tarefas em background
        force: Forçar nova verificação
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        ROMVerification: Resultado da verificação
        
    Raises:
        HTTPException: Se ROM não encontrada
    """
    rom_service = ROMService(db)
    
    # Verifica se ROM existe
    rom = await rom_service.get_by_id(rom_id)
    if not rom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ROM não encontrada"
        )
    
    # Verifica se já foi verificada recentemente
    if not force and rom.verified_at:
        from datetime import datetime, timedelta
        if datetime.utcnow() - rom.verified_at < timedelta(hours=24):
            return ROMVerification(
                rom_id=rom_id,
                verified=rom.verified,
                verification_date=rom.verified_at,
                file_exists=bool(rom.file_path and os.path.exists(rom.file_path)),
                hash_match=rom.verified,
                message="Verificação recente encontrada"
            )
    
    # Inicia verificação em background
    background_tasks.add_task(
        verify_rom_background,
        rom_id,
        current_user.id
    )
    
    return ROMVerification(
        rom_id=rom_id,
        verified=None,
        verification_date=None,
        file_exists=bool(rom.file_path and os.path.exists(rom.file_path)),
        hash_match=None,
        message="Verificação iniciada em background"
    )


@router.post("/batch-verify")
async def batch_verify_roms(
    background_tasks: BackgroundTasks,
    rom_ids: List[int] = Query(..., description="IDs das ROMs para verificar"),
    force: bool = Query(False, description="Forçar nova verificação"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Verifica múltiplas ROMs em lote.
    
    Args:
        background_tasks: Tarefas em background
        rom_ids: Lista de IDs das ROMs
        force: Forçar nova verificação
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        dict: Status da operação em lote
        
    Raises:
        HTTPException: Se lista vazia ou muitas ROMs
    """
    if not rom_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lista de ROMs não pode estar vazia"
        )
    
    if len(rom_ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Máximo de 100 ROMs por operação"
        )
    
    # Verifica se ROMs existem
    rom_service = ROMService(db)
    existing_roms = await rom_service.get_multiple(rom_ids)
    existing_ids = [rom.id for rom in existing_roms]
    
    not_found = set(rom_ids) - set(existing_ids)
    if not_found:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ROMs não encontradas: {list(not_found)}"
        )
    
    # Inicia verificação em background
    background_tasks.add_task(
        batch_verify_roms_background,
        rom_ids,
        force,
        current_user.id
    )
    
    return {
        "message": "Verificação em lote iniciada",
        "rom_count": len(rom_ids),
        "force": force
    }


@router.post("/batch-operation")
async def batch_rom_operation(
    operation: ROMBatchOperation,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Executa operação em lote em ROMs (apenas superusers).
    
    Args:
        operation: Dados da operação em lote
        background_tasks: Tarefas em background
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        dict: Status da operação
        
    Raises:
        HTTPException: Se operação inválida
    """
    if not operation.rom_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lista de ROMs não pode estar vazia"
        )
    
    if len(operation.rom_ids) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Máximo de 500 ROMs por operação"
        )
    
    # Valida operação
    valid_operations = ["verify", "delete", "update_metadata", "move_files"]
    if operation.operation not in valid_operations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Operação inválida. Opções: {', '.join(valid_operations)}"
        )
    
    # Verifica se ROMs existem
    rom_service = ROMService(db)
    existing_roms = await rom_service.get_multiple(operation.rom_ids)
    existing_ids = [rom.id for rom in existing_roms]
    
    not_found = set(operation.rom_ids) - set(existing_ids)
    if not_found:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ROMs não encontradas: {list(not_found)}"
        )
    
    # Inicia operação em background
    background_tasks.add_task(
        execute_batch_operation,
        operation.operation,
        operation.rom_ids,
        operation.parameters or {},
        current_user.id
    )
    
    return {
        "message": f"Operação '{operation.operation}' iniciada",
        "rom_count": len(operation.rom_ids),
        "operation": operation.operation
    }


# Funções auxiliares para tarefas em background

async def extract_and_process_archive(rom_id: int, file_path: Path, user_id: int):
    """Extrai arquivo compactado e processa conteúdo."""
    try:
        # Implementar extração de arquivo
        pass
    except Exception as e:
        # Log do erro
        pass


async def verify_rom_background(rom_id: int, user_id: int):
    """Verifica ROM em background."""
    try:
        # Implementar verificação
        pass
    except Exception as e:
        # Log do erro
        pass


async def batch_verify_roms_background(rom_ids: List[int], force: bool, user_id: int):
    """Verifica múltiplas ROMs em background."""
    try:
        # Implementar verificação em lote
        pass
    except Exception as e:
        # Log do erro
        pass


async def execute_batch_operation(operation: str, rom_ids: List[int], parameters: dict, user_id: int):
    """Executa operação em lote em background."""
    try:
        # Implementar operação em lote
        pass
    except Exception as e:
        # Log do erro
        pass