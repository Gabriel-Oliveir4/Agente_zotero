import os
import re
from typing import Optional, List, Dict, Any, Tuple

import requests
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from pyzotero import zotero

load_dotenv()

app = FastAPI(title="Zotero Bibliotecario API", version="1.1.0")

# =========================
# Zotero config (NÃO alterar env vars)
# =========================
ZOTERO_GROUP_ID = os.getenv("ZOTERO_GROUP_ID")
ZOTERO_API_KEY = os.getenv("ZOTERO_API_KEY")

if not ZOTERO_GROUP_ID or not ZOTERO_API_KEY:
    raise RuntimeError("Variáveis de ambiente ZOTERO_GROUP_ID e/ou ZOTERO_API_KEY não definidas.")

zot = zotero.Zotero(ZOTERO_GROUP_ID, "group", ZOTERO_API_KEY)

ZOTERO_BASE_URL = f"https://api.zotero.org/groups/{ZOTERO_GROUP_ID}"
ZOTERO_HEADERS = {"Zotero-API-Key": ZOTERO_API_KEY}

# =========================
# Auth simples (opcional, mas recomendado)
# =========================
# Se AGENT_API_KEY existir no Render, exige header X-AGENT-KEY nas rotas.
AGENT_API_KEY = os.getenv("AGENT_API_KEY")


def require_agent_key(x_agent_key: Optional[str]) -> None:
    if AGENT_API_KEY:
        if not x_agent_key or x_agent_key != AGENT_API_KEY:
            raise HTTPException(status_code=401, detail="Unauthorized (missing/invalid X-AGENT-KEY)")


# =========================
# Models
# =========================
class SearchRequest(BaseModel):
    query: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=50)
    start: int = Field(default=0, ge=0)


class EvidenceRequest(BaseModel):
    query: str = Field(..., min_length=2)
    max_snippets: int = Field(default=6, ge=1, le=20)
    context_chars: int = Field(default=220, ge=80, le=1000)


# =========================
# Helpers
# =========================
def first_author_name(item_data: Dict[str, Any]) -> str:
    creators = item_data.get("creators", []) or []
    if not creators:
        return "Autor Desconhecido"
    c0 = creators[0]
    return c0.get("lastName") or c0.get("name") or "Desconhecido"


def extract_year(item_data: Dict[str, Any]) -> str:
    date_str = item_data.get("date") or ""
    m = re.search(r"\b(19\d{2}|20\d{2})\b", date_str)
    return m.group(1) if m else "N/A"


def zotero_get_json(url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    try:
        r = requests.get(url, headers=ZOTERO_HEADERS, params=params, timeout=25)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        raise HTTPException(status_code=r.status_code, detail=f"Zotero HTTP error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")


def get_parent_item(item_key: str) -> Optional[Dict[str, Any]]:
    # pyzotero já resolve /items/{key} e retorna um dict no formato padrão
    try:
        item = zot.item(item_key)
        return item
    except Exception:
        return None


def list_children(parent_key: str, limit: int = 200) -> List[Dict[str, Any]]:
    url = f"{ZOTERO_BASE_URL}/items/{parent_key}/children"
    data = zotero_get_json(url, params={"format": "json", "limit": limit})
    return data or []


def get_fulltext(attachment_key: str) -> Optional[str]:
    # Fulltext indexado do Zotero (não baixa PDF)
    url = f"{ZOTERO_BASE_URL}/items/{attachment_key}/fulltext"
    data = zotero_get_json(url, params={"format": "json"})
    if not data:
        return None
    content = data.get("content")
    if not content or not isinstance(content, str):
        return None
    return content


def build_snippets(text: str, query: str, max_snippets: int, context_chars: int) -> List[Dict[str, Any]]:
    # Heurística barata: termos >= 3 chars, procura ocorrências e retorna janelas de contexto.
    q = query.strip().lower()
    terms = [t for t in re.split(r"\s+", q) if len(t) >= 3]
    if not terms:
        terms = [q]

    lower = text.lower()
    hits: List[Tuple[int, int, str]] = []

    for term in terms:
        start = 0
        while True:
            idx = lower.find(term, start)
            if idx == -1:
                break
            hits.append((idx, idx + len(term), term))
            start = idx + len(term)
            if len(hits) > 250:  # limite de segurança
                break
        if len(hits) > 250:
            break

    hits.sort(key=lambda x: x[0])

    snippets = []
    used_windows = set()

    for (a, b, term) in hits:
        left = max(0, a - context_chars)
        right = min(len(text), b + context_chars)
        window_key = (left, right)
        if window_key in used_windows:
            continue
        used_windows.add(window_key)

        excerpt = text[left:right].replace("\n", " ").strip()
        snippets.append({"termo": term, "inicio": left, "fim": right, "trecho": excerpt})
        if len(snippets) >= max_snippets:
            break

    return snippets


def normalize_article_ref(item: Dict[str, Any]) -> Dict[str, str]:
    data = (item or {}).get("data", {}) or {}
    return {
        "itemKey": (item or {}).get("key") or "N/A",
        "titulo": data.get("title", "Sem título"),
        "autor": first_author_name(data),
        "ano": extract_year(data),
        "doi": data.get("DOI", "N/A"),
        "url": data.get("url", "N/A"),
        "tipo": data.get("itemType", "N/A"),
    }


# =========================
# Endpoints
# =========================
@app.get("/health")
async def health():
    # Ping simples pra você testar deploy rápido
    return {"status": "ok"}


@app.post("/buscar_artigos")
async def buscar_artigos(request: SearchRequest, x_agent_key: Optional[str] = Header(default=None)):
    require_agent_key(x_agent_key)

    try:
        limit_efetivo = min(request.limit, 50)

        if request.query and request.query.strip():
            items = zot.items(
                q=request.query.strip(),
                qmode="everything",
                limit=limit_efetivo,
                start=request.start,
            )
        else:
            items = zot.top(limit=limit_efetivo, start=request.start)

        lista_final = []
        bruto = 0
        filtrado = 0

        for item in items:
            bruto += 1
            data = item.get("data", {}) or {}

            # Ignora anexos (PDFs/attachments)
            if data.get("itemType") == "attachment":
                continue

            filtrado += 1
            lista_final.append(normalize_article_ref(item))

        return {
            "artigos": lista_final,
            "paginacao": {
                "start_recebido": request.start,
                "limit_efetivo": limit_efetivo,
                "itens_brutos_recebidos": bruto,
                "itens_filtrados_retornados": filtrado,
                # 'start' do Zotero avança em itens brutos (inclui attachments), por isso usamos bruto.
                "proximo_start": request.start + bruto,
            },
            "origem": "Grupo AUFTEK",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/itens/{item_key}/evidencias")
async def evidencias(item_key: str, req: EvidenceRequest, x_agent_key: Optional[str] = Header(default=None)):
    require_agent_key(x_agent_key)

    # Metadados do artigo pai (pra citação)
    parent_item = get_parent_item(item_key)
    if not parent_item:
        raise HTTPException(status_code=404, detail="Item não encontrado no Zotero.")

    artigo_ref = normalize_article_ref(parent_item)

    children = list_children(item_key, limit=200)
    attachments = [
        ch for ch in children
        if (ch.get("data", {}) or {}).get("itemType") == "attachment"
    ]

    resultados = []
    anexos_com_fulltext = 0

    for att in attachments:
        att_key = att.get("key")
        if not att_key:
            continue

        content = get_fulltext(att_key)
        if not content:
            continue

        anexos_com_fulltext += 1

        snippets = build_snippets(
            text=content,
            query=req.query,
            max_snippets=req.max_snippets,
            context_chars=req.context_chars,
        )

        if snippets:
            resultados.append(
                {
                    "attachmentKey": att_key,
                    "filename": (att.get("data", {}) or {}).get("filename", "N/A"),
                    "snippets": snippets,
                }
            )

    obs = (
        "Se não aparecer evidência, pode ser que o Zotero ainda não tenha fulltext indexado para os PDFs "
        "ou que o termo não ocorra no texto indexado."
    )

    return {
        "artigo": artigo_ref,          # <-- facilita a vida do agente para citar
        "itemKey": item_key,
        "query": req.query,
        "evidencias": resultados,
        "cobertura": {
            "anexos_total": len(attachments),
            "anexos_com_fulltext": anexos_com_fulltext,
            "anexos_com_hits": len(resultados),
        },
        "observacao": obs,
    }
