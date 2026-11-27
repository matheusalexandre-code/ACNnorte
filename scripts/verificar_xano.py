#!/usr/bin/env python3
"""Verifica, pelo terminal, se o ACNnorte está realmente vinculado ao Xano.

Uso (na raiz do projeto, com o venv ativado):

    python scripts/verificar_xano.py              # verificações só de leitura
    python scripts/verificar_xano.py --pytest     # + roda os testes do Xano e a suíte completa
    python scripts/verificar_xano.py --escrita    # + cria e apaga um cliente de teste no Xano

Nenhum valor de token é impresso. O teste de escrita pede confirmação antes de executar.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OK, FALHA, AVISO = "OK", "FALHA", "AVISO"
resultados: list[tuple[str, str, str]] = []


def registrar(etapa: str, status: str, detalhe: str) -> None:
    resultados.append((etapa, status, detalhe))
    cor = {"OK": "\033[32m", "FALHA": "\033[31m", "AVISO": "\033[33m"}[status]
    print(f"  {cor}[{status}]\033[0m {etapa}: {detalhe}")


def secao(titulo: str) -> None:
    print(f"\n\033[1m== {titulo} ==\033[0m")


# ---------------------------------------------------------------------------
# 1. Configuração
# ---------------------------------------------------------------------------
def verificar_configuracao() -> tuple[str, str]:
    secao("1. Configuração (.env)")
    env_file = ROOT / ".env"
    if env_file.exists():
        registrar("Arquivo .env", OK, "encontrado")
        try:
            from dotenv import load_dotenv

            load_dotenv(env_file, override=False)
        except ImportError:
            registrar("python-dotenv", FALHA, "não instalado (pip install -r requirements.txt)")
    else:
        registrar("Arquivo .env", FALHA, "não existe; rode: cp .env.example .env e preencha")

    url = (os.getenv("XANO_BASE_URL") or "").strip()
    token = (os.getenv("XANO_AUTH_TOKEN") or "").strip()

    if not url:
        registrar("XANO_BASE_URL", FALHA, "vazia")
    elif "SEU-INSTANCIA" in url:
        registrar("XANO_BASE_URL", FALHA, "ainda é o placeholder do .env.example")
    elif url.endswith("/"):
        registrar("XANO_BASE_URL", AVISO, f"{url} (tem barra no final; o cliente remove, mas corrija)")
    else:
        registrar("XANO_BASE_URL", OK, url)

    email = (os.getenv("XANO_SERVICE_EMAIL") or "").strip()
    senha = os.getenv("XANO_SERVICE_PASSWORD") or ""
    if email and senha:
        registrar("Conta de serviço", OK, f"{email} (senha definida)")
    else:
        registrar("Conta de serviço", FALHA if not token else AVISO,
                  "XANO_SERVICE_EMAIL/XANO_SERVICE_PASSWORD vazios"
                  + ("" if not token else "; usando só o token fixo, que expira em 24 h"))
    registrar("XANO_AUTH_TOKEN (reserva)", OK if token else AVISO, "definido" if token else "vazio")
    return url, token


# ---------------------------------------------------------------------------
# 2. Conectividade
# ---------------------------------------------------------------------------
def verificar_conexao(url: str, token: str):
    secao("2. Conectividade com o Xano")
    try:
        from src.core.database.xano_client import XanoClient, XanoError, smoke_test
    except ImportError as exc:
        registrar("Import do cliente", FALHA, f"{exc} (instale as dependências)")
        return None

    if not url or "SEU-INSTANCIA" in url:
        registrar("Smoke test", FALHA, "pulado: URL não configurada")
        return None

    r = smoke_test()
    status = OK if r.ok else FALHA
    registrar("Smoke test /auth/me", status,
              f"HTTP {r.status_code} em {r.latency_ms} ms, autenticado={r.authenticated}. {r.message}")

    try:
        import src.xano_sync as xano_sync

        token_app = xano_sync._resolve_token()
    except ImportError as exc:
        registrar("Import de xano_sync", FALHA, str(exc))
        return None
    if not token_app:
        registrar("Login no Xano", FALHA,
                  "sem token: confira XANO_SERVICE_EMAIL/XANO_SERVICE_PASSWORD e se o usuário está ativo no Xano")
        return None
    registrar("Login no Xano", OK, "token obtido (conta de serviço ou token fixo)")

    try:
        client = XanoClient(token=token_app)
        dados = client.get("/clients", params={"page": 1, "per_page": 5})
        itens = dados.get("items", dados) if isinstance(dados, dict) else dados
        total = dados.get("itemsTotal") if isinstance(dados, dict) else None
        qtd = len(itens) if isinstance(itens, list) else "?"
        registrar("Leitura GET /clients", OK,
                  f"{qtd} cliente(s) na 1ª página" + (f", {total} no total" if total is not None else ""))
        return client
    except XanoError as exc:
        registrar("Leitura GET /clients", FALHA, f"HTTP {exc.status_code}: {exc.message}")
        return None


# ---------------------------------------------------------------------------
# 3. O app liga o sync?
# ---------------------------------------------------------------------------
def verificar_fluxo_sync(token: str) -> None:
    secao("3. O app liga a sincronização?")
    try:
        import src.xano_sync as xano_sync
    except ImportError as exc:
        registrar("Import de xano_sync", FALHA, str(exc))
        return

    if not hasattr(xano_sync, "service_account_configured"):
        registrar("Suporte à conta de serviço", FALHA,
                  "src/xano_sync.py ainda é a versão antiga, que só sincroniza com token na sessão")
    ativo = xano_sync.sync_enabled()
    registrar("sync_enabled() como o app chama", OK if ativo else FALHA,
              "True: clientes, visitas e fotos vão para o Xano" if ativo
              else "False: o app grava só em data/*.json")


# ---------------------------------------------------------------------------
# 4. Escrita ponta a ponta (opcional)
# ---------------------------------------------------------------------------
def verificar_escrita(client) -> None:
    secao("4. Escrita ponta a ponta (cliente de teste)")
    if client is None:
        registrar("Escrita", FALHA, "pulada: sem leitura autenticada funcionando")
        return
    resp = input("  Isto cria e depois APAGA o cliente 'TESTE SYNC - APAGAR' no Xano. Continuar? [s/N] ")
    if resp.strip().lower() not in {"s", "sim"}:
        registrar("Escrita", AVISO, "cancelada pelo usuário")
        return

    from src.core.database.xano_client import XanoError

    cnpj = "99" + str(int(time.time() * 1000))[-12:]
    payload = {"name": "TESTE SYNC - APAGAR", "cnpj": cnpj, "responsible_person": "verificar_xano.py"}
    try:
        criado = client.post("/clients", json=payload)
        remote_id = criado.get("id") if isinstance(criado, dict) else None
        registrar("POST /clients", OK if remote_id else FALHA, f"id remoto = {remote_id}")
    except XanoError as exc:
        registrar("POST /clients", FALHA, f"HTTP {exc.status_code}: {exc.message}")
        return

    if not remote_id:
        return
    try:
        lido = client.get(f"/clients/{remote_id}")
        registrar("GET /clients/{id}", OK if isinstance(lido, dict) and lido.get("cnpj") == cnpj else FALHA,
                  "registro lido de volta com o mesmo CNPJ")
    except XanoError as exc:
        registrar("GET /clients/{id}", FALHA, f"HTTP {exc.status_code}: {exc.message}")
    try:
        client.delete(f"/clients/{remote_id}")
        registrar("DELETE /clients/{id}", OK, "cliente de teste apagado")
    except XanoError as exc:
        registrar("DELETE /clients/{id}", FALHA,
                  f"HTTP {exc.status_code}: {exc.message}. Apague 'TESTE SYNC - APAGAR' (id {remote_id}) à mão")


# ---------------------------------------------------------------------------
# 5. Testes automatizados (opcional)
# ---------------------------------------------------------------------------
def rodar_pytest() -> None:
    secao("5. Testes automatizados")
    alvos = ["tests/test_xano_client.py", "tests/test_xano_sync.py", "tests/test_xano_service_account.py",
             "tests/test_passwordless_auth.py", "tests/test_auth_service.py"]
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", *alvos], cwd=ROOT,
                       capture_output=True, text=True)
    ultima = (r.stdout.strip().splitlines() or ["sem saída"])[-1]
    registrar("Testes do Xano e do login", OK if r.returncode == 0 else FALHA, ultima)
    if r.returncode != 0:
        print(r.stdout[-3000:])

    r = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, capture_output=True, text=True)
    ultima = (r.stdout.strip().splitlines() or ["sem saída"])[-1]
    base = ROOT / "pytest_baseline.txt"
    ref = ""
    if base.exists():
        linhas = base.read_text(encoding="utf-8-sig", errors="ignore").strip().splitlines()
        ref = f" | baseline: {linhas[-1].strip()}" if linhas else ""
    registrar("Suíte completa", OK if r.returncode == 0 else FALHA, ultima + ref)


# ---------------------------------------------------------------------------
def veredito() -> int:
    secao("Resumo")
    falhas = [r for r in resultados if r[1] == FALHA]
    nomes = {r[0] for r in falhas}
    conexao_ok = not ({"Smoke test /auth/me", "XANO_BASE_URL", "Login no Xano", "Leitura GET /clients"} & nomes)
    sync_ok = "sync_enabled() como o app chama" not in nomes

    if conexao_ok and sync_ok:
        v = "VINCULADO"
    elif conexao_ok:
        v = "PARCIAL: o Xano responde, mas o app não liga o sync (grava só em data/*.json)"
    else:
        v = "NÃO VINCULADO: corrija a configuração/conexão primeiro"
    print(f"  Veredito: \033[1m{v}\033[0m")
    print(f"  {len(resultados)} verificações, {len(falhas)} falha(s).")
    return 0 if v == "VINCULADO" else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Verifica o vínculo do ACNnorte com o Xano.")
    p.add_argument("--escrita", action="store_true", help="cria e apaga um cliente de teste no Xano")
    p.add_argument("--pytest", action="store_true", help="roda os testes do Xano e a suíte completa")
    args = p.parse_args()

    url, token = verificar_configuracao()
    client = verificar_conexao(url, token)
    verificar_fluxo_sync(token)
    if args.escrita:
        verificar_escrita(client)
    if args.pytest:
        rodar_pytest()
    return veredito()


if __name__ == "__main__":
    sys.exit(main())
