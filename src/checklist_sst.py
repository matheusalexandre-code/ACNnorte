"""Checklist modular de Segurança do Trabalho do ACNnorte.

Este módulo é complementar ao ``caderno_avaliacao`` existente: ele oferece uma
visão objetiva por categoria, com respostas padronizadas, sem substituir a
avaliação profissional nem o cumprimento das normas oficiais.
"""

# Respostas padronizadas exigidas no formulário de nova visita.
SST_OPTIONS = ("Conforme", "Não conforme", "Não aplicável")
SST_UNANSWERED = "Não avaliado"

# Observação individual por categoria (os 14 tópicos da seção 3 do formulário).
SST_OBSERVATION_LABEL = "Comentários / Observações"
SST_OBSERVATION_PLACEHOLDER = "Adicione observações ou não conformidades deste tópico..."

# Categorias organizadas de forma modular: basta adicionar uma nova entrada
# para incluir um bloco inteiro no formulário e nos relatórios.
SST_CATEGORIES = {
    "epi": {
        "title": "Equipamentos de Proteção Individual (EPIs)",
        "icon": "🦺",
        "items": [
            {"id": "epi_fornecimento", "label": "Fornecimento de EPIs adequados"},
            {"id": "epi_uso", "label": "Uso correto e obrigatório dos EPIs"},
            {"id": "epi_conservacao", "label": "Conservação e higienização dos EPIs"},
        ],
    },
    "epc": {
        "title": "Equipamentos de Proteção Coletiva (EPCs)",
        "icon": "🛡️",
        "items": [
            {"id": "epc_instalacao", "label": "Instalação e manutenção de EPCs"},
            {"id": "epc_adequacao", "label": "Adequação dos EPCs aos riscos da atividade"},
        ],
    },
    "sinalizacao": {
        "title": "Sinalização de segurança",
        "icon": "🚧",
        "items": [
            {"id": "sinalizacao_visibilidade", "label": "Sinalização visível e legível"},
            {"id": "sinalizacao_norma", "label": "Sinalização conforme as normas aplicáveis"},
        ],
    },
    "organizacao": {
        "title": "Organização e limpeza",
        "icon": "🧹",
        "items": [
            {"id": "organizacao_geral", "label": "Ambiente organizado e limpo"},
            {"id": "organizacao_residuos", "label": "Descarte adequado de resíduos"},
        ],
    },
    "circulacao": {
        "title": "Condições de circulação",
        "icon": "🚶",
        "items": [
            {"id": "circulacao_pisos", "label": "Pisos e passagens em boas condições"},
            {"id": "circulacao_obstaculos", "label": "Ausência de obstáculos nas rotas de fuga"},
        ],
    },
    "maquinas": {
        "title": "Máquinas e equipamentos",
        "icon": "⚙️",
        "items": [
            {"id": "maquinas_protecoes", "label": "Proteções mecânicas instaladas"},
            {"id": "maquinas_manual", "label": "Manual e procedimentos disponíveis"},
        ],
    },
    "eletrica": {
        "title": "Instalações elétricas",
        "icon": "⚡",
        "items": [
            {"id": "eletrica_quadros", "label": "Quadros elétricos identificados e fechados"},
            {"id": "eletrica_fios", "label": "Ausência de fios expostos ou emenda improvisada"},
        ],
    },
    "incendio": {
        "title": "Prevenção contra incêndios",
        "icon": "🧯",
        "items": [
            {"id": "incendio_extintores", "label": "Extintores válidos e acessíveis"},
            {"id": "incendio_rotas", "label": "Rotas de fuga desobstruídas e sinalizadas"},
        ],
    },
    "ergonomia": {
        "title": "Ergonomia",
        "icon": "🪑",
        "items": [
            {"id": "ergonomia_postura", "label": "Posturas e estações de trabalho adequadas"},
            {"id": "ergonomia_pausas", "label": "Pausas e rodízio de atividades definidos"},
        ],
    },
    "armazenamento": {
        "title": "Armazenamento de materiais",
        "icon": "📦",
        "items": [
            {"id": "armazenamento_empilhamento", "label": "Empilhamento seguro e estável"},
            {"id": "armazenamento_compatibilidade", "label": "Armazenamento compatível com os produtos"},
        ],
    },
    "ambiental": {
        "title": "Condições ambientais",
        "icon": "🌡️",
        "items": [
            {"id": "ambiental_ventilacao", "label": "Ventilação e iluminação adequadas"},
            {"id": "ambiental_ruido", "label": "Exposição a ruído controlada"},
        ],
    },
    "procedimentos": {
        "title": "Procedimentos de segurança",
        "icon": "📋",
        "items": [
            {"id": "procedimentos_escritos", "label": "Procedimentos escritos e disponíveis"},
            {"id": "procedimentos_are", "label": "Análise de riscos atualizada"},
        ],
    },
    "treinamentos": {
        "title": "Treinamentos",
        "icon": "🎓",
        "items": [
            {"id": "treinamentos_previstos", "label": "Treinamentos previstos realizados"},
            {"id": "treinamentos_registros", "label": "Registros de treinamento arquivados"},
        ],
    },
    "documentacao": {
        "title": "Documentação de segurança",
        "icon": "📁",
        "items": [
            {"id": "documentacao_pgrs", "label": "PGRS/PCMSO disponíveis e atualizados"},
            {"id": "documentacao_registros", "label": "Registros de exames e ocorrências mantidos"},
        ],
    },
}


def iter_sst_items():
    """Percorre todas as categorias/itens do checklist."""
    for category_key, category in SST_CATEGORIES.items():
        for item in category["items"]:
            yield category_key, item


def sst_widget_key(visit_id: str, category_key: str, item_id: str) -> str:
    """Chave estável e única para os widgets do Streamlit."""
    return f"sst_{visit_id}_{category_key}_{item_id}"


def build_sst_answers(visit_id: str, answers: dict) -> dict:
    """Normaliza as respostas coletadas no formulário para persistência."""
    normalized = {}
    for category_key, item in iter_sst_items():
        key = sst_widget_key(visit_id, category_key, item["id"])
        value = str(answers.get(key, SST_UNANSWERED) or SST_UNANSWERED).strip()
        normalized[item["id"]] = value if value in SST_OPTIONS else SST_UNANSWERED
    return normalized


def summarize_sst(answers: dict) -> dict:
    """Resume as respostas do checklist para tabelas e relatórios."""
    answers = answers if isinstance(answers, dict) else {}
    counts = {option: 0 for option in SST_OPTIONS}
    counts[SST_UNANSWERED] = 0
    non_conformities = []
    for category_key, item in iter_sst_items():
        value = str(answers.get(item["id"], SST_UNANSWERED) or SST_UNANSWERED)
        if value not in counts:
            value = SST_UNANSWERED
        counts[value] += 1
        if value == "Não conforme":
            non_conformities.append(
                {
                    "categoria": SST_CATEGORIES[category_key]["title"],
                    "item": item["label"],
                }
            )
    counts["total"] = sum(counts.values())
    counts["non_conformities"] = non_conformities
    return counts


def sst_observation_widget_key(visit_id: str, category_key: str) -> str:
    """Chave estável e única para o campo de observações de um tópico.

    O identificador usa o ID da visita e o ID da categoria — nunca a posição
    na lista — para não colidir entre visitas nem mudar se a ordem dos tópicos
    for alterada.
    """
    return f"sst_obs_{visit_id}_{category_key}"


def normalize_sst_observations(value) -> dict:
    """Normaliza observações por tópico com valores padrão seguros.

    Registros antigos não possuem ``sst_observations``; o resultado sempre traz
    as 14 chaves conhecidas, preenchidas com string vazia quando ausentes.
    """
    if not isinstance(value, dict):
        value = {}
    normalized = {}
    for category_key in SST_CATEGORIES:
        raw = value.get(category_key, "")
        if raw is None:
            raw = ""
        normalized[category_key] = str(raw).strip()
    return normalized


def get_sst_observations(visit: dict) -> dict:
    """Retorna as observações persistidas de uma visita (compatível com antigas)."""
    if not isinstance(visit, dict):
        return normalize_sst_observations(None)
    return normalize_sst_observations(visit.get("sst_observations"))


def build_sst_observations(visit_id: str, observations: dict) -> dict:
    """Converte os valores dos widgets em observações indexadas por tópico."""
    if not isinstance(observations, dict):
        observations = {}
    collected = {}
    for category_key in SST_CATEGORIES:
        key = sst_observation_widget_key(visit_id, category_key)
        raw = observations.get(key, "")
        collected[category_key] = "" if raw is None else str(raw).strip()
    return collected
