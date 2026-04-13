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
    * { box-sizing: border-box; margin: 0; padding: 0; }
    [data-testid="stHeader"],[data-testid="stToolbar"],#MainMenu,footer { display:none !important; }
    section[data-testid="stMain"] {
        background:
            radial-gradient(ellipse at 15% 85%, rgba(180,30,60,0.45) 0%, transparent 50%),
            radial-gradient(ellipse at 85% 15%, rgba(140,20,45,0.3) 0%, transparent 50%),
            linear-gradient(150deg, #1a0d12 0%, #2a1020 40%, #1a0d20 70%, #0f1020 100%) !important;
        min-height: 100vh;
    }
    .block-container { padding: 0 !important; max-width: 100% !important; }
    section[data-testid="stMain"] * { font-family: 'Poppins', sans-serif !important; }
    .lc-page { display:flex; align-items:center; justify-content:center; min-height:100vh; padding:24px; }
    .lc { width:100%; max-width:420px; background:rgba(8,4,12,0.72); border:1px solid rgba(255,255,255,0.08); border-radius:20px; padding:36px 32px 32px; }
    .lc-top { display:flex; align-items:center; justify-content:space-between; margin-bottom:24px; }
    .lc-logo { display:flex; align-items:center; gap:10px; }
    .lc-icon { width:34px; height:34px; background:rgba(210,45,65,0.15); border:1px solid rgba(210,45,65,0.3); border-radius:9px; display:flex; align-items:center; justify-content:center; }
    .lc-name { font-size:16px; font-weight:800; color:white; letter-spacing:1.5px; text-transform:uppercase; }
    .lc-status { display:flex; align-items:center; gap:5px; font-family:'Space Mono',monospace; font-size:10px; color:rgba(255,255,255,0.25); text-transform:uppercase; }
    .lc-dot { width:6px; height:6px; background:#4ade80; border-radius:50%; display:inline-block; animation:pulse 2s infinite; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
    .lc-div { height:1px; background:linear-gradient(90deg,transparent,rgba(210,45,65,0.35),transparent); margin-bottom:24px; }
    .lc-tag { display:inline-flex; align-items:center; gap:6px; background:rgba(210,45,65,0.1); border:1px solid rgba(210,45,65,0.2); border-radius:6px; padding:4px 10px; font-size:10px; font-weight:600; color:#e05070; letter-spacing:1px; text-transform:uppercase; margin-bottom:14px; }
    .lc-title { font-size:28px; font-weight:800; color:white; letter-spacing:-0.5px; line-height:1.1; margin-bottom:6px; text-transform:uppercase; }
    .lc-title span { color:#d9304f; }
    .lc-sub { font-size:10px; color:rgba(255,255,255,0.28); margin-bottom:28px; letter-spacing:0.8px; text-transform:uppercase; }
    .lc-label { font-size:9px; font-weight:700; color:rgba(255,255,255,0.3); letter-spacing:2px; text-transform:uppercase; margin-bottom:8px; }
    .lc-input-wrap { position:relative; margin-bottom:12px; }
    .lc-input { width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.08); border-radius:10px; padding:12px 52px 12px 16px; color:white; font-family:'Poppins',sans-serif; font-size:15px; letter-spacing:3px; outline:none; transition:all 0.2s; }
    .lc-input:focus { border-color:rgba(210,45,65,0.5); background:rgba(210,45,65,0.04); }
    .lc-input::placeholder { letter-spacing:2px; color:rgba(255,255,255,0.15); }
    .lc-input-btn { position:absolute; right:6px; top:50%; transform:translateY(-50%); width:36px; height:36px; background:#c8253f; border:none; border-radius:8px; cursor:pointer; display:flex; align-items:center; justify-content:center; transition:background 0.2s; }
    .lc-input-btn:hover { background:#a81e34; }
    .lc-btn { width:100%; background:rgba(210,45,65,0.25); border:1px solid rgba(210,45,65,0.45); border-radius:10px; padding:12px; color:rgba(255,255,255,0.6); font-family:'Poppins',sans-serif; font-size:11px; font-weight:700; letter-spacing:1.5px; text-transform:uppercase; cursor:pointer; transition:all 0.3s; display:flex; align-items:center; justify-content:center; gap:8px; }
    .lc-btn:hover, .lc-btn.on { background:#c8253f; border-color:#c8253f; color:white; }
    .lc-err { background:rgba(210,45,65,0.08); border:1px solid rgba(210,45,65,0.25); border-radius:8px; padding:10px 14px; color:#e05070; font-size:11px; margin-top:10px; display:none; }
    .lc-foot { margin-top:20px; padding-top:16px; border-top:1px solid rgba(255,255,255,0.04); }
    .lc-foot-l1 { font-size:9px; font-weight:600; color:rgba(255,255,255,0.18); text-transform:uppercase; letter-spacing:0.8px; margin-bottom:2px; }
    .lc-foot-l2 { font-size:9px; color:rgba(200,37,63,0.4); text-transform:uppercase; letter-spacing:0.5px; }
    div[data-testid="stTextInput"] { display:none !important; }
    </style>

    <div class="lc-page">
     <div class="lc">
      <div class="lc-top">
        <div class="lc-logo">
          <div class="lc-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#d9304f" stroke-width="2.5" stroke-linecap="round">
              <line x1="18" y1="20" x2="18" y2="10"/>
              <line x1="12" y1="20" x2="12" y2="4"/>
              <line x1="6" y1="20" x2="6" y2="14"/>
            </svg>
          </div>
          <span class="lc-name">Webmotors</span>
        </div>
        <div class="lc-status"><span class="lc-dot"></span> Sistema Ativo</div>
      </div>
      <div class="lc-div"></div>
      <div class="lc-tag">
        <svg width="7" height="7" viewBox="0 0 8 8"><rect width="8" height="8" rx="2" fill="#d9304f"/></svg>
        HR Analytics
      </div>
      <div class="lc-title">Pessoas<br>&amp; <span>Cultura</span></div>
      <div class="lc-sub">Dados de Ativos &amp; Inativos — Senior</div>
      <div class="lc-label">Senha de Acesso</div>
      <div class="lc-input-wrap">
        <input class="lc-input" id="lc-pwd" type="password" placeholder="••••••••••"
          oninput="document.getElementById('lc-main-btn').classList.toggle('on', this.value.length>0)"
          onkeydown="if(event.key==='Enter')doLogin()"/>
        <button class="lc-input-btn" onclick="doLogin()" title="Entrar">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
            <polyline points="10 17 15 12 10 7"/>
            <line x1="15" y1="12" x2="3" y2="12"/>
          </svg>
        </button>
      </div>
      <button class="lc-btn" id="lc-main-btn" onclick="doLogin()">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        Acessar Plataforma
      </button>
      <div class="lc-err" id="lc-err">Senha incorreta. Solicite ao responsável.</div>
      <div class="lc-foot">
        <div class="lc-foot-l1">HR Analytics &amp; Operations | Webmotors SA</div>
        <div class="lc-foot-l2">Owner: Gustavo Pereira das Neves</div>
      </div>
     </div>
    </div>

    <script>
    function doLogin() {
      const pwd = document.getElementById('lc-pwd').value;
      if (!pwd) return;
      const inputs = window.parent.document.querySelectorAll('input[type="password"]');
      inputs.forEach(inp => {
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(inp, pwd);
        inp.dispatchEvent(new Event('input', {bubbles:true}));
      });
      setTimeout(() => {
        const btns = window.parent.document.querySelectorAll('button[kind="secondary"], button');
        btns.forEach(b => { if(b.innerText && b.innerText.includes('Acessar')) b.click(); });
      }, 100);
    }
    </script>
    """, unsafe_allow_html=True)

    senha = st.text_input("pwd", type="password", key="pwd_native", label_visibility="collapsed")
    if st.button("Acessar Plataforma →", key="btn_login"):
        if hashlib.md5(senha.encode()).hexdigest() == APP_PASSWORD_HASH:
            st.session_state["autenticado"] = True
            st.session_state["historico"]   = []
            st.session_state["mensagens"]   = []
            st.rerun()
        else:
            st.session_state["login_erro"] = True


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
