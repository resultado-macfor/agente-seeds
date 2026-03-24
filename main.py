import os
from anthropic import Anthropic
import streamlit as st
import io
import google.generativeai as genai
from PIL import Image
import datetime
from openai import OpenAI
from pymongo import MongoClient
from bson import ObjectId
import json
import hashlib
from google.genai import types
import PyPDF2
from pptx import Presentation
import docx
import openai
from typing import List, Dict, Tuple
import hashlib
import pandas as pd
import re
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Text
import requests
from google.genai import types
import PyPDF2
from pptx import Presentation
import docx
import openai
from typing import List, Dict, Tuple
import hashlib
import pandas as pd
import re
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Text
import requests
import pdfplumber
from pathlib import Path
import uuid

# Configuração inicial
st.set_page_config(
    layout="wide",
    page_title="Agente Seeds",
    page_icon="🤖"
)

# --- CARREGAR VARIÁVEIS DO AMBIENTE ---
perp_api_key = os.getenv("PERP_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
gemini_api_key = os.getenv("GEM_API_KEY")
mongo_uri = os.getenv("MONGO_URI")
senha_admin = os.getenv("SENHA_ADMIN", "admin123")

# --- CONFIGURAÇÃO DOS MODELOS ---
if anthropic_api_key:
    anthropic_client = Anthropic(api_key=anthropic_api_key)
else:
    anthropic_client = None

if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    modelo_vision = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.0})
    modelo_texto = genai.GenerativeModel("gemini-2.5-flash")
else:
    modelo_vision = None
    modelo_texto = None

if openai_api_key:
    openai_client = OpenAI(api_key=openai_api_key)
else:
    openai_client = None

# --- Conexão MongoDB ---
if mongo_uri:
    client = MongoClient(mongo_uri)
    db = client['agentes_personalizados']
    collection_agentes = db['agentes']
    collection_conversas = db['conversas']
    collection_usuarios = db['usuarios']
else:
    st.error("MONGO_URI não encontrada")
    st.stop()

# --- Sistema de Autenticação Único (Apenas Admin) ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

# Senha admin do ambiente
ADMIN_PASSWORD_HASH = make_hashes(senha_admin)

def verificar_login_admin(senha):
    """Verifica apenas a senha do admin"""
    return check_hashes(senha, ADMIN_PASSWORD_HASH)

def login():
    st.title("🔒 Agente Seeds - Login Administrativo")
    
    with st.form("login_form"):
        st.markdown("### Acesso Restrito - Administrador")
        password = st.text_input("Senha de Administrador", type="password")
        submit_button = st.form_submit_button("Entrar")
        
        if submit_button:
            if password and verificar_login_admin(password):
                st.session_state.logged_in = True
                st.session_state.user = {
                    "email": "admin@seeds.com",
                    "nome": "Administrador",
                    "squad": "admin",
                    "_id": "admin"
                }
                st.success("Login realizado com sucesso!")
                st.rerun()
            else:
                st.error("Senha incorreta")

# Verificar login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login()
    st.stop()

# --- Funções auxiliares ---
def get_current_user():
    return st.session_state.get('user', {})

def get_current_squad():
    return "admin"

def check_admin_password():
    return True

# --- FUNÇÕES CRUD PARA AGENTES ---
def criar_agente(nome, system_prompt, base_conhecimento, comments, planejamento, categoria, squad_permitido, agente_mae_id=None, herdar_elementos=None):
    agente = {
        "nome": nome,
        "system_prompt": system_prompt,
        "base_conhecimento": base_conhecimento,
        "comments": comments,
        "planejamento": planejamento,
        "categoria": categoria,
        "squad_permitido": squad_permitido,
        "agente_mae_id": agente_mae_id,
        "herdar_elementos": herdar_elementos or [],
        "data_criacao": datetime.datetime.now(),
        "ativo": True,
        "criado_por": get_current_user().get('email', 'admin'),
        "criado_por_squad": "admin"
    }
    result = collection_agentes.insert_one(agente)
    return result.inserted_id

def listar_agentes():
    return list(collection_agentes.find({"ativo": True}).sort("data_criacao", -1))

def listar_agentes_para_heranca(agente_atual_id=None):
    query = {"ativo": True}
    if agente_atual_id:
        if isinstance(agente_atual_id, str):
            agente_atual_id = ObjectId(agente_atual_id)
        query["_id"] = {"$ne": agente_atual_id}
    return list(collection_agentes.find(query).sort("data_criacao", -1))

def obter_agente(agente_id):
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    return collection_agentes.find_one({"_id": agente_id, "ativo": True})

def atualizar_agente(agente_id, nome, system_prompt, base_conhecimento, comments, planejamento, categoria, squad_permitido, agente_mae_id=None, herdar_elementos=None):
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    return collection_agentes.update_one(
        {"_id": agente_id},
        {
            "$set": {
                "nome": nome,
                "system_prompt": system_prompt,
                "base_conhecimento": base_conhecimento,
                "comments": comments,
                "planejamento": planejamento,
                "categoria": categoria,
                "squad_permitido": squad_permitido,
                "agente_mae_id": agente_mae_id,
                "herdar_elementos": herdar_elementos or [],
                "data_atualizacao": datetime.datetime.now()
            }
        }
    )

def desativar_agente(agente_id):
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    return collection_agentes.update_one(
        {"_id": agente_id},
        {"$set": {"ativo": False, "data_desativacao": datetime.datetime.now()}}
    )

def obter_agente_com_heranca(agente_id):
    agente = obter_agente(agente_id)
    if not agente or not agente.get('agente_mae_id'):
        return agente
    
    agente_mae = obter_agente(agente['agente_mae_id'])
    if not agente_mae:
        return agente
    
    elementos_herdar = agente.get('herdar_elementos', [])
    agente_completo = agente.copy()
    
    for elemento in elementos_herdar:
        if elemento == 'system_prompt' and not agente_completo.get('system_prompt'):
            agente_completo['system_prompt'] = agente_mae.get('system_prompt', '')
        elif elemento == 'base_conhecimento' and not agente_completo.get('base_conhecimento'):
            agente_completo['base_conhecimento'] = agente_mae.get('base_conhecimento', '')
        elif elemento == 'comments' and not agente_completo.get('comments'):
            agente_completo['comments'] = agente_mae.get('comments', '')
        elif elemento == 'planejamento' and not agente_completo.get('planejamento'):
            agente_completo['planejamento'] = agente_mae.get('planejamento', '')
    
    return agente_completo

def salvar_conversa(agente_id, mensagens, segmentos_utilizados=None):
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    conversa = {
        "agente_id": agente_id,
        "mensagens": mensagens,
        "segmentos_utilizados": segmentos_utilizados,
        "data_criacao": datetime.datetime.now()
    }
    return collection_conversas.insert_one(conversa)

def obter_conversas(agente_id, limite=10):
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    return list(collection_conversas.find(
        {"agente_id": agente_id}
    ).sort("data_criacao", -1).limit(limite))

def construir_contexto(agente, segmentos_selecionados, historico_mensagens=None):
    contexto = ""
    
    if "system_prompt" in segmentos_selecionados and agente.get('system_prompt'):
        contexto += f"### INSTRUÇÕES DO SISTEMA ###\n{agente['system_prompt']}\n\n"
    
    if "base_conhecimento" in segmentos_selecionados and agente.get('base_conhecimento'):
        contexto += f"### BASE DE CONHECIMENTO ###\n{agente['base_conhecimento']}\n\n"
    
    if "comments" in segmentos_selecionados and agente.get('comments'):
        contexto += f"### Diário DO CLIENTE ###\n{agente['comments']}\n\n"
    
    if "planejamento" in segmentos_selecionados and agente.get('planejamento'):
        contexto += f"### PLANEJAMENTO ###\n{agente['planejamento']}\n\n"
    
    if historico_mensagens:
        contexto += "### HISTÓRICO DA CONVERSA ###\n"
        for msg in historico_mensagens:
            contexto += f"{msg['role']}: {msg['content']}\n"
        contexto += "\n"
    
    contexto += "### RESPOSTA ATUAL ###\nassistant:"
    
    return contexto

def gerar_resposta_modelo(prompt: str, modelo_escolhido: str = "Gemini", contexto_agente: str = None) -> str:
    try:
        if modelo_escolhido == "Gemini" and modelo_texto:
            if contexto_agente:
                prompt_completo = f"{contexto_agente}\n\n{prompt}"
            else:
                prompt_completo = prompt
            
            resposta = modelo_texto.generate_content(prompt_completo)
            return resposta.text
            
        elif modelo_escolhido == "Claude" and anthropic_client:
            if contexto_agente:
                system_prompt = contexto_agente
            else:
                system_prompt = "Você é um assistente útil."
            
            message = anthropic_client.messages.create(
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
                model="claude-haiku-4-5-20251001",
                system=system_prompt
            )
            return message.content[0].text
            
        elif modelo_escolhido == "OpenAI" and openai_client:
            messages = []
            if contexto_agente:
                messages.append({"role": "system", "content": contexto_agente})
            messages.append({"role": "user", "content": prompt})
            
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=4000,
                temperature=0.0
            )
            return response.choices[0].message.content
            
        else:
            return f"❌ Modelo {modelo_escolhido} não disponível"
            
    except Exception as e:
        return f"❌ Erro ao gerar resposta: {str(e)}"

# --- FUNÇÕES DE BUSCA WEB ---
def realizar_busca_web_com_fontes(termos_busca: str, contexto_agente: str = None) -> str:
    if not perp_api_key:
        return "❌ API do Perplexity não configurada"
    
    try:
        headers = {
            "Authorization": f"Bearer {perp_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": "Você é um assistente de pesquisa que fornece informações com fontes."
                },
                {
                    "role": "user", 
                    "content": f"Pesquise informações sobre: {termos_busca}\n\nINCLUA AS FONTES no formato: **Fonte: [Nome] ([link])**"
                }
            ],
            "max_tokens": 4000,
            "temperature": 0.0
        }
        
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return f"❌ Erro na busca: {response.status_code}"
                
    except Exception as e:
        return f"❌ Erro: {str(e)}"

# --- FUNÇÕES DE EXTRAÇÃO DE TEXTO ---
def extract_text_from_pdf_com_slides(arquivo_pdf):
    try:
        pdf_reader = PyPDF2.PdfReader(arquivo_pdf)
        slides_info = []
        
        for pagina_num, pagina in enumerate(pdf_reader.pages):
            texto = pagina.extract_text()
            slides_info.append({
                'numero': pagina_num + 1,
                'conteudo': texto,
                'tipo': 'página'
            })
        
        texto_completo = "\n\n".join([f"--- PÁGINA {s['numero']} ---\n{s['conteudo']}" for s in slides_info])
        return texto_completo, slides_info
        
    except Exception as e:
        return f"Erro: {str(e)}", []

def extract_text_from_pptx_com_slides(arquivo_pptx):
    try:
        prs = Presentation(io.BytesIO(arquivo_pptx.read()))
        slides_info = []
        
        for slide_num, slide in enumerate(prs.slides):
            texto_slide = f"--- SLIDE {slide_num + 1} ---\n"
            
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    texto_slide += shape.text + "\n"
            
            slides_info.append({
                'numero': slide_num + 1,
                'conteudo': texto_slide,
                'tipo': 'slide'
            })
        
        texto_completo = "\n\n".join([s['conteudo'] for s in slides_info])
        return texto_completo, slides_info
        
    except Exception as e:
        return f"Erro: {str(e)}", []

def extrair_texto_arquivo(arquivo):
    try:
        if arquivo.type == "text/plain":
            return str(arquivo.read(), "utf-8")
        elif arquivo.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = docx.Document(io.BytesIO(arquivo.read()))
            texto = ""
            for para in doc.paragraphs:
                texto += para.text + "\n"
            return texto
        else:
            return f"Tipo não suportado"
    except Exception as e:
        return f"Erro: {str(e)}"

def extrair_score(texto_analise):
    padrao = r'SCORE.*?\[(\d+)(?:/10)?\]'
    correspondencias = re.findall(padrao, texto_analise, re.IGNORECASE)
    if correspondencias:
        return int(correspondencias[0])
    return 5

def criar_analisadores_texto(contexto_agente, contexto_global):
    analisadores = {
        'ortografia': {
            'nome': '🔤 Especialista em Ortografia',
            'prompt': f"""
{contexto_global}

## FUNÇÃO: ESPECIALISTA EM ORTOGRAFIA E GRAMÁTICA

### FORMATO DE RESPOSTA:

## 🔤 RELATÓRIO ORTOGRÁFICO

### ✅ ACERTOS
### ❌ ERROS IDENTIFICADOS
### 📊 SCORE ORTOGRÁFICO: [X/10]
"""
        },
        'lexico': {
            'nome': '📚 Especialista em Léxico',
            'prompt': f"""
{contexto_agente}
{contexto_global}

## FUNÇÃO: ESPECIALISTA EM LÉXICO

### FORMATO DE RESPOSTA:

## 📚 RELATÓRIO LEXICAL
### ✅ VOCABULÁRIO ADEQUADO
### ⚠️ ASPECTOS A MELHORAR
### 📊 SCORE LEXICAL: [X/10]
"""
        },
        'branding': {
            'nome': '🎨 Especialista em Branding',
            'prompt': f"""
{contexto_agente}
{contexto_global}

## FUNÇÃO: ESPECIALISTA EM BRANDING

### FORMATO DE RESPOSTA:

## 🎨 RELATÓRIO DE BRANDING
### ✅ ALINHAMENTOS
### ❌ DESVIOS IDENTIFICADOS
### 📊 SCORE BRANDING: [X/10]
"""
        }
    }
    return analisadores

def executar_analise_texto_especializada(texto, nome_arquivo, analisadores):
    resultados = {}
    
    for area, config in analisadores.items():
        with st.spinner(f"Executando {config['nome']}..."):
            try:
                prompt_completo = f"""
{config['prompt']}

###BEGIN TEXTO###
**Arquivo:** {nome_arquivo}
**Conteúdo:**
{texto[:8000]}
###END TEXTO###
"""
                resposta = modelo_texto.generate_content(prompt_completo)
                resultados[area] = {
                    'nome': config['nome'],
                    'analise': resposta.text,
                    'score': extrair_score(resposta.text)
                }
            except Exception as e:
                resultados[area] = {
                    'nome': config['nome'],
                    'analise': f"❌ Erro: {str(e)}",
                    'score': 0
                }
    
    return resultados

def gerar_relatorio_texto_consolidado(resultados_especialistas, nome_arquivo):
    relatorio = f"""
# 📊 RELATÓRIO CONSOLIDADO

**Documento:** {nome_arquivo}
**Data:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}

## 🎖️ SCORES
"""
    for area, resultado in resultados_especialistas.items():
        emoji = "✅" if resultado['score'] >= 8 else "⚠️" if resultado['score'] >= 6 else "❌"
        relatorio += f"- {emoji} **{resultado['nome']}:** {resultado['score']}/10\n"
    
    relatorio += "\n## 📋 ANÁLISES\n"
    for area, resultado in resultados_especialistas.items():
        relatorio += f"\n### {resultado['nome']}\n{resultado['analise']}\n---\n"
    
    return relatorio

def revisar_texto_ortografia(texto, agente, segmentos_selecionados, revisao_estilo=True, manter_estrutura=True, explicar_alteracoes=True, modelo_escolhido="Gemini"):
    contexto_agente = ""
    if "system_prompt" in segmentos_selecionados and agente.get('system_prompt'):
        contexto_agente += f"DIRETRIZES:\n{agente['system_prompt']}\n\n"
    
    prompt = f"""
{contexto_agente}

TEXTO PARA REVISÃO:
{texto}

REALIZE REVISÃO ORTOGRÁFICA E GRAMATICAL.

FORMATO:
## 📋 TEXTO REVISADO
## 🔍 PRINCIPAIS ALTERAÇÕES
## 📊 RESUMO
"""
    
    try:
        return gerar_resposta_modelo(prompt, modelo_escolhido)
    except Exception as e:
        return f"❌ Erro: {str(e)}"

def gerar_relatorio_texto_imagem_consolidado(resultados):
    relatorio = f"""
# 📝 RELATÓRIO DE VALIDAÇÃO DE TEXTO EM IMAGEM

**Data:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}
**Total:** {len(resultados)}

## 📋 ANÁLISE INDIVIDUAL
"""
    for r in resultados:
        relatorio += f"\n{r['analise']}\n"
    
    relatorio += "\n## 📌 RESUMO FINAL\n"
    relatorio += "Arte\tErros encontrados?\tObservações\n"
    relatorio += "---\t---\t---\n"
    for r in resultados:
        status_text = {"Correto": "❌ Não", "Ajustes sugeridos": "⚠️ Sugestões", "Com erros": "✅ Sim"}.get(r['status'], "❓")
        relatorio += f"Arte {r['indice']}\t{status_text}\t{r['status']}\n"
    
    return relatorio

def criar_analisadores_imagem(contexto_agente, contexto_global):
    return {
        'composicao_visual': {
            'nome': '🎨 Composição Visual',
            'prompt': f"""
{contexto_agente}
{contexto_global}

## RELATÓRIO DE COMPOSIÇÃO VISUAL
### ✅ PONTOS FORTES
### ⚠️ PROBLEMAS
### 📊 SCORE: [X/10]
"""
        },
        'cores_branding': {
            'nome': '🌈 Cores e Branding',
            'prompt': f"""
{contexto_agente}
{contexto_global}

## RELATÓRIO DE CORES
### ✅ CORES ALINHADAS
### ❌ PROBLEMAS
### 📊 SCORE: [X/10]
"""
        }
    }

def executar_analise_imagem_especializada(uploaded_image, nome_imagem, analisadores):
    resultados = {}
    for area, config in analisadores.items():
        with st.spinner(f"Analisando {config['nome']}..."):
            try:
                response = modelo_vision.generate_content([
                    config['prompt'],
                    {"mime_type": "image/jpeg", "data": uploaded_image.getvalue()}
                ])
                resultados[area] = {
                    'nome': config['nome'],
                    'analise': response.text,
                    'score': extrair_score(response.text)
                }
            except Exception as e:
                resultados[area] = {
                    'nome': config['nome'],
                    'analise': f"❌ Erro: {str(e)}",
                    'score': 0
                }
    return resultados

def gerar_relatorio_imagem_consolidado(resultados, nome_imagem, dimensoes):
    relatorio = f"""
# 🖼️ RELATÓRIO DE IMAGEM

**Arquivo:** {nome_imagem}
**Dimensões:** {dimensoes}
**Data:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}

## 🎖️ SCORES
"""
    for area, r in resultados.items():
        emoji = "✅" if r['score'] >= 8 else "⚠️" if r['score'] >= 6 else "❌"
        relatorio += f"- {emoji} **{r['nome']}:** {r['score']}/10\n"
    
    relatorio += "\n## 📋 ANÁLISES\n"
    for area, r in resultados.items():
        relatorio += f"\n### {r['nome']}\n{r['analise']}\n---\n"
    
    return relatorio

def criar_analisadores_video(contexto_agente, contexto_global, contexto_video_especifico):
    return {
        'narrativa_estrutura': {
            'nome': '📖 Narrativa',
            'prompt': f"""
{contexto_agente}
{contexto_global}
{contexto_video_especifico}

## RELATÓRIO DE NARRATIVA
### ✅ PONTOS FORTES
### ⚠️ PROBLEMAS
### 📊 SCORE: [X/10]
"""
        },
        'qualidade_audio': {
            'nome': '🔊 Qualidade de Áudio',
            'prompt': f"""
{contexto_agente}
{contexto_global}
{contexto_video_especifico}

## RELATÓRIO DE ÁUDIO
### ✅ ACERTOS
### ❌ PROBLEMAS
### 📊 SCORE: [X/10]
"""
        }
    }

def executar_analise_video_especializada(uploaded_video, nome_video, analisadores):
    resultados = {}
    for area, config in analisadores.items():
        with st.spinner(f"Analisando {config['nome']}..."):
            try:
                video_bytes = uploaded_video.getvalue()
                response = modelo_vision.generate_content([
                    config['prompt'],
                    {"mime_type": uploaded_video.type, "data": video_bytes}
                ])
                resultados[area] = {
                    'nome': config['nome'],
                    'analise': response.text,
                    'score': extrair_score(response.text)
                }
            except Exception as e:
                resultados[area] = {
                    'nome': config['nome'],
                    'analise': f"❌ Erro: {str(e)}",
                    'score': 0
                }
    return resultados

def gerar_relatorio_video_consolidado(resultados, nome_video, tipo_video):
    relatorio = f"""
# 🎬 RELATÓRIO DE VÍDEO

**Arquivo:** {nome_video}
**Formato:** {tipo_video}
**Data:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}

## 🎖️ SCORES
"""
    for area, r in resultados.items():
        emoji = "✅" if r['score'] >= 8 else "⚠️" if r['score'] >= 6 else "❌"
        relatorio += f"- {emoji} **{r['nome']}:** {r['score']}/10\n"
    
    relatorio += "\n## 📋 ANÁLISES\n"
    for area, r in resultados.items():
        relatorio += f"\n### {r['nome']}\n{r['analise']}\n---\n"
    
    return relatorio

def extrair_comentarios_analise(texto_analise):
    comentarios = []
    padroes = [r'❌\s*(.*?)(?=\n|$)', r'⚠️\s*(.*?)(?=\n|$)', r'PROBLEMAS.*?\n(.*?)(?=###|\n\n|$)']
    for padrao in padroes:
        matches = re.findall(padrao, texto_analise, re.IGNORECASE | re.DOTALL)
        for match in matches:
            comentario = match.strip() if isinstance(match, str) else match[0].strip()
            if comentario and len(comentario) > 10:
                comentarios.append(comentario)
    return comentarios[:10]

def adicionar_comentarios_pdf(arquivo_pdf_original, comentarios, nome_documento):
    try:
        reader = PdfReader(io.BytesIO(arquivo_pdf_original.getvalue()))
        writer = PdfWriter()
        
        for page in reader.pages:
            writer.add_page(page)
        
        for i, comentario in enumerate(comentarios[:5]):
            y_pos = 750 - (i * 100)
            annotation = Text(
                text=f"📝 Comentário {i+1}: {comentario[:200]}...",
                rect=(50, y_pos, 400, y_pos + 20),
                open=False
            )
            writer.add_annotation(page_number=0, annotation=annotation)
        
        pdf_com_comentarios = io.BytesIO()
        writer.write(pdf_com_comentarios)
        pdf_com_comentarios.seek(0)
        return pdf_com_comentarios
    except Exception as e:
        st.error(f"Erro: {str(e)}")
        return None

def criar_relatorio_comentarios(comentarios, nome_documento, contexto_analise):
    relatorio = f"# 📋 RELATÓRIO DE COMENTÁRIOS - {nome_documento}\n\n"
    for i, comentario in enumerate(comentarios, 1):
        relatorio += f"### 🔍 Comentário {i}\n{comentario}\n\n"
    return relatorio

def gerar_conteudo_modelo(prompt, modelo_escolhido, contexto_agente=None):
    return gerar_resposta_modelo(prompt, modelo_escolhido, contexto_agente)

def transcrever_audio_video(arquivo, tipo):
    return f"Transcrição do {tipo} {arquivo.name}"

def gerar_resposta_agente(pergunta, historico, agente_monitoramento, modelo, contexto_adicional):
    system_prompt = agente_monitoramento.get('base_conhecimento', "Especialista que fala como gente")
    if contexto_adicional:
        system_prompt += f"\n\nCONTEXTO: {contexto_adicional}"
    
    prompt = f"{system_prompt}\n\nPERGUNTA: {pergunta}\n\nResponda de forma breve e direta."
    return gerar_resposta_modelo(prompt, modelo)

# --- DICIONÁRIO DE PRODUTOS ---
PRODUCT_DESCRIPTIONS = {
    "megafol": "Bioativador natural que potencializa o metabolismo da planta",
    "verdatis": "Inseticida com tecnologia PLINAZOLIN",
    "fortenza": "Tratamento de sementes inseticida",
    "miravis duo": "Fungicida para controle de manchas foliares"
}

def extract_product_info(content):
    content_lower = content.lower()
    for product in PRODUCT_DESCRIPTIONS.keys():
        if product in content_lower:
            parts = content_lower.split('-')
            culture = parts[1].strip() if len(parts) >= 2 else ""
            action = parts[2].strip() if len(parts) >= 3 else ""
            return product, culture, action
    return None, None, None

def generate_briefing(content, product_name, culture, action, data_input, formato_principal):
    meses = {1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril", 5: "maio", 6: "junho",
             7: "julho", 8: "agosto", 9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"}
    mes = meses[data_input.month]
    descricao = PRODUCT_DESCRIPTIONS.get(product_name, "Produto SYN")
    
    return f"""
# BRIEFING - {product_name.upper()}

**Produto:** {product_name}
**Cultura:** {culture}
**Ação:** {action}
**Data:** {mes}/{data_input.year}
**Formato:** {formato_principal}

## DESCRIÇÃO
{descricao}

## CONTEÚDO
{content}
"""

def is_syn_agent(agent_name):
    return agent_name and "SYN" in agent_name.upper()

def selecionar_agente_interface():
    st.title("Agente Seeds")
    agentes = listar_agentes()
    
    if not agentes:
        st.error("Nenhum agente disponível")
        return None
    
    opcoes = []
    for agente in agentes:
        agente_completo = obter_agente_com_heranca(agente['_id'])
        if agente_completo:
            desc = f"{agente['nome']} - {agente.get('categoria', 'Social')}"
            if agente.get('agente_mae_id'):
                desc += " 🔗"
            opcoes.append((desc, agente_completo))
    
    if opcoes:
        selecionado = st.selectbox("Selecione um agente:", [op[0] for op in opcoes])
        for desc, agente in opcoes:
            if desc == selecionado and st.button("✅ Confirmar"):
                st.session_state.agente_selecionado = agente
                st.session_state.messages = []
                st.session_state.segmentos_selecionados = ["system_prompt", "base_conhecimento", "comments", "planejamento"]
                st.rerun()
        return next((agente for desc, agente in opcoes if desc == selecionado), None)
    return None

# --- INICIALIZAÇÃO DE SESSION STATE ---
if 'analise_especializada_texto' not in st.session_state:
    st.session_state.analise_especializada_texto = True
if 'analise_especializada_imagem' not in st.session_state:
    st.session_state.analise_especializada_imagem = True
if 'analise_especializada_video' not in st.session_state:
    st.session_state.analise_especializada_video = True
if 'analisadores_selecionados_texto' not in st.session_state:
    st.session_state.analisadores_selecionados_texto = ['ortografia', 'lexico', 'branding']
if 'analisadores_selecionados_imagem' not in st.session_state:
    st.session_state.analisadores_selecionados_imagem = ['composicao_visual', 'cores_branding']
if 'analisadores_selecionados_video' not in st.session_state:
    st.session_state.analisadores_selecionados_video = ['narrativa_estrutura', 'qualidade_audio']
if 'validacao_triggered' not in st.session_state:
    st.session_state.validacao_triggered = False
if 'todos_textos' not in st.session_state:
    st.session_state.todos_textos = []
if 'resultados_analise_imagem' not in st.session_state:
    st.session_state.resultados_analise_imagem = []
if 'resultados_analise_video' not in st.session_state:
    st.session_state.resultados_analise_video = []
if 'conteudo_gerado' not in st.session_state:
    st.session_state.conteudo_gerado = None
if 'calendario_gerado' not in st.session_state:
    st.session_state.calendario_gerado = None
if 'agente_selecionado' not in st.session_state:
    st.session_state.agente_selecionado = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'segmentos_selecionados' not in st.session_state:
    st.session_state.segmentos_selecionados = []
if 'messages_monitoramento' not in st.session_state:
    st.session_state.messages_monitoramento = []

# --- VERIFICAÇÃO DE AGENTE SELECIONADO ---
if not st.session_state.agente_selecionado:
    selecionar_agente_interface()
    st.stop()

# --- INTERFACE PRINCIPAL ---
agente_selecionado = st.session_state.agente_selecionado

# Sidebar
st.sidebar.title(f"🤖 Bem-vindo, {get_current_user().get('nome', 'Admin')}!")
st.sidebar.info(f"**Agente:** {agente_selecionado['nome']}")

if st.sidebar.button("🚪 Sair", key="logout_btn"):
    for key in ["logged_in", "user", "agente_selecionado", "messages"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

if st.sidebar.button("🔄 Trocar Agente", key="trocar_agente_global"):
    st.session_state.agente_selecionado = None
    st.session_state.messages = []
    st.rerun()

# Status das APIs
st.sidebar.markdown("---")
st.sidebar.subheader("🔌 Status das APIs")
if gemini_api_key:
    st.sidebar.success("✅ Gemini: OK")
else:
    st.sidebar.error("❌ Gemini")
if anthropic_api_key:
    st.sidebar.success("✅ Claude: OK")
else:
    st.sidebar.error("❌ Claude")
if openai_api_key:
    st.sidebar.success("✅ OpenAI: OK")
else:
    st.sidebar.warning("⚠️ OpenAI")
if perp_api_key:
    st.sidebar.success("✅ Perplexity: OK")
else:
    st.sidebar.warning("⚠️ Perplexity")

# Título e seletor de agente
st.title("🤖 Agente Seeds")

agentes = listar_agentes()
if agentes:
    opcoes = []
    for agente in agentes:
        agente_completo = obter_agente_com_heranca(agente['_id'])
        if agente_completo:
            desc = f"{agente['nome']} - {agente.get('categoria', 'Social')}"
            if agente.get('agente_mae_id'):
                desc += " 🔗"
            opcoes.append((desc, agente_completo))
    
    if opcoes:
        indice_atual = 0
        for i, (desc, agente) in enumerate(opcoes):
            if agente['_id'] == st.session_state.agente_selecionado['_id']:
                indice_atual = i
                break
        
        col1, col2 = st.columns([3, 1])
        with col1:
            novo_agente_desc = st.selectbox(
                "Selecionar Agente:",
                options=[op[0] for op in opcoes],
                index=indice_atual,
                key="selectbox_trocar_agente"
            )
        with col2:
            if st.button("🔄 Trocar", key="botao_trocar_agente"):
                for desc, agente in opcoes:
                    if desc == novo_agente_desc:
                        st.session_state.agente_selecionado = agente
                        st.session_state.messages = []
                        st.success(f"✅ Agente alterado para '{agente['nome']}'!")
                        st.rerun()

# --- DEFINIÇÃO DAS ABAS ---
abas_base = [
    "💬 Chat", 
    "⚙️ Gerenciar Agentes",
    "📓 Diário de Bordo",
    "✅ Validação Unificada",
    "✨ Geração de Conteúdo",
    "📝 Revisão Ortográfica",
    "Monitoramento de Redes",
    "🚀 Otimização de Conteúdo",
    "📅 Criadora de Calendário",
    "📊 Planejamento Estratégico",
    "📱 Planejamento de Mídias",
]

if is_syn_agent(agente_selecionado['nome']):
    abas_base.append("📋 Briefing")

tabs = st.tabs(abas_base)
tab_mapping = {aba: tabs[i] for i, aba in enumerate(abas_base)}

# ==================== ABA: CHAT ====================
with tab_mapping["💬 Chat"]:
    st.header("💬 Chat com Agente")
    
    if 'modelo_chat' not in st.session_state:
        st.session_state.modelo_chat = "Gemini"
    
    agente = st.session_state.agente_selecionado
    st.subheader(f"Conversando com: {agente['nome']}")
    
    st.sidebar.subheader("🤖 Modelo")
    modelo_chat = st.sidebar.selectbox(
        "Escolha o modelo:",
        ["Gemini", "Claude", "OpenAI"],
        key="modelo_chat_selector",
        index=0
    )
    st.session_state.modelo_chat = modelo_chat
    
    st.sidebar.subheader("🔧 Bases de Conhecimento")
    segmentos_disponiveis = {
        "Prompt do Sistema": "system_prompt",
        "Brand Guidelines": "base_conhecimento", 
        "Diário do Cliente": "comments",
        "Planejamento": "planejamento"
    }
    
    segmentos_selecionados = []
    for nome, chave in segmentos_disponiveis.items():
        if st.sidebar.checkbox(nome, value=chave in st.session_state.segmentos_selecionados, key=f"seg_{chave}"):
            segmentos_selecionados.append(chave)
    st.session_state.segmentos_selecionados = segmentos_selecionados
    
    for message in st.session_state.messages:
        if isinstance(message, dict) and "role" in message:
            with st.chat_message(message["role"]):
                st.markdown(message.get("content", ""))
    
    if prompt := st.chat_input("Digite sua mensagem..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        contexto = construir_contexto(agente, st.session_state.segmentos_selecionados, st.session_state.messages)
        
        with st.chat_message("assistant"):
            with st.spinner('Pensando...'):
                resposta = gerar_resposta_modelo(prompt, st.session_state.modelo_chat, contexto)
                st.markdown(resposta)
                st.session_state.messages.append({"role": "assistant", "content": resposta})
                salvar_conversa(agente['_id'], st.session_state.messages, st.session_state.segmentos_selecionados)

# ==================== ABA: GERENCIAR AGENTES ====================
with tab_mapping["⚙️ Gerenciar Agentes"]:
    st.header("Gerenciamento de Agentes")
    
    sub_tab1, sub_tab2, sub_tab3 = st.tabs(["Criar Agente", "Editar Agente", "Gerenciar Agentes"])
    
    with sub_tab1:
        st.subheader("Criar Novo Agente")
        with st.form("form_criar_agente"):
            nome_agente = st.text_input("Nome do Agente:")
            categoria = st.selectbox("Categoria:", ["Social", "SEO", "Conteúdo", "Monitoramento"])
            squad_permitido = st.selectbox("Squad Permitido:", ["Todos", "Syngenta", "SME", "Enterprise"])
            
            if categoria == "Monitoramento":
                base_conhecimento = st.text_area("Base de Conhecimento:", height=300)
                system_prompt = comments = planejamento = ""
                criar_como_filho = False
                agente_mae_id = None
                herdar_elementos = []
            else:
                criar_como_filho = st.checkbox("Criar como agente filho")
                if criar_como_filho:
                    agentes_mae = listar_agentes_para_heranca()
                    if agentes_mae:
                        opcoes = {f"{a['nome']} ({a.get('categoria', 'Social')})": a['_id'] for a in agentes_mae}
                        mae_selecionado = st.selectbox("Agente Mãe:", list(opcoes.keys()))
                        agente_mae_id = opcoes[mae_selecionado]
                        herdar_elementos = st.multiselect("Herdar:", ["system_prompt", "base_conhecimento", "comments", "planejamento"])
                else:
                    agente_mae_id = None
                    herdar_elementos = []
                
                system_prompt = st.text_area("Prompt de Sistema:", height=150)
                base_conhecimento = st.text_area("Brand Guidelines:", height=200)
                comments = st.text_area("Diário do cliente:", height=200)
                planejamento = st.text_area("Planejamento:", height=200)
            
            if st.form_submit_button("Criar Agente") and nome_agente:
                criar_agente(nome_agente, system_prompt, base_conhecimento, comments, planejamento,
                            categoria, squad_permitido, agente_mae_id, herdar_elementos)
                st.success(f"Agente '{nome_agente}' criado!")
                st.rerun()
    
    with sub_tab2:
        st.subheader("Editar Agente")
        agentes = listar_agentes()
        if agentes:
            agente_nomes = {a['nome']: a for a in agentes}
            selecionado = st.selectbox("Selecione:", list(agente_nomes.keys()))
            agente = agente_nomes[selecionado]
            
            with st.form("form_editar_agente"):
                novo_nome = st.text_input("Nome:", value=agente['nome'])
                nova_categoria = st.selectbox("Categoria:", ["Social", "SEO", "Conteúdo", "Monitoramento"], 
                                             index=["Social", "SEO", "Conteúdo", "Monitoramento"].index(agente.get('categoria', 'Social')))
                novo_squad = st.selectbox("Squad:", ["Todos", "Syngenta", "SME", "Enterprise"],
                                         index=["Todos", "Syngenta", "SME", "Enterprise"].index(agente.get('squad_permitido', 'Todos')))
                
                if nova_categoria == "Monitoramento":
                    nova_base = st.text_area("Base:", value=agente.get('base_conhecimento', ''), height=300)
                    novo_prompt = nova_comment = novo_planejamento = ""
                else:
                    novo_prompt = st.text_area("Prompt:", value=agente.get('system_prompt', ''), height=150)
                    nova_base = st.text_area("Brand:", value=agente.get('base_conhecimento', ''), height=200)
                    nova_comment = st.text_area("Diário:", value=agente.get('comments', ''), height=200)
                    novo_planejamento = st.text_area("Planejamento:", value=agente.get('planejamento', ''), height=200)
                
                if st.form_submit_button("Atualizar"):
                    atualizar_agente(agente['_id'], novo_nome, novo_prompt, nova_base, nova_comment,
                                    novo_planejamento, nova_categoria, novo_squad,
                                    agente.get('agente_mae_id'), agente.get('herdar_elementos', []))
                    st.success("Atualizado!")
                    st.rerun()
    
    with sub_tab3:
        st.subheader("Gerenciar Agentes")
        categoria_filtro = st.selectbox("Filtrar:", ["Todos", "Social", "SEO", "Conteúdo", "Monitoramento"])
        agentes = [a for a in listar_agentes() if categoria_filtro == "Todos" or a.get('categoria') == categoria_filtro]
        
        for i, agente in enumerate(agentes):
            with st.expander(f"{agente['nome']} - {agente.get('categoria', 'Social')}"):
                if agente.get('agente_mae_id'):
                    st.write(f"🔗 Herda de: {agente.get('agente_mae_id')}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Selecionar", key=f"select_{i}"):
                        st.session_state.agente_selecionado = obter_agente_com_heranca(agente['_id'])
                        st.session_state.messages = []
                        st.rerun()
                with col2:
                    if st.button("Desativar", key=f"delete_{i}"):
                        desativar_agente(agente['_id'])
                        st.rerun()

# ==================== ABA: DIÁRIO DE BORDO ====================
with tab_mapping["📓 Diário de Bordo"]:
    st.header("📓 Diário de Bordo")
    agente = st.session_state.agente_selecionado
    comentarios_atuais = agente.get('comments', '')
    
    tab_vis, tab_add, tab_rel = st.tabs(["Visualizar", "Adicionar", "Relatório"])
    
    with tab_vis:
        if comentarios_atuais:
            st.text_area("Diário:", value=comentarios_atuais, height=400, disabled=True)
            st.download_button("Exportar", data=comentarios_atuais, file_name=f"diario_{agente['nome']}.txt")
        else:
            st.info("Diário vazio")
    
    with tab_add:
        metodo = st.radio("Método:", ["Texto Manual", "Upload Documento"], horizontal=True)
        if metodo == "Texto Manual":
            titulo = st.text_input("Título:")
            novo = st.text_area("Conteúdo:", height=200)
            if st.button("Salvar"):
                entrada = f"\n\n--- {titulo} ({datetime.datetime.now().strftime('%d/%m/%Y')}) ---\n{novo}"
                atualizar_agente(agente['_id'], agente['nome'], agente.get('system_prompt', ''),
                                agente.get('base_conhecimento', ''), comentarios_atuais + entrada,
                                agente.get('planejamento', ''), agente.get('categoria', 'Social'),
                                agente.get('squad_permitido', 'Todos'), agente.get('agente_mae_id'),
                                agente.get('herdar_elementos', []))
                st.session_state.agente_selecionado = obter_agente_com_heranca(agente['_id'])
                st.success("Salvo!")
                st.rerun()
        else:
            arquivo = st.file_uploader("Arquivo:", type=['pdf', 'docx', 'txt'])
            if arquivo:
                texto = extrair_texto_arquivo(arquivo) if arquivo.type != "application/pdf" else extract_text_from_pdf_com_slides(arquivo)[0]
                contexto = st.text_input("Contexto:")
                if st.button("Adicionar"):
                    entrada = f"\n\n--- {contexto} - {arquivo.name} ({datetime.datetime.now().strftime('%d/%m/%Y')}) ---\n{texto[:10000]}"
                    atualizar_agente(agente['_id'], agente['nome'], agente.get('system_prompt', ''),
                                    agente.get('base_conhecimento', ''), comentarios_atuais + entrada,
                                    agente.get('planejamento', ''), agente.get('categoria', 'Social'),
                                    agente.get('squad_permitido', 'Todos'), agente.get('agente_mae_id'),
                                    agente.get('herdar_elementos', []))
                    st.session_state.agente_selecionado = obter_agente_com_heranca(agente['_id'])
                    st.success("Adicionado!")
                    st.rerun()
    
    with tab_rel:
        if len(comentarios_atuais) > 50:
            if st.button("Gerar Análise"):
                with st.spinner("Analisando..."):
                    prompt = f"Analise este diário e gere um relatório:\n\n{comentarios_atuais[:8000]}"
                    resposta = modelo_texto.generate_content(prompt)
                    st.markdown(resposta.text)
                    st.download_button("Baixar", data=resposta.text, file_name=f"analise_diario.txt")
        else:
            st.info("Adicione mais conteúdo para gerar relatório")

# ==================== ABA: VALIDAÇÃO UNIFICADA ====================
with tab_mapping["✅ Validação Unificada"]:
    st.header("✅ Validação Unificada")
    agente = st.session_state.agente_selecionado
    contexto_global = st.text_area("Contexto adicional:", height=100, key="ctx_global")
    
    subtab_img, subtab_txt, subtab_vid, subtab_txt_img = st.tabs(["Imagem", "Documentos", "Vídeo", "Texto em Imagem"])
    
    with subtab_txt_img:
        uploaded = st.file_uploader("Imagens:", type=["jpg", "png"], accept_multiple_files=True, key="img_text_upload")
        if uploaded and st.button("Validar", key="valid_txt_img"):
            resultados = []
            for i, img in enumerate(uploaded):
                with st.spinner(f"Imagem {i+1}..."):
                    prompt = f"{contexto_global}\n\nAnalise o texto nesta imagem."
                    response = modelo_vision.generate_content([prompt, {"mime_type": img.type, "data": img.getvalue()}])
                    status = "Com erros" if "❌" in response.text else "Ajustes sugeridos" if "⚠️" in response.text else "Correto"
                    resultados.append({'indice': i+1, 'analise': response.text, 'status': status})
                    st.markdown(response.text)
            st.download_button("Relatório", data=gerar_relatorio_texto_imagem_consolidado(resultados), file_name="relatorio.txt")
    
    with subtab_txt:
        texto_input = st.text_area("Texto:", height=150, key="txt_valid")
        arquivos = st.file_uploader("Arquivos:", type=['pdf', 'pptx', 'txt', 'docx'], accept_multiple_files=True, key="docs_valid")
        
        if st.button("Validar", key="valid_txt"):
            todos = []
            if texto_input.strip():
                todos.append({'nome': 'Texto', 'conteudo': texto_input})
            for arq in arquivos:
                if arq.type == "application/pdf":
                    texto, _ = extract_text_from_pdf_com_slides(arq)
                elif arq.type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
                    texto, _ = extract_text_from_pptx_com_slides(arq)
                else:
                    texto = extrair_texto_arquivo(arq)
                todos.append({'nome': arq.name, 'conteudo': texto, 'arquivo': arq})
            
            for doc in todos:
                with st.expander(f"📄 {doc['nome']}"):
                    analisadores = criar_analisadores_texto(agente.get('base_conhecimento', ''), contexto_global)
                    resultados = executar_analise_texto_especializada(doc['conteudo'], doc['nome'], analisadores)
                    st.markdown(gerar_relatorio_texto_consolidado(resultados, doc['nome']))
    
    with subtab_img:
        uploaded = st.file_uploader("Imagens:", type=["jpg", "png"], accept_multiple_files=True, key="img_upload")
        analise_esp = st.checkbox("Análise especializada", value=st.session_state.analise_especializada_imagem, key="analise_img")
        if uploaded and st.button("Validar Imagens", key="valid_img"):
            for img in uploaded:
                with st.expander(f"🖼️ {img.name}"):
                    image = Image.open(img)
                    st.image(image, width=200)
                    if analise_esp:
                        analisadores = criar_analisadores_imagem(agente.get('base_conhecimento', ''), contexto_global)
                        resultados = executar_analise_imagem_especializada(img, img.name, analisadores)
                        st.markdown(gerar_relatorio_imagem_consolidado(resultados, img.name, f"{image.width}x{image.height}"))
                    else:
                        response = modelo_vision.generate_content([f"{contexto_global}\n\nAnalise esta imagem.", {"mime_type": img.type, "data": img.getvalue()}])
                        st.markdown(response.text)
    
    with subtab_vid:
        uploaded = st.file_uploader("Vídeos:", type=["mp4", "mov", "avi"], accept_multiple_files=True, key="vid_upload")
        if uploaded and st.button("Validar Vídeos", key="valid_vid"):
            for vid in uploaded:
                with st.expander(f"🎬 {vid.name}"):
                    st.video(vid)
                    analisadores = criar_analisadores_video(agente.get('base_conhecimento', ''), contexto_global, "")
                    resultados = executar_analise_video_especializada(vid, vid.name, analisadores)
                    st.markdown(gerar_relatorio_video_consolidado(resultados, vid.name, vid.type))

# ==================== ABA: GERAÇÃO DE CONTEÚDO ====================
with tab_mapping["✨ Geração de Conteúdo"]:
    st.header("✨ Geração de Conteúdo")
    
    tab_gerar, tab_ajustar = st.tabs(["Gerar", "Ajustar"])
    
    with tab_gerar:
        usar_busca = st.checkbox("Busca web", value=True)
        if usar_busca:
            termos = st.text_area("Termos de busca:", height=80)
        
        arquivos = st.file_uploader("Arquivos:", type=['pdf', 'txt', 'pptx', 'docx'], accept_multiple_files=True, key="gen_files")
        briefing = st.text_area("Briefing:", height=100)
        
        col1, col2 = st.columns(2)
        with col1:
            modelo = st.selectbox("Modelo:", ["Gemini", "Claude", "OpenAI"])
            tipo = st.selectbox("Tipo:", ["Post Social", "Artigo Blog", "Email Marketing"])
        with col2:
            tom = st.text_input("Tom de Voz:", "Profissional")
            palavras = st.slider("Palavras:", 100, 3000, 800)
        
        if st.button("Gerar", type="primary"):
            contexto = ""
            for arq in arquivos:
                if arq.type == "application/pdf":
                    texto, _ = extract_text_from_pdf_com_slides(arq)
                else:
                    texto = extrair_texto_arquivo(arq)
                contexto += f"\n--- {arq.name} ---\n{texto}"
            
            if briefing:
                contexto += f"\n--- BRIEFING ---\n{briefing}"
            
            if usar_busca and termos:
                busca = realizar_busca_web_com_fontes(termos, "")
                contexto += f"\n--- BUSCA WEB ---\n{busca}"
            
            prompt = f"{contexto}\n\nGere um {tipo} com tom {tom} e aproximadamente {palavras} palavras."
            with st.spinner("Gerando..."):
                conteudo = gerar_conteudo_modelo(prompt, modelo, "")
                st.session_state.conteudo_gerado = conteudo
                st.markdown(conteudo)
                st.download_button("Baixar", data=conteudo, file_name=f"conteudo.txt")
    
    with tab_ajustar:
        if st.session_state.conteudo_gerado:
            st.text_area("Conteúdo atual:", value=st.session_state.conteudo_gerado, height=200, disabled=True)
            ajustes = st.text_area("Ajustes desejados:", height=100)
            if st.button("Aplicar") and ajustes:
                prompt = f"Conteúdo original:\n{st.session_state.conteudo_gerado}\n\nAjustes: {ajustes}\n\nRetorne apenas o conteúdo ajustado."
                novo = gerar_conteudo_modelo(prompt, "Gemini", "")
                st.session_state.conteudo_gerado = novo
                st.markdown(novo)
        else:
            st.info("Gere um conteúdo primeiro")

# ==================== ABA: REVISÃO ORTOGRÁFICA ====================
with tab_mapping["📝 Revisão Ortográfica"]:
    st.header("📝 Revisão Ortográfica")
    agente = st.session_state.agente_selecionado
    
    tab_texto, tab_arquivo = st.tabs(["Texto", "Arquivos"])
    
    with tab_texto:
        texto = st.text_area("Texto:", height=300, key="rev_texto")
        if st.button("Revisar") and texto:
            with st.spinner("Revisando..."):
                resultado = revisar_texto_ortografia(texto, agente, st.session_state.segmentos_selecionados, True, True, True, "Gemini")
                st.markdown(resultado)
    
    with tab_arquivo:
        arquivos = st.file_uploader("Arquivos:", type=['pdf', 'pptx', 'txt', 'docx'], accept_multiple_files=True, key="rev_files")
        if arquivos and st.button("Revisar Arquivos"):
            for arq in arquivos:
                with st.expander(f"📄 {arq.name}"):
                    if arq.type == "application/pdf":
                        texto, _ = extract_text_from_pdf_com_slides(arq)
                    elif arq.type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
                        texto, _ = extract_text_from_pptx_com_slides(arq)
                    else:
                        texto = extrair_texto_arquivo(arq)
                    resultado = revisar_texto_ortografia(texto, agente, st.session_state.segmentos_selecionados, True, True, True, "Gemini")
                    st.markdown(resultado)

# ==================== ABA: MONITORAMENTO DE REDES ====================
with tab_mapping["Monitoramento de Redes"]:
    st.header("🤖 Monitoramento de Redes")
    
    contexto_adicional = st.text_area("Contexto:", height=80, key="monitor_ctx")
    modelo_monitor = st.sidebar.selectbox("Modelo:", ["Gemini", "Claude"], key="modelo_monitor")
    
    agentes_monitor = [a for a in listar_agentes() if a.get('categoria') == 'Monitoramento']
    if agentes_monitor:
        agente_monitor = st.selectbox("Agente:", [a['nome'] for a in agentes_monitor])
        agente_monitor = next(a for a in agentes_monitor if a['nome'] == agente_monitor)
    else:
        st.error("Nenhum agente de monitoramento")
        agente_monitor = None
    
    for msg in st.session_state.messages_monitoramento:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    if prompt := st.chat_input("Mensagem:"):
        st.session_state.messages_monitoramento.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            resposta = gerar_resposta_agente(prompt, st.session_state.messages_monitoramento, agente_monitor, modelo_monitor, contexto_adicional)
            st.markdown(resposta)
            st.session_state.messages_monitoramento.append({"role": "assistant", "content": resposta})

# ==================== ABA: OTIMIZAÇÃO DE CONTEÚDO ====================
with tab_mapping["🚀 Otimização de Conteúdo"]:
    st.header("🚀 Otimização de Conteúdo")
    
    texto = st.text_area("Conteúdo:", height=300)
    tipo_otimizacao = st.selectbox("Tipo:", ["SEO", "Engajamento", "Conversão", "Clareza"])
    tom_voz = st.text_input("Tom:", "Técnico")
    
    if st.button("Otimizar") and texto:
        with st.spinner("Otimizando..."):
            busca = realizar_busca_web_com_fontes(texto[:500], "") if st.checkbox("Buscar dados", value=True) else ""
            prompt = f"""
            Texto original: {texto}
            Dados: {busca}
            Tipo: {tipo_otimizacao}
            Tom: {tom_voz}
            
            Gere conteúdo otimizado com meta title e description.
            """
            resultado = modelo_texto.generate_content(prompt)
            st.session_state.conteudo_gerado = resultado.text
            st.markdown(resultado.text)
            st.download_button("Baixar", data=resultado.text, file_name="otimizado.txt")

# ==================== ABA: CRIADORA DE CALENDÁRIO ====================
with tab_mapping["📅 Criadora de Calendário"]:
    st.header("📅 Criadora de Calendário")
    
    mes_ano = st.text_input("Mês/Ano:", "FEVEREIRO 2026")
    data_inicio = st.date_input("Início:", datetime.date(2026, 2, 1))
    data_fim = st.date_input("Fim:", datetime.date(2026, 2, 28))
    produtos = st.text_area("Produtos:", height=100)
    
    if st.button("Gerar Calendário"):
        with st.spinner("Gerando..."):
            prompt = f"""
            Calendário para {mes_ano} de {data_inicio} a {data_fim}.
            Produtos: {produtos}
            Gere CSV com as datas e pautas.
            """
            resultado = modelo_texto.generate_content(prompt)
            csv = resultado.text.replace('```csv', '').replace('```', '').strip()
            st.text_area("CSV:", csv, height=300)
            st.download_button("Baixar CSV", data=csv, file_name=f"calendario_{mes_ano.replace(' ', '_')}.csv")

# ==================== ABA: PLANEJAMENTO ESTRATÉGICO ====================
with tab_mapping["📊 Planejamento Estratégico"]:
    st.header("📊 Planejamento Estratégico")
    
    nome = st.text_input("Cliente:", key="plan_estrategico_nome")
    ramo = st.text_input("Ramo:")
    objetivo = st.text_input("Objetivo:")
    publico = st.text_input("Público:")

    if st.button("Gerar Planejamento", key="btn_plan_estrategico") and nome:
        with st.spinner("Gerando..."):
            prompt = f"""
            Cliente: {nome}
            Ramo: {ramo}
            Objetivo: {objetivo}
            Público: {publico}
            
            Gere: SWOT, PEST, Posicionamento, Brand Persona, Buyer Persona, Tom de Voz.
            """
            resultado = modelo_texto.generate_content(prompt)
            st.markdown(resultado.text)
            st.download_button("Baixar", data=resultado.text, file_name=f"planejamento_{nome}.txt")

# ==================== ABA: PLANEJAMENTO DE MÍDIAS ====================
with tab_mapping["📱 Planejamento de Mídias"]:
    st.header("📱 Planejamento de Mídias")
    
    nome = st.text_input("Cliente:", key="midias_nome")
    orcamento = st.number_input("Orçamento (R$):", 1000, 1000000, 10000)
    periodo = st.selectbox("Período:", ["1 mês", "3 meses", "6 meses"])
    
    if st.button("Gerar Planejamento", key="btn_plan_midias") and nome:
        with st.spinner("Gerando..."):
            prompt = f"""
            Cliente: {nome}
            Orçamento: R${orcamento}
            Período: {periodo}
            
            Gere planejamento de mídias com distribuição orçamentária e estratégias.
            """
            resultado = modelo_texto.generate_content(prompt)
            st.markdown(resultado.text)
            st.download_button("Baixar", data=resultado.text, file_name=f"midias_{nome}.txt")

# ==================== ABA: BRIEFING (se existir) ====================
if "📋 Briefing" in tab_mapping:
    with tab_mapping["📋 Briefing"]:
        st.header("📋 Gerador de Briefings - SYN")
        
        content = st.text_area("Conteúdo da célula:", height=100)
        data = st.date_input("Data:", datetime.datetime.now())
        formato = st.selectbox("Formato:", ["Reels + capa", "Carrossel + stories", "Blog + redes"])
        
        if st.button("Gerar Briefing") and content:
            product, culture, action = extract_product_info(content)
            if product:
                briefing = generate_briefing(content, product, culture, action, data, formato)
                st.text(briefing)
                st.download_button("Baixar", data=briefing, file_name=f"briefing_{product}.txt")
            else:
                st.error("Produto não identificado")
