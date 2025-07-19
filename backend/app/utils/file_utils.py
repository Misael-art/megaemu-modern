"""Utilitários para manipulação de arquivos.

Este módulo contém funções para operações com arquivos,
cálculo de hashes, compressão/descompressão e validação.
"""

import asyncio
import hashlib
import os
import shutil
import zipfile
import rarfile
import py7zr
import gzip
import tarfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Union, Tuple


async def calculate_file_hash(
    file_path: Union[str, Path],
    hash_type: str = "md5",
    chunk_size: int = 8192
) -> str:
    """Calcula hash de um arquivo.
    
    Args:
        file_path: Caminho do arquivo
        hash_type: Tipo de hash (md5, sha1, sha256, crc32)
        chunk_size: Tamanho do chunk para leitura
        
    Returns:
        Hash do arquivo em hexadecimal
        
    Raises:
        FileNotFoundError: Se arquivo não existe
        ValueError: Se tipo de hash não suportado
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    
    # Seleciona algoritmo de hash
    if hash_type.lower() == "md5":
        hasher = hashlib.md5()
    elif hash_type.lower() == "sha1":
        hasher = hashlib.sha1()
    elif hash_type.lower() == "sha256":
        hasher = hashlib.sha256()
    elif hash_type.lower() == "crc32":
        import zlib
        crc = 0
        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                crc = zlib.crc32(chunk, crc)
        return format(crc & 0xffffffff, '08x')
    else:
        raise ValueError(f"Tipo de hash não suportado: {hash_type}")
    
    # Calcula hash em chunks para arquivos grandes
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    
    return hasher.hexdigest()


def get_file_size(file_path: Union[str, Path]) -> int:
    """Obtém tamanho do arquivo em bytes.
    
    Args:
        file_path: Caminho do arquivo
        
    Returns:
        Tamanho em bytes
        
    Raises:
        FileNotFoundError: Se arquivo não existe
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    
    return file_path.stat().st_size


def get_file_extension(file_path: Union[str, Path]) -> str:
    """Obtém extensão do arquivo.
    
    Args:
        file_path: Caminho do arquivo
        
    Returns:
        Extensão do arquivo (com ponto)
    """
    return Path(file_path).suffix.lower()


def is_archive_file(file_path: Union[str, Path]) -> bool:
    """Verifica se arquivo é um arquivo comprimido.
    
    Args:
        file_path: Caminho do arquivo
        
    Returns:
        True se for arquivo comprimido
    """
    archive_extensions = {
        '.zip', '.rar', '.7z', '.gz', '.tar',
        '.bz2', '.xz', '.lzma', '.tar.gz',
        '.tar.bz2', '.tar.xz'
    }
    
    extension = get_file_extension(file_path)
    return extension in archive_extensions


async def extract_archive(
    archive_path: Union[str, Path],
    extract_to: Union[str, Path],
    password: Optional[str] = None
) -> List[Path]:
    """Extrai arquivo comprimido.
    
    Args:
        archive_path: Caminho do arquivo
        extract_to: Diretório de destino
        password: Senha do arquivo (opcional)
        
    Returns:
        Lista de arquivos extraídos
        
    Raises:
        ValueError: Se formato não suportado
        RuntimeError: Se erro na extração
    """
    archive_path = Path(archive_path)
    extract_to = Path(extract_to)
    
    if not archive_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {archive_path}")
    
    extract_to.mkdir(parents=True, exist_ok=True)
    extracted_files = []
    
    try:
        extension = get_file_extension(archive_path)
        
        if extension == '.zip':
            extracted_files = await _extract_zip(archive_path, extract_to, password)
        elif extension == '.rar':
            extracted_files = await _extract_rar(archive_path, extract_to, password)
        elif extension == '.7z':
            extracted_files = await _extract_7z(archive_path, extract_to, password)
        elif extension in ['.gz', '.tar']:
            extracted_files = await _extract_tar(archive_path, extract_to)
        else:
            raise ValueError(f"Formato não suportado: {extension}")
    
    except Exception as e:
        raise RuntimeError(f"Erro ao extrair arquivo: {e}")
    
    return extracted_files


async def _extract_zip(
    zip_path: Path,
    extract_to: Path,
    password: Optional[str] = None
) -> List[Path]:
    """Extrai arquivo ZIP."""
    extracted_files = []
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        if password:
            zip_ref.setpassword(password.encode())
        
        for file_info in zip_ref.filelist:
            if not file_info.is_dir():
                extracted_path = extract_to / file_info.filename
                extracted_path.parent.mkdir(parents=True, exist_ok=True)
                
                with zip_ref.open(file_info) as source:
                    with open(extracted_path, 'wb') as target:
                        shutil.copyfileobj(source, target)
                
                extracted_files.append(extracted_path)
    
    return extracted_files


async def _extract_rar(
    rar_path: Path,
    extract_to: Path,
    password: Optional[str] = None
) -> List[Path]:
    """Extrai arquivo RAR."""
    extracted_files = []
    
    with rarfile.RarFile(rar_path, 'r') as rar_ref:
        if password:
            rar_ref.setpassword(password)
        
        for file_info in rar_ref.infolist():
            if not file_info.is_dir():
                extracted_path = extract_to / file_info.filename
                extracted_path.parent.mkdir(parents=True, exist_ok=True)
                
                with rar_ref.open(file_info) as source:
                    with open(extracted_path, 'wb') as target:
                        shutil.copyfileobj(source, target)
                
                extracted_files.append(extracted_path)
    
    return extracted_files


async def _extract_7z(
    seven_z_path: Path,
    extract_to: Path,
    password: Optional[str] = None
) -> List[Path]:
    """Extrai arquivo 7Z."""
    extracted_files = []
    
    with py7zr.SevenZipFile(seven_z_path, 'r', password=password) as seven_z_ref:
        seven_z_ref.extractall(path=extract_to)
        
        for file_info in seven_z_ref.list():
            if not file_info.is_dir:
                extracted_path = extract_to / file_info.filename
                if extracted_path.exists():
                    extracted_files.append(extracted_path)
    
    return extracted_files


async def _extract_tar(
    tar_path: Path,
    extract_to: Path
) -> List[Path]:
    """Extrai arquivo TAR/GZ."""
    extracted_files = []
    
    # Detecta modo de abertura
    if tar_path.suffix == '.gz' or '.tar.gz' in str(tar_path):
        mode = 'r:gz'
    elif tar_path.suffix == '.bz2' or '.tar.bz2' in str(tar_path):
        mode = 'r:bz2'
    elif tar_path.suffix == '.xz' or '.tar.xz' in str(tar_path):
        mode = 'r:xz'
    else:
        mode = 'r'
    
    with tarfile.open(tar_path, mode) as tar_ref:
        tar_ref.extractall(path=extract_to)
        
        for member in tar_ref.getmembers():
            if member.isfile():
                extracted_path = extract_to / member.name
                if extracted_path.exists():
                    extracted_files.append(extracted_path)
    
    return extracted_files


def normalize_path(path: Union[str, Path]) -> Path:
    """Normaliza caminho do arquivo.
    
    Args:
        path: Caminho para normalizar
        
    Returns:
        Caminho normalizado
    """
    path = Path(path)
    return path.resolve()


def validate_file_path(file_path: Union[str, Path]) -> bool:
    """Valida se caminho do arquivo é válido.
    
    Args:
        file_path: Caminho para validar
        
    Returns:
        True se válido
    """
    try:
        path = Path(file_path)
        # Verifica se o caminho é absoluto e válido
        return path.is_absolute() and path.parent.exists()
    except (OSError, ValueError):
        return False


def create_directory(dir_path: Union[str, Path]) -> Path:
    """Cria diretório se não existir.
    
    Args:
        dir_path: Caminho do diretório
        
    Returns:
        Caminho do diretório criado
        
    Raises:
        OSError: Se erro na criação
    """
    dir_path = Path(dir_path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


async def copy_file(
    source: Union[str, Path],
    destination: Union[str, Path],
    overwrite: bool = False
) -> Path:
    """Copia arquivo.
    
    Args:
        source: Arquivo de origem
        destination: Destino
        overwrite: Se deve sobrescrever
        
    Returns:
        Caminho do arquivo copiado
        
    Raises:
        FileNotFoundError: Se origem não existe
        FileExistsError: Se destino existe e overwrite=False
    """
    source = Path(source)
    destination = Path(destination)
    
    if not source.exists():
        raise FileNotFoundError(f"Arquivo de origem não encontrado: {source}")
    
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Arquivo de destino já existe: {destination}")
    
    # Cria diretório de destino se necessário
    destination.parent.mkdir(parents=True, exist_ok=True)
    
    # Copia arquivo
    shutil.copy2(source, destination)
    
    return destination


async def move_file(
    source: Union[str, Path],
    destination: Union[str, Path],
    overwrite: bool = False
) -> Path:
    """Move arquivo.
    
    Args:
        source: Arquivo de origem
        destination: Destino
        overwrite: Se deve sobrescrever
        
    Returns:
        Caminho do arquivo movido
        
    Raises:
        FileNotFoundError: Se origem não existe
        FileExistsError: Se destino existe e overwrite=False
    """
    source = Path(source)
    destination = Path(destination)
    
    if not source.exists():
        raise FileNotFoundError(f"Arquivo de origem não encontrado: {source}")
    
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Arquivo de destino já existe: {destination}")
    
    # Cria diretório de destino se necessário
    destination.parent.mkdir(parents=True, exist_ok=True)
    
    # Move arquivo
    shutil.move(source, destination)
    
    return destination


def delete_file(file_path: Union[str, Path]) -> bool:
    """Remove arquivo.
    
    Args:
        file_path: Caminho do arquivo
        
    Returns:
        True se removido com sucesso
    """
    try:
        file_path = Path(file_path)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    except OSError:
        return False


def list_directory_files(
    directory: Union[str, Path],
    pattern: str = "*",
    recursive: bool = False
) -> List[Path]:
    """Lista arquivos em diretório.
    
    Args:
        directory: Diretório para listar
        pattern: Padrão de arquivos
        recursive: Se deve buscar recursivamente
        
    Returns:
        Lista de arquivos encontrados
    """
    directory = Path(directory)
    
    if not directory.exists() or not directory.is_dir():
        return []
    
    if recursive:
        return list(directory.rglob(pattern))
    else:
        return list(directory.glob(pattern))


def get_file_info(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Obtém informações detalhadas do arquivo.
    
    Args:
        file_path: Caminho do arquivo
        
    Returns:
        Dicionário com informações do arquivo
        
    Raises:
        FileNotFoundError: Se arquivo não existe
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    
    stat = file_path.stat()
    
    return {
        "name": file_path.name,
        "path": str(file_path),
        "size": stat.st_size,
        "extension": file_path.suffix.lower(),
        "created": datetime.fromtimestamp(stat.st_ctime),
        "modified": datetime.fromtimestamp(stat.st_mtime),
        "accessed": datetime.fromtimestamp(stat.st_atime),
        "is_file": file_path.is_file(),
        "is_dir": file_path.is_dir(),
        "is_archive": is_archive_file(file_path)
    }


async def compress_file(
    file_path: Union[str, Path],
    output_path: Union[str, Path],
    compression_type: str = "zip"
) -> Path:
    """Comprime arquivo.
    
    Args:
        file_path: Arquivo para comprimir
        output_path: Arquivo de saída
        compression_type: Tipo de compressão (zip, gz, 7z)
        
    Returns:
        Caminho do arquivo comprimido
        
    Raises:
        ValueError: Se tipo não suportado
        FileNotFoundError: Se arquivo não existe
    """
    file_path = Path(file_path)
    output_path = Path(output_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if compression_type.lower() == "zip":
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
            zip_ref.write(file_path, file_path.name)
    
    elif compression_type.lower() == "gz":
        with open(file_path, 'rb') as f_in:
            with gzip.open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    
    elif compression_type.lower() == "7z":
        with py7zr.SevenZipFile(output_path, 'w') as seven_z_ref:
            seven_z_ref.write(file_path, file_path.name)
    
    else:
        raise ValueError(f"Tipo de compressão não suportado: {compression_type}")
    
    return output_path


async def decompress_file(
    compressed_path: Union[str, Path],
    output_path: Union[str, Path]
) -> Path:
    """Descomprime arquivo.
    
    Args:
        compressed_path: Arquivo comprimido
        output_path: Arquivo de saída
        
    Returns:
        Caminho do arquivo descomprimido
        
    Raises:
        ValueError: Se formato não suportado
        FileNotFoundError: Se arquivo não existe
    """
    compressed_path = Path(compressed_path)
    output_path = Path(output_path)
    
    if not compressed_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {compressed_path}")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    extension = get_file_extension(compressed_path)
    
    if extension == ".gz":
        with gzip.open(compressed_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    
    elif extension in [".zip", ".rar", ".7z"]:
        # Para estes formatos, usa extract_archive
        extracted_files = await extract_archive(compressed_path, output_path.parent)
        if extracted_files:
            return extracted_files[0]  # Retorna primeiro arquivo extraído
    
    else:
        raise ValueError(f"Formato não suportado para descompressão: {extension}")
    
    return output_path


def get_directory_size(directory: Union[str, Path]) -> int:
    """Calcula tamanho total de um diretório.
    
    Args:
        directory: Diretório para calcular
        
    Returns:
        Tamanho total em bytes
    """
    directory = Path(directory)
    total_size = 0
    
    if directory.exists() and directory.is_dir():
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                try:
                    total_size += file_path.stat().st_size
                except OSError:
                    pass  # Ignora arquivos inacessíveis
    
    return total_size


def clean_directory(
    directory: Union[str, Path],
    max_age_hours: int = 24,
    pattern: str = "*"
) -> int:
    """Limpa arquivos antigos de um diretório.
    
    Args:
        directory: Diretório para limpar
        max_age_hours: Idade máxima em horas
        pattern: Padrão de arquivos para limpar
        
    Returns:
        Número de arquivos removidos
    """
    directory = Path(directory)
    
    if not directory.exists() or not directory.is_dir():
        return 0
    
    max_age_seconds = max_age_hours * 3600
    current_time = datetime.now().timestamp()
    removed_count = 0
    
    for file_path in directory.glob(pattern):
        if file_path.is_file():
            try:
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    file_path.unlink()
                    removed_count += 1
            except OSError:
                pass  # Ignora erros de remoção
    
    return removed_count

def scan_directory(directory: Union[str, Path], recursive: bool = True) -> List[Path]:
    """Escaneia diretório em busca de arquivos ROM.
    
    Args:
        directory: Diretório para escanear
        recursive: Se deve buscar recursivamente
        
    Returns:
        Lista de arquivos ROM encontrados
    """
    directory = Path(directory)
    
    if not directory.exists() or not directory.is_dir():
        return []
    
    rom_extensions = {
        '.zip', '.rar', '.7z', '.gz',
        '.nes', '.smc', '.sfc', '.gb', '.gbc', '.gba',
        '.n64', '.z64', '.v64', '.ndd',
        '.iso', '.cue', '.bin', '.img',
        '.rom', '.a26', '.a78',
        '.md', '.gen', '.smd',
        '.pce', '.sgx',
        '.ws', '.wsc',
        '.ngp', '.ngc'
    }
    
    rom_files = []
    
    if recursive:
        for file_path in directory.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in rom_extensions:
                rom_files.append(file_path)
    else:
        for file_path in directory.glob('*'):
            if file_path.is_file() and file_path.suffix.lower() in rom_extensions:
                rom_files.append(file_path)
    
    return rom_files


def is_valid_rom_file(file_path: Union[str, Path]) -> bool:
    """Verifica se arquivo é um ROM válido.
    
    Args:
        file_path: Caminho do arquivo
        
    Returns:
        True se for um ROM válido
    """
    file_path = Path(file_path)
    
    if not file_path.exists() or not file_path.is_file():
        return False
    
    # Verifica extensão
    rom_extensions = {
        '.zip', '.rar', '.7z', '.gz',
        '.nes', '.smc', '.sfc', '.gb', '.gbc', '.gba',
        '.n64', '.z64', '.v64', '.ndd',
        '.iso', '.cue', '.bin', '.img',
        '.rom', '.a26', '.a78',
        '.md', '.gen', '.smd',
        '.pce', '.sgx',
        '.ws', '.wsc',
        '.ngp', '.ngc'
    }
    
    if file_path.suffix.lower() not in rom_extensions:
        return False
    
    # Verifica tamanho mínimo (1KB)
    try:
        if file_path.stat().st_size < 1024:
            return False
    except OSError:
        return False
    
    return True


# Alias para compatibilidade
get_file_hash = calculate_file_hash