import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from pyzotero import zotero
from groq import Groq

# 1. Carrega as variáveis de ambiente (.env no local, Config Vars no Render)
load_dotenv()

# 2. INICIALIZA O APP (O erro estava aqui: esta linha deve vir antes das rotas)
app = FastAPI()

# 3. Inicializa os clientes das APIs
zot = zotero.Zotero(os.getenv('ZOTERO_USER_ID'), 'user', os.getenv('ZOTERO_API_KEY'))
groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))

# Esta é a parte que você altera para "treinar" o comportamento do Agente
INSTRUCAO_SISTEMA = """
Você é um Assistente de Pesquisa Científica de alto nível.
Sua tarefa é analisar resumos técnicos do Zotero e validar hipóteses.
Seja sempre formal, técnico e aponte contradições se houver.
"""

class ResearchRequest(BaseModel):
    hipotese: str

# 4. Agora sim, definimos a rota usando o 'app' já criado
@app.post("/analisar")
async def analisar(request: ResearchRequest):
    try:
        # Busca os itens no Zotero
        items = zot.top(limit=10)
        
        contexto = ""
        for item in items:
            dados = item['data']
            titulo = dados.get('title', 'Sem título')
            resumo = dados.get('abstractNote', 'Sem resumo')
            contexto += f"TÍTULO: {titulo}\nRESUMO: {resumo}\n---\n"

        # Combina o "treinamento" com os dados e a pergunta
        prompt_final = f"{INSTRUCAO_SISTEMA}\n\nHIPÓTESE: {request.hipotese}\n\nCONTEXTO:\n{contexto}"
        
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt_final}],
            model="llama-3.3-70b-versatile",
        )
        
        return {"resposta": chat_completion.choices[0].message.content}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))