"""Espelhamento opcional de arquivos gerados para ``storage/``.

O ACNnorte usa ``data/`` como armazenamento principal (JSON, fotos e exports).
Este módulo apenas cria uma cópia de segurança legível dos arquivos finalizados
nas pastas solicitadas ``storage/photos``, ``storage/reports`` e
``storage/exports``. Nunca sobrescreve arquivos existentes e nunca interrompe a
operação principal se o espelhamento falhar.
"""

import os
import shutil
import uuid
from pathlib import Path

_KINDS = ("photos", "reports", "exports")


def storage_root() -> Path:
    """Raiz de armazenamento derivada do DATA_DIR ativo (respeita testes temporários)."""
    from src.storage_manager import DATA_DIR

    return Path(DATA_DIR).resolve().parent


def ensure_storage_dirs() -> dict:
    """Cria (se necessário) e devolve as pastas de espelhamento."""
    root = storage_root()
    dirs = {kind: root / "storage" / kind for kind in _KINDS}
    for path in dirs.values():
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    return dirs


def _unique_destination(directory: Path, filename: str) -> Path:
    base, ext = os.path.splitext(filename)
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    return directory / f"{base}_{uuid.uuid4().hex[:8]}{ext}"


def mirror_file(source_path: str, kind: str) -> str:
    """Copia ``source_path`` para ``storage/<kind>`` sem sobrescrever arquivos.

    Retorna o caminho da cópia ou ``None`` quando não há arquivo de origem ou
    quando o espelhamento não é possível. Erros são silenciosos por design:
    a persistência principal não pode depender desta cópia auxiliar.
    """
    if kind not in _KINDS or not source_path:
        return None
    source = Path(source_path)
    if not source.is_file():
        return None
    try:
        directory = ensure_storage_dirs()[kind]
        destination = _unique_destination(directory, source.name)
        shutil.copy2(str(source), str(destination))
        return str(destination)
    except (OSError, ValueError):
        return None
