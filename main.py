import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from pyzotero import zotero
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURAÇÃO DE GRUPO ---
# No Render, você deve criar a variável ZOTERO_GROUP_ID com o número do grupo
zot = zotero.Zotero(
    os.getenv('ZOTERO_GROUP_ID'), 
    'group', 
    os.getenv('ZOTERO_API_KEY')
)

class SearchRequest(BaseModel):
    query: str = None
    limit: int = 50
    start: int = 0

@app.post("/buscar_artigos")
async def buscar_artigos(request: SearchRequest):
    try:
        limit_efetivo = min(request.limit, 50)
        
        # Busca direta no topo do grupo (não precisa mais buscar ID de pasta)
        if request.query:
            items = zot.items(q=request.query, limit=limit_efetivo, start=request.start)
        else:
            items = zot.top(limit=limit_efetivo, start=request.start)
        
        lista_final = []
        for item in items:
            dados = item['data']
            
            # Filtro para ignorar anexos e PDFs soltos
            if dados.get('itemType') == 'attachment':
                continue

            creators = dados.get('creators', [])
            autor_nome = "Autor Desconhecido"
            if creators:
                autor_nome = creators[0].get('lastName') or creators[0].get('name') or "Desconhecido"

            lista_final.append({
                "titulo": dados.get('title', 'Sem título'),
                "autor": autor_nome,
                "resumo": dados.get('abstractNote', 'Sem resumo disponível'),
                "doi": dados.get('DOI', 'N/A')
            })
            
        return {
            "artigos": lista_final,
            "proximo_start": request.start + len(items),
            "origem": "Grupo AUFTEK"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))