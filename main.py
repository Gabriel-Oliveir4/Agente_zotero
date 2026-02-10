import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from pyzotero import zotero
from fastapi.middleware.cors import CORSMiddleware

# Carrega chaves do .env (local) ou do Render (produção)
load_dotenv()

app = FastAPI()

# Configuração de CORS para o ChatGPT não ser bloqueado
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializa Zotero com suas credenciais
zot = zotero.Zotero(os.getenv('ZOTERO_USER_ID'), 'user', os.getenv('ZOTERO_API_KEY'))

class SearchRequest(BaseModel):
    query: str = None
    limit: int = 50  # Limite máximo sugerido para evitar timeouts
    start: int = 0   # Índice inicial para paginação

@app.post("/buscar_artigos")
async def buscar_artigos(request: SearchRequest):
    try:
        # Garante que o limite não ultrapasse 50 por chamada
        limit_efetivo = min(request.limit, 50)
        
        # Busca itens no Zotero
        if request.query:
            items = zot.items(q=request.query, limit=limit_efetivo, start=request.start)
        else:
            items = zot.top(limit=limit_efetivo, start=request.start)
        
        lista_final = []
        for item in items:
            dados = item['data']
            
            # Pula anexos (PDFs soltos) que não possuem metadados completos
            if dados.get('itemType') == 'attachment':
                continue

            # Extração segura de autor para evitar erro 'index out of range'
            creators = dados.get('creators', [])
            autor_nome = "Autor Desconhecido"
            if creators:
                # Tenta pegar o sobrenome ou o nome institucional se o sobrenome falhar
                autor_nome = creators[0].get('lastName') or creators[0].get('name') or "Desconhecido"

            lista_final.append({
                "titulo": dados.get('title', 'Sem título'),
                "autor": autor_nome,
                "resumo": dados.get('abstractNote', 'Sem resumo disponível'),
                "doi": dados.get('DOI', 'N/A'),
                "tipo": dados.get('itemType')
            })
            
        return {
            "artigos": lista_final,
            "proximo_start": request.start + len(items),
            "total_retornado": len(lista_final)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))