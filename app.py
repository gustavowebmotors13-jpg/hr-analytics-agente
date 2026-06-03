# =============================================================
#  AGENTE ANALÍTICO DE HR — Webmotors
#  Backend: Google Gemini 1.5 Flash / Groq
#  Auth:    Microsoft Entra ID (SSO corporativo) via st.login()
# =============================================================

import os
import time
import pandas as pd
import streamlit as st
from datetime import datetime
from groq import Groq

# ── CONFIGURAÇÕES DA PÁGINA ───────────────────────────────────
st.set_page_config(
    page_title="HR Analytics · Webmotors",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Domínio corporativo permitido
DOMINIO_PERMITIDO = "webmotors.com.br"

# 🔄 SOLUÇÃO DO 404: Leitura direta dos arquivos locais clonados pelo Streamlit Cloud
PARQUET_FILE = "Headcount_Consolidado.parquet"
HP_PARQUET_FILE = "HighPerformance_Consolidado.parquet"

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))

# ── UTILITÁRIOS DE DATA / FY ──────────────────────────────────
def mes_para_fy(data: pd.Timestamp) -> str:
    if pd.isnull(data): return "OTHERS"
    ano_fy = data.year + 1 if data.month >= 7 else data.year
    return f"FY{str(ano_fy)[-2:]}"

def proximo_5_dia_util() -> str:
    """Calcula o 5º dia útil do próximo mês (considerando feriados nacionais)."""
    import holidays
    from datetime import date, timedelta
    hoje = date.today()
    if hoje.month == 12:
        primeiro = date(hoje.year + 1, 1, 1)
    else:
        primeiro = date(hoje.year, hoje.month + 1, 1)
    feriados = holidays.Brazil(years=primeiro.year)
    count = 0
    d = primeiro
    while True:
        if d.weekday() < 5 and d not in feriados:
            count += 1
            if count == 5:
                return d.strftime("%d/%m/%Y")
        d += timedelta(days=1)

# ── CARREGAMENTO DOS DADOS LOCAIS (SEM REQUISIÇÃO HTTP/404) ──
@st.cache_data(ttl=3600)
def carregar_dados() -> pd.DataFrame:
    """Carrega o headcount diretamente do arquivo local clonado no repositório."""
    if os.path.exists(PARQUET_FILE):
        return pd.read_parquet(PARQUET_FILE)
    else:
        st.error(f"❌ Arquivo '{PARQUET_FILE}' não encontrado na raiz do projeto.")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def carregar_high_performance() -> pd.DataFrame:
    """Carrega o High Performance diretamente do arquivo local."""
    if os.path.exists(HP_PARQUET_FILE):
        return pd.read_parquet(HP_PARQUET_FILE)
    return pd.DataFrame()


# ══════════════════════════════════════════════════════════════
#  TELA DE LOGIN — Microsoft SSO
# ══════════════════════════════════════════════════════════════

def tela_login():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');
    * { box-sizing:border-box; margin:0; padding:0; }
    [data-testid="stHeader"],[data-testid="stToolbar"],#MainMenu,footer { display:none !important; }
    section[data-testid="stMain"] {
        background: radial-gradient(ellipse at 15% 85%,rgba(180,30,60,.45) 0%,transparent 50%),
            radial-gradient(ellipse at 85% 15%,rgba(140,20,45,.3) 0%,transparent 50%),
            linear-gradient(150deg,#1a0d12 0%,#2a1020 40%,#1a0d20 70%,#0f1020 100%) !important;
        min-height:100vh; display:flex !important; align-items:center !important; justify-content:center !important;
    }
    .block-container { padding:2rem 1rem !important; max-width:460px !important; width:100% !important; }
    section[data-testid="stMain"] * { font-family:'Poppins',sans-serif !important; }
    .lc { width:100%; background:rgba(8,4,12,.85); border:1px solid rgba(255,255,255,.08); border-radius:20px; padding:36px 32px 32px; }
    .lc-top { display:flex; align-items:center; justify-content:space-between; margin-bottom:24px; }
    .lc-logo { display:flex; align-items:center; gap:10px; }
    .lc-icon { width:34px; height:34px; background:rgba(210,45,65,.15); border:1px solid rgba(210,45,65,.3); border-radius:9px; display:flex; align-items:center; justify-content:center; }
    .lc-name { font-size:16px; font-weight:800; color:white; letter-spacing:1.5px; text-transform:uppercase; }
    .lc-status { display:flex; align-items:center; gap:5px; font-size:10px; color:rgba(255,255,255,.25); text-transform:uppercase; }
    .lc-dot { width:6px; height:6px; background:#4ade80; border-radius:50%; display:inline-block; animation:pulse 2s infinite; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
    .lc-div { height:1px; background:linear-gradient(90deg,transparent,rgba(210,45,65,.35),transparent); margin-bottom:24px; }
    .lc-tag { display:inline-flex; align-items:center; gap:6px; background:rgba(210,45,65,.1); border:1px solid rgba(210,45,65,.2); border-radius:6px; padding:4px 10px; font-size:10px; font-weight:600; color:#e05070; letter-spacing:1px; text-transform:uppercase; margin-bottom:14px; }
    .lc-title { font-size:28px; font-weight:800; color:white; letter-spacing:-.5px; line-height:1.1; margin-bottom:6px; text-transform:uppercase; }
    .lc-title span { color:#d9304f; }
    .lc-sub { font-size:10px; color:rgba(255,255,255,.28); margin-bottom:28px; letter-spacing:.8px; text-transform:uppercase; }
    .lc-info { background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.06); border-radius:10px; padding:12px 14px; margin-bottom:20px; font-size:11px; color:rgba(255,255,255,.45); line-height:1.6; }
    .lc-foot { margin-top:20px; padding-top:16px; border-top:1px solid rgba(255,255,255,.04); }
    .lc-foot-l1 { font-size:9px; font-weight:600; color:rgba(255,255,255,.18); text-transform:uppercase; letter-spacing:.8px; margin-bottom:2px; }
    .lc-foot-l2 { font-size:9px; color:rgba(200,37,63,.4); text-transform:uppercase; letter-spacing:.5px; }
    div[data-testid="stButton"] > button {
        background: rgba(255,255,255,.06) !important;
        border: 1px solid rgba(255,255,255,.12) !important;
        border-radius: 10px !important;
        color: white !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        padding: 12px !important;
        width: 100% !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('''
    <div class="lc">
      <div class="lc-top">
        <div class="lc-logo"><span class="lc-name">Webmotors</span></div>
        <div class="lc-status"><span class="lc-dot"></span> Sistema Ativo</div>
      </div>
      <div class="lc-div"></div>
      <div class="lc-tag">HR Analytics</div>
      <div class="lc-title">Pessoas<br>&amp; <span>Cultura</span></div>
      <div class="lc-sub">Dados de Ativos &amp; Inativos</div>
    </div>
    ''', unsafe_allow_html=True)

    if st.button("Entrar com conta Microsoft", use_container_width=True):
        st.login()


def tela_acesso_negado(email: str):
    st.error("🚫 Acesso negado")
    st.markdown(f"O e-mail `{email}` não pertence ao domínio corporativo `@{DOMINIO_PERMITIDO}`.")
    if st.button("Sair"):
        st.logout()


# ══════════════════════════════════════════════════════════════
#  MÓDULOS DE CÁLCULO INTERNO (PURE PYTHON)
# ══════════════════════════════════════════════════════════════

def _prep(df): 
    df = df.copy()
    df["_D"] = pd.to_datetime(df["DATA"], dayfirst=True, errors="coerce")
    return df

def _pct(v, t): return round(v / t * 100, 1) if t > 0 else 0
def _var(a, b): return round((a - b) / b * 100, 1) if b > 0 else 0

def analise_hc_empresa(df):
    df = _prep(df)
    if df.empty: return "Base de dados vazia.", None
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    if pd.isnull(mes_ref): return "Nenhum dado ativo encontrado.", None
    
    ref = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)].groupby("EMPRESA").size()
    linhas = [f"### 📊 Headcount por Empresa — {mes_ref.strftime('%b/%Y').upper()}"]
    for emp, qtd in ref.items():
        linhas.append(f"- **{emp}**: {qtd} colaboradores ativos")
    return "\n".join(linhas), None


# ══════════════════════════════════════════════════════════════
#  CONTROLE DE FLUXO PRINCIPAL
# ══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = "Você é o assistente analítico de HR da Webmotors. Use tom executivo e direto."

if not st.user.is_logged_in:
    tela_login()
else:
    email_usuario = st.user.email
    if not email_usuario.endswith(f"@{DOMINIO_PERMITIDO}"):
        tela_acesso_negado(email_usuario)
    else:
        df_headcount = carregar_dados()
        df_high_perf = carregar_high_performance()
        
        st.sidebar.title("Navegação")
        st.sidebar.markdown(f"👤 **{st.user.name}**\n`{email_usuario}`")
        app_mode = st.sidebar.radio("Selecione o Módulo:", ["💬 Agente Analítico", "📊 Relatórios Diretos"])
        st.sidebar.markdown(f"📅 **Próximo 5º dia útil:** `{proximo_5_dia_util()}`")
        
        if st.sidebar.button("Log Out / Sair"):
            st.logout()
            
        if app_mode == "💬 Agente Analítico":
            st.title("💬 Agente Analítico de HR")
            if "messages" not in st.session_state:
                st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                
            for msg in st.session_state.messages:
                if msg["role"] != "system":
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])
                        
            if user_prompt := st.chat_input("Pergunte algo sobre a base..."):
                st.session_state.messages.append({"role": "user", "content": user_prompt})
                with st.chat_message("user"):
                    st.markdown(user_prompt)
                    
                with st.chat_message("assistant"):
                    if GROQ_API_KEY:
                        try:
                            client = Groq(api_key=GROQ_API_KEY)
                            contexto = f"\n[Contexto: {df_headcount.shape[0]} linhas carregadas]"
                            st.session_state.messages[0]["content"] = SYSTEM_PROMPT + contexto
                            
                            response = client.chat.completions.create(
                                model="llama-3.3-70b-versatile",
                                messages=st.session_state.messages
                            )
                            output = response.choices[0].message.content
                            st.markdown(output)
                            st.session_state.messages.append({"role": "assistant", "content": output})
                        except Exception as e:
                            st.error(f"Erro no Agente: {e}")
                    else:
                        st.warning("⚠️ GROQ_API_KEY não configurada nos Secrets.")
                        
        elif app_mode == "📊 Relatórios Diretos":
            st.title("📊 Relatórios Diretos")
            if st.button("Gerar Sumário de Headcount", use_container_width=True):
                with st.spinner("Processando..."):
                    txt, _ = analise_hc_empresa(df_headcount)
                    st.markdown(txt)
