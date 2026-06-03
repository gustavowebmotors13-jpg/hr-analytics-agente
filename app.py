# =============================================================
#  AGENTE ANALÍTICO DE HR — Webmotors
#  Backend: Google Gemini 1.5 Flash / Groq
#  Auth:    Microsoft Entra ID (SSO corporativo) via st.login()
#
#  Arquitetura de autenticação:
#  - st.login()  → redireciona para Microsoft Entra ID
#  - st.user     → expõe email, nome, etc. após login
#  - Restrição de domínio: só @webmotors.com.br acessa
#  - st.logout() → encerra sessão
#
#  Secrets necessários (.streamlit/secrets.toml):
#     [auth]
#     redirect_uri    = "https://SEU-APP.streamlit.app/oauth2callback"
#     cookie_secret   = "string-aleatoria-forte-32-chars"
#     client_id       = "xxxx-xxxx-xxxx-xxxx"       # Azure App Registration
#     client_secret   = "xxxx~xxxx~xxxx"             # Azure Client Secret
#     server_metadata_url = "https://login.microsoftonline.com/SEU-TENANT-ID/v2.0/.well-known/openid-configuration"
#
#     GEMINI_API_KEY  = "AIzaSy..."
#     GROQ_API_KEY    = "gsk_..."
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

# 🔄 CORREÇÃO: Leitura direta dos arquivos locais clonados pelo Streamlit Cloud
PARQUET_FILE = "Headcount_Consolidado.parquet"
HP_PARQUET_FILE = "HighPerformance_Consolidado.parquet"

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

# ── CARREGAMENTO DOS DADOS (CORRIGIDO PARA REPOSITÓRIO PRIVADO) ──
@st.cache_data(ttl=3600)
def carregar_dados() -> pd.DataFrame:
    """Carrega o headcount diretamente da raiz do sistema de arquivos local."""
    if os.path.exists(PARQUET_FILE):
        return pd.read_parquet(PARQUET_FILE)
    else:
        st.error(f"❌ Arquivo '{PARQUET_FILE}' não foi encontrado na raiz do projeto.")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def carregar_high_performance() -> pd.DataFrame:
    """Carrega o High Performance diretamente da raiz do sistema de arquivos local."""
    if os.path.exists(HP_PARQUET_FILE):
        return pd.read_parquet(HP_PARQUET_FILE)
    return pd.DataFrame()


# ══════════════════════════════════════════════════════════════
#  TELA DE LOGIN — Microsoft SSO
# ══════════════════════════════════════════════════════════════

def tela_login():
    """Tela de login com botão Microsoft via st.login() nativo."""
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

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Entrar com conta Microsoft", use_container_width=True):
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
    if st.button("← Sair e tentar outro login"):
        st.logout()


# ══════════════════════════════════════════════════════════════
#  UTILITÁRIOS DE CÁLCULO
# ══════════════════════════════════════════════════════════════

def _prep(df): df = df.copy(); df["_D"] = pd.to_datetime(df["DATA"], dayfirst=True, errors="coerce"); return df
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
    df_hc = df_hc.copy(); df_hp = df_hp.copy()
    df_hc["_CPF"] = df_hc["CPF"].apply(_norm_cpf)
    df_hp["_CPF"] = df_hp["CPF"].apply(_norm_cpf) if "CPF" in df_hp.columns else ""
    df_hc["_D"] = pd.to_datetime(df_hc["DATA"], dayfirst=True, errors="coerce")
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
#  AGENTE GROQ — Interface e Lógica de Chat reconstruída
# ══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Você é um assistente especializado em análise de dados de RH da Webmotors. 
Seu objetivo é ajudar os gestores e o time de People & Culture a entenderem os dados estruturados de headcount, turnover, diversidade e performance do grupo. 
Seja analítico, estratégico, focado em relações de causa e efeito, e use tom executivo pronto para apresentações à diretoria."""

# ── CONTROLE PRINCIPAL DE FLUXO (AUTENTICAÇÃO & EXECUÇÃO) ───────
if not st.user.is_logged_in:
    tela_login()
else:
    email_usuario = st.user.email
    
    # Validação rigorosa de domínio corporativo
    if not email_usuario.endswith(f"@{DOMINIO_PERMITIDO}"):
        tela_acesso_negado(email_usuario)
    else:
        # Carregamento local otimizado
        df_headcount = carregar_dados()
        df_high_perf = carregar_high_performance()
        
        # Estrutura de Navegação Lateral
        st.sidebar.image("https://www.webmotors.com.br/assets/img/webmotors_logo.png", width=160)
        st.sidebar.title("Navegação")
        st.sidebar.markdown(f"👤 **{st.user.name}**\n`{email_usuario}`")
        
        app_mode = st.sidebar.radio("Selecione o Módulo:", ["💬 Agente Analítico", "📊 Relatórios Diretos"])
        
        st.sidebar.markdown(f"📅 **Próximo 5º dia útil:**\n`{proximo_5_dia_util()}`")
        
        if st.sidebar.button("Log Out / Sair"):
            st.logout()
            
        # --- MÓDULO 1: AGENTE INTELIGENTE ---
        if app_mode == "💬 Agente Analítico":
            st.title("💬 Agente Analítico de HR")
            st.caption("Faça perguntas livres sobre os comportamentos e tendências do Headcount.")
            
            # Inicialização do histórico de mensagens
            if "messages" not in st.session_state:
                st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                
            # Exibe histórico do chat (ocultando prompt de sistema)
            for msg in st.session_state.messages:
                if msg["role"] != "system":
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])
                        
            # Entrada do usuário
            if user_prompt := st.chat_input("Ex: Qual foi a variação do Turnover Voluntário no último período?"):
                st.session_state.messages.append({"role": "user", "content": user_prompt})
                with st.chat_message("user"):
                    st.markdown(user_prompt)
                    
                with st.chat_message("assistant"):
                    if GROQ_API_KEY:
                        try:
                            client = Groq(api_key=GROQ_API_KEY)
                            
                            # Injeta sumários contextuais dos DataFrames direto no contexto do chat para o Agente responder com propriedade
                            contexto_dados = f"\n\nContexto de Ativos Atuais: {df_headcount.shape[0]} registros mapeados."
                            st.session_state.messages[0]["content"] = SYSTEM_PROMPT + contexto_dados
                            
                            response = client.chat.completions.create(
                                model="llama-3.3-70b-versatile",
                                messages=st.session_state.messages
                            )
                            output_text = response.choices[0].message.content
                            st.markdown(output_text)
                            st.session_state.messages.append({"role": "assistant", "content": output_text})
                        except Exception as err:
                            st.error(f"Erro na chamada do agente: {str(err)}")
                    else:
                        st.warning("⚠️ GROQ_API_KEY não localizada nas configurações de Secrets do Streamlit.")
                        
        # --- MÓDULO 2: RELATÓRIOS DIRETOS (BOTÕES AUTOMÁTICOS) ---
        elif app_mode == "📊 Relatórios Diretos":
            st.title("📊 Relatórios Diretos de Business Intelligence")
            st.write("Gere insights e visões tabulares instantâneas processadas 100% via Python local.")
            
            opcoes_analise = {
                "Turnover YoY (Comparativo Anual)": "turnover_yoy",
                "Headcount por Empresa": "hc_empresa",
                "Tipo de Contratação": "tipo_contrato",
                "Top 5 Áreas em Volume": "top5_areas",
                "Distribuição por Senioridade": "senioridade",
                "Desligamentos do Mês Vigente": "inativos",
                "Histórico Turnover Mensal (Tabela 12m)": "to_mensal",
                "Curva Turnover Mensal (Gráfico 24m)": "to_grafico",
                "Indicadores de Diversidade (MoM & YoY)": "diversidade",
                "Tempo de Casa (Colaboradores Ativos)": "tempo_casa_ativos",
                "Tempo de Casa (Colaboradores Inativos)": "tempo_casa_inativos",
                "Regrettable Turnover (Talentos HP)": "regrettable"
            }
            
            escolha = st.selectbox("Escolha a métrica que deseja consolidar:", list(opcoes_analise.keys()))
            
            if st.button("Executar Análise Corporativa", use_container_width=True):
                tipo_chave = opcoes_analise[escolha]
                
                with st.spinner("Compilando bases de dados..."):
                    resultado_md, figura_plotly = executar_analise(tipo_chave, df_headcount, df_high_perf)
                    
                    if figura_plotly:
                        st.plotly_chart(figura_plotly, use_container_width=True)
                        
                    if resultado_md:
                        st.markdown(resultado_md)
