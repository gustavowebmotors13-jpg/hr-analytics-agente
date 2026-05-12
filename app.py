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
#    GITHUB_TOKEN      = "ghp_..."
#
#  Para gerar o hash da senha (rode no terminal):
#    python -c "import hashlib; print(hashlib.md5('SUA_SENHA'.encode()).hexdigest())"
# =============================================================

import os
import hashlib
import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime
import anthropic

# ── CONFIGURAÇÕES ─────────────────────────────────────────────
st.set_page_config(
    page_title="HR Analytics · Webmotors",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

MODEL = "claude-sonnet-4-20250514"

# ── FONTE DE DADOS — Headcount_Consolidado.parquet ────────────
# Gerado pelo ETL Ativo_e_Inativos.py e enviado automaticamente ao GitHub
PARQUET_URL = (
    "https://raw.githubusercontent.com/gustavowebmotors13-jpg/"
    "hr-analytics-agente/main/Headcount_Consolidado.parquet"
)

# Hash da senha — lido do Streamlit Secrets
APP_PASSWORD_HASH = st.secrets.get(
    "APP_PASSWORD_HASH",
    hashlib.md5("demo123".encode()).hexdigest()
)

ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))


# ── CARREGAMENTO DOS DADOS ────────────────────────────────────
@st.cache_data(ttl=3600)  # Recarrega automaticamente a cada 1h
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

    # Usa STATUS_TIPO (coluna adicionada pelo ETL para distinguir ativos/inativos)
    ativos   = len(df[df["STATUS_TIPO"] == "ATIVO"])   if "STATUS_TIPO" in df.columns else "?"
    inativos = len(df[df["STATUS_TIPO"] == "INATIVO"]) if "STATUS_TIPO" in df.columns else "?"

    # Data de extração do ETL
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
- Coluna DATA: primeiro dia do mês de referência (para ativos = mês do arquivo; para inativos = mês do desligamento)
- Coluna DATA DESLIGAMENTO: data de desligamento (apenas inativos)
- Coluna DATA DE ADMISSAO: data de admissão
- Coluna INICIATIVA: motivo do desligamento — valores: "INICIATIVA DA EMPRESA" (involuntário) ou "INICIATIVA DO EMPREGADO" (voluntário). Sempre use .str.upper().str.contains() para filtrar.
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
10. NUNCA use tags HTML (<span>, <div>, etc.) nas respostas — use apenas markdown puro.
11. Para destacar percentuais use apenas texto: ex. **15,0%** (involuntário) / **21,6%** (voluntário)
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
            "Use .str.upper() para filtros de texto. "
            "Para ativos use df[df['STATUS_TIPO']=='ATIVO'], "
            "para inativos use df[df['STATUS_TIPO']=='INATIVO']."
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
    client    = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
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
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    .block-container {
        padding: 2rem 1rem !important;
        max-width: 460px !important;
        width: 100% !important;
    }
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
        background:rgba(255,255,255,0.05) !important;
        border:1px solid rgba(255,255,255,0.08) !important;
        border-radius:10px !important; color:white !important;
        letter-spacing:3px !important; font-size:15px !important;
        padding:12px 16px !important;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color:rgba(210,45,65,0.5) !important;
        background:rgba(210,45,65,0.04) !important;
        box-shadow:none !important;
    }
    div[data-testid="stTextInput"] label {
        color:rgba(255,255,255,0.3) !important; font-size:9px !important;
        font-weight:700 !important; letter-spacing:2px !important;
        text-transform:uppercase !important;
    }
    small, .st-emotion-cache-1gulkj5, [data-testid="InputInstructions"],
    div[class*="InputInstructions"], div[class*="inputInstructions"],
    div[data-testid="stTextInput"] > div > div > div:last-child { display: none !important; }
    div[data-testid="stFormSubmitButton"] > button {
        background: rgba(210,45,65,0.35) !important;
        border: 1px solid rgba(210,45,65,0.55) !important;
        border-radius:10px !important;
        color: rgba(255,255,255,0.75) !important;
        font-size:11px !important; font-weight:700 !important;
        letter-spacing:1.5px !important; text-transform:uppercase !important;
        padding:12px !important; width:100% !important;
        transition:all 0.2s !important;
    }
    div[data-testid="stFormSubmitButton"] > button:hover {
        background: #c8253f !important;
        border-color: #c8253f !important;
        color: white !important;
    }
    div[data-testid="stAlert"] { border-radius:8px !important; font-size:12px !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('''
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
        section[data-testid="stSidebar"] {
            background: #0d0d0f !important;
            border-right: 1px solid rgba(255,255,255,0.06) !important;
        }
        section[data-testid="stSidebar"] * { font-family: 'Poppins', sans-serif !important; color: white !important; }
        button[data-testid="collapsedControl"] { display: none !important; }
        section[data-testid="stSidebarCollapseButton"] { display: none !important; }
        div[data-testid="stSidebarCollapseButton"] { display: none !important; }
        button[kind="header"] { display: none !important; }
        [title="keyboard_double_arrow_left"],
        [aria-label="keyboard_double_arrow_left"],
        button[title*="keyboard"] { display: none !important; }
        span[class*="material"] { display: none !important; }
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
        /* Botão limpar filtros — estilo distinto */
        section[data-testid="stSidebar"] button[data-testid="baseButton-secondary"]:has(div:contains("✕")) {
            background: rgba(230,57,70,0.08) !important;
            border: 1px solid rgba(230,57,70,0.25) !important;
            color: rgba(230,57,70,0.7) !important;
            font-size: 10px !important;
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

        # ── FILTROS (aplicados ANTES dos cards) ──────────────────
        st.markdown('<div class="sb-section" style="margin-top:4px">Filtros</div>', unsafe_allow_html=True)

        # Filtro de Empresa
        empresas_disponiveis = sorted(df["EMPRESA"].dropna().unique().tolist()) if "EMPRESA" in df.columns else []
        empresas_selecionadas = st.multiselect(
            "Empresa", options=empresas_disponiveis, default=empresas_disponiveis,
            key="filtro_empresa", label_visibility="collapsed", placeholder="Selecione empresas..."
        )
        if empresas_selecionadas:
            df = df[df["EMPRESA"].isin(empresas_selecionadas)]

        # Botão limpar filtros
        if st.button("✕  Limpar filtros", use_container_width=True, key="btn_limpar"):
            st.session_state.pop("filtro_empresa", None)
            st.rerun()

        # Label filtro ativo
        if empresas_selecionadas and len(empresas_selecionadas) < len(empresas_disponiveis):
            st.markdown(f'<div style="font-size:9px;color:rgba(230,57,70,0.8);margin-top:2px">🔴 {", ".join(empresas_selecionadas)}</div>', unsafe_allow_html=True)

        st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

        # ── CARDS (calculados APÓS filtros) ───────────────────────
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
            ativos_mes = inativos_mes = total_mes = 0; mes_ref_label = ""

        ultima_etl = df["DATA_EXTRACAO"].iloc[0] if "DATA_EXTRACAO" in df.columns and len(df) > 0 else datetime.now().strftime("%d/%m %H:%M")

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
        <div style="font-size:9px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:rgba(255,255,255,0.25);margin-bottom:6px">{mes_ref_label}</div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:8px">
            <div class="sb-stat">
                <div class="sb-stat-label">Total</div>
                <div class="sb-stat-value">{total_mes:,}</div>
            </div>
            <div class="sb-stat">
                <div class="sb-stat-label">Ativos</div>
                <div class="sb-stat-value">{ativos_mes:,}</div>
            </div>
            <div class="sb-stat">
                <div class="sb-stat-label">Inativos</div>
                <div class="sb-stat-value">{inativos_mes:,}</div>
            </div>
        </div>
        <div class="sb-stat" style="margin-bottom:0">
            <div class="sb-stat-label">Última atualização ETL</div>
            <div class="sb-stat-sub">{ultima_etl}</div>
        </div>
        <div class="sb-divider"></div>
        <div class="sb-section">Análises Rápidas</div>
        """, unsafe_allow_html=True)

        # ── Botão de Turnover destacado ───────────────────────────────────────
        PROMPT_TURNOVER = """Calcule o relatório de Turnover dos últimos 12 meses usando a coluna DATA.

Siga estes passos no código:
1. Converta DATA para datetime: df['_DATA_DT'] = pd.to_datetime(df['DATA'], dayfirst=True, errors='coerce')
2. Pegue o mês mais recente dos ATIVOS: mes_max = df[df['STATUS_TIPO']=='ATIVO']['_DATA_DT'].max()
3. Defina início da janela: mes_inicio = mes_max - pd.DateOffset(months=11)
4. Filtre inativos na janela: df_inat = df[(df['STATUS_TIPO']=='INATIVO') & (df['_DATA_DT'] >= mes_inicio) & (df['_DATA_DT'] <= mes_max)]
5. Filtre ativos na janela: df_at = df[(df['STATUS_TIPO']=='ATIVO') & (df['_DATA_DT'] >= mes_inicio) & (df['_DATA_DT'] <= mes_max)]
6. HC Médio: agrupe df_at por mês, conte por mês, tire a média
7. Involuntários: df_inat onde INICIATIVA.str.upper().str.contains('EMPRESA', na=False)
8. Voluntários: df_inat onde INICIATIVA.str.upper().str.contains('EMPREGADO', na=False)

Calcule e apresente em tabela markdown:
| Métrica | Valor |
- Período (ex: Mai/25 → Abr/26)
- Empresas consideradas (liste as únicas da coluna EMPRESA no df filtrado)
- HC Médio (12 meses)
- Desligamentos Involuntários
- Desligamentos Voluntários
- Turnover % Involuntário (1 casa decimal)
- Turnover % Voluntário (1 casa decimal)
- Turnover % Total (1 casa decimal)

Use apenas markdown — sem HTML."""

        st.markdown("""
        <style>
        div[data-testid="stSidebar"] button[kind="secondary"]:first-of-type {
            background: rgba(230,57,70,0.15) !important;
            border: 1px solid rgba(230,57,70,0.4) !important;
            color: #ff8090 !important;
            font-weight: 700 !important;
        }
        </style>
        """, unsafe_allow_html=True)

        if st.button("📊 Relatório de Turnover (12m)", use_container_width=True, key="btn_turnover"):
            st.session_state["pergunta_rapida"] = PROMPT_TURNOVER

        st.markdown('<div style="margin-bottom:4px"></div>', unsafe_allow_html=True)

        exemplos = [
            "Headcount total por empresa",
            "Quantos ativos temos hoje?",
            "Distribuição por gênero",
            "Top 5 áreas com mais pessoas",
            "Desligamentos este mês",
            "Headcount por senioridade",
            "Headcount por tipo de contrato",
            "Diversidade étnica dos ativos",
            "Colaboradores por FY",
            "Tempo de casa médio",
        ]
        for ex in exemplos:
            if st.button(ex, use_container_width=True, key=f"ex_{ex[:25]}"):
                st.session_state["pergunta_rapida"] = ex

        st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sb-section">Análises Rápidas</div>', unsafe_allow_html=True)

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
    div[data-testid="stChatMessage"] p { color: #e0e0e0 !important; }
    div[data-testid="stChatMessage"] { color: #e0e0e0 !important; }
    section[data-testid="stMain"] * { font-family: 'Poppins', sans-serif !important; }
    div[data-testid="stChatMessage"] {
        background: #ffffff !important;
        border: 1px solid rgba(0,0,0,0.06) !important;
        border-radius: 12px !important;
        margin-bottom: 12px !important;
        color: #1a1a1a !important;
    }
    div[data-testid="stChatMessage"] p,
    div[data-testid="stChatMessage"] li,
    div[data-testid="stChatMessage"] span { color: #1a1a1a !important; }
    div[data-testid="stChatMessage"] strong { color: #111111 !important; }
    div[data-testid="stChatInput"] textarea {
        background: #ffffff !important;
        border: 1px solid rgba(0,0,0,0.12) !important;
        border-radius: 12px !important;
        color: #1a1a1a !important;
        font-family: 'Poppins', sans-serif !important;
        font-size: 13px !important;
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

    # Renderiza histórico
    for msg in st.session_state.get("mensagens", []):
        avatar = "🧑" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # Captura pergunta digitada ou clicada na sidebar
    pergunta_rapida = st.session_state.pop("pergunta_rapida", None)
    pergunta = st.chat_input("Ex.: Quantos colaboradores ativos temos por área?") or pergunta_rapida

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
        st.info("Verifique se o Parquet foi enviado ao GitHub e se o GITHUB_TOKEN está configurado nos Secrets.")
        return

    tela_chat(df)


if __name__ == "__main__":
    main()
