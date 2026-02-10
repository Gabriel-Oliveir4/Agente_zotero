# Definimos uma "Persona" ou "Instrução de Treinamento" que você pode alterar aqui
# Isso dita como o agente deve se comportar perante seus artigos
INSTRUCAO_IA = """
Você é o Assistente Sênior do BioAiLab. 
Sua especialidade é correlacionar dados de sensores industriais e biotecnologia.
Sempre priorize evidências quantitativas e mencione se o artigo é recente (pós-2024).
"""

@app.post("/analisar")
async def analisar(request: ResearchRequest):
    # O "treinamento" acontece aqui: unimos a instrução fixa com a dúvida do usuário
    contexto_zotero = buscar_artigos_zotero() # Sua função de busca
    
    prompt_completo = f"""
    {INSTRUCAO_IA}
    
    CONTEXTO DOS ARTIGOS:
    {contexto_zotero}
    
    PERGUNTA/HIPÓTESE:
    {request.hipotese}
    """
    
    # Chamada para o Groq com a lógica 'treinada'
    resposta = groq_client.chat.completions.create(
        messages=[{"role": "system", "content": prompt_completo}],
        model="llama-3.3-70b-versatile"
    )
    return {"analise": resposta.choices[0].message.content}