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

# Configuração inicial
st.set_page_config(
    layout="wide",
    page_title="Agente Health",
    page_icon="🤖"
)

import os
import PyPDF2
import pdfplumber
from pathlib import Path

# --- CONFIGURAÇÃO DOS MODELOS ---
# Configuração da API do Anthropic (Claude)
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
if anthropic_api_key:
    anthropic_client = Anthropic(api_key=anthropic_api_key)
else:
    st.error("ANTHROPIC_API_KEY não encontrada nas variáveis de ambiente")
    anthropic_client = None

# Configuração da API do Gemini
gemini_api_key = os.getenv("GEM_API_KEY")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    modelo_vision = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.0})
    modelo_texto = genai.GenerativeModel("gemini-2.5-flash")
else:
    st.error("GEM_API_KEY não encontrada nas variáveis de ambiente")
    modelo_vision = None
    modelo_texto = None

openai_api_key = os.getenv("OPENAI_API_KEY")
if openai_api_key:
    openai_client = OpenAI(api_key=openai_api_key)
else:
    st.warning("OPENAI_API_KEY não encontrada nas variáveis de ambiente")
    openai_client = None

import os
import PyPDF2
import pdfplumber
from pathlib import Path

# --- FUNÇÕES AUXILIARES MELHORADAS ---

def criar_prompt_validacao_preciso(texto, nome_arquivo, contexto_agente):
    """Cria um prompt de validação muito mais preciso para evitar falsos positivos"""
    
    prompt = f"""
{contexto_agente}


###BEGIN TEXTO PARA VALIDAÇÃO###
**Arquivo:** {nome_arquivo}
**Conteúdo:**
{texto[:12000]}
###END TEXTO PARA VALIDAÇÃO###

## FORMATO DE RESPOSTA OBRIGATÓRIO:



### ✅ CONFORMIDADE COM DIRETRIZES
- [Itens que estão alinhados com as diretrizes de branding]



**INCONSISTÊNCIAS COM BRANDING:**
- [Só liste desvios REAIS das diretrizes de branding]

### 💡 TEXTO REVISADO
- [Sugestões para aprimorar]

### 📊 STATUS FINAL
**Documento:** [Aprovado/Necessita ajustes/Reprovado]
**Principais ações necessárias:** [Lista resumida]

"""
    return prompt


# --- FUNÇÃO PARA ESCOLHER ENTRE GEMINI E CLAUDE ---
def gerar_resposta_modelo(prompt: str, modelo_escolhido: str = "Gemini", contexto_agente: str = None) -> str:
    """
    Gera resposta usando Gemini ou Claude baseado na escolha do usuário
    """
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
            
        else:
            return f"❌ Modelo {modelo_escolhido} não disponível. Verifique as configurações da API."
            
    except Exception as e:
        return f"❌ Erro ao gerar resposta com {modelo_escolhido}: {str(e)}"

def analisar_documento_por_slides(doc, contexto_agente):
    """Analisa documento slide por slide com alta precisão"""
    
    resultados = []
    
    for i, slide in enumerate(doc['slides']):
        with st.spinner(f"Analisando slide {i+1}..."):
            try:
                prompt_slide = f"""
{contexto_agente}

## ANÁLISE POR SLIDE - PRECISÃO ABSOLUTA

###BEGIN TEXTO PARA VALIDAÇÃO###
**SLIDE {i+1}:**
{slide['conteudo'][:2000]}
###END TEXTO PARA VALIDAÇÃO###


**ANÁLISE DO SLIDE {i+1}:**

### ✅ Pontos Fortes:
[O que está bom neste slide]

### ⚠️ Problemas REAIS:
- [Lista CURTA de problemas]

### 💡 Sugestões Específicas:
[Melhorias para ESTE slide específico]

Considere que slides que são introdutórios ou apenas de títulos não precisam de tanto rigor de branding

**STATUS:** [✔️ Aprovado / ⚠️ Ajustes Menores / ❌ Problemas Sérios]
"""
                
                resposta = modelo_texto.generate_content(prompt_slide)
                resultados.append({
                    'slide_num': i+1,
                    'analise': resposta.text,
                    'tem_alteracoes': '❌' in resposta.text or '⚠️' in resposta.text
                })
                
            except Exception as e:
                resultados.append({
                    'slide_num': i+1,
                    'analise': f"❌ Erro na análise do slide: {str(e)}",
                    'tem_alteracoes': False
                })
    
    # Construir relatório consolidado
    relatorio = f"# 📊 RELATÓRIO DE VALIDAÇÃO - {doc['nome']}\n\n"
    relatorio += f"**Total de Slides:** {len(doc['slides'])}\n"
    relatorio += f"**Slides com Alterações:** {sum(1 for r in resultados if r['tem_alteracoes'])}\n\n"
    
    # Slides que precisam de atenção
    slides_com_problemas = [r for r in resultados if r['tem_alteracoes']]
    if slides_com_problemas:
        relatorio += "## 🚨 SLIDES QUE PRECISAM DE ATENÇÃO:\n\n"
        for resultado in slides_com_problemas:
            relatorio += f"### 📋 Slide {resultado['slide_num']}\n"
            relatorio += f"{resultado['analise']}\n\n"
    
    # Resumo executivo
    relatorio += "## 📈 RESUMO EXECUTIVO\n\n"
    if slides_com_problemas:
        relatorio += f"**⚠️ {len(slides_com_problemas)} slide(s) necessitam de ajustes**\n"
        relatorio += f"**✅ {len(doc['slides']) - len(slides_com_problemas)} slide(s) estão adequados**\n"
    else:
        relatorio += "**🎉 Todos os slides estão em conformidade com as diretrizes!**\n"
    
    return relatorio

def extract_text_from_pdf_com_slides(arquivo_pdf):
    """Extrai texto de PDF com informação de páginas"""
    try:
        import PyPDF2
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
        return f"Erro na extração PDF: {str(e)}", []

def extract_text_from_pptx_com_slides(arquivo_pptx):
    """Extrai texto de PPTX com informação de slides"""
    try:
        from pptx import Presentation
        import io
        
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
        return f"Erro na extração PPTX: {str(e)}", []

def extrair_texto_arquivo(arquivo):
    """Extrai texto de arquivos TXT e DOCX"""
    try:
        if arquivo.type == "text/plain":
            return str(arquivo.read(), "utf-8")
        elif arquivo.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            import docx
            import io
            doc = docx.Document(io.BytesIO(arquivo.read()))
            texto = ""
            for para in doc.paragraphs:
                texto += para.text + "\n"
            return texto
        else:
            return f"Tipo não suportado: {arquivo.type}"
    except Exception as e:
        return f"Erro na extração: {str(e)}"

def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF file using multiple methods for better coverage
    """
    text = ""

    # Method 1: Try with pdfplumber (better for some PDFs)
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text
    except Exception as e:
        print(f"pdfplumber failed for {pdf_path}: {e}")

    # Method 2: Fallback to PyPDF2 if pdfplumber didn't extract much text
    if len(text.strip()) < 100:  # If very little text was extracted
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text 
        except Exception as e:
            print(f"PyPDF2 also failed for {pdf_path}: {e}")

    return text
    

# --- Sistema de Autenticação MELHORADO ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

# Dados de usuário (em produção, isso deve vir de um banco de dados seguro)
users_db = {
    "admin": {
        "password": make_hashes("MacforIA2026@"),
        "squad": "admin",
        "nome": "Administrador"
    }
}

# Conexão MongoDB
client = MongoClient("mongodb+srv://gustavoromao3345:RqWFPNOJQfInAW1N@cluster0.5iilj.mongodb.net/auto_doc?retryWrites=true&w=majority&ssl=true&ssl_cert_reqs=CERT_NONE&tlsAllowInvalidCertificates=true")
db = client['agentes_personalizados']
collection_agentes = db['agentes']
collection_conversas = db['conversas']
collection_usuarios = db['usuarios']  # Nova coleção para usuários

# --- FUNÇÕES DE CADASTRO E LOGIN ---
def criar_usuario(email, senha, nome, squad):
    """Cria um novo usuário no banco de dados"""
    try:
        # Verificar se usuário já existe
        if collection_usuarios.find_one({"email": email}):
            return False, "Usuário já existe"
        
        # Criar hash da senha
        senha_hash = make_hashes(senha)
        
        novo_usuario = {
            "email": email,
            "senha": senha_hash,
            "nome": nome,
            "squad": squad,
            "data_criacao": datetime.datetime.now(),
            "ultimo_login": None,
            "ativo": True
        }
        
        result = collection_usuarios.insert_one(novo_usuario)
        return True, "Usuário criado com sucesso"
        
    except Exception as e:
        return False, f"Erro ao criar usuário: {str(e)}"

def verificar_login(email, senha):
    """Verifica as credenciais do usuário"""
    try:
        # Primeiro verificar no banco de dados
        usuario = collection_usuarios.find_one({"email": email, "ativo": True})
        
        if usuario:
            if check_hashes(senha, usuario["senha"]):
                # Atualizar último login
                collection_usuarios.update_one(
                    {"_id": usuario["_id"]},
                    {"$set": {"ultimo_login": datetime.datetime.now()}}
                )
                return True, usuario, "Login bem-sucedido"
            else:
                return False, None, "Senha incorreta"
        
        # Fallback para usuários hardcoded (apenas para admin)
        if email in users_db:
            user_data = users_db[email]
            if check_hashes(senha, user_data["password"]):
                usuario_fallback = {
                    "email": email,
                    "nome": user_data["nome"],
                    "squad": user_data["squad"],
                    "_id": "admin"
                }
                return True, usuario_fallback, "Login bem-sucedido"
            else:
                return False, None, "Senha incorreta"
        
        return False, None, "Usuário não encontrado"
        
    except Exception as e:
        return False, None, f"Erro no login: {str(e)}"

def get_current_user():
    """Retorna o usuário atual da sessão"""
    return st.session_state.get('user', {})

def get_current_squad():
    """Retorna o squad do usuário atual"""
    user = get_current_user()
    return user.get('squad', 'unknown')

def login():
    """Formulário de login e cadastro"""
    st.title("🔒 Agente Health - Login")
    
    tab_login, tab_cadastro = st.tabs(["Login", "Cadastro"])
    
    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Senha", type="password")
            submit_button = st.form_submit_button("Login")
            
            if submit_button:
                if email and password:
                    sucesso, usuario, mensagem = verificar_login(email, password)
                    if sucesso:
                        st.session_state.logged_in = True
                        st.session_state.user = usuario
                        st.success("Login realizado com sucesso!")
                        st.rerun()
                    else:
                        st.error(mensagem)
                else:
                    st.error("Por favor, preencha todos os campos")
    
    with tab_cadastro:
        with st.form("cadastro_form"):
            st.subheader("Criar Nova Conta")
            
            nome = st.text_input("Nome Completo")
            email = st.text_input("Email")
            squad = st.selectbox(
                "Selecione seu Squad:",
                ["Syngenta", "SME", "Enterprise"],
                help="Escolha o squad ao qual você pertence"
            )
            senha = st.text_input("Senha", type="password")
            confirmar_senha = st.text_input("Confirmar Senha", type="password")
            
            submit_cadastro = st.form_submit_button("Criar Conta")
            
            if submit_cadastro:
                if not all([nome, email, squad, senha, confirmar_senha]):
                    st.error("Por favor, preencha todos os campos")
                elif senha != confirmar_senha:
                    st.error("As senhas não coincidem")
                elif len(senha) < 6:
                    st.error("A senha deve ter pelo menos 6 caracteres")
                else:
                    sucesso, mensagem = criar_usuario(email, senha, nome, squad)
                    if sucesso:
                        st.success("Conta criada com sucesso! Faça login para continuar.")
                    else:
                        st.error(mensagem)

# Verificar se o usuário está logado
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login()
    st.stop()

# --- CONFIGURAÇÕES APÓS LOGIN ---
gemini_api_key = os.getenv("GEM_API_KEY")
if not gemini_api_key:
    st.error("GEMINI_API_KEY não encontrada nas variáveis de ambiente")
    st.stop()

genai.configure(api_key=gemini_api_key)
modelo_vision = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.0})
modelo_texto = genai.GenerativeModel("gemini-2.5-flash")

# Configuração da API do Perplexity
perp_api_key = os.getenv("PERP_API_KEY")
if not perp_api_key:
    st.error("PERP_API_KEY não encontrada nas variáveis de ambiente")

# --- Configuração de Autenticação de Administrador ---
def check_admin_password():
    """Retorna True para usuários admin sem verificação de senha."""
    return st.session_state.user.get('squad') == "admin"

# --- FUNÇÕES CRUD PARA AGENTES (MODIFICADAS PARA SQUADS) ---
def criar_agente(nome, system_prompt, base_conhecimento, comments, planejamento, categoria, squad_permitido, agente_mae_id=None, herdar_elementos=None):
    """Cria um novo agente no MongoDB com squad permitido"""
    agente = {
        "nome": nome,
        "system_prompt": system_prompt,
        "base_conhecimento": base_conhecimento,
        "comments": comments,
        "planejamento": planejamento,
        "categoria": categoria,
        "squad_permitido": squad_permitido,  # Novo campo
        "agente_mae_id": agente_mae_id,
        "herdar_elementos": herdar_elementos or [],
        "data_criacao": datetime.datetime.now(),
        "ativo": True,
        "criado_por": get_current_user().get('email', 'unknown'),
        "criado_por_squad": get_current_squad()  # Novo campo
    }
    result = collection_agentes.insert_one(agente)
    return result.inserted_id

def listar_agentes():
    """Retorna todos os agentes ativos que o usuário atual pode ver"""
    current_squad = get_current_squad()
    
    # Admin vê todos os agentes
    if current_squad == "admin":
        return list(collection_agentes.find({"ativo": True}).sort("data_criacao", -1))
    
    # Usuários normais veem apenas agentes do seu squad ou squad "Todos"
    return list(collection_agentes.find({
        "ativo": True,
        "$or": [
            {"squad_permitido": current_squad},
            {"squad_permitido": "Todos"},
            {"criado_por_squad": current_squad}  # Usuário pode ver seus próprios agentes
        ]
    }).sort("data_criacao", -1))

def listar_agentes_para_heranca(agente_atual_id=None):
    """Retorna todos os agentes ativos que podem ser usados como mãe (com filtro de squad)"""
    current_squad = get_current_squad()
    
    query = {"ativo": True}
    
    # Filtro por squad
    if current_squad != "admin":
        query["$or"] = [
            {"squad_permitido": current_squad},
            {"squad_permitido": "Todos"},
            {"criado_por_squad": current_squad}
        ]
    
    if agente_atual_id:
        # Excluir o próprio agente da lista de opções para evitar auto-herança
        if isinstance(agente_atual_id, str):
            agente_atual_id = ObjectId(agente_atual_id)
        query["_id"] = {"$ne": agente_atual_id}
    
    return list(collection_agentes.find(query).sort("data_criacao", -1))

def obter_agente(agente_id):
    """Obtém um agente específico pelo ID com verificação de permissão por squad"""
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    
    agente = collection_agentes.find_one({"_id": agente_id})
    
    # Verificar permissão baseada no squad
    if agente and agente.get('ativo', True):
        current_squad = get_current_squad()
        
        # Admin pode ver tudo
        if current_squad == "admin":
            return agente
        
        # Usuários normais só podem ver agentes do seu squad ou "Todos"
        squad_permitido = agente.get('squad_permitido')
        criado_por_squad = agente.get('criado_por_squad')
        
        if squad_permitido == current_squad or squad_permitido == "Todos" or criado_por_squad == current_squad:
            return agente
    
    return None

def atualizar_agente(agente_id, nome, system_prompt, base_conhecimento, comments, planejamento, categoria, squad_permitido, agente_mae_id=None, herdar_elementos=None):
    """Atualiza um agente existente com verificação de permissão"""
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    
    # Verificar se o usuário tem permissão para editar este agente
    agente_existente = obter_agente(agente_id)
    if not agente_existente:
        raise PermissionError("Agente não encontrado ou sem permissão de edição")
    
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
                "squad_permitido": squad_permitido,  # Novo campo
                "agente_mae_id": agente_mae_id,
                "herdar_elementos": herdar_elementos or [],
                "data_atualizacao": datetime.datetime.now()
            }
        }
    )

def desativar_agente(agente_id):
    """Desativa um agente (soft delete) com verificação de permissão"""
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    
    # Verificar se o usuário tem permissão para desativar este agente
    agente_existente = obter_agente(agente_id)
    if not agente_existente:
        raise PermissionError("Agente não encontrado ou sem permissão para desativar")
    
    return collection_agentes.update_one(
        {"_id": agente_id},
        {"$set": {"ativo": False, "data_desativacao": datetime.datetime.now()}}
    )

def obter_agente_com_heranca(agente_id):
    """Obtém um agente com os elementos herdados aplicados"""
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
    """Salva uma conversa no histórico"""
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
    """Obtém o histórico de conversas de um agente"""
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    return list(collection_conversas.find(
        {"agente_id": agente_id}
    ).sort("data_criacao", -1).limit(limite))

# --- Função para construir contexto com segmentos selecionados ---
def construir_contexto(agente, segmentos_selecionados, historico_mensagens=None):
    """Constrói o contexto com base nos segmentos selecionados"""
    contexto = ""
    
    if "system_prompt" in segmentos_selecionados and agente.get('system_prompt'):
        contexto += f"### INSTRUÇÕES DO SISTEMA ###\n{agente['system_prompt']}\n\n"
    
    if "base_conhecimento" in segmentos_selecionados and agente.get('base_conhecimento'):
        contexto += f"### BASE DE CONHECIMENTO ###\n{agente['base_conhecimento']}\n\n"
    
    if "comments" in segmentos_selecionados and agente.get('comments'):
        contexto += f"### Diário DO CLIENTE ###\n{agente['comments']}\n\n"
    
    if "planejamento" in segmentos_selecionados and agente.get('planejamento'):
        contexto += f"### PLANEJAMENTO ###\n{agente['planejamento']}\n\n"
    
    # Adicionar histórico se fornecido
    if historico_mensagens:
        contexto += "### HISTÓRICO DA CONVERSA ###\n"
        for msg in historico_mensagens:
            contexto += f"{msg['role']}: {msg['content']}\n"
        contexto += "\n"
    
    contexto += "### RESPOSTA ATUAL ###\nassistant:"
    
    return contexto

# --- MODIFICAÇÃO: SELECTBOX PARA SELEÇÃO DE AGENTE ---
def selecionar_agente_interface():
    """Interface para seleção de agente usando selectbox"""
    st.title("Agente Health")
    
    # Carregar agentes disponíveis
    agentes = listar_agentes()
    
    if not agentes:
        st.error("❌ Nenhum agente disponível. Crie um agente primeiro na aba de Gerenciamento.")
        return None
    
    # Preparar opções para o selectbox
    opcoes_agentes = []
    for agente in agentes:
        agente_completo = obter_agente_com_heranca(agente['_id'])
        if agente_completo:  # Só adiciona se tiver permissão
            descricao = f"{agente['nome']} - {agente.get('categoria', 'Social')}"
            if agente.get('agente_mae_id'):
                descricao += " 🔗"
            # Adicionar indicador de squad
            squad_permitido = agente.get('squad_permitido', 'Todos')
            descricao += f" 👥{squad_permitido}"
            opcoes_agentes.append((descricao, agente_completo))
    
    if opcoes_agentes:
        # Selectbox para seleção de agente
        agente_selecionado_desc = st.selectbox(
            "Selecione uma base de conhecimento para usar o sistema:",
            options=[op[0] for op in opcoes_agentes],
            index=0,
            key="selectbox_agente_principal"
        )
        
        # Encontrar o agente completo correspondente
        agente_completo = None
        for desc, agente in opcoes_agentes:
            if desc == agente_selecionado_desc:
                agente_completo = agente
                break
        
        if agente_completo and st.button("✅ Confirmar Seleção", key="confirmar_agente"):
            st.session_state.agente_selecionado = agente_completo
            st.session_state.messages = []
            st.session_state.segmentos_selecionados = ["system_prompt", "base_conhecimento", "comments", "planejamento"]
            st.success(f"✅ Agente '{agente_completo['nome']}' selecionado!")
            st.rerun()
        
        return agente_completo
    else:
        st.info("Nenhum agente disponível com as permissões atuais.")
        return None

# --- Verificar se o agente já foi selecionado ---
if "agente_selecionado" not in st.session_state:
    st.session_state.agente_selecionado = None

# Se não há agente selecionado, mostrar interface de seleção
if not st.session_state.agente_selecionado:
    selecionar_agente_interface()
    st.stop()

# --- INTERFACE PRINCIPAL (apenas se agente estiver selecionado) ---
agente_selecionado = st.session_state.agente_selecionado

def is_syn_agent(agent_name):
    """Verifica se o agente é da baseado no nome"""
    return agent_name and any(keyword in agent_name.upper() for keyword in ['SYN'])



def generate_context(content, product_name, culture, action, data_input, formato_principal):
    """Gera o texto de contexto discursivo usando LLM"""
    if not gemini_api_key:
        return "API key do Gemini não configurada. Contexto não disponível."
    
    # Determinar mês em português
    meses = {
        1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
        5: "maio", 6: "junho", 7: "julho", 8: "agosto",
        9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
    }
    mes = meses[data_input.month]
    
    prompt = f"""
    Como redator, Elabore um texto contextual discursivo de 3-4 parágrafos para uma pauta de conteúdo.

    Informações da pauta:
    - Produto: {product_name}
    - Ação/tema: {action}
    - Mês de publicação: {mes}
    - Formato principal: {formato_principal}
    - Conteúdo original: {content}


    Instruções:
    - Escreva em formato discursivo e fluido, com 3-4 parágrafos bem estruturados
    - Mantenha tom técnico mas acessível, adequado para produtores rurais
    - Contextualize a importância do tema para a cultura e época do ano
    - Explique por que este conteúdo é relevante neste momento
    - Inclua considerações sobre o público-alvo e objetivos da comunicação
    - Não repita literalmente a descrição do produto, mas a incorpore naturalmente no texto
    - Use linguagem persuasiva mas factual, baseada em dados técnicos

    Formato: Texto corrido em português brasileiro
    """
    
    try:
        response = modelo_texto.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erro ao gerar contexto: {str(e)}"

def generate_platform_strategy(product_name, culture, action, content):
    """Gera estratégia por plataforma usando Gemini"""
    if not gemini_api_key:
        return "API key do Gemini não configurada. Estratégias por plataforma não disponíveis."
    
    prompt = f"""
    Como especialista em mídias sociais para o agronegócio, crie uma estratégia de conteúdo detalhada:

    PRODUTO: {product_name}
    CONTEÚDO ORIGINAL: {content}

    FORNECER ESTRATÉGIA PARA:
    - Instagram (Feed, Reels, Stories)
    - Facebook 
    - LinkedIn
    - WhatsApp Business
    - YouTube

    INCLUIR PARA CADA PLATAFORMA:
    1. Tipo de conteúdo recomendado
    2. Formato ideal (vídeo, carrossel, estático, etc.)
    3. Tom de voz apropriado
    4. CTA específico
    5. Melhores práticas

    Formato: Texto claro com seções bem definidas
    """
    
    try:
        response = modelo_texto.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erro ao gerar estratégia: {str(e)}"



# --- Interface Principal ---
st.sidebar.title(f"🤖 Bem-vindo, {get_current_user().get('nome', 'Usuário')}!")
st.sidebar.info(f"**Squad:** {get_current_squad()}")
st.sidebar.info(f"**Agente selecionado:** {agente_selecionado['nome']}")

# Botão de logout na sidebar
if st.sidebar.button("🚪 Sair", key="logout_btn"):
    for key in ["logged_in", "user", "admin_password_correct", "admin_user", "agente_selecionado"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# Botão para trocar agente
if st.sidebar.button("🔄 Trocar Agente", key="trocar_agente_global"):
    st.session_state.agente_selecionado = None
    st.session_state.messages = []
    st.rerun()

# --- SELECTBOX PARA TROCAR AGENTE ACIMA DAS ABAS ---
st.title("🤖 Agente BD")

# Carregar agentes disponíveis
agentes = listar_agentes()

if agentes:
    # Preparar opções para o selectbox
    opcoes_agentes = []
    for agente in agentes:
        agente_completo = obter_agente_com_heranca(agente['_id'])
        if agente_completo:  # Só adiciona se tiver permissão
            descricao = f"{agente['nome']} - {agente.get('categoria', 'Social')}"
            if agente.get('agente_mae_id'):
                descricao += " 🔗"
            # Adicionar indicador de squad
            squad_permitido = agente.get('squad_permitido', 'Todos')
            descricao += f" 👥{squad_permitido}"
            opcoes_agentes.append((descricao, agente_completo))
    
    if opcoes_agentes:
        # Encontrar o índice atual
        indice_atual = 0
        for i, (desc, agente) in enumerate(opcoes_agentes):
            if agente['_id'] == st.session_state.agente_selecionado['_id']:
                indice_atual = i
                break
        
        # Selectbox para trocar agente
        col1, col2 = st.columns([3, 1])
        with col1:
            novo_agente_desc = st.selectbox(
                "Selecionar Agente:",
                options=[op[0] for op in opcoes_agentes],
                index=indice_atual,
                key="selectbox_trocar_agente"
            )
        with col2:
            if st.button("🔄 Trocar", key="botao_trocar_agente"):
                # Encontrar o agente completo correspondente
                for desc, agente in opcoes_agentes:
                    if desc == novo_agente_desc:
                        st.session_state.agente_selecionado = agente
                        st.session_state.messages = []
                        st.success(f"✅ Agente alterado para '{agente['nome']}'!")
                        st.rerun()
                        break
    else:
        st.info("Nenhum agente disponível com as permissões atuais.")

# Menu de abas - DETERMINAR QUAIS ABAS MOSTRAR
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

# Criar abas dinamicamente
tabs = st.tabs(abas_base)

# Mapear abas para suas respectivas funcionalidades
tab_mapping = {}
for i, aba in enumerate(abas_base):
    tab_mapping[aba] = tabs[i]

# --- ABA: CHAT ---
with tab_mapping["💬 Chat"]:
    st.header("💬 Chat com Agente")
    
    # Inicializar session_state se não existir
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'segmentos_selecionados' not in st.session_state:
        st.session_state.segmentos_selecionados = []
    if 'show_historico' not in st.session_state:
        st.session_state.show_historico = False
    if 'modelo_chat' not in st.session_state:
        st.session_state.modelo_chat = "Gemini"
    
    agente = st.session_state.agente_selecionado
    st.subheader(f"Conversando com: {agente['nome']}")
    
    # Seletor de modelo na sidebar do chat
    st.sidebar.subheader("🤖 Configurações do Modelo")
    modelo_chat = st.sidebar.selectbox(
        "Escolha o modelo:",
        ["Gemini", "Claude"],
        key="modelo_chat_selector",
        index=0 if st.session_state.modelo_chat == "Gemini" else 1
    )
    st.session_state.modelo_chat = modelo_chat
    
    # Status dos modelos
    if modelo_chat == "Gemini" and not gemini_api_key:
        st.sidebar.error("❌ Gemini não disponível")
    elif modelo_chat == "Claude" and not anthropic_api_key:
        st.sidebar.error("❌ Claude não disponível")
    else:
        st.sidebar.success(f"✅ {modelo_chat} ativo")
    
    
    
    # Controles de segmentos na sidebar do chat
    st.sidebar.subheader("🔧 Configurações do Agente")
    st.sidebar.write("Selecione quais bases de conhecimento usar:")
    
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
    
    # Exibir status dos segmentos
    if segmentos_selecionados:
        st.sidebar.success(f"✅ Usando {len(segmentos_selecionados)} segmento(s)")
    else:
        st.sidebar.warning("⚠️ Nenhum segmento selecionado")
    
    # Indicador de posição na conversa
    if len(st.session_state.messages) > 4:
        st.caption(f"📄 Conversa com {len(st.session_state.messages)} mensagens")
    
    # CORREÇÃO: Exibir histórico de mensagens DENTRO do contexto correto
    # Verificar se messages existe e é iterável
    if hasattr(st.session_state, 'messages') and st.session_state.messages:
        for message in st.session_state.messages:
            # Verificar se message é um dicionário e tem a chave 'role'
            if isinstance(message, dict) and "role" in message:
                with st.chat_message(message["role"]):
                    st.markdown(message.get("content", ""))
            else:
                # Se a estrutura não for a esperada, pular esta mensagem
                continue
    else:
        # Se não houver mensagens, mostrar estado vazio
        st.info("💬 Inicie uma conversa digitando uma mensagem abaixo!")
    
    # Input do usuário
    if prompt := st.chat_input("Digite sua mensagem..."):
        # Adicionar mensagem do usuário ao histórico
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Construir contexto com segmentos selecionados
        contexto = construir_contexto(
            agente, 
            st.session_state.segmentos_selecionados, 
            st.session_state.messages
        )
        
        # Gerar resposta
        with st.chat_message("assistant"):
            with st.spinner('Pensando...'):
                try:
                    resposta = gerar_resposta_modelo(
                        contexto, 
                        st.session_state.modelo_chat,
                        contexto
                    )
                    st.markdown(resposta)
                    
                    # Adicionar ao histórico
                    st.session_state.messages.append({"role": "assistant", "content": resposta})
                    
                    # Salvar conversa com segmentos utilizados
                    salvar_conversa(
                        agente['_id'], 
                        st.session_state.messages,
                        st.session_state.segmentos_selecionados
                    )
                    
                except Exception as e:
                    st.error(f"Erro ao gerar resposta: {str(e)}")

# --- ABA: GERENCIAMENTO DE AGENTES (MODIFICADA PARA SQUADS) ---
with tab_mapping["⚙️ Gerenciar Agentes"]:
    st.header("Gerenciamento de Agentes")
    
    # Verificar autenticação apenas para gerenciamento
    current_user = get_current_user()
    current_squad = get_current_squad()
    
    if current_squad not in ["admin", "Syngenta", "SME", "Enterprise"]:
        st.warning("Acesso restrito a usuários autorizados")
    else:
        # Para admin, verificar senha adicional
        if current_squad == "admin":
            if not check_admin_password():
                st.warning("Digite a senha de administrador")
            else:
                st.write(f'Bem-vindo administrador!')
        else:
            st.write(f'Bem-vindo {current_user.get("nome", "Usuário")} do squad {current_squad}!')
            
        # Subabas para gerenciamento
        sub_tab1, sub_tab2, sub_tab3 = st.tabs(["Criar Agente", "Editar Agente", "Gerenciar Agentes"])
        
        with sub_tab1:
            st.subheader("Criar Novo Agente")
            
            with st.form("form_criar_agente"):
                nome_agente = st.text_input("Nome do Agente:")
                
                # Seleção de categoria - AGORA COM MONITORAMENTO
                categoria = st.selectbox(
                    "Categoria:",
                    ["Social", "SEO", "Conteúdo", "Monitoramento"],
                    help="Organize o agente por área de atuação"
                )
                
                # NOVO: Seleção de squad permitido
                squad_permitido = st.selectbox(
                    "Squad Permitido:",
                    ["Todos", "Syngenta", "SME", "Enterprise"],
                    help="Selecione qual squad pode ver e usar este agente"
                )
                
                # Configurações específicas para agentes de monitoramento
                if categoria == "Monitoramento":
                    st.info("🔍 **Agente de Monitoramento**: Este agente será usado apenas na aba de Monitoramento de Redes e terá uma estrutura simplificada.")
                    
                    # Para monitoramento, apenas base de conhecimento
                    base_conhecimento = st.text_area(
                        "Base de Conhecimento para Monitoramento:", 
                        height=300,
                        placeholder="""Cole aqui a base de conhecimento específica para monitoramento de redes sociais.

PERSONALIDADE: Especialista técnico do agronegócio com habilidade social - "Especialista que fala como gente"

TOM DE VOZ:
- Técnico, confiável e seguro, mas acessível
- Evita exageros e promessas vazias
- Sempre embasado em fatos e ciência
- Frases curtas e diretas, mais simpáticas
- Toque de leveza e ironia pontual quando o contexto permite

PRODUTOS SYN:
- Fortenza: Tratamento de sementes inseticida para Cerrado
- Verdatis: Inseticida com tecnologia PLINAZOLIN
- Megafol: Bioativador natural
- Miravis Duo: Fungicida para controle de manchas foliares

DIRETRIZES:
- NÃO inventar informações técnicas
- Sempre basear respostas em fatos
- Manter tom profissional mas acessível
- Adaptar resposta ao tipo de pergunta""",
                        help="Esta base será usada exclusivamente para monitoramento de redes sociais"
                    )
                    
                    # Campos específicos ocultos para monitoramento
                    system_prompt = ""
                    comments = ""
                    planejamento = ""
                    criar_como_filho = False
                    agente_mae_id = None
                    herdar_elementos = []
                    
                else:
                    # Para outras categorias, manter estrutura original
                    criar_como_filho = st.checkbox("Criar como agente filho (herdar elementos)")
                    
                    agente_mae_id = None
                    herdar_elementos = []
                    
                    if criar_como_filho:
                        # Listar TODOS os agentes disponíveis para herança (exceto monitoramento)
                        agentes_mae = listar_agentes_para_heranca()
                        agentes_mae = [agente for agente in agentes_mae if agente.get('categoria') != 'Monitoramento']
                        
                        if agentes_mae:
                            agente_mae_options = {f"{agente['nome']} ({agente.get('categoria', 'Social')})": agente['_id'] for agente in agentes_mae}
                            agente_mae_selecionado = st.selectbox(
                                "Agente Mãe:",
                                list(agente_mae_options.keys()),
                                help="Selecione o agente do qual este agente irá herdar elementos"
                            )
                            agente_mae_id = agente_mae_options[agente_mae_selecionado]
                            
                            st.subheader("Elementos para Herdar")
                            herdar_elementos = st.multiselect(
                                "Selecione os elementos a herdar do agente mãe:",
                                ["system_prompt", "base_conhecimento", "comments", "planejamento"],
                                help="Estes elementos serão herdados do agente mãe se não preenchidos abaixo"
                            )
                        else:
                            st.info("Nenhum agente disponível para herança. Crie primeiro um agente mãe.")
                    
                    system_prompt = st.text_area("Prompt de Sistema:", height=150, 
                                                placeholder="Ex: Você é um assistente especializado em...",
                                                help="Deixe vazio se for herdar do agente mãe")
                    base_conhecimento = st.text_area("Brand Guidelines:", height=200,
                                                   placeholder="Cole aqui informações, diretrizes, dados...",
                                                   help="Deixe vazio se for herdar do agente mãe")
                    comments = st.text_area("Diário do cliente:", height=200,
                                                   placeholder="Cole aqui o diário de acompanhamento do cliente",
                                                   help="Deixe vazio se for herdar do agente mãe")
                    planejamento = st.text_area("Planejamento:", height=200,
                                               placeholder="Estratégias, planejamentos, cronogramas...",
                                               help="Deixe vazio se for herdar do agente mãe")
                
                submitted = st.form_submit_button("Criar Agente")
                if submitted:
                    if nome_agente:
                        agente_id = criar_agente(
                            nome_agente, 
                            system_prompt, 
                            base_conhecimento, 
                            comments, 
                            planejamento,
                            categoria,
                            squad_permitido,  # Novo campo
                            agente_mae_id if criar_como_filho else None,
                            herdar_elementos if criar_como_filho else []
                        )
                        st.success(f"Agente '{nome_agente}' criado com sucesso na categoria {categoria} para o squad {squad_permitido}!")
                    else:
                        st.error("Nome é obrigatório!")
        
        with sub_tab2:
            st.subheader("Editar Agente Existente")
            
            agentes = listar_agentes()
            if agentes:
                agente_options = {agente['nome']: agente for agente in agentes}
                agente_selecionado_nome = st.selectbox("Selecione o agente para editar:", 
                                                     list(agente_options.keys()))
                
                if agente_selecionado_nome:
                    agente = agente_options[agente_selecionado_nome]
                    
                    with st.form("form_editar_agente"):
                        novo_nome = st.text_input("Nome do Agente:", value=agente['nome'])
                        
                        # Categoria - AGORA COM MONITORAMENTO
                        categorias_disponiveis = ["Social", "SEO", "Conteúdo", "Monitoramento"]
                        if agente.get('categoria') in categorias_disponiveis:
                            index_categoria = categorias_disponiveis.index(agente.get('categoria', 'Social'))
                        else:
                            index_categoria = 0
                            
                        nova_categoria = st.selectbox(
                            "Categoria:",
                            categorias_disponiveis,
                            index=index_categoria,
                            help="Organize o agente por área de atuação"
                        )
                        
                        # NOVO: Squad permitido
                        squads_disponiveis = ["Todos", "Syngenta", "SME", "Enterprise"]
                        squad_atual = agente.get('squad_permitido', 'Todos')
                        if squad_atual in squads_disponiveis:
                            index_squad = squads_disponiveis.index(squad_atual)
                        else:
                            index_squad = 0
                            
                        novo_squad_permitido = st.selectbox(
                            "Squad Permitido:",
                            squads_disponiveis,
                            index=index_squad,
                            help="Selecione qual squad pode ver e usar este agente"
                        )
                        
                        # Interface diferente para agentes de monitoramento
                        if nova_categoria == "Monitoramento":
                            st.info("🔍 **Agente de Monitoramento**: Este agente será usado apenas na aba de Monitoramento de Redes.")
                            
                            # Para monitoramento, apenas base de conhecimento
                            nova_base = st.text_area(
                                "Base de Conhecimento para Monitoramento:", 
                                value=agente.get('base_conhecimento', ''),
                                height=300,
                                help="Esta base será usada exclusivamente para monitoramento de redes sociais"
                            )
                            
                            # Campos específicos ocultos para monitoramento
                            novo_prompt = ""
                            nova_comment = ""
                            novo_planejamento = ""
                            agente_mae_id = None
                            herdar_elementos = []
                            
                            # Remover herança se existir
                            if agente.get('agente_mae_id'):
                                st.warning("⚠️ Agentes de monitoramento não suportam herança. A herança será removida.")
                            
                        else:
                            # Para outras categorias, manter estrutura original
                            
                            # Informações de herança (apenas se não for monitoramento)
                            if agente.get('agente_mae_id'):
                                agente_mae = obter_agente(agente['agente_mae_id'])
                                if agente_mae:
                                    st.info(f"🔗 Este agente é filho de: {agente_mae['nome']}")
                                    st.write(f"Elementos herdados: {', '.join(agente.get('herdar_elementos', []))}")
                            
                            # Opção para tornar independente
                            if agente.get('agente_mae_id'):
                                tornar_independente = st.checkbox("Tornar agente independente (remover herança)")
                                if tornar_independente:
                                    agente_mae_id = None
                                    herdar_elementos = []
                                else:
                                    agente_mae_id = agente.get('agente_mae_id')
                                    herdar_elementos = agente.get('herdar_elementos', [])
                            else:
                                agente_mae_id = None
                                herdar_elementos = []
                                # Opção para adicionar herança
                                adicionar_heranca = st.checkbox("Adicionar herança de agente mãe")
                                if adicionar_heranca:
                                    # Listar TODOS os agentes disponíveis para herança (excluindo o próprio e monitoramento)
                                    agentes_mae = listar_agentes_para_heranca(agente['_id'])
                                    agentes_mae = [agente_mae for agente_mae in agentes_mae if agente_mae.get('categoria') != 'Monitoramento']
                                    
                                    if agentes_mae:
                                        agente_mae_options = {f"{agente_mae['nome']} ({agente_mae.get('categoria', 'Social')})": agente_mae['_id'] for agente_mae in agentes_mae}
                                        if agente_mae_options:
                                            agente_mae_selecionado = st.selectbox(
                                                "Agente Mãe:",
                                                list(agente_mae_options.keys()),
                                                help="Selecione o agente do qual este agente irá herdar elementos"
                                            )
                                            agente_mae_id = agente_mae_options[agente_mae_selecionado]
                                            herdar_elementos = st.multiselect(
                                                "Elementos para herdar:",
                                                ["system_prompt", "base_conhecimento", "comments", "planejamento"],
                                                default=herdar_elementos
                                            )
                                        else:
                                            st.info("Nenhum agente disponível para herança.")
                                    else:
                                        st.info("Nenhum agente disponível para herança.")
                            
                            novo_prompt = st.text_area("Prompt de Sistema:", value=agente['system_prompt'], height=150)
                            nova_base = st.text_area("Brand Guidelines:", value=agente.get('base_conhecimento', ''), height=200)
                            nova_comment = st.text_area("Diário:", value=agente.get('comments', ''), height=200)
                            novo_planejamento = st.text_area("Planejamento:", value=agente.get('planejamento', ''), height=200)
                        
                        submitted = st.form_submit_button("Atualizar Agente")
                        if submitted:
                            if novo_nome:
                                atualizar_agente(
                                    agente['_id'], 
                                    novo_nome, 
                                    novo_prompt, 
                                    nova_base, 
                                    nova_comment, 
                                    novo_planejamento,
                                    nova_categoria,
                                    novo_squad_permitido,  # Novo campo
                                    agente_mae_id,
                                    herdar_elementos
                                )
                                st.success(f"Agente '{novo_nome}' atualizado com sucesso!")
                                st.rerun()
                            else:
                                st.error("Nome é obrigatório!")
            else:
                st.info("Nenhum agente criado ainda.")
        
        with sub_tab3:
            st.subheader("Gerenciar Agentes")
            
            # Mostrar informações do usuário atual
            current_squad = get_current_squad()
            if current_squad == "admin":
                st.info("👑 Modo Administrador: Visualizando todos os agentes do sistema")
            else:
                st.info(f"👤 Visualizando agentes do squad {current_squad} e squad 'Todos'")
            
            # Filtros por categoria - AGORA COM MONITORAMENTO
            categorias = ["Todos", "Social", "SEO", "Conteúdo", "Monitoramento"]
            categoria_filtro = st.selectbox("Filtrar por categoria:", categorias)
            
            agentes = listar_agentes()
            
            # Aplicar filtro
            if categoria_filtro != "Todos":
                agentes = [agente for agente in agentes if agente.get('categoria') == categoria_filtro]
            
            if agentes:
                for i, agente in enumerate(agentes):
                    with st.expander(f"{agente['nome']} - {agente.get('categoria', 'Social')} - Squad: {agente.get('squad_permitido', 'Todos')} - Criado em {agente['data_criacao'].strftime('%d/%m/%Y')}"):
                        
                        # Mostrar proprietário se for admin
                        owner_info = ""
                        if current_squad == "admin" and agente.get('criado_por'):
                            owner_info = f" | 👤 {agente['criado_por']}"
                            st.write(f"**Proprietário:** {agente['criado_por']}")
                            st.write(f"**Squad do Criador:** {agente.get('criado_por_squad', 'N/A')}")
                        
                        # Mostrar informações específicas por categoria
                        if agente.get('categoria') == 'Monitoramento':
                            st.info("🔍 **Agente de Monitoramento** - Usado apenas na aba de Monitoramento de Redes")
                            
                            if agente.get('base_conhecimento'):
                                st.write(f"**Base de Conhecimento:** {agente['base_conhecimento'][:200]}...")
                            else:
                                st.warning("⚠️ Base de conhecimento não configurada")
                            

                            
                        else:
                            # Para outras categorias, mostrar estrutura completa
                            if agente.get('agente_mae_id'):
                                agente_mae = obter_agente(agente['agente_mae_id'])
                                if agente_mae:
                                    st.write(f"**🔗 Herda de:** {agente_mae['nome']}")
                                    st.write(f"**Elementos herdados:** {', '.join(agente.get('herdar_elementos', []))}")
                            
                            st.write(f"**Prompt de Sistema:** {agente['system_prompt'][:100]}..." if agente['system_prompt'] else "**Prompt de Sistema:** (herdado ou vazio)")
                            if agente.get('base_conhecimento'):
                                st.write(f"**Brand Guidelines:** {agente['base_conhecimento'][:200]}...")
                            if agente.get('comments'):
                                st.write(f"**Diário do cliente:** {agente['comments'][:200]}...")
                            if agente.get('planejamento'):
                                st.write(f"**Planejamento:** {agente['planejamento'][:200]}...")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("Selecionar para Chat", key=f"select_{i}"):
                                agente_completo = obter_agente_com_heranca(agente['_id'])
                                st.session_state.agente_selecionado = agente_completo
                                st.session_state.messages = []
                                st.success(f"Agente '{agente['nome']}' selecionado!")
                                st.rerun()
                        with col2:
                            if st.button("Desativar", key=f"delete_{i}"):
                                desativar_agente(agente['_id'])
                                st.success(f"Agente '{agente['nome']}' desativado!")
                                st.rerun()
            else:
                st.info("Nenhum agente encontrado para esta categoria.")

if "📋 Briefing" in tab_mapping:
    with tab_mapping["📋 Briefing"]:
        st.header("📋 Gerador de Briefings - SYN")
        st.markdown("Digite o conteúdo da célula do calendário para gerar um briefing completo no padrão SYN.")
        
        # Abas para diferentes modos de operação
        tab1, tab2 = st.tabs(["Briefing Individual", "Processamento em Lote (CSV)"])
        
        with tab1:
            st.markdown("### Digite o conteúdo da célula do calendário")

            content_input = st.text_area(
                "Conteúdo da célula:",
                placeholder="Ex: megafol - série - potencial máximo, todo o tempo",
                height=100,
                help="Cole aqui o conteúdo exato da célula do calendário do Sheets",
                key="individual_content"
            )

            # Campos opcionais para ajuste
            col1, col2 = st.columns(2)

            with col1:
                data_input = st.date_input("Data prevista:", value=datetime.datetime.now(), key="individual_date")

            with col2:
                formato_principal = st.selectbox(
                    "Formato principal:",
                    ["Reels + capa", "Carrossel + stories", "Blog + redes", "Vídeo + stories", "Multiplataforma"],
                    key="individual_format"
                )

            generate_btn = st.button("Gerar Briefing Individual", type="primary", key="individual_btn")

            # Processamento e exibição do briefing individual
            if generate_btn and content_input:
                with st.spinner("Analisando conteúdo e gerando briefing..."):
                    # Extrair informações do produto
                    product, culture, action = extract_product_info(content_input)
                    
                    if product and product in PRODUCT_DESCRIPTIONS:
                        # Gerar briefing completo
                        briefing = generate_briefing(content_input, product, culture, action, data_input, formato_principal)
                        
                        # Exibir briefing
                        st.markdown("## Briefing Gerado")
                        st.text(briefing)
                        
                        # Botão de download
                        st.download_button(
                            label="Baixar Briefing",
                            data=briefing,
                            file_name=f"briefing_{product}_{data_input.strftime('%Y%m%d')}.txt",
                            mime="text/plain",
                            key="individual_download"
                        )
                        
                        # Informações extras
                        with st.expander("Informações Extraídas"):
                            st.write(f"Produto: {product}")
                            st.write(f"Cultura: {culture}")
                            st.write(f"Ação: {action}")
                            st.write(f"Data: {data_input.strftime('%d/%m/%Y')}")
                            st.write(f"Formato principal: {formato_principal}")
                            st.write(f"Descrição: {PRODUCT_DESCRIPTIONS[product]}")
                            
                    elif product:
                        st.warning(f"Produto '{product}' não encontrado no dicionário. Verifique a grafia.")
                        st.info("Produtos disponíveis: " + ", ".join(list(PRODUCT_DESCRIPTIONS.keys())[:10]) + "...")
                    else:
                        st.error("Não foi possível identificar um produto no conteúdo. Tente formatos como:")
                        st.code("""
                        megafol - série - potencial máximo, todo o tempo
                        verdavis - soja - depoimento produtor
                        engeo pleno s - milho - controle percevejo
                        miravis duo - algodão - reforço preventivo
                        """)

        with tab2:
            st.markdown("### Processamento em Lote via CSV")
            
            st.info("""
            Faça upload de um arquivo CSV exportado do Google Sheets.
            O sistema irá processar cada linha a partir da segunda linha (ignorando cabeçalhos)
            e gerar briefings apenas para as linhas que contêm produtos reconhecidos.
            """)
            
            uploaded_file = st.file_uploader(
                "Escolha o arquivo CSV", 
                type=['csv'],
                help="Selecione o arquivo CSV exportado do Google Sheets"
            )
            
            if uploaded_file is not None:
                try:
                    # Ler o CSV
                    df = pd.read_csv(uploaded_file)
                    st.success(f"CSV carregado com sucesso! {len(df)} linhas encontradas.")
                    
                    # Mostrar prévia do arquivo
                    with st.expander("Visualizar primeiras linhas do CSV"):
                        st.dataframe(df.head())
                    
                    # Configurações para processamento em lote
                    st.markdown("### Configurações do Processamento em Lote")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        data_padrao = st.date_input(
                            "Data padrão para todos os briefings:",
                            value=datetime.datetime.now(),
                            key="batch_date"
                        )
                    
                    with col2:
                        formato_padrao = st.selectbox(
                            "Formato principal padrão:",
                            ["Reels + capa", "Carrossel + stories", "Blog + redes", "Vídeo + stories", "Multiplataforma"],
                            key="batch_format"
                        )
                    
                    # Identificar coluna com conteúdo
                    colunas = df.columns.tolist()
                    coluna_conteudo = st.selectbox(
                        "Selecione a coluna que contém o conteúdo das células:",
                        colunas,
                        help="Selecione a coluna que contém os textos das células do calendário"
                    )
                    
                    processar_lote = st.button("Processar CSV e Gerar Briefings", type="primary", key="batch_btn")
                    
                    if processar_lote:
                        briefings_gerados = []
                        linhas_processadas = 0
                        linhas_com_produto = 0
                        
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        for index, row in df.iterrows():
                            linhas_processadas += 1
                            progress_bar.progress(linhas_processadas / len(df))
                            status_text.text(f"Processando linha {linhas_processadas} de {len(df)}...")
                            
                            # Pular a primeira linha (cabeçalhos)
                            if index == 0:
                                continue
                            
                            # Obter conteúdo da célula
                            content = str(row[coluna_conteudo]) if pd.notna(row[coluna_conteudo]) else ""
                            
                            if content:
                                # Extrair informações do produto
                                product, culture, action = extract_product_info(content)
                                
                                if product and product in PRODUCT_DESCRIPTIONS:
                                    linhas_com_produto += 1
                                    # Gerar briefing
                                    briefing = generate_briefing(
                                        content, 
                                        product, 
                                        culture, 
                                        action, 
                                        data_padrao, 
                                        formato_padrao
                                    )
                                    
                                    briefings_gerados.append({
                                        'linha': index + 1,
                                        'produto': product,
                                        'conteudo': content,
                                        'briefing': briefing,
                                        'arquivo': f"briefing_{product}_{index+1}.txt"
                                    })
                        
                        progress_bar.empty()
                        status_text.empty()
                        
                        # Resultados do processamento
                        st.success(f"Processamento concluído! {linhas_com_produto} briefings gerados de {linhas_processadas-1} linhas processadas.")
                        
                        if briefings_gerados:
                            # Exibir resumo
                            st.markdown("### Briefings Gerados")
                            resumo_df = pd.DataFrame([{
                                'Linha': b['linha'],
                                'Produto': b['produto'],
                                'Conteúdo': b['conteudo'][:50] + '...' if len(b['conteudo']) > 50 else b['conteudo']
                            } for b in briefings_gerados])
                            
                            st.dataframe(resumo_df)
                            
                            # Criar arquivo ZIP com todos os briefings
                            import zipfile
                            from io import BytesIO
                            
                            zip_buffer = BytesIO()
                            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                for briefing_info in briefings_gerados:
                                    zip_file.writestr(
                                        briefing_info['arquivo'], 
                                        briefing_info['briefing']
                                    )
                            
                            zip_buffer.seek(0)
                            
                            # Botão para download do ZIP
                            st.download_button(
                                label="📥 Baixar Todos os Briefings (ZIP)",
                                data=zip_buffer,
                                file_name="briefings_syn.zip",
                                mime="application/zip",
                                key="batch_download_zip"
                            )
                            
                            # Também permitir download individual
                            st.markdown("---")
                            st.markdown("### Download Individual")
                            
                            for briefing_info in briefings_gerados:
                                col1, col2 = st.columns([3, 1])
                                with col1:
                                    st.text(f"Linha {briefing_info['linha']}: {briefing_info['produto']} - {briefing_info['conteudo'][:30]}...")
                                with col2:
                                    st.download_button(
                                        label="📄 Baixar",
                                        data=briefing_info['briefing'],
                                        file_name=briefing_info['arquivo'],
                                        mime="text/plain",
                                        key=f"download_{briefing_info['linha']}"
                                    )
                        else:
                            st.warning("Nenhum briefing foi gerado. Verifique se o CSV contém produtos reconhecidos.")
                            st.info("Produtos reconhecidos: " + ", ".join(list(PRODUCT_DESCRIPTIONS.keys())[:15]) + "...")
                            
                except Exception as e:
                    st.error(f"Erro ao processar o arquivo CSV: {str(e)}")

        # Seção de exemplos
        with st.expander("Exemplos de Conteúdo", expanded=True):
            st.markdown("""
            Formatos Reconhecidos:

            Padrão: PRODUTO - CULTURA - AÇÃO ou PRODUTO - AÇÃO

            Exemplos:
            - megafol - série - potencial máximo, todo o tempo
            - verdavis - milho - resultados do produto
            - engeo pleno s - soja - resultados GTEC
            - miravis duo - algodão - depoimento produtor
            - axial - trigo - reforço pós-emergente
            - manejo limpo - importância manejo antecipado
            - certano HF - a jornada de certano
            - elestal neo - soja - depoimento de produtor
            - fortenza - a jornada da semente mais forte - EP 01
            - reverb - vídeo conceito
            """)

        # Lista de produtos reconhecidos
        with st.expander("Produtos Reconhecidos"):
            col1, col2, col3 = st.columns(3)
            products = list(PRODUCT_DESCRIPTIONS.keys())
            
            with col1:
                for product in products[:10]:
                    st.write(f"• {product}")
            
            with col2:
                for product in products[10:20]:
                    st.write(f"• {product}")
            
            with col3:
                for product in products[20:]:
                    st.write(f"• {product}")

        # Rodapé
        st.markdown("---")
        st.caption("Ferramenta de geração automática de briefings - Padrão SYN. Digite o conteúdo da célula do calendário para gerar briefings completos.")

def criar_analisadores_especialistas(contexto_agente, contexto_global):
    """Cria prompts especializados para cada área de análise"""
    
    analisadores = {
        'ortografia': {
            'nome': '🔤 Especialista em Ortografia e Gramática',
            'prompt': f"""
{contexto_global}

## FUNÇÃO: ESPECIALISTA EM ORTOGRAFIA E GRAMÁTICA PORTUGUÊS BR

**Sua tarefa:** Analisar EXCLUSIVAMENTE aspectos ortográficos e gramaticais.

### CRITÉRIOS DE ANÁLISE:
1. **Ortografia** - Erros de escrita
2. **Gramática** - Concordância, regência, colocação
3. **Pontuação** - Uso de vírgulas, pontos, etc.
4. **Acentuação** - Erros de acentuação
5. **Padrão Culto** - Conformidade com norma culta

### FORMATO DE RESPOSTA OBRIGATÓRIO:

## 🔤 RELATÓRIO ORTOGRÁFICO

### ✅ ACERTOS
- [Itens corretos]

### ❌ ERROS IDENTIFICADOS
- [Lista específica de erros com correções]


### 💡 SUGESTÕES DE MELHORIA
- [Recomendações específicas]
"""
        },
        'lexico': {
            'nome': '📚 Especialista em Léxico e Vocabulário',
            'prompt': f"""
{contexto_agente}
{contexto_global}

## FUNÇÃO: ESPECIALISTA EM LÉXICO E VOCABULÁRIO

**Sua tarefa:** Analisar EXCLUSIVAMENTE aspectos lexicais e de vocabulário.

### CRITÉRIOS DE ANÁLISE:
1. **Variedade Lexical** - Riqueza de vocabulário
2. **Precisão Semântica** - Uso adequado das palavras
3. **Repetição** - Palavras ou expressões repetidas em excesso
4. **Jargões** - Uso inadequado de termos técnicos
5. **Clareza** - Facilidade de compreensão

### FORMATO DE RESPOSTA OBRIGATÓRIO:

## 📚 RELATÓRIO LEXICAL

### ✅ VOCABULÁRIO ADEQUADO
- [Pontos fortes do vocabulário]

### ⚠️ ASPECTOS A MELHORAR
- [Problemas lexicais identificados]

### 🔄 SUGESTÕES DE SINÔNIMOS
- [Palavras para substituir]

"""
        },
        'branding': {
            'nome': '🎨 Especialista em Branding e Identidade',
            'prompt': f"""
{contexto_agente}
{contexto_global}

## FUNÇÃO: ESPECIALISTA EM BRANDING E IDENTIDADE

**Sua tarefa:** Analisar EXCLUSIVAMENTE conformidade com diretrizes de branding.

### CRITÉRIOS DE ANÁLISE:
1. **Tom de Voz** - Alinhamento com personalidade da marca
2. **Mensagem Central** - Consistência da mensagem
3. **Valores da Marca** - Reflexo dos valores organizacionais
4. **Público-Alvo** - Adequação ao público pretendido
5. **Diferenciação** - Elementos únicos da marca

### FORMATO DE RESPOSTA OBRIGATÓRIO:

## 🎨 RELATÓRIO DE BRANDING

### ✅ ALINHAMENTOS
- [Elementos que seguem as diretrizes]

### ❌ DESVIOS IDENTIFICADOS
- [Elementos fora do padrão da marca]


### 💡 RECOMENDAÇÕES ESTRATÉGICAS
- [Sugestões para melhor alinhamento]
"""
        
        
        }
    }
    
    return analisadores

def executar_analise_especializada(texto, nome_arquivo, analisadores):
    """Executa análise com múltiplos especialistas"""
    
    resultados = {}
    
    for area, config in analisadores.items():
        with st.spinner(f"Executando {config['nome']}..."):
            try:
                prompt_completo = f"""
{config['prompt']}

###BEGIN TEXTO PARA ANÁLISE###
**Arquivo:** {nome_arquivo}
**Conteúdo:**
{texto[:8000]}
###END TEXTO PARA ANÁLISE###

Por favor, forneça sua análise no formato solicitado.
"""
                
                resposta = modelo_texto.generate_content(prompt_completo)
                resultados[area] = {
                    'nome': config['nome'],
                    'analise': resposta.text,
                }
                
            except Exception as e:
                resultados[area] = {
                    'nome': config['nome'],
                    'analise': f"❌ Erro na análise: {str(e)}",
                    'score': 0
                }
    
    return resultados

def extrair_score(texto_analise):
    """Extrai score numérico do texto de análise"""
    import re
    padrao = r'SCORE.*?\[(\d+)(?:/10)?\]'
    correspondencias = re.findall(padrao, texto_analise, re.IGNORECASE)
    if correspondencias:
        return int(correspondencias[0])
    return 5  # Score padrão se não encontrar

def gerar_relatorio_consolidado(resultados_especialistas, nome_arquivo):
    """Gera relatório consolidado a partir das análises especializadas"""
    
   
    
    relatorio = f"""
# 📊 RELATÓRIO CONSOLIDADO DE VALIDAÇÃO

**Documento:** {nome_arquivo}
**Data da Análise:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}

"""
    
    # Adicionar scores individuais
    for area, resultado in resultados_especialistas.items():
        emoji = "✅" if resultado['score'] >= 8 else "⚠️" if resultado['score'] >= 6 else "❌"
        relatorio += f"- {emoji} **{resultado['nome']}:** {resultado['score']}/10\n"
    
    relatorio += "\n## 📋 ANÁLISES DETALHADAS POR ESPECIALISTA\n"
    
    # Adicionar análises detalhadas
    for area, resultado in resultados_especialistas.items():
        relatorio += f"\n### {resultado['nome']}\n"
        relatorio += f"{resultado['analise']}\n"
        relatorio += "---\n"
    
    # Resumo executivo
    relatorio += f"""
## 🚀 RESUMO EXECUTIVO


### 🎯 PRÓXIMOS PASSOS RECOMENDADOS:
"""
    
    # Recomendações baseadas nos scores
    areas_baixas = [area for area, resultado in resultados_especialistas.items() if resultado['score'] < 6]
    if areas_baixas:
        relatorio += f"- **Prioridade:** Focar em {', '.join(areas_baixas)}\n"
    
    areas_medianas = [area for area, resultado in resultados_especialistas.items() if 6 <= resultado['score'] < 8]
    if areas_medianas:
        relatorio += f"- **Otimização:** Melhorar {', '.join(areas_medianas)}\n"
    
    relatorio += "- **Manutenção:** Manter as áreas com scores altos\n"
    
    return relatorio

# --- FUNÇÕES ORIGINAIS MANTIDAS ---

def criar_prompt_validacao_preciso(texto, nome_arquivo, contexto_agente):
    """Cria um prompt de validação muito mais preciso para evitar falsos positivos"""
    
    prompt = f"""
{contexto_agente}

###BEGIN TEXTO PARA VALIDAÇÃO###
**Arquivo:** {nome_arquivo}
**Conteúdo:**
{texto[:12000]}
###END TEXTO PARA VALIDAÇÃO###

## FORMATO DE RESPOSTA OBRIGATÓRIO:

### ✅ CONFORMIDADE COM DIRETRIZES
- [Itens que estão alinhados com as diretrizes de branding]

**INCONSISTÊNCIAS COM BRANDING:**
- [Só liste desvios REAIS das diretrizes de branding]

### 💡 TEXTO REVISADO
- [Sugestões para aprimorar]

### 📊 STATUS FINAL
**Documento:** [Aprovado/Necessita ajustes/Reprovado]
**Principais ações necessárias:** [Lista resumida]
"""
    return prompt

def analisar_documento_por_slides(doc, contexto_agente):
    """Analisa documento slide por slide com alta precisão"""
    
    resultados = []
    
    for i, slide in enumerate(doc['slides']):
        with st.spinner(f"Analisando slide {i+1}..."):
            try:
                prompt_slide = f"""
{contexto_agente}

## ANÁLISE POR SLIDE - PRECISÃO ABSOLUTA

###BEGIN TEXTO PARA VALIDAÇÃO###
**SLIDE {i+1}:**
{slide['conteudo'][:2000]}
###END TEXTO PARA VALIDAÇÃO###

**ANÁLISE DO SLIDE {i+1}:**

### ✅ Pontos Fortes:
[O que está bom neste slide]

### ⚠️ Problemas REAIS:
- [Lista CURTA de problemas]

### 💡 Sugestões Específicas:
[Melhorias para ESTE slide específico]

Considere que slides que são introdutórios ou apenas de títulos não precisam de tanto rigor de branding

**STATUS:** [✔️ Aprovado / ⚠️ Ajustes Menores / ❌ Problemas Sérios]
"""
                
                resposta = modelo_texto.generate_content(prompt_slide)
                resultados.append({
                    'slide_num': i+1,
                    'analise': resposta.text,
                    'tem_alteracoes': '❌' in resposta.text or '⚠️' in resposta.text
                })
                
            except Exception as e:
                resultados.append({
                    'slide_num': i+1,
                    'analise': f"❌ Erro na análise do slide: {str(e)}",
                    'tem_alteracoes': False
                })
    
    # Construir relatório consolidado
    relatorio = f"# 📊 RELATÓRIO DE VALIDAÇÃO - {doc['nome']}\n\n"
    relatorio += f"**Total de Slides:** {len(doc['slides'])}\n"
    relatorio += f"**Slides com Alterações:** {sum(1 for r in resultados if r['tem_alteracoes'])}\n\n"
    
    # Slides que precisam de atenção
    slides_com_problemas = [r for r in resultados if r['tem_alteracoes']]
    if slides_com_problemas:
        relatorio += "## 🚨 SLIDES QUE PRECISAM DE ATENÇÃO:\n\n"
        for resultado in slides_com_problemas:
            relatorio += f"### 📋 Slide {resultado['slide_num']}\n"
            relatorio += f"{resultado['analise']}\n\n"
    
    # Resumo executivo
    relatorio += "## 📈 RESUMO EXECUTIVO\n\n"
    if slides_com_problemas:
        relatorio += f"**⚠️ {len(slides_com_problemas)} slide(s) necessitam de ajustes**\n"
        relatorio += f"**✅ {len(doc['slides']) - len(slides_com_problemas)} slide(s) estão adequados**\n"
    else:
        relatorio += "**🎉 Todos os slides estão em conformidade com as diretrizes!**\n"
    
    return relatorio

def extract_text_from_pdf_com_slides(arquivo_pdf):
    """Extrai texto de PDF com informação de páginas"""
    try:
        import PyPDF2
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
        return f"Erro na extração PDF: {str(e)}", []

def extract_text_from_pptx_com_slides(arquivo_pptx):
    """Extrai texto de PPTX com informação de slides"""
    try:
        from pptx import Presentation
        import io
        
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
        return f"Erro na extração PPTX: {str(e)}", []

def extrair_texto_arquivo(arquivo):
    """Extrai texto de arquivos TXT e DOCX"""
    try:
        if arquivo.type == "text/plain":
            return str(arquivo.read(), "utf-8")
        elif arquivo.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            import docx
            import io
            doc = docx.Document(io.BytesIO(arquivo.read()))
            texto = ""
            for para in doc.paragraphs:
                texto += para.text + "\n"
            return texto
        else:
            return f"Tipo não suportado: {arquivo.type}"
    except Exception as e:
        return f"Erro na extração: {str(e)}"

def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF file using multiple methods for better coverage
    """
    text = ""

    # Method 1: Try with pdfplumber (better for some PDFs)
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text
    except Exception as e:
        print(f"pdfplumber failed for {pdf_path}: {e}")

    # Method 2: Fallback to PyPDF2 if pdfplumber didn't extract much text
    if len(text.strip()) < 100:  # If very little text was extracted
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text 
        except Exception as e:
            print(f"PyPDF2 also failed for {pdf_path}: {e}")

    return text

def criar_analisadores_imagem(contexto_agente, contexto_global):
    """Cria analisadores especializados para imagens"""
    
    analisadores = {
        'composicao_visual': {
            'nome': '🎨 Especialista em Composição Visual',
            'prompt': f"""
{contexto_agente}
{contexto_global}

## FUNÇÃO: ESPECIALISTA EM COMPOSIÇÃO VISUAL

**Sua tarefa:** Analisar EXCLUSIVAMENTE a composição visual da imagem.

### CRITÉRIOS DE ANÁLISE:
1. **Balanceamento** - Distribuição equilibrada dos elementos
2. **Hierarquia Visual** - Foco e pontos de atenção
3. **Espaçamento** - Uso adequado do espaço
4. **Proporções** - Relação entre elementos visuais
5. **Harmonia** - Conjunto visual coeso

### FORMATO DE RESPOSTA OBRIGATÓRIO:

## 🎨 RELATÓRIO DE COMPOSIÇÃO VISUAL

### ✅ PONTOS FORTES DA COMPOSIÇÃO
- [Elementos bem compostos]

### ⚠️ PROBLEMAS DE COMPOSIÇÃO
- [Issues de organização visual]

### 📊 SCORE COMPOSIÇÃO: [X/10]

### 💡 SUGESTÕES DE MELHORIA VISUAL
- [Recomendações para melhor composição]
"""
        },
        'cores_branding': {
            'nome': '🌈 Especialista em Cores e Branding',
            'prompt': f"""
{contexto_agente}
{contexto_global}

## FUNÇÃO: ESPECIALISTA EM CORES E BRANDING

**Sua tarefa:** Analisar EXCLUSIVAMENTE cores e alinhamento com branding.

### CRITÉRIOS DE ANÁLISE:
1. **Paleta de Cores** - Cores utilizadas na imagem
2. **Contraste** - Legibilidade e visibilidade
3. **Consistência** - Coerência com identidade visual
4. **Psicologia das Cores** - Efeito emocional das cores
5. **Acessibilidade** - Visibilidade para diferentes usuários

### FORMATO DE RESPOSTA OBRIGATÓRIO:

## 🌈 RELATÓRIO DE CORES E BRANDING

### ✅ CORES ALINHADAS
- [Cores que seguem as diretrizes]

### ❌ PROBLEMAS DE COR
- [Cores fora do padrão]


### 🎯 RECOMENDAÇÕES DE COR
- [Sugestões para paleta de cores]
"""
        },
        'tipografia_texto': {
            'nome': '🔤 Especialista em Tipografia e Texto',
            'prompt': f"""
{contexto_agente}
{contexto_global}

## FUNÇÃO: ESPECIALISTA EM TIPOGRAFIA E TEXTO

**Sua tarefa:** Analisar EXCLUSIVAMENTE tipografia e elementos textuais.

### CRITÉRIOS DE ANÁLISE:
1. **Legibilidade** - Facilidade de leitura do texto
2. **Hierarquia Tipográfica** - Tamanhos e pesos de fonte
3. **Alinhamento** - Organização do texto na imagem
4. **Consistência** - Uso uniforme de fontes
5. **Mensagem Textual** - Conteúdo das palavras

### FORMATO DE RESPOSTA OBRIGATÓRIO:

## 🔤 RELATÓRIO DE TIPOGRAFIA

### ✅ ACERTOS TIPOGRÁFICOS
- [Elementos textuais bem executados]

### ⚠️ PROBLEMAS DE TEXTO
- [Problemas com tipografia e texto - Sejam erros visuais, ortográficos ou lexicais]


### ✏️ SUGESTÕES TIPOGRÁFICAS
- [Melhorias para texto e fontes]
"""
        },
        'elementos_marca': {
            'nome': '🏷️ Especialista em Elementos de Marca',
            'prompt': f"""
{contexto_agente}
{contexto_global}

## FUNÇÃO: ESPECIALISTA EM ELEMENTOS DE MARCA

**Sua tarefa:** Analisar EXCLUSIVAMENTE elementos de identidade visual da marca.

### CRITÉRIOS DE ANÁLISE:
1. **Logo e Identidade** - Uso correto da marca
2. **Elementos Gráficos** - Ícones, padrões, ilustrações
3. **Fotografia** - Estilo e tratamento de imagens
4. **Consistência Visual** - Coerência com guidelines
5. **Diferenciação** - Elementos únicos da marca

### FORMATO DE RESPOSTA OBRIGATÓRIO:

## 🏷️ RELATÓRIO DE ELEMENTOS DE MARCA

### ✅ ELEMENTOS CORRETOS
- [Elementos alinhados com a marca]

### ❌ ELEMENTOS INCORRETOS
- [Elementos fora do padrão]


### 🎨 RECOMENDAÇÕES DE MARCA
- [Sugestões para identidade visual]
"""
        },
        'impacto_comunicacao': {
            'nome': '🎯 Especialista em Impacto e Comunicação',
            'prompt': f"""
{contexto_agente}
{contexto_global}

## FUNÇÃO: ESPECIALISTA EM IMPACTO E COMUNICAÇÃO

**Sua tarefa:** Analisar EXCLUSIVAMENTE impacto visual e comunicação.

### CRITÉRIOS DE ANÁLISE:
1. **Mensagem Central** - Clareza da comunicação
2. **Apelo Emocional** - Conexão com o público
3. **Chamada para Ação** - Efetividade persuasiva
4. **Originalidade** - Diferenciação criativa
5. **Memorabilidade** - Capacidade de ser lembrado

### FORMATO DE RESPOSTA OBRIGATÓRIO:

## 🎯 RELATÓRIO DE IMPACTO

### ✅ PONTOS DE IMPACTO
- [Elementos comunicativos eficazes]

### 📉 OPORTUNIDADES DE MELHORIA
- [Áreas para aumentar impacto]


### 🚀 ESTRATÉGIAS DE COMUNICAÇÃO
- [Técnicas para melhor comunicação]
"""
        }
    }
    
    return analisadores

def criar_analisadores_video(contexto_agente, contexto_global, contexto_video_especifico):
        """Cria analisadores especializados para vídeos - VERSÃO COMPLETA COM 6 ESPECIALISTAS"""
        
        analisadores = {
            'narrativa_estrutura': {
                'nome': '📖 Especialista em Narrativa e Estrutura',
                'prompt': f"""
    {contexto_agente}
    {contexto_global}
    {contexto_video_especifico}
    
    ## FUNÇÃO: ESPECIALISTA EM NARRATIVA E ESTRUTURA
    
    **Sua tarefa:** Analisar EXCLUSIVAMENTE a estrutura narrativa do vídeo.
    
    ### CRITÉRIOS DE ANÁLISE:
    1. **Arco Narrativo** - Desenvolvimento da história
    2. **Ritmo** - Velocidade e fluidez da narrativa
    3. **Estrutura** - Organização do conteúdo
    4. **Transições** - Conexão entre cenas/ideias
    5. **Clímax e Resolução** - Ponto alto e conclusão
    
    ### FORMATO DE RESPOSTA OBRIGATÓRIO:
    
    ## 📖 RELATÓRIO DE NARRATIVA
    
    ### ✅ PONTOS FORTES DA NARRATIVA
    - [Elementos narrativos bem executados]
    
    ### ⚠️ PROBLEMAS DE ESTRUTURA
    - [Issues na organização do conteúdo]
    
    ### 📊 SCORE NARRATIVA: [X/10]
    
    ### 💡 SUGESTÕES NARRATIVAS
    - [Melhorias para estrutura e ritmo]
    """
            },
            'qualidade_audio': {
                'nome': '🔊 Especialista em Qualidade de Áudio',
                'prompt': f"""
    {contexto_agente}
    {contexto_global}
    {contexto_video_especifico}
    
    ## FUNÇÃO: ESPECIALISTA EM QUALIDADE DE ÁUDIO
    
    **Sua tarefa:** Analisar EXCLUSIVAMENTE aspectos de áudio do vídeo.
    
    ### CRITÉRIOS DE ANÁLISE:
    1. **Clareza Vocal** - Inteligibilidade da fala
    2. **Qualidade Técnica** - Ruído, distorção, equilíbrio
    3. **Trilha Sonora** - Música e efeitos sonoros
    4. **Sincronização** - Relação áudio-vídeo
    5. **Mixagem** - Balanceamento de elementos sonoros
    
    ### FORMATO DE RESPOSTA OBRIGATÓRIO:
    
    ## 🔊 RELATÓRIO DE ÁUDIO
    
    ### ✅ ACERTOS DE ÁUDIO
    - [Elementos sonoros bem executados]
    
    ### ❌ PROBLEMAS DE ÁUDIO
    - [Issues técnicos e de qualidade]
    
    ### 📊 SCORE ÁUDIO: [X/10]
    
    ### 🎧 RECOMENDAÇÕES DE ÁUDIO
    - [Sugestões para melhor qualidade sonora]
    """
            },
            'visual_cinematografia': {
                'nome': '🎥 Especialista em Visual e Cinematografia',
                'prompt': f"""
    {contexto_agente}
    {contexto_global}
    {contexto_video_especifico}
    
    ## FUNÇÃO: ESPECIALISTA EM VISUAL E CINEMATOGRAFIA
    
    **Sua tarefa:** Analisar EXCLUSIVAMENTE aspectos visuais do vídeo.
    
    ### CRITÉRIOS DE ANÁLISE:
    1. **Enquadramento** - Composição de cenas
    2. **Iluminação** - Uso da luz e sombras
    3. **Movimento de Câmera** - Dinâmica visual
    
    ### FORMATO DE RESPOSTA OBRIGATÓRIO:
    
    ## 🎥 RELATÓRIO VISUAL
    
    ### ✅ PONTOS FORTES VISUAIS
    - [Elementos visuais bem executados]
    
    ### ⚠️ PROBLEMAS VISUAIS
    - [Issues de qualidade visual]
    
    ### 📊 SCORE VISUAL: [X/10]
    
    ### 🌟 SUGESTÕES VISUAIS
    - [Melhorias para cinematografia]
    """
            },
            'branding_consistencia': {
                'nome': '🏢 Especialista em Branding e Consistência',
                'prompt': f"""
    {contexto_agente}
    {contexto_global}
    {contexto_video_especifico}
    
    ## FUNÇÃO: ESPECIALISTA EM BRANDING E CONSISTÊNCIA
    
    **Sua tarefa:** Analisar EXCLUSIVAMENTE alinhamento com branding.
    
    ### CRITÉRIOS DE ANÁLISE:
    1. **Identidade Visual** - Cores, logos, elementos da marca
    2. **Tom de Voz** - Personalidade da comunicação
    3. **Mensagem Central** - Alinhamento com valores
    4. **Público-Alvo** - Adequação ao destinatário
    
    ### FORMATO DE RESPOSTA OBRIGATÓRIO:
    
    ## 🏢 RELATÓRIO DE BRANDING
    
    ### ✅ ALINHAMENTOS DE MARCA
    - [Elementos que seguem as diretrizes]
    
    ### ❌ DESVIOS DE MARCA
    - [Elementos fora do padrão]
    
    
    ### 🎯 RECOMENDAÇÕES DE MARCA
    - [Sugestões para melhor alinhamento]
    """
            },
            'engajamento_eficacia': {
                'nome': '📈 Especialista em Engajamento e Eficácia',
                'prompt': f"""
    {contexto_agente}
    {contexto_global}
    {contexto_video_especifico}
    
    ## FUNÇÃO: ESPECIALISTA EM ENGAJAMENTO E EFICÁCIA
    
    **Sua tarefa:** Analisar EXCLUSIVAMENTE potencial de engajamento e eficácia comunicativa.
    
    ### CRITÉRIOS DE ANÁLISE:
    1. **Hook Inicial** - Capacidade de prender atenção
    2. **Retenção** - Manutenção do interesse
    3. **Chamada para Ação** - Clareza e persuasão
    4. **Emoção** - Conexão emocional com o público
    5. **Compartilhamento** - Potencial viral
    
    ### FORMATO DE RESPOSTA OBRIGATÓRIO:
    
    ## 📈 RELATÓRIO DE ENGAJAMENTO
    
    ### ✅ PONTOS FORTES DE ENGAJAMENTO
    - [Elementos que engajam o público]
    
    ### 📉 OPORTUNIDADES DE MELHORIA
    - [Áreas para aumentar engajamento]
    
    
    ### 🚀 ESTRATÉGIAS DE ENGAJAMENTO
    - [Técnicas para melhor conexão]
    """
            },
            'sincronizacao_audio_legendas': {
                'nome': '🎯 Especialista em Sincronização Áudio-Legendas',
                'prompt': f"""
    {contexto_agente}
    {contexto_global}
    {contexto_video_especifico}
    
    ## FUNÇÃO: ESPECIALISTA EM SINCRONIZAÇÃO ÁUDIO-LEGENDAS
    
    **Sua tarefa:** Analisar EXCLUSIVAMENTE sincronização entre áudio e legendas.
    
    ### CRITÉRIOS DE ANÁLISE:
    1. **Timing** - Sincronização precisa
    2. **Legibilidade** - Clareza das legendas

    
    ### FORMATO DE RESPOSTA OBRIGATÓRIO:
    
    ## 🎯 RELATÓRIO DE SINCRONIZAÇÃO
    
    ### Time stamps específicos das ocorrências de erros entre o que foi falado e o que está escrito nas legendas
    ### Verificação se a legenda em si está escrita corretamente
    

    """
            }
        }
        
        return analisadores

def executar_analise_imagem_especializada(uploaded_image, nome_imagem, analisadores):
    """Executa análise especializada para imagens com múltiplos especialistas"""
    
    resultados = {}
    
    for area, config in analisadores.items():
        with st.spinner(f"Executando {config['nome']}..."):
            try:
                prompt_completo = f"""
{config['prompt']}

###BEGIN IMAGEM PARA ANÁLISE###
**Arquivo:** {nome_imagem}
**Análise solicitada para:** {config['nome']}
###END IMAGEM PARA ANÁLISE###

Por favor, forneça sua análise especializada no formato solicitado.
"""
                
                # Processar imagem com o especialista específico
                response = modelo_vision.generate_content([
                    prompt_completo,
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
                    'analise': f"❌ Erro na análise: {str(e)}",
                    'score': 0
                }
    
    return resultados

def executar_analise_video_especializada(uploaded_video, nome_video, analisadores):
    """Executa análise especializada para vídeos com múltiplos especialistas"""
    
    resultados = {}
    
    for area, config in analisadores.items():
        with st.spinner(f"Executando {config['nome']}..."):
            try:
                prompt_completo = f"""
{config['prompt']}

###BEGIN VÍDEO PARA ANÁLISE###
**Arquivo:** {nome_video}
**Análise solicitada para:** {config['nome']}
###END VÍDEO PARA ANÁLISE###

Por favor, forneça sua análise especializada no formato solicitado.
"""
                
                # Processar vídeo com o especialista específico
                video_bytes = uploaded_video.getvalue()
                
                if len(video_bytes) < 200 * 1024 * 1024:
                    response = modelo_vision.generate_content([
                        prompt_completo,
                        {"mime_type": uploaded_video.type, "data": video_bytes}
                    ])
                else:
                    response = modelo_vision.generate_content([
                        prompt_completo,
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
                    'analise': f"❌ Erro na análise: {str(e)}",
                    'score': 0
                }
    
    return resultados

def gerar_relatorio_imagem_consolidado(resultados_especialistas, nome_imagem, dimensoes):
    """Gera relatório consolidado para imagens"""

    
    relatorio = f"""
# 🖼️ RELATÓRIO CONSOLIDADO DE IMAGEM

**Arquivo:** {nome_imagem}
**Dimensões:** {dimensoes}

**Data da Análise:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}

## 🎖️ SCORES POR ÁREA ESPECIALIZADA
"""
    
    # Adicionar scores individuais

    
    relatorio += "\n## 📋 ANÁLISES DETALHADAS POR ESPECIALISTA\n"
    
    # Adicionar análises detalhadas
    for area, resultado in resultados_especialistas.items():
        relatorio += f"\n### {resultado['nome']}\n"
        relatorio += f"{resultado['analise']}\n"
        relatorio += "---\n"
    
    # Resumo executivo
    relatorio += f"""
## 🚀 RESUMO EXECUTIVO - IMAGEM



### 🎯 PRÓXIMOS PASSOS RECOMENDADOS:
"""
    

    
    return relatorio

def gerar_relatorio_video_consolidado(resultados_especialistas, nome_video, tipo_video):
    """Gera relatório consolidado para vídeos"""
    
   
    
    relatorio = f"""
# 🎬 RELATÓRIO CONSOLIDADO DE VÍDEO

**Arquivo:** {nome_video}
**Formato:** {tipo_video}
**Data da Análise:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}

## 🎖️ SCORES POR ÁREA ESPECIALIZADA
"""
    
    
    
    relatorio += "\n## 📋 ANÁLISES DETALHADAS POR ESPECIALISTA\n"
    
    # Adicionar análises detalhadas
    for area, resultado in resultados_especialistas.items():
        relatorio += f"\n### {resultado['nome']}\n"
        relatorio += f"{resultado['analise']}\n"
        relatorio += "---\n"
    
    # Resumo executivo
    relatorio += f"""
## 🚀 RESUMO EXECUTIVO - VÍDEO


### 🎯 PRÓXIMOS PASSOS RECOMENDADOS:
"""
    
    # Recomendações baseadas nos scores
    areas_baixas = [area for area, resultado in resultados_especialistas.items() if resultado['score'] < 6]
    if areas_baixas:
        nomes_areas = [resultados_especialistas[area]['nome'] for area in areas_baixas]
        relatorio += f"- **Prioridade Máxima:** Focar em {', '.join(nomes_areas)}\n"
    
    areas_medianas = [area for area, resultado in resultados_especialistas.items() if 6 <= resultado['score'] < 8]
    if areas_medianas:
        nomes_areas = [resultados_especialistas[area]['nome'] for area in areas_medianas]
        relatorio += f"- **Otimização Necessária:** Melhorar {', '.join(nomes_areas)}\n"
    
    areas_altas = [area for area, resultado in resultados_especialistas.items() if resultado['score'] >= 8]
    if areas_altas:
        nomes_areas = [resultados_especialistas[area]['nome'] for area in areas_altas]
        relatorio += f"- **Manutenção:** Manter a excelência em {', '.join(nomes_areas)}\n"
    
    return relatorio

# --- FUNÇÕES DE ANÁLISE DE TEXTO (MANTIDAS) ---

def criar_analisadores_texto(contexto_agente, contexto_global):
    """Cria prompts especializados para cada área de análise de texto"""
    
    analisadores = {
        'ortografia': {
            'nome': '🔤 Especialista em Ortografia e Gramática',
            'prompt': f"""
{contexto_global}

## FUNÇÃO: ESPECIALISTA EM ORTOGRAFIA E GRAMÁTICA PORTUGUÊS BR

**Sua tarefa:** Analisar EXCLUSIVAMENTE aspectos ortográficos e gramaticais.

### CRITÉRIOS DE ANÁLISE:
1. **Ortografia** - Erros de escrita
2. **Gramática** - Concordância, regência, colocação
3. **Pontuação** - Uso de vírgulas, pontos, etc.
4. **Acentuação** - Erros de acentuação
5. **Padrão Culto** - Conformidade com norma culta

### FORMATO DE RESPOSTA OBRIGATÓRIO:

## 🔤 RELATÓRIO ORTOGRÁFICO

### ✅ ACERTOS
- [Itens corretos]

### ❌ ERROS IDENTIFICADOS
- [Lista específica de erros com correções]

### 📊 SCORE ORTOGRÁFICO: [X/10]

### 💡 SUGESTÕES DE MELHORIA
- [Recomendações específicas]
"""
        },
        'lexico': {
            'nome': '📚 Especialista em Léxico e Vocabulário',
            'prompt': f"""
{contexto_agente}
{contexto_global}

## FUNÇÃO: ESPECIALISTA EM LÉXICO E VOCABULÁRIO

**Sua tarefa:** Analisar EXCLUSIVAMENTE aspectos lexicais e de vocabulário.

### CRITÉRIOS DE ANÁLISE:
1. **Variedade Lexical** - Riqueza de vocabulário
2. **Precisão Semântica** - Uso adequado das palavras
3. **Repetição** - Palavras ou expressões repetidas em excesso
4. **Jargões** - Uso inadequado de termos técnicos
5. **Clareza** - Facilidade de compreensão

### FORMATO DE RESPOSTA OBRIGATÓRIO:

## 📚 RELATÓRIO LEXICAL

### ✅ VOCABULÁRIO ADEQUADO
- [Pontos fortes do vocabulário]

### ⚠️ ASPECTOS A MELHORAR
- [Problemas lexicais identificados]

### 🔄 SUGESTÕES DE SINÔNIMOS
- [Palavras para substituir]

### 📊 SCORE LEXICAL: [X/10]
"""
        },
        'branding': {
            'nome': '🎨 Especialista em Branding e Identidade',
            'prompt': f"""
{contexto_agente}
{contexto_global}

## FUNÇÃO: ESPECIALISTA EM BRANDING E IDENTIDADE

**Sua tarefa:** Analisar EXCLUSIVAMENTE conformidade com diretrizes de branding.

### CRITÉRIOS DE ANÁLISE:
1. **Tom de Voz** - Alinhamento com personalidade da marca
2. **Mensagem Central** - Consistência da mensagem
3. **Valores da Marca** - Reflexo dos valores organizacionais
4. **Público-Alvo** - Adequação ao público pretendido
5. **Diferenciação** - Elementos únicos da marca

### FORMATO DE RESPOSTA OBRIGATÓRIO:

## 🎨 RELATÓRIO DE BRANDING

### ✅ ALINHAMENTOS
- [Elementos que seguem as diretrizes]

### ❌ DESVIOS IDENTIFICADOS
- [Elementos fora do padrão da marca]

### 📊 SCORE BRANDING: [X/10]

### 💡 RECOMENDAÇÕES ESTRATÉGICAS
- [Sugestões para melhor alinhamento]
"""
        },
        'estrutura': {
            'nome': '📋 Especialista em Estrutura e Formatação',
            'prompt': f"""
{contexto_agente}
{contexto_global}

## FUNÇÃO: ESPECIALISTA EM ESTRUTURA E FORMATAÇÃO

**Sua tarefa:** Analisar EXCLUSIVAMENTE estrutura e organização do conteúdo.

### CRITÉRIOS DE ANÁLISE:
1. **Organização** - Estrutura lógica e sequência
2. **Hierarquia** - Uso adequado de títulos e subtítulos
3. **Coesão** - Ligação entre ideias e parágrafos
4. **Formatação** - Consistência visual
5. **Objetividade** - Clareza na apresentação das ideias

### FORMATO DE RESPOSTA OBRIGATÓRIO:

## 📋 RELATÓRIO ESTRUTURAL

### ✅ ESTRUTURA ADEQUADA
- [Elementos bem organizados]

### ⚠️ PROBLEMAS ESTRUTURAIS
- [Issues de organização identificados]

### 📊 SCORE ESTRUTURAL: [X/10]

### 🏗️ SUGESTÕES DE REORGANIZAÇÃO
- [Melhorias na estrutura]
"""
        }
        
    }
    
    return analisadores

def executar_analise_texto_especializada(texto, nome_arquivo, analisadores):
    """Executa análise com múltiplos especialistas para texto"""
    
    resultados = {}
    
    for area, config in analisadores.items():
        with st.spinner(f"Executando {config['nome']}..."):
            try:
                prompt_completo = f"""
{config['prompt']}

###BEGIN TEXTO PARA ANÁLISE###
**Arquivo:** {nome_arquivo}
**Conteúdo:**
{texto[:8000]}
###END TEXTO PARA ANÁLISE###

Por favor, forneça sua análise no formato solicitado.
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
                    'analise': f"❌ Erro na análise: {str(e)}",
                    'score': 0
                }
    
    return resultados

def gerar_relatorio_texto_consolidado(resultados_especialistas, nome_arquivo):
    """Gera relatório consolidado a partir das análises especializadas de texto"""

  
    
    relatorio = f"""
# 📊 RELATÓRIO CONSOLIDADO DE VALIDAÇÃO

**Documento:** {nome_arquivo}

**Data da Análise:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}

## 🎖️ SCORES POR ÁREA
"""
    
  
    
    relatorio += "\n## 📋 ANÁLISES DETALHADAS POR ESPECIALISTA\n"
    
    # Adicionar análises detalhadas
    for area, resultado in resultados_especialistas.items():
        relatorio += f"\n### {resultado['nome']}\n"
        relatorio += f"{resultado['analise']}\n"
        relatorio += "---\n"
    
    # Resumo executivo
    relatorio += f"""
## 🚀 RESUMO EXECUTIVO



### 🎯 PRÓXIMOS PASSOS RECOMENDADOS:
"""
    
   
    
    relatorio += "- **Manutenção:** Manter as áreas com scores altos\n"
    
    return relatorio

def extrair_score(texto_analise):
    """Extrai score numérico do texto de análise"""
    import re
    padrao = r'SCORE.*?\[(\d+)(?:/10)?\]'
    correspondencias = re.findall(padrao, texto_analise, re.IGNORECASE)
    if correspondencias:
        return int(correspondencias[0])
    return 5  # Score padrão se não encontrar

# --- FUNÇÕES ORIGINAIS MANTIDAS ---

def criar_prompt_validacao_preciso(texto, nome_arquivo, contexto_agente):
    """Cria um prompt de validação muito mais preciso para evitar falsos positivos"""
    
    prompt = f"""
{contexto_agente}

###BEGIN TEXTO PARA VALIDAÇÃO###
**Arquivo:** {nome_arquivo}
**Conteúdo:**
{texto[:12000]}
###END TEXTO PARA VALIDAÇÃO###

## FORMATO DE RESPOSTA OBRIGATÓRIO:

### ✅ CONFORMIDADE COM DIRETRIZES
- [Itens que estão alinhados com as diretrizes de branding]

**INCONSISTÊNCIAS COM BRANDING:**
- [Só liste desvios REAIS das diretrizes de branding]

### 💡 TEXTO REVISADO
- [Sugestões para aprimorar]

### 📊 STATUS FINAL
**Documento:** [Aprovado/Necessita ajustes/Reprovado]
**Principais ações necessárias:** [Lista resumida]
"""
    return prompt

def analisar_documento_por_slides(doc, contexto_agente):
    """Analisa documento slide por slide com alta precisão"""
    
    resultados = []
    
    for i, slide in enumerate(doc['slides']):
        with st.spinner(f"Analisando slide {i+1}..."):
            try:
                prompt_slide = f"""
{contexto_agente}

## ANÁLISE POR SLIDE - PRECISÃO ABSOLUTA

###BEGIN TEXTO PARA VALIDAÇÃO###
**SLIDE {i+1}:**
{slide['conteudo'][:2000]}
###END TEXTO PARA VALIDAÇÃO###

**ANÁLISE DO SLIDE {i+1}:**

### ✅ Pontos Fortes:
[O que está bom neste slide]

### ⚠️ Problemas REAIS:
- [Lista CURTA de problemas]

### 💡 Sugestões Específicas:
[Melhorias para ESTE slide específico]

Considere que slides que são introdutórios ou apenas de títulos não precisam de tanto rigor de branding

**STATUS:** [✔️ Aprovado / ⚠️ Ajustes Menores / ❌ Problemas Sérios]
"""
                
                resposta = modelo_texto.generate_content(prompt_slide)
                resultados.append({
                    'slide_num': i+1,
                    'analise': resposta.text,
                    'tem_alteracoes': '❌' in resposta.text or '⚠️' in resposta.text
                })
                
            except Exception as e:
                resultados.append({
                    'slide_num': i+1,
                    'analise': f"❌ Erro na análise do slide: {str(e)}",
                    'tem_alteracoes': False
                })
    
    # Construir relatório consolidado
    relatorio = f"# 📊 RELATÓRIO DE VALIDAÇÃO - {doc['nome']}\n\n"
    relatorio += f"**Total de Slides:** {len(doc['slides'])}\n"
    relatorio += f"**Slides com Alterações:** {sum(1 for r in resultados if r['tem_alteracoes'])}\n\n"
    
    # Slides que precisam de atenção
    slides_com_problemas = [r for r in resultados if r['tem_alteracoes']]
    if slides_com_problemas:
        relatorio += "## 🚨 SLIDES QUE PRECISAM DE ATENÇÃO:\n\n"
        for resultado in slides_com_problemas:
            relatorio += f"### 📋 Slide {resultado['slide_num']}\n"
            relatorio += f"{resultado['analise']}\n\n"
    
    # Resumo executivo
    relatorio += "## 📈 RESUMO EXECUTIVO\n\n"
    if slides_com_problemas:
        relatorio += f"**⚠️ {len(slides_com_problemas)} slide(s) necessitam de ajustes**\n"
        relatorio += f"**✅ {len(doc['slides']) - len(slides_com_problemas)} slide(s) estão adequados**\n"
    else:
        relatorio += "**🎉 Todos os slides estão em conformidade com as diretrizes!**\n"
    
    return relatorio

def extract_text_from_pdf_com_slides(arquivo_pdf):
    """Extrai texto de PDF com informação de páginas"""
    try:
        import PyPDF2
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
        return f"Erro na extração PDF: {str(e)}", []

def extract_text_from_pptx_com_slides(arquivo_pptx):
    """Extrai texto de PPTX com informação de slides"""
    try:
        from pptx import Presentation
        import io
        
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
        return f"Erro na extração PPTX: {str(e)}", []

def extrair_texto_arquivo(arquivo):
    """Extrai texto de arquivos TXT e DOCX"""
    try:
        if arquivo.type == "text/plain":
            return str(arquivo.read(), "utf-8")
        elif arquivo.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            import docx
            import io
            doc = docx.Document(io.BytesIO(arquivo.read()))
            texto = ""
            for para in doc.paragraphs:
                texto += para.text + "\n"
            return texto
        else:
            return f"Tipo não suportado: {arquivo.type}"
    except Exception as e:
        return f"Erro na extração: {str(e)}"

def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF file using multiple methods for better coverage
    """
    text = ""

    # Method 1: Try with pdfplumber (better for some PDFs)
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text
    except Exception as e:
        print(f"pdfplumber failed for {pdf_path}: {e}")

    # Method 2: Fallback to PyPDF2 if pdfplumber didn't extract much text
    if len(text.strip()) < 100:  # If very little text was extracted
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text 
        except Exception as e:
            print(f"PyPDF2 also failed for {pdf_path}: {e}")

    return text

# --- INICIALIZAÇÃO DE SESSION_STATE ---
if 'analise_especializada_texto' not in st.session_state:
    st.session_state.analise_especializada_texto = True

if 'analise_especializada_imagem' not in st.session_state:
    st.session_state.analise_especializada_imagem = True

if 'analise_especializada_video' not in st.session_state:
    st.session_state.analise_especializada_video = True

if 'analisadores_selecionados_texto' not in st.session_state:
    st.session_state.analisadores_selecionados_texto = ['ortografia', 'lexico', 'branding']

if 'analisadores_selecionados_imagem' not in st.session_state:
    st.session_state.analisadores_selecionados_imagem = ['composicao_visual', 'cores_branding', 'tipografia_texto', 'elementos_marca']

if 'analisadores_selecionados_video' not in st.session_state:
    st.session_state.analisadores_selecionados_video = ['narrativa_estrutura', 'qualidade_audio', 'visual_cinematografia', 'branding_consistencia']

if 'analise_detalhada' not in st.session_state:
    st.session_state.analise_detalhada = True

if 'validacao_triggered' not in st.session_state:
    st.session_state.validacao_triggered = False

if 'todos_textos' not in st.session_state:
    st.session_state.todos_textos = []

if 'resultados_analise_imagem' not in st.session_state:
    st.session_state.resultados_analise_imagem = []

if 'resultados_analise_video' not in st.session_state:
    st.session_state.resultados_analise_video = []

# --- NOVAS FUNÇÕES PARA COMENTÁRIOS EM PDF ---
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Text
import io

def extrair_comentarios_analise(texto_analise):
    """Extrai os comentários principais do texto de análise da LLM"""
    comentarios = []
    
    # Padrões para extrair comentários
    padroes = [
        r'❌\s*(.*?)(?=\n|$)',
        r'⚠️\s*(.*?)(?=\n|$)',
        r'###\s*❌\s*(.*?)(?=###|\n\n|$)',
        r'###\s*⚠️\s*(.*?)(?=###|\n\n|$)',
        r'PROBLEMAS.*?\n(.*?)(?=###|\n\n|$)',
        r'ALTERAÇÕES.*?\n(.*?)(?=###|\n\n|$)',
        r'DESVIOS.*?\n(.*?)(?=###|\n\n|$)'
    ]
    
    for padrao in padroes:
        matches = re.findall(padrao, texto_analise, re.IGNORECASE | re.DOTALL)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            comentario = match.strip()
            if comentario and len(comentario) > 10:  # Filtra comentários muito curtos
                comentarios.append(comentario)
    
    # Se não encontrou padrões específicos, extrai parágrafos que contenham palavras-chave
    if not comentarios:
        linhas = texto_analise.split('\n')
        for linha in linhas:
            linha = linha.strip()
            if any(palavra in linha.lower() for palavra in ['erro', 'problema', 'ajuste', 'corrigir', 'melhorar', 'sugestão', 'recomendação']):
                if len(linha) > 20 and not linha.startswith('#'):
                    comentarios.append(linha)
    
    return comentarios[:10]  # Limita a 10 comentários

def adicionar_comentarios_pdf(arquivo_pdf_original, comentarios, nome_documento):
    """Adiciona comentários como anotações no PDF"""
    try:
        # Ler o PDF original
        reader = PdfReader(io.BytesIO(arquivo_pdf_original.getvalue()))
        writer = PdfWriter()
        
        # Copiar todas as páginas
        for page in reader.pages:
            writer.add_page(page)
        
        # Adicionar comentários como anotações
        for i, comentario in enumerate(comentarios):
            if i >= 5:  # Limita a 5 comentários para não sobrecarregar
                break
                
            # Calcular posição (distribui os comentários verticalmente)
            y_pos = 750 - (i * 100)
            
            # Criar anotação de texto
            annotation = Text(
                text=f"📝 Comentário {i+1}: {comentario[:200]}...",  # Limita o texto
                rect=(50, y_pos, 400, y_pos + 20),
                open=False
            )
            
            # Adicionar anotação à primeira página
            writer.add_annotation(page_number=0, annotation=annotation)
        
        # Salvar PDF com comentários
        pdf_com_comentarios = io.BytesIO()
        writer.write(pdf_com_comentarios)
        pdf_com_comentarios.seek(0)
        
        return pdf_com_comentarios
        
    except Exception as e:
        st.error(f"❌ Erro ao adicionar comentários ao PDF: {str(e)}")
        return None


def criar_relatorio_comentarios(comentarios, nome_documento, contexto_analise):
    """Cria um relatório de comentários em formato de texto"""
    relatorio = f"""
# 📋 RELATÓRIO DE COMENTÁRIOS - {nome_documento}

**Data da Análise:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}
**Total de Comentários:** {len(comentarios)}

## 🎯 CONTEXTO DA ANÁLISE
{contexto_analise[:500]}...

## 📝 COMENTÁRIOS E SUGESTÕES

"""
    
    for i, comentario in enumerate(comentarios, 1):
        relatorio += f"### 🔍 Comentário {i}\n{comentario}\n\n"
    
    relatorio += """
## 📊 RESUMO EXECUTIVO

**Próximos Passos Recomendados:**
1. Revisar os comentários no PDF anotado
2. Implementar as correções sugeridas
3. Validar conformidade com diretrizes de branding
4. Realizar revisão final do documento

---
*Relatório gerado automaticamente pelo Sistema de Validação Unificada*
"""
    
    return relatorio
# --- FUNÇÕES PARA VALIDAÇÃO DE TEXTO EM IMAGEM ---

def gerar_relatorio_texto_imagem_consolidado(resultados):
    """Gera relatório consolidado no formato específico para texto em imagem"""
    
    relatorio = f"""
# 📝 RELATÓRIO DE VALIDAÇÃO DE TEXTO EM IMAGEM

**Data da Análise:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}
**Total de Imagens Analisadas:** {len(resultados)}

## 📋 ANÁLISE INDIVIDUAL POR ARTE
"""
    
    for resultado in resultados:
        relatorio += f"\n{resultado['analise']}\n"
    
    # Resumo final em formato de tabela
    relatorio += "\n\n## 📌 RESUMO FINAL\n"
    relatorio += "Arte\tErros encontrados?\tObservações\n"
    relatorio += "---\t---\t---\n"
    
    for resultado in resultados:
        status_text = {
            "Correto": "❌ Não",
            "Ajustes sugeridos": "⚠️ Sugestões apenas",
            "Com erros": "✅ Sim",
            "Erro": "❌ Erro na análise"
        }.get(resultado['status'], "❓ Desconhecido")
        
        relatorio += f"Arte {resultado['indice']}\t{status_text}\t{resultado['status']}\n"
    
    relatorio += f"""
    
**🔍 LEGENDA:**
✅ = Correto
⚠️ = Ajustes sugeridos (não são erros, apenas melhorias)
❌ = Sem erros
❌ = Erro na análise (problema técnico)

---
Relatório gerado automaticamente pelo Sistema de Validação de Texto em Imagem
"""
    
    return relatorio

# --- ABA: VALIDAÇÃO UNIFICADA (COMPLETA) ---
with tab_mapping["✅ Validação Unificada"]:
    st.header("✅ Validação Unificada de Conteúdo")
    
    if not st.session_state.get('agente_selecionado'):
        st.info("Selecione um agente primeiro na aba de Chat")
    else:
        agente = st.session_state.agente_selecionado
        st.subheader(f"Validação com: {agente.get('nome', 'Agente')}")
        
        # Container de contexto global
        st.markdown("---")
        st.subheader("🎯 Contexto para Análise")
        
        contexto_global = st.text_area(
            "**✍️ Contexto adicional para todas as análises:**", 
            height=120, 
            key="contexto_global_validacao",
            placeholder="Forneça contexto adicional que será aplicado a TODAS as análises (texto, documentos, imagens e vídeos)..."
        )
        
        # Subabas para diferentes tipos de validação - AGORA COM VALIDAÇÃO DE TEXTO EM IMAGEM E BATIMENTO DE LEGENDAS
        subtab_imagem, subtab_texto, subtab_video, subtab_texto_imagem, subtab_batimento_legendas = st.tabs(
            ["🖼️ Validação de Imagem", "📄 Validação de Documentos", "🎬 Validação de Vídeo", "📝 Validação de Texto em Imagem", "🎧 Batimento de Legendas"]
        )
        
        # --- SUBTAB: BATIMENTO DE LEGENDAS ---
        with subtab_batimento_legendas:
            st.subheader("🎧 Análise de Legendas em Vídeo")
            st.write("Verifica se as legendas embutidas no vídeo batem com o áudio.")
            
            # Campo para nomes próprios que devem ser reconhecidos corretamente
            with st.expander("🔤 Configurações de Nomes Próprios", expanded=True):
                st.markdown("""
                **Adicione aqui nomes próprios que devem ser reconhecidos corretamente:**
                
                - **Nomes de empresas:** MRS Logística, Syngenta, etc.
                - **Produtos:** Fortenza, Verdatis, Megafol, etc.
                - **Nomes de pessoas:** João Silva, Maria Santos, etc.
                - **Termos técnicos específicos:** PLINAZOLIN, ADEPIDYN, etc.
                
                **Formato:** um por linha, exatamente como deve aparecer nas legendas.
                """)
                
                nomes_proprios_input = st.text_area(
                    "Nomes próprios e termos específicos (um por linha):",
                    height=150,
                    placeholder="Exemplo:\nSyngenta\nMRS Logística\nFortenza\nVerdatis\nPLINAZOLIN\nJoão Silva\n...",
                    help="Insira cada nome próprio ou termo específico em uma linha separada. Esses termos serão tratados como corretos mesmo se o modelo de reconhecimento não os identificar perfeitamente.",
                    key="nomes_proprios_legendas"
                )
            
            # Converter o input em lista
            nomes_proprios = []
            if nomes_proprios_input:
                nomes_proprios = [nome.strip() for nome in nomes_proprios_input.split('\n') if nome.strip()]
                st.success(f"✅ {len(nomes_proprios)} nome(s) próprio(s) configurado(s)")
                
                # Mostrar preview dos nomes
                if len(nomes_proprios) > 0:
                    col_nomes1, col_nomes2 = st.columns(2)
                    with col_nomes1:
                        st.markdown("**📋 Nomes configurados:**")
                        for i, nome in enumerate(nomes_proprios[:10]):  # Mostrar até 10
                            st.write(f"- {nome}")
                    if len(nomes_proprios) > 10:
                        with col_nomes2:
                            st.markdown("**📋 Continuação:**")
                            for i, nome in enumerate(nomes_proprios[10:20], 11):
                                st.write(f"- {nome}")
            
            # Botão para limpar análises anteriores
            if st.button("🗑️ Limpar Análises Anteriores", key="limpar_analises_legendas"):
                st.session_state.resultados_analise_legendas = []
                st.rerun()
            
            # Upload de vídeos
            uploaded_videos_legendas = st.file_uploader(
                "Carregue vídeo(s) para análise de legendas:",
                type=["mp4", "mpeg", "mov", "avi", "flv", "mpg", "webm", "wmv", "3gpp"],
                key="video_legendas_upload",
                accept_multiple_files=True
            )
            
            if uploaded_videos_legendas:
                st.success(f"✅ {len(uploaded_videos_legendas)} vídeo(s) carregado(s)")
                
                # Configurações simples
                col1, col2 = st.columns(2)
                with col1:
                    linguagem_audio = st.selectbox(
                        "Linguagem do áudio:",
                        ["pt-BR", "pt-PT", "en-US", "en-GB", "es-ES"],
                        index=0
                    )
                with col2:
                    sensibilidade = st.slider(
                        "Sensibilidade (segundos):",
                        min_value=0.5,
                        max_value=5.0,
                        value=2.0,
                        step=0.5,
                        help="Tolerância para considerar que legenda e áudio estão sincronizados"
                    )
                
                # Botão para analisar
                if st.button("🔍 Analisar Sincronização de Legendas", type="primary", key="analisar_legendas"):
                    
                    resultados_legendas = []
                    
                    for idx, uploaded_video in enumerate(uploaded_videos_legendas):
                        with st.spinner(f'Analisando legendas no vídeo {idx+1} de {len(uploaded_videos_legendas)}: {uploaded_video.name}...'):
                            try:
                                # Criar prompt específico para análise de legendas COM nomes próprios
                                nomes_proprios_texto = ""
                                if nomes_proprios:
                                    nomes_proprios_texto = "### NOMES PRÓPRIOS CONFIGURADOS (CONSIDERAR CORRETOS):\n"
                                    for nome in nomes_proprios:
                                        nomes_proprios_texto += f"- {nome}\n"
                                    nomes_proprios_texto += "\nIMPORTANTE: Esses nomes devem ser considerados corretos mesmo se aparecerem com pequenas variações.\n\n"
                                
                                prompt_legendas = f'''
                                INSTRUÇÕES PARA ANÁLISE DE SINCRONIZAÇÃO LEGENDA-ÁUDIO
        
                                Objetivo: Analisar o vídeo fornecido para verificar a precisão e o sincronismo entre as legendas embutidas (texto visível no vídeo) e o áudio. O foco principal é identificar discrepâncias.
        
                                {nomes_proprios_texto}
        
                                Parâmetros da Análise:
        
                                    Linguagem do Áudio: {linguagem_audio}
        
                                    Tolerância de Sincronização (Timing): {sensibilidade} segundos. Diferenças menores que este valor não são consideradas problemas.
        
                                    Checagem de Estilo de Texto: A análise deve flagrar erros de capitalização, como letra maiúscula indevida após vírgula dentro de uma frase.
        
                                CONSIDERAÇÕES ESPECIAIS PARA NOMES PRÓPRIOS:
                                1. Os nomes listados acima são específicos e devem ser aceitos como corretos
                                2. Pequenas variações nos nomes (diferenças de capitalização, acentuação) devem ser consideradas aceitáveis
                                3. Se um nome da lista aparecer nas legendas, considere que está correto (não marque como erro)
                                4. Para nomes que NÃO estão na lista, aplique as regras normais de análise
        
                                Passos da Análise:
        
                                    Detecção de Legendas: Utilize OCR para detectar e extrair todo o texto visível (legendas embutidas) no vídeo, registrando seus timestamps de entrada e saída.
        
                                    Transcrição do Áudio: Transcreva com precisão o áudio do vídeo, gerando uma transcrição com timestamps por frase ou segmento significativo.
        
                                    Comparação e Validação:
                                    a. Sincronismo (Timing): Para cada bloco de legenda, verifique se o texto correspondente no áudio é falado dentro da janela de tempo definida pela legenda +/- a tolerância.
                                    b. Precisão Textual: Compare o texto da legenda com a transcrição do áudio correspondente. Identifique:
                                    * Omissões de palavras.
                                    * Acréscimos de palavras não faladas.
                                    * Substituições ou erros de palavras.
                                    * Diferenças de pontuação que alterem o sentido.
                                    * Erros de Capitalização: Ex: Letra maiúscula incorreta após uma vírgula no meio de uma frase (ex: "Vamos lá, Como está?").
                                    c. Verificação de Nomes Próprios: Para nomes da lista fornecida, aceite pequenas variações e não marque como erro.
        
                                Formato do Relatório de Saída:
        
                                CASO A: Sincronização Correta (Sem Problemas)
                                Se, e somente se, não forem encontrados problemas de timing (dentro da tolerância) OU de texto (incluindo os erros de capitalização especificados), retorne APENAS a seguinte mensagem:
        
                                    ✅ STATUS: SINCRONIZAÇÃO VERIFICADA.
                                    As legendas embutidas no vídeo "{uploaded_video.name}" estão perfeitamente sincronizadas com o áudio e textualmente corretas dentro dos parâmetros definidos (Tolerância: {sensibilidade}s). Nenhuma ação é necessária.
        
                                CASO B: Problemas Encontrados
                                Se QUALQUER problema for detectado (de timing, texto ou capitalização), retorne um relatório completo no seguinte formato:
                                🎬 Relatório de Análise: {uploaded_video.name}
                                
                                📋 Resumo Executivo
        
                                    Status Geral: ❌ Sincronização com Problemas.
        
                                    Total de Problemas Identificados: [X]
        
                                        Problemas de Timing/Janela: [Y]
        
                                        Problemas Textuais (Conteúdo): [Z]
        
                                        Problemas de Nomes Próprios: [W] (se aplicável)
        
                                    Nomes Próprios Encontrados: [Listar os nomes da sua lista que apareceram no vídeo]
                                    
                                    Conclusão Rápida: [Uma ou duas linhas resumindo a qualidade geral, ex: "As legendas estão geralmente atrasadas e contêm vários erros de digitação."]
        
                                ❌ Problemas Detalhados (Com Timestamps)
        
                                Liste cada problema encontrado, na ordem cronológica. Use o formato abaixo para cada item:
        
                                    [MM:SS] - [TIPO DE PROBLEMA]
        
                                        Legenda no Vídeo: "[Texto exato da legenda conforme exibido]"
        
                                        Áudio Transcrito: "[Texto exato falado no áudio]"
        
                                        Descrição: [Explicação clara do problema. Ex: "Legenda exibida 2.5s antes da fala.", "Substituição de palavra.", "Capitalização incorreta após vírgula."]
        
                                PARA PROBLEMAS COM NOMES PRÓPRIOS (se não estiverem na lista):
        
                                    [MM:SS] - NOME PRÓPRIO INCORRETO
        
                                        Legenda no Vídeo: "[Nome como aparece]"
        
                                        Áudio Transcrito: "[Nome como foi falado]"
        
                                        Sugestão de Correção: [Nome correto, se conhecido]
        
                                ✅ NOMES PRÓPRIOS RECONHECIDOS CORRETAMENTE:
                                [Liste os nomes da sua lista que foram identificados corretamente no vídeo]
        
                                💡 RECOMENDAÇÕES DE CORREÇÃO
        
                                [Forneça sugestões específicas e acionáveis com base nos problemas encontrados, por exemplo:]
        
                                    Ajuste de Timing: Ajuste todas as legendas a partir de [MM:SS] com um delay de aproximadamente [X] segundos.
        
                                    Revisão Textual: Corrija as palavras específicas citadas na seção de problemas.
        
                                    Revisão de Estilo: Verifique as regras de capitalização, especialmente após vírgulas.
        
                                    Nomes Próprios: [Sugestões específicas para nomes próprios problemáticos]
        
                                Notas Finais para o Analista:
        
                                    Seja meticuloso na comparação textual, incluindo a verificação do erro de maiúscula pós-vírgula.
        
                                    Os timestamps nos problemas devem referenciar o momento aproximado no vídeo onde o erro é perceptível.
        
                                    O relatório deve ser factual, direto e útil para um editor de vídeo ou legendas corrigir os itens.
        
                                    CONSIDERE OS NOMES PRÓPRIOS FORNECIDOS COMO CORRETOS - não marque como erro se estiverem na lista.
                                '''
                                
                                # Usar modelo de visão para análise
                                response = modelo_vision.generate_content([
                                    prompt_legendas,
                                    {"mime_type": uploaded_video.type, "data": uploaded_video.getvalue()}
                                ])
                                
                                resultados_legendas.append({
                                    'nome': uploaded_video.name,
                                    'indice': idx,
                                    'analise': response.text,
                                    'tem_problemas': '❌' in response.text or 'PROBLEMAS' in response.text or 'não está batendo' in response.text.lower()
                                })
                                
                            except Exception as e:
                                resultados_legendas.append({
                                    'nome': uploaded_video.name,
                                    'indice': idx,
                                    'analise': f"❌ Erro na análise: {str(e)}",
                                    'tem_problemas': True
                                })
                    
                    # Armazenar resultados na sessão
                    st.session_state.resultados_analise_legendas = resultados_legendas
                    
                    # Exibir resultados
                    st.markdown("---")
                    st.subheader("📊 Resultados da Análise")
                    
                    # Mostrar estatísticas dos nomes próprios
                    if nomes_proprios:
                        st.info(f"**🔤 Nomes próprios configurados:** {len(nomes_proprios)}")
                        if len(nomes_proprios) <= 15:
                            st.caption(f"{', '.join(nomes_proprios)}")
                        else:
                            st.caption(f"{', '.join(nomes_proprios[:15])}... e mais {len(nomes_proprios) - 15}")
                    
                    # Vídeos com problemas
                    videos_com_problemas = [r for r in resultados_legendas if r['tem_problemas']]
                    
                    if videos_com_problemas:
                        st.error(f"⚠️ {len(videos_com_problemas)} vídeo(s) com problemas de sincronização encontrados")
                        
                        for resultado in videos_com_problemas:
                            with st.expander(f"🎬 {resultado['nome']} - Problemas Detectados", expanded=True):
                                st.markdown(resultado['analise'])
                    
                    # Vídeos sem problemas
                    videos_sem_problemas = [r for r in resultados_legendas if not r['tem_problemas']]
                    
                    if videos_sem_problemas:
                        st.success(f"✅ {len(videos_sem_problemas)} vídeo(s) com legendas sincronizadas")
                        
                        for resultado in videos_sem_problemas:
                            with st.expander(f"🎬 {resultado['nome']} - Análise Completa", expanded=False):
                                st.markdown(resultado['analise'])
                    
                    # Estatísticas
                    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                    with col_stat1:
                        st.metric("Vídeos Analisados", len(uploaded_videos_legendas))
                    with col_stat2:
                        st.metric("Com Problemas", len(videos_com_problemas))
                    with col_stat3:
                        percentual = (len(videos_com_problemas) / len(uploaded_videos_legendas) * 100) if uploaded_videos_legendas else 0
                        st.metric("% com Problemas", f"{percentual:.1f}%")
                    with col_stat4:
                        st.metric("Nomes Configurados", len(nomes_proprios))
            
            # Mostrar análises anteriores se existirem
            elif 'resultados_analise_legendas' in st.session_state and st.session_state.resultados_analise_legendas:
                st.info("📋 Análises anteriores encontradas. Carregue novos vídeos para nova análise.")
                
                resultados = st.session_state.resultados_analise_legendas
                
                videos_com_problemas = [r for r in resultados if r['tem_problemas']]
                
                if videos_com_problemas:
                    st.warning(f"{len(videos_com_problemas)} vídeo(s) com problemas na análise anterior")
                    
                    for resultado in videos_com_problemas:
                        with st.expander(f"🎬 {resultado['nome']} - Análise Anterior", expanded=False):
                            st.markdown(resultado['analise'])
            
            else:
                st.info("🎬 Carregue um ou mais vídeos para analisar a sincronização das legendas com o áudio")
        
        # --- SUBTAB: VALIDAÇÃO DE TEXTO EM IMAGEM ---
        with subtab_texto_imagem:
            st.subheader("📝 Validação de Texto em Imagem")
            
            
            # Upload de múltiplas imagens
            st.markdown("### 📤 Upload de Imagens com Texto")
            
            uploaded_images_texto = st.file_uploader(
                "Carregue uma ou mais imagens para análise de texto",
                type=["jpg", "jpeg", "png", "webp", "gif", "bmp"],
                accept_multiple_files=True,
                key="image_text_upload",
                help="Arquivos de imagem contendo texto para validação"
            )
            
            # Botão para limpar análises anteriores
            if st.button("🗑️ Limpar Análises Anteriores", key="limpar_texto_imagem"):
                if 'resultados_texto_imagem' in st.session_state:
                    del st.session_state.resultados_texto_imagem
                st.rerun()
            
            if uploaded_images_texto:
                st.success(f"✅ {len(uploaded_images_texto)} imagem(ns) carregada(s) para análise de texto")
                
                # Exibir miniaturas das imagens
                st.markdown("### 🖼️ Imagens Carregadas")
                cols = st.columns(min(4, len(uploaded_images_texto)))
                
                for idx, img in enumerate(uploaded_images_texto):
                    with cols[idx % 4]:
                        # Abrir imagem para mostrar miniatura
                        image = Image.open(img)
                        st.image(image, use_container_width=True, caption=f"Arte {idx+1}")
                        st.caption(f"📏 {image.width}x{image.height}px")
                
                # Botão para iniciar análise
                if st.button("🔍 Validar Texto em Todas as Imagens", type="primary", key="validar_texto_imagens"):
                    
                    resultados = []
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for idx, uploaded_image in enumerate(uploaded_images_texto):
                        status_text.text(f"📊 Analisando texto na imagem {idx+1} de {len(uploaded_images_texto)}...")
                        progress_bar.progress((idx + 1) / len(uploaded_images_texto))
                        
                        with st.spinner(f'Processando "Arte {idx+1}"...'):
                            try:
                                # Criar prompt específico para análise de texto em imagem
                                prompt_texto_imagem = f"""
                                {contexto_global if contexto_global else ''}
                                
                                ## ANÁLISE DE TEXTO EM IMAGEM
                                
                                **INSTRUÇÕES:**
                                1. Transcreva e analise TODO o texto visível na imagem
                                2. Foque em: ortografia, gramática, clareza e adequação
                                3. Use emojis para indicar o status
                                
                                **FORMATO DE RESPOSTA OBRIGATÓRIO:**
                                
                                ## Arte {idx+1} – [Título do texto extraído ou descrição da imagem]
                                
                                **Texto:**
                                "[Texto extraído da imagem]"
                                
                                **Correções:**
                                [✅/⚠️/❌] [Descrição da análise]
                                
                                🔍 [Observação opcional: sugestões de estilo ou melhoria]
                                
                                ---
                                """
                                
                                # Usar modelo de visão para análise
                                response = modelo_vision.generate_content([
                                    prompt_texto_imagem,
                                    {"mime_type": uploaded_image.type, "data": uploaded_image.getvalue()}
                                ])
                                
                                # Processar resposta
                                analise = response.text
                                
                                # Determinar status baseado na resposta
                                if "❌" in analise:
                                    status = "Com erros"
                                elif "⚠️" in analise:
                                    status = "Ajustes sugeridos"
                                else:
                                    status = "Correto"
                                
                                resultados.append({
                                    'indice': idx + 1,
                                    'nome': uploaded_image.name,
                                    'analise': analise,
                                    'status': status,
                                    'imagem': uploaded_image
                                })
                                
                            except Exception as e:
                                st.error(f"❌ Erro ao processar imagem {uploaded_image.name}: {str(e)}")
                                resultados.append({
                                    'indice': idx + 1,
                                    'nome': uploaded_image.name,
                                    'analise': f"❌ Erro na análise: {str(e)}",
                                    'status': "Erro",
                                    'imagem': uploaded_image
                                })
                    
                    progress_bar.empty()
                    status_text.empty()
                    
                    # Armazenar resultados na sessão
                    st.session_state.resultados_texto_imagem = resultados
                    
                    # Gerar relatório consolidado
                    relatorio_consolidado = gerar_relatorio_texto_imagem_consolidado(resultados)
                    
                    # Exibir resultados
                    st.markdown("---")
                    st.subheader("📋 Relatório de Validação de Texto em Imagens")
                    
                    # Exibir análises individuais
                    for resultado in resultados:
                        with st.expander(f"🖼️ Arte {resultado['indice']} - {resultado['status']}", expanded=True):
                            col_img, col_text = st.columns([1, 2])
                            
                            with col_img:
                                image = Image.open(resultado['imagem'])
                                st.image(image, use_container_width=True, caption=f"Arte {resultado['indice']}")
                            
                            with col_text:
                                st.markdown(resultado['analise'])
                    
                    # Exibir resumo final
                    st.markdown("---")
                    st.subheader("📌 Resumo Final")
                    
                    # Criar tabela de resumo
                    resumo_data = []
                    for resultado in resultados:
                        emoji = {
                            "Correto": "✅",
                            "Ajustes sugeridos": "⚠️", 
                            "Com erros": "❌",
                            "Erro": "❌"
                        }.get(resultado['status'], "❓")
                        
                        resumo_data.append({
                            "Arte": resultado['indice'],
                            "Status": emoji,
                            "Erros encontrados?": "❌ Não" if resultado['status'] == "Correto" else "✅ Sim" if resultado['status'] == "Com erros" else "⚠️ Sugestões",
                            "Observações": resultado['status']
                        })
                    
                    # Mostrar tabela
                    import pandas as pd
                    df_resumo = pd.DataFrame(resumo_data)
                    st.table(df_resumo)
                    
                    # Botão de download
                    st.download_button(
                        "📥 Baixar Relatório Completo (TXT)",
                        data=relatorio_consolidado,
                        file_name=f"relatorio_texto_imagens_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                        mime="text/plain",
                        key="download_relatorio_texto_imagem"
                    )
            
            # Mostrar análises anteriores se existirem
            elif 'resultados_texto_imagem' in st.session_state and st.session_state.resultados_texto_imagem:
                st.info("📋 Análises anteriores encontradas. Carregue novas imagens para nova análise ou use o botão 'Limpar Análises'.")
                
                resultados = st.session_state.resultados_texto_imagem
                
                for resultado in resultados:
                    with st.expander(f"Arte {resultado['indice']} - {resultado['status']} (Análise Anterior)", expanded=False):
                        st.markdown(resultado['analise'])
            
            
        # --- SUBTAB: VALIDAÇÃO DE DOCUMENTOS E TEXTO ---
        with subtab_texto:
            st.subheader("📄 Validação de Documentos e Texto")
            
            # Configurações de exportação PDF
            with st.expander("Configurações de Exportação PDF", expanded=True):
                col_export1, col_export2 = st.columns(2)
                
                with col_export1:
                    incluir_comentarios_pdf = st.checkbox(
                        "Incluir comentários no PDF",
                        value=True,
                        help="Adiciona os comentários da análise como anotações no PDF original"
                    )
                    
                    gerar_relatorio_completo = st.checkbox(
                        "Gerar relatório completo",
                        value=True,
                        help="Cria um arquivo de texto com todos os comentários e análises"
                    )
                
                with col_export2:
                    limitar_comentarios = st.slider(
                        "Máximo de comentários por PDF:",
                        min_value=1,
                        max_value=10,
                        value=5,
                        help="Limita o número de comentários adicionados ao PDF"
                    )
            
            # Botão para limpar análises de texto
            if st.button("🗑️ Limpar Análises de Texto", key="limpar_analises_texto"):
                st.session_state.validacao_triggered = False
                st.session_state.todos_textos = []
                st.session_state.resultados_pdf = {}
                st.rerun()
            
            # Container principal com duas colunas
            col_entrada, col_saida = st.columns([1, 1])
            
            with col_entrada:
                st.markdown("### Entrada de Conteúdo")
                
                # Opção 1: Texto direto
                texto_input = st.text_area(
                    "**Digite o texto para validação:**", 
                    height=150, 
                    key="texto_validacao",
                    placeholder="Cole aqui o texto que deseja validar..."
                )
                
                # Opção 2: Upload de múltiplos arquivos
                st.markdown("### 📎 Ou carregue arquivos")
                
                arquivos_documentos = st.file_uploader(
                    "**Documentos suportados:** PDF, PPTX, TXT, DOCX",
                    type=['pdf', 'pptx', 'txt', 'docx'],
                    accept_multiple_files=True,
                    key="arquivos_documentos_validacao"
                )
                
                # Configurações de análise
                with st.expander("Configurações de Análise de Texto"):
                    analise_especializada = st.checkbox(
                        "Análise especializada por áreas (recomendado)",
                        value=st.session_state.analise_especializada_texto,
                        help="Usa múltiplos especialistas para análise mais precisa"
                    )
                    
                    analisadores_selecionados = st.multiselect(
                        "Especialistas de texto a incluir:",
                        options=['ortografia', 'lexico', 'branding', 'estrutura', 'engajamento'],
                        default=st.session_state.analisadores_selecionados_texto,
                        format_func=lambda x: {
                            'ortografia': 'Ortografia e Gramática',
                            'lexico': 'Léxico e Vocabulário', 
                            'branding': 'Branding e Identidade',
                            'estrutura': 'Estrutura e Formatação',
                            'engajamento': 'Engajamento e Persuasão'
                        }[x]
                    )
                    
                    analise_detalhada = st.checkbox(
                        "Análise detalhada por slide/página",
                        value=st.session_state.analise_detalhada
                    )
                
                # Botão de validação
                if st.button("Validar Conteúdo de Texto", type="primary", key="validate_documents", use_container_width=True):
                    st.session_state.validacao_triggered = True
                    st.session_state.analise_especializada_texto = analise_especializada
                    st.session_state.analise_detalhada = analise_detalhada
                    st.session_state.analisadores_selecionados_texto = analisadores_selecionados
            
            with col_saida:
                st.markdown("### 📊 Resultados de Texto")
                
                if st.session_state.validacao_triggered:
                    # Processar todos os conteúdos
                    todos_textos = []
                    arquivos_processados = []
                    resultados_pdf = {}  # Armazena resultados para exportação PDF
                    
                    # Adicionar texto manual se existir
                    if texto_input and texto_input.strip():
                        todos_textos.append({
                            'nome': 'Texto_Manual',
                            'conteudo': texto_input,
                            'tipo': 'texto_direto',
                            'tamanho': len(texto_input),
                            'slides': []
                        })
                    
                    # Processar arquivos uploadados
                    if arquivos_documentos:
                        for arquivo in arquivos_documentos:
                            with st.spinner(f"Processando {arquivo.name}..."):
                                try:
                                    if arquivo.type == "application/pdf":
                                        texto_extraido, slides_info = extract_text_from_pdf_com_slides(arquivo)
                                        # Guardar o arquivo PDF original para possível anotação
                                        arquivo_original = arquivo
                                    elif arquivo.type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
                                        texto_extraido, slides_info = extract_text_from_pptx_com_slides(arquivo)
                                        arquivo_original = None
                                    elif arquivo.type in ["text/plain", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
                                        texto_extraido = extrair_texto_arquivo(arquivo)
                                        slides_info = []
                                        arquivo_original = None
                                    else:
                                        st.warning(f"Tipo de arquivo não suportado: {arquivo.name}")
                                        continue
                                    
                                    if texto_extraido and texto_extraido.strip():
                                        doc_info = {
                                            'nome': arquivo.name,
                                            'conteudo': texto_extraido,
                                            'slides': slides_info,
                                            'tipo': arquivo.type,
                                            'tamanho': len(texto_extraido),
                                            'arquivo_original': arquivo_original
                                        }
                                        todos_textos.append(doc_info)
                                        arquivos_processados.append(arquivo.name)
                                    
                                except Exception as e:
                                    st.error(f"Erro ao processar {arquivo.name}: {str(e)}")
                    
                    # Verificar se há conteúdo para validar
                    if not todos_textos:
                        st.warning("Nenhum conteúdo válido encontrado para validação.")
                    else:
                        st.success(f"{len(todos_textos)} documento(s) processado(s) com sucesso!")
                        
                        # Exibir estatísticas rápidas
                        col_docs, col_palavras, col_chars = st.columns(3)
                        with col_docs:
                            st.metric("📄 Documentos", len(todos_textos))
                        with col_palavras:
                            total_palavras = sum(len(doc['conteudo'].split()) for doc in todos_textos)
                            st.metric("📝 Palavras", total_palavras)
                        with col_chars:
                            total_chars = sum(doc['tamanho'] for doc in todos_textos)
                            st.metric("🔤 Caracteres", f"{total_chars:,}")
                        
                        # Análise individual por documento
                        st.markdown("---")
                        st.subheader("📋 Análise Individual por Documento")
                        
                        for doc in todos_textos:
                            with st.expander(f"📄 {doc['nome']} - {doc['tamanho']} chars", expanded=True):
                                # Informações básicas do documento
                                col_info1, col_info2 = st.columns(2)
                                with col_info1:
                                    st.write(f"**Tipo:** {doc['tipo']}")
                                    st.write(f"**Tamanho:** {doc['tamanho']} caracteres")
                                with col_info2:
                                    if doc['slides']:
                                        st.write(f"**Slides/Páginas:** {len(doc['slides'])}")
                                    else:
                                        st.write("**Estrutura:** Texto simples")
                                
                                # Contexto aplicado
                                if contexto_global and contexto_global.strip():
                                    st.info(f"**Contexto Aplicado:** {contexto_global}")
                                
                                # Análise de branding
                                with st.spinner(f"Analisando {doc['nome']}..."):
                                    try:
                                        # Construir contexto do agente
                                        contexto_agente = ""
                                        if "base_conhecimento" in agente:
                                            contexto_agente = f"""
                                            ###BEGIN DIRETRIZES DE BRANDING DO AGENTE:###
                                            {agente['base_conhecimento']}
                                            ###END DIRETRIZES DE BRANDING DO AGENTE###
                                            """
                                        
                                        # Adicionar contexto global se fornecido
                                        contexto_completo = contexto_agente
                                        if contexto_global and contexto_global.strip():
                                            contexto_completo += f"""
                                            ###BEGIN CONTEXTO ADICIONAL DO USUARIO###
                                            {contexto_global}
                                            ###END CONTEXTO ADICIONAL DO USUARIO###
                                            """
                                        
                                        # Escolher método de análise
                                        if st.session_state.analise_especializada_texto:
                                            # ANÁLISE ESPECIALIZADA POR MÚLTIPLOS ESPECIALISTAS
                                            st.info("**Executando análise especializada por múltiplos especialistas...**")
                                            
                                            # Criar analisadores especialistas
                                            analisadores_config = criar_analisadores_texto(contexto_completo, "")
                                            
                                            # Filtrar apenas os selecionados
                                            analisadores_filtrados = {k: v for k, v in analisadores_config.items() 
                                                                     if k in st.session_state.analisadores_selecionados_texto}
                                            
                                            # Executar análises especializadas
                                            resultados_especialistas = executar_analise_texto_especializada(
                                                doc['conteudo'], 
                                                doc['nome'], 
                                                analisadores_filtrados
                                            )
                                            
                                            # Gerar relatório consolidado
                                            relatorio_consolidado = gerar_relatorio_texto_consolidado(
                                                resultados_especialistas, 
                                                doc['nome']
                                            )
                                            
                                            st.markdown(relatorio_consolidado, unsafe_allow_html=True)
                                            
                                            # EXTRAIR COMENTÁRIOS PARA PDF
                                            if incluir_comentarios_pdf and doc['tipo'] == "application/pdf" and doc.get('arquivo_original'):
                                                comentarios = extrair_comentarios_analise(relatorio_consolidado)
                                                if comentarios:
                                                    with st.spinner("Adicionando comentários ao PDF..."):
                                                        pdf_com_comentarios = adicionar_comentarios_pdf(
                                                            doc['arquivo_original'],
                                                            comentarios[:limitar_comentarios],
                                                            doc['nome']
                                                        )
                                                        
                                                        if pdf_com_comentarios:
                                                            # Armazenar para download posterior
                                                            resultados_pdf[doc['nome']] = {
                                                                'pdf_com_comentarios': pdf_com_comentarios,
                                                                'comentarios': comentarios,
                                                                'relatorio': relatorio_consolidado
                                                            }
                                                            
                                                            # Botão de download imediato
                                                            st.download_button(
                                                                label="Baixar PDF com Comentários",
                                                                data=pdf_com_comentarios.getvalue(),
                                                                file_name=f"comentarios_{doc['nome']}",
                                                                mime="application/pdf",
                                                                key=f"download_pdf_{doc['nome']}"
                                                            )
                                            
                                        elif st.session_state.analise_detalhada and doc['slides']:
                                            # Análise detalhada por slide (método antigo)
                                            resultado_analise = analisar_documento_por_slides(doc, contexto_completo)
                                            st.markdown(resultado_analise)
                                            
                                            # EXTRAIR COMENTÁRIOS PARA PDF
                                            if incluir_comentarios_pdf and doc['tipo'] == "application/pdf" and doc.get('arquivo_original'):
                                                comentarios = extrair_comentarios_analise(resultado_analise)
                                                if comentarios:
                                                    with st.spinner("Adicionando comentários ao PDF..."):
                                                        pdf_com_comentarios = adicionar_comentarios_pdf(
                                                            doc['arquivo_original'],
                                                            comentarios[:limitar_comentarios],
                                                            doc['nome']
                                                        )
                                                        
                                                        if pdf_com_comentarios:
                                                            resultados_pdf[doc['nome']] = {
                                                                'pdf_com_comentarios': pdf_com_comentarios,
                                                                'comentarios': comentarios,
                                                                'relatorio': resultado_analise
                                                            }
                                                            
                                                            st.download_button(
                                                                label="Baixar PDF com Comentários",
                                                                data=pdf_com_comentarios.getvalue(),
                                                                file_name=f"comentarios_{doc['nome']}",
                                                                mime="application/pdf",
                                                                key=f"download_pdf_{doc['nome']}"
                                                            )
                                            
                                        else:
                                            # Análise geral do documento (método antigo)
                                            prompt_analise = criar_prompt_validacao_preciso(doc['conteudo'], doc['nome'], contexto_completo)
                                            resposta = modelo_texto.generate_content(prompt_analise)
                                            st.markdown(resposta.text)
                                            
                                            # EXTRAIR COMENTÁRIOS PARA PDF
                                            if incluir_comentarios_pdf and doc['tipo'] == "application/pdf" and doc.get('arquivo_original'):
                                                comentarios = extrair_comentarios_analise(resposta.text)
                                                if comentarios:
                                                    with st.spinner("📝 Adicionando comentários ao PDF..."):
                                                        pdf_com_comentarios = adicionar_comentarios_pdf(
                                                            doc['arquivo_original'],
                                                            comentarios[:limitar_comentarios],
                                                            doc['nome']
                                                        )
                                                        
                                                        if pdf_com_comentarios:
                                                            resultados_pdf[doc['nome']] = {
                                                                'pdf_com_comentarios': pdf_com_comentarios,
                                                                'comentarios': comentarios,
                                                                'relatorio': resposta.text
                                                            }
                                                            
                                                            st.download_button(
                                                                label="Baixar PDF com Comentários",
                                                                data=pdf_com_comentarios.getvalue(),
                                                                file_name=f"comentarios_{doc['nome']}",
                                                                mime="application/pdf",
                                                                key=f"download_pdf_{doc['nome']}"
                                                            )
                                        
                                    except Exception as e:
                                        st.error(f"Erro na análise de {doc['nome']}: {str(e)}")
                        
                        # Armazenar na sessão
                        st.session_state.todos_textos = todos_textos
                        st.session_state.resultados_pdf = resultados_pdf
                        
                        # DOWNLOADS CONSOLIDADOS
                        if resultados_pdf or gerar_relatorio_completo:
                            st.markdown("---")
                            st.subheader("Downloads Consolidados")
                            
                            # Download de todos os PDFs com comentários
                            if resultados_pdf and incluir_comentarios_pdf:
                                col_dl1, col_dl2 = st.columns(2)
                                
                                with col_dl1:
                                    # Criar ZIP com todos os PDFs comentados
                                    import zipfile
                                    from io import BytesIO
                                    
                                    zip_buffer = BytesIO()
                                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                        for nome_doc, resultado in resultados_pdf.items():
                                            pdf_data = resultado['pdf_com_comentarios'].getvalue()
                                            zip_file.writestr(f"comentarios_{nome_doc}", pdf_data)
                                    
                                    zip_buffer.seek(0)
                                    
                                    st.download_button(
                                        "📚 Baixar Todos os PDFs com Comentários (ZIP)",
                                        data=zip_buffer.getvalue(),
                                        file_name=f"pdfs_com_comentarios_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.zip",
                                        mime="application/zip",
                                        key="download_zip_pdfs"
                                    )
                                
                                with col_dl2:
                                    # Relatório completo com todos os comentários
                                    if gerar_relatorio_completo:
                                        relatorio_completo = f"""
# 📋 RELATÓRIO COMPLETO DE VALIDAÇÃO

**Data:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}
**Agente:** {agente.get('nome', 'N/A')}
**Total de Documentos:** {len(todos_textos)}
**Contexto Aplicado:** {contexto_global if contexto_global else 'Nenhum contexto adicional'}

## DOCUMENTOS ANALISADOS:
"""
                                        
                                        for doc in todos_textos:
                                            relatorio_completo += f"\n### 📄 {doc['nome']}\n"
                                            if doc['nome'] in resultados_pdf:
                                                resultado = resultados_pdf[doc['nome']]
                                                relatorio_completo += f"**Comentários extraídos:** {len(resultado['comentarios'])}\n\n"
                                                for i, comentario in enumerate(resultado['comentarios'][:limitar_comentarios], 1):
                                                    relatorio_completo += f"**Comentário {i}:** {comentario}\n\n"
                                            relatorio_completo += "---\n"
                                        
                                        st.download_button(
                                            "Baixar Relatório Completo (TXT)",
                                            data=relatorio_completo,
                                            file_name=f"relatorio_completo_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                                            mime="text/plain",
                                            key="download_relatorio_completo"
                                        )
                            
                            # Download individual de relatórios de comentários
                            if gerar_relatorio_completo:
                                st.markdown("### 📄 Relatórios Individuais de Comentários")
                                
                                for nome_doc, resultado in resultados_pdf.items():
                                    col_rel1, col_rel2 = st.columns([3, 1])
                                    
                                    with col_rel1:
                                        st.write(f"**{nome_doc}** - {len(resultado['comentarios'])} comentários")
                                    
                                    with col_rel2:
                                        relatorio_individual = criar_relatorio_comentarios(
                                            resultado['comentarios'],
                                            nome_doc,
                                            resultado['relatorio'][:500]  # Contexto resumido
                                        )
                                        
                                        st.download_button(
                                            "Baixar Relatório",
                                            data=relatorio_individual,
                                            file_name=f"relatorio_comentarios_{nome_doc.split('.')[0]}.txt",
                                            mime="text/plain",
                                            key=f"download_relatorio_{nome_doc}"
                                        )
                
                else:
                    st.info("Digite texto ou carregue arquivos para validar")
        
        # --- SUBTAB: VALIDAÇÃO DE IMAGEM ---
        with subtab_imagem:
            st.subheader("Validação de Imagem")
            
            # Botão para limpar análises de imagem
            if st.button("🗑️ Limpar Análises de Imagem", key="limpar_analises_imagem"):
                st.session_state.resultados_analise_imagem = []
                st.rerun()
            
            uploaded_images = st.file_uploader(
                "Carregue uma ou mais imagens para análise", 
                type=["jpg", "jpeg", "png", "webp"], 
                key="image_upload_validacao",
                accept_multiple_files=True
            )
            
            # Configurações de análise de imagem
            with st.expander("⚙️ Configurações de Análise de Imagem"):
                analise_especializada_imagem = st.checkbox(
                    "Análise especializada por áreas (recomendado)",
                    value=st.session_state.analise_especializada_imagem,
                    help="Usa múltiplos especialistas visuais para análise mais precisa",
                    key="analise_especializada_imagem_check"
                )
                
                analisadores_selecionados_imagem = st.multiselect(
                    "Especialistas de imagem a incluir:",
                    options=['composicao_visual', 'cores_branding', 'tipografia_texto', 'elementos_marca', 'impacto_comunicacao'],
                    default=st.session_state.analisadores_selecionados_imagem,
                    format_func=lambda x: {
                        'composicao_visual': 'Composição Visual',
                        'cores_branding': 'Cores e Branding', 
                        'tipografia_texto': 'Tipografia e Texto',
                        'elementos_marca': 'Elementos de Marca',
                        'impacto_comunicacao': 'Impacto e Comunicação'
                    }[x],
                    key="analisadores_imagem_select"
                )
            
            if uploaded_images:
                st.success(f"✅ {len(uploaded_images)} imagem(ns) carregada(s)")
                
                # Botão para validar todas as imagens
                if st.button("🔍 Validar Todas as Imagens", type="primary", key="validar_imagens_multiplas"):
                    
                    # Lista para armazenar resultados
                    resultados_analise = []
                    
                    # Loop através de cada imagem
                    for idx, uploaded_image in enumerate(uploaded_images):
                        with st.spinner(f'Analisando imagem {idx+1} de {len(uploaded_images)}: {uploaded_image.name}...'):
                            try:
                                # Criar container para cada imagem
                                with st.container():
                                    st.markdown("---")
                                    col_img, col_info = st.columns([2, 1])
                                    
                                    with col_img:
                                        # Exibir imagem
                                        image = Image.open(uploaded_image)
                                        st.image(image, use_container_width=True, caption=f"Imagem {idx+1}: {uploaded_image.name}")
                                    
                                    with col_info:
                                        # Informações da imagem
                                        st.metric("📐 Dimensões", f"{image.width} x {image.height}")
                                        st.metric("📊 Formato", uploaded_image.type)
                                        st.metric("📁 Tamanho", f"{uploaded_image.size / 1024:.1f} KB")
                                    
                                    # Contexto aplicado
                                    if contexto_global and contexto_global.strip():
                                        st.info(f"**🎯 Contexto Aplicado:** {contexto_global}")
                                    
                                    # Análise individual
                                    with st.expander(f"📋 Análise Detalhada - Imagem {idx+1}", expanded=True):
                                        try:
                                            # Construir contexto com base de conhecimento do agente
                                            contexto_agente = ""
                                            if "base_conhecimento" in agente:
                                                contexto_agente = f"""
                                                ###BEGIN DIRETRIZES DE BRANDING DO AGENTE:###
                                                {agente['base_conhecimento']}
                                                ###END DIRETRIZES DE BRANDING DO AGENTE###
                                                """
                                            
                                            # Adicionar contexto global se fornecido
                                            contexto_completo = contexto_agente
                                            if contexto_global and contexto_global.strip():
                                                contexto_completo += f"""
                                                ###BEGIN CONTEXTO ADICIONAL DO USUARIO###
                                                {contexto_global}
                                                ###END CONTEXTO ADICIONAL DO USUARIO###
                                                """
                                            
                                            # Escolher método de análise
                                            if st.session_state.analise_especializada_imagem:
                                                # ANÁLISE ESPECIALIZADA POR MÚLTIPLOS ESPECIALISTAS VISUAIS
                                                st.info("🎯 **Executando análise especializada por múltiplos especialistas visuais...**")
                                                
                                                # Criar analisadores especialistas
                                                analisadores_config = criar_analisadores_imagem(contexto_completo, "")
                                                
                                                # Filtrar apenas os selecionados
                                                analisadores_filtrados = {k: v for k, v in analisadores_config.items() 
                                                                         if k in st.session_state.analisadores_selecionados_imagem}
                                                
                                                # Executar análises especializadas
                                                resultados_especialistas = executar_analise_imagem_especializada(
                                                    uploaded_image, 
                                                    uploaded_image.name, 
                                                    analisadores_filtrados
                                                )
                                                
                                                # Gerar relatório consolidado
                                                relatorio_consolidado = gerar_relatorio_imagem_consolidado(
                                                    resultados_especialistas, 
                                                    uploaded_image.name,
                                                    f"{image.width}x{image.height}"
                                                )
                                                
                                                st.markdown(relatorio_consolidado, unsafe_allow_html=True)
                                                
                                                # Armazenar resultado
                                                resultados_analise.append({
                                                    'nome': uploaded_image.name,
                                                    'indice': idx,
                                                    'analise': relatorio_consolidado,
                                                    'dimensoes': f"{image.width}x{image.height}",
                                                    'tamanho': uploaded_image.size
                                                })
                                                
                                            else:
                                                # Análise geral da imagem (método antigo)
                                                prompt_analise = f"""
                                                {contexto_completo}
                                                
                                                Analise esta imagem e verifique o alinhamento com as diretrizes de branding.
                                                
                                                Forneça a análise em formato claro:
                                                
                                                ## RELATÓRIO DE ALINHAMENTO - IMAGEM {idx+1}
                                                
                                                **Arquivo:** {uploaded_image.name}
                                                **Dimensões:** {image.width} x {image.height}
                                                
                                                ### RESUMO DA IMAGEM
                                                [Avaliação geral de conformidade visual e textual]
                                                
                                                ### ELEMENTOS ALINHADOS 
                                                [Itens visuais e textuais que seguem as diretrizes]
                                                
                                                ### ELEMENTOS FORA DO PADRÃO
                                                [Itens visuais e textuais que não seguem as diretrizes]
                                                
                                                ### RECOMENDAÇÕES
                                                [Sugestões para melhorar o alinhamento visual e textual]
                                                
                                                ### ASPECTOS TÉCNICOS
                                                [Composição, cores, tipografia, etc.]
                                                """
                                                
                                                # Processar imagem
                                                response = modelo_vision.generate_content([
                                                    prompt_analise,
                                                    {"mime_type": "image/jpeg", "data": uploaded_image.getvalue()}
                                                ])
                                                
                                                st.markdown(response.text)
                                                
                                                # Armazenar resultado
                                                resultados_analise.append({
                                                    'nome': uploaded_image.name,
                                                    'indice': idx,
                                                    'analise': response.text,
                                                    'dimensoes': f"{image.width}x{image.height}",
                                                    'tamanho': uploaded_image.size
                                                })
                                            
                                        except Exception as e:
                                            st.error(f"Erro ao processar imagem {uploaded_image.name}: {str(e)}")
                                
                                # Separador visual entre imagens
                                if idx < len(uploaded_images) - 1:
                                    st.markdown("---")
                                    
                            except Exception as e:
                                st.error(f"Erro ao carregar imagem {uploaded_image.name}: {str(e)}")
                    
                    # Armazenar na sessão
                    st.session_state.resultados_analise_imagem = resultados_analise
                    
                    # Resumo executivo
                    st.markdown("---")
                    st.subheader("Resumo Executivo de Imagens")
                    
                    col_resumo1, col_resumo2, col_resumo3 = st.columns(3)
                    with col_resumo1:
                        st.metric("📊 Total de Imagens", len(uploaded_images))
                    with col_resumo2:
                        st.metric("Análises Concluídas", len(resultados_analise))
                    with col_resumo3:
                        st.metric("Processadas", len(uploaded_images))
                    
                    # Contexto aplicado no resumo
                    if contexto_global and contexto_global.strip():
                        st.info(f"**Contexto Aplicado em Todas as Análises:** {contexto_global}")
                    
                    # Botão para download do relatório consolidado
                    if st.button("Exportar Relatório Completo de Imagens", key="exportar_relatorio_imagens"):
                        relatorio = f"""
                        # RELATÓRIO DE VALIDAÇÃO DE IMAGENS
                        
                        **Agente:** {agente.get('nome', 'N/A')}
                        **Data:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}
                        **Total de Imagens:** {len(uploaded_images)}
                        **Contexto Aplicado:** {contexto_global if contexto_global else 'Nenhum contexto adicional'}
                        **Método de Análise:** {'Especializada por Múltiplos Especialistas' if st.session_state.analise_especializada_imagem else 'Tradicional'}
                        
                        ## RESUMO EXECUTIVO
                        {chr(10).join([f"{idx+1}. {img.name}" for idx, img in enumerate(uploaded_images)])}
                        
                        ## ANÁLISES INDIVIDUAIS
                        {chr(10).join([f'### {res["nome"]} {chr(10)}{res["analise"]}' for res in resultados_analise])}
                        """
                        
                        st.download_button(
                            "Baixar Relatório em TXT",
                            data=relatorio,
                            file_name=f"relatorio_validacao_imagens_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                            mime="text/plain"
                        )
            
            # Mostrar análises existentes da sessão
            elif st.session_state.resultados_analise_imagem:
                st.info("Análises anteriores encontradas. Use o botão 'Limpar Análises' para recomeçar.")
                
                for resultado in st.session_state.resultados_analise_imagem:
                    with st.expander(f"{resultado['nome']} - Análise Salva", expanded=False):
                        st.markdown(resultado['analise'])
            
            else:
                st.info("Carregue uma ou mais imagens para iniciar a validação de branding")
        
        # --- SUBTAB: VALIDAÇÃO DE VÍDEO ---
        with subtab_video:
            st.subheader("🎬 Validação de Vídeo")
            
            # Botão para limpar análises de vídeo
            if st.button("🗑️ Limpar Análises de Vídeo", key="limpar_analises_video"):
                st.session_state.resultados_analise_video = []
                st.rerun()
            
            # Container principal
            col_upload, col_config = st.columns([2, 1])
            
            with col_upload:
                uploaded_videos = st.file_uploader(
                    "Carregue um ou mais vídeos para análise",
                    type=["mp4", "mpeg", "mov", "avi", "flv", "mpg", "webm", "wmv", "3gpp"],
                    key="video_upload_validacao",
                    accept_multiple_files=True
                )
            
            with col_config:
                st.markdown("### ⚙️ Configurações de Vídeo")
                contexto_video_especifico = st.text_area(
                    "**Contexto específico para vídeos:**", 
                    height=120, 
                    key="video_context_especifico",
                    placeholder="Contexto adicional específico para análise de vídeos (opcional)..."
                )
                
                analise_especializada_video = st.checkbox(
                    "Análise especializada por áreas (recomendado)",
                    value=True,  # Sempre ativo por padrão
                    help="Usa múltiplos especialistas em vídeo para análise mais precisa",
                    key="analise_especializada_video_check"
                )
                
                # Definir todos os especialistas disponíveis
                todos_analisadores_video = ['narrativa_estrutura', 'qualidade_audio', 'visual_cinematografia', 'branding_consistencia', 'engajamento_eficacia', 'sincronizacao_audio_legendas']
                
                # SEMPRE selecionar todos os especialistas por padrão
                analisadores_selecionados_video = st.multiselect(
                    "Especialistas de vídeo a incluir:",
                    options=todos_analisadores_video,
                    default=todos_analisadores_video,  # TODOS selecionados por padrão
                    format_func=lambda x: {
                        'narrativa_estrutura': 'Narrativa e Estrutura',
                        'qualidade_audio': 'Qualidade de Áudio', 
                        'visual_cinematografia': 'Visual e Cinematografia',
                        'sincronizacao_audio_legendas': 'Sincronização Áudio-Legendas',
                        'branding_consistencia': 'Branding e Consistência',
                        'engajamento_eficacia': 'Engajamento e Eficácia'
                    }[x],
                    key="analisadores_video_select"
                )
                
                # Botão para selecionar automaticamente todos os especialistas
                if st.button("✅ Selecionar Todos os Especialistas", key="select_all_video_analysts"):
                    st.session_state.analisadores_selecionados_video = todos_analisadores_video
                    st.rerun()
            
            if uploaded_videos:
                st.success(f"✅ {len(uploaded_videos)} vídeo(s) carregado(s)")
                
                # Contexto aplicado
                if contexto_global and contexto_global.strip():
                    st.info(f"**Contexto Global Aplicado:** {contexto_global}")
                if contexto_video_especifico and contexto_video_especifico.strip():
                    st.info(f"**Contexto Específico Aplicado:** {contexto_video_especifico}")
                
                # Exibir informações dos vídeos
                st.markdown("### Informações dos Vídeos")
                
                for idx, video in enumerate(uploaded_videos):
                    col_vid, col_info, col_actions = st.columns([2, 2, 1])
                    
                    with col_vid:
                        st.write(f"**{idx+1}. {video.name}**")
                        st.caption(f"Tipo: {video.type} | Tamanho: {video.size / (1024*1024):.1f} MB")
                    
                    with col_info:
                        st.write("📏 Duração: A ser detectada")
                        st.write("🎞️ Resolução: A ser detectada")
                    
                    with col_actions:
                        if st.button("🔍 Preview", key=f"preview_{idx}"):
                            st.video(video, format=f"video/{video.type.split('/')[-1]}")
                
                # Botão para validar todos os vídeos
                if st.button("🎬 Validar Todos os Vídeos", type="primary", key="validar_videos_multiplas"):
                    
                    resultados_video = []
                    
                    for idx, uploaded_video in enumerate(uploaded_videos):
                        with st.spinner(f'Analisando vídeo {idx+1} de {len(uploaded_videos)}: {uploaded_video.name}...'):
                            try:
                                # Container para cada vídeo
                                with st.container():
                                    st.markdown("---")
                                    
                                    # Header do vídeo
                                    col_header, col_stats = st.columns([3, 1])
                                    
                                    with col_header:
                                        st.subheader(f"🎬 {uploaded_video.name}")
                                    
                                    with col_stats:
                                        st.metric("📊 Status", "Processando")
                                    
                                    # Contexto aplicado para este vídeo
                                    if contexto_global and contexto_global.strip():
                                        st.info(f"**🎯 Contexto Aplicado:** {contexto_global}")
                                    if contexto_video_especifico and contexto_video_especifico.strip():
                                        st.info(f"**🎯 Contexto Específico:** {contexto_video_especifico}")
                                    
                                    # Preview do vídeo
                                    with st.expander("👀 Preview do Vídeo", expanded=False):
                                        st.video(uploaded_video, format=f"video/{uploaded_video.type.split('/')[-1]}")
                                    
                                    # Análise detalhada
                                    with st.expander(f"📋 Análise Completa - {uploaded_video.name}", expanded=True):
                                        try:
                                            # Construir contexto com base de conhecimento do agente
                                            contexto_agente = ""
                                            if "base_conhecimento" in agente:
                                                contexto_agente = f"""
                                                ###BEGIN DIRETRIZES DE BRANDING DO AGENTE:###
                                                {agente['base_conhecimento']}
                                                ###END DIRETRIZES DE BRANDING DO AGENTE###
                                                """
                                            
                                            # Adicionar contexto global se fornecido
                                            contexto_completo = contexto_agente
                                            if contexto_global and contexto_global.strip():
                                                contexto_completo += f"""
                                                ###BEGIN CONTEXTO GLOBAL DO USUARIO###
                                                {contexto_global}
                                                ###END CONTEXTO GLOBAL DO USUARIO###
                                                """
                                            
                                            # Adicionar contexto específico de vídeo se fornecido
                                            if contexto_video_especifico and contexto_video_especifico.strip():
                                                contexto_completo += f"""
                                                ###BEGIN CONTEXTO ESPECÍFICO PARA VÍDEOS###
                                                {contexto_video_especifico}
                                                ###END CONTEXTO ESPECÍFICO PARA VÍDEOS###
                                                """
                                            
                                            # SEMPRE usar análise especializada com TODOS os especialistas selecionados
                                            st.info("🎯 **Executando análise especializada por TODOS os especialistas de vídeo...**")
                                            
                                            # Atualizar session state com os analisadores selecionados
                                            st.session_state.analisadores_selecionados_video = analisadores_selecionados_video
                                            
                                            # Verificar se há especialistas selecionados
                                            if not analisadores_selecionados_video:
                                                st.warning("⚠️ Nenhum especialista selecionado. Selecionando todos automaticamente.")
                                                analisadores_selecionados_video = todos_analisadores_video
                                                st.session_state.analisadores_selecionados_video = todos_analisadores_video
                                            
                                            # Criar analisadores especialistas
                                            analisadores_config = criar_analisadores_video(contexto_agente, contexto_global, contexto_video_especifico)
                                            
                                            # Usar SEMPRE todos os especialistas selecionados
                                            analisadores_filtrados = {k: v for k, v in analisadores_config.items() 
                                                                     if k in analisadores_selecionados_video}
                                            
                                            # Mostrar quais especialistas estão sendo executados
                                            st.success(f"**Especialistas ativos:** {len(analisadores_filtrados)}")
                                            for analista_key in analisadores_filtrados.keys():
                                                emoji_nome = {
                                                    'narrativa_estrutura': '📖 Narrativa e Estrutura',
                                                    'qualidade_audio': '🔊 Qualidade de Áudio',
                                                    'visual_cinematografia': '🎥 Visual e Cinematografia', 
                                                    'sincronizacao_audio_legendas': '🎯 Sincronização Áudio-Legendas',
                                                    'branding_consistencia': '🏢 Branding e Consistência',
                                                    'engajamento_eficacia': '📈 Engajamento e Eficácia'
                                                }.get(analista_key, analista_key)
                                                st.write(f"  - {emoji_nome}")
                                            
                                            # Executar análises especializadas
                                            resultados_especialistas = executar_analise_video_especializada(
                                                uploaded_video, 
                                                uploaded_video.name, 
                                                analisadores_filtrados
                                            )
                                            
                                            # Gerar relatório consolidado
                                            relatorio_consolidado = gerar_relatorio_video_consolidado(
                                                resultados_especialistas, 
                                                uploaded_video.name,
                                                uploaded_video.type
                                            )
                                            
                                            st.markdown(relatorio_consolidado, unsafe_allow_html=True)
                                            
                                            # Armazenar resultado
                                            resultados_video.append({
                                                'nome': uploaded_video.name,
                                                'indice': idx,
                                                'analise': relatorio_consolidado,
                                                'tipo': uploaded_video.type,
                                                'tamanho': uploaded_video.size,
                                                'especialistas_utilizados': list(analisadores_filtrados.keys())
                                            })
                                            
                                        except Exception as e:
                                            st.error(f"❌ Erro ao processar vídeo {uploaded_video.name}: {str(e)}")
                                            resultados_video.append({
                                                'nome': uploaded_video.name,
                                                'indice': idx,
                                                'analise': f"Erro na análise: {str(e)}",
                                                'tipo': uploaded_video.type,
                                                'tamanho': uploaded_video.size,
                                                'especialistas_utilizados': []
                                            })
                                    
                            except Exception as e:
                                st.error(f"❌ Erro ao processar vídeo {uploaded_video.name}: {str(e)}")
                    
                    # Armazenar resultados na sessão
                    st.session_state.resultados_analise_video = resultados_video
                    
                    # Resumo executivo dos vídeos
                    st.markdown("---")
                    st.subheader("📋 Resumo Executivo - Vídeos")
                    
                    col_vid1, col_vid2, col_vid3 = st.columns(3)
                    with col_vid1:
                        st.metric("🎬 Total de Vídeos", len(uploaded_videos))
                    with col_vid2:
                        st.metric("✅ Análises Concluídas", len(resultados_video))
                    with col_vid3:
                        total_especialistas = sum(len(res.get('especialistas_utilizados', [])) for res in resultados_video)
                        st.metric("🎯 Especialistas Executados", total_especialistas)
                    
                    # Contexto aplicado no resumo
                    if contexto_global and contexto_global.strip():
                        st.info(f"**🎯 Contexto Global Aplicado:** {contexto_global}")
                    if contexto_video_especifico and contexto_video_especifico.strip():
                        st.info(f"**🎯 Contexto Específico Aplicado:** {contexto_video_especifico}")
                    
                    # Mostrar especialistas utilizados
                    st.info(f"**🔧 Especialistas utilizados na análise:** {', '.join([analisadores_config[k]['nome'] for k in analisadores_selecionados_video if k in analisadores_config])}")
                    
                    # Botão para download do relatório
                    if st.button("📥 Exportar Relatório de Vídeos", key="exportar_relatorio_videos"):
                        relatorio_videos = f"""
                        # RELATÓRIO DE VALIDAÇÃO DE VÍDEOS
                        
                        **Agente:** {agente.get('nome', 'N/A')}
                        **Data:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}
                        **Total de Vídeos:** {len(uploaded_videos)}
                        **Contexto Global:** {contexto_global if contexto_global else 'Nenhum'}
                        **Contexto Específico:** {contexto_video_especifico if contexto_video_especifico else 'Nenhum'}
                        **Método de Análise:** Análise Especializada por Múltiplos Especialistas
                        **Especialistas Utilizados:** {', '.join(analisadores_selecionados_video)}
                        
                        ## VÍDEOS ANALISADOS:
                        {chr(10).join([f"{idx+1}. {vid.name} ({vid.type}) - {vid.size/(1024*1024):.1f} MB" for idx, vid in enumerate(uploaded_videos)])}
                        
                        ## ANÁLISES INDIVIDUAIS:
                        {chr(10).join([f'### {res["nome"]} {chr(10)}{res["analise"]}' for res in resultados_video])}
                        """
                        
                        st.download_button(
                            "💾 Baixar Relatório em TXT",
                            data=relatorio_videos,
                            file_name=f"relatorio_validacao_videos_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                            mime="text/plain"
                        )
            
            # Mostrar análises existentes da sessão
            elif st.session_state.get('resultados_analise_video'):
                st.info("📋 Análises anteriores encontradas. Use o botão 'Limpar Análises' para recomeçar.")
                
                for resultado in st.session_state.resultados_analise_video:
                    with st.expander(f"🎬 {resultado['nome']} - Análise Salva", expanded=False):
                        st.markdown(resultado['analise'])
                        if resultado.get('especialistas_utilizados'):
                            st.caption(f"**Especialistas utilizados:** {', '.join(resultado['especialistas_utilizados'])}")
            
            else:
                st.info("🎬 Carregue um ou mais vídeos para iniciar a validação")
                
# --- ABA: GERAÇÃO DE CONTEÚDO (COM BUSCA WEB FUNCIONAL) ---
with tab_mapping["✨ Geração de Conteúdo"]:
    st.header("✨ Geração de Conteúdo com Múltiplos Insumos")
    
    # Configuração da API do OpenAI
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        openai_client = OpenAI(api_key=openai_api_key)
    else:
        openai_client = None
    
    # Conexão com MongoDB para briefings
    try:
        client2 = MongoClient("mongodb+srv://gustavoromao3345:RqWFPNOJQfInAW1N@cluster0.5iilj.mongodb.net/auto_doc?retryWrites=true&w=majority&ssl=true&ssl_cert_reqs=CERT_NONE&tlsAllowInvalidCertificates=true")
        db_briefings = client2['briefings_Broto_Tecnologia']
        collection_briefings = db_briefings['briefings']
        mongo_connected_conteudo = True
    except Exception as e:
        mongo_connected_conteudo = False

    # Função para gerar conteúdo com diferentes modelos
    def gerar_conteudo_modelo(prompt: str, modelo_escolhido: str = "Gemini", contexto_agente: str = None) -> str:
        """Gera conteúdo usando diferentes modelos de LLM"""
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
                    system_prompt = "Você é um assistente útil para geração de conteúdo."
                
                message = anthropic_client.messages.create(
                    max_tokens=4000,
                    messages=[{"role": "user", "content": prompt}],
                    model="claude-haiku-4-5-20251001",
                    system=system_prompt
                )
                return message.content[0].text
                
            elif modelo_escolhido == "OpenAI" and openai_client:
                try:
                    response = openai_client.responses.create(
                        model="gpt-4o-mini",
                        input=prompt,
                        instructions=contexto_agente if contexto_agente else "Você é um assistente especializado em geração de conteúdo."
                    )
                    return response.output_text
                except Exception as openai_error:
                    try:
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
                    except Exception as fallback_error:
                        return f"❌ Erro com OpenAI: {str(fallback_error)}"
                
            else:
                return f"❌ Modelo {modelo_escolhido} não disponível. Verifique as configurações da API."
                
        except Exception as e:
            return f"❌ Erro ao gerar conteúdo com {modelo_escolhido}: {str(e)}"

    # FUNÇÃO PARA BUSCA WEB COM FONTES
    def realizar_busca_web_com_fontes(termos_busca: str, contexto_agente: str = None) -> str:
        """Realiza busca web usando API do Perplexity e RETORNA SEMPRE AS FONTES"""
        if not perp_api_key:
            return "❌ API do Perplexity não configurada. Configure a variável de ambiente PERP_API_KEY."
        
        try:
            headers = {
                "Authorization": f"Bearer {perp_api_key}",
                "Content-Type": "application/json"
            }
            
            mensagem_sistema = contexto_agente if contexto_agente else "Você é um assistente de pesquisa que fornece informações precisas e atualizadas COM FONTES."
            
            data = {
                "model": "sonar",
                "messages": [
                    {
                        "role": "system",
                        "content": f"{mensagem_sistema}\n\nIMPORTANTE: Você DEVE SEMPRE incluir as fontes (links e nomes dos sites) de onde tirou as informações. Para cada informação ou dado, mencione a fonte específica no formato: **Fonte: [Nome do Site/Portal] ([link completo])**"
                    },
                    {
                        "role": "user", 
                        "content": f"""Pesquise informações sobre: {termos_busca}

                        REQUISITOS OBRIGATÓRIOS:
                        1. Forneça informações TÉCNICAS e ATUALIZADAS (últimos 2-3 anos)
                        2. INCLUA SEMPRE as fontes para cada informação
                        3. Use o formato: **Fonte: [Nome do Site/Portal] ([link completo])**
                        4. Priorize fontes confiáveis: sites governamentais, instituições de pesquisa, universidades, órgãos oficiais
                        5. Forneça dados concretos: números, estatísticas, resultados
                        6. Seja preciso nas citações
                        
                        ESTRUTURA DA RESPOSTA:
                        1. Introdução sobre o tema
                        2. Dados e estatísticas (com fontes)
                        3. Tendências recentes (com fontes)
                        4. Melhores práticas (com fontes)
                        5. Conclusão com insights (com fontes)
                        
                        FORNECER INFORMAÇÕES COM ANCORAGEM DE REFERÊNCIAS - cada parágrafo ou dado deve ter sua fonte citada."""
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
                resposta_completa = result['choices'][0]['message']['content']
                
                if any(keyword in resposta_completa.lower() for keyword in ['fonte:', 'source:', 'http', 'https', 'www.', '.com', '.br', '.org', '.gov']):
                    return resposta_completa
                else:
                    return f"{resposta_completa}\n\n⚠️ **AVISO:** As fontes não foram incluídas na resposta. Recomendo reformular a busca para termos mais específicos."
            else:
                return f"❌ Erro na busca web (código {response.status_code}): {response.text}"
                
        except requests.exceptions.Timeout:
            return "❌ Tempo esgotado na busca web. Tente novamente com termos mais específicos."
        except Exception as e:
            return f"❌ Erro ao realizar busca web: {str(e)}"

    # Função para analisar URLs específicas COM FONTES
    def analisar_urls_com_fontes(urls: List[str], pergunta: str, contexto_agente: str = None) -> str:
        """Analisa URLs específicas usando Perplexity SEMPRE com fontes"""
        try:
            headers = {
                "Authorization": f"Bearer {perp_api_key}",
                "Content-Type": "application/json"
            }
            
            urls_contexto = "\n".join([f"- {url}" for url in urls])
            
            messages = []
            
            if contexto_agente:
                messages.append({
                    "role": "system",
                    "content": f"Contexto do agente: {contexto_agente}\n\nIMPORTANTE: Sempre cite as fontes específicas das URLs analisadas."
                })
            else:
                messages.append({
                    "role": "system",
                    "content": "Você é um analista de conteúdo. Sempre cite as fontes específicas das URLs analisadas."
                })
            
            messages.append({
                "role": "user",
                "content": f"""Analise as seguintes URLs e responda à pergunta:

URLs para análise (CITE CADA UMA ESPECIFICAMENTE):
{urls_contexto}

Pergunta específica: {pergunta}

REQUISITOS OBRIGATÓRIOS:
1. Para cada informação, mencione de qual URL específica veio
2. Use formato: **Fonte: [Nome do Site/Portal] ([URL específica])**
3. Se uma informação vem de múltiplas URLs, cite todas
4. Seja preciso nas citações
5. Analise o conteúdo técnico de cada URL

Forneça uma análise detalhada baseada no conteúdo dessas URLs, sempre citando as fontes específicas."""
            })
            
            data = {
                "model": "sonar-medium-online",
                "messages": messages,
                "max_tokens": 3000,
                "temperature": 0.0
            }
            
            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=data,
                timeout=45
            )
            
            if response.status_code == 200:
                result = response.json()
                resposta_completa = result['choices'][0]['message']['content']
                
                if any(url in resposta_completa for url in urls):
                    return resposta_completa
                else:
                    return f"{resposta_completa}\n\n⚠️ **AVISO:** As URLs não foram citadas na resposta. As informações podem não estar devidamente referenciadas."
            else:
                return f"❌ Erro na análise: {response.status_code} - {response.text}"
                
        except Exception as e:
            return f"❌ Erro ao analisar URLs: {str(e)}"

    # Função para extrair texto de diferentes tipos de arquivo
    def extrair_texto_arquivo(arquivo):
        """Extrai texto de diferentes formatos de arquivo"""
        try:
            extensao = arquivo.name.split('.')[-1].lower()
            
            if extensao == 'pdf':
                return extrair_texto_pdf(arquivo)
            elif extensao == 'txt':
                return extrair_texto_txt(arquivo)
            elif extensao in ['pptx', 'ppt']:
                return extrair_texto_pptx(arquivo)
            elif extensao in ['docx', 'doc']:
                return extrair_texto_docx(arquivo)
            else:
                return f"Formato {extensao} não suportado para extração de texto."
                
        except Exception as e:
            return f"Erro ao extrair texto do arquivo {arquivo.name}: {str(e)}"

    def extrair_texto_pdf(arquivo):
        """Extrai texto de arquivos PDF"""
        try:
            import PyPDF2
            pdf_reader = PyPDF2.PdfReader(arquivo)
            texto = ""
            for pagina in pdf_reader.pages:
                texto += pagina.extract_text() + "\n"
            return texto
        except Exception as e:
            return f"Erro na leitura do PDF: {str(e)}"

    def extrair_texto_txt(arquivo):
        """Extrai texto de arquivos TXT"""
        try:
            return arquivo.read().decode('utf-8')
        except:
            try:
                return arquivo.read().decode('latin-1')
            except Exception as e:
                return f"Erro na leitura do TXT: {str(e)}"

    def extrair_texto_pptx(arquivo):
        """Extrai texto de arquivos PowerPoint"""
        try:
            from pptx import Presentation
            import io
            prs = Presentation(io.BytesIO(arquivo.read()))
            texto = ""
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        texto += shape.text + "\n"
            return texto
        except Exception as e:
            return f"Erro na leitura do PowerPoint: {str(e)}"

    def extrair_texto_docx(arquivo):
        """Extrai texto de arquivos Word"""
        try:
            import docx
            import io
            doc = docx.Document(io.BytesIO(arquivo.read()))
            texto = ""
            for para in doc.paragraphs:
                texto += para.text + "\n"
            return texto
        except Exception as e:
            return f"Erro na leitura do Word: {str(e)}"

    # Função para ajuste incremental do conteúdo
    def ajustar_conteudo_incremental(conteudo_original: str, instrucoes_ajuste: str, modelo_escolhido: str = "Gemini", contexto_agente: str = None) -> str:
        """Realiza ajustes incrementais no conteúdo mantendo a estrutura original"""
        
        prompt_ajuste = f"""
        CONTEÚDO ORIGINAL:
        {conteudo_original}
        
        INSTRUÇÕES DE AJUSTE:
        {instrucoes_ajuste}
        
        DIRETRIZES PARA AJUSTE:
        1. Mantenha a estrutura geral do conteúdo original
        2. Preserve o tom de voz e estilo original
        3. Incorpore as mudanças solicitadas de forma natural
        4. Não remova informações importantes não mencionadas nas instruções
        5. Mantenha a consistência com o conteúdo existente
        6. PRESERVE AS FONTES: mantenha todas as citações de fontes e links
        
        FORNECER APENAS O CONTEÚDO AJUSTADO, sem comentários ou explicações adicionais.
        """
        
        try:
            resposta = gerar_conteudo_modelo(prompt_ajuste, modelo_escolhido, contexto_agente)
            return resposta
        except Exception as e:
            return f"❌ Erro ao ajustar conteúdo: {str(e)}"

    # Layout principal com tabs
    tab_geracao, tab_ajuste = st.tabs(["📝 Geração de Conteúdo", "✏️ Ajustes Incrementais"])

    with tab_geracao:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📝 Fontes de Conteúdo")
            
            usar_busca_web = st.checkbox(
                "🔍 Realizar busca web para obter informações atualizadas com fontes",
                value=True,
                key="usar_busca_web_conteudo"
            )
            
            if usar_busca_web:
                if not perp_api_key:
                    st.write("❌ API do Perplexity não configurada. Configure a variável de ambiente PERP_API_KEY.")
                else:
                    termos_busca = st.text_area(
                        "🔎 Termos para busca web (obtenha informações com fontes):",
                        height=100,
                        placeholder="Ex: tendências marketing digital 2024, estatísticas redes sociais Brasil, exemplos campanhas bem-sucedidas...",
                        key="termos_busca_conteudo"
                    )
                    
                    if termos_busca:
                        st.write(f"📝 {len(termos_busca)} caracteres")
            
            # Upload de múltiplos arquivos
            st.write("📎 Upload de Arquivos (PDF, TXT, PPTX, DOCX):")
            arquivos_upload = st.file_uploader(
                "Selecione um ou mais arquivos:",
                type=['pdf', 'txt', 'pptx', 'ppt', 'docx', 'doc'],
                accept_multiple_files=True,
                key="arquivos_conteudo"
            )
            
            textos_arquivos = ""
            if arquivos_upload:
                for i, arquivo in enumerate(arquivos_upload):
                    texto_extraido = extrair_texto_arquivo(arquivo)
                    textos_arquivos += f"\n\n--- CONTEÚDO DE {arquivo.name.upper()} ---\n{texto_extraido}"
            
            # Upload de imagem para geração de legenda
            st.write("🖼️ Gerar Legenda para Imagem:")
            imagem_upload = st.file_uploader(
                "Selecione uma imagem:",
                type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'],
                key="imagem_conteudo"
            )
            
            if imagem_upload:
                col_img1, col_img2 = st.columns([1, 2])
                with col_img1:
                    st.image(imagem_upload, caption="Imagem Carregada", use_container_width=True)
                
                with col_img2:
                    estilo_legenda = st.selectbox(
                        "Estilo da Legenda:",
                        ["Descritiva", "Criativa", "Técnica", "Comercial", "Emocional", "Storytelling"],
                        key="estilo_legenda"
                    )
                    
                    comprimento_legenda = st.select_slider(
                        "Comprimento da Legenda:",
                        options=["Curta", "Média", "Longa"],
                        value="Média",
                        key="comprimento_legenda"
                    )
                    
                    incluir_hashtags = st.checkbox("Incluir hashtags relevantes", value=True, key="hashtags_legenda")
                    
                    modelo_legenda = st.selectbox(
                        "Modelo para gerar legenda:",
                        ["Gemini", "Claude", "OpenAI"],
                        key="modelo_legenda_select"
                    )
                    
                    if st.button("📝 Gerar Legenda para esta Imagem", use_container_width=True, key="gerar_legenda_btn"):
                        if not st.session_state.agente_selecionado:
                            st.write("❌ Selecione um agente primeiro para usar seu contexto na geração da legenda")
                        else:
                            try:
                                contexto_agente = ""
                                if st.session_state.agente_selecionado:
                                    agente = st.session_state.agente_selecionado
                                    contexto_agente = construir_contexto(agente, st.session_state.segmentos_selecionados)
                                
                                prompt_legenda = f"""
                                ## GERAÇÃO DE LEGENDA PARA IMAGEM:
                                
                                **ESTILO SOLICITADO:** {estilo_legenda}
                                **COMPRIMENTO:** {comprimento_legenda}
                                **INCLUIR HASHTAGS:** {incluir_hashtags}
                                
                                ## TAREFA:
                                Analise a imagem e gere uma legenda que:
                                
                                1. **Descreva** accuratamente o conteúdo visual
                                2. **Contextualize** com base no conhecimento do agente selecionado
                                3. **Engaje** o público-alvo apropriado
                                4. **Siga** o estilo {estilo_legenda.lower()}
                                5. **Tenha** comprimento {comprimento_legenda.lower()}
                                { "6. **Inclua** hashtags relevantes ao final" if incluir_hashtags else "" }
                                
                                Seja criativo mas mantenha a precisão factual.
                                """
                                
                                if modelo_legenda == "Gemini":
                                    modelo_visao = genai.GenerativeModel('gemini-2.5-flash')
                                    resposta_legenda = modelo_visao.generate_content([
                                        prompt_legenda,
                                        {"mime_type": imagem_upload.type, "data": imagem_upload.getvalue()}
                                    ])
                                    legenda_gerada = resposta_legenda.text
                                    
                                elif modelo_legenda == "OpenAI" and openai_client:
                                    try:
                                        import base64
                                        encoded_image = base64.b64encode(imagem_upload.getvalue()).decode('utf-8')
                                        
                                        response = openai_client.chat.completions.create(
                                            model="gpt-4o-mini",
                                            messages=[
                                                {
                                                    "role": "system",
                                                    "content": contexto_agente if contexto_agente else "Você é um especialista em geração de legendas para mídias sociais."
                                                },
                                                {
                                                    "role": "user",
                                                    "content": [
                                                        {"type": "text", "text": prompt_legenda},
                                                        {
                                                            "type": "image_url",
                                                            "image_url": {
                                                                "url": f"data:image/jpeg;base64,{encoded_image}"
                                                            }
                                                        }
                                                    ]
                                                }
                                            ],
                                            max_tokens=500
                                        )
                                        legenda_gerada = response.choices[0].message.content
                                        
                                    except Exception as vision_error:
                                        legenda_gerada = gerar_conteudo_modelo(
                                            f"Gere uma legenda {estilo_legenda.lower()} para uma imagem: {prompt_legenda}",
                                            "OpenAI",
                                            contexto_agente
                                        )
                                    
                                else:
                                    legenda_gerada = gerar_conteudo_modelo(
                                        f"Gere uma legenda {estilo_legenda.lower()} para uma imagem: {prompt_legenda}",
                                        modelo_legenda,
                                        contexto_agente
                                    )
                                
                                st.write("✅ Legenda gerada com sucesso!")
                                st.subheader("Legenda Gerada:")
                                st.write(legenda_gerada)
                                
                                st.session_state.conteudo_gerado = legenda_gerada
                                st.session_state.tipo_conteudo_gerado = "legenda_imagem"
                                st.session_state.modelo_utilizado_geracao = modelo_legenda
                                
                                st.download_button(
                                    "📋 Baixar Legenda",
                                    data=legenda_gerada,
                                    file_name=f"legenda_{imagem_upload.name.split('.')[0]}.txt",
                                    mime="text/plain",
                                    key="download_legenda_imagem"
                                )
                                
                                if mongo_connected_conteudo:
                                    try:
                                        historico_legenda = {
                                            "tipo": "legenda_imagem",
                                            "nome_imagem": imagem_upload.name,
                                            "estilo_legenda": estilo_legenda,
                                            "comprimento_legenda": comprimento_legenda,
                                            "modelo_utilizado": modelo_legenda,
                                            "legenda_gerada": legenda_gerada,
                                            "agente_utilizado": st.session_state.agente_selecionado.get('nome') if st.session_state.agente_selecionado else "Nenhum",
                                            "data_criacao": datetime.datetime.now()
                                        }
                                        db_briefings['historico_legendas'].insert_one(historico_legenda)
                                    except Exception as e:
                                        pass
                                    
                            except Exception as e:
                                st.write(f"❌ Erro ao gerar legenda: {str(e)}")
            
            # Inserir briefing manualmente
            st.write("✍️ Briefing Manual:")
            briefing_manual = st.text_area("Ou cole o briefing completo aqui:", height=150,
                                          placeholder="""Exemplo:
Título: Campanha de Lançamento
Objetivo: Divulgar novo produto
Público-alvo: Empresários...
Pontos-chave: [lista os principais pontos]""",
                                          key="briefing_manual")
            
            # Transcrição de áudio/vídeo
            st.write("🎤 Transcrição de Áudio/Vídeo:")
            arquivos_midia = st.file_uploader(
                "Áudios/Vídeos para transcrição:",
                type=['mp3', 'wav', 'mp4', 'mov', 'avi'],
                accept_multiple_files=True,
                key="arquivos_midia"
            )
            
            transcricoes_texto = ""
            if arquivos_midia:
                if st.button("🔄 Transcrever Todos os Arquivos de Mídia", key="transcrever_btn"):
                    for arquivo in arquivos_midia:
                        tipo = "audio" if arquivo.type.startswith('audio') else "video"
                        transcricao = transcrever_audio_video(arquivo, tipo)
                        transcricoes_texto += f"\n\n--- TRANSCRIÇÃO DE {arquivo.name.upper()} ---\n{transcricao}"
        
        with col2:
            st.subheader("⚙️ Configurações de Geração")
            
            modelo_principal = st.selectbox(
                "Escolha o modelo principal:",
                ["Gemini", "Claude", "OpenAI"],
                key="modelo_principal_select",
                index=0
            )
            
            if modelo_principal == "Gemini" and not gemini_api_key:
                st.write("❌ Gemini não disponível")
            elif modelo_principal == "Claude" and not anthropic_api_key:
                st.write("❌ Claude não disponível")
            elif modelo_principal == "OpenAI" and not openai_api_key:
                st.write("❌ OpenAI não disponível")
            
            if st.session_state.agente_selecionado:
                st.write(f"🤖 Agente: {st.session_state.agente_selecionado.get('nome', 'N/A')}")
            else:
                st.write("⚠️ Nenhum agente selecionado")
            
            st.markdown("---")
            st.subheader("🌐 Análise de URLs Específicas")
            
            usar_analise_urls = st.checkbox(
                "Analisar URLs específicas",
                value=False,
                key="usar_analise_urls"
            )
            
            if usar_analise_urls:
                urls_para_analise = st.text_area(
                    "URLs para análise (uma por linha):",
                    height=120,
                    placeholder="https://exemplo.com/artigo1\nhttps://exemplo.com/artigo2\nhttps://exemplo.com/dados",
                    key="urls_analise"
                )
            
            modo_geracao = st.radio(
                "Modo de Geração:",
                ["Configurações Padrão", "Prompt Personalizado"],
                key="modo_geracao"
            )
            
            if modo_geracao == "Configurações Padrão":
                tipo_conteudo = st.selectbox("Tipo de Conteúdo:", 
                                           ["Post Social", "Artigo Blog", "Email Marketing", 
                                            "Landing Page", "Script Vídeo", "Relatório Técnico",
                                            "Press Release", "Newsletter", "Case Study"],
                                           key="tipo_conteudo")
                
                tom_voz = st.text_area(
                    "Tom de Voz:",
                    placeholder="Ex: Formal e profissional, mas acessível\nOu: Casual e descontraído\nOu: Persuasivo e motivacional",
                    key="tom_voz_textarea"
                )
                
                palavras_chave = st.text_input("Palavras-chave (opcional):",
                                              placeholder="separadas por vírgula",
                                              key="palavras_chave")
                
                numero_palavras = st.slider("Número de Palavras:", 100, 3000, 800, key="numero_palavras")
                
                usar_contexto_agente = st.checkbox("Usar contexto do agente selecionado", 
                                                 value=bool(st.session_state.agente_selecionado),
                                                 key="usar_contexto")
                
                incluir_cta = st.checkbox("Incluir Call-to-Action", value=True, key="incluir_cta")
                
                incluir_fontes_destaque = st.checkbox(
                    "Destacar fontes no conteúdo",
                    value=True,
                    key="incluir_fontes_destaque"
                )
            
            else:
                prompt_personalizado = st.text_area(
                    "Seu Prompt Personalizado:",
                    height=200,
                    placeholder="""Exemplo:
Com base no contexto fornecido, crie um artigo detalhado que:

1. Explique os conceitos principais de forma clara
2. Destaque os benefícios para o público-alvo
3. Inclua exemplos práticos de aplicação
4. Mantenha um tom {tom} e acessível
5. **SEMPRE INCLUA AS FONTES** das informações

Contexto: {contexto}

Gere o conteúdo em formato {formato} com aproximadamente {palavras} palavras.""",
                    key="prompt_personalizado"
                )
                
                col_var1, col_var2, col_var3 = st.columns(3)
                with col_var1:
                    tom_personalizado = st.text_area(
                        "Tom:",
                        value="formal e profissional",
                        height=60,
                        key="tom_personalizado_textarea"
                    )
                with col_var2:
                    formato_personalizado = st.selectbox("Formato:", 
                                                       ["texto simples", "markdown", "HTML básico"], 
                                                       key="formato_personalizado")
                with col_var3:
                    palavras_personalizado = st.slider("Palavras:", 100, 3000, 800, key="palavras_personalizado")
                
                usar_contexto_agente = st.checkbox("Usar contexto do agente selecionado", 
                                                 value=bool(st.session_state.agente_selecionado),
                                                 key="contexto_personalizado")
                
                incluir_fontes_personalizado = st.checkbox(
                    "Solicitar fontes no prompt",
                    value=True,
                    key="incluir_fontes_personalizado"
                )

        if modo_geracao == "Configurações Padrão":
            st.subheader("🎯 Instruções Específicas")
            instrucoes_especificas = st.text_area(
                "Diretrizes adicionais para geração:",
                placeholder="""Exemplos:
- Focar nos benefícios para o usuário final
- Incluir estatísticas quando possível (COM FONTES)
- Manter linguagem acessível
- Evitar jargões técnicos excessivos
- Seguir estrutura: problema → solução → benefícios
- **SEMPRE CITAR FONTES** para dados e informações""",
                height=100,
                key="instrucoes_especificas"
            )

        if st.button("🚀 Gerar Conteúdo com Todos os Insumos", type="primary", use_container_width=True, key="gerar_conteudo_btn"):
            tem_conteudo = (arquivos_upload or 
                           briefing_manual or 
                           arquivos_midia or
                           (textos_arquivos and textos_arquivos.strip()) or
                           (usar_busca_web and termos_busca) or
                           (usar_analise_urls and urls_para_analise))
            
            if not tem_conteudo:
                st.write("❌ Por favor, forneça pelo menos uma fonte de conteúdo (arquivos, briefing, mídia ou busca web)")
            elif modo_geracao == "Prompt Personalizado" and not prompt_personalizado:
                st.write("❌ Por favor, escreva um prompt personalizado para geração")
            else:
                try:
                    contexto_completo = "## FONTES DE CONTEÚDO COMBINADAS:\n\n"
                    
                    if textos_arquivos and textos_arquivos.strip():
                        contexto_completo += "### CONTEÚDO DOS ARQUIVOS:\n" + textos_arquivos + "\n\n"
                    
                    if briefing_manual and briefing_manual.strip():
                        contexto_completo += "### BRIEFING MANUAL:\n" + briefing_manual + "\n\n"
                    
                    if transcricoes_texto and transcricoes_texto.strip():
                        contexto_completo += "### TRANSCRIÇÕES DE MÍDIA:\n" + transcricoes_texto + "\n\n"
                    
                    busca_web_resultado = ""
                    if usar_busca_web and termos_busca and termos_busca.strip() and perp_api_key:
                        contexto_agente_busca = ""
                        if st.session_state.agente_selecionado:
                            agente = st.session_state.agente_selecionado
                            contexto_agente_busca = construir_contexto(agente, st.session_state.segmentos_selecionados)
                        
                        busca_web_resultado = realizar_busca_web_com_fontes(termos_busca, contexto_agente_busca)
                        
                        if "❌" not in busca_web_resultado:
                            contexto_completo += f"### RESULTADOS DA BUSCA WEB ({termos_busca}):\n{busca_web_resultado}\n\n"
                    
                    elif usar_analise_urls and urls_para_analise and urls_para_analise.strip() and perp_api_key:
                        contexto_agente_analise = ""
                        if st.session_state.agente_selecionado:
                            agente = st.session_state.agente_selecionado
                            contexto_agente_analise = construir_contexto(agente, st.session_state.segmentos_selecionados)
                        
                        urls_list = [url.strip() for url in urls_para_analise.split('\n') if url.strip()]
                        
                        if urls_list:
                            pergunta_analise = st.session_state.get('termos_busca_conteudo', termos_busca) if 'termos_busca_conteudo' in st.session_state else "Analise o conteúdo destas URLs"
                            
                            analise_urls_resultado = analisar_urls_com_fontes(urls_list, pergunta_analise, contexto_agente_analise)
                            
                            if "❌" not in analise_urls_resultado:
                                contexto_completo += f"### ANÁLISE DAS URLs:\n{analise_urls_resultado}\n\n"
                    
                    contexto_agente = ""
                    if usar_contexto_agente and st.session_state.agente_selecionado:
                        agente = st.session_state.agente_selecionado
                        contexto_agente = construir_contexto(agente, st.session_state.segmentos_selecionados)
                    
                    if modo_geracao == "Configurações Padrão":
                        instrucoes_fontes = ""
                        if usar_busca_web and termos_busca:
                            instrucoes_fontes = "\n7. **SEMPRE CITAR FONTES:** Para todas as informações da busca web, inclua o nome do site e o link específico"
                        
                        destaque_fontes = ""
                        if incluir_fontes_destaque:
                            destaque_fontes = """
                            8. **DESTACAR FONTES:** Use formatação para destacar as fontes (ex: **Fonte:** [Nome do Site](link))
                            9. **CREDIBILIDADE:** A credibilidade do conteúdo depende das fontes citadas
                            """
                        
                        prompt_final = f"""
                        {contexto_agente}
                        
                        ## INSTRUÇÕES PARA GERAÇÃO DE CONTEÚDO:
                        
                        **TIPO DE CONTEÚDO:** {tipo_conteudo}
                        **TOM DE VOZ:** {tom_voz if tom_voz.strip() else 'Não especificado'}
                        **PALAVRAS-CHAVE:** {palavras_chave if palavras_chave else 'Não especificadas'}
                        **NÚMERO DE PALAVRAS:** {numero_palavras} (±10%)
                        **INCLUIR CALL-TO-ACTION:** {incluir_cta}
                        
                        **INSTRUÇÕES ESPECÍFICAS:**
                        {instrucoes_especificas if instrucoes_especificas else 'Nenhuma instrução específica fornecida.'}
                        {instrucoes_fontes}
                        {destaque_fontes}
                        
                        ## FONTES E REFERÊNCIAS:
                        {contexto_completo}
                        
                        ## TAREFA:
                        Com base em TODAS as fontes fornecidas acima, gere um conteúdo do tipo {tipo_conteudo} que:
                        
                        1. **Síntese Eficiente:** Combine e sintetize informações de todas as fontes
                        2. **Coerência:** Mantenha consistência com as informações originais
                        3. **Valor Agregado:** Vá além da simples cópia, agregando insights
                        4. **Engajamento:** Crie conteúdo que engaje o público-alvo
                        5. **Clareza:** Comunique ideias complexas de forma acessível
                        6. **TRANSPARÊNCIA:** **SEMPRE cite as fontes específicas** para dados, estatísticas e informações importantes
                        
                        **IMPORTANTE SOBRE FONTES:**
                        - Para cada dado ou informação da busca web, cite a fonte específica
                        - Use formato: **Fonte:** [Nome do Site ou Autor] ([link completo])
                        - Se múltiplas fontes confirmam algo, cite as principais
                        - A credibilidade do conteúdo depende das fontes citadas
                        
                        Gere um conteúdo completo, profissional e com fontes verificáveis.
                        """
                    else:
                        prompt_processado = prompt_personalizado.replace("{contexto}", contexto_completo)
                        prompt_processado = prompt_processado.replace("{tom}", tom_personalizado if tom_personalizado.strip() else "adequado")
                        prompt_processado = prompt_processado.replace("{formato}", formato_personalizado)
                        prompt_processado = prompt_processado.replace("{palavras}", str(palavras_personalizado))
                        
                        if incluir_fontes_personalizado:
                            prompt_processado += "\n\n**IMPORTANTE:** SEMPRE cite as fontes das informações, incluindo nome do site e link específico no formato **Fonte: [Nome do Site] ([link])**."
                        
                        prompt_final = f"""
                        {contexto_agente}
                        
                        {prompt_processado}
                        """
                    
                    conteudo_gerado = gerar_conteudo_modelo(prompt_final, modelo_principal, contexto_agente)
                    
                    formato_output = "texto simples"
                    
                    st.session_state.conteudo_gerado = conteudo_gerado
                    st.session_state.tipo_conteudo_gerado = tipo_conteudo if modo_geracao == "Configurações Padrão" else "personalizado"
                    st.session_state.modelo_utilizado_geracao = modelo_principal
                    st.session_state.formato_output = formato_output
                    st.session_state.contexto_usado = contexto_completo
                    
                    st.subheader("📄 Conteúdo Gerado (com Fontes Ancoradas)")
                    
                    st.write(conteudo_gerado)
                    
                    conteudo_lower = conteudo_gerado.lower()
                    tem_fontes = any(keyword in conteudo_lower for keyword in ['fonte:', 'source:', 'http', 'https', 'www.', '.com', '.br', '.gov'])
                    
                    palavras_count = len(conteudo_gerado.split())
                    
                    st.download_button(
                        f"💾 Baixar Conteúdo",
                        data=conteudo_gerado,
                        file_name=f"conteudo_{modelo_principal}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                        mime="text/plain",
                        key="download_conteudo_principal"
                    )
                    
                    if not tem_fontes and (usar_busca_web or usar_analise_urls):
                        st.write("""
                        ⚠️ **ATENÇÃO:** O conteúdo gerado não parece conter fontes explícitas.
                        
                        **Sugestões:**
                        1. Verifique se a busca web retornou informações com fontes
                        2. Tente reformular os termos de busca para serem mais específicos
                        3. Use o modo "Configurações Padrão" com "Destacar fontes" ativado
                        4. Solicite explicitamente fontes no prompt personalizado
                        5. Inclua palavras como "fontes", "referências", "citações" no prompt
                        """)
                        
                except Exception as e:
                    st.write(f"❌ Erro ao gerar conteúdo: {str(e)}")

    with tab_ajuste:
        st.header("✏️ Ajustes Incrementais no Conteúdo")
        
        if 'conteudo_gerado' not in st.session_state or not st.session_state.conteudo_gerado:
            st.write("⚠️ Nenhum conteúdo gerado recentemente. Gere um conteúdo primeiro na aba 'Geração de Conteúdo'.")
        else:
            col_info1, col_info2, col_info3 = st.columns(3)
            with col_info1:
                st.write(f"Modelo Original: {st.session_state.modelo_utilizado_geracao}")
            with col_info2:
                st.write(f"Tipo: {st.session_state.tipo_conteudo_gerado}")
            with col_info3:
                st.write(f"Formato: {st.session_state.formato_output}")
            
            conteudo_lower = st.session_state.conteudo_gerado.lower()
            tem_fontes = any(keyword in conteudo_lower for keyword in ['fonte:', 'source:', 'http', 'https', 'www.', '.com', '.br'])
            
            st.subheader("🎯 Instruções de Ajuste")
            
            instrucoes_ajuste = st.text_area(
                "Descreva o que deseja ajustar no conteúdo:",
                height=150,
                placeholder="""Exemplos:
- Adicione mais estatísticas na introdução (COM FONTES)
- Torne o tom mais formal na seção técnica
- Inclua um exemplo prático no terceiro parágrafo
- Resuma a conclusão para ficar mais direta
- Adicione uma chamada para ação mais urgente
- Reforce os benefícios principais no segundo tópico
- **IMPORTANTE:** Mantenha todas as fontes citadas""",
                key="instrucoes_ajuste"
            )
            
            col_ajuste1, col_ajuste2 = st.columns(2)
            
            with col_ajuste1:
                modelo_ajuste = st.selectbox(
                    "Modelo para ajuste:",
                    ["Gemini", "Claude", "OpenAI"],
                    key="modelo_ajuste_select"
                )
            
            with col_ajuste2:
                usar_contexto_ajuste = st.checkbox(
                    "Usar contexto do agente selecionado",
                    value=bool(st.session_state.agente_selecionado),
                    key="usar_contexto_ajuste"
                )
                
                preservar_fontes = st.checkbox(
                    "Preservar fontes existentes",
                    value=True,
                    key="preservar_fontes"
                )
            
            if st.button("🔄 Aplicar Ajustes", type="primary", key="aplicar_ajustes_btn"):
                if not instrucoes_ajuste or not instrucoes_ajuste.strip():
                    st.write("⚠️ Por favor, descreva as alterações que deseja fazer.")
                else:
                    try:
                        contexto_agente = ""
                        if usar_contexto_ajuste and st.session_state.agente_selecionado:
                            agente = st.session_state.agente_selecionado
                            contexto_agente = construir_contexto(agente, st.session_state.segmentos_selecionados)
                        
                        if preservar_fontes:
                            instrucoes_ajuste_completa = f"{instrucoes_ajuste}\n\nIMPORTANTE: Mantenha todas as fontes citadas no conteúdo original. Não remova ou altere as referências às fontes existentes."
                        else:
                            instrucoes_ajuste_completa = instrucoes_ajuste
                        
                        conteudo_ajustado = ajustar_conteudo_incremental(
                            st.session_state.conteudo_gerado,
                            instrucoes_ajuste_completa,
                            modelo_ajuste,
                            contexto_agente
                        )
                        
                        if "❌" in conteudo_ajustado:
                            st.write(conteudo_ajustado)
                        else:
                            st.write("✅ Ajustes aplicados com sucesso!")
                            
                            conteudo_ajustado_lower = conteudo_ajustado.lower()
                            tem_fontes_apos = any(keyword in conteudo_ajustado_lower for keyword in ['fonte:', 'source:', 'http', 'https', 'www.', '.com', '.br'])
                            
                            st.session_state.conteudo_gerado = conteudo_ajustado
                            
                            st.write("📋 Conteúdo Ajustado:")
                            st.write(conteudo_ajustado)
                            
                            st.download_button(
                                "💾 Baixar Conteúdo Atual",
                                data=st.session_state.conteudo_gerado,
                                file_name=f"conteudo_ajustado_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                                mime="text/plain",
                                key="download_conteudo_ajustado"
                            )
                    
                    except Exception as e:
                        st.write(f"❌ Erro ao aplicar ajustes: {str(e)}")


# --- FUNÇÕES DE REVISÃO ORTOGRÁFICA ---
def revisar_texto_ortografia(texto, agente, segmentos_selecionados, revisao_estilo=True, manter_estrutura=True, explicar_alteracoes=True, modelo_escolhido="Gemini"):
    """
    Realiza revisão ortográfica e gramatical do texto considerando as diretrizes do agente
    """
    
    # Construir o contexto do agente
    contexto_agente = "CONTEXTO DO AGENTE PARA REVISÃO:\n\n"
    
    if "system_prompt" in segmentos_selecionados and agente.get('system_prompt'):
        contexto_agente += f"DIRETRIZES PRINCIPAIS:\n\n"
    
    if "base_conhecimento" in segmentos_selecionados and agente.get('base_conhecimento'):
        contexto_agente += f"BASE DE CONHECIMENTO:\n\n\n"
    
    if "comments" in segmentos_selecionados and agente.get('comments'):
        contexto_agente += f"COMENTÁRIOS E OBSERVAÇÕES:\n\n\n"
    
    if "planejamento" in segmentos_selecionados and agente.get('planejamento'):
        contexto_agente += f"PLANEJAMENTO E ESTRATÉGIA:\n\n\n"
    
    # Construir instruções baseadas nas configurações
    instrucoes_revisao = ""
    
    if revisao_estilo:
        instrucoes_revisao += """
        - Analise e melhore a clareza, coesão e coerência textual
        - Verifique adequação ao tom da marca
        - Elimine vícios de linguagem e redundâncias
        - Simplifique frases muito longas ou complexas
        """
    
    if manter_estrutura:
        instrucoes_revisao += """
        - Mantenha a estrutura geral do texto original
        - Preserve parágrafos e seções quando possível
        - Conserve o fluxo lógico do conteúdo
        """
    
    if explicar_alteracoes:
        instrucoes_revisao += """
        - Inclua justificativa para as principais alterações
        - Explique correções gramaticais importantes
        - Destaque melhorias de estilo significativas
        """
    
    # Construir o prompt para revisão
    prompt_revisao = f"""
    
    TEXTO PARA REVISÃO:
    {texto}
    
    INSTRUÇÕES PARA REVISÃO:
    
    1. **REVISÃO ORTOGRÁFICA E GRAMATICAL:**
       - Corrija erros de ortografia, acentuação e grafia
       - Verifique concordância nominal e verbal
       - Ajuste pontuação (vírgulas, pontos, travessões)
       - Corrija regência verbal e nominal
       - Ajuste colocação pronominal
    
    2. **REVISÃO DE ESTILO E CLAREZA:**
       {instrucoes_revisao}
    
    FORMATO DA RESPOSTA:
    
    ## 📋 TEXTO REVISADO
    [Aqui vai o texto completo revisado, mantendo a estrutura geral quando possível]
    
    ## 🔍 PRINCIPAIS ALTERAÇÕES REALIZADAS
    [Lista das principais correções realizadas com justificativa]
    
    ## 📊 RESUMO DA REVISÃO
    [Resumo dos problemas encontrados e melhorias aplicadas]
    
    **IMPORTANTE:**
    - Seja preciso nas explicações
    - Mantenha o formato markdown para fácil leitura
    - Foque nas correções ortográficas e gramaticais
    """
    
    try:
        resposta = gerar_resposta_modelo(prompt_revisao, modelo_escolhido)
        return resposta
        
    except Exception as e:
        return f"❌ Erro durante a revisão: {str(e)}"

def revisar_documento_por_slides(doc, agente, segmentos_selecionados, revisao_estilo=True, explicar_alteracoes=True, modelo_escolhido="Gemini"):
    """Revisa documento slide por slide com análise detalhada"""
    
    resultados = []
    
    for i, slide in enumerate(doc['slides']):
        with st.spinner(f"Revisando slide {i+1} de {len(doc['slides'])}..."):
            try:
                # Construir contexto do agente para este slide
                contexto_agente = "CONTEXTO DO AGENTE PARA REVISÃO:\n\n"
                
                if "system_prompt" in segmentos_selecionados and agente.get('system_prompt'):
                    contexto_agente += f"DIRETRIZES PRINCIPAIS:\n{agente['system_prompt']}\n\n"
                
                if "base_conhecimento" in segmentos_selecionados and agente.get('base_conhecimento'):
                    contexto_agente += f"BASE DE CONHECIMENTO:\n{agente['base_conhecimento']}\n\n"
                
                prompt_slide = f"""
{contexto_agente}

## REVISÃO ORTOGRÁFICA - SLIDE {i+1}

**CONTEÚDO DO SLIDE {i+1}:**
{slide['conteudo'][:1500]}

**INSTRUÇÕES:**
- Faça uma revisão ortográfica e gramatical detalhada
- Corrija erros de português, acentuação e pontuação
- Mantenha o conteúdo original - apenas corrija ortograficamente e aponte onde as correções foram feitas
- { "Inclua sugestões de melhoria de estilo" if revisao_estilo else "Foque apenas em correções gramaticais" }
- { "Explique as principais alterações" if explicar_alteracoes else "Apenas apresente o texto corrigido" }

**FORMATO DE RESPOSTA:**

### 📋 SLIDE {i+1} - TEXTO REVISADO
[Texto corrigido do slide]

### 🔍 ALTERAÇÕES REALIZADAS
- [Lista das correções com explicação]

### ✅ STATUS
[✔️ Sem erros / ⚠️ Pequenos ajustes / ❌ Correções necessárias]
"""
                
                resposta = gerar_resposta_modelo(prompt_slide, modelo_escolhido)
                resultados.append({
                    'slide_num': i+1,
                    'analise': resposta,
                    'tem_alteracoes': '❌' in resposta or '⚠️' in resposta or 'Correções' in resposta
                })
                
            except Exception as e:
                resultados.append({
                    'slide_num': i+1,
                    'analise': f"❌ Erro na revisão do slide: {str(e)}",
                    'tem_alteracoes': False
                })
    
    # Construir relatório consolidado
    relatorio = f"# 📊 RELATÓRIO DE REVISÃO ORTOGRÁFICA - {doc['nome']}\n\n"
    relatorio += f"**Total de Slides:** {len(doc['slides'])}\n"
    relatorio += f"**Slides com Correções:** {sum(1 for r in resultados if r['tem_alteracoes'])}\n"
    relatorio += f"**Modelo Utilizado:** {modelo_escolhido}\n\n"
    
    # Slides que precisam de atenção
    slides_com_correcoes = [r for r in resultados if r['tem_alteracoes']]
    if slides_com_correcoes:
        relatorio += "## 🚨 SLIDES COM CORREÇÕES:\n\n"
        for resultado in slides_com_correcoes:
            relatorio += f"### 📋 Slide {resultado['slide_num']}\n"
            relatorio += f"{resultado['analise']}\n\n"
    
    # Resumo executivo
    relatorio += "## 📈 RESUMO EXECUTIVO\n\n"
    if slides_com_correcoes:
        relatorio += f"**⚠️ {len(slides_com_correcoes)} slide(s) necessitam de correções**\n"
        relatorio += f"**✅ {len(doc['slides']) - len(slides_com_correcoes)} slide(s) estão corretos**\n"
        
        # Lista resumida de problemas
        relatorio += "\n**📝 PRINCIPAIS TIPOS DE CORREÇÕES:**\n"
        problemas_comuns = []
        for resultado in slides_com_correcoes:
            if "ortográfico" in resultado['analise'].lower():
                problemas_comuns.append("Erros ortográficos")
            if "pontuação" in resultado['analise'].lower():
                problemas_comuns.append("Problemas de pontuação")
            if "concordância" in resultado['analise'].lower():
                problemas_comuns.append("Erros de concordância")
        
        problemas_unicos = list(set(problemas_comuns))
        for problema in problemas_unicos:
            relatorio += f"- {problema}\n"
    else:
        relatorio += "**🎉 Todos os slides estão ortograficamente corretos!**\n"
    
    return relatorio

# --- ABA: REVISÃO ORTOGRÁFICA ---
with tab_mapping["📝 Revisão Ortográfica"]:
    st.header("📝 Revisão Ortográfica e Gramatical")
    
    # Seletor de modelo para revisão
    st.sidebar.subheader("🤖 Modelo para Revisão")
    modelo_revisao = st.sidebar.selectbox(
        "Escolha o modelo:",
        ["Gemini", "Claude"],
        key="modelo_revisao_selector"
    )
    
    if not st.session_state.agente_selecionado:
        st.info("Selecione um agente primeiro na aba de Chat")
    else:
        agente = st.session_state.agente_selecionado
        st.subheader(f"Revisão com: {agente['nome']}")
        
        # Configurações de segmentos para revisão
        st.sidebar.subheader("🔧 Configurações de Revisão")
        st.sidebar.write("Selecione bases para orientar a revisão:")
        
        segmentos_revisao = st.sidebar.multiselect(
            "Bases para revisão:",
            options=["system_prompt", "base_conhecimento", "comments", "planejamento"],
            default=st.session_state.get('segmentos_selecionados', []),
            key="revisao_segmentos"
        )
        
        # Layout em abas para diferentes métodos de entrada
        tab_texto, tab_arquivo = st.tabs(["📝 Texto Direto", "📎 Upload de Arquivos"])
        
        with tab_texto:
            # Layout em colunas para texto direto
            col_original, col_resultado = st.columns(2)
            
            with col_original:
                st.subheader("📄 Texto Original")
                
                texto_para_revisao = st.text_area(
                    "Cole o texto que deseja revisar:",
                    height=400,
                    placeholder="Cole aqui o texto que precisa de revisão ortográfica e gramatical...",
                    help="O texto será analisado considerando as diretrizes do agente selecionado",
                    key="texto_revisao"
                )
                
                # Estatísticas do texto
                if texto_para_revisao:
                    palavras = len(texto_para_revisao.split())
                    caracteres = len(texto_para_revisao)
                    paragrafos = texto_para_revisao.count('\n\n') + 1
                    
                    col_stats1, col_stats2, col_stats3 = st.columns(3)
                    with col_stats1:
                        st.metric("📊 Palavras", palavras)
                    with col_stats2:
                        st.metric("🔤 Caracteres", caracteres)
                    with col_stats3:
                        st.metric("📄 Parágrafos", paragrafos)
                
                # Configurações de revisão
                with st.expander("⚙️ Configurações da Revisão"):
                    revisao_estilo = st.checkbox(
                        "Incluir revisão de estilo",
                        value=True,
                        help="Analisar clareza, coesão e adequação ao tom da marca",
                        key="revisao_estilo"
                    )
                    
                    manter_estrutura = st.checkbox(
                        "Manter estrutura original",
                        value=True,
                        help="Preservar a estrutura geral do texto quando possível",
                        key="manter_estrutura"
                    )
                    
                    explicar_alteracoes = st.checkbox(
                        "Explicar alterações principais",
                        value=True,
                        help="Incluir justificativa para as mudanças mais importantes",
                        key="explicar_alteracoes"
                    )
            
            with col_resultado:
                st.subheader("📋 Resultado da Revisão")
                
                if st.button("🔍 Realizar Revisão Completa", type="primary", key="revisar_texto"):
                    if not texto_para_revisao.strip():
                        st.warning("⚠️ Por favor, cole o texto que deseja revisar.")
                    else:
                        with st.spinner("🔄 Analisando texto e realizando revisão..."):
                            try:
                                resultado = revisar_texto_ortografia(
                                    texto=texto_para_revisao,
                                    agente=agente,
                                    segmentos_selecionados=segmentos_revisao,
                                    revisao_estilo=revisao_estilo,
                                    manter_estrutura=manter_estrutura,
                                    explicar_alteracoes=explicar_alteracoes,
                                    modelo_escolhido=modelo_revisao
                                )
                                
                                st.markdown(resultado)
                                
                                # Opções de download
                                col_dl1, col_dl2, col_dl3 = st.columns(3)
                                
                                with col_dl1:
                                    st.download_button(
                                        "💾 Baixar Relatório Completo",
                                        data=resultado,
                                        file_name=f"relatorio_revisao_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                                        mime="text/plain",
                                        key="download_revisao_completo"
                                    )
                                
                                with col_dl2:
                                    # Extrair apenas o texto revisado se disponível
                                    if "## 📋 TEXTO REVISADO" in resultado:
                                        texto_revisado_start = resultado.find("## 📋 TEXTO REVISADO")
                                        texto_revisado_end = resultado.find("##", texto_revisado_start + 1)
                                        texto_revisado = resultado[texto_revisado_start:texto_revisado_end] if texto_revisado_end != -1 else resultado[texto_revisado_start:]
                                        
                                        st.download_button(
                                            "📄 Baixar Texto Revisado",
                                            data=texto_revisado,
                                            file_name=f"texto_revisado_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                                            mime="text/plain",
                                            key="download_texto_revisado"
                                        )
                                
                                with col_dl3:
                                    # Extrair apenas as explicações se disponível
                                    if "## 🔍 PRINCIPAIS ALTERAÇÕES REALIZADAS" in resultado:
                                        explicacoes_start = resultado.find("## 🔍 PRINCIPAIS ALTERAÇÕES REALIZADAS")
                                        explicacoes_end = resultado.find("##", explicacoes_start + 1)
                                        explicacoes = resultado[explicacoes_start:explicacoes_end] if explicacoes_end != -1 else resultado[explicacoes_start:]
                                        
                                        st.download_button(
                                            "📝 Baixar Explicações",
                                            data=explicacoes,
                                            file_name=f"explicacoes_revisao_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                                            mime="text/plain",
                                            key="download_explicacoes"
                                        )
                                
                            except Exception as e:
                                st.error(f"❌ Erro ao realizar revisão: {str(e)}")
        
        with tab_arquivo:
            st.subheader("📎 Upload de Arquivos para Revisão")
            
            # Upload de múltiplos arquivos
            arquivos_upload = st.file_uploader(
                "Selecione arquivos para revisão:",
                type=['pdf', 'pptx', 'txt', 'docx'],
                accept_multiple_files=True,
                help="Arquivos serão convertidos para texto e revisados ortograficamente",
                key="arquivos_revisao"
            )
            
            # Configurações para arquivos
            with st.expander("⚙️ Configurações da Revisão para Arquivos"):
                analise_por_slide = st.checkbox(
                    "Análise detalhada por slide/página",
                    value=True,
                    help="Analisar cada slide/página individualmente",
                    key="analise_por_slide"
                )
                
                revisao_estilo_arquivos = st.checkbox(
                    "Incluir revisão de estilo",
                    value=True,
                    help="Analisar clareza, coesão e adequação ao tom da marca",
                    key="revisao_estilo_arquivos"
                )
                
                explicar_alteracoes_arquivos = st.checkbox(
                    "Explicar alterações principais",
                    value=True,
                    help="Incluir justificativa para as mudanças mais importantes",
                    key="explicar_alteracoes_arquivos"
                )
            
            if arquivos_upload:
                st.success(f"✅ {len(arquivos_upload)} arquivo(s) carregado(s)")
                
                # Mostrar preview dos arquivos
                with st.expander("📋 Visualizar Arquivos Carregados", expanded=False):
                    for i, arquivo in enumerate(arquivos_upload):
                        st.write(f"**{arquivo.name}** ({arquivo.size} bytes)")
                
                if st.button("🔍 Revisar Todos os Arquivos", type="primary", key="revisar_arquivos"):
                    resultados_completos = []
                    
                    for arquivo in arquivos_upload:
                        with st.spinner(f"Processando {arquivo.name}..."):
                            try:
                                # Extrair texto do arquivo
                                texto_extraido = ""
                                slides_info = []
                                
                                if arquivo.type == "application/pdf":
                                    texto_extraido, slides_info = extract_text_from_pdf_com_slides(arquivo)
                                elif arquivo.type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
                                    texto_extraido, slides_info = extract_text_from_pptx_com_slides(arquivo)
                                elif arquivo.type == "text/plain":
                                    texto_extraido = extrair_texto_arquivo(arquivo)
                                elif arquivo.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                                    texto_extraido = extrair_texto_arquivo(arquivo)
                                else:
                                    st.warning(f"Tipo de arquivo não suportado: {arquivo.name}")
                                    continue
                                
                                if texto_extraido and len(texto_extraido.strip()) > 0:
                                    doc_info = {
                                        'nome': arquivo.name,
                                        'conteudo': texto_extraido,
                                        'slides': slides_info,
                                        'tipo': arquivo.type
                                    }
                                    
                                    # Escolher o método de revisão baseado nas configurações
                                    if analise_por_slide and slides_info:
                                        # Revisão detalhada por slide
                                        resultado = revisar_documento_por_slides(
                                            doc_info,
                                            agente,
                                            segmentos_revisao,
                                            revisao_estilo_arquivos,
                                            explicar_alteracoes_arquivos,
                                            modelo_revisao
                                        )
                                    else:
                                        # Revisão geral do documento
                                        resultado = revisar_texto_ortografia(
                                            texto=texto_extraido,
                                            agente=agente,
                                            segmentos_selecionados=segmentos_revisao,
                                            revisao_estilo=revisao_estilo_arquivos,
                                            manter_estrutura=True,
                                            explicar_alteracoes=explicar_alteracoes_arquivos,
                                            modelo_escolhido=modelo_revisao
                                        )
                                    
                                    resultados_completos.append({
                                        'nome': arquivo.name,
                                        'texto_original': texto_extraido,
                                        'resultado': resultado,
                                        'tipo': 'por_slide' if (analise_por_slide and slides_info) else 'geral'
                                    })
                                    
                                    # Exibir resultado individual
                                    with st.expander(f"📄 Resultado - {arquivo.name}", expanded=False):
                                        st.markdown(resultado)
                                        
                                        # Estatísticas do arquivo processado
                                        palavras_orig = len(texto_extraido.split())
                                        st.info(f"📊 Arquivo original: {palavras_orig} palavras")
                                        if slides_info:
                                            st.info(f"📑 {len(slides_info)} slides/páginas processados")
                                        
                                else:
                                    st.warning(f"❌ Não foi possível extrair texto do arquivo: {arquivo.name}")
                                
                            except Exception as e:
                                st.error(f"❌ Erro ao processar {arquivo.name}: {str(e)}")
                    
                    # Botão para download de todos os resultados
                    if resultados_completos:
                        st.markdown("---")
                        st.subheader("📦 Download de Todos os Resultados")
                        
                        # Criar relatório consolidado
                        relatorio_consolidado = f"# RELATÓRIO DE REVISÃO ORTOGRÁFICA\n\n"
                        relatorio_consolidado += f"**Data:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
                        relatorio_consolidado += f"**Agente:** {agente['nome']}\n"
                        relatorio_consolidado += f"**Modelo Utilizado:** {modelo_revisao}\n"
                        relatorio_consolidado += f"**Total de Arquivos:** {len(resultados_completos)}\n\n"
                        
                        for resultado in resultados_completos:
                            relatorio_consolidado += f"## 📄 {resultado['nome']}\n\n"
                            relatorio_consolidado += f"{resultado['resultado']}\n\n"
                            relatorio_consolidado += "---\n\n"
                        
                        st.download_button(
                            "💾 Baixar Relatório Consolidado",
                            data=relatorio_consolidado,
                            file_name=f"relatorio_revisao_arquivos_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                            mime="text/plain",
                            key="download_consolidado"
                        )
            
        
        
with tab_mapping["Monitoramento de Redes"]:
    st.header("🤖 Agente de Monitoramento")
    st.markdown("**Especialista que fala como gente**")

    def gerar_resposta_agente(pergunta_usuario: str, historico: List[Dict] = None, agente_monitoramento=None, modelo_escolhido="Gemini", contexto_adicional: str = None) -> str:
        """Gera resposta do agente usando RAG e base do agente de monitoramento"""
        
        # Configuração do agente - usa base do agente selecionado ou padrão
        if agente_monitoramento and agente_monitoramento.get('base_conhecimento'):
            system_prompt = agente_monitoramento['base_conhecimento']
        else:
            # Fallback para prompt padrão se não houver agente selecionado
            system_prompt = """
            PERSONALIDADE: Especialista com habilidade social - "Especialista que fala como gente"

            TOM DE VOZ:
            - Técnico, confiável e seguro, mas acessível
            - Evita exageros e promessas vazias
            - Sempre embasado em fatos e ciência
            - Frases curtas e diretas, mais simpáticas
            - Toque de leveza e ironia pontual quando o contexto permite


            TOM DE VOZ (BASEADO NO FEEDBACK):
            - Equilíbrio entre institucional e casual
            - Evitar respostas muito longas ou com excesso de adjetivos
            - Adaptar ao contexto específico do post
            - Respostas diretas e objetivas quando necessário
            - Uso moderado de emojis (apenas quando fizer sentido)
            - Respostas para emojis isolados devem ser apenas emojis também
            - Não inventar informações técnicas
            - Reconhecer elogios de forma genuína mas sucinta

            FEEDBACK A CONSIDERAR:
            1. PARA PERGUNTAS DIRETAS: Responder de fato à pergunta, não ser genérico
            2. PARA LINKS: Usar links diretos quando disponíveis
            3. PARA ELOGIOS: Agradecer de forma simples e personalizada quando possível
            4. PARA SUGESTÕES: Reconhecer a sugestão e mostrar abertura
            5. PARA COMENTÁRIOS FORA DE CONTEXTO: Não responder com informações irrelevantes
            6. PARA APENAS EMOJIS: Responder apenas com emojis também

           
            """

        # Adicionar contexto adicional se fornecido
        contexto_completo = system_prompt
        if contexto_adicional and contexto_adicional.strip():
            contexto_completo += f"\n\nCONTEXTO ADICIONAL FORNECIDO:\n{contexto_adicional}"
        
        # Constrói o prompt final
        prompt_final = f"""
        {contexto_completo}
        
        
        PERGUNTA DO USUÁRIO:
        {pergunta_usuario}
        
        HISTÓRICO DA CONVERSA (se aplicável):
        {historico if historico else "Nenhum histórico anterior"}
        
        INSTRUÇÕES FINAIS:
        Adapte seu tom ao tipo de pergunta:
        - Tom que encontra um equilíbrio entre institucional e casual, afinal, as respostas estão sendo geradas no ambiente de rede social por parte de um perfil de empresa
        - Perguntas técnicas: seja preciso e didático
        - Perguntas sociais: seja leve e engajador  
        - Críticas ou problemas: seja construtivo e proativo
        - Forneça respostas breves - 1 a 2 frases

        TOM DE VOZ (BASEADO NO FEEDBACK):
            - Equilíbrio entre institucional e casual
            - Evitar respostas muito longas ou com excesso de adjetivos
            - Adaptar ao contexto específico do post
            - Respostas diretas e objetivas quando necessário
            - Uso moderado de emojis (apenas quando fizer sentido)
            - Respostas para emojis isolados devem ser apenas emojis também
            - Não inventar informações técnicas
            - Reconhecer elogios de forma genuína mas sucinta
            - Forneça respostas breves - 1 a 2 frases

            FEEDBACK A CONSIDERAR:
            1. PARA PERGUNTAS DIRETAS: Responder de fato à pergunta, não ser genérico
            2. PARA LINKS: Usar links diretos quando disponíveis
            3. PARA ELOGIOS: Agradecer de forma simples e personalizada quando possível
            4. PARA SUGESTÕES: Reconhecer a sugestão e mostrar abertura
            5. PARA COMENTÁRIOS FORA DE CONTEXTO: Não responder com informações irrelevantes
            6. PARA APENAS EMOJIS: Responder apenas com emojis também
            - Forneça respostas breves - 1 a 2 frases

           
        
        Sua resposta deve ser curta (apenas 1 a 2 frases). Você está no contexto de rede social. Não enrole.
        """
        
        try:
            resposta = gerar_resposta_modelo(prompt_final, modelo_escolhido)
            return resposta
        except Exception as e:
            return f"Erro ao gerar resposta: {str(e)}"

    # SELEÇÃO DE AGENTE DE MONITORAMENTO
    st.header("🔧 Configuração do Agente de Monitoramento")
    
    # Caixa de texto para contexto adicional
    st.subheader("📝 Contexto Adicional para Respostas")
    
    contexto_adicional = st.text_area(
        "Forneça contexto adicional para as respostas:",
        height=150,
        placeholder="Ex: Este post é sobre vagas de emprego na MRS...\nOu: Estamos respondendo comentários sobre decoração de Natal...\nOu: O vídeo é sobre corrida de equipes...",
        help="Este contexto será incluído no prompt para gerar respostas mais adequadas ao cenário específico",
        key="contexto_monitoramento"
    )
    
    # Seletor de modelo para monitoramento
    st.sidebar.subheader("🤖 Modelo para Monitoramento")
    modelo_monitoramento = st.sidebar.selectbox(
        "Escolha o modelo:",
        ["Gemini", "Claude"],
        key="modelo_monitoramento_selector"
    )
    
    # Carregar apenas agentes de monitoramento
    agentes_monitoramento = [agente for agente in listar_agentes() if agente.get('categoria') == 'Monitoramento']
    
    col_sel1, col_sel2 = st.columns([3, 1])
    
    with col_sel1:
        if agentes_monitoramento:
            # Criar opções para selectbox
            opcoes_agentes = {f"{agente['nome']}": agente for agente in agentes_monitoramento}
            
            agente_selecionado_nome = st.selectbox(
                "Selecione o agente de monitoramento:",
                list(opcoes_agentes.keys()),
                key="seletor_monitoramento"
            )
            
            agente_monitoramento = opcoes_agentes[agente_selecionado_nome]
            
            # Mostrar informações do agente selecionado
            with st.expander("📋 Informações do Agente Selecionado", expanded=False):
                if agente_monitoramento.get('base_conhecimento'):
                    st.text_area(
                        "Base de Conhecimento:",
                        value=agente_monitoramento['base_conhecimento'],
                        height=200,
                        disabled=True
                    )
                else:
                    st.warning("⚠️ Este agente não possui base de conhecimento configurada")
                
                st.write(f"**Criado em:** {agente_monitoramento['data_criacao'].strftime('%d/%m/%Y %H:%M')}")
                # Mostrar proprietário se for admin
                if get_current_user() == "admin" and agente_monitoramento.get('criado_por'):
                    st.write(f"**👤 Proprietário:** {agente_monitoramento['criado_por']}")
        
        else:
            st.error("❌ Nenhum agente de monitoramento encontrado.")
            st.info("💡 Crie um agente de monitoramento na aba 'Gerenciar Agentes' primeiro.")
            agente_monitoramento = None
    
    with col_sel2:
        if st.button("🔄 Atualizar Lista", key="atualizar_monitoramento"):
            st.rerun()

    # Sidebar com informações
    with st.sidebar:
        st.header("ℹ️ Sobre o Monitoramento")
        
        if agente_monitoramento:
            st.success(f"**Agente Ativo:** {agente_monitoramento['nome']}")
        else:
            st.warning("⚠️ Nenhum agente selecionado")
        
        # Mostrar contexto atual se houver
        if contexto_adicional and contexto_adicional.strip():
            st.info("📝 Contexto ativo:")
            st.caption(contexto_adicional[:100] + "..." if len(contexto_adicional) > 100 else contexto_adicional)
        
        st.markdown("""
        **Personalidade:**
        - 🎯 Técnico mas acessível
        - 💬 Direto mas simpático
        - 🌱 Conhece o campo e a internet
        - 🔬 Baseado em ciência
        
        **Capacidades:**
        - Respostas técnicas baseadas em RAG
        - Engajamento em redes sociais
        - Suporte a produtores
        - Esclarecimento de dúvidas
        """)

        
        if st.button("🔄 Reiniciar Conversa", key="reiniciar_monitoramento"):
            if "messages_monitoramento" in st.session_state:
                st.session_state.messages_monitoramento = []
            st.rerun()

        # Status da conexão
        
        if os.getenv('OPENAI_API_KEY'):
            st.success("✅ OpenAI: Configurado")
        else:
            st.warning("⚠️ OpenAI: Não configurado")

    # Inicializar histórico de mensagens específico para monitoramento
    if "messages_monitoramento" not in st.session_state:
        st.session_state.messages_monitoramento = []

    # Área de chat principal
    st.header("💬 Simulador de Respostas do Agente")

   

    # Exibir histórico de mensagens
    for message in st.session_state.messages_monitoramento:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Input do usuário
    if prompt := st.chat_input("Digite sua mensagem ou pergunta...", key="chat_monitoramento"):
        # Adicionar mensagem do usuário
        st.session_state.messages_monitoramento.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Gerar resposta do agente
        with st.chat_message("assistant"):
            with st.spinner("🌱 Consultando base técnica..."):
                resposta = gerar_resposta_agente(
                    prompt, 
                    st.session_state.messages_monitoramento,
                    agente_monitoramento,
                    modelo_monitoramento,
                    contexto_adicional  # Passa o contexto adicional
                )
                st.markdown(resposta)
                
                # Adicionar ao histórico
                st.session_state.messages_monitoramento.append({"role": "assistant", "content": resposta})



# --- Funções auxiliares para busca web ---
def buscar_perplexity(pergunta: str, contexto_agente: str = None) -> str:
    """Realiza busca na web usando API do Perplexity"""
    try:
        headers = {
            "Authorization": f"Bearer {perp_api_key}",
            "Content-Type": "application/json"
        }
        
        # Construir o conteúdo da mensagem
        messages = []
        
        if contexto_agente:
            messages.append({
                "role": "system",
                "content": f"Contexto do agente: {contexto_agente}"
            })
        
        messages.append({
            "role": "user",
            "content": pergunta
        })
        
        data = {
            "model": "sonar-medium-online",
            "messages": messages,
            "max_tokens": 2000,
            "temperature": 0.0
        }
        
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return f"❌ Erro na busca: {response.status_code} - {response.text}"
            
    except Exception as e:
        return f"❌ Erro ao conectar com Perplexity: {str(e)}"

def analisar_urls_perplexity(urls: List[str], pergunta: str, contexto_agente: str = None) -> str:
    """Analisa URLs específicas usando Perplexity"""
    try:
        headers = {
            "Authorization": f"Bearer {perp_api_key}",
            "Content-Type": "application/json"
        }
        
        # Construir contexto com URLs
        urls_contexto = "\n".join([f"- {url}" for url in urls])
        
        messages = []
        
        if contexto_agente:
            messages.append({
                "role": "system",
                "content": f"Contexto do agente: {contexto_agente}"
            })
        
        messages.append({
            "role": "user",
            "content": f"""Analise as seguintes URLs e responda à pergunta:

URLs para análise:
{urls_contexto}

Pergunta: {pergunta}

Forneça uma análise detalhada baseada no conteúdo dessas URLs."""
        })
        
        data = {
            "model": "sonar-medium-online",
            "messages": messages,
            "max_tokens": 3000,
            "temperature": 0.0
        }
        
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=data,
            timeout=45
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return f"❌ Erro na análise: {response.status_code} - {response.text}"
            
    except Exception as e:
        return f"❌ Erro ao analisar URLs: {str(e)}"

def transcrever_audio_video(arquivo, tipo):
    """Função placeholder para transcrição de áudio/vídeo"""
    return f"Transcrição do {tipo} {arquivo.name} - Esta funcionalidade requer configuração adicional de APIs de transcrição."



# --- Informações do sistema na sidebar ---
with st.sidebar:
    st.markdown("---")
    st.subheader("🔐 Sistema de Isolamento")
    
    current_user = get_current_user()
    if current_user == "admin":
        st.success("👑 **Modo Administrador**")
        st.info("Visualizando e gerenciando TODOS os agentes do sistema")
    else:
        st.success(f"👤 **Usuário: {current_user}**")
        st.info("Visualizando e gerenciando apenas SEUS agentes")
    
    # Estatísticas rápidas
    agentes_usuario = listar_agentes()
    if agentes_usuario:
        categorias_count = {}
        for agente in agentes_usuario:
            cat = agente.get('categoria', 'Social')
            categorias_count[cat] = categorias_count.get(cat, 0) + 1
        
        st.markdown("### 📊 Seus Agentes")
        for categoria, count in categorias_count.items():
            st.write(f"- **{categoria}:** {count} agente(s)")
        
        st.write(f"**Total:** {len(agentes_usuario)} agente(s)")


# --- FUNÇÃO ESPECÍFICA PARA OTIMIZAÇÃO DE CONTEÚDO ---
def buscar_fontes_para_otimizacao(conteudo: str, tipo: str, tom: str) -> str:
    """Busca fontes específicas para otimização de conteúdo agrícola"""
    if not perplexity_available:
        return "Busca web desativada"
    
    prompt = f"""
    
   
    DADOS TÉCNICOS ATUALIZADOS para este conteúdo:
    {conteudo[:800]}
    
    
    """
    
    return buscar_perplexity(prompt)
        

# ========== ABA: OTIMIZAÇÃO DE CONTEÚDO ==========
with tab_mapping["🚀 Otimização de Conteúdo"]:
    st.header("🚀 Otimização de Conteúdo")
    
    # Inicializar session state
    if 'conteudo_otimizado' not in st.session_state:
        st.session_state.conteudo_otimizado = None
    if 'ultima_otimizacao' not in st.session_state:
        st.session_state.ultima_otimizacao = None
    if 'ajustes_realizados' not in st.session_state:
        st.session_state.ajustes_realizados = []
    if 'fontes_busca_web' not in st.session_state:
        st.session_state.fontes_busca_web = ""
    
    # Área para entrada do conteúdo
    texto_para_otimizar = st.text_area("Cole o conteúdo para otimização:", height=300)
    
    # Configurações
    col_config1, col_config2 = st.columns([2, 1])
    
    with col_config1:
        tipo_otimizacao = st.selectbox("Tipo de Otimização:", 
                                      ["SEO", "Engajamento", "Conversão", "Clareza"])
        
    with col_config2:
        tom_voz = st.text_input("Tom de Voz (ex: Técnico, Persuasivo):", 
                               value="Técnico",
                               key="tom_voz_otimizacao")
        
        nivel_heading = st.selectbox("Nível de Heading Solicitado:", 
                                   ["H1", "H2", "H3", "H4"],
                                   help="Nível de heading que foi solicitado no briefing. CORRIJA se o texto usar nível diferente")

    # CONFIGURAÇÕES DE BUSCA WEB
    st.subheader("🔍 Busca Web e Links")
    
    usar_busca_web = st.checkbox("Usar busca web para enriquecer conteúdo", 
                               value=True,
                               help="Ativa a busca no Perplexity para encontrar informações atualizadas")
    
    incluir_links_internos = st.checkbox("Incluir links internos", 
                                       value=True,
                                       help="Sugere e ancora links relevantes no texto")

    # Área para briefing
    instrucoes_briefing = st.text_area(
        "Instruções do briefing (opcional):",
        height=80
    )

    # --- FUNÇÃO DE BUSCA WEB SEPARADA ---
    def realizar_busca_web_perplexity(texto, tipo_otimizacao, tom_voz):
        """Função separada para realizar busca web"""
        try:
            # Importar dentro da função para evitar erros de importação
            from perplexity import Perplexity
            
            # Obter API key
            perp_api_key = os.getenv("PERP_API_KEY")
            if not perp_api_key:
                return "❌ ERRO: PERP_API_KEY não encontrada nas variáveis de ambiente"
            
            # Inicializar cliente
            client = Perplexity(api_key=perp_api_key)
            
            # Construir prompt para busca
            prompt = f"""
            Você é um assistente especializado em pesquisa agrícola. Busque informações atualizadas e confiáveis sobre:
            
            TÓPICO PRINCIPAL: {texto}
            
            CRITÉRIOS DE PESQUISA:
            1. Fontes confiáveis: Embrapa, universidades, órgãos governamentais, institutos de pesquisa
            2. Informações técnicas atualizadas (últimos 2-3 anos)
            3. Dados concretos: números, estatísticas, resultados de pesquisa
            4. Melhores práticas agrícolas
            5. Soluções tecnológicas inovadoras
            
            FORMATO DE RESPOSTA:
            Para CADA fonte encontrada, forneça:
            - TÍTULO: Título do artigo/referência
            - CONTEÚDO: Resumo das informações relevantes (máx 200 palavras)
            - URL: Link completo para a fonte
            - RELEVÂNCIA: Por que esta fonte é relevante para o tópico
            
            Retorne no máximo 20 fontes mais relevantes.
            """
            
            # Fazer busca
            response = client.chat.completions.create(
                model="sonar",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=20000
            )
            
            if response and response.choices:
                resultado = response.choices[0].message.content
                return resultado
            else:
                return "❌ ERRO: Nenhuma resposta recebida do Perplexity"
                
        except ImportError as e:
            return f"❌ ERRO: Biblioteca perplexity-api não instalada. Execute: pip install perplexity-api\nDetalhes: {str(e)}"
        except Exception as e:
            return f"❌ ERRO na busca web: {str(e)}"

    # Botão de otimização
    if st.button("🚀 Otimizar Conteúdo", type="primary", use_container_width=True):
        if texto_para_otimizar:
            with st.spinner("Processando otimização..."):
                try:
                    # FASE 1: BUSCA WEB (se ativada) - AGORA COM TRATAMENTO SEPARADO
                    fontes_encontradas = ""
                    if usar_busca_web:
                        # Container separado para busca web
                        with st.container():
                            st.info("🔍 Iniciando busca web no Perplexity...")
                            
                            # Criar um placeholder para os resultados
                            busca_placeholder = st.empty()
                            
                            # Executar busca web em um bloco try separado
                            try:
                                resultado_busca = realizar_busca_web_perplexity(
                                    texto_para_otimizar, 
                                    tipo_otimizacao, 
                                    tom_voz
                                )
                                
                                # Verificar resultado
                                if resultado_busca and not resultado_busca.startswith("❌"):
                                    fontes_encontradas = resultado_busca
                                    st.session_state.fontes_busca_web = resultado_busca
                                    busca_placeholder.success(f"✅ Busca web concluída: {len(resultado_busca.split())} palavras encontradas")
                                    
                                    # Mostrar preview
                                    with st.expander("📋 Prévia das fontes encontradas", expanded=False):
                                        st.markdown(resultado_busca[:1000] + "..." if len(resultado_busca) > 1000 else resultado_busca)
                                else:
                                    busca_placeholder.warning("⚠️ Busca web não retornou resultados válidos")
                                    st.info("⚠️ Continuando sem fontes externas da busca web")
                                    
                            except Exception as busca_error:
                                busca_placeholder.error(f"❌ Erro na busca web: {str(busca_error)}")
                                st.info("⚠️ Continuando sem fontes externas da busca web")
                    
                    # FASE 2: OTIMIZAÇÃO COM GEMINI
                    st.info("🤖 Iniciando otimização com Gemini...")
                    
                    # Contexto do agente
                    contexto_agente = ""
                    if st.session_state.agente_selecionado:
                        agente = st.session_state.agente_selecionado
                        contexto_agente = construir_contexto(agente, st.session_state.segmentos_selecionados)
                    
                    # Prompt de otimização
                    prompt = f"""
                    ###BEGIN contexto agente###
                    {contexto_agente}
                    ###END contexto agente###

                    Instruções: Você é um especialista em agronomia e redator técnico. Com base nas informações fornecidas no formato abaixo, gere um artigo completo e bem estruturado sobre o ciclo de desenvolvimento de uma cultura agrícola, seguindo rigorosamente a estrutura, diretrizes e marcação solicitadas.

                    ############BEGIN Formato de Entrada################
                    TÍTULO/H1 desejado: [Título do artigo]
                    Objetivo do conteúdo: [Objetivo descritivo do conteúdo]
                    Público-alvo (persona, nível técnico): [Descrição do público]
                    Palavra-chave principal (KW1): [Palavra-chave primária]
                    Palavras-chave secundárias: [Lista de palavras-chave secundárias, uma por linha]
                    Estrutura (H2/H3 em ordem):
                    [Estrutura completa do artigo com títulos H2 e H3]
                    Região/bioma/safra alvo: [Cultura e contexto]
                    CTA FINAL OBRIGATÓRIA:
                    [Texto do call-to-action]
                    link da CTA: [URL]
                    Interlinks prioritários (URLs internas existentes): [Lista ou "não aplicável"]
                    Links externos obrigatórios (se houver): [Lista ou "não aplicável"]
                    Diretrizes de tom/estilo (brand voice): [Ex.: técnico e leve]
                    Observações/restrições: [Informações adicionais]
                    ############END Formato de Entrada################

                    
                    Sua tarefa: Ao receber uma entrada no formato acima, você deve gerar um documento de artigo completo que inclua:
                    
                        Metadados SEO:
                    
                            Meta title: Crie um com até 60 caracteres, incluindo a KW1.
                    
                            Meta description: Crie uma descrição persuasiva com até 160 caracteres, incluindo a KW1 e uma chamada para ação.
                    
                            URL: Sugira uma URL amigável para SEO baseada no título.
                    
                            Categoria: Sugira uma categoria temática.
                    
                            Imagem de capa: Sugira um tema genérico para imagem (ex.: "Lavouras de [cultura] em campo aberto") e um Alt text descritivo.
                    
                        Corpo do Artigo:
                    
                            Inicie com o TÍTULO/H1 fornecido.
                    
                            Escreva uma introdução envolvente que contextualize a importância da cultura e do manejo correto do seu ciclo.
                    
                            Desenvolva o conteúdo seguindo exatamente a ordem e a hierarquia (H2, H3) fornecidas na "Estrutura".
                    
                            Para cada H3 (que representa um estágio fenológico), estruture o texto com os seguintes subtópicos, sem usar marcadores na explicação:
                    
                                O que é: Definição clara do estágio.
                    
                                Características: Descrições morfológicas e fisiológicas principais.
                    
                                Práticas de Manejo: Recomendações técnicas específicas para essa fase (nutrição, irrigação, controle fitossanitário).
                    
                                Pontos Críticos e Cuidados: Principais riscos (estresses, pragas, doenças) e como mitigá-los.
                    
                            Incorpore naturalmente a KW principal e as palavras-chave secundárias ao longo do texto.
                    
                            Use um tom que equilibre precisão técnica e clareza, conforme as diretrizes de "brand voice".
                    
                            Onde a estrutura sugerir (ex.: após seções longas), insira uma caixa "Leia mais:" ou "Leia também:" com 2-3 sugestões de artigos relacionados baseadas no tema geral. Invente títulos plausíveis para estes interlinks.
                    
                            Finalize com uma conclusão que resuma a importância do manejo faseado.
                    
                            Inclua obrigatoriamente o CTA FINAL com o texto e link fornecidos.
                    
                        Elementos Adicionais (se aplicável na estrutura):
                    
                            Se a estrutura incluir "Tabela", crie uma tabela em markdown resumindo os estágios, características, práticas e pontos críticos.
                    
                            Se a estrutura incluir uma seção sobre "Quanto tempo dura o ciclo...", explique a variação de duração com base em cultivares, clima e região.
                    
                    Regras Gerais:
                    
                        Fidelidade: Siga a estrutura fornecida à risca. Não altere a ordem dos H2/H3.
                    
                        Objetividade: Forneça informações práticas e acionáveis. Evite linguagem excessivamente promocional no corpo do texto.
                    
                        Completude: Certifique-se de que todos os elementos da entrada foram atendidos (KWs, estrutura, CTA).
                    
                        Formatação: Use negrito para termos técnicos importantes ou frases de impacto ocasionais. Use marcadores apenas em listas de itens muito concisos (ex.: características de um estágio). Prefira parágrafos fluidos.
                    
                    Exemplo de Saída (Estrutura Visual):
                    text
                    
                    Meta title: [Texto]
                    Meta description: [Texto]
                    URL: /url-sugerida
                    Categoria: [Categoria Sugerida]
                    Imagem de capa: [Tema sugerido]
                    Alt text: [Descrição da imagem]
                    
                    # TÍTULO/H1 FORNECIDO
                    
                    [Parágrafo de introdução]
                    
                    ## H2 FORNECIDO
                    [Texto explicativo da seção]
                    
                    ### H3 FORNECIDO
                    **O que é:** [Definição].
                    **Características:** [Descrição].
                    **Práticas de Manejo:** [Recomendações].
                    **Pontos Críticos e Cuidados:** [Riscos e soluções].
                    
                    [Continue para todos os H3s e H2s...]
                    
                    **Leia mais:**
                    *   Título de artigo relacionado 1
                    *   Título de artigo relacionado 2
                    
                    ## H2 FINAL (ex.: Conclusão)
                    [Texto de conclusão]
                    
                    [CTA FINAL OBRIGATÓRIO com link]

                    [Links que foram ancorados por extenso]



                    **TEXTO ORIGINAL:**
                    {texto_para_otimizar}

                    **FONTES DA BUSCA WEB (para serem usadas de forma ancorada ao longo do texto quando relevantes)**
                    {fontes_encontradas if fontes_encontradas else "Nenhuma fonte externa disponível."}

                    **INSTRUÇÕES DO BRIEFING:**
                    {instrucoes_briefing if instrucoes_briefing else 'Sem briefing específico'}

                    **CONFIGURAÇÕES:**
                    - Tipo: {tipo_otimizacao}
                    - Tom: {tom_voz}
                    - Heading level: {nivel_heading}
                    - Links internos: {"Sim" if incluir_links_internos else "Não"}
                    - Busca web usada: {"Sim" if fontes_encontradas else "Não"}

                    ## REQUISITOS OBRIGATÓRIOS:

                    1. **TITLES E DESCRIPTIONS (OBRIGATÓRIO):**
                       Gere 3 opções de meta title (≤60 chars) e description (≤155 chars)
                       Exemplo:
                       Title: Guia Prático de Adubação Nitrogenada no Milho - Aumente sua Produtividade
                       Description: Descubra como a adubação nitrogenada adequada pode aumentar em até 30% a produtividade do milho. Técnicas comprovadas!

                    2. **BULLETS QUANDO APLICÁVEL:**
                       - Use bullets para listas de benefícios
                       - Use bullets para características técnicas
                       - Use bullets para etapas de processo
                       - Máximo 5 itens por lista

                    3. **HEADING LEVEL {nivel_heading}:**
                       - Todos os headings principais devem ser {nivel_heading}
                       - Corrigir se estiver usando nível diferente
                       - Manter hierarquia consistente

                    4. **CORREÇÕES AUTOMÁTICAS:**
                       - Remova introduções genéricas - Você é um profissional experiente
                       - Quebre parágrafos longos (3-4 frases máx)
                       - Remova repetições
                       - Melhore escaneabilidade
                       - Divida frases complexas
                       - Incorpore dados das fontes quando relevante

                    5. **LINKS INTERNOS:**
                       Sugira 3-5 links relevantes no formato: [texto âncora](url)
                       Escreva os links que foram ancorados por extenso ao final
                    """

                    # Gerar otimização
                    resposta = modelo_texto.generate_content(prompt)
                    resultado = resposta.text
                    
                    # Processar resultado
                    partes_do_resultado = {
                        "📝 CONTEÚDO OTIMIZADO": resultado  # Default
                    }
                    
                    # Tentar extrair seções
                    secoes = ["📊 SUGESTÕES DE META TAGS", "✅ CORREÇÕES APLICADAS", "🔗 LINKS INTERNOS SUGERIDOS", "📝 CONTEÚDO OTIMIZADO"]
                    
                    for i in range(len(secoes)):
                        if secoes[i] in resultado:
                            inicio = resultado.find(secoes[i])
                            if i < len(secoes) - 1 and secoes[i+1] in resultado:
                                fim = resultado.find(secoes[i+1])
                                conteudo = resultado[inicio + len(secoes[i]):fim].strip()
                            else:
                                conteudo = resultado[inicio + len(secoes[i]):].strip()
                            
                            # Limpar formatação extra
                            conteudo = conteudo.strip(":#*-\n ")
                            partes_do_resultado[secoes[i]] = conteudo
                    
                    # Salvar no session state
                    st.session_state.conteudo_otimizado = partes_do_resultado.get("📝 CONTEÚDO OTIMIZADO", resultado)
                    st.session_state.ultima_otimizacao = resultado
                    st.session_state.texto_original = texto_para_otimizar
                    st.session_state.fontes_busca_web = fontes_encontradas
                    st.session_state.partes_resultado = partes_do_resultado
                    
                    # Exibir resultados
                    st.success("✅ Conteúdo otimizado com sucesso!")
                    
                    # 1. Meta Tags
                    st.subheader("📊 Meta Tags Geradas")
                    if "📊 SUGESTÕES DE META TAGS" in partes_do_resultado:
                        st.markdown(partes_do_resultado["📊 SUGESTÕES DE META TAGS"])
                    else:
                        # Procurar meta tags no texto
                        lines = resultado.split('\n')
                        meta_candidates = []
                        for line in lines:
                            line_lower = line.lower()
                            if ('title:' in line_lower or 'description:' in line_lower or 
                                'meta ' in line_lower or 'tag' in line_lower):
                                meta_candidates.append(line)
                        
                        if meta_candidates:
                            st.info("Meta tags encontradas:")
                            for line in meta_candidates[:6]:
                                st.write(line)
                        else:
                            st.warning("Meta tags não foram detectadas automaticamente")
                    
                    # 2. Correções
                    if "✅ CORREÇÕES APLICADAS" in partes_do_resultado:
                        with st.expander("✅ Correções Aplicadas", expanded=True):
                            st.markdown(partes_do_resultado["✅ CORREÇÕES APLICADAS"])
                    
                    # 3. Links Internos
                    if "🔗 LINKS INTERNOS SUGERIDOS" in partes_do_resultado and incluir_links_internos:
                        with st.expander("🔗 Links Sugeridos"):
                            st.markdown(partes_do_resultado["🔗 LINKS INTERNOS SUGERIDOS"])
                    
                    # 4. Conteúdo Otimizado
                    st.subheader("📝 Conteúdo Otimizado")
                    conteudo_final = partes_do_resultado.get("📝 CONTEÚDO OTIMIZADO", resultado)
                    st.markdown(conteudo_final)
                    
                    # Verificações
                    st.subheader("🔍 Verificação")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        bullets = conteudo_final.count("- ") + conteudo_final.count("* ")
                        st.metric("Bullet Points", bullets)
                    with col2:
                        has_heading = nivel_heading.lower() in conteudo_final.lower()
                        st.metric(f"Heading {nivel_heading}", "✅" if has_heading else "❌")
                    with col3:
                        has_meta = 'title' in conteudo_final[:500].lower() or 'description' in conteudo_final[:500].lower()
                        st.metric("Meta Tags", "✅" if has_meta else "❌")
                    
                    # Download
                    st.download_button(
                        "💾 Baixar Conteúdo Otimizado",
                        data=conteudo_final,
                        file_name=f"conteudo_otimizado_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                        mime="text/plain"
                    )
                    
                except Exception as e:
                    st.error(f"❌ Erro na otimização: {str(e)}")
                    st.info("Dica: Verifique sua conexão com a API do Gemini")
        else:
            st.warning("Por favor, cole um conteúdo para otimizar")

    # Ajustes incrementais
    if st.session_state.conteudo_otimizado:
        st.divider()
        st.subheader("🔄 Ajustes Incrementais")
        
        comando_ajuste = st.text_area(
            "Ajustes desejados:",
            height=80,
            placeholder="Ex: Adicione mais bullets, corrija headings, melhore meta tags...",
            key="ajuste_text"
        )
        
        if st.button("🔄 Aplicar Ajustes", key="btn_ajuste"):
            if comando_ajuste:
                with st.spinner("Aplicando ajustes..."):
                    try:
                        prompt_ajuste = f"""
                        **CONTEÚDO ATUAL:** {st.session_state.conteudo_otimizado[:1000]}
                        
                        **AJUSTES SOLICITADOS:** {comando_ajuste}
                        
                        **MANTENHA:** 
                        - Meta tags existentes
                        - Heading level {nivel_heading}
                        - Bullets onde aplicável
                        
                        Aplique os ajustes e retorne APENAS o conteúdo atualizado.
                        """
                        
                        resposta = modelo_texto.generate_content(prompt_ajuste)
                        st.session_state.conteudo_otimizado = resposta.text
                        st.session_state.ajustes_realizados.append(comando_ajuste)
                        
                        st.success("✅ Ajustes aplicados!")
                        st.markdown(resposta.text)
                        
                    except Exception as e:
                        st.error(f"Erro: {str(e)}")
            else:
                st.warning("Digite os ajustes desejados")
        
        # Limpar histórico
        if st.button("🗑️ Limpar Histórico de Ajustes"):
            st.session_state.ajustes_realizados = []
            st.success("Histórico limpo")
            
# ========== ABA: CRIADORA DE CALENDÁRIO ==========
with tab_mapping["📅 Criadora de Calendário"]:
    st.header("📅 Criadora de Calendário")
    
    if not st.session_state.agente_selecionado:
        st.warning("Nenhum agente selecionado.")
    else:
        agente = st.session_state.agente_selecionado
        st.success(f"Agente: {agente['nome']}")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            mes_ano = st.text_input("Mês/Ano:", "FEVEREIRO 2026")
            data_inicio = st.date_input("Data início:", value=datetime.date(2026, 2, 1))
            data_fim = st.date_input("Data fim:", value=datetime.date(2026, 2, 28))
            
            delta_dias = (data_fim - data_inicio).days + 1
            
            
        
        with col2:
            dias_com_1_pauta = st.number_input("Dias com 1 pauta:", 0, delta_dias, 5)
            dias_com_2_pautas = st.number_input("Dias com 2 pautas:", 0, delta_dias, 15)
            dias_com_3_pautas = st.number_input("Dias com 3 pautas:", 0, delta_dias, 3)
            dias_sem_pautas = delta_dias - (dias_com_1_pauta + dias_com_2_pautas + dias_com_3_pautas)
            
            if dias_sem_pautas < 0:
                st.error("Total excede dias disponíveis")
        
        st.subheader("Produtos e Direcionais")
        
        produtos_direcionais = st.text_area(
            "Produtos",
            height=150
        )
        
        produtos_com_direcionais = []
        if produtos_direcionais:
            for linha in produtos_direcionais.split('\n'):
                linha = linha.strip()
                if linha and ' - ' in linha:
                    partes = linha.split(' - ')
                    if len(partes) >= 3:
                        produtos = [p.strip() for p in partes[0].split(' e ') if p.strip()]
                        tema = ' - '.join(partes[2:]).strip()
                        produtos_com_direcionais.append({
                            'produtos': produtos,
                            'tema': tema
                        })
        
        col_feira, col_recorrente = st.columns(2)
        
        with col_feira:
            st.write("Semana com evento (1 post/dia):")
            semana_feira_inicio = st.date_input("Início:", value=datetime.date(2026, 2, 9))
            semana_feira_fim = st.date_input("Fim:", value=datetime.date(2026, 2, 13))
            produtos_prioritarios_feira = st.text_input("Produtos prioritários:")
        
        with col_recorrente:
            pauta_recorrente_texto = st.text_input("Pauta fixa:")
            pauta_recorrente_dias = st.multiselect(
                "Dias da semana:",
                ["Terça", "Quinta"],
                default=["Terça", "Quinta"]
            )
        
        contexto_mensal = st.text_area(
            "Contexto do mês:",
            
            height=120
        )
        
        evitar_consecutivos_sem_pautas = st.checkbox("Evitar dias consecutivos sem pautas", True)
        max_repeticoes_tema = st.slider("Máx repetições por tema:", 1, 5, 2)
        
        if st.button("Gerar Calendário", type="primary"):
            if data_inicio >= data_fim:
                st.error("Data início deve ser anterior")

            elif (dias_com_1_pauta + dias_com_2_pautas + dias_com_3_pautas) > delta_dias:
                st.error("Total excede período")
            else:
                with st.spinner("Gerando calendário..."):
                    try:
                        contexto_agente = construir_contexto(agente, st.session_state.segmentos_selecionados)
                        
                        info_especifica = f"""
                        CONFIGURAÇÕES:
                        1. SEMANA COM EVENTO ({semana_feira_inicio.strftime('%d/%m')} a {semana_feira_fim.strftime('%d/%m')}):
                           - Apenas 1 pauta por dia
                           - Priorizar: {produtos_prioritarios_feira}
                        
                        2. PAUTA FIXA: "{pauta_recorrente_texto}"
                           - Dias: {', '.join(pauta_recorrente_dias)}
                        
                        3. FREQUÊNCIA:
                           - Dias com 1 pauta: {dias_com_1_pauta}
                           - Dias com 2 pautas: {dias_com_2_pautas} 
                           - Dias com 3 pautas: {dias_com_3_pautas}
                           - Dias sem pautas: {max(0, dias_sem_pautas)}
                           - Evitar consecutivos sem pautas: {evitar_consecutivos_sem_pautas}
                        
                        4. CONTROLE REPETIÇÃO:
                           - Máximo repetições por tema: {max_repeticoes_tema}
                        """
                        
                        prompt_calendario = f'''
                        {contexto_agente}

                        GERAR CALENDÁRIO COM ESTAS REGRAS:

                        PERÍODO: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}
                        MÊS: {mes_ano}
                        
                        {info_especifica}
                        
                        CONTEXTO: {contexto_mensal}
                        
                        PRODUTOS E TEMAS:
                        {chr(10).join([f"- {', '.join(p['produtos'])} - {', '.join(p['culturas'])} - {p['tema']}" for p in produtos_com_direcionais])}
                        
                        REGRAS CRÍTICAS:
                        1. Semana {semana_feira_inicio.strftime('%d/%m')} a {semana_feira_fim.strftime('%d/%m')}: APENAS 1 PAUTA POR DIA
                        2. Priorizar produtos: {produtos_prioritarios_feira} na semana da feira
                        3. Inserir "{pauta_recorrente_texto}" em TODAS as {', '.join(pauta_recorrente_dias)}
                        4. NÃO repetir temas (máximo {max_repeticoes_tema} repetições)
                        6. Praticamente todos os dias com conteúdo
                        7. NUNCA 3 dias consecutivos sem pautas
                        8. Baseie pautas no contexto do mês
                        
                        FORMATO:
                        - Célula: "[EMOJI] Produto(s) - Tema - Breve descrição"
                        
                        Retorne CSV pronto para Excel.
                        '''
                        
                        resposta = modelo_texto.generate_content(prompt_calendario)
                        calendario_csv = resposta.text
                        
                        calendario_limpo = calendario_csv.strip()
                        if '```csv' in calendario_limpo:
                            calendario_limpo = calendario_limpo.replace('```csv', '').replace('```', '')
                        if '```' in calendario_limpo:
                            calendario_limpo = calendario_limpo.replace('```', '')
                        
                        st.session_state.calendario_gerado = calendario_limpo
                        st.session_state.mes_ano_calendario = mes_ano
                        
                        st.success("Calendário gerado")
                        
                    except Exception as e:
                        st.error(f"Erro: {str(e)}")
        
        if 'calendario_gerado' in st.session_state:
            st.subheader(f"Calendário - {st.session_state.mes_ano_calendario}")
            
            tab_csv, tab_xlsx = st.tabs(["CSV", "XLSX"])
            
            with tab_csv:
                st.text_area("CSV:", st.session_state.calendario_gerado, height=400)
                
                st.download_button(
                    "Baixar CSV",
                    data=st.session_state.calendario_gerado,
                    file_name=f"calendario_{mes_ano.replace(' ', '_').lower()}.csv",
                    mime="text/csv"
                )
            
            with tab_xlsx:
                try:
                    import openpyxl
                    from openpyxl.styles import Font, Alignment, Border, Side
                    from io import BytesIO
                    
                    def gerar_xlsx():
                        wb = openpyxl.Workbook()
                        ws = wb.active
                        ws.title = f"Calendário {mes_ano}"
                        
                        ws.merge_cells('A1:G1')
                        ws['A1'] = f"CALENDÁRIO - {mes_ano}"
                        ws['A1'].font = Font(bold=True, size=14)
                        ws['A1'].alignment = Alignment(horizontal='center')
                        
                        dias_semana = ["DOMINGO", "SEGUNDA", "TERÇA", "QUARTA", "QUINTA", "SEXTA", "SÁBADO"]
                        for col, dia in enumerate(dias_semana, 1):
                            cell = ws.cell(row=3, column=col)
                            cell.value = dia
                            cell.font = Font(bold=True)
                            cell.alignment = Alignment(horizontal='center')
                        
                        linhas = st.session_state.calendario_gerado.split('\n')
                        linha_atual = 4
                        
                        for linha in linhas:
                            if linha.strip() and not linha.startswith(',,'):
                                celulas = linha.split(',')
                                for col, conteudo in enumerate(celulas, 1):
                                    if conteudo.strip():
                                        cell = ws.cell(row=linha_atual, column=col)
                                        cell.value = conteudo.strip()
                                        cell.alignment = Alignment(wrap_text=True, vertical='top')
                                        cell.border = Border(
                                            left=Side(style='thin'),
                                            right=Side(style='thin'),
                                            top=Side(style='thin'),
                                            bottom=Side(style='thin')
                                        )
                                linha_atual += 1
                        
                        for col in range(1, 8):
                            ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 30
                            for row in range(4, linha_atual):
                                ws.row_dimensions[row].height = 60
                        
                        buffer = BytesIO()
                        wb.save(buffer)
                        buffer.seek(0)
                        return buffer
                    
                    if st.button("Gerar XLSX"):
                        buffer_xlsx = gerar_xlsx()
                        
                        st.download_button(
                            "Baixar XLSX",
                            data=buffer_xlsx.getvalue(),
                            file_name=f"calendario_{mes_ano.replace(' ', '_').lower()}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    
                except ImportError:
                    st.write("Para XLSX: pip install openpyxl")
                    st.code("pip install openpyxl")
                except Exception as e:
                    st.error(f"Erro XLSX: {str(e)}")



with tab_mapping["📓 Diário de Bordo"]:
    st.header("📓 Diário de Bordo - Cliente")
    
    if not st.session_state.agente_selecionado:
        st.warning("⚠️ Selecione um agente primeiro na aba de Chat")
        st.stop()
    
    agente = st.session_state.agente_selecionado
    st.subheader(f"Diário para: {agente['nome']}")
    
    # Carregar comentários atuais do agente
    comentarios_atuais = agente.get('comments', '')
    
    # Layout em abas
    tab_visualizar, tab_adicionar, tab_relatorio = st.tabs(["👁️ Visualizar", "➕ Adicionar", "📊 Relatório"])
    
    # --- TAB: VISUALIZAR DIÁRIO ---
    with tab_visualizar:
        if comentarios_atuais:
            # Exibir com formatação
            st.markdown("### 📝 Diário Atual do Cliente")
            
            # Estatísticas
            palavras = len(comentarios_atuais.split())
            caracteres = len(comentarios_atuais)
            linhas = comentarios_atuais.count('\n') + 1
            
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            with col_stat1:
                st.metric("📝 Palavras", palavras)
            with col_stat2:
                st.metric("🔤 Caracteres", caracteres)
            with col_stat3:
                st.metric("📄 Linhas", linhas)
            
            # Área de visualização
            st.text_area(
                "Conteúdo do diário:",
                value=comentarios_atuais,
                height=400,
                disabled=True,
                key="visualizar_diario"
            )
            
            # Botão para exportar
            st.download_button(
                "💾 Exportar Diário",
                data=comentarios_atuais,
                file_name=f"diario_{agente['nome']}_{datetime.datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain"
            )
            
            # Análise rápida
            with st.expander("🔍 Análise Rápida", expanded=False):

                palavras_chave = ['problema', 'ajuste', 'melhorar', 'gostei', 'não gostei', 'sugestão', 'importante', 'urgente']
                contagens = {}
                    
                texto_lower = comentarios_atuais.lower()
                for palavra in palavras_chave:
                    contagens[palavra] = texto_lower.count(palavra)
                    
                st.write("**Palavras-chave encontradas:**")
                for palavra, count in contagens.items():
                    if count > 0:
                        st.write(f"- {palavra}: {count} ocorrência(s)")
                    
                if sum(contagens.values()) == 0:
                        st.info("Nenhuma palavra-chave comum encontrada")
                
        
        else:
            st.info("📭 O diário está vazio. Adicione conteúdo na aba 'Adicionar'")
    
    # --- TAB: ADICIONAR CONTEÚDO ---
    with tab_adicionar:
        st.markdown("### 📤 Adicionar ao Diário")
        
        # Método de adição
        metodo_adicional = st.radio(
            "Como deseja adicionar conteúdo:",
            ["📝 Texto Manual", "📎 Upload de Documento", "✂️ Extrair de Conversa"],
            horizontal=True
        )
        
        if metodo_adicional == "📝 Texto Manual":
            st.markdown("#### ✍️ Adicionar Notas Manuais")
            
            data_registro = st.date_input("Data do registro:", value=datetime.datetime.now())
            titulo_registro = st.text_input("Título/Contexto:", placeholder="Ex: Reunião de ajuste, Feedback por email, etc.")
            
            novo_conteudo = st.text_area(
                "Conteúdo:",
                height=200,
                placeholder="""Exemplo:
                
                Reunião com cliente em 15/03:
                - Cliente pediu tom mais técnico nos parágrafos 3-5
                - Solicitaram inclusão de mais dados de pesquisa
                - Aprovaram mudança na estrutura de tópicos
                - Próxima revisão: 22/03""",
                help="Descreva o feedback, observações ou decisões"
            )
            
            if st.button("💾 Salvar no Diário", type="primary", key="salvar_manual"):
                if novo_conteudo.strip():
                    # Formatar entrada
                    entrada_formatada = f"\n\n--- {titulo_registro if titulo_registro else 'Nova Entrada'} ({data_registro.strftime('%d/%m/%Y')}) ---\n{novo_conteudo}"
                    
                    # Atualizar comentários
                    novos_comentarios = comentarios_atuais + entrada_formatada
                    
                    # Atualizar agente no banco
                    atualizar_agente(
                        agente['_id'],
                        agente['nome'],
                        agente.get('system_prompt', ''),
                        agente.get('base_conhecimento', ''),
                        novos_comentarios,
                        agente.get('planejamento', ''),
                        agente.get('categoria', 'Social'),
                        agente.get('squad_permitido', 'Todos'),
                        agente.get('agente_mae_id'),
                        agente.get('herdar_elementos', [])
                    )
                    
                    # Atualizar session state
                    st.session_state.agente_selecionado = obter_agente_com_heranca(agente['_id'])
                    
                    st.success("✅ Conteúdo adicionado ao diário!")
                    st.balloons()
                    st.rerun()
                else:
                    st.warning("Digite algum conteúdo para salvar")
        
        elif metodo_adicional == "📎 Upload de Documento":
            st.markdown("#### 📎 Carregar Documento")
            
            uploaded_file = st.file_uploader(
                "Selecione um documento (PDF, DOCX, TXT):",
                type=['pdf', 'docx', 'txt'],
                key="upload_diario"
            )
            
            if uploaded_file:
                st.success(f"✅ {uploaded_file.name} carregado")
                
                # Extrair texto
                with st.spinner("Extraindo texto..."):
                    try:
                        if uploaded_file.type == "application/pdf":
                            texto_extraido, _ = extract_text_from_pdf_com_slides(uploaded_file)
                        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                            texto_extraido = extrair_texto_arquivo(uploaded_file)
                        elif uploaded_file.type == "text/plain":
                            texto_extraido = str(uploaded_file.read(), "utf-8")
                        else:
                            texto_extraido = f"[Arquivo {uploaded_file.type} não suportado para extração automática]"
                        
                        # Mostrar preview
                        with st.expander("👁️ Preview do Texto Extraído", expanded=False):
                            st.text_area("", value=texto_extraido[:1000], height=200, disabled=True)
                        
                        # Adicionar contexto
                        st.markdown("#### 📝 Contexto do Documento")
                        contexto_doc = st.text_input(
                            "Contexto/Origem:",
                            placeholder="Ex: Email do cliente, Relatório de reunião, Feedback por escrito"
                        )
                        
                        if st.button("💾 Adicionar Documento ao Diário", type="primary"):
                            if texto_extraido.strip():
                                # Formatar entrada
                                data_atual = datetime.datetime.now().strftime('%d/%m/%Y')
                                contexto = contexto_doc if contexto_doc else "Documento carregado"
                                entrada_formatada = f"\n\n--- {contexto} - {uploaded_file.name} ({data_atual}) ---\n{texto_extraido[:10000]}"  # Limitar tamanho
                                
                                # Atualizar comentários
                                novos_comentarios = comentarios_atuais + entrada_formatada
                                
                                # Atualizar agente
                                atualizar_agente(
                                    agente['_id'],
                                    agente['nome'],
                                    agente.get('system_prompt', ''),
                                    agente.get('base_conhecimento', ''),
                                    novos_comentarios,
                                    agente.get('planejamento', ''),
                                    agente.get('categoria', 'Social'),
                                    agente.get('squad_permitido', 'Todos'),
                                    agente.get('agente_mae_id'),
                                    agente.get('herdar_elementos', [])
                                )
                                
                                # Atualizar session state
                                st.session_state.agente_selecionado = obter_agente_com_heranca(agente['_id'])
                                
                                st.success(f"✅ Documento '{uploaded_file.name}' adicionado ao diário!")
                                st.rerun()
                            else:
                                st.warning("Documento vazio ou não foi possível extrair texto")
                    
                    except Exception as e:
                        st.error(f"❌ Erro ao processar documento: {str(e)}")
        
        elif metodo_adicional == "✂️ Extrair de Conversa":
            st.markdown("#### 💬 Extrair de Histórico de Chat")
            
            # Carregar conversas recentes
            conversas = obter_conversas(agente['_id'], limite=5)
            
            if conversas:
                st.info("Selecione uma conversa para extrair trechos:")
                
                for i, conversa in enumerate(conversas):
                    with st.expander(f"Conversa {i+1} - {conversa.get('data_criacao', 'Data desconhecida')}", expanded=False):
                        # Mostrar mensagens
                        mensagens = conversa.get('mensagens', [])
                        for msg in mensagens[-6:]:  # Últimas 6 mensagens
                            role = "👤" if msg.get("role") == "user" else "🤖"
                            st.write(f"{role}: {msg.get('content', '')[:200]}...")
                        
                        # Botão para selecionar
                        if st.button(f"📋 Usar esta conversa", key=f"usar_conversa_{i}"):
                            # Extrair texto da conversa
                            texto_conversa = ""
                            for msg in mensagens:
                                if msg.get("role") == "user":  # Apenas mensagens do usuário
                                    texto_conversa += f"Cliente: {msg.get('content', '')}\n"
                            
                            if texto_conversa.strip():
                                # Formatar entrada
                                data_atual = datetime.datetime.now().strftime('%d/%m/%Y')
                                entrada_formatada = f"\n\n--- Conversa extraída ({data_atual}) ---\n{texto_conversa}"
                                
                                # Atualizar comentários
                                novos_comentarios = comentarios_atuais + entrada_formatada
                                
                                # Atualizar agente
                                atualizar_agente(
                                    agente['_id'],
                                    agente['nome'],
                                    agente.get('system_prompt', ''),
                                    agente.get('base_conhecimento', ''),
                                    novos_comentarios,
                                    agente.get('planejamento', ''),
                                    agente.get('categoria', 'Social'),
                                    agente.get('squad_permitido', 'Todos'),
                                    agente.get('agente_mae_id'),
                                    agente.get('herdar_elementos', [])
                                )
                                
                                # Atualizar session state
                                st.session_state.agente_selecionado = obter_agente_com_heranca(agente['_id'])
                                
                                st.success("✅ Conversa adicionada ao diário!")
                                st.rerun()
                            else:
                                st.warning("Nenhuma mensagem do usuário encontrada nesta conversa")
            else:
                st.info("Nenhuma conversa recente encontrada")
    
    # --- TAB: RELATÓRIO ---
    with tab_relatorio:
        st.markdown("### 📊 Relatório de Andamento com Cliente")
        
        if not comentarios_atuais or len(comentarios_atuais.strip()) < 50:
            st.info("📭 Diário muito curto para gerar relatório. Adicione mais conteúdo primeiro.")
        else:
            # Configurações do relatório
            col_config1, col_config2 = st.columns(2)
            
            with col_config1:
                tipo_analise = st.selectbox(
                    "Tipo de análise:",
                    ["Análise Completa", "Foco em Oportunidades", "Identificar Problemas", "Evolução do Feedback", "Próximos Passos"],
                    help="Escolha o tipo de análise desejada"
                )
            
            with col_config2:
                formato_relatorio = st.selectbox(
                    "Formato do relatório:",
                    ["Relatório Executivo", "Lista de Ações", "Análise Detalhada", "Resumo Rápido"]
                )
            
            # Perguntas específicas
            perguntas_especificas = st.text_area(
                "Perguntas para análise (opcional):",
                height=100,
                placeholder="Ex: \n1. Quais são os principais pontos de atenção?\n2. Há padrões no feedback?\n3. Quais oportunidades de melhoria?",
                help="Adicione perguntas específicas para direcionar a análise"
            )
            
            if st.button("📈 Gerar Análise do Diário", type="primary", key="gerar_analise_diario"):
                with st.spinner("🔍 Analisando diário..."):
                    try:
                        # Construir prompt para análise
                        prompt_analise = f"""
                        ## ANÁLISE DE DIÁRIO DE CLIENTE - RELATÓRIO DE ANDAMENTO
                        
                        **AGENTE:** {agente['nome']}
                        **CATEGORIA:** {agente.get('categoria', 'N/A')}
                        **TIPO DE ANÁLISE:** {tipo_analise}
                        **FORMATO:** {formato_relatorio}
                        
                        **CONTEÚDO DO DIÁRIO (COMENTÁRIOS DO CLIENTE):**
                        {comentarios_atuais[:8000]}
                        
                        **PERGUNTAS ESPECÍFICAS PARA ANÁLISE:**
                        {perguntas_especificas if perguntas_especificas else 'Nenhuma pergunta específica fornecida'}
                        
                        ## INSTRUÇÕES:
                        
                        Analise o diário/comentários do cliente e gere um relatório que identifique:
                        
                        1. **PADRÕES E TENDÊNCIAS** no feedback do cliente
                        2. **OPORTUNIDADES** para melhoria do agente/serviço
                        3. **RED FLAGS** ou pontos críticos que precisam de atenção imediata
                        4. **EVOLUÇÃO** do feedback ao longo do tempo
                        5. **INSIGHTS** valiosos sobre as preferências do cliente
                        6. **RECOMENDAÇÕES** concretas para próximos passos
                        
                        ## FORMATAÇÃO ESPECÍFICA:
                        
                        Use esta estrutura EXATA para o relatório:
                        
                        # 📊 RELATÓRIO DE ANDAMENTO - {agente['nome']}
                        **Data da análise:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}
                        **Tipo:** {tipo_analise}
                        
                        ## 🎯 RESUMO EXECUTIVO
                        [2-3 parágrafos com visão geral]
                        
                        ## 📈 OPORTUNIDADES IDENTIFICADAS
                        [Lista com bullets das principais oportunidades]
                        
                        ## ⚠️ RED FLAGS / PONTOS CRÍTICOS
                        [Lista com bullets dos problemas identificados]
                        
                        ## 💡 INSIGHTS E PADRÕES
                        [Principais descobertas sobre o cliente]
                        
                        ## 🚀 PRÓXIMOS PASSOS RECOMENDADOS
                        [Ações específicas e prioritárias]
                        
                        ## 📅 LINHA DO TEMPO SUGERIDA
                        [Cronograma sugerido para implementação]
                        
                        ## 🔍 RESPOSTAS ÀS PERGUNTAS ESPECÍFICAS
                        {perguntas_especificas if perguntas_especificas else 'Nenhuma pergunta específica fornecida'}
                        
                        ---
                        *Análise gerada automaticamente com base no diário do cliente*
                        """
                        
                        # Gerar análise com Gemini
                        resposta = modelo_texto.generate_content(prompt_analise)
                        relatorio_gerado = resposta.text
                        
                        # Salvar no session state
                        st.session_state.ultima_analise_diario = relatorio_gerado
                        
                        # Exibir relatório
                        st.markdown("---")
                        st.subheader("📋 Relatório de Análise")
                        st.markdown(relatorio_gerado)
                        
                        # Estatísticas
                        palavras_diario = len(comentarios_atuais.split())
                        palavras_relatorio = len(relatorio_gerado.split())
                        
                        col_stat1, col_stat2, col_stat3 = st.columns(3)
                        with col_stat1:
                            st.metric("📚 Palavras do Diário", palavras_diario)
                        with col_stat2:
                            st.metric("📝 Palavras do Relatório", palavras_relatorio)
                        with col_stat3:
                            st.metric("📊 Taxa de Síntese", f"{(palavras_relatorio/palavras_diario*100):.1f}%" if palavras_diario > 0 else "N/A")
                        
                        # Botões de download
                        col_dl1, col_dl2 = st.columns(2)
                        
                        with col_dl1:
                            st.download_button(
                                "💾 Baixar Relatório (TXT)",
                                data=relatorio_gerado,
                                file_name=f"analise_diario_{agente['nome']}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                                mime="text/plain",
                                key="download_analise"
                            )
                        
                        with col_dl2:
                            # Extrair ações para CSV
                            acoes_csv = "Tipo,Ação,Prioridade\n"
                            
                            # Extrair oportunidades
                            if "OPORTUNIDADES IDENTIFICADAS" in relatorio_gerado:
                                inicio = relatorio_gerado.find("OPORTUNIDADES IDENTIFICADAS")
                                fim = relatorio_gerado.find("##", inicio + 1)
                                if fim != -1:
                                    conteudo = relatorio_gerado[inicio:fim]
                                    for linha in conteudo.split('\n'):
                                        if linha.strip().startswith('-') or linha.strip().startswith('•'):
                                            acao = linha.strip().lstrip('-• ').strip()
                                            acoes_csv += f"OPORTUNIDADE,\"{acao}\",MÉDIA\n"
                            
                            # Extrair próximos passos
                            if "PRÓXIMOS PASSOS RECOMENDADOS" in relatorio_gerado:
                                inicio = relatorio_gerado.find("PRÓXIMOS PASSOS RECOMENDADOS")
                                fim = relatorio_gerado.find("##", inicio + 1)
                                if fim != -1:
                                    conteudo = relatorio_gerado[inicio:fim]
                                    for linha in conteudo.split('\n'):
                                        if linha.strip().startswith('-') or linha.strip().startswith('•'):
                                            acao = linha.strip().lstrip('-• ').strip()
                                            acoes_csv += f"AÇÃO,\"{acao}\",ALTA\n"
                            
                            st.download_button(
                                "📋 Baixar Ações (CSV)",
                                data=acoes_csv,
                                file_name=f"acoes_diario_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                mime="text/csv",
                                key="download_acoes"
                            )
                        
                        # Sugestão de integração
                        with st.expander("🔄 Integrar com Agente", expanded=False):
                            st.info("Use estas sugestões para melhorar o agente:")
                            
                            # Botão para aplicar sugestões ao system prompt
                            if st.button("✨ Aplicar Insights ao Agente"):
                                try:
                                    # Extrair insights do relatório
                                    insights = []
                                    if "INSIGHTS E PADRÕES" in relatorio_gerado:
                                        inicio = relatorio_gerado.find("INSIGHTS E PADRÕES")
                                        fim = relatorio_gerado.find("##", inicio + 1)
                                        if fim != -1:
                                            conteudo = relatorio_gerado[inicio:fim]
                                            for linha in conteudo.split('\n'):
                                                if linha.strip().startswith('-') or linha.strip().startswith('•'):
                                                    insights.append(linha.strip().lstrip('-• ').strip())
                                    
                                    if insights:
                                        # Atualizar system prompt com insights
                                        system_prompt_atual = agente.get('system_prompt', '')
                                        novos_insights = "\n\n## INSIGHTS DO DIÁRIO DO CLIENTE:\n" + "\n".join([f"- {insight}" for insight in insights[:5]])
                                        novo_system_prompt = system_prompt_atual + novos_insights
                                        
                                        # Atualizar agente
                                        atualizar_agente(
                                            agente['_id'],
                                            agente['nome'],
                                            novo_system_prompt,
                                            agente.get('base_conhecimento', ''),
                                            comentarios_atuais,  # Mantém os comentários
                                            agente.get('planejamento', ''),
                                            agente.get('categoria', 'Social'),
                                            agente.get('squad_permitido', 'Todos'),
                                            agente.get('agente_mae_id'),
                                            agente.get('herdar_elementos', [])
                                        )
                                        
                                        st.session_state.agente_selecionado = obter_agente_com_heranca(agente['_id'])
                                        st.success("✅ Insights aplicados ao agente!")
                                    else:
                                        st.warning("Nenhum insight extraído do relatório")
                                
                                except Exception as e:
                                    st.error(f"Erro ao aplicar insights: {str(e)}")
                    
                    except Exception as e:
                        st.error(f"❌ Erro ao gerar análise: {str(e)}")

# --- ADICIONAR APÓS A ABA DE CRIADORA DE CALENDÁRIO ---
with tab_mapping["📊 Planejamento Estratégico"]:
    st.header("📊 Planejamento Estratégico")
    st.markdown("""
    Aqui é gerado o planejamento de Pesquisa e Estratégia. 
    Geramos análise SWOT, análise PEST, análise de concorrências, Golden Circle, 
    Posicionamento de marca, Brand Persona, Buyer Persona e Tom de Voz
    """)
    
    # Importar uuid
    import uuid
    
    # Funções do MongoDB
    def gerar_id_planejamento():
        return str(uuid.uuid4())
    
    def save_to_mongo_MKT(SWOT_output, PEST_output, concorrencias_output, golden_output, 
                         posicionamento_output, brand_persona_output, buyer_persona_output, 
                         tom_output, nome_cliente):
        """Salva o planejamento estratégico no MongoDB"""
        try:
            client2 = MongoClient("mongodb+srv://gustavoromao3345:RqWFPNOJQfInAW1N@cluster0.5iilj.mongodb.net/auto_doc?retryWrites=true&w=majority&ssl=true&ssl_cert_reqs=CERT_NONE&tlsAllowInvalidCertificates=true")
            db = client2['arquivos_planejamento']
            collection = db['auto_doc']
            
            id_planejamento = gerar_id_planejamento()
            
            task_outputs = {
                "id_planejamento": f'Plano_Estrategico_{nome_cliente}_{id_planejamento}',
                "nome_cliente": nome_cliente,
                "tipo_plano": 'Plano Estratégico',
                "data_criacao": datetime.datetime.now(),
                "Etapa_1_Pesquisa_Mercado": {
                    "Análise_SWOT": SWOT_output,
                    "Análise_PEST": PEST_output,
                    "Análise_Concorrência": concorrencias_output,
                },
                "Etapa_2_Estrategica": {
                    "Golden_Circle": golden_output,
                    "Posicionamento_Marca": posicionamento_output,
                    "Brand_Persona": brand_persona_output,
                    "Buyer_Persona": buyer_persona_output,
                    "Tom_de_Voz": tom_output,
                }
            }
            
            collection.insert_one(task_outputs)
            st.success(f"✅ Planejamento gerado com sucesso e salvo no banco de dados!")
            return True
        except Exception as e:
            st.error(f"❌ Erro ao salvar no MongoDB: {str(e)}")
            return False
    
    # Configuração do Gemini
    gemini_api_key = os.getenv("GEM_API_KEY")
    if gemini_api_key:
        genai.configure(api_key=gemini_api_key)
        modelo_planejamento = genai.GenerativeModel("gemini-2.5-flash")
    else:
        st.error("❌ GEM_API_KEY não encontrada nas variáveis de ambiente")
        st.stop()
    
    # Textos explicativos
    exp_golden = '''
    Comunique seu 'porquê' aos seus clientes

    Sinek explica que o 'Porquê' é provavelmente a mensagem mais importante que uma organização ou indivíduo pode comunicar, pois é isso que inspira os outros a agir. "Comece pelo Porquê" é a forma de explicar seu propósito, a razão pela qual você existe e se comporta como se comporta. A teoria de Sinek é que comunicar com sucesso a paixão por trás do 'Porquê' é uma maneira de se conectar com o cérebro límbico do ouvinte. Essa é a parte do nosso cérebro que processa sentimentos como confiança e lealdade – além de ser responsável pela tomada de decisões.

    Articular com sucesso seu 'Porquê' é uma maneira muito impactante de se comunicar com outras pessoas, definir sua proposta de valor específica e inspirá-las a agir. Sinek argumenta que comunicar o 'Porquê' ativa a parte do cérebro que influencia o comportamento. É por isso que o modelo do Círculo Dourado é considerado uma teoria tão influente de liderança. No nível organizacional, comunicar seu 'Porquê' é a base de uma proposta de valor forte que diferenciará sua marca das demais.

    Anthony Villis apresenta um visual útil no blog First Wealth, relacionando os objetivos do Círculo Dourado à resposta psicológica.

    Como
    Os fatores do 'Como' de uma organização podem incluir seus pontos fortes ou valores que a diferenciam da concorrência. Sinek afirma que a mensagem do 'Como' também pode se comunicar com o cérebro límbico – a parte importante que governa o comportamento e a emoção. No entanto, ele defende que as organizações deveriam melhorar a forma como articulam seu 'Porquê', além do 'Como'.

    O que
    É relativamente fácil para qualquer líder ou organização articular 'O que' fazem. Isso pode ser expresso pelos produtos que uma empresa vende ou pelos serviços que oferece. Para um indivíduo, seria seu cargo. Sinek argumenta que a comunicação do 'O que' envolve apenas o neocórtex – a parte racional do nosso cérebro. Ele acredita que essa parte do cérebro tem um papel menor na tomada de decisões em comparação ao cérebro límbico, que é alcançado melhor pelo 'Porquê' e pelo 'Como'. Pessoas e organizações bem-sucedidas expressam por que fazem o que fazem, em vez de se concentrarem apenas no que fazem.
    '''
    
    # Formulário de entrada de dados
    st.markdown("### 📋 Informações do Cliente")
    
    col1, col2 = st.columns(2)
    
    with col1:
        nome_cliente = st.text_input('Nome do Cliente:', 
                                   help="Digite o nome do cliente que será planejado. Ex: 'Empresa XYZ'",
                                   key="nome_cliente_planejamento")
        site_cliente = st.text_input('Site do Cliente:', key="site_cliente_planejamento")
        ramo_atuacao = st.text_input('Ramo de Atuação:', key="ramo_atuacao_planejamento")
    
    with col2:
        intuito_plano = st.text_input('Intuito do Planejamento estratégico:', 
                                    placeholder="Ex: Aumentar as vendas em 30% no próximo trimestre...",
                                    key="intuito_plano_planejamento")
        publico_alvo = st.text_input('Público alvo:', 
                                   placeholder="Ex: Jovens de 18 a 25 anos, interessados em moda...",
                                   key="publico_alvo_planejamento")
    
    st.markdown("### 🏆 Objetivos e Sucesso")
    
    objetivos_opcoes = [
        'Criar ou aumentar relevância, reconhecimento e autoridade para a marca',
        'Entregar potenciais consumidores para a área comercial',
        'Venda, inscrição, cadastros, contratação ou qualquer outra conversão final do público',
        'Fidelizar e reter um público fiel já convertido',
        'Garantir que o público esteja engajado com os canais ou ações da marca'
    ]
    
    objetivos_de_marca = st.selectbox('Quais são os objetivos da sua marca?', 
                                    objetivos_opcoes, 
                                    key="objetivos_marca_planejamento")
    
    referencia_da_marca = st.text_area('Referência de marca:', 
                                     placeholder="Conte um pouco mais sobre sua marca, o que ela representa, seus valores e diferenciais no mercado...",
                                     height=100,
                                     key="referencia_da_marca_planejamento")

    contexto_extra = st.text_area('Contexto adicional e/ou Briefing:', 
                                     placeholder="",
                                     height=100,
                                     key="contexto_extra")
    
    sucesso = st.text_input('O que é sucesso para a marca?:', 
                          help='Redija aqui um texto que define o que a marca considera como sucesso.',
                          key="sucesso_planejamento")
    
    st.markdown("### 🥊 Concorrência")
    
    concorrentes = st.text_input('Concorrentes:', 
                               placeholder="Ex: Loja A, Loja B, Loja C. Liste os concorrentes mais relevantes...",
                               key="concorrentes_planejamento")
    
    site_concorrentes = st.text_input('Site dos concorrentes:', 
                                    placeholder="Ex: www.loja-a.com.br, www.loja-b.com.br, www.loja-c.com.br",
                                    key="site_concorrentes_planejamento")
    

    
    # Botão para iniciar planejamento
    if st.button("🚀 Iniciar Planejamento Estratégico", type="primary", use_container_width=True, key="iniciar_planejamento"):
        # Validação dos campos obrigatórios
        campos_obrigatorios = [nome_cliente, ramo_atuacao, intuito_plano, publico_alvo]
        nomes_campos = ["Nome do Cliente", "Ramo de Atuação", "Intuito do Planejamento", "Público-alvo"]
        
        campos_faltando = []
        for campo, nome in zip(campos_obrigatorios, nomes_campos):
            if not campo or campo.strip() == "":
                campos_faltando.append(nome)
        
        if campos_faltando:
            st.error(f"❌ Por favor, preencha os seguintes campos obrigatórios: {', '.join(campos_faltando)}")
        else:
            with st.spinner("🔍 Iniciando pesquisa e análise de mercado..."):
                try:
                    # Inicializar variáveis para resultados
                    resultados = {}
                    
                    # 1. PESQUISAS WEB COM PERPLEXITY (usando a função realizar_busca_web_com_fontes)
                    st.info("🌐 Realizando pesquisas web...")
                    
                    # Construir contexto do agente para as pesquisas
                    contexto_agente_pesquisa = ""
                    if st.session_state.agente_selecionado:
                        agente_atual = st.session_state.agente_selecionado
                        contexto_agente_pesquisa = construir_contexto(
                            agente_atual, 
                            st.session_state.segmentos_selecionados if hasattr(st.session_state, 'segmentos_selecionados') else []
                        )
                    
                    # Criar container para as pesquisas
                    pesquisa_container = st.container()
                    
                    with pesquisa_container:
                        # Pesquisa política
                        st.write("📰 **Pesquisa política e regulatória...**")
                        pls = realizar_busca_web_com_fontes(
                            f"notícias políticas recentes sobre o Brasil 2024 que podem afetar o setor de {ramo_atuacao}",
                            contexto_agente_pesquisa
                        )
                        
                        # Pesquisa econômica
                        st.write("💰 **Pesquisa econômica e de mercado...**")
                        dados_econ_brasil = realizar_busca_web_com_fontes(
                            f"dados econômicos recentes sobre o Brasil 2024 PIB inflação setor {ramo_atuacao} tendências mercado",
                            contexto_agente_pesquisa
                        )
                        
                        # Pesquisa sobre concorrentes (se houver)
                        if concorrentes and concorrentes.strip():
                            st.write("🏢 **Pesquisa sobre concorrentes...**")
                            novids_conc = realizar_busca_web_com_fontes(
                                f"notícias mais recentes sobre os concorrentes: {concorrentes} no setor de {ramo_atuacao}",
                                contexto_agente_pesquisa
                            )
                        else:
                            novids_conc = "Nenhum concorrente informado para pesquisa."
                        
                        # Pesquisa social
                        st.write("👥 **Pesquisa social e demográfica...**")
                        tend_social_duck = realizar_busca_web_com_fontes(
                            f"novidades no âmbito social brasileiro 2024 que afetam o setor de {ramo_atuacao} tendências sociais demográficas",
                            contexto_agente_pesquisa
                        )
                        
                        # Pesquisa tecnológica
                        st.write("🔬 **Pesquisa tecnológica e inovação...**")
                        tec = realizar_busca_web_com_fontes(
                            f"novidades tecnológicas no ramo de {ramo_atuacao} 2024 tendências inovações tecnologias emergentes",
                            contexto_agente_pesquisa
                        )
                    
                    # Armazenar pesquisas para uso posterior
                    pesquisas = {
                        'politica': pls,
                        'economia': dados_econ_brasil,
                        'concorrentes': novids_conc,
                        'social': tend_social_duck,
                        'tecnologica': tec
                    }
                    
                    # Verificar se as pesquisas tiveram sucesso
                    erros_pesquisa = []
                    for nome, resultado in pesquisas.items():
                        if resultado.startswith("❌") or resultado.startswith("⚠️"):
                            erros_pesquisa.append(nome)
                    
                    if erros_pesquisa:
                        st.warning(f"⚠️ Algumas pesquisas tiveram problemas: {', '.join(erros_pesquisa)}. Continuando com os dados disponíveis.")
                    
                    # 2. ANÁLISE SWOT
                    st.info("📊 Gerando análise SWOT...")
                    
                    prompt_SWOT = f'''Assumindo um especialista em administração de marketing, extraia todo o conhecimento existente sobre marketing em um nível extremamente aprofundado.
                    
                    Para o cliente {nome_cliente}, Considerando o seguinte contexto a referência da marca:
                                {referencia_da_marca}, para o cliente no ramo de atuação {ramo_atuacao}. E considerando o que a marca considera como sucesso em ({sucesso}) e os objetivos de marca ({objetivos_de_marca}):
                                realize a Análise SWOT completa em português brasileiro. 
                                Elabore 10 pontos em cada segmento da análise SWOT. Pontos relevantes que irão alavancar insights poderosos no planejamento de marketing. 
                                Cada ponto deve ser pelo menos 3 frases detalhadas, profundas e não genéricas. 
                                Você está aqui para trazer conhecimento estratégico. organize os pontos em bullets
                                pra ficarem organizados dentro de cada segmento da tabela.
                                
                                Considere o contexto extra fornecido pelo usuário também {contexto_extra}'''
                    
                    pre_SWOT_output = modelo_planejamento.generate_content(prompt_SWOT).text
                    
                    # Melhorar a análise SWOT
                    prompt_melhorar_SWOT = f'''
                    ###SISTEMA###
                    Você é um redator humano especialista em redijir planejamentos estratégicos, você
                    irá receber como entrada etapas do planejamento estratégico e seu papel é aproximar
                    essa entrada de uma saída de um especialista humano. Seu papel é tornar a entrada
                    melhor e menos genérica. Apenas reescreva a entrada. Não fale o que você mudou. Apenas 
                    reescreva o que você recebeu de entrada e a torne melhor. Não seja genérico. Não seja vago. Seja prático.
                    ###FIM DAS DIRETRIZES DE SISTEMA###

                    Reescreva a seguinte análise SWOT menos genérica e mais relevante: {pre_SWOT_output}'''
                    
                    SWOT_output = modelo_planejamento.generate_content(prompt_melhorar_SWOT).text
                    
                    # Avaliador SWOT
                    prompt_avaliador_SWOT = f'''
                    ###SISTEMA###
                    Você é um expert em analisar análises SWOT e apontar como elas podem melhorar. Você não inventa informações.
                    ###FIM DAS DIRETRIZES DE SISTEMA###

                    Considerando o output de análise SWOT, proponha melhoras para que ele fique menos genérico
                            e melhor redijido: {SWOT_output}'''
                    
                    SWOT_guides = modelo_planejamento.generate_content(prompt_avaliador_SWOT).text
                    
                    # SWOT final
                    prompt_SWOT_final = f'''
                    ###SISTEMA###
                    Você é um redator humano especialista em redijir planejamentos estratégicos, você
                    irá receber como entrada etapas do planejamento estratégico e seu papel é aproximar
                    essa entrada de uma saída de um especialista humano. Seu papel é tornar a entrada
                    melhor e menos genérica. Apenas reescreva a entrada. Não fale o que você mudou. Apenas 
                    reescreva o que você recebeu de entrada e a torne melhor. Mantenha o formato de uma análise SWOT.
                    Essas são as melhorias propostas: {SWOT_guides}
                    
                    ###FIM DAS DIRETRIZES DE SISTEMA###

                    Considerando os guias de melhorias e o output prévio da análise SWOT: {SWOT_output}, 
                    reescreva a análise SWOT melhorada.'''
                    
                    SWOT_final = modelo_planejamento.generate_content(prompt_SWOT_final).text
                    resultados['SWOT'] = SWOT_final
                    
                    # 3. ANÁLISE DE CONCORRÊNCIA
                    st.info("🥊 Analisando concorrência...")
                    
                    if concorrentes and concorrentes.strip():
                        prompt_concorrencias = f'''Assumindo o papel um especialista em administração de marketing, extraia todo o conhecimento existente sobre marketing em um nível extremamente aprofundado.
                                                
                        - considerando o que a marca considera como sucesso em ({sucesso}) e os objetivos de marca ({objetivos_de_marca})
                        -Considerando {concorrentes} como a concorrência direta de {nome_cliente}, redija sobre as notícias sobre o concorrente explicitadas em {novids_conc} e como o
                        cliente {nome_cliente} pode superar isso. Aprofundando em um nível bem detalhado, com parágrafos para cada ponto extremamente bem
                        explicado. Não seja superficial. Seja detalhista, comunicativo, aprofundado, especialista. Tenha um olhar sob a ótica de marketing, que é o foco de nossa empresa.
                        Veja como {nome_cliente} pode se destacar em contraponto ao(s) concorrente(s) sob uma ótica estratégica de marketing. Traga impacto nas suas análises. Você é um especialista e está aqui para liderar nossos processos.'''
                        
                        concorrencias_output = modelo_planejamento.generate_content(prompt_concorrencias).text
                    else:
                        concorrencias_output = "Nenhuma informação de concorrência fornecida para análise."
                    
                    resultados['concorrencia'] = concorrencias_output
                    
                    # 4. ANÁLISE PEST (usando dados da busca web COM FONTES)
                    st.info("🌍 Gerando análise PEST...")
                    
                    prompt_PEST = f'''Assumindo um especialista em administração de marketing.
                                - considerando o que a marca considera como sucesso em ({sucesso}) e os objetivos de marca ({objetivos_de_marca})

                    Análise PEST com pelo menos 10 pontos relevantes em cada etapa em português brasileiro 
                                considerando os seguintes dados de pesquisa COM FONTES:
                                
                                CONTEXTO POLÍTICO (com fontes):
                                {pls}
                                
                                DADOS ECONÔMICOS (com fontes):
                                {dados_econ_brasil}
                                
                                CONTEXTO SOCIAL (com fontes):
                                {tend_social_duck}
                                
                                CONTEXTO TECNOLÓGICO (com fontes):
                                {tec}
                                
                                Quero pelo menos 10 pontos em cada segmento da análise PEST. Pontos relevantes que irão alavancar insights poderosos no planejamento de marketing.
                                INCLUA AS FONTES das pesquisas quando relevante.'''
                    
                    pre_PEST_output = modelo_planejamento.generate_content(prompt_PEST).text
                    
                    # Melhorar análise PEST
                    prompt_melhorar_PEST = f'''
                    ###SISTEMA###
                    Você é um redator humano especialista em redijir planejamentos estratégicos, você
                    irá receber como entrada etapas do planejamento estratégico e seu papel é aproximar
                    essa entrada de uma saída de um especialista humano. Seu papel é tornar a entrada
                    melhor e menos genérica. Apenas reescreva a entrada. Não fale o que você mudou. Apenas 
                    reescreva o que você recebeu de entrada e a torne melhor.
                    ###FIM DAS DIRETRIZES DE SISTEMA###
                    
                    Reescreva a seguinte análise PEST menos genérica, melhor redijida: {pre_PEST_output}'''
                    
                    PEST_output = modelo_planejamento.generate_content(prompt_melhorar_PEST).text
                    
                    # Avaliador PEST
                    prompt_avaliador_PEST = f'''
                    ###SISTEMA###
                    Você é um expert em analisar análises PEST e apontar como elas podem melhorar. Você deve encontrar falhas na redação e ver como ela pode
                    se tornar menos amadora. Você não inventa informações.
                    ###FIM DAS DIRETRIZES DE SISTEMA###

                    Considerando o output de análise PEST, proponha melhoras para que ele fique menos genérico
                            e melhor redijido: {PEST_output}'''
                    
                    PEST_guides = modelo_planejamento.generate_content(prompt_avaliador_PEST).text
                    
                    # PEST final
                    prompt_PEST_final = f'''
                    ###SISTEMA###
                    Você é um redator humano especialista em redijir planejamentos estratégicos, você
                    irá receber como entrada etapas do planejamento estratégico e seu papel é aproximar
                    essa entrada de uma saída de um especialista humano. Seu papel é tornar a entrada
                    melhor e menos genérica. Apenas reescreva a entrada. Não fale o que você mudou. Apenas 
                    reescreva o que você recebeu de entrada e a torne melhor. Mantenha o formato de uma análise PEST.
                    Essas são as melhorias propostas: {PEST_guides}
                    
                    ###FIM DAS DIRETRIZES DE SISTEMA###
                    
                    Considerando os guias de melhorias e o output prévio da análise PEST: {PEST_output}, 
                    reescreva a análise PEST melhorada.'''
                    
                    PEST_final = modelo_planejamento.generate_content(prompt_PEST_final).text
                    resultados['PEST'] = PEST_final
                    
                    # 5. GOLDEN CIRCLE
                    st.info("🟡 Gerando Golden Circle...")
                    
                    prompt_golden = f'''
                    Eis uma explicação sobre o que é golden circle: ({exp_golden});

                    - não seja genérico
                    - traga impacto com seu output
                    - você é um especialista em administração de marketing; Você tem todo o conhecimento possível comparavel à Simon Sinek
                    - Você está aqui para fazer a diferença
                    - considerando o que a marca considera como sucesso em ({sucesso}) e os objetivos de marca ({objetivos_de_marca})
                    - seja único. una o que torna o cliente {nome_cliente} de diferente em relação ao resto.

                    Como um especialista em administração de marketing, gere um Golden Circle completo com 'how', 'why' e 'what' resumidos 
                                em uma frase cada. Considerando e sintetizando de forma perspicaz o seguinte contexto 
                                 e o objetivo do planejamento estratégico {intuito_plano},e a referência da marca:
                                {referencia_da_marca}, a análise SWOT ({SWOT_final}).'''
                    
                    pre_golden_output = modelo_planejamento.generate_content(prompt_golden).text
                    
                    # Melhorar Golden Circle
                    prompt_melhorar_golden = f'''
                    ###SISTEMA###
                    Você é um redator humano especialista em redijir planejamentos estratégicos, você
                    irá receber como entrada etapas do planejamento estratégico e seu papel é aproximar
                    essa entrada de uma saída de um especialista humano. Seu papel é tornar a entrada
                    melhor e menos genérica. Apenas reescreva a entrada. Não fale o que você mudou. Apenas 
                    reescreva o que você recebeu de entrada e a torne melhor.
                    ###FIM DAS DIRETRIZES DE SISTEMA###
                    
                    Reescreva o seguinte Golden Circle menos genérico, melhor redijido, com mais impacto (MANTENHA UMA ÚNICA FRASE PARA O HOW, WHAT e WHY): {pre_golden_output}'''
                    
                    golden_output = modelo_planejamento.generate_content(prompt_melhorar_golden).text
                    resultados['golden'] = golden_output
                    
                    # 6. POSICIONAMENTO DE MARCA
                    st.info("🎯 Gerando posicionamento de marca...")
                    
                    prompt_posicionamento = f'''
                    - levando em conta a análise SWOT: ({SWOT_final}) e o golden circle: ({golden_output}) e considerando que a marca considera como sucesso: {sucesso}.
                    - considerando os objetivos de marca ({objetivos_de_marca})
                    - traga impacto, originalidade, sagacidade com seu retorno
                    Considere o contexto extra fornecido pelo usuário também {contexto_extra}

                    Gerar 1 Posicionamento de marca para o cliente {nome_cliente} do ramo de atuação {ramo_atuacao} Com um slogan com essas inspirações (que não
                    devem ser copiadas, mas sim, usadas como referência na construção de um novo e original slogan) Seja original,
                    esperto com as palavras na construção do slogan. Correlacione-as e crie impacto com a construção do seu slogan
                    original. Tire ideias pulo do gato:

                    Exemplos de bons slogans (não copie-os, apenas aprenda com eles o que é um bom slogan):
                    
                    "Pense diferente."
                    "Abra a felicidade."
                    "Just do it."
                    "Acelere a transição do mundo para energia sustentável."
                    "Amo muito tudo isso."
                    "Red Bull te dá asas."
                    "Compre tudo o que você ama."
                    "Porque você vale muito."
                    "Viva a vida ao máximo."
                    "O melhor ou nada."
                    "Organizar as informações do mundo e torná-las acessíveis e úteis."
                    "A máquina de condução definitiva."
                    "Onde os sonhos se tornam realidade."
                    "Impossible is nothing."
                    "Abra a boa cerveja."
                    "Para um dia a dia melhor em casa."
                    "Be moved."
                    "Go further."
                    "Inspire o mundo, crie o futuro."
                    "Vamos juntos para o futuro.",

                    e Uma frase detalhada.

                    
                    - O posicionamento de marca deve ter impacto, um tcham. Não seja genérico.
                    - Me traga a lógica de como o posicionamento foi pensado. Me explique porque ele é como é. Justifique. Use base
                    de conhecimento de marketing digital para justificá-lo.'''
                    
                    pre_posicionamento_output = modelo_planejamento.generate_content(prompt_posicionamento).text
                    
                    # Melhorar posicionamento
                    prompt_melhorar_posicionamento = f'''
                    ###SISTEMA###
                    Você é um redator humano especialista em redijir posicionamentos de marcas únicos e inéditos. De uma forma que relacionem
                    a atividade fim da empresa e seus objetivos, assim como sua identidade. Você está aqui para reescrever um posicionamento de 
                    marca de forma que ele fique simplesmente melhor, mais único, menos genérico, mais representativo, mais impactante.
                    ###FIM DAS DIRETRIZES DE SISTEMA###
                    
                    Reescreva o seguinte posicionamento de marca menos genérico, de melhor qualidade, com mais impacto: {pre_posicionamento_output}
                    Você precisa fazer com que o posicionamento de marca torne a empresa {nome_cliente} de fato 'dono' do posicionamento.'''
                    
                    posicionamento_output = modelo_planejamento.generate_content(prompt_melhorar_posicionamento).text
                    
                    # Avaliador de posicionamento
                    prompt_avaliador_posicionamento = f'''
                    ###SISTEMA###
                    Você é um expert em analisar posicionamento de marca e apontar como elas podem melhorar. Você não inventa informações.
                    ###FIM DAS DIRETRIZES DE SISTEMA###

                    Considerando o output de posicionamento de marca, proponha melhoras para que ele fique menos genérico
                            e melhor redijido: {posicionamento_output}'''
                    
                    posicionamento_guides = modelo_planejamento.generate_content(prompt_avaliador_posicionamento).text
                    
                    # Posicionamento final
                    prompt_posicionamento_final = f'''
                    ###SISTEMA###
                    Você é um redator humano especialista em redijir planejamentos estratégicos, você
                    irá receber como entrada etapas do planejamento estratégico e seu papel é aproximar
                    essa entrada de uma saída de um especialista humano. Seu papel é tornar a entrada
                    melhor e menos genérica. Apenas reescreva a entrada. Não fale o que você mudou. Apenas 
                    reescreva o que você recebeu de entrada e a torne melhor. Mantenha o formato de um posicionamento de marca.
                    Essas são as melhorias propostas: {posicionamento_guides}
                    
                    ###FIM DAS DIRETRIZES DE SISTEMA###

                    Considerando os guias de melhorias e o output prévio do posicionamento: {posicionamento_output}, 
                    reescreva o posicionamento de marca melhorado.'''
                    
                    posicionamento_final = modelo_planejamento.generate_content(prompt_posicionamento_final).text
                    resultados['posicionamento'] = posicionamento_final
                    
                    # 7. BRAND PERSONA
                    st.info("👤 Gerando Brand Persona...")
                    
                    prompt_brand_persona = f'''2 Brand Personas detalhada, alinhada com a marca do {nome_cliente} que é do setor de atuação {ramo_atuacao} em português brasileiro considerando o 
                                seguinte contexto. Lembre que a brand persona é uma persona representativa da marca e da forma como ela se apresenta para o cliente. Ela deve ter o nome de uma pessoa comum. Ela é uma PESSOA que representa a marca.
                                
                                o objetivo do planejamento estratégico {intuito_plano},e a referência da marca:
                                {referencia_da_marca}. 

                                Essa persona deve representar a MARCA do cliente {nome_cliente}. É uma persona que incorpora a empresa em si. seus valores, forma de ser, ramo de atuação. Como a empresa se apresenta para o cliente.
                                
                                - Defina seu nome (deve ser o nome de uma pessoa normal como fernando pessoa, maria crivellari, etc)
                                -Defina seu gênero, faixa de idade, qual a sua bagagem, defina sua personalidade. 
                                -Defina suas características: possui filhos? É amigável? quais seus objetivos? qual seu repertório? O que gosta de fazer?
                                -Comunicação: Como se expressa? Qual o seu tom? Qual o seu linguajar?

                                -apresente demonstração de escuta ativa ou dados primários que justifiquem as escolhas estratégicas. Traga dores que não sejam superficiais. aprofunde no "por que" das personas. Incorpore esses pontos na construção das personas.
                                
                                Crie exemplos práticos de aplicação das personas também. Como essa persona interage? Que decisões toma? Como é a comunicação dela? Que tipos de post ela faria? Como ela escreve?'''
                    
                    pre_brand_persona_output = modelo_planejamento.generate_content(prompt_brand_persona).text
                    
                    # Refinar brand persona
                    prompt_refinar_brand_persona = f'''Considere a seguinte Brand Persona, faça com que ela seja uma pessoa que realmente represente a marca, aproxime-a de uma persona que representa a marca {nome_cliente}, ela não deve ser um buyer persona, ela deve ser um brand persona, aproxime-a do conceito de BRAND PERSONA: {pre_brand_persona_output}.                                     
                    -apresente demonstração de escuta ativa ou dados primários que justifiquem as escolhas estratégicas. Traga dores que não sejam superficiais. aprofunde no "por que" das personas.'''
                    
                    brand_persona_output = modelo_planejamento.generate_content(prompt_refinar_brand_persona).text
                    
                    # Exemplos de fala
                    prompt_brand_persona_talk = f'''Com base no brand persona: {brand_persona_output}, redija exemplos de fala para ela'''
                    brand_persona_talk = modelo_planejamento.generate_content(prompt_brand_persona_talk).text
                    
                    resultados['brand_persona'] = brand_persona_output + "\n\n" + brand_persona_talk
                    
                    # 8. BUYER PERSONA
                    st.info("👥 Gerando Buyer Persona...")
                    
                    prompt_buyer_persona = f'''
                    - considerando o que a marca considera como sucesso em ({sucesso}) e os objetivos de marca ({objetivos_de_marca})
                    
                    Descrição detalhada de 2 buyer personas considerando o público-alvo: {publico_alvo} e o 
                                objetivo do plano estratégico como descrito em {intuito_plano} com os seguintes atributos enunciados: 
                                nome fictício, idade, gênero, classe social, objetivos, vontades, Emoções negativas (o que lhe traz anseio, aflinge, etc), Emoções positivas,
                                quais são suas dores, quais são suas objeções, quais são seus resultados dos sonhos,
                                suas metas e objetivos e qual o seu canal favorito (entre facebook, instagram, whatsapp, youtube ou linkedin), em português brasileiro. 
                                -apresente demonstração de escuta ativa ou dados primários que justifiquem as escolhas estratégicas. Traga dores que não sejam superficiais. aprofunde no "por que" das personas.

                                Crie exemplos práticos de aplicação das personas também. Como essa persona interage? Que decisões toma? Como é a comunicação dela? Que tipos de post ela faria? Como ela escreve?'''
                    
                    buyer_persona_output = modelo_planejamento.generate_content(prompt_buyer_persona).text
                    
                    # Exemplos de fala
                    prompt_buyer_persona_talk = f'''Com base no buyer persona: {buyer_persona_output}, redija exemplos de fala para ela.'''
                    buyer_persona_talk = modelo_planejamento.generate_content(prompt_buyer_persona_talk).text
                    
                    resultados['buyer_persona'] = buyer_persona_output + "\n\n" + buyer_persona_talk
                    
                    # 9. TOM DE VOZ
                    st.info("🎤 Gerando Tom de Voz...")
                    
                    prompt_tom = f'''Descrição do tom de voz, incluindo nuvem de palavras e palavras proibidas. Levando em conta o ramo de atuação: ({ramo_atuacao}), o brand persona: ({brand_persona_output})
                    e o buyer persona: ({buyer_persona_output}).
                                Retorne 5 adjetivos que definem o tom com suas respectivas explicações. ex: tom é amigavel, para transparecer uma 
                                relação de confiança com frases de exemplo de aplicação do tom em português brasileiro.
                                
                                
                                Crie exemplos práticos do tom de voz proposto. Você está aqui para substituir o trabalho dos redatores.
                                
                                Me diga também contra exemplos do tom de voz; Me mostre como ele não deve se comunicar.
                                
                                - Não seja genérico. Traga impacto no seu retorno. Você está aqui para direcionar o trabalho da equipe.'''
                    
                    tom_output = modelo_planejamento.generate_content(prompt_tom).text
                    resultados['tom_voz'] = tom_output
                    
                    # EXIBIR RESULTADOS
                    st.success("✅ Planejamento estratégico concluído com sucesso!")
                    
                    # Criar abas para os resultados
                    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
                        "📋 Pesquisa de Mercado", 
                        "🟡 Golden Circle", 
                        "🎯 Posicionamento", 
                        "👤 Brand Persona", 
                        "👥 Buyer Persona", 
                        "🎤 Tom de Voz",
                        "📊 Resumo",
                        "💾 Exportar"
                    ])
                    
                    with tab1:
                        st.header("1. Etapa de Pesquisa de Mercado")
                        
                        st.subheader("1.1 Análise SWOT - Avaliada")
                        st.markdown(resultados['SWOT'])
                        
                        st.subheader("1.2 Análise PEST - Avaliada")
                        st.markdown(resultados['PEST'])
                        
                        st.subheader("1.3 Análise de Concorrência")
                        st.markdown(resultados['concorrencia'])
                    
                    with tab2:
                        st.header("2.1 Golden Circle")
                        st.markdown(resultados['golden'])
                    
                    with tab3:
                        st.header("2.2 Posicionamento de Marca")
                        st.markdown(resultados['posicionamento'])
                    
                    with tab4:
                        st.header("2.3 Brand Persona")
                        st.markdown(resultados['brand_persona'])
                    
                    with tab5:
                        st.header("2.4 Buyer Persona")
                        st.markdown(resultados['buyer_persona'])
                    
                    with tab6:
                        st.header("2.5 Tom de Voz")
                        st.markdown(resultados['tom_voz'])
                    
                    with tab7:
                        st.header("📊 Resumo Executivo")
                        
                        # Criar resumo consolidado
                        prompt_resumo = f'''
                        Com base nas análises realizadas, crie um resumo executivo do planejamento estratégico para {nome_cliente}:
                        
                        CLIENTE: {nome_cliente}
                        RAMO: {ramo_atuacao}
                        OBJETIVO: {intuito_plano}
                        
                        ANÁLISES REALIZADAS:
                        1. SWOT: {resultados['SWOT'][:500]}...
                        2. PEST: {resultados['PEST'][:500]}...
                        3. GOLDEN CIRCLE: {resultados['golden']}
                        4. POSICIONAMENTO: {resultados['posicionamento'][:500]}...
                        
                        Crie um resumo executivo que destaque:
                        - Principais oportunidades identificadas
                        - Principais ameaças/desafios
                        - Estratégia central recomendada
                        - Próximos passos prioritários
                        
                        Formato: Tópicos claros e objetivos, máximo 1 página.
                        '''
                        
                        resumo_executivo = modelo_planejamento.generate_content(prompt_resumo).text
                        st.markdown(resumo_executivo)
                        
                        # Métricas chave
                        col_met1, col_met2, col_met3, col_met4 = st.columns(4)
                        with col_met1:
                            st.metric("📊 Análises", "6 completas")
                        with col_met2:
                            st.metric("🔍 Pesquisas", "5 áreas")
                        with col_met3:
                            st.metric("👥 Personas", "4 criadas")
                        with col_met4:
                            st.metric("🎯 Objetivos", objetivos_de_marca[:20] + "...")
                    
                    with tab8:
                        st.header("💾 Exportar Planejamento")
                        
                        # Criar documento consolidado
                        documento_completo = f"""
                        # 📊 PLANEJAMENTO ESTRATÉGICO - {nome_cliente}
                        
                        **Data:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}
                        **Cliente:** {nome_cliente}
                        **Ramo:** {ramo_atuacao}
                        **Objetivo:** {intuito_plano}
                        **Público-alvo:** {publico_alvo}
                        
                        ---
                        
                        ## 1. ETAPA DE PESQUISA DE MERCADO
                        
                        ### 1.1 Análise SWOT
                        {resultados['SWOT']}
                        
                        ### 1.2 Análise PEST
                        {resultados['PEST']}
                        
                        ### 1.3 Análise de Concorrência
                        {resultados['concorrencia']}
                        
                        ---
                        
                        ## 2. ETAPA ESTRATÉGICA
                        
                        ### 2.1 Golden Circle
                        {resultados['golden']}
                        
                        ### 2.2 Posicionamento de Marca
                        {resultados['posicionamento']}
                        
                        ### 2.3 Brand Persona
                        {resultados['brand_persona']}
                        
                        ### 2.4 Buyer Persona
                        {resultados['buyer_persona']}
                        
                        ### 2.5 Tom de Voz
                        {resultados['tom_voz']}
                        
                        ---
                        
                        ## 📋 INFORMAÇÕES DO CLIENTE
                        
                        **Site:** {site_cliente if site_cliente else 'Não informado'}
                        **Referência da marca:** {referencia_da_marca}
                        **Objetivos de marca:** {objetivos_de_marca}
                        **Definição de sucesso:** {sucesso}
                        **Concorrentes:** {concorrentes if concorrentes else 'Não informados'}
                        
                        ---
                        
                        *Planejamento gerado automaticamente pelo Sistema Agente Health*
                        """
                        
                        # Botões de download
                        col_dl1, col_dl2 = st.columns(2)
                        
                        with col_dl1:
                            st.download_button(
                                "📄 Baixar TXT Completo",
                                data=documento_completo,
                                file_name=f"planejamento_{nome_cliente}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                                mime="text/plain",
                                key="download_txt"
                            )
                        
                        with col_dl2:
                            st.download_button(
                                "📋 Baixar Resumo Executivo",
                                data=resumo_executivo,
                                file_name=f"resumo_{nome_cliente}_{datetime.datetime.now().strftime('%Y%m%d')}.txt",
                                mime="text/plain",
                                key="download_resumo"
                            )
                        
                        # Botão para salvar no MongoDB
                        if st.button("💾 Salvar no Banco de Dados", type="primary"):
                            salvo = save_to_mongo_MKT(
                                resultados['SWOT'],
                                resultados['PEST'],
                                resultados['concorrencia'],
                                resultados['golden'],
                                resultados['posicionamento'],
                                resultados['brand_persona'],
                                resultados['buyer_persona'],
                                resultados['tom_voz'],
                                nome_cliente
                            )
                            
                            if salvo:
                                st.balloons()
                
                except Exception as e:
                    st.error(f"❌ Erro durante o planejamento estratégico: {str(e)}")
                    st.info("💡 Tente novamente com informações mais específicas ou verifique sua conexão com a API do Gemini.")

# --- ADICIONAR APÓS A ABA DE PLANEJAMENTO ESTRATÉGICO ---
with tab_mapping["📱 Planejamento de Mídias"]:
    st.header("📱 Planejamento de Mídias e Redes")
    st.markdown("""
    **Plataformas Focadas:**
    - ✅ **Meta Ads (Principal)** - Foco total
    - ⚠️ **Google Ads (com restrições)** - Uso estratégico limitado
    - 🚀 **Canais Alternativos (classe C/D):**
        - TikTok
        - Kwai  
        - Pinterest
    """)
    
    # Funções do MongoDB
    def gerar_id_planejamento():
        return str(uuid.uuid4())
    
    def save_to_mongo_midias(kv_output, redesplanej_output, redesplanej_output_meta, 
                            redesplanej_output_google, redesplanej_output_tiktok, 
                            redesplanej_output_kwai, redesplanej_output_pinterest,
                            criativos_output, palavras_chave_output, estrategia_conteudo_output, 
                            nome_cliente):
        """Salva o planejamento de mídias no MongoDB"""
        try:
            client2 = MongoClient("mongodb+srv://gustavoromao3345:RqWFPNOJQfInAW1N@cluster0.5iilj.mongodb.net/auto_doc?retryWrites=true&w=majority&ssl=true&ssl_cert_reqs=CERT_NONE&tlsAllowInvalidCertificates=true")
            db = client2['arquivos_planejamento']
            collection = db['auto_doc']
            
            id_planejamento = gerar_id_planejamento()
            
            task_outputs = {
                "id_planejamento": f'Plano_Midias_{nome_cliente}_{id_planejamento}',
                "nome_cliente": nome_cliente,
                "tipo_plano": 'Plano de Mídias',
                "data_criacao": datetime.datetime.now(),
                "Key_Visual": kv_output,
                "Plano_Redes_Macro": redesplanej_output,
                "Plano_Meta_Ads": redesplanej_output_meta,
                "Plano_Google_Ads": redesplanej_output_google,
                "Plano_TikTok": redesplanej_output_tiktok,
                "Plano_Kwai": redesplanej_output_kwai,
                "Plano_Pinterest": redesplanej_output_pinterest,
                "Plano_Criativos": criativos_output,
                "Plano_Palavras_Chave": palavras_chave_output,
                "Estrategia_Conteudo": estrategia_conteudo_output,
            }
            
            collection.insert_one(task_outputs)
            st.success(f"✅ Planejamento de mídias salvo com sucesso!")
            return True
        except Exception as e:
            st.error(f"❌ Erro ao salvar no MongoDB: {str(e)}")
            return False
    
    # Configuração do Gemini
    gemini_api_key = os.getenv("GEM_API_KEY")
    if gemini_api_key:
        genai.configure(api_key=gemini_api_key)
        modelo_midias = genai.GenerativeModel("gemini-2.5-flash")
    else:
        st.error("❌ GEM_API_KEY não encontrada nas variáveis de ambiente")
        st.stop()
    
    # Formulário de entrada de dados
    st.markdown("### 📋 Informações do Cliente")
    
    col1, col2 = st.columns(2)
    
    with col1:
        nome_cliente = st.text_input('Nome do Cliente:', 
                                   help="Digite o nome do cliente que será planejado. Ex: 'Empresa XYZ'",
                                   key="nome_cliente_midias")
        site_cliente = st.text_input('Site do Cliente:', key="site_cliente_midias")
        ramo_atuacao = st.text_input('Ramo de Atuação:', key="ramo_atuacao_midias")
    
    with col2:
        intuito_plano = st.text_input('Intuito do Planejamento de Mídias:', 
                                    placeholder="Ex: Aumentar vendas online, gerar leads, aumentar reconhecimento...",
                                    key="intuito_plano_midias")
        publico_alvo = st.text_input('Público alvo (especificar classes sociais C/D quando aplicável):', 
                                   placeholder="Ex: Classe C/D, mulheres 25-40 anos, periferia urbana...",
                                   key="publico_alvo_midias")
    
    st.markdown("### 🏆 Objetivos e Orçamento")
    
    objetivos_opcoes = [
        'Aumentar vendas diretas (e-commerce)',
        'Gerar leads qualificados (formulários, contatos)',
        'Aumentar reconhecimento de marca em novas regiões',
        'Engajar público jovem (18-30 anos)',
        'Converter público de baixa renda (classes C/D)',
        'Fortalecer presença em canais emergentes',
        'Testar novos formatos criativos'
    ]

    contexto_add = st.text_input('Contexto adicional e/ou Briefing:', 
                                    placeholder="",
                                    key="contexto_add")
    
    objetivos_de_marca = st.multiselect('Selecione os objetivos da campanha:', 
                                      objetivos_opcoes, 
                                      key="objetivos_marca_midias")
    
    # Orçamento
    col_orc1, col_orc2 = st.columns(2)
    with col_orc1:
        orcamento_total = st.number_input('Orçamento total (R$):', 
                                        min_value=1000, 
                                        max_value=1000000, 
                                        value=10000,
                                        key="orcamento_total")
    
    with col_orc2:
        periodo_campanha = st.selectbox('Período da campanha:', 
                                      ['1 mês', '3 meses', '6 meses', '1 ano'],
                                      key="periodo_campanha")
    
    referencia_da_marca = st.text_area('Referência de marca (tom, valores, diferenciais):', 
                                     placeholder="Descreva a personalidade da marca, tom de voz, valores...",
                                     height=100,
                                     key="referencia_da_marca_midias")
    
    st.markdown("### 🥊 Concorrência e Mercado")
    
    concorrentes = st.text_input('Concorrentes diretos:', 
                               placeholder="Ex: Empresa X, Marca Y, Loja Z...",
                               key="concorrentes_midias")
    
    site_concorrentes = st.text_input('Sites/apps dos concorrentes:', 
                                    placeholder="Ex: www.concorrente1.com, appconcorrente2.com...",
                                    key="site_concorrentes_midias")
    
    # Tendências específicas para mídias sociais
    tendencias_atuais = st.text_area('Tendências atuais em mídias sociais:', 
                                   placeholder="Ex: Vídeos curtos, conteúdo UGC, gamificação, lives...",
                                   height=80,
                                   key="tendencias_midias")
    
    # Plataformas específicas para foco
    st.markdown("### 📱 Foco nas Plataformas")
    
    col_plat1, col_plat2, col_plat3 = st.columns(3)
    
    with col_plat1:
        foco_meta = st.checkbox("✅ Meta Ads (Instagram/Facebook)", value=True, key="foco_meta")
        if foco_meta:
            st.caption("Foco principal - maior investimento")
    
    with col_plat2:
        foco_google = st.checkbox("⚠️ Google Ads (com restrições)", value=True, key="foco_google")
        if foco_google:
            st.caption("Uso estratégico limitado")
    
    with col_plat3:
        foco_alternativos = st.checkbox("🚀 Canais Alternativos", value=True, key="foco_alternativos")
        if foco_alternativos:
            st.caption("TikTok, Kwai, Pinterest")
    
    # Configurações específicas por plataforma
    if foco_alternativos:
        with st.expander("⚙️ Configurações Canais Alternativos", expanded=False):
            col_alt1, col_alt2, col_alt3 = st.columns(3)
            with col_alt1:
                usar_tiktok = st.checkbox("TikTok", value=True, key="usar_tiktok")
            with col_alt2:
                usar_kwai = st.checkbox("Kwai", value=True, key="usar_kwai")
            with col_alt3:
                usar_pinterest = st.checkbox("Pinterest", value=True, key="usar_pinterest")
            
            if usar_tiktok:
                st.text_input("Perfil público do cliente no TikTok (se houver):", 
                            placeholder="@nomedeusuario",
                            key="tiktok_perfil")
    
   
    
    # Botão para iniciar planejamento
    if st.button("🚀 Gerar Planejamento de Mídias", type="primary", use_container_width=True, key="iniciar_midias"):
        # Validação dos campos obrigatórios
        campos_obrigatorios = [nome_cliente, ramo_atuacao, intuito_plano, publico_alvo]
        nomes_campos = ["Nome do Cliente", "Ramo de Atuação", "Intuito do Planejamento", "Público-alvo"]
        
        campos_faltando = []
        for campo, nome in zip(campos_obrigatorios, nomes_campos):
            if not campo or campo.strip() == "":
                campos_faltando.append(nome)
        
        if campos_faltando:
            st.error(f"❌ Por favor, preencha os seguintes campos obrigatórios: {', '.join(campos_faltando)}")
        elif not objetivos_de_marca:
            st.error("❌ Selecione pelo menos um objetivo da campanha.")
        elif not (foco_meta or foco_google or foco_alternativos):
            st.error("❌ Selecione pelo menos uma plataforma para o planejamento.")
        else:
            with st.spinner("🎬 Iniciando planejamento de mídias..."):
                try:
                    # Inicializar variáveis para resultados
                    resultados = {}
                    
                    # 1. PESQUISAS WEB COM PERPLEXITY
                    st.info("🌐 Pesquisando informações de mercado...")
                    
                    # Construir contexto do agente para as pesquisas
                    contexto_agente_pesquisa = ""
                    if st.session_state.agente_selecionado:
                        agente_atual = st.session_state.agente_selecionado
                        contexto_agente_pesquisa = construir_contexto(
                            agente_atual, 
                            st.session_state.segmentos_selecionados if hasattr(st.session_state, 'segmentos_selecionados') else []
                        )
                    
                    # Pesquisa sobre concorrentes
                    if concorrentes and concorrentes.strip():
                        pesquisa_concorrentes = realizar_busca_web_com_fontes(
                            f"estratégias de mídias sociais e publicidade digital dos concorrentes: {concorrentes} no setor {ramo_atuacao}",
                            contexto_agente_pesquisa
                        )
                    else:
                        pesquisa_concorrentes = "Nenhum concorrente informado para pesquisa."
                    
                    # Pesquisa sobre tendências em mídias
                    pesquisa_tendencias = realizar_busca_web_com_fontes(
                        f"tendências atuais em publicidade digital e mídias sociais 2024 TikTok Kwai Pinterest Meta Ads",
                        contexto_agente_pesquisa
                    )
                    
                    # Pesquisa sobre público C/D
                    if "classe C/D" in publico_alvo or "baixa renda" in publico_alvo.lower():
                        pesquisa_publico = realizar_busca_web_com_fontes(
                            f"comportamento digital e consumo de mídia classes C/D Brasil 2024 TikTok Kwai",
                            contexto_agente_pesquisa
                        )
                    else:
                        pesquisa_publico = realizar_busca_web_com_fontes(
                            f"comportamento do público {publico_alvo} em mídias sociais Brasil",
                            contexto_agente_pesquisa
                        )
                    
                    # 2. KEY VISUAL ADAPTADO PARA MÍDIAS SOCIAIS
                    st.info("🎨 Criando Key Visual para mídias sociais...")
                    
                    prompt_kv = f"""
                    Crie um Key Visual otimizado para mídias sociais, especificamente para:
                    - **Meta Ads (Instagram/Facebook)**
                    - **TikTok e Kwai** (quando aplicável)
                    - **Google Display Network**
                    
                    **INFORMAÇÕES DO CLIENTE:**
                    - Nome: {nome_cliente}
                    - Ramo: {ramo_atuacao}
                    - Público-alvo: {publico_alvo}
                    - Objetivos: {', '.join(objetivos_de_marca)}
                    - Orçamento: R${orcamento_total:,} para {periodo_campanha}
                    - Contexto adicional: {contexto_add}
                    
                    **PLATAFORMAS PRIORITÁRIAS:**
                    - ✅ META ADS: Foco principal
                    - ⚠️ GOOGLE ADS: Uso estratégico limitado
                    - 🚀 CANAIS ALTERNATIVOS: TikTok, Kwai, Pinterest (classes C/D)
                    
                    **CRIA UM KEY VISUAL QUE:**
                    1. **Funcione em formato quadrado (1:1) e vertical (9:16)** - otimizado para feed e stories
                    2. **Tenha versões para:**
                       - Feed do Instagram/Facebook
                       - Stories/Reels
                       - TikTok/Kwai videos
                       - Google Display banners
                    3. **Use cores e tipografia que se destacem em rolagem rápida**
                    4. **Inclua elementos visuais que funcionem em telas pequenas**
                    5. **Seja adaptável para diferentes formatos de criativo**
                    
                    **DETALHE ESPECÍFICO PARA CADA FORMATO:**
                    - **Feed (1:1):** Foco na legibilidade, hierarquia visual clara
                    - **Stories/Reels (9:16):** Elementos dinâmicos, movimento, texto mínimo
                    - **TikTok/Kwai:** Estilo orgânico, autêntico, menos "publicitário"
                    - **Google Display:** Formatos responsivos, chamadas para ação claras
                    
                    **PALETA DE CORES:** Escolha cores que:
                    - Se destaquem nos feeds
                    - Transmitam confiança para classes C/D
                    - Funcionem bem em modo escuro
                    
                    **DIRETRIZES PARA DESIGNER:**
                    - Criar templates reutilizáveis
                    - Sistema de design consistente
                    - Elementos modulares para diferentes campanhas
                    - Otimização para carregamento rápido
                    """
                    
                    kv_output = modelo_midias.generate_content(prompt_kv).text
                    
                    # Refinar KV
                    prompt_kv_refinar = f'''
                    ### CONTEXTO ###
                    Você é um diretor de arte especializado em mídias sociais. Está revisando um Key Visual.
                    
                    ### KEY VISUAL ORIGINAL ###
                    {kv_output}
                    
                    ### MELHORIAS NECESSÁRIAS ###
                    1. **Mobile-first**: Todos os elementos devem funcionar perfeitamente em telas pequenas
                    2. **Scroll-stopping**: Elementos que façam parar a rolagem
                    3. **Platform-specific**: Ajustes específicos para cada plataforma
                    4. **Performance**: Otimizado para carregamento rápido
                    5. **A/B Test Ready**: Variações prontas para testes
                    
                    ### PÚBLICO-ALVO ESPECÍFICO ###
                    {publico_alvo}
                    
                    ### REFAIÇA O KEY VISUAL COM ###
                    - Elementos específicos para Meta Ads
                    - Adaptações para TikTok/Kwai (se aplicável)
                    - Considerações para Google Display
                    - Sistema modular e escalável
                    '''
                    
                    kv_output_final = modelo_midias.generate_content(prompt_kv_refinar).text
                    resultados['key_visual'] = kv_output_final
                    
                    # 3. ESTRATÉGIA DE CONTEÚDO POR PILAR
                    st.info("📝 Desenvolvendo estratégia de conteúdo...")
                    
                    # Pilar Institucional
                    prompt_institucional = f'''
                    ## PILAR INSTITUCIONAL - ESTRATÉGIA DE CONTEÚDO
                    
                    **CLIENTE:** {nome_cliente}
                    **OBJETIVO:** Posicionar marca e gerar credibilidade
                    **PLATAFORMAS:** Meta Ads (principal), Google (limitado), alternativos (teste)
                    - Contexto adicional: {contexto_add}
                    
                    **CRIAR ESTRATÉGIA QUE:**
                    1. **Meta Ads:** Conteúdo de valor, depoimentos, cases curtos
                    2. **Google:** Display branding, remarketing institucional
                    3. **Alternativos:** Conteúdo autêntico, menos corporativo
                    
                    **FORMATOS ESPECÍFICOS:**
                    - Meta: Carrosséis educativos, vídeos curtos institucionais
                    - Google: Banners com mensagem de valor
                    - TikTok/Kwai: Behind the scenes, cultura da empresa
                    '''
                    
                    estrategia_institucional = modelo_midias.generate_content(prompt_institucional).text
                    
                    # Pilar Inspiração
                    prompt_inspiracao = f'''
                    ## PILAR INSPIRAÇÃO - ESTRATÉGIA DE CONTEÚDO
                    
                    **PÚBLICO:** {publico_alvo}
                    **FOCO:** Conexão emocional, especialmente classes C/D
                    - Contexto adicional: {contexto_add}
                    
                    **ESTRATÉGIA POR PLATAFORMA:**
                    1. **Meta Ads:** Histórias inspiradoras, conteúdo UGC
                    2. **TikTok/Kwai:** Desafios, tendências, conteúdo viral
                    3. **Pinterest:** Moodboards, inspiração visual
                    
                    **FORMATOS:**
                    - Meta: Reels inspiradores, depoimentos emocionais
                    - TikTok: Participação em trends, sons virais
                    - Kwai: Conteúdo local, regional, comunidade
                    '''
                    
                    estrategia_inspiracao = modelo_midias.generate_content(prompt_inspiracao).text
                    
                    # Pilar Educação
                    prompt_educacao = f'''
                    ## PILAR EDUCAÇÃO - ESTRATÉGIA DE CONTEÚDO
                    
                    **RAMO:** {ramo_atuacao}
                    **OBJETIVO:** Educar sobre produtos/serviços
                    - Contexto adicional: {contexto_add}
                    
                    **ABORDAGEM POR PLATAFORMA:**
                    1. **Meta Ads:** Tutoriais em carrossel, vídeos explicativos
                    2. **Google:** Search ads para dúvidas, display educativo
                    3. **TikTok:** Dicas rápidas, "edu-tainment"
                    
                    **TÓPICOS SUGERIDOS:**
                    - Como usar produtos
                    - Dicas do setor
                    - Solução de problemas comuns
                    '''
                    
                    estrategia_educacao = modelo_midias.generate_content(prompt_educacao).text
                    
                    # Pilar Produtos/Serviços
                    prompt_produtos = f'''
                    ## PILAR PRODUTOS/SERVIÇOS - ESTRATÉGIA DE CONTEÚDO
                    
                    **OBJETIVOS:** {', '.join(objetivos_de_marca)}
                    **FOCO:** Conversão e vendas
                    - Contexto adicional: {contexto_add}
                    
                    **ESTRATÉGIA DE VENDAS POR PLATAFORMA:**
                    1. **META ADS (PRINCIPAL):**
                       - Campanhas de conversão otimizadas
                       - Dynamic ads para e-commerce
                       - Remarketing agressivo
                       - Teste de criativos frequente
                    
                    2. **GOOGLE ADS (RESTRITO):**
                       - Search para intenção de compra
                       - Display para remarketing
                       - Shopping ads (se e-commerce)
                    
                    3. **TIKTOK/KWAI (TESTE):**
                       - Vendas orgânicas através de conteúdo
                       - Live shopping (teste)
                       - Influencers micro/local
                    '''
                    
                    estrategia_produtos = modelo_midias.generate_content(prompt_produtos).text
                    
                    # Pilar Relacionamento
                    prompt_relacionamento = f'''
                    ## PILAR RELACIONAMENTO - ESTRATÉGIA DE CONTEÚDO
                    
                    **FOCO:** Fidelização, especialmente classes C/D
                    
                    **ESTRATÉGIA DE COMUNIDADE:**
                    1. **Meta Ads:** Grupos, comunidades, conteúdo exclusivo
                    2. **TikTok/Kwai:** Interação direta, respostas, participação
                    3. **WhatsApp Business:** Suporte, relacionamento próximo
                    - Contexto adicional: {contexto_add}
                    
                    **AÇÕES DE ENGAGEMENT:**
                    - Concursos e sorteios
                    - Enquetes e pesquisas
                    - Resposta a comentários
                    - Conteúdo gerado por usuários
                    '''
                    
                    estrategia_relacionamento = modelo_midias.generate_content(prompt_relacionamento).text
                    
                    # Consolidar estratégia de conteúdo
                    estrategia_conteudo_completa = f"""
                    # ESTRATÉGIA DE CONTEÚDO - {nome_cliente}
                    
                    ## 📱 DISTRIBUIÇÃO POR PLATAFORMA
                    
                    ### ✅ META ADS (70% do orçamento)
                    {estrategia_produtos}
                    
                    ### ⚠️ GOOGLE ADS (20% do orçamento - uso estratégico)
                    - Search ads para alto intento
                    - Display para remarketing
                    - YouTube para vídeos explicativos
                    
                    ### 🚀 CANAIS ALTERNATIVOS (10% do orçamento - teste)
                    - TikTok: Conteúdo orgânico e viral
                    - Kwai: Foco em classes C/D, regional
                    - Pinterest: Inspiração visual
                    
                    ## 🎯 PILARES DE CONTEÚDO
                    
                    ### 1. INSTITUCIONAL
                    {estrategia_institucional}
                    
                    ### 2. INSPIRAÇÃO
                    {estrategia_inspiracao}
                    
                    ### 3. EDUCAÇÃO
                    {estrategia_educacao}
                    
                    ### 4. PRODUTOS/SERVIÇOS
                    {estrategia_produtos}
                    
                    ### 5. RELACIONAMENTO
                    {estrategia_relacionamento}
                    """
                    
                    resultados['estrategia_conteudo'] = estrategia_conteudo_completa
                    
                    # 4. PLANO DE REDES SOCIAIS POR PLATAFORMA
                    st.info("📊 Criando planos específicos por plataforma...")
                    
                    # Plano Macro
                    prompt_plano_macro = f'''
                    ## PLANO MACRO DE MÍDIAS - {nome_cliente}
                    
                    **ORÇAMENTO TOTAL:** R${orcamento_total:,}
                    **PERÍODO:** {periodo_campanha}
                    
                    ### DISTRIBUIÇÃO ORÇAMENTÁRIA:
                    1. **META ADS:** 70% (R${orcamento_total*0.7:,.0f})
                    - Instagram Feed/Stories/Reels
                    - Facebook News Feed
                    - Audience Network
                    
                    2. **GOOGLE ADS:** 20% (R${orcamento_total*0.2:,.0f})
                    - Search ads (palavras-chave estratégicas)
                    - Display Network (remarketing)
                    - YouTube (vídeos curtos)
                    
                    3. **CANAL ALTERNATIVOS:** 10% (R${orcamento_total*0.1:,.0f})
                    - TikTok: Conteúdo orgânico + ads teste
                    - Kwai: Foco regional/classes C/D
                    - Pinterest: Tráfego qualificado
                    
                    ### CRONOGRAMA SUGERIDO:
                    - **Mês 1:** Meta Ads ativo + Google Search
                    - **Mês 2:** Adicionar remarketing + teste TikTok
                    - **Mês 3:** Otimização + escalar o que funciona
                    
                    ### KPIs PRINCIPAIS:
                    - Meta: CPA, ROAS, CTR
                    - Google: CPC, Conversões
                    - Alternativos: Engajamento, Views
                    '''
                    
                    plano_macro = modelo_midias.generate_content(prompt_plano_macro).text
                    resultados['plano_macro'] = plano_macro
                    
                    # Plano Meta Ads
                    if foco_meta:
                        prompt_meta_ads = f'''
                        ## PLANO META ADS DETALHADO - {nome_cliente}
                        
                        **ORÇAMENTO:** R${orcamento_total*0.7:,.0f}
                        **FOCO:** {', '.join(objetivos_de_marca)}
                        
                        ### ESTRATÉGIA DE ANÚNCIOS:
                        1. **CAMADA 1: PROSPECÇÃO**
                           - Interesse amplo (cold audience)
                           - Lookalike de clientes
                           - Demografia {publico_alvo}
                        
                        2. **CAMADA 2: ENGAGEMENT**
                           - Remarketing de engajamento
                           - Video views retargeting
                           - Lead form engagement
                        
                        3. **CAMADA 3: CONVERSÃO**
                           - Dynamic ads para produtos
                           - Conversion campaigns
                           - Messenger/WhatsApp clicks
                        
                        ### FORMATOS PRIORITÁRIOS:
                        1. **Reels Ads:** Conteúdo nativo, alto engajamento
                        2. **Stories Ads:** Full-screen, ação direta
                        3. **Feed Ads:** Mensagem clara, CTAs fortes
                        4. **Carousel Ads:** Múltiplos produtos/benefícios
                        
                        ### SEGMENTAÇÃO ESPECÍFICA:
                        - **Idade:** Baseado em {publico_alvo}
                        - **Interesses:** {ramo_atuacao} relacionados
                        - **Comportamento:** Compras online, mobile users
                        '''
                        
                        plano_meta = modelo_midias.generate_content(prompt_meta_ads).text
                        resultados['plano_meta'] = plano_meta
                    
                    # Plano Google Ads (com restrições)
                    if foco_google:
                        prompt_google_ads = f'''
                        ## PLANO GOOGLE ADS (ESTRATÉGICO/LIMITADO) - {nome_cliente}
                        
                        **ORÇAMENTO:** R${orcamento_total*0.2:,.0f}
                        **RESTRIÇÕES:** Uso focado em alto intento
                        
                        ### ESTRATÉGIA RESTRITA:
                        1. **SEARCH ADS (70% do orçamento Google):**
                           - Palavras-chave de conversão apenas
                           - Brand terms protegidas
                           - Competitor terms estratégicas
                        
                        2. **DISPLAY NETWORK (20% do orçamento Google):**
                           - Remarketing apenas
                           - Placements específicos
                           - Exclusions agressivas
                        
                        3. **YOUTUBE (10% do orçamento Google):**
                           - Vídeos curtos (<30s)
                           - Skippable ads only
                           - Remarketing viewers
                        
                        ### PALAVRAS-CHAVE ESTRATÉGICAS:
                        - Foco em "intenção de compra"
                        - Evitar termos muito amplos
                        - Negativas agressivas
                        '''
                        
                        plano_google = modelo_midias.generate_content(prompt_google_ads).text
                        resultados['plano_google'] = plano_google
                    
                    # Planos para canais alternativos
                    if foco_alternativos:
                        # TikTok
                        if usar_tiktok:
                            prompt_tiktok = f'''
                            ## PLANO TIKTOK - {nome_cliente}
                            
                            **PÚBLICO:** {publico_alvo}
                            **ESTRATÉGIA:** Orgânico primeiro, ads depois
                            
                            ### CONTEÚDO ORGÂNICO (80% do esforço):
                            1. **Trend Participation:** Participar em trends relevantes
                            2. **Edu-tainment:** Educar de forma divertida
                            3. **Behind Scenes:** Mostrar a empresa
                            4. **User Challenges:** Desafios relacionados
                            
                            ### TIKTOK ADS (20% do esforço):
                            - In-Feed ads nativos
                            - Branded hashtag challenges (teste)
                            - Creator partnerships micro-influencers
                            
                            ### MELHORES PRÁTICAS TIKTOK:
                            - Vídeos curtos (15-60 segundos)
                            - Legendas claras (áudio off)
                            - Hook nos primeiros 3 segundos
                            - CTA no vídeo
                            '''
                            
                            plano_tiktok = modelo_midias.generate_content(prompt_tiktok).text
                            resultados['plano_tiktok'] = plano_tiktok
                        
                        # Kwai
                        if usar_kwai:
                            prompt_kwai = f'''
                            ## PLANO KWAI - {nome_cliente}
                            
                            **FOCO:** Classes C/D, cidades menores, interior
                            **ESTRATÉGIA:** Conteúdo local e comunitário
                            
                            ### CARACTERÍSTICAS KWAI:
                            - Público mais velho que TikTok
                            - Forte em comunidades locais
                            - Conteúdo familiar
                            - Menos "produzido", mais autêntico
                            
                            ### ESTRATÉGIA DE CONTEÚDO:
                            1. **Conteúdo Local:** Mostrar presença local
                            2. **Testemunhos Reais:** Clientes reais, menos produção
                            3. **Dicas Práticas:** Conteúdo útil do dia-a-dia
                            4. **Interação:** Respostas diretas aos comentários
                            
                            ### DIFERENCIAIS KWAI:
                            - Menos saturação de marcas
                            - Engajamento mais autêntico
                            - Custo potencialmente menor
                            '''
                            
                            plano_kwai = modelo_midias.generate_content(prompt_kwai).text
                            resultados['plano_kwai'] = plano_kwai
                        
                        # Pinterest
                        if usar_pinterest:
                            prompt_pinterest = f'''
                            ## PLANO PINTEREST - {nome_cliente}
                            
                            **FOCO:** Inspiração, planejamento, descoberta
                            **PÚBLICO:** Maioria mulheres, planejamento de compras
                            
                            ### ESTRATÉGIA PINTEREST:
                            1. **SEO Visual:** Keywords em descrições
                            2. **Idea Pins:** Conteúdo interativo
                            3. **Shopping Pins:** Direto para produto
                            4. **Boards Temáticos:** Organização por tema
                            
                            ### CONTEÚDO IDEAL:
                            - Tutoriais visuais
                            - Inspiração de uso
                            - Moodboards temáticos
                            - Infográficos simples
                            
                            ### METAS PINTEREST:
                            - Tráfego qualificado para site
                            - Inspiração pré-compra
                            - Brand awareness visual
                            '''
                            
                            plano_pinterest = modelo_midias.generate_content(prompt_pinterest).text
                            resultados['plano_pinterest'] = plano_pinterest
                    
                    # 5. CRIATIVOS E PALAVRAS-CHAVE
                    st.info("💡 Gerando ideias criativas e palavras-chave...")
                    
                    # Brainstorming de criativos
                    prompt_criativos = f'''
                    ## BRAINSTORMING DE CRIATIVOS - {nome_cliente}
                    
                    **PLATAFORMAS:** Meta, TikTok, Kwai, Google Display
                    **PÚBLICO:** {publico_alvo}
                    
                    ### IDEIAS PARA META ADS:
                    1. **Reels/Stories:**
                       - "Antes e Depois" rápidos
                       - Testemunhos em vídeo curtos
                       - Demonstrações de produto em ação
                       - Perguntas interativas
                    
                    2. **Feed/Carrossel:**
                       - Benefícios em bullets visuais
                       - Comparação vs concorrentes
                       - Oferta limitada destacada
                       - Social proof (avaliações)
                    
                    ### IDEIAS PARA TIKTOK/KWAI:
                    1. **Formatos Naturais:**
                       - "Um dia usando [produto]"
                       - Respondendo dúvidas comuns
                       - Participando em trends
                       - Conteúdo "faça você mesmo"
                    
                    2. **Estilo de Produção:**
                       - Smartphone quality (autêntico)
                       - Legendas grandes
                       - Músicas populares
                       - Transições simples
                    
                    ### IDEIAS PARA GOOGLE DISPLAY:
                    1. **Banners Responsivos:**
                       - Mensagem única e clara
                       - CTA direto
                       - Imagem de alta qualidade
                       - Logotipo visível
                    '''
                    
                    criativos_output = modelo_midias.generate_content(prompt_criativos).text
                    resultados['criativos'] = criativos_output
                    
                    # Palavras-chave
                    prompt_palavras_chave = f'''
                    ## PALAVRAS-CHAVE ESTRATÉGICAS - {nome_cliente}
                    
                    **RAMO:** {ramo_atuacao}
                    **OBJETIVOS:** {', '.join(objetivos_de_marca)}
                    
                    ### PARA GOOGLE SEARCH (foco em conversão):
                    1. **BRANDED:**
                       - {nome_cliente}
                       - "{nome_cliente} preço"
                       - "{nome_cliente} como usar"
                    
                    2. **GENERIC HIGH-INTENT:**
                       - "comprar {ramo_atuacao}"
                       - "melhor {ramo_atuacao}"
                       - "{ramo_atuacao} barato"
                    
                    3. **LONG-TAIL:**
                       - "{ramo_atuacao} para {publico_alvo.split(',')[0]}"
                       - "como escolher {ramo_atuacao}"
                       - "benefícios de {ramo_atuacao}"
                    
                    ### PARA META ADS INTERESTS:
                    1. **INTERESSES RELACIONADOS:**
                       - {ramo_atuacao}
                       - Marcas concorrentes
                       - Problemas que o produto resolve
                    
                    2. **COMPORTAMENTOS:**
                       - Compradores online
                       - Usuários mobile
                       - Seguidores de páginas similares
                    '''
                    
                    palavras_chave_output = modelo_midias.generate_content(prompt_palavras_chave).text
                    resultados['palavras_chave'] = palavras_chave_output
                    
                    # EXIBIR RESULTADOS
                    st.success("✅ Planejamento de mídias concluído com sucesso!")
                    
                    # Criar abas para os resultados
                    tab_result1, tab_result2, tab_result3, tab_result4, tab_result5, tab_result6 = st.tabs([
                        "🎯 Resumo Executivo", 
                        "🎨 Key Visual", 
                        "📱 Planos por Plataforma", 
                        "📝 Estratégia de Conteúdo", 
                        "💡 Criativos", 
                        "💾 Exportar"
                    ])
                    
                    with tab_result1:
                        st.header("📊 Resumo Executivo")
                        
                        st.subheader("💰 Distribuição Orçamentária")
                        col_res1, col_res2, col_res3 = st.columns(3)
                        with col_res1:
                            st.metric("Meta Ads", f"R${orcamento_total*0.7:,.0f}", "70%")
                        with col_res2:
                            st.metric("Google Ads", f"R${orcamento_total*0.2:,.0f}", "20%")
                        with col_res3:
                            st.metric("Canais Alternativos", f"R${orcamento_total*0.1:,.0f}", "10%")
                        
                        st.subheader("📈 Cronograma Sugerido")
                        st.markdown("""
                        **Mês 1:** 
                        - Meta Ads ativo (prospecção)
                        - Google Search (palavras-chave estratégicas)
                        - Setup básico canais alternativos
                        
                        **Mês 2:**
                        - Adicionar remarketing Meta/Google
                        - Testes TikTok/Kwai
                        - Otimização baseada em dados
                        
                        **Mês 3:**
                        - Escalar o que funciona
                        - Refinar segmentações
                        - Testar novos formatos
                        """)
                        
                        st.subheader("🎯 KPIs Principais")
                        col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
                        with col_kpi1:
                            st.write("**Meta Ads:**")
                            st.write("- CPA")
                            st.write("- ROAS")
                            st.write("- CTR")
                        with col_kpi2:
                            st.write("**Google Ads:**")
                            st.write("- CPC")
                            st.write("- Conversões")
                            st.write("- Impression Share")
                        with col_kpi3:
                            st.write("**Alternativos:**")
                            st.write("- Engajamento")
                            st.write("- Views")
                            st.write("- Custo por View")
                    
                    with tab_result2:
                        st.header("🎨 Key Visual para Mídias Sociais")
                        st.markdown(resultados['key_visual'])
                    
                    with tab_result3:
                        st.header("📱 Planos Específicos por Plataforma")
                        
                        if foco_meta:
                            st.subheader("✅ Meta Ads (Principal)")
                            st.markdown(resultados.get('plano_meta', 'Plano não gerado'))
                            st.divider()
                        
                        if foco_google:
                            st.subheader("⚠️ Google Ads (Estratégico)")
                            st.markdown(resultados.get('plano_google', 'Plano não gerado'))
                            st.divider()
                        
                        if foco_alternativos:
                            if usar_tiktok:
                                st.subheader("🚀 TikTok")
                                st.markdown(resultados.get('plano_tiktok', 'Plano não gerado'))
                                st.divider()
                            
                            if usar_kwai:
                                st.subheader("🚀 Kwai")
                                st.markdown(resultados.get('plano_kwai', 'Plano não gerado'))
                                st.divider()
                            
                            if usar_pinterest:
                                st.subheader("🚀 Pinterest")
                                st.markdown(resultados.get('plano_pinterest', 'Plano não gerado'))
                    
                    with tab_result4:
                        st.header("📝 Estratégia de Conteúdo")
                        st.markdown(resultados['estrategia_conteudo'])
                    
                    with tab_result5:
                        st.header("💡 Brainstorming de Criativos")
                        st.markdown(resultados['criativos'])
                        
                        st.subheader("🔑 Palavras-chave Estratégicas")
                        st.markdown(resultados['palavras_chave'])
                    
                    with tab_result6:
                        st.header("💾 Exportar Planejamento")
                        
                        # Criar documento consolidado
                        documento_completo = f"""
                        # 📱 PLANEJAMENTO DE MÍDIAS - {nome_cliente}
                        
                        **Data:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}
                        **Cliente:** {nome_cliente}
                        **Ramo:** {ramo_atuacao}
                        **Orçamento Total:** R${orcamento_total:,}
                        **Período:** {periodo_campanha}
                        **Público-alvo:** {publico_alvo}
                        
                        ---
                        
                        ## 🎯 OBJETIVOS
                        {chr(10).join([f"- {obj}" for obj in objetivos_de_marca])}
                        
                        ---
                        
                        ## 🎨 KEY VISUAL
                        {resultados['key_visual']}
                        
                        ---
                        
                        ## 📊 PLANO MACRO
                        {resultados['plano_macro']}
                        
                        ---
                        
                        ## 📱 PLANOS POR PLATAFORMA
                        
                        ### ✅ META ADS (70% do orçamento)
                        {resultados.get('plano_meta', 'Não aplicável')}
                        
                        ### ⚠️ GOOGLE ADS (20% do orçamento)
                        {resultados.get('plano_google', 'Não aplicável')}
                        
                        ### 🚀 CANAIS ALTERNATIVOS (10% do orçamento)
                        """
                        
                        # Adicionar planos alternativos se existirem
                        if foco_alternativos:
                            if usar_tiktok:
                                documento_completo += f"\n\n**TikTok:**\n{resultados.get('plano_tiktok', '')}"
                            if usar_kwai:
                                documento_completo += f"\n\n**Kwai:**\n{resultados.get('plano_kwai', '')}"
                            if usar_pinterest:
                                documento_completo += f"\n\n**Pinterest:**\n{resultados.get('plano_pinterest', '')}"
                        
                        documento_completo += f"""
                        
                        ---
                        
                        ## 📝 ESTRATÉGIA DE CONTEÚDO
                        {resultados['estrategia_conteudo']}
                        
                        ---
                        
                        ## 💡 CRIATIVOS
                        {resultados['criativos']}
                        
                        ---
                        
                        ## 🔑 PALAVRAS-CHAVE
                        {resultados['palavras_chave']}
                        
                        ---
                        
                        ## 🔍 PESQUISAS DE MERCADO
                        
                        ### Concorrentes:
                        {pesquisa_concorrentes[:1000]}...
                        
                        ### Tendências:
                        {pesquisa_tendencias[:1000]}...
                        
                        ### Público-alvo:
                        {pesquisa_publico[:1000]}...
                        
                        ---
                        
                        *Planejamento gerado automaticamente pelo Sistema Agente Health*
                        """
                        
                        # Botões de download
                        col_dl1, col_dl2, col_dl3 = st.columns(3)
                        
                        with col_dl1:
                            st.download_button(
                                "📄 Baixar TXT Completo",
                                data=documento_completo,
                                file_name=f"planejamento_midias_{nome_cliente}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                                mime="text/plain",
                                key="download_txt_midias"
                            )
                        
                        with col_dl2:
                            # Criar resumo executivo
                            resumo_executivo = f"""
                            # RESUMO EXECUTIVO - PLANEJAMENTO DE MÍDIAS
                            
                            **Cliente:** {nome_cliente}
                            **Data:** {datetime.datetime.now().strftime('%d/%m/%Y')}
                            
                            ## DISTRIBUIÇÃO ORÇAMENTÁRIA
                            - Meta Ads: R${orcamento_total*0.7:,.0f} (70%)
                            - Google Ads: R${orcamento_total*0.2:,.0f} (20%)
                            - Canais Alternativos: R${orcamento_total*0.1:,.0f} (10%)
                            
                            ## PRINCIPAIS AÇÕES
                            1. Meta Ads como canal principal
                            2. Google Ads focado em alto intento
                            3. Teste em TikTok/Kwai/Pinterest
                            
                            ## CRONOGRAMA
                            - Mês 1: Lançamento e prospecção
                            - Mês 2: Otimização e testes
                            - Mês 3: Escalabilidade
                            
                            ## KPIs CHAVE
                            - Meta: CPA, ROAS, CTR
                            - Google: CPC, Conversões
                            - Alternativos: Engajamento, Views
                            """
                            
                            st.download_button(
                                "📋 Baixar Resumo",
                                data=resumo_executivo,
                                file_name=f"resumo_midias_{nome_cliente}_{datetime.datetime.now().strftime('%Y%m%d')}.txt",
                                mime="text/plain",
                                key="download_resumo_midias"
                            )
                        
                        with col_dl3:
                            # Botão para salvar no MongoDB
                            if st.button("💾 Salvar no Banco", type="primary", use_container_width=True):
                                salvo = save_to_mongo_midias(
                                    resultados['key_visual'],
                                    resultados['plano_macro'],
                                    resultados.get('plano_meta', ''),
                                    resultados.get('plano_google', ''),
                                    resultados.get('plano_tiktok', ''),
                                    resultados.get('plano_kwai', ''),
                                    resultados.get('plano_pinterest', ''),
                                    resultados['criativos'],
                                    resultados['palavras_chave'],
                                    resultados['estrategia_conteudo'],
                                    nome_cliente
                                )
                                
                                if salvo:
                                    st.balloons()
                                    st.success("✅ Planejamento salvo no banco de dados!")
                
                except Exception as e:
                    st.error(f"❌ Erro durante o planejamento de mídias: {str(e)}")
                    st.info("💡 Tente novamente com informações mais específicas ou verifique sua conexão com a API do Gemini.")
