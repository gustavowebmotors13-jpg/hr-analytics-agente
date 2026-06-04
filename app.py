# =============================================================
#  AGENTE ANALÍTICO DE HR — Webmotors
#  Backend: Google Gemini 1.5 Flash
#  Auth:    Microsoft Entra ID (SSO corporativo) via st.login()
#
#  Arquitetura de autenticação:
#  - st.login()  → redireciona para Microsoft Entra ID
#  - st.user     → expõe email, nome, etc. após login
#  - Restrição de domínio: só @webmotors.com.br acessa
#  - st.logout() → encerra sessão
#
#  Secrets necessários (.streamlit/secrets.toml):
#    [auth]
#    redirect_uri    = "https://SEU-APP.streamlit.app/oauth2callback"
#    cookie_secret   = "string-aleatoria-forte-32-chars"
#    client_id       = "xxxx-xxxx-xxxx-xxxx"       # Azure App Registration
#    client_secret   = "xxxx~xxxx~xxxx"             # Azure Client Secret
#    server_metadata_url = "https://login.microsoftonline.com/SEU-TENANT-ID/v2.0/.well-known/openid-configuration"
#
#    GEMINI_API_KEY  = "AIzaSy..."
#    GITHUB_TOKEN    = "ghp_..."
#
#  Configuração Azure (passo a passo no README):
#    1. Azure Portal → Microsoft Entra ID → App registrations → New registration
#    2. Supported account types: "Accounts in this organizational directory only"
#    3. Redirect URI: https://SEU-APP.streamlit.app/oauth2callback
#    4. Certificates & secrets → New client secret → copiar Value
#    5. Overview → copiar Application (client) ID e Directory (tenant) ID
# =============================================================

import os
import time
import pandas as pd
import streamlit as st
from datetime import datetime
from groq import Groq

# ── CONFIGURAÇÕES ─────────────────────────────────────────────
st.set_page_config(
    page_title="HR Analytics · Webmotors",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Domínio corporativo permitido — só este domínio acessa o app
DOMINIO_PERMITIDO = "webmotors.com.br"

PARQUET_URL = (
    "https://raw.githubusercontent.com/gustavowebmotors13-jpg/"
    "hr-analytics-agente/main/Headcount_Consolidado.parquet?v=20260603"
)
HP_PARQUET_URL = (
    "https://raw.githubusercontent.com/gustavowebmotors13-jpg/"
    "hr-analytics-agente/main/HighPerformance_Consolidado.parquet?v=20260603"
)

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))

# ── UTILITÁRIOS DE DATA / FY ──────────────────────────────────
def mes_para_fy(data: pd.Timestamp) -> str:
    if pd.isnull(data): return "OTHERS"
    ano_fy = data.year + 1 if data.month >= 7 else data.year
    return f"FY{str(ano_fy)[-2:]}"



# ── PRÓXIMO 5º DIA ÚTIL ───────────────────────────────────────
def proximo_5_dia_util() -> str:
    """Calcula o 5º dia útil do próximo mês (feriados nacionais Brasil)."""
    import holidays
    from datetime import date, timedelta
    hoje = date.today()
    # Primeiro dia do próximo mês
    if hoje.month == 12:
        primeiro = date(hoje.year + 1, 1, 1)
    else:
        primeiro = date(hoje.year, hoje.month + 1, 1)
    feriados = holidays.Brazil(years=primeiro.year)
    count = 0
    d = primeiro
    while True:
        if d.weekday() < 5 and d not in feriados:  # seg-sex e não feriado
            count += 1
            if count == 5:
                return d.strftime("%d/%m/%Y")
        d += timedelta(days=1)

# ── CARREGAMENTO DOS DADOS ────────────────────────────────────
@st.cache_data(ttl=3600)
def carregar_dados() -> pd.DataFrame:
    import requests, io
    r = requests.get(PARQUET_URL, timeout=60)
    r.raise_for_status()
    return pd.read_parquet(io.BytesIO(r.content))


@st.cache_data(ttl=3600)
def carregar_high_performance() -> pd.DataFrame:
    import requests, io
    try:
        r = requests.get(HP_PARQUET_URL, timeout=60)
        if r.status_code == 404: return pd.DataFrame()
        r.raise_for_status()
        return pd.read_parquet(io.BytesIO(r.content))
    except Exception:
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════
#  TELA DE LOGIN — Microsoft SSO
# ══════════════════════════════════════════════════════════════

def tela_login():
    """
    Tela de login com botão Microsoft.
    Usa st.login() nativo do Streamlit (>= 1.40) que redireciona
    para o fluxo OAuth2 do Microsoft Entra ID configurado nos secrets.
    """
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
    .lc-info strong { color:rgba(255,255,255,.65); }
    .lc-foot { margin-top:20px; padding-top:16px; border-top:1px solid rgba(255,255,255,.04); }
    .lc-foot-l1 { font-size:9px; font-weight:600; color:rgba(255,255,255,.18); text-transform:uppercase; letter-spacing:.8px; margin-bottom:2px; }
    .lc-foot-l2 { font-size:9px; color:rgba(200,37,63,.4); text-transform:uppercase; letter-spacing:.5px; }
    /* Botão Microsoft SSO */
    div[data-testid="stButton"] > button {
        background: rgba(255,255,255,.06) !important;
        border: 1px solid rgba(255,255,255,.12) !important;
        border-radius: 10px !important;
        color: white !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        letter-spacing: .5px !important;
        padding: 12px !important;
        width: 100% !important;
        transition: all .2s !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 10px !important;
    }
    div[data-testid="stButton"] > button:hover {
        background: rgba(0,120,212,.2) !important;
        border-color: rgba(0,120,212,.5) !important;
    }
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
      <div class="lc-info">
        🔐 <strong>Acesso restrito</strong><br>
        Este sistema é exclusivo para colaboradores Webmotors.<br>
        Utilize seu e-mail corporativo <strong>@webmotors.com.br</strong> para autenticar.
      </div>
    </div>
    ''', unsafe_allow_html=True)

    # Botão Microsoft SSO nativo do Streamlit
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Ícone Microsoft (SVG inline) + texto
        microsoft_svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 21 21">
          <rect x="1" y="1" width="9" height="9" fill="#f25022"/>
          <rect x="11" y="1" width="9" height="9" fill="#7fba00"/>
          <rect x="1" y="11" width="9" height="9" fill="#00a4ef"/>
          <rect x="11" y="11" width="9" height="9" fill="#ffb900"/>
        </svg>
        """
        # O st.login() redireciona para o fluxo Microsoft configurado nos secrets
        if st.button(f"Entrar com conta Microsoft", use_container_width=True):
            st.login()

    st.markdown('''
    <div class="lc-foot">
      <div class="lc-foot-l1">HR Analytics &amp; Operations | Webmotors SA</div>
      <div class="lc-foot-l2">Owner: Gustavo Pereira das Neves</div>
    </div>
    ''', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  TELA DE ACESSO NEGADO
# ══════════════════════════════════════════════════════════════

def tela_acesso_negado(email: str):
    """
    Exibida quando o usuário autenticou com Microsoft mas usa
    um domínio não corporativo (ex: gmail, hotmail, etc.)
    """
    st.markdown("""
    <style>
    [data-testid="stHeader"],[data-testid="stToolbar"],#MainMenu,footer { display:none !important; }
    section[data-testid="stMain"] {
        background: #0f0f11 !important;
        min-height:100vh; display:flex !important; align-items:center !important; justify-content:center !important;
    }
    .block-container { max-width:460px !important; }
    </style>
    """, unsafe_allow_html=True)

    st.error(f"🚫 **Acesso negado**")
    st.markdown(f"""
    O e-mail **`{email}`** não pertence ao domínio corporativo `@{DOMINIO_PERMITIDO}`.

    Este sistema é de uso exclusivo para colaboradores Webmotors.
    Entre em contato com o time de HR Analytics caso acredite que isso seja um erro.
    """)
    if st.button("← Sair e tentar outro login", key="btn_sair_login"):
        st.logout()


# ══════════════════════════════════════════════════════════════
#  UTILITÁRIOS DE CÁLCULO
# ══════════════════════════════════════════════════════════════

def _prep(df):
    df = df.copy()
    # DATA pode ser datetime ou string
    if df["DATA"].dtype == "object":
        df["_D"] = pd.to_datetime(df["DATA"], dayfirst=True, errors="coerce")
    else:
        df["_D"] = pd.to_datetime(df["DATA"], errors="coerce")
    # Normaliza STATUS_TIPO
    if "STATUS_TIPO" not in df.columns:
        if "STATUS" in df.columns:
            df["STATUS_TIPO"] = df["STATUS"].str.upper().str.strip()
        else:
            df["STATUS_TIPO"] = "ATIVO"
    else:
        df["STATUS_TIPO"] = df["STATUS_TIPO"].str.upper().str.strip()
    # Normaliza INICIATIVA para padrão antigo (EMPRESA/EMPREGADO)
    if "INICIATIVA" in df.columns:
        ini = df["INICIATIVA"].fillna("").str.upper()
        df["_INI_INV"] = ini.str.contains("EMPRESA", na=False)
        df["_INI_VOL"] = ini.str.contains("EMPREGADO", na=False)
    else:
        df["_INI_INV"] = False
        df["_INI_VOL"] = False
    return df
def _pct(v, t):  return round(v / t * 100, 1) if t > 0 else 0
def _var(a, b):  return round((a - b) / b * 100, 1) if b > 0 else 0
def _sinal(v):   return "▲" if v >= 0 else "▼"
def _fmt_anos(a):
    anos = int(a); meses = int((a - anos) * 12)
    return f"{anos} anos e {meses} meses"
def _norm_cpf(v):
    import re
    if not v or str(v).strip().lower() in ("nan", "none", ""): return ""
    s = re.sub(r'[.\-\s]', '', str(v).strip()); s = re.sub(r'\.0$', '', s)
    return s.zfill(11)


# ══════════════════════════════════════════════════════════════
#  CÁLCULOS — BOTÕES SIDEBAR (100% Python, zero API)
# ══════════════════════════════════════════════════════════════

def analise_turnover_yoy(df):
    df = _prep(df)
    mes_max = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    def _periodo(ini_off, fim_off):
        ini = mes_max - pd.DateOffset(months=ini_off); fim = mes_max - pd.DateOffset(months=fim_off)
        at = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] >= ini) & (df["_D"] <= fim)]
        inat = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] >= ini) & (df["_D"] <= fim)]
        hc_med = at.groupby("_D").size().mean() if len(at) > 0 else 0
        inv = int(inat["INICIATIVA"].str.upper().str.contains("EMPRESA", na=False).sum())
        vol = int(inat["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False).sum())
        ti = _pct(inv, hc_med); tv = _pct(vol, hc_med); tt = _pct(inv + vol, hc_med)
        label = f"{ini.strftime('%b/%y').upper()} → {fim.strftime('%b/%y').upper()}"
        return label, round(hc_med, 1), inv, vol, ti, tv, tt
    l0, hc0, i0, v0, ti0, tv0, tt0 = _periodo(23, 12)
    l1, hc1, i1, v1, ti1, tv1, tt1 = _periodo(11, 0)
    # Narrativa
    var_total = _var(tt1, tt0)
    var_vol   = _var(tv1, tv0)
    var_inv   = _var(ti1, ti0)
    s_total   = "crescimento" if var_total >= 0 else "redução"
    narrativa = (
        f"\n\n---\n"
        f"**📊 Análise:** No período atual o turnover total ficou em **{tt1}%**, "
        f"representando {s_total} de **{abs(var_total)}%** vs período anterior ({tt0}%). "
        f"O turnover voluntário ({'▲' if var_vol>=0 else '▼'} {abs(var_vol)}%) "
        f"{'merece atenção' if tv1 > tv0 else 'apresentou melhora'}, "
        f"enquanto o involuntário ({'▲' if var_inv>=0 else '▼'} {abs(var_inv)}%) "
        f"{'aumentou' if ti1 > ti0 else 'reduziu'} no comparativo."
    )
    tabela = (f"| Métrica | {l0} | {l1} |\n|---|---|---|\n"
            f"| HC Médio (12 meses) | {hc0} | {hc1} |\n"
            f"| Desligamentos Involuntários | {i0} | {i1} |\n"
            f"| Desligamentos Voluntários | {v0} | {v1} |\n"
            f"| Turnover % Involuntário | {ti0}% | {ti1}% |\n"
            f"| Turnover % Voluntário | {tv0}% | {tv1}% |\n"
            f"| Turnover % Total | {tt0}% | {tt1}% |\n")
    return tabela + narrativa, None

def analise_hc_empresa(df):
    df = _prep(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max(); mes_yoy = mes_ref - pd.DateOffset(years=1)
    ref = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)].groupby("EMPRESA").size()
    yoy = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_yoy)].groupby("EMPRESA").size()
    linhas = [f"**Headcount por Empresa — {mes_ref.strftime('%b/%y').upper()}**\n"]
    for emp in ref.index:
        atual = int(ref[emp]); ant = int(yoy.get(emp, 0))
        v = _var(atual, ant); s = _sinal(v)
        linhas.append(f"Temos **{atual} colaboradores** na empresa **{emp}**. {s} **{abs(v)}% YoY** ({mes_yoy.strftime('%b/%y').upper()}: {ant})")
    total_atual = int(ref.sum()); total_ant = int(yoy.sum())
    var_grupo = _var(total_atual, total_ant)
    linhas.append(
        f"\n---\n**📊 Análise:** O grupo soma **{total_atual} colaboradores** ativos, "
        f"{'crescimento' if var_grupo >= 0 else 'redução'} de **{abs(var_grupo)}% YoY** "
        f"vs {total_ant} no mesmo mês do ano anterior."
    )
    return "\n\n".join(linhas), None

def analise_tipo_contrato(df):
    df = _prep(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max(); mes_yoy = mes_ref - pd.DateOffset(years=1)
    ref = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)].groupby("TIPO CONTRATACAO").size()
    yoy = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_yoy)].groupby("TIPO CONTRATACAO").size()
    linhas = [f"**Tipo de Contratação — {mes_ref.strftime('%b/%y').upper()} vs {mes_yoy.strftime('%b/%y').upper()}**\n",
              "| Tipo de Contratação | Qtd Atual | Qtd YoY | Var % |", "|---|---|---|---|"]
    for tp in ref.index:
        atual = int(ref[tp]); ant = int(yoy.get(tp, 0)); v = _var(atual, ant); s = _sinal(v)
        linhas.append(f"| {tp} | {atual} | {ant} | {s} {abs(v)}% |")
    tot_v = _var(ref.sum(), yoy.sum())
    linhas.append(f"| **TOTAL** | **{int(ref.sum())}** | **{int(yoy.sum())}** | {_sinal(tot_v)} {abs(tot_v)}% |")
    return "\n".join(linhas), None

def analise_top5_areas(df):
    df = _prep(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    df_ref = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)]
    top5 = df_ref.groupby("AREA").size().sort_values(ascending=False).head(5); total = len(df_ref)
    linhas = [f"**Top 5 Áreas — {mes_ref.strftime('%b/%y').upper()}** (Total: {total})\n",
              "| # | Área | Headcount | % do Total |", "|---|---|---|---|"]
    for i, (area, qtd) in enumerate(top5.items(), 1):
        linhas.append(f"| {i}º | {area} | {int(qtd)} | {_pct(qtd, total)}% |")
    return "\n".join(linhas), None

def analise_senioridade(df):
    df = _prep(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    df_ref = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)]
    sen = df_ref.groupby("SENIORIDADE").size().sort_index(); total = len(df_ref)
    linhas = [f"**Headcount por Senioridade — {mes_ref.strftime('%b/%y').upper()}** (Total: {total})\n",
              "| Senioridade | Headcount | % |", "|---|---|---|"]
    for s, qtd in sen.items():
        linhas.append(f"| {s} | {int(qtd)} | {_pct(qtd, total)}% |")
    return "\n".join(linhas), None

def analise_inativos(df):
    df = _prep(df)
    mes_ref_inat = df[df["STATUS_TIPO"] == "INATIVO"]["_D"].max()
    mes_ant = mes_ref_inat - pd.DateOffset(months=1)
    mes_ref_ativ = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    inat_mes = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] == mes_ref_inat)]
    inat_ant = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] == mes_ant)]
    hc_ref = len(df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref_ativ)])
    total = len(inat_mes); ant = len(inat_ant)
    inv = int(inat_mes["INICIATIVA"].str.upper().str.contains("EMPRESA", na=False).sum())
    vol = int(inat_mes["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False).sum())
    to_pct = _pct(total, hc_ref); var_mom = total - ant; s = _sinal(var_mom)
    narrativa_inv = "**Involuntários** lideram" if inv > vol else "**Voluntários** lideram"
    narrativa = (
        f"\n---\n**📊 Análise:** {narrativa_inv} os desligamentos do mês. "
        f"O turnover de **{to_pct}%** {'está acima' if to_pct > 2 else 'está dentro'} da faixa saudável. "
        f"{'⚠️ Volume aumentou vs mês anterior.' if var_mom > 0 else '✅ Volume reduziu vs mês anterior.'}"
    )
    return (f"**Desligamentos — {mes_ref_inat.strftime('%b/%y').upper()}**\n\n"
            f"- **Total:** {total} ({s} {abs(var_mom)} vs mês anterior: {ant})\n"
            f"- **Involuntários:** {inv}\n- **Voluntários:** {vol}\n- **TO% do mês:** {to_pct}%\n"
            + narrativa), None

def analise_to_mensal(df):
    df = _prep(df)
    mes_max = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    meses = pd.date_range(start=(mes_max - pd.DateOffset(months=11)).replace(day=1), end=mes_max, freq="MS")
    linhas = ["**TO% Mensal — Últimos 12 meses**\n",
              "| Mês/Ano | HC | Inv | Vol | TO% Inv | TO% Vol | TO% Total |", "|---|---|---|---|---|---|---|"]
    t_inv = t_vol = 0; hc_list = []
    for mes in meses:
        at = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes)]
        inat = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] == mes)]
        hc = len(at)
        inv = int(inat["INICIATIVA"].str.upper().str.contains("EMPRESA", na=False).sum())
        vol = int(inat["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False).sum())
        ti = _pct(inv, hc); tv = _pct(vol, hc); tt = _pct(inv + vol, hc)
        linhas.append(f"| {mes.strftime('%b/%Y').upper()} | {hc} | {inv} | {vol} | {ti}% | {tv}% | {tt}% |")
        t_inv += inv; t_vol += vol
        if hc > 0: hc_list.append(hc)
    hc_med = round(sum(hc_list) / len(hc_list), 1) if hc_list else 0
    ti_ac = _pct(t_inv, hc_med); tv_ac = _pct(t_vol, hc_med); tt_ac = _pct(t_inv + t_vol, hc_med)
    linhas.append(f"| **ACUMULADO 12m** | **{hc_med}** | **{t_inv}** | **{t_vol}** | **{ti_ac}%** | **{tv_ac}%** | **{tt_ac}%** |")
    return "\n".join(linhas), None

def analise_to_grafico(df):
    import plotly.graph_objects as go
    df = _prep(df)
    mes_max = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    meses = pd.date_range(start=(mes_max - pd.DateOffset(months=23)).replace(day=1), end=mes_max, freq="MS")
    dados = []
    for mes in meses:
        at = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes)]
        inat = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] == mes)]
        hc = len(at)
        inv = int(inat["INICIATIVA"].str.upper().str.contains("EMPRESA", na=False).sum())
        vol = int(inat["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False).sum())
        tot = inv + vol
        fy = df[df["_D"] == mes]["FY"].iloc[0] if len(df[df["_D"] == mes]) > 0 else ""
        dados.append({"mes": mes, "hc": hc, "inv": inv, "vol": vol, "total": tot,
                      "to_pct": _pct(tot, hc), "to_inv": _pct(inv, hc), "to_vol": _pct(vol, hc), "fy": fy})
    df_to = pd.DataFrame(dados); df_to = df_to[df_to["hc"] > 0]
    labels = [m.strftime("%b/%y").upper() for m in df_to["mes"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=labels, y=df_to["to_pct"], fill="tozeroy", fillcolor="rgba(192,0,60,0.15)",
        line=dict(color="#C0003C", width=2.5), mode="lines+markers+text",
        text=[f"{v}%" for v in df_to["to_pct"]], textposition="top center",
        textfont=dict(size=11, color="white", family="Poppins"),
        marker=dict(size=8, color="#C0003C", line=dict(color="white", width=1.5)),
        name="TO% Total", hovertemplate="<b>%{x}</b><br>TO%: %{y}%<extra></extra>"
    ))
    fig.update_layout(
        title=dict(text="Turnover Mensal (24 meses)", font=dict(size=16, color="white", family="Poppins"), x=0.5),
        paper_bgcolor="#111111", plot_bgcolor="#111111",
        font=dict(color="white", family="Poppins"),
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", ticksuffix="%", tickfont=dict(size=11)),
        height=380, margin=dict(l=40, r=40, t=50, b=40), hovermode="x unified"
    )
    tabela = ["**Detalhamento por FY**\n", "| FY | Mês | HC | Inativos | TO% Inv | TO% Vol | TO% Total |", "|---|---|---|---|---|---|---|"]
    for _, row in df_to.sort_values("mes", ascending=False).iterrows():
        tabela.append(f"| {row['fy']} | {row['mes'].strftime('%b/%Y').upper()} | {int(row['hc'])} | {int(row['total'])} | {row['to_inv']}% | {row['to_vol']}% | {row['to_pct']}% |")
    return "\n".join(tabela), fig

def analise_diversidade(df):
    df = _prep(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    mes_mom = mes_ref - pd.DateOffset(months=1); mes_yoy = mes_ref - pd.DateOffset(years=1)
    def _m(sub):
        hc = len(sub)
        masc = int(sub["GENERO"].str.upper().str.contains("MASCULINO", na=False).sum()) if "GENERO" in sub.columns else 0
        fem = int(sub["GENERO"].str.upper().str.contains("FEMININO", na=False).sum()) if "GENERO" in sub.columns else 0
        pret = int(sub["ETNIA"].str.upper().str.contains("PRETO$|PRETO ", na=False).sum()) if "ETNIA" in sub.columns else 0
        pp = int(sub["ETNIA"].str.upper().str.contains("PRETO|PARDO", na=False).sum()) if "ETNIA" in sub.columns else 0
        pcd = int((sub["PCD"] == "SIM").sum()) if "PCD" in sub.columns else 0
        m46 = int((sub["+46"] == "SIM").sum()) if "+46" in sub.columns else 0
        return [hc, masc, fem, pret, pp, pcd, m46]
    r = _m(df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)])
    m = _m(df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_mom)])
    y = _m(df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_yoy)])
    nomes = ["HEADCOUNT", "MASCULINO", "FEMININO", "PRETOS", "PRETOS & PARDOS", "PCD", "FAIXA +46"]
    linhas = [f"**Diversidade — {mes_ref.strftime('%b/%y').upper()}**\n"]
    for i, nome in enumerate(nomes):
        vr = r[i]; vm = m[i]; vy = y[i]
        p = _pct(vr, r[0]) if i > 0 else 100
        vm_v = _var(vr, vm); vy_v = _var(vr, vy)
        linhas.append(f"**{nome}**: {vr} ({p}%) | MoM: {_sinal(vm_v)} {abs(vm_v)}% ({vm}) | YoY: {_sinal(vy_v)} {abs(vy_v)}% ({vy})")
    return "\n\n".join(linhas), None

def analise_tempo_casa_ativos(df):
    df = _prep(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    df_ref = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)].copy()
    df_ref["_ADM"] = pd.to_datetime(df_ref["DATA DE ADMISSAO"], dayfirst=True, errors="coerce")
    df_ref["_ANOS"] = (mes_ref - df_ref["_ADM"]).dt.days / 365.25
    df_ref = df_ref.dropna(subset=["_ANOS"]); total = len(df_ref); media = df_ref["_ANOS"].mean()
    faixas = [("<1 ano", df_ref[df_ref["_ANOS"] < 1]), ("1-2 anos", df_ref[(df_ref["_ANOS"] >= 1) & (df_ref["_ANOS"] < 2)]),
              ("2-5 anos", df_ref[(df_ref["_ANOS"] >= 2) & (df_ref["_ANOS"] < 5)]),
              ("5-10 anos", df_ref[(df_ref["_ANOS"] >= 5) & (df_ref["_ANOS"] < 10)]), (">10 anos", df_ref[df_ref["_ANOS"] >= 10])]
    linhas = [f"**Tempo de Casa — Ativos ({mes_ref.strftime('%b/%y').upper()})**\n",
              f"- **Média geral:** {_fmt_anos(media)} | Total: {total}\n", "| Faixa | Quantidade | % |", "|---|---|---|"]
    for nome, sub in faixas: linhas.append(f"| {nome} | {len(sub)} | {_pct(len(sub), total)}% |")
    return "\n".join(linhas), None

def analise_tempo_casa_inativos(df):
    df = _prep(df)
    mes_max = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max(); mes_ini = mes_max - pd.DateOffset(months=11)
    df_in = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] >= mes_ini) & (df["_D"] <= mes_max)].copy()
    df_in["_ADM"] = pd.to_datetime(df_in["DATA DE ADMISSAO"], dayfirst=True, errors="coerce")
    df_in["_DESL"] = pd.to_datetime(df_in["DATA DESLIGAMENTO"], dayfirst=True, errors="coerce")
    df_in["_ANOS"] = (df_in["_DESL"] - df_in["_ADM"]).dt.days / 365.25
    df_in = df_in.dropna(subset=["_ANOS"]); total = len(df_in); media = df_in["_ANOS"].mean() if total > 0 else 0
    faixas = [("<1 ano", df_in[df_in["_ANOS"] < 1]), ("1-2 anos", df_in[(df_in["_ANOS"] >= 1) & (df_in["_ANOS"] < 2)]),
              ("2-5 anos", df_in[(df_in["_ANOS"] >= 2) & (df_in["_ANOS"] < 5)]),
              ("5-10 anos", df_in[(df_in["_ANOS"] >= 5) & (df_in["_ANOS"] < 10)]), (">10 anos", df_in[df_in["_ANOS"] >= 10])]
    linhas = [f"**Tempo de Casa — Inativos ({mes_ini.strftime('%b/%y').upper()} → {mes_max.strftime('%b/%y').upper()})**\n",
              f"- **Média geral:** {_fmt_anos(media)} | Total: {total}\n", "| Faixa | Quantidade | % |", "|---|---|---|"]
    for nome, sub in faixas: linhas.append(f"| {nome} | {len(sub)} | {_pct(len(sub), total)}% |")
    return "\n".join(linhas), None

def analise_regrettable_turnover(df_hc, df_hp):
    if df_hp.empty:
        return ("⚠️ **Arquivo High Performance não encontrado.**\n\n"
                "Execute o ETL para gerar `HighPerformance_Consolidado.parquet`."), None
    if "CPF" not in df_hc.columns:
        return "⚠️ Coluna CPF não encontrada no Headcount.", None
    df_hc = _prep(df_hc); df_hp = df_hp.copy()
    df_hc["_CPF"] = df_hc["CPF"].apply(_norm_cpf)
    df_hp["_CPF"] = df_hp["CPF"].apply(_norm_cpf) if "CPF" in df_hp.columns else ""
    mes_ref = df_hc[df_hc["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    mes_yoy = mes_ref - pd.DateOffset(years=1)
    def _calcular(mes):
        fy_mes = mes_para_fy(mes)
        hp_fy = df_hp[df_hp["FY_HP"] == fy_mes] if "FY_HP" in df_hp.columns else df_hp
        cpfs_talentos = set(hp_fy[hp_fy["_CPF"] != ""]["_CPF"].unique())
        hc = len(df_hc[(df_hc["STATUS_TIPO"] == "ATIVO") & (df_hc["_D"] == mes)])
        inat_vol = df_hc[(df_hc["STATUS_TIPO"] == "INATIVO") & (df_hc["_D"] == mes) &
                         (df_hc["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False))]
        talentos_deslig = inat_vol[inat_vol["_CPF"].isin(cpfs_talentos)]
        qtd = len(talentos_deslig); to_pct = _pct(qtd, hc)
        detalhes = []
        for _, row in talentos_deslig.iterrows():
            cpf = row["_CPF"]; hp_row = hp_fy[hp_fy["_CPF"] == cpf]
            if not hp_row.empty:
                hp_tipo = hp_row.iloc[0].get("H_P", ""); nome_hp = hp_row.iloc[0].get("NOME_HP", row.get("NOME COMPLETO", ""))
            else:
                hp_tipo = ""; nome_hp = row.get("NOME COMPLETO", "")
            detalhes.append(f"{nome_hp} ({hp_tipo})" if hp_tipo else nome_hp)
        return hc, qtd, to_pct, detalhes, fy_mes
    hc_ref, reg_ref, to_ref, det_ref, fy_ref = _calcular(mes_ref)
    hc_yoy, reg_yoy, to_yoy, det_yoy, fy_yoy = _calcular(mes_yoy)
    var_yoy = _var(reg_ref, reg_yoy); s_yoy = _sinal(var_yoy)
    linhas = [f"**Regrettable Turnover — {mes_ref.strftime('%b/%y').upper()}**\n",
              f"*Desligamentos voluntários de talentos HP/Potencial — filtrado por FY*\n", "---",
              f"| Métrica | {mes_yoy.strftime('%b/%y').upper()} ({fy_yoy}) | {mes_ref.strftime('%b/%y').upper()} ({fy_ref}) |",
              "|---|---|---|", f"| HC Mês Vigente | {hc_yoy} | {hc_ref} |",
              f"| Desligamentos Vol. de Talentos | {reg_yoy} | {reg_ref} |",
              f"| Regrettable TO% | {to_yoy}% | {to_ref}% |", "",
              f"**Variação YoY:** {s_yoy} {abs(var_yoy)}% vs {mes_yoy.strftime('%b/%y').upper()}"]
    if det_ref:
        linhas.append(f"\n**Talentos desligados em {mes_ref.strftime('%b/%y').upper()} ({fy_ref}):**\n")
        for d in det_ref: linhas.append(f"- {d}")
    else:
        linhas.append(f"\n✅ Nenhum talento {fy_ref} desligado voluntariamente em {mes_ref.strftime('%b/%y').upper()}.")
    return "\n".join(linhas), None

def executar_analise(tipo, df, df_hp=None):
    try:
        mapa = {
            "turnover_yoy": lambda: analise_turnover_yoy(df),
            "hc_empresa": lambda: analise_hc_empresa(df),
            "tipo_contrato": lambda: analise_tipo_contrato(df),
            "top5_areas": lambda: analise_top5_areas(df),
            "senioridade": lambda: analise_senioridade(df),
            "inativos": lambda: analise_inativos(df),
            "to_mensal": lambda: analise_to_mensal(df),
            "diversidade": lambda: analise_diversidade(df),
            "tempo_casa_ativos": lambda: analise_tempo_casa_ativos(df),
            "tempo_casa_inativos": lambda: analise_tempo_casa_inativos(df),
            "regrettable": lambda: analise_regrettable_turnover(df, df_hp if df_hp is not None else pd.DataFrame()),
            "to_grafico": lambda: analise_to_grafico(df),
        }
        if tipo in mapa: return mapa[tipo]()
    except Exception as e:
        return f"❌ **Erro:** `{str(e)[:300]}`", None


# ══════════════════════════════════════════════════════════════
#  AGENTE GEMINI — perguntas livres
# ══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Você é um assistente especializado em análise de dados de RH da Webmotors.

DATAFRAMES DISPONÍVEIS:
df (Headcount — ativos e inativos):
- STATUS_TIPO: "ATIVO" ou "INATIVO"
- EMPRESA, AREA, DIRETORIA, CARGO, SENIORIDADE
- TIPO CONTRATACAO, GENERO, ETNIA
- DATA, DATA DESLIGAMENTO, DATA DE ADMISSAO
- INICIATIVA: "INICIATIVA DA EMPRESA" ou "INICIATIVA DO EMPREGADO"
- CPF, FY

df_hp (High Performance):
- CPF, NOME_HP, DIRETORIA_HP, CARGO_HP, REGIME
- H_P: "HP" ou "POTENCIAL"
- FY_HP: ano fiscal (FY25, FY26...)
- DPO_2022 a DPO_2025

Regras:
1. Para INICIATIVA use .str.upper().str.contains()
2. Responda em português brasileiro, markdown puro
3. Salve resultado na variável 'resultado'
"""

FERRAMENTAS = [
    {"name": "obter_schema", "description": "Retorna schema de df e df_hp. Use sempre como primeiro passo.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"name": "executar_pandas", "description": "Executa código Python/pandas em df e df_hp. Salve em 'resultado'.",
     "parameters": {"type": "object", "properties": {"codigo": {"type": "string"}}, "required": ["codigo"]}}
]

def _schema(df, df_hp):
    def _cols(d):
        return "\n".join(f"  {c} ({d[c].dtype}): ex. {', '.join(str(e) for e in d[c].dropna().unique()[:3])}" for c in d.columns)
    at = len(df[df["STATUS_TIPO"] == "ATIVO"]) if "STATUS_TIPO" in df.columns else "?"
    it = len(df[df["STATUS_TIPO"] == "INATIVO"]) if "STATUS_TIPO" in df.columns else "?"
    hp_fy = df_hp["FY_HP"].value_counts().to_dict() if "FY_HP" in df_hp.columns else {}
    return (f"=== df ===\nTotal: {len(df)} | Ativos: {at} | Inativos: {it}\n{_cols(df)}\n\n"
            f"=== df_hp ===\nTotal: {len(df_hp)} | por FY: {hp_fy}\n{_cols(df_hp)}")

def _exec_pandas(codigo, df, df_hp):
    try:
        lv = {"df": df, "df_hp": df_hp, "pd": pd}
        exec(codigo, {}, lv)
        res = lv.get("resultado", "Sem variável 'resultado'.")
        if isinstance(res, pd.DataFrame): return res.to_string(index=False, max_rows=50)
        if isinstance(res, pd.Series): return res.to_string(max_rows=50)
        try:
            import plotly.graph_objects as go
            if isinstance(res, go.Figure): return "__PLOTLY__:" + res.to_json()
        except Exception: pass
        return str(res)
    except Exception as e:
        return f"ERRO: {e}"

def rodar_agente_livre(pergunta, historico, df, df_hp, contexto=""):
    """Agente Groq: gera código Python com visualizações Plotly e cards HTML."""
    api_key = GROQ_API_KEY
    if not api_key:
        return "GROQ_API_KEY nao configurada.", None

    import pandas as pd, re

    df2 = df.copy()
    df2["_D"] = pd.to_datetime(df2["DATA"], dayfirst=True, errors="coerce")
    mes_ref = df2[df2["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    cols_hc = list(df.columns)
    emp_disponiveis = df2["EMPRESA"].dropna().unique().tolist() if "EMPRESA" in df2.columns else []
    dir_disponiveis = df2["DIRETORIA"].dropna().unique().tolist()[:8] if "DIRETORIA" in df2.columns else []

    prompt_codigo = f"""Você é analista Python de RH da Webmotors. Gere código Python que responde à pergunta com visualizações.

DADOS:
- df: {len(df)} linhas TOTAL (ativos + inativos de múltiplos meses)
- STATUS_TIPO: "ATIVO" (colaboradores ativos) ou "INATIVO" (desligados)
- Mês mais recente dos ATIVOS: {mes_ref.strftime("%b/%Y").upper()}
- Empresas disponíveis: {emp_disponiveis}
- Diretorias (amostra): {dir_disponiveis}
- ATENÇÃO: df tem {len(df[df["STATUS_TIPO"]=="ATIVO"]) if "STATUS_TIPO" in df.columns else "?"} registros ATIVOS e {len(df[df["STATUS_TIPO"]=="INATIVO"]) if "STATUS_TIPO" in df.columns else "?"} INATIVOS

REGRAS CRÍTICAS DOS DADOS:
- df["DATA"] string "DD/MM/YYYY" — converta: df["_D"] = pd.to_datetime(df["DATA"], dayfirst=True, errors="coerce")
- STATUS_TIPO: "ATIVO" ou "INATIVO"
- Involuntário: .str.upper().str.contains("EMPRESA", na=False)
- Voluntário: .str.upper().str.contains("EMPREGADO", na=False)
- NUNCA use len(df) como headcount — sempre filtre STATUS_TIPO=="ATIVO" E agrupe por mês

EXEMPLOS CORRETOS DE CÁLCULO:
# ATENÇÃO: df tem STATUS_TIPO="ATIVO" e STATUS_TIPO="INATIVO"
# NUNCA use len(df) — sempre filtre por STATUS_TIPO e mês
df_calc = df.copy(); df_calc["_D"] = pd.to_datetime(df_calc["DATA"], dayfirst=True, errors="coerce")

# Headcount atual (CORRETO):
mes_ref = df_calc[df_calc["STATUS_TIPO"]=="ATIVO"]["_D"].max()
hc_atual = df_calc[(df_calc["STATUS_TIPO"]=="ATIVO") & (df_calc["_D"]==mes_ref) & (df_calc["EMPRESA"]==empresa_filtro)].shape[0]
# ex: hc_atual = 529 para WEBMOTORS em MAY/2026

# HC por mês (CORRETO):
hc_mensal = df_calc[df_calc["STATUS_TIPO"]=="ATIVO"].groupby(["EMPRESA","_D"]).size()
media_hc = round(hc_mensal["WEBMOTORS"].mean(), 1)  # ex: 533.0

# Inativos por mês (CORRETO):
inat_mensal = df_calc[df_calc["STATUS_TIPO"]=="INATIVO"].groupby("_D").size()

# Turnover mensal (CORRETO):
at = df_calc[(df_calc["STATUS_TIPO"]=="ATIVO") & (df_calc["_D"]==mes_ref)].shape[0]
it = df_calc[(df_calc["STATUS_TIPO"]=="INATIVO") & (df_calc["_D"]==mes_ref)].shape[0]
to_pct = round(it/at*100, 1) if at > 0 else 0

# Últimos N meses (CORRETO):
meses = pd.date_range(end=mes_ref, periods=N, freq="MS")
dados = {{m: df_calc[(df_calc["STATUS_TIPO"]=="ATIVO") & (df_calc["_D"]==m)].shape[0] for m in meses}}

BIBLIOTECAS DISPONÍVEIS: pd (pandas), go (plotly.graph_objects)

IDENTIDADE VISUAL WEBMOTORS (OBRIGATÓRIO):
- Cor principal: #F2214B (vermelho Webmotors) — NÃO use azul ou Plotly
- Fundo: branco (#FFFFFF) com texto preto (#111111)
- Fonte: Poppins
- Use SEMPRE SVG/HTML puro para gráficos — NÃO use Plotly (fig)
- Gráficos de barra/coluna: SEMPRE ordenar do maior para o menor

PADRÃO HTML BARRA HORIZONTAL:
# Monte uma lista de tuplas (label, valor) ordenada maior→menor
# Depois use a função _build_bars abaixo para gerar o HTML
def _build_bars(titulo, itens):
    max_val = max(v for _, v in itens) or 1
    rows = ""
    for lbl, val in itens:
        pct = val / max_val * 100
        rows += (
            "<div style='margin-bottom:12px'>"
            "<div style='display:flex;justify-content:space-between;font-size:12px;"
            "font-weight:600;color:#333;margin-bottom:5px'>"
            f"<span>{lbl}</span><span style='color:#F2214B'>{val}</span></div>"
            "<div style='background:#f5f5f5;border-radius:4px;height:8px'>"
            f"<div style='background:#F2214B;width:{pct:.0f}%;height:8px;border-radius:4px'></div>"
            "</div></div>"
        )
    return (
        "<div style='font-family:Poppins,sans-serif;padding:20px;background:#fff;"
        "border-radius:12px;border:1px solid #eee'>"
        f"<div style='font-size:11px;font-weight:700;color:#999;letter-spacing:2px;"
        f"margin-bottom:16px'>{titulo}</div>{rows}</div>"
    )
# Exemplo de uso:
# itens = sorted([("WM TECNOLOGIA", 22), ("WM COMERCIAL", 13)], key=lambda x: -x[1])
# st_html = _build_bars("INATIVOS POR DIRETORIA — MAI/26", itens)

CARDS HTML (para 1-3 métricas):
st_html = f"<div style='background:#fff;border:1px solid #eee;border-radius:12px;padding:24px 28px;font-family:Poppins,sans-serif;border-left:4px solid #F2214B'><div style='font-size:11px;font-weight:600;color:#999;letter-spacing:2px;text-transform:uppercase'>TÍTULO</div><div style='font-size:42px;font-weight:900;color:#F2214B;margin:8px 0'>VALOR</div><div style='font-size:13px;color:#555'>CONTEXTO</div></div>"

VARIÁVEIS DE SAÍDA (defina as que usar):
- resultado: string markdown (sempre defina, mesmo que vazio "")
- st_html: string HTML para cards (opcional)
- fig: objeto plotly Figure (opcional)

REGRAS DE FORMATO POR TIPO DE PERGUNTA:
- 1 número simples (HC atual, total inativos, etc): card HTML com número grande + texto narrativo "HEADCOUNT: 529 | MoM: ▼ 3.1% (546) | YoY: ▲ 2.1% (518)" — SEM gráfico
- Ranking/agrupamento (top N, por diretoria, por área): st_html com barras horizontais SVG ordenado maior→menor
- Turnover: resultado markdown com bullet points incluindo MoM e YoY em pp  
- Sempre calcule MoM e YoY quando relevante

PERGUNTA: {pergunta}

Escreva APENAS código Python válido. Use pd e go já importados. Sem explicações."""

    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt_codigo}],
            temperature=0.1,
            max_tokens=2500,
        )
        codigo = resp.choices[0].message.content
        codigo = re.sub("```python", "", codigo)
        codigo = re.sub("```", "", codigo)
        codigo = codigo.strip()

        local_vars = {
            "df": df.copy(), "df_hp": df_hp.copy(),
            "pd": pd,
            "resultado": "", "st_html": None, "fig": None
        }
        def _build_bars(titulo, itens):
            max_val = max(v for _, v in itens) or 1
            rows = ""
            for lbl, val in itens:
                pct = val / max_val * 100
                rows += (
                    "<div style='margin-bottom:12px'>"
                    "<div style='display:flex;justify-content:space-between;font-size:12px;"
                    "font-weight:600;color:#333;margin-bottom:5px'>"
                    f"<span>{lbl}</span><span style='color:#F2214B'>{val}</span></div>"
                    "<div style='background:#f5f5f5;border-radius:4px;height:8px'>"
                    f"<div style='background:#F2214B;width:{pct:.0f}%;height:8px;border-radius:4px'></div>"
                    "</div></div>"
                )
            return (
                "<div style='font-family:Poppins,sans-serif;padding:20px;background:#fff;"
                "border-radius:12px;border:1px solid #eee'>"
                f"<div style='font-size:11px;font-weight:700;color:#999;letter-spacing:2px;"
                f"margin-bottom:16px'>{titulo}</div>{rows}</div>"
            )
        local_vars["_build_bars"] = _build_bars
        exec(codigo, {"pd": pd, "_build_bars": _build_bars}, local_vars)

        resultado  = str(local_vars.get("resultado", ""))
        st_html    = local_vars.get("st_html", None)
        fig        = local_vars.get("fig", None)

        # Monta retorno composto
        output_parts = []
        if st_html:
            output_parts.append(("html", st_html))
        if fig is not None:
            output_parts.append(("plotly", fig))
        if resultado and len(resultado) > 5:
            output_parts.append(("markdown", resultado))

        if output_parts:
            return output_parts

        # Fallback texto direto
        resp2 = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Analista RH Webmotors. Portugues, markdown, max 8 linhas. Tabelas para agrupamentos."},
                {"role": "user", "content": f"mes_ref={mes_ref.strftime('%b/%Y').upper()}, empresas={emp_disponiveis}. Pergunta: {pergunta}"}
            ],
            temperature=0.2, max_tokens=1024,
        )
        return [("markdown", resp2.choices[0].message.content)]

    except Exception as e:
        es = str(e).lower()
        if any(k in es for k in ("429", "quota", "rate", "limit")):
            return [("markdown", "Limite da API Groq atingido. Aguarde alguns segundos.")]
        try:
            client2 = Groq(api_key=api_key)
            resp3 = client2.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "Analista RH Webmotors. Portugues, direto, max 6 linhas."},
                    {"role": "user", "content": pergunta}
                ],
                temperature=0.3, max_tokens=512,
            )
            return [("markdown", resp3.choices[0].message.content)]
        except Exception:
            return [("markdown", f"Erro: {str(e)[:200]}")]




# ══════════════════════════════════════════════════════════════
#  TELA DE CHAT
# ══════════════════════════════════════════════════════════════

def tela_chat(df, df_hp, user_name: str, user_email: str):
    with st.sidebar:
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
        section[data-testid="stSidebar"] { background:#0d0d0f !important; border-right:1px solid rgba(255,255,255,.06) !important; }
        section[data-testid="stSidebar"] * { font-family:'Poppins',sans-serif !important; color:white !important; }
        section[data-testid="stSidebar"] .stButton button {
            background:rgba(255,255,255,.04) !important; border:1px solid rgba(255,255,255,.08) !important;
            border-radius:8px !important; color:rgba(255,255,255,.6) !important;
            font-size:11px !important; font-weight:500 !important; text-align:left !important;
            padding:8px 12px !important; transition:all .2s !important;
        }
        section[data-testid="stSidebar"] .stButton button:hover { background:rgba(230,57,70,.12) !important; border-color:rgba(230,57,70,.3) !important; color:white !important; }
        .sb-divider { height:1px; background:linear-gradient(90deg,transparent,rgba(230,57,70,.3),transparent); margin:12px 0; }
        .sb-section { font-size:9px; font-weight:700; letter-spacing:2px; text-transform:uppercase; color:rgba(255,255,255,.25) !important; margin:16px 0 8px; }
        .sb-stat { background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.06); border-radius:8px; padding:10px 12px; margin-bottom:8px; }
        .sb-stat-label { font-size:9px; font-weight:600; letter-spacing:1px; text-transform:uppercase; color:rgba(255,255,255,.3) !important; margin-bottom:2px; }
        .sb-stat-value { font-size:18px; font-weight:800; color:white !important; }
        .sb-stat-sub { font-size:10px; color:rgba(255,255,255,.3) !important; }
        .sb-user { background:rgba(192,0,60,.08); border:1px solid rgba(192,0,60,.2); border-radius:8px; padding:10px 12px; margin-bottom:8px; }
        .sb-user-name { font-size:12px; font-weight:700; color:white !important; }
        .sb-user-email { font-size:10px; color:rgba(255,255,255,.4) !important; }
        </style>
        """, unsafe_allow_html=True)

        # Filtros
        emp_disp = sorted(df["EMPRESA"].dropna().unique().tolist()) if "EMPRESA" in df.columns else []
        # Default: WEBMOTORS. Limpar volta para WEBMOTORS
        _wm_default = ["WEBMOTORS"] if "WEBMOTORS" in emp_disp else emp_disp[:1]
        if st.button("✕  Limpar filtros", use_container_width=True, key="btn_limpar"):
            for k in list(st.session_state.keys()):
                if "empresa" in k.lower(): del st.session_state[k]
            st.session_state["_emp_default"] = _wm_default
            st.rerun()

        _default_sel = st.session_state.get("_emp_default", _wm_default)
        _default_sel = [e for e in _default_sel if e in emp_disp] or _wm_default
        emp_sel = st.multiselect(
            "Empresa", options=emp_disp, default=_default_sel,
            key="ms_empresa",
            label_visibility="collapsed", placeholder="Selecione empresas..."
        )
        st.session_state["_emp_default"] = emp_sel
        if emp_sel:
            df = df[df["EMPRESA"].isin(emp_sel)]

        st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

        # Stats
        mes_ref_label = ""
        if "DATA" in df.columns and len(df) > 0:
            dfd = df.copy()
            dfd["_D"] = pd.to_datetime(dfd["DATA"], dayfirst=True, errors="coerce")
            # Detecta coluna de status — pode ser STATUS_TIPO ou STATUS
            # Usa _prep para normalizar STATUS_TIPO corretamente
            dfd = _prep(dfd)
            ativos_mask = dfd["STATUS_TIPO"] == "ATIVO"
            mma = dfd[ativos_mask]["_D"].max()
            mes_ref_label = mma.strftime("%b/%y").upper() if pd.notna(mma) else ""
            dfm = dfd[dfd["_D"] == mma]
            atm = len(dfm[dfm["STATUS_TIPO"] == "ATIVO"])
            inm = len(dfm[dfm["STATUS_TIPO"] == "INATIVO"])
        else: atm = inm = 0

        etl = df["DATA_EXTRACAO"].iloc[0] if "DATA_EXTRACAO" in df.columns and len(df) > 0 else datetime.now().strftime("%d/%m %H:%M")
        proxima_etl = proximo_5_dia_util()
        hp_info = ""
        if not df_hp.empty and "FY_HP" in df_hp.columns:
            for fy, qtd in df_hp["FY_HP"].value_counts().items(): hp_info += f"{fy}: {qtd} | "
            hp_info = hp_info.rstrip(" | ")
        hp_status = hp_info if hp_info else ("✔ carregado" if not df_hp.empty else "⚠ não carregado")

        # Card do usuário logado (via SSO)
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:8px;padding:4px 0 8px">
            <div style="width:30px;height:30px;background:rgba(192,0,60,.15);border:1px solid rgba(192,0,60,.3);border-radius:8px;display:flex;align-items:center;justify-content:center;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#E63946" stroke-width="2.5" stroke-linecap="round">
                    <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
                </svg>
            </div>
            <span style="font-size:15px;font-weight:800;letter-spacing:.8px;text-transform:uppercase;color:white">Webmotors</span>
        </div>
        <div class="sb-user">
            <div class="sb-user-name">👤 {user_name}</div>
            <div class="sb-user-email">{user_email}</div>
        </div>
        <div class="sb-divider"></div>
        <div style="font-size:9px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:rgba(255,255,255,.25);margin-bottom:6px">{mes_ref_label}</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">
            <div class="sb-stat"><div class="sb-stat-label">Ativos</div><div class="sb-stat-value">{atm:,}</div></div>
            <div class="sb-stat"><div class="sb-stat-label">Inativos</div><div class="sb-stat-value">{inm:,}</div></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:0">
            <div class="sb-stat"><div class="sb-stat-label">Última ETL</div><div class="sb-stat-sub">{etl}</div><div style="font-size:9px;color:rgba(192,0,60,.7);margin-top:2px">Próxima: {proxima_etl}</div></div>
            <div class="sb-stat"><div class="sb-stat-label">High Perf.</div><div class="sb-stat-sub">{hp_status}</div></div>
        </div>
        <div class="sb-divider"></div>
        <div class="sb-section">Análises Rápidas</div>
        """, unsafe_allow_html=True)

        BOTOES = [
            ("📊 Relatório de Turnover (12m)", "turnover_yoy"),
            ("⭐ Regrettable Turnover",         "regrettable"),
            ("🏢 Headcount por Empresa",        "hc_empresa"),
            ("📋 Tipo de Contrato",             "tipo_contrato"),
            ("🏆 Top 5 Áreas",                  "top5_areas"),
            ("📊 Headcount por Senioridade",    "senioridade"),
            ("🚪 Inativos",                     "inativos"),
            ("📈 TO% Mensal (Tabela)",          "to_mensal"),
            ("📉 TO% Gráfico + Tabela",         "to_grafico"),
            ("🌈 Diversidade",                  "diversidade"),
            ("⏱️ Tempo de Casa (Ativos)",       "tempo_casa_ativos"),
            ("⏱️ Tempo de Casa (Inativos)",     "tempo_casa_inativos"),
        ]
        LABEL_MAP = {tipo: label for label, tipo in BOTOES}
        for label, tipo in BOTOES:
            if st.button(label, use_container_width=True, key=f"btn_{tipo}"):
                st.session_state["analise_rapida"] = tipo

        st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sb-section">Sessão</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("↺ Nova conversa", use_container_width=True, key="btn_nova_conversa"):
                st.session_state.update({"historico": [], "mensagens": []}); st.rerun()
        with c2:
            # st.logout() encerra a sessão Microsoft SSO
            if st.button("→ Sair", use_container_width=True, key="btn_sair"):
                st.logout()

    # Área principal
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
    section[data-testid="stMain"] { background:#0f0f11 !important; }
    section[data-testid="stMain"] * { font-family:'Poppins',sans-serif !important; }
    div[data-testid="stChatMessage"] { background:#ffffff !important; border:1px solid rgba(0,0,0,.06) !important; border-radius:12px !important; margin-bottom:12px !important; }
    div[data-testid="stChatMessage"] p,div[data-testid="stChatMessage"] li,div[data-testid="stChatMessage"] span { color:#1a1a1a !important; }
    div[data-testid="stChatInput"] textarea { background:#ffffff !important; border:1px solid rgba(0,0,0,.12) !important; border-radius:12px !important; color:#1a1a1a !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f'''
    <div style="background:linear-gradient(135deg,#7a0a1e 0%,#a0102a 40%,#6b0a1a 100%);padding:20px 28px 16px;margin-bottom:8px;border-radius:12px">
        <div style="font-family:Poppins,sans-serif;font-size:20px;font-weight:800;text-transform:uppercase;letter-spacing:.5px;line-height:1.2;color:#ffffff">
            Pessoas &amp; Cultura
            <span style="font-family:Poppins,sans-serif;font-size:11px;font-weight:500;color:rgba(255,255,255,.55);letter-spacing:2px;margin-left:10px">| HR Analytics</span>
        </div>
        <div style="font-family:Poppins,sans-serif;font-size:10px;color:rgba(255,255,255,.5);letter-spacing:1px;text-transform:uppercase;margin-top:4px">
            Análises rápidas na sidebar · Perguntas livres no chat abaixo
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # ── Boas-vindas personalizadas ──────────────────────────────────────────
    if not st.session_state.get("mensagens"):
        import datetime, random, pytz
        tz_br = pytz.timezone("America/Sao_Paulo")
        hora = datetime.datetime.now(tz_br).hour
        saudacao = "Bom dia" if hora < 12 else "Boa tarde" if hora < 18 else "Boa noite"
        primeiro_nome = user_name.split()[0] if user_name else "!"
        frases = [
            "Dados são o novo RH — e você está no controle. 🚀",
            "Pessoas são o ativo mais valioso. Vamos entendê-las melhor. 💡",
            "Decisões baseadas em dados começam aqui. 📊",
            "O que não é medido, não é gerenciado. Mas hoje isso muda. 🎯",
            "People Analytics: onde ciência encontra estratégia de pessoas. 🔬",
            "Cada número conta uma história. Vamos ouvi-la juntos. 📖",
            "Insights de RH em segundos. Porque o seu tempo é precioso. ⚡",
        ]
        frase = random.choice(frases)
        st.markdown(f"""
        <div style="text-align:center;padding:48px 20px 24px">
            <div style="font-size:28px;font-weight:800;color:#c0003c;font-family:Poppins,sans-serif">
                {saudacao}, {primeiro_nome}! 👋
            </div>
            <div style="font-size:14px;color:#666;margin-top:10px;
                        font-style:italic;font-family:Poppins,sans-serif">
                {frase}
            </div>
            <div style="margin-top:20px;font-size:12px;color:#aaa;
                        font-family:Poppins,sans-serif">
                Use o sidebar para análises rápidas ou faça uma pergunta abaixo
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Histórico
    for msg in st.session_state.get("mensagens", []):
        avatar = "🧑" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar):
            if msg.get("tipo") == "plotly":
                import plotly.io as pio
                st.plotly_chart(pio.from_json(msg["fig_json"]), use_container_width=True)
            if msg.get("content"): st.markdown(msg["content"])

    # Análise rápida
    analise_tipo = st.session_state.pop("analise_rapida", None)
    if analise_tipo:
        label = LABEL_MAP.get(analise_tipo, analise_tipo)
        st.session_state["mensagens"].append({"role": "user", "content": label})
        with st.chat_message("user", avatar="🧑"): st.markdown(label)
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Calculando..."):
                texto, fig = executar_analise(analise_tipo, df, df_hp)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True); st.markdown(texto)
                import plotly.io as pio
                st.session_state["mensagens"].append({"role": "assistant", "tipo": "plotly",
                                                       "fig_json": pio.to_json(fig), "content": texto})
            else:
                st.markdown(texto)
                st.session_state["mensagens"].append({"role": "assistant", "content": texto})
        st.session_state.setdefault("historico", []).extend([{"role": "user", "content": label},
                                                              {"role": "assistant", "content": texto}])

    # Pergunta livre
    pergunta = st.chat_input("Faça uma pergunta livre sobre os dados...")
    if pergunta:
        st.session_state["mensagens"].append({"role": "user", "content": pergunta})
        with st.chat_message("user", avatar="🧑"): st.markdown(pergunta)
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Consultando Gemini..."):
                ctx = (f"Empresas: {sorted(df['EMPRESA'].dropna().unique().tolist())} | "
                       f"Ativos: {len(df[df['STATUS_TIPO']=='ATIVO'])} | "
                       f"Inativos: {len(df[df['STATUS_TIPO']=='INATIVO'])} | Mês ref: {mes_ref_label}") if "EMPRESA" in df.columns else ""
                try:
                    partes = rodar_agente_livre(pergunta, st.session_state.get("historico", []), df, df_hp, ctx)
                    if isinstance(partes, str):
                        partes = [("markdown", partes)]
                except Exception as e:
                    partes = [("markdown", f"Erro: {str(e)[:200]}")]

            resposta_texto = ""
            for tipo, conteudo in partes:
                if tipo == "html":
                    st.markdown(conteudo, unsafe_allow_html=True)
                elif tipo == "plotly":
                    st.plotly_chart(conteudo, use_container_width=True)
                elif tipo == "markdown":
                    st.markdown(conteudo)
                    resposta_texto += conteudo + "\n"
            if not resposta_texto:
                resposta_texto = "(visualizacao gerada)"

        st.session_state["mensagens"].append({"role": "assistant", "content": resposta_texto})
        st.session_state.setdefault("historico", []).extend([{"role": "user", "content": pergunta},
                                                              {"role": "assistant", "content": resposta_texto}])
        if len(st.session_state.get("historico", [])) > 20:
            st.session_state["historico"] = st.session_state["historico"][-20:]


# ══════════════════════════════════════════════════════════════
#  MAIN — fluxo de autenticação Microsoft SSO
# ══════════════════════════════════════════════════════════════

def main():
    # ── 1. Verifica se o usuário está logado via Microsoft SSO ──
    if not st.user.is_logged_in:
        tela_login()
        return

    # ── 2. Restrição de domínio corporativo ──────────────────
    user_email = getattr(st.user, "email", "") or ""
    user_name  = getattr(st.user, "name", "Colaborador") or "Colaborador"

    if not user_email.lower().endswith(f"@{DOMINIO_PERMITIDO}"):
        tela_acesso_negado(user_email)
        return

    # ── 3. Usuário autenticado e autorizado → carrega dados ──
    if "historico" not in st.session_state:
        st.session_state["historico"] = []
    if "mensagens" not in st.session_state:
        st.session_state["mensagens"] = []

    try:
        df = carregar_dados()
    except Exception as e:
        st.error(f"Erro ao carregar Headcount: {e}")
        st.info("Verifique se o Parquet foi enviado ao GitHub e se o GITHUB_TOKEN está configurado.")
        return

    df_hp = carregar_high_performance()
    tela_chat(df, df_hp, user_name=user_name, user_email=user_email)


if __name__ == "__main__":
    main()
