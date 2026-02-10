import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from pyzotero import zotero
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# 1. Inicializa o App
app = FastAPI()

# 2. Configura o CORS (Essencial para o GPT e testes no navegador)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Conexão com Zotero
zot = zotero.Zotero(os.getenv('ZOTERO_USER_ID'), 'user', os.getenv('ZOTERO_API_KEY'))

class SearchRequest(BaseModel):
    query: str = None
    limit: int = 10

@app.post("/buscar_artigos")
async def buscar_artigos(request: SearchRequest):
    try:
        # Busca no Zotero
        if request.query:
            items = zot.items(q=request.query)
        else:
            items = zot.top(limit=request.limit)
        
        lista = []
        for item in items:
            dados = item['data']
            # Captura os dados brutos, incluindo o DOI da Nature
            lista.append({
                "titulo": dados.get('title', 'Sem título'),
                "autor": dados.get('creators', [{}])[0].get('lastName', 'N/A'),
                "resumo": dados.get('abstractNote', 'Sem resumo'),
                "doi": dados.get('DOI', 'N/A')
            })
        return {"artigos": lista}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))