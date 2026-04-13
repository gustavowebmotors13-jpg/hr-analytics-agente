# =============================================================
#  AGENTE ANALÍTICO DE HR — Webmotors
#  Acesso por senha única compartilhada com o time de RH
#
#  Instalação:
#    pip install -r requirements.txt
#
#  Rodar local:
#    streamlit run app.py
#
#  Secrets necessários no Streamlit Cloud:
#    ANTHROPIC_API_KEY = "sk-ant-..."
#    APP_PASSWORD_HASH = "hash_md5_da_sua_senha"
#
#  Para gerar o hash da senha (rode no terminal):
#    python -c "import hashlib; print(hashlib.md5('SUA_SENHA'.encode()).hexdigest())"
# =============================================================

import os
import hashlib
import pandas as pd
import anthropic
import streamlit as st
from pathlib import Path
from datetime import datetime

# ── CONFIGURAÇÕES ─────────────────────────────────────────────
st.set_page_config(
    page_title="HR Analytics · Webmotors",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

MODEL = "claude-sonnet-4-20250514"

# Caminho do parquet — ajuste se necessário
# Parquet lido direto do repositório GitHub (arquivo privado)
PARQUET_URL = (
    "https://raw.githubusercontent.com/gustavowebmotors13-jpg/"
    "hr-analytics-agente/main/Colaboradores.parquet"
)

# Hash da senha — lido do Streamlit Secrets (ou variável de ambiente local)
# Fallback "demo123" apenas para testes locais — remova antes de produção
APP_PASSWORD_HASH = st.secrets.get(
    "APP_PASSWORD_HASH",
    hashlib.md5("demo123".encode()).hexdigest()
)

ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))

# ── CORREÇÕES MANUAIS DE DADOS ────────────────────────────────
# Regras aplicadas após a extração da API, antes de salvar o parquet.
# Quando a API for corrigida, basta remover a linha correspondente.
# Para adicionar novos casos: inclua uma nova linha no dicionário.
#
# Formato:
#   "CARGO EXATO EM MAIÚSCULO": "TIPO DE CONTRATAÇÃO CORRETO"

CORRECOES_TIPO_CONTRATACAO = {
    "ESTAGIARIO WM J6 (W)": "ESTÁGIO",
    # "APRENDIZ XYZ":        "JOVEM APRENDIZ",   ← exemplo de como adicionar
}

def aplicar_correcoes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Corrige o TipoContratacao com base no Cargo,
    para casos em que a API retorna valores incorretos.
    Registra no log quantas linhas foram corrigidas por regra.
    """
    col_cargo = "Cargo"
    col_tipo  = "TipoContratacao"

    if col_cargo not in df.columns or col_tipo not in df.columns:
        return df

    total_corrigidos = 0
    for cargo, tipo_correto in CORRECOES_TIPO_CONTRATACAO.items():
        mascara = df[col_cargo].str.upper().str.strip() == cargo.upper()
        n = mascara.sum()
        if n > 0:
            df.loc[mascara, col_tipo] = tipo_correto
            print(f"  [Correção] '{cargo}' → TipoContratacao = '{tipo_correto}' ({n} registro{'s' if n > 1 else ''})")
            total_corrigidos += n

    if total_corrigidos == 0:
        print("  [Correção] Nenhuma correção necessária.")
    else:
        print(f"  [Correção] Total corrigido: {total_corrigidos} registro(s)")

    return df


# ── CARREGAMENTO DOS DADOS ────────────────────────────────────
@st.cache_data(ttl=3600)  # Recarrega automaticamente a cada 1h
def carregar_dados() -> pd.DataFrame:
    import requests, io
    token = st.secrets.get("GITHUB_TOKEN", "")
    headers = {"Authorization": f"token {token}"} if token else {}
    r = requests.get(PARQUET_URL, headers=headers, timeout=60)
    r.raise_for_status()
    return pd.read_parquet(io.BytesIO(r.content))

# ── FERRAMENTAS DO AGENTE ─────────────────────────────────────
def obter_schema(df: pd.DataFrame) -> str:
    linhas = []
    for col in df.columns:
        dtype    = str(df[col].dtype)
        exemplos = df[col].dropna().unique()[:3]
        ex_str   = ", ".join(str(e) for e in exemplos)
        linhas.append(f"  {col} ({dtype}): ex. {ex_str}")

    ativos   = len(df[df["Status"] == "ATIVO"])   if "Status" in df.columns else "?"
    inativos = len(df[df["Status"] == "INATIVO"]) if "Status" in df.columns else "?"

    return (
        f"Total de registros: {len(df)}\n"
        f"Ativos: {ativos} | Inativos: {inativos}\n\n"
        f"Colunas disponíveis:\n" + "\n".join(linhas)
    )

def executar_pandas(codigo: str, df: pd.DataFrame) -> str:
    try:
        local_vars = {"df": df, "pd": pd}
        exec(codigo, {}, local_vars)
        resultado = local_vars.get("resultado", "Código executado sem variável 'resultado'.")
        if isinstance(resultado, pd.DataFrame):
            return resultado.to_string(index=False, max_rows=50)
        elif isinstance(resultado, pd.Series):
            return resultado.to_string(max_rows=50)
        return str(resultado)
    except Exception as e:
        return f"ERRO: {e}"

SYSTEM_PROMPT = """Você é um assistente especializado em análise de dados de RH da Webmotors.
Você tem acesso aos dados de colaboradores ativos e inativos da Webmotors, CAR10 e LOOP.

