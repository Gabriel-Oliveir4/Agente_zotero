import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from pyzotero import zotero
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
app = FastAPI()

# Configuração de CORS para garantir que o GPT consiga acessar sem bloqueios
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializa apenas o Zotero
zot = zotero.Zotero(os.getenv('ZOTERO_USER_ID'), 'user', os.getenv('ZOTERO_API_KEY'))

class SearchRequest(BaseModel):
    query: str = None
    limit: int = 10

@app.post("/buscar_artigos")
async def buscar_artigos(request: SearchRequest):
    try:
        # Busca no Zotero (seja por termo ou os mais recentes)
        if request.query:
            items = zot.items(q=request.query)
        else:
            items = zot.top(limit=request.limit)
        
        lista_artigos = []
        for item in items:
            dados = item['data']
            # Enviamos os metadados brutos (como o DOI da Nature)
            lista_artigos.append({
                "titulo": dados.get('title', 'Sem título'),
                "autor": dados.get('creators', [{}])[0].get('lastName', 'N/A'),
                "resumo": dados.get('abstractNote', 'Sem resumo'),
                "doi": dados.get('DOI', 'N/A')
            })
            
        return {"artigos": lista_artigos}

    except Exception as e:
        # Se o erro 403 persistir, ele será capturado aqui
        raise HTTPException(status_code=500, detail=str(e))