# =============================================================
#  AGENTE ANALÍTICO DE HR — Webmotors
#  Backend: Google Gemini 1.5 Flash (gratuito)
#
#  Instalação:
#    pip install -r requirements.txt
#
#  Rodar local:
#    streamlit run app.py
#
#  Secrets necessários no Streamlit Cloud:
#    GEMINI_API_KEY    = "AIzaSy..."
#    APP_PASSWORD_HASH = "hash_md5_da_sua_senha"
#    GITHUB_TOKEN      = "ghp_..."
#
#  Para gerar o hash da senha (rode no terminal):
#    python -c "import hashlib; print(hashlib.md5('SUA_SENHA'.encode()).hexdigest())"
# =============================================================

import os
import hashlib
import time
import pandas as pd
import streamlit as st
from datetime import datetime
import google.generativeai as genai

# ── CONFIGURAÇÕES ─────────────────────────────────────────────
st.set_page_config(
    page_title="HR Analytics · Webmotors",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

MODEL = "gemini-1.5-flash"

PARQUET_URL = (
    "https://raw.githubusercontent.com/gustavowebmotors13-jpg/"
    "hr-analytics-agente/main/Headcount_Consolidado.parquet"
)

APP_PASSWORD_HASH = st.secrets.get(
    "APP_PASSWORD_HASH",
    hashlib.md5("demo123".encode()).hexdigest()
)

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
genai.configure(api_key=GEMINI_API_KEY)


# ── CARREGAMENTO DOS DADOS ────────────────────────────────────
@st.cache_data(ttl=3600)
def carregar_dados() -> pd.DataFrame:
    import requests, io
    token = st.secrets.get("GITHUB_TOKEN", "")
    headers = {"Authorization": f"token {token}"} if token else {}
    r = requests.get(PARQUET_URL, headers=headers, timeout=60)
    r.raise_for_status()
    df = pd.read_parquet(io.BytesIO(r.content))
    return df


# ── FERRAMENTAS DO AGENTE ─────────────────────────────────────
def obter_schema(df: pd.DataFrame) -> str:
    linhas = []
    for col in df.columns:
        dtype    = str(df[col].dtype)
        exemplos = df[col].dropna().unique()[:3]
        ex_str   = ", ".join(str(e) for e in exemplos)
        linhas.append(f"  {col} ({dtype}): ex. {ex_str}")

    ativos   = len(df[df["STATUS_TIPO"] == "ATIVO"])   if "STATUS_TIPO" in df.columns else "?"
    inativos = len(df[df["STATUS_TIPO"] == "INATIVO"]) if "STATUS_TIPO" in df.columns else "?"

    ultima_extracao = ""
    if "DATA_EXTRACAO" in df.columns:
        ultima_extracao = f"\nÚltima atualização ETL: {df['DATA_EXTRACAO'].iloc[0]}"

    return (
        f"Total de registros: {len(df)}\n"
        f"Ativos: {ativos} | Inativos: {inativos}"
        f"{ultima_extracao}\n\n"
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
        try:
            import plotly.graph_objects as go
            if isinstance(resultado, go.Figure):
                return "__PLOTLY__:" + resultado.to_json()
        except Exception:
            pass
        return str(resultado)
    except Exception as e:
        return f"ERRO: {e}"


SYSTEM_PROMPT = """Você é um assistente especializado em análise de dados de RH da Webmotors.

Você tem acesso ao dataframe 'df' com dados de colaboradores ATIVOS e INATIVOS da Webmotors, CAR10, LOOP, Revenda Mais e Syonet.

ESTRUTURA IMPORTANTE DO DATAFRAME:
- Coluna STATUS_TIPO: "ATIVO" ou "INATIVO" — use para filtrar entre ativos e desligados
- Coluna EMPRESA: nome da empresa (WEBMOTORS, CAR10, LOOP, REVENDA MAIS, SYONET)
- Coluna NOME COMPLETO: nome do colaborador
- Coluna AREA: área/time do colaborador
- Coluna DIRETORIA: diretoria do colaborador
- Coluna CARGO: cargo com sufixo da empresa ex: ANALISTA DE DADOS SR (W)
- Coluna SENIORIDADE: nível hierárquico ex: 1.6. SENIOR, 1.8. COORDENADOR
- Coluna TIPO CONTRATACAO: CLT, PJ, ESTÁGIO, APRENDIZ, etc.
- Coluna GENERO: MASCULINO, FEMININO
- Coluna ETNIA: BRANCO, PRETO, PARDO, etc.
- Coluna DATA: primeiro dia do mês de referência
- Coluna DATA DESLIGAMENTO: data de desligamento (apenas inativos)
- Coluna DATA DE ADMISSAO: data de admissão
- Coluna INICIATIVA: "INICIATIVA DA EMPRESA" (involuntário) ou "INICIATIVA DO EMPREGADO" (voluntário). Sempre use .str.upper().str.contains() para filtrar.
- Coluna FY: ano fiscal (FY26, FY25, FY24, FY23, OTHERS)
- Coluna DATA_EXTRACAO: timestamp da última execução do ETL

Suas regras:
1. Sempre consulte o schema antes de escrever qualquer código de consulta.
2. Responda sempre em português brasileiro, de forma clara e objetiva.
3. Contextualize os números quando relevante (ex: percentuais, comparações).
4. Nunca invente dados — se não souber, diga claramente.
5. Para filtros de texto, SEMPRE use .str.upper().str.contains() — nunca == com texto fixo para INICIATIVA.
6. Sempre salve o resultado final na variável 'resultado'.
7. Seja conciso e direto, sem respostas longas demais.
8. Para analisar apenas ativos: df[df['STATUS_TIPO'] == 'ATIVO']
9. Para analisar apenas inativos/desligados: df[df['STATUS_TIPO'] == 'INATIVO']
10. NUNCA use tags HTML nas respostas — use apenas markdown puro.
11. Para destacar percentuais use apenas texto: ex. **15,0%**
"""

# ── Ferramentas no formato Gemini ─────────────────────────────
FERRAMENTAS_GEMINI = [
    {
        "name": "obter_schema",
        "description": (
            "Retorna o schema completo do dataframe: colunas, tipos e exemplos. "
            "Use SEMPRE como primeiro passo antes de qualquer consulta."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "executar_pandas",
        "description": (
            "Executa código Python/pandas no dataframe 'df'. "
            "Salve o resultado na variável 'resultado'. "
            "Use .str.upper() para filtros de texto. "
            "Para ativos: df[df['STATUS_TIPO']=='ATIVO']. "
            "Para inativos: df[df['STATUS_TIPO']=='INATIVO']."
        ),
        "parameters": {
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


# ── AGENTE COM RETRY/BACKOFF ──────────────────────────────────
def rodar_agente(pergunta: str, historico: list, df: pd.DataFrame, contexto_filtros: str = "") -> str:

    system_completo = SYSTEM_PROMPT
    if contexto_filtros:
        system_completo = SYSTEM_PROMPT + "\n" + contexto_filtros

    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=system_completo,
        tools=[{"function_declarations": FERRAMENTAS_GEMINI}]
    )

    # Converte histórico para formato Gemini
    gemini_history = []
    for msg in historico:
        role = "user" if msg["role"] == "user" else "model"
        gemini_history.append({"role": role, "parts": [msg["content"]]})

    chat = model.start_chat(history=gemini_history)

    MAX_RETRIES = 4
    BASE_WAIT   = 15  # segundos — backoff: 15s, 30s, 60s, 120s

    def enviar_com_retry(mensagem):
        """Envia mensagem ao Gemini com retry exponencial em caso de rate limit."""
        for tentativa in range(MAX_RETRIES):
            try:
                return chat.send_message(mensagem)
            except Exception as e:
                erro_str = str(e).lower()
                if any(k in erro_str for k in ("429", "quota", "rate", "resource_exhausted")):
                    if tentativa < MAX_RETRIES - 1:
                        espera = BASE_WAIT * (2 ** tentativa)
                        st.toast(
                            f"⏳ Limite da API atingido. Aguardando {espera}s...",
                            icon="⏳"
                        )
                        time.sleep(espera)
                    else:
                        raise
                else:
                    raise

    # Loop agêntico — máx 6 iterações
    resposta = enviar_com_retry(pergunta)

    for _ in range(6):
        # Verifica se há chamadas de ferramenta
        tool_calls = []
        for part in resposta.parts:
            if hasattr(part, "function_call") and part.function_call.name:
                tool_calls.append(part.function_call)

        if not tool_calls:
            # Sem tool calls — retorna texto final
            try:
                return resposta.text
            except Exception:
                return "(sem resposta)"

        # Executa as ferramentas e devolve os resultados ao modelo
        tool_results = []
        for call in tool_calls:
            nome = call.name
            args = dict(call.args) if call.args else {}

            if nome == "obter_schema":
                resultado_tool = obter_schema(df)
            elif nome == "executar_pandas":
                resultado_tool = executar_pandas(args.get("codigo", ""), df)
            else:
                resultado_tool = "Ferramenta não encontrada."

            tool_results.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=nome,
                        response={"result": resultado_tool}
                    )
                )
            )

        resposta = enviar_com_retry(tool_results)

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
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    .block-container { padding: 2rem 1rem !important; max-width: 460px !important; width: 100% !important; }
    section[data-testid="stMain"] * { font-family: 'Poppins', sans-serif !important; }
    .lc { width:100%; background:rgba(8,4,12,0.75); border:1px solid rgba(255,255,255,0.08); border-radius:20px; padding:36px 32px 32px; }
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
    .lc-foot { margin-top:20px; padding-top:16px; border-top:1px solid rgba(255,255,255,0.04); }
    .lc-foot-l1 { font-size:9px; font-weight:600; color:rgba(255,255,255,0.18); text-transform:uppercase; letter-spacing:0.8px; margin-bottom:2px; }
    .lc-foot-l2 { font-size:9px; color:rgba(200,37,63,0.4); text-transform:uppercase; letter-spacing:0.5px; }
    div[data-testid="stForm"] { border:none !important; padding:0 !important; background:transparent !important; }
    div[data-testid="stTextInput"] input {
        background:rgba(255,255,255,0.05) !important; border:1px solid rgba(255,255,255,0.08) !important;
        border-radius:10px !important; color:white !important; letter-spacing:3px !important;
        font-size:15px !important; padding:12px 16px !important;
    }
    div[data-testid="stTextInput"] input:focus { border-color:rgba(210,45,65,0.5) !important; background:rgba(210,45,65,0.04) !important; box-shadow:none !important; }
    div[data-testid="stTextInput"] label { color:rgba(255,255,255,0.3) !important; font-size:9px !important; font-weight:700 !important; letter-spacing:2px !important; text-transform:uppercase !important; }
    small, .st-emotion-cache-1gulkj5, [data-testid="InputInstructions"],
    div[class*="InputInstructions"], div[class*="inputInstructions"],
    div[data-testid="stTextInput"] > div > div > div:last-child { display: none !important; }
    div[data-testid="stFormSubmitButton"] > button {
        background: rgba(210,45,65,0.35) !important; border: 1px solid rgba(210,45,65,0.55) !important;
        border-radius:10px !important; color: rgba(255,255,255,0.75) !important;
        font-size:11px !important; font-weight:700 !important; letter-spacing:1.5px !important;
        text-transform:uppercase !important; padding:12px !important; width:100% !important; transition:all 0.2s !important;
    }
    div[data-testid="stFormSubmitButton"] > button:hover { background: #c8253f !important; border-color: #c8253f !important; color: white !important; }
    div[data-testid="stAlert"] { border-radius:8px !important; font-size:12px !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('''
    <div class="lc">
      <div class="lc-top">
        <div class="lc-logo">
          <div class="lc-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#d9304f" stroke-width="2.5" stroke-linecap="round">
              <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
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
      <div class="lc-sub">Dados de Ativos &amp; Inativos — Headcount ETL</div>
    </div>
    ''', unsafe_allow_html=True)

    with st.form("login_form"):
        senha = st.text_input("Senha de Acesso", type="password", placeholder="••••••••••")
        submit = st.form_submit_button("🔒  Acessar Plataforma", use_container_width=True)
        if submit:
            if hashlib.md5(senha.encode()).hexdigest() == APP_PASSWORD_HASH:
                st.session_state["autenticado"] = True
                st.session_state["historico"]   = []
                st.session_state["mensagens"]   = []
                st.rerun()
            else:
                st.error("Senha incorreta. Solicite ao responsável pelo HR Analytics.")

    st.markdown('''
    <div class="lc-foot">
      <div class="lc-foot-l1">HR Analytics &amp; Operations | Webmotors SA</div>
      <div class="lc-foot-l2">Owner: Gustavo Pereira das Neves</div>
    </div>
    ''', unsafe_allow_html=True)


def tela_chat(df: pd.DataFrame):

    # SIDEBAR ─────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
        section[data-testid="stSidebar"] { background: #0d0d0f !important; border-right: 1px solid rgba(255,255,255,0.06) !important; }
        section[data-testid="stSidebar"] * { font-family: 'Poppins', sans-serif !important; color: white !important; }
        button[data-testid="collapsedControl"],
        section[data-testid="stSidebarCollapseButton"],
        div[data-testid="stSidebarCollapseButton"],
        button[kind="header"],
        [title="keyboard_double_arrow_left"],
        [aria-label="keyboard_double_arrow_left"],
        button[title*="keyboard"],
        span[class*="material"] { display: none !important; }
        section[data-testid="stSidebar"] .stButton button {
            background: rgba(255,255,255,0.04) !important; border: 1px solid rgba(255,255,255,0.08) !important;
            border-radius: 8px !important; color: rgba(255,255,255,0.6) !important;
            font-size: 11px !important; font-weight: 500 !important; text-align: left !important;
            padding: 8px 12px !important; transition: all 0.2s !important;
        }
        section[data-testid="stSidebar"] .stButton button:hover {
            background: rgba(230,57,70,0.12) !important; border-color: rgba(230,57,70,0.3) !important; color: white !important;
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

        st.markdown('<div class="sb-section" style="margin-top:4px">Filtros</div>', unsafe_allow_html=True)

        empresas_disponiveis = sorted(df["EMPRESA"].dropna().unique().tolist()) if "EMPRESA" in df.columns else []
        empresas_selecionadas = st.multiselect(
            "Empresa", options=empresas_disponiveis, default=empresas_disponiveis,
            key="filtro_empresa", label_visibility="collapsed", placeholder="Selecione empresas..."
        )
        if empresas_selecionadas:
            df = df[df["EMPRESA"].isin(empresas_selecionadas)]

        if st.button("✕  Limpar filtros", use_container_width=True, key="btn_limpar"):
            st.session_state.pop("filtro_empresa", None)
            st.rerun()

        if empresas_selecionadas and len(empresas_selecionadas) < len(empresas_disponiveis):
            st.markdown(f'<div style="font-size:9px;color:rgba(230,57,70,0.8);margin-top:2px">🔴 {", ".join(empresas_selecionadas)}</div>', unsafe_allow_html=True)

        st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

        if "DATA" in df.columns and "STATUS_TIPO" in df.columns and len(df) > 0:
            df_d = df.copy()
            df_d["_DATA_DT"] = pd.to_datetime(df_d["DATA"], dayfirst=True, errors="coerce")
            mes_max_ativos   = df_d[df_d["STATUS_TIPO"] == "ATIVO"]["_DATA_DT"].max()
            mes_ref_label    = mes_max_ativos.strftime("%b/%y").upper() if pd.notna(mes_max_ativos) else ""
            df_mes           = df_d[df_d["_DATA_DT"] == mes_max_ativos]
            ativos_mes       = len(df_mes[df_mes["STATUS_TIPO"] == "ATIVO"])
            inativos_mes     = len(df_mes[df_mes["STATUS_TIPO"] == "INATIVO"])
            total_mes        = ativos_mes + inativos_mes
        else:
            ativos_mes = inativos_mes = total_mes = 0
            mes_ref_label = ""

        ultima_etl = df["DATA_EXTRACAO"].iloc[0] if "DATA_EXTRACAO" in df.columns and len(df) > 0 else datetime.now().strftime("%d/%m %H:%M")

        st.markdown(f"""
        <div class="sb-logo">
            <div class="sb-logo-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#E63946" stroke-width="2.5" stroke-linecap="round">
                    <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
                </svg>
            </div>
            <span class="sb-logo-name">Webmotors</span>
        </div>
        <div class="sb-divider"></div>
        <div style="font-size:9px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:rgba(255,255,255,0.25);margin-bottom:6px">{mes_ref_label}</div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:8px">
            <div class="sb-stat"><div class="sb-stat-label">Total</div><div class="sb-stat-value">{total_mes:,}</div></div>
            <div class="sb-stat"><div class="sb-stat-label">Ativos</div><div class="sb-stat-value">{ativos_mes:,}</div></div>
            <div class="sb-stat"><div class="sb-stat-label">Inativos</div><div class="sb-stat-value">{inativos_mes:,}</div></div>
        </div>
        <div class="sb-stat" style="margin-bottom:0">
            <div class="sb-stat-label">Última atualização ETL</div>
            <div class="sb-stat-sub">{ultima_etl}</div>
        </div>
        <div class="sb-divider"></div>
        <div class="sb-section">Análises Rápidas</div>
        """, unsafe_allow_html=True)

        PROMPT_TURNOVER = """Calcule o relatório de Turnover com comparativo YoY (ano anterior vs ano atual).

Siga estes passos no código:
1. df['_DATA_DT'] = pd.to_datetime(df['DATA'], dayfirst=True, errors='coerce')
2. mes_max = df[df['STATUS_TIPO']=='ATIVO']['_DATA_DT'].max()
3. Período ATUAL: ini_atual = mes_max - pd.DateOffset(months=11) até mes_max
4. Período ANTERIOR: ini_ant = mes_max - pd.DateOffset(months=23) até mes_max - pd.DateOffset(months=12)

Para CADA período calcule:
- HC Médio (média mensal dos ativos)
- Involuntários: INICIATIVA.str.upper().str.contains('EMPRESA', na=False)
- Voluntários: INICIATIVA.str.upper().str.contains('EMPREGADO', na=False)
- TO% Involuntário, Voluntário e Total (1 casa decimal)

Apresente tabela markdown:
| Métrica | [período anterior] | [período atual] |
|---|---|---|
| HC Médio (12 meses) | X | X |
| Desligamentos Involuntários | X | X |
| Desligamentos Voluntários | X | X |
| Turnover % Involuntário | X% | X% |
| Turnover % Voluntário | X% | X% |
| Turnover % Total | X% | X% |
Use apenas markdown — sem HTML."""

        st.markdown("""
        <style>
        div[data-testid="stSidebar"] button[kind="secondary"]:first-of-type {
            background: rgba(230,57,70,0.15) !important;
            border: 1px solid rgba(230,57,70,0.4) !important;
            color: #ff8090 !important; font-weight: 700 !important;
        }
        </style>
        """, unsafe_allow_html=True)

        if st.button("📊 Relatório de Turnover (12m)", use_container_width=True, key="btn_turnover"):
            st.session_state["pergunta_rapida"] = PROMPT_TURNOVER

        st.markdown('<div style="margin-bottom:4px"></div>', unsafe_allow_html=True)

        PROMPTS = {
            "🏢 Headcount por Empresa": """Analise o headcount atual por empresa com comparativo YoY.
Passos: converta DATA, pegue mes_ref (mais recente ativos) e mes_yoy (mes_ref - 1 ano).
Calcule HC por empresa nos dois períodos e variação %.
Apresente para cada empresa: "Temos **X colaboradores** na **EMPRESA**. ▲/▼ X% YoY"
Use apenas markdown.""",

            "📋 Tipo de Contrato": """Distribuição de ATIVOS por tipo de contratação com YoY.
Passos: mes_ref e mes_yoy, agrupe por TIPO CONTRATACAO.
Tabela markdown: | Tipo | Qtd Atual | Qtd YoY | Var % | — com totais.
Use apenas markdown.""",

            "🏆 Top 5 Áreas": """Top 5 áreas por headcount de ATIVOS no mês mais recente.
Passos: mes_ref, df_ref = ativos, top 5 por AREA com %.
Tabela markdown: | # | Área | Headcount | % do Total |
Use apenas markdown.""",

            "📊 Headcount por Senioridade": """Distribuição de ATIVOS por SENIORIDADE no mês mais recente.
Passos: mes_ref, df_ref, agrupe por SENIORIDADE ordenado numericamente, calcule %.
Tabela markdown: | Senioridade | Headcount | % |
Use apenas markdown.""",

            "🚪 Inativos": """Analise desligamentos do mês mais recente dos inativos.
Passos: mes_ref_inat (max dos inativos), total, por iniciativa (EMPRESA/EMPREGADO), MoM.
Apresente: total, involuntários, voluntários, TO% do mês.
Use apenas markdown.""",

            "📈 TO% Mensal (Tabela)": """Turnover mensal dos últimos 12 meses com acumulado.
Passos: para cada mês, HC ativos + inativos por iniciativa → TO% Inv, Vol, Total.
Tabela: | Mês/Ano | HC | Inv | Vol | TO% Inv | TO% Vol | TO% Total |
Linha ACUMULADO ao final. Use apenas markdown.""",

            "📉 TO% Gráfico + Tabela": """Gere gráfico Plotly de Turnover mensal (24 meses) + tabela por FY.

```python
import plotly.graph_objects as go
import pandas as pd
df['_D'] = pd.to_datetime(df['DATA'], dayfirst=True, errors='coerce')
mes_max = df[df['STATUS_TIPO']=='ATIVO']['_D'].max()
mes_ini = mes_max - pd.DateOffset(months=23)
meses = pd.date_range(start=mes_ini.replace(day=1), end=mes_max, freq='MS')
dados = []
for mes in meses:
    at = df[(df['STATUS_TIPO']=='ATIVO') & (df['_D']==mes)]
    inat = df[(df['STATUS_TIPO']=='INATIVO') & (df['_D']==mes)]
    hc = len(at)
    inv = inat['INICIATIVA'].str.upper().str.contains('EMPRESA', na=False).sum()
    vol = inat['INICIATIVA'].str.upper().str.contains('EMPREGADO', na=False).sum()
    total_inat = inv + vol
    to_pct = round(total_inat / hc * 100, 1) if hc > 0 else 0
    to_inv = round(inv / hc * 100, 1) if hc > 0 else 0
    to_vol = round(vol / hc * 100, 1) if hc > 0 else 0
    fy = df[df['_D']==mes]['FY'].iloc[0] if len(df[df['_D']==mes]) > 0 else ''
    dados.append({'mes': mes, 'hc': hc, 'inv': inv, 'vol': vol, 'total': total_inat, 'to_pct': to_pct, 'to_inv': to_inv, 'to_vol': to_vol, 'fy': fy})
df_to = pd.DataFrame(dados)
df_to = df_to[df_to['hc'] > 0]
labels = [m.strftime('%b/%y').upper() for m in df_to['mes']]
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=labels, y=df_to['to_pct'], fill='tozeroy', fillcolor='rgba(192,0,60,0.15)',
    line=dict(color='#C0003C', width=2.5), mode='lines+markers+text',
    text=[f"{v}%" for v in df_to['to_pct']], textposition='top center',
    textfont=dict(size=11, color='white', family='Poppins'),
    marker=dict(size=8, color='#C0003C', line=dict(color='white', width=1.5)), name='TO% Total'
))
fig.update_layout(
    title=dict(text='Turnover Mensal', font=dict(size=16, color='white', family='Poppins'), x=0.5),
    paper_bgcolor='#111111', plot_bgcolor='#111111', font=dict(color='white', family='Poppins'),
    xaxis=dict(showgrid=False, tickfont=dict(size=11)),
    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.08)', ticksuffix='%', tickfont=dict(size=11)),
    height=380, margin=dict(l=40, r=40, t=50, b=40), hovermode='x unified'
)
resultado = fig
```
Após o gráfico, tabela markdown por FY: | FY | Mês | HC | Inativos | TO% Inv | TO% Vol | TO% Total |""",

            "🌈 Diversidade": """Indicadores de diversidade dos ATIVOS com MoM e YoY.
Calcule para mes_ref, mes_mom e mes_yoy: HC, Masculino, Feminino, Pretos, Pretos & Pardos, PCD, +46.
Formato: **INDICADOR**: X (X%) | MoM: ▲/▼ X% | YoY: ▲/▼ X%
Use apenas markdown.""",

            "⏱️ Tempo de Casa (Ativos)": """Tempo médio de casa dos ATIVOS no mês mais recente.
Calcule: média geral, distribuição por faixa (<1, 1-2, 2-5, 5-10, >10 anos), Top 3 áreas.
Apresente média, tabela por faixa com %, Top 3. Use apenas markdown.""",

            "⏱️ Tempo de Casa (Inativos)": """Tempo médio de casa dos INATIVOS nos últimos 12 meses.
Calcule: média geral, distribuição por faixa, comparativo Inv vs Vol.
Use apenas markdown.""",
        }

        for label, prompt in PROMPTS.items():
            if st.button(label, use_container_width=True, key=f"btn_{label[:20]}"):
                st.session_state["pergunta_rapida"] = prompt

        st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sb-section">Sessão</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("↺ Nova conversa", use_container_width=True):
                st.session_state["historico"] = []
                st.session_state["mensagens"] = []
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
    section[data-testid="stMain"] > div { background: #0f0f11 !important; }
    section[data-testid="stMain"] * { font-family: 'Poppins', sans-serif !important; }
    div[data-testid="stChatMessage"] {
        background: #ffffff !important; border: 1px solid rgba(0,0,0,0.06) !important;
        border-radius: 12px !important; margin-bottom: 12px !important; color: #1a1a1a !important;
    }
    div[data-testid="stChatMessage"] p,
    div[data-testid="stChatMessage"] li,
    div[data-testid="stChatMessage"] span { color: #1a1a1a !important; }
    div[data-testid="stChatMessage"] strong { color: #111111 !important; }
    div[data-testid="stChatInput"] textarea {
        background: #ffffff !important; border: 1px solid rgba(0,0,0,0.12) !important;
        border-radius: 12px !important; color: #1a1a1a !important;
        font-family: 'Poppins', sans-serif !important; font-size: 13px !important;
    }
    div[data-testid="stChatInput"] textarea::placeholder { color: #888 !important; }
    div[data-testid="stChatInput"] textarea:focus { border-color: rgba(210,45,65,0.5) !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('''
    <div style="background:linear-gradient(135deg,#7a0a1e 0%,#a0102a 40%,#6b0a1a 100%);padding:20px 28px 16px;margin-bottom:8px;border-radius:12px">
        <div style="font-family:Poppins,sans-serif;font-size:20px;font-weight:800;text-transform:uppercase;letter-spacing:0.5px;line-height:1.2;color:#ffffff">
            Pessoas &amp; Cultura
            <span style="font-family:Poppins,sans-serif;font-size:11px;font-weight:500;color:rgba(255,255,255,0.55);letter-spacing:2px;margin-left:10px">| HR Analytics</span>
        </div>
        <div style="font-family:Poppins,sans-serif;font-size:10px;color:rgba(255,255,255,0.5);letter-spacing:1px;text-transform:uppercase;margin-top:4px">
            Faça perguntas sobre os dados de colaboradores ativos e inativos
        </div>
    </div>
    ''', unsafe_allow_html=True)

    for msg in st.session_state.get("mensagens", []):
        avatar = "🧑" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    pergunta_rapida = st.session_state.pop("pergunta_rapida", None)
    pergunta = st.chat_input("Ex.: Quantos colaboradores ativos temos por área?") or pergunta_rapida

    if pergunta:
        st.session_state["mensagens"].append({"role": "user", "content": pergunta})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(pergunta)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Analisando dados..."):
                empresas_ativas = df["EMPRESA"].dropna().unique().tolist() if "EMPRESA" in df.columns else []
                ativos_atual    = len(df[df["STATUS_TIPO"] == "ATIVO"])   if "STATUS_TIPO" in df.columns else 0
                inativos_atual  = len(df[df["STATUS_TIPO"] == "INATIVO"]) if "STATUS_TIPO" in df.columns else 0
                total_atual     = len(df)

                contexto_filtros = f"""
CONTEXTO ATUAL DO DATAFRAME (após filtros da sidebar):
- Empresas no df: {sorted(empresas_ativas)}
- Total de registros: {total_atual}
- Ativos: {ativos_atual}
- Inativos: {inativos_atual}
- Mês de referência dos cards: {mes_ref_label}

IMPORTANTE: Use SEMPRE estes números como referência para headcount atual.
"""
                try:
                    resposta = rodar_agente(
                        pergunta         = pergunta,
                        historico        = st.session_state.get("historico", []),
                        df               = df,
                        contexto_filtros = contexto_filtros
                    )
                except Exception as e:
                    erro_str = str(e).lower()
                    if any(k in erro_str for k in ("429", "quota", "rate", "resource_exhausted")):
                        resposta = (
                            "⚠️ **Limite de requisições da API Gemini atingido.**\n\n"
                            "Aguarde **1 minuto** e tente novamente. "
                            "O plano gratuito permite 15 requisições/minuto com o Gemini Flash."
                        )
                    else:
                        resposta = (
                            f"❌ **Erro inesperado ao processar sua pergunta.**\n\n"
                            f"Detalhe: `{str(e)[:300]}`"
                        )

            if isinstance(resposta, str) and resposta.startswith("__PLOTLY__:"):
                import plotly.io as pio
                fig = pio.from_json(resposta.replace("__PLOTLY__:", ""))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.markdown(resposta)

        st.session_state["mensagens"].append({
            "role": "assistant",
            "content": resposta if not resposta.startswith("__PLOTLY__:") else "📉 *Gráfico gerado — veja acima*"
        })
        st.session_state["historico"].append({"role": "user",      "content": pergunta})
        st.session_state["historico"].append({
            "role": "assistant",
            "content": resposta if not resposta.startswith("__PLOTLY__:") else "Gráfico de Turnover gerado com sucesso."
        })

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
        st.info("Verifique se o Parquet foi enviado ao GitHub e se o GITHUB_TOKEN está configurado nos Secrets.")
        return

    tela_chat(df)


if __name__ == "__main__":
    main()