Suas regras:
1. Sempre consulte o schema antes de escrever qualquer código de consulta.
2. Responda sempre em português brasileiro, de forma clara e objetiva.
3. Contextualize os números quando relevante (ex: percentuais, comparações).
4. Nunca invente dados — se não souber, diga claramente.
5. Para filtros de texto, use .str.upper() para garantir o match correto.
6. Sempre salve o resultado final na variável 'resultado'.
7. Seja conciso e direto, sem respostas longas demais.
"""

FERRAMENTAS = [
    {
        "name": "obter_schema",
        "description": (
            "Retorna o schema completo do dataframe: colunas, tipos e exemplos. "
            "Use SEMPRE como primeiro passo antes de qualquer consulta."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "executar_pandas",
        "description": (
            "Executa código Python/pandas no dataframe 'df'. "
            "Salve o resultado na variável 'resultado'. "
            "Use .str.upper() para filtros de texto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "codigo": {
                    "type": "string",
                    "description": "Código Python/pandas válido com o resultado em 'resultado'."
                }
            },
            "required": ["codigo"]
        }
    }
]

def rodar_agente(pergunta: str, historico: list, df: pd.DataFrame) -> str:
    client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    mensagens = historico + [{"role": "user", "content": pergunta}]

    while True:
        resposta = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=FERRAMENTAS,
            messages=mensagens
        )

        if resposta.stop_reason == "end_turn":
            for bloco in resposta.content:
                if hasattr(bloco, "text"):
                    return bloco.text
            return "(sem resposta)"

        if resposta.stop_reason == "tool_use":
            mensagens.append({"role": "assistant", "content": resposta.content})
            resultados = []
            for bloco in resposta.content:
                if bloco.type == "tool_use":
                    if bloco.name == "obter_schema":
                        res = obter_schema(df)
                    elif bloco.name == "executar_pandas":
                        res = executar_pandas(bloco.input.get("codigo", ""), df)
                    else:
                        res = "Ferramenta não encontrada."
                    resultados.append({
                        "type": "tool_result",
                        "tool_use_id": bloco.id,
                        "content": res
                    })
            mensagens.append({"role": "user", "content": resultados})
        else:
            break

    return "O agente não conseguiu completar a análise."

# ── TELA DE LOGIN ─────────────────────────────────────────────
def tela_login():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap');
    * { box-sizing: border-box; }
    section[data-testid="stMain"] { background: #0d0d0f !important; min-height: 100vh; }
    section[data-testid="stMain"] > div > div { padding-top: 0 !important; }
    .wm-grid { position: fixed; inset: 0; background-image: linear-gradient(rgba(230,57,70,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(230,57,70,0.04) 1px, transparent 1px); background-size: 40px 40px; pointer-events: none; z-index: 0; }
    .wm-glow1 { position: fixed; width: 400px; height: 400px; background: radial-gradient(circle, rgba(230,57,70,0.12) 0%, transparent 70%); bottom: -100px; left: -80px; pointer-events: none; z-index: 0; }
    .wm-glow2 { position: fixed; width: 250px; height: 250px; background: radial-gradient(circle, rgba(230,57,70,0.07) 0%, transparent 70%); top: -50px; right: 20px; pointer-events: none; z-index: 0; }
    .wm-wrap { display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 24px; position: relative; z-index: 2; }
    .wm-card { width: 100%; max-width: 420px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.07); border-radius: 20px; padding: 36px 32px 28px; }
    .wm-topbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
    .wm-logo { display: flex; align-items: center; gap: 10px; }
    .wm-logo-icon { width: 34px; height: 34px; background: rgba(230,57,70,0.15); border: 1px solid rgba(230,57,70,0.3); border-radius: 9px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
    .wm-logo-name { font-size: 16px; font-weight: 800; color: white; letter-spacing: 1px; text-transform: uppercase; font-family: 'Poppins', sans-serif; }
    .wm-status { display: flex; align-items: center; gap: 5px; font-family: 'Space Mono', monospace; font-size: 10px; color: rgba(255,255,255,0.25); text-transform: uppercase; }
    .wm-dot { width: 6px; height: 6px; background: #22c55e; border-radius: 50%; animation: wmpulse 2s infinite; display: inline-block; }
    @keyframes wmpulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
    .wm-divider { height: 1px; background: linear-gradient(90deg, transparent, rgba(230,57,70,0.4), transparent); margin-bottom: 24px; }
    .wm-tag { display: inline-flex; align-items: center; gap: 6px; background: rgba(230,57,70,0.1); border: 1px solid rgba(230,57,70,0.2); border-radius: 6px; padding: 4px 10px; font-size: 10px; font-weight: 600; color: #E63946; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 12px; font-family: 'Poppins', sans-serif; }
    .wm-title { font-size: 24px; font-weight: 800; color: white; letter-spacing: -0.5px; line-height: 1.15; margin-bottom: 4px; text-transform: uppercase; font-family: 'Poppins', sans-serif; }
    .wm-title span { color: #E63946; }
    .wm-subtitle { font-size: 10px; font-weight: 500; color: rgba(255,255,255,0.35); margin-bottom: 28px; letter-spacing: 0.8px; text-transform: uppercase; font-family: 'Poppins', sans-serif; }
    .wm-label { font-size: 9px; font-weight: 600; color: rgba(255,255,255,0.3); letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 8px; font-family: 'Poppins', sans-serif; }
    .wm-input-wrap { margin-bottom: 12px; }
    .wm-footer { margin-top: 20px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.05); }
    .wm-footer-l1 { font-size: 9px; font-weight: 600; color: rgba(255,255,255,0.22); text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 2px; font-family: 'Poppins', sans-serif; }
    .wm-footer-l2 { font-size: 9px; color: rgba(230,57,70,0.45); text-transform: uppercase; letter-spacing: 0.5px; font-family: 'Poppins', sans-serif; }
    div[data-testid="stTextInput"] input { background: rgba(255,255,255,0.05) !important; border: 1px solid rgba(255,255,255,0.08) !important; border-radius: 10px !important; color: white !important; font-family: 'Poppins', sans-serif !important; letter-spacing: 2px !important; }
    div[data-testid="stTextInput"] input:focus { border-color: rgba(230,57,70,0.5) !important; background: rgba(230,57,70,0.04) !important; }
    div[data-testid="stTextInput"] label { color: rgba(255,255,255,0.3) !important; font-family: 'Poppins', sans-serif !important; font-size: 9px !important; font-weight: 600 !important; letter-spacing: 1.5px !important; text-transform: uppercase !important; }
    div[data-testid="stButton"] button { background: rgba(255,255,255,0.06) !important; border: 1px solid rgba(255,255,255,0.1) !important; border-radius: 10px !important; color: rgba(255,255,255,0.35) !important; font-family: 'Poppins', sans-serif !important; font-size: 11px !important; font-weight: 700 !important; letter-spacing: 1.5px !important; text-transform: uppercase !important; padding: 10px !important; transition: all 0.3s !important; width: 100% !important; }
    div[data-testid="stButton"] button:hover { background: #E63946 !important; border-color: #E63946 !important; color: white !important; }
    div[data-testid="stAlert"] { border-radius: 8px !important; font-size: 12px !important; }
    </style>
    <div class="wm-grid"></div>
    <div class="wm-glow1"></div>
    <div class="wm-glow2"></div>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        st.markdown('''
        <div class="wm-card">
            <div class="wm-topbar">
                <div class="wm-logo">
                    <div class="wm-logo-icon">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#E63946" stroke-width="2.5" stroke-linecap="round">
                            <line x1="18" y1="20" x2="18" y2="10"/>
                            <line x1="12" y1="20" x2="12" y2="4"/>
                            <line x1="6" y1="20" x2="6" y2="14"/>
                        </svg>
                    </div>
                    <span class="wm-logo-name">Webmotors</span>
                </div>
                <div class="wm-status">
                    <span class="wm-dot"></span>
                    Sistema Ativo
                </div>
            </div>
            <div class="wm-divider"></div>
            <div class="wm-tag">
                <svg width="7" height="7" viewBox="0 0 8 8"><rect width="8" height="8" rx="2" fill="#E63946"/></svg>
                HR Analytics
            </div>
            <div class="wm-title">Pessoas<br>&amp; <span>Cultura</span></div>
            <div class="wm-subtitle">Dados de Ativos &amp; Inativos — Senior</div>
        </div>
        ''', unsafe_allow_html=True)

        senha = st.text_input("Senha de Acesso", type="password", placeholder="••••••••••")

        if st.button("Acessar Plataforma →", use_container_width=True):
            if hashlib.md5(senha.encode()).hexdigest() == APP_PASSWORD_HASH:
                st.session_state["autenticado"] = True
                st.session_state["historico"]   = []
                st.session_state["mensagens"]   = []
                st.rerun()
            else:
                st.error("Senha incorreta.")

        st.markdown('''
        <div class="wm-footer">
            <div class="wm-footer-l1">HR Analytics &amp; Operations | Webmotors SA</div>
            <div class="wm-footer-l2">Owner: Gustavo Pereira das Neves</div>
        </div>
        ''', unsafe_allow_html=True)


def tela_chat(df: pd.DataFrame):

    # SIDEBAR ─────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
        section[data-testid="stSidebar"] {
            background: #0d0d0f !important;
            border-right: 1px solid rgba(255,255,255,0.06) !important;
        }
        section[data-testid="stSidebar"] * { font-family: 'Poppins', sans-serif !important; color: white !important; }
        section[data-testid="stSidebar"] .stButton button {
            background: rgba(255,255,255,0.04) !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            border-radius: 8px !important;
            color: rgba(255,255,255,0.6) !important;
            font-size: 11px !important;
            font-weight: 500 !important;
            text-align: left !important;
            padding: 8px 12px !important;
            transition: all 0.2s !important;
        }
        section[data-testid="stSidebar"] .stButton button:hover {
            background: rgba(230,57,70,0.12) !important;
            border-color: rgba(230,57,70,0.3) !important;
            color: white !important;
        }
        .sb-logo { display:flex; align-items:center; gap:8px; padding:4px 0 16px; }
        .sb-logo-icon { width:30px; height:30px; background:rgba(230,57,70,0.15); border:1px solid rgba(230,57,70,0.3); border-radius:8px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
        .sb-logo-name { font-size:15px; font-weight:800; letter-spacing:0.8px; text-transform:uppercase; }
        .sb-divider { height:1px; background:linear-gradient(90deg,transparent,rgba(230,57,70,0.3),transparent); margin:12px 0; }
        .sb-section { font-size:9px; font-weight:700; letter-spacing:2px; text-transform:uppercase; color:rgba(255,255,255,0.25) !important; margin:16px 0 8px; }
        .sb-stat { background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); border-radius:8px; padding:10px 12px; margin-bottom:8px; }
        .sb-stat-label { font-size:9px; font-weight:600; letter-spacing:1px; text-transform:uppercase; color:rgba(255,255,255,0.3) !important; margin-bottom:2px; }
        .sb-stat-value { font-size:18px; font-weight:800; color:white !important; }
        .sb-stat-sub { font-size:10px; color:rgba(255,255,255,0.3) !important; }
        </style>
        """, unsafe_allow_html=True)

        total = len(df)
        ativos = len(df[df["Status"] == "ATIVO"]) if "Status" in df.columns else 0
        ultima = datetime.now().strftime("%d/%m %H:%M")

        st.markdown(f"""
        <div class="sb-logo">
            <div class="sb-logo-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#E63946" stroke-width="2.5" stroke-linecap="round">
                    <line x1="18" y1="20" x2="18" y2="10"/>
                    <line x1="12" y1="20" x2="12" y2="4"/>
                    <line x1="6" y1="20" x2="6" y2="14"/>
                </svg>
            </div>
            <span class="sb-logo-name">Webmotors</span>
        </div>
        <div class="sb-divider"></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:4px">
            <div class="sb-stat">
                <div class="sb-stat-label">Ativos</div>
                <div class="sb-stat-value">{ativos:,}</div>
            </div>
            <div class="sb-stat">
                <div class="sb-stat-label">Total</div>
                <div class="sb-stat-value">{total:,}</div>
            </div>
        </div>
        <div class="sb-stat" style="margin-bottom:0">
            <div class="sb-stat-label">Última extração</div>
            <div class="sb-stat-sub">{ultima}</div>
        </div>
        <div class="sb-divider"></div>
        <div class="sb-section">Sugestões</div>
        """, unsafe_allow_html=True)

        exemplos = [
            "Headcount total por empresa",
            "Quantos ativos temos hoje?",
            "Distribuição por gênero",
            "Top 5 áreas com mais pessoas",
            "Contratados este mês",
            "Colaboradores afastados",
            "Headcount por tipo de contrato",
            "Tempo de casa médio",
        ]
        for ex in exemplos:
            if st.button(ex, use_container_width=True, key=f"ex_{ex[:25]}"):
                st.session_state["pergunta_rapida"] = ex

        st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("↺ Nova conversa", use_container_width=True):
                st.session_state["historico"]  = []
                st.session_state["mensagens"]  = []
                st.rerun()
        with col2:
            if st.button("→ Sair", use_container_width=True):
                st.session_state.clear()
                st.rerun()

    # ÁREA PRINCIPAL ──────────────────────────────────────────
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
    section[data-testid="stMain"] { background: #0f0f11 !important; }
    section[data-testid="stMain"] * { font-family: 'Poppins', sans-serif !important; }
    .main-header { margin-bottom: 24px; }
    .main-title { font-size: 22px; font-weight: 800; color: white; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
    .main-title span { color: #E63946; }
    .main-sub { font-size: 11px; color: rgba(255,255,255,0.3); letter-spacing: 0.8px; text-transform: uppercase; }
    div[data-testid="stChatMessage"] {
        background: rgba(255,255,255,0.03) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 12px !important;
        margin-bottom: 12px !important;
        color: white !important;
    }
    div[data-testid="stChatInput"] textarea {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 12px !important;
        color: white !important;
        font-family: 'Poppins', sans-serif !important;
        font-size: 13px !important;
    }
    div[data-testid="stChatInput"] textarea:focus {
        border-color: rgba(230,57,70,0.4) !important;
    }
    </style>
    <div class="main-header">
        <div class="main-title">Pessoas &amp; <span>Cultura</span></div>
        <div class="main-sub">Faça perguntas sobre os dados de colaboradores</div>
    </div>
    """, unsafe_allow_html=True)

    # Renderiza histórico
    for msg in st.session_state.get("mensagens", []):
        avatar = "🧑" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # Captura pergunta digitada ou clicada na sidebar
    pergunta_rapida = st.session_state.pop("pergunta_rapida", None)
    pergunta = st.chat_input("Ex: Qual o headcount da CAR10 por área?") or pergunta_rapida

    if pergunta:
        st.session_state["mensagens"].append({"role": "user", "content": pergunta})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(pergunta)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Analisando dados..."):
                resposta = rodar_agente(
                    pergunta  = pergunta,
                    historico = st.session_state.get("historico", []),
                    df        = df
                )
            st.markdown(resposta)

        st.session_state["mensagens"].append({"role": "assistant", "content": resposta})
        st.session_state["historico"].append({"role": "user",      "content": pergunta})
        st.session_state["historico"].append({"role": "assistant", "content": resposta})

        # Mantém apenas as últimas 10 trocas para não estourar o contexto
        if len(st.session_state["historico"]) > 20:
            st.session_state["historico"] = st.session_state["historico"][-20:]

# ── MAIN ──────────────────────────────────────────────────────
def main():
    if not st.session_state.get("autenticado"):
        tela_login()
        return

    try:
        df = carregar_dados()
    except Exception as e:
        st.error(f"Erro ao carregar os dados: {e}")
        st.info("Verifique se o link do SharePoint está correto e acessível.")
        return

    tela_chat(df)

if __name__ == "__main__":
    main()
