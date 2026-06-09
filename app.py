# =============================================================
#  AGENTE ANALÍTICO DE HR — Webmotors
#  Backend: Groq Llama 3.3 70B
#  Auth:    Microsoft Entra ID (SSO corporativo) via st.login()
# =============================================================

import os
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from groq import Groq

# ── CONFIGURAÇÕES ─────────────────────────────────────────────
st.set_page_config(
    page_title="HR Analytics · Webmotors",
    page_icon="https://raw.githubusercontent.com/gustavowebmotors13-jpg/hr-analytics-agente/main/webmotors_icon.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Splash / loading screen personalizada ─────────────────────
# Abordagem: CSS global esconde o app durante carregamento.
# Um componente iframe injeta o splash e script no documento pai.
import streamlit.components.v1 as _splash_comp

_SPLASH_HTML = """<!DOCTYPE html>
<html>
<head>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body { width:100%; height:100%; background:transparent; overflow:hidden; }
</style>
</head>
<body>
<script>
(function() {
  var doc = window.parent.document;
  var head = doc.head || doc.getElementsByTagName('head')[0];

  // ── 1. Injeta estilo da splash no documento pai ──────────────
  var style = doc.createElement('style');
  style.id = 'wm-splash-style';
  style.textContent = [
    '@import url("https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap");',
    '#wm-splash-overlay {',
    '  position:fixed; top:0; left:0; width:100vw; height:100vh;',
    '  background:',
    '    radial-gradient(ellipse at 25% 75%, rgba(192,0,60,.6) 0%, transparent 50%),',
    '    radial-gradient(ellipse at 78% 18%, rgba(100,0,30,.45) 0%, transparent 50%),',
    '    linear-gradient(150deg,#110509 0%,#1c0910 40%,#100716 70%,#07080f 100%);',
    '  display:flex; flex-direction:column; align-items:center; justify-content:center;',
    '  z-index:2147483647;',
    '  opacity:1; transition:opacity .55s ease;',
    '}',
    '#wm-splash-overlay.out { opacity:0; pointer-events:none; }',
    '#wm-splash-overlay::before {',
    '  content:""; position:absolute; inset:0;',
    '  background-image:radial-gradient(circle,rgba(255,255,255,.5) 1px,transparent 1px);',
    '  background-size:52px 52px; opacity:.08; pointer-events:none;',
    '}',
    '.wms-row { display:flex; align-items:center; gap:22px; margin-bottom:26px; }',
    '.wms-icon-box {',
    '  width:72px; height:72px; border-radius:18px;',
    '  background:rgba(255,255,255,.07);',
    '  border:1px solid rgba(255,255,255,.13);',
    '  display:flex; align-items:center; justify-content:center;',
    '  box-shadow:0 0 40px rgba(192,0,60,.4);',
    '}',
    '.wms-word {',
    '  font-family:"Poppins",sans-serif !important;',
    '  font-size:40px; font-weight:800;',
    '  color:#fff; letter-spacing:3px; text-transform:uppercase; line-height:1;',
    '}',
    '.wms-sub {',
    '  font-family:"Poppins",sans-serif;',
    '  font-size:11px; font-weight:600; color:rgba(255,255,255,.35);',
    '  letter-spacing:5px; text-transform:uppercase; margin-bottom:52px;',
    '}',
    '.wms-track { width:200px; height:2px; background:rgba(255,255,255,.08); border-radius:2px; overflow:hidden; }',
    '.wms-fill  {',
    '  height:2px; background:linear-gradient(90deg,#8b001f,#C0003C,#e8385a);',
    '  border-radius:2px; width:0%;',
    '  animation:wmFill 2.4s cubic-bezier(.4,0,.2,1) forwards;',
    '}',
    '@keyframes wmFill {',
    '  0%{width:0%} 50%{width:68%} 85%{width:90%} 100%{width:100%}',
    '}',
  ].join('\n');
  head.appendChild(style);

  // ── 2. Cria o overlay no documento pai ───────────────────────
  var div = doc.createElement('div');
  div.id = 'wm-splash-overlay';
  div.innerHTML = [
    '<div class="wms-row">',
    '  <div class="wms-icon-box">',
    '    <svg width="38" height="38" viewBox="0 0 38 38" fill="none">',
    '      <rect x="3" y="22" width="6" height="13" rx="2" fill="#C0003C"/>',
    '      <rect x="11" y="15" width="6" height="20" rx="2" fill="#e0284a" opacity=".9"/>',
    '      <rect x="19" y="7"  width="6" height="28" rx="2" fill="#C0003C"/>',
    '      <polyline points="6,26 14,18 22,10 30,4"',
    '        stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" opacity=".75"/>',
    '      <circle cx="30" cy="4" r="2.2" fill="white" opacity=".95"/>',
    '      <circle cx="30" cy="4" r="4" fill="white" opacity=".15"/>',
    '    </svg>',
    '  </div>',
    '  <span class="wms-word">WEBMOTORS</span>',
    '</div>',
    '<div class="wms-sub">Agente IA &nbsp;|&nbsp; HR Analytics</div>',
    '<div class="wms-track"><div class="wms-fill"></div></div>',
  ].join('');
  doc.body.appendChild(div);

  // ── 3. Remove quando o app estiver pronto ────────────────────
  function hide() {
    var el = doc.getElementById('wm-splash-overlay');
    if (!el) return;
    el.classList.add('out');
    setTimeout(function(){ if (el.parentNode) el.parentNode.removeChild(el); }, 600);
  }

  var MAX = 12000;
  var t0  = Date.now();
  var obs = new MutationObserver(function() {
    // App pronto = sidebar renderizado com conteúdo (botões/texto dentro)
    var sidebar = doc.querySelector('[data-testid="stSidebar"] [data-testid="stButton"]')
                  || doc.querySelector('[data-testid="stChatInput"]')
                  || doc.querySelector('[data-testid="stChatMessage"]')
                  || doc.querySelector('.sb-user');
    if (sidebar) { obs.disconnect(); setTimeout(hide, 600); return; }
    if (Date.now() - t0 > MAX) { obs.disconnect(); hide(); }
  });
  obs.observe(doc.body, { childList:true, subtree:true });
  setTimeout(function(){ obs.disconnect(); hide(); }, MAX);
})();
</script>
</body>
</html>"""

_splash_comp.html(_SPLASH_HTML, height=0)

DOMINIO_PERMITIDO = "webmotors.com.br"

PARQUET_URL = (
    "https://raw.githubusercontent.com/gustavowebmotors13-jpg/"
    "hr-analytics-agente/main/Headcount_Consolidado.parquet?v=20260603"
)
HP_PARQUET_URL = (
    "https://raw.githubusercontent.com/gustavowebmotors13-jpg/"
    "hr-analytics-agente/main/HighPerformance_Consolidado.parquet?v=20260603"
)
RS_PARQUET_URL = (
    "https://raw.githubusercontent.com/gustavowebmotors13-jpg/"
    "hr-analytics-agente/main/RS_Consolidado.parquet"
)

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))

# ── UTILITÁRIOS DE DATA / FY ──────────────────────────────────
def mes_para_fy(data: pd.Timestamp) -> str:
    if pd.isnull(data): return "OTHERS"
    ano_fy = data.year + 1 if data.month >= 7 else data.year
    return f"FY{str(ano_fy)[-2:]}"

# ── PRÓXIMO 5º DIA ÚTIL ───────────────────────────────────────
def proximo_5_dia_util() -> str:
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

@st.cache_data(ttl=3600)
def carregar_rs() -> pd.DataFrame:
    import requests, io
    try:
        r = requests.get(RS_PARQUET_URL, timeout=60)
        if r.status_code == 404: return pd.DataFrame()
        r.raise_for_status()
        return pd.read_parquet(io.BytesIO(r.content))
    except Exception:
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
    .lc-info strong { color:rgba(255,255,255,.65); }
    .lc-foot { margin-top:20px; padding-top:16px; border-top:1px solid rgba(255,255,255,.04); }
    .lc-foot-l1 { font-size:9px; font-weight:600; color:rgba(255,255,255,.18); text-transform:uppercase; letter-spacing:.8px; margin-bottom:2px; }
    .lc-foot-l2 { font-size:9px; color:rgba(200,37,63,.4); text-transform:uppercase; letter-spacing:.5px; }
    div[data-testid="stButton"] > button {
        background: rgba(255,255,255,.06) !important; border: 1px solid rgba(255,255,255,.12) !important;
        border-radius: 10px !important; color: white !important; font-size: 13px !important;
        font-weight: 600 !important; letter-spacing: .5px !important; padding: 12px !important;
        width: 100% !important; transition: all .2s !important;
    }
    div[data-testid="stButton"] > button:hover { background: rgba(0,120,212,.2) !important; border-color: rgba(0,120,212,.5) !important; }
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
    section[data-testid="stMain"] { background:#0f0f11 !important; min-height:100vh; display:flex !important; align-items:center !important; justify-content:center !important; }
    .block-container { max-width:460px !important; }
    </style>
    """, unsafe_allow_html=True)
    st.error("🚫 **Acesso negado**")
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
    if df["DATA"].dtype == "object":
        df["_D"] = pd.to_datetime(df["DATA"], dayfirst=True, errors="coerce")
    else:
        df["_D"] = pd.to_datetime(df["DATA"], errors="coerce")
    if "STATUS_TIPO" not in df.columns:
        if "STATUS" in df.columns:
            df["STATUS_TIPO"] = df["STATUS"].str.upper().str.strip()
        else:
            df["STATUS_TIPO"] = "ATIVO"
    else:
        df["STATUS_TIPO"] = df["STATUS_TIPO"].str.upper().str.strip()
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
#  HELPER: renderiza HTML dentro do chat usando iframe
#  ✅ SOLUÇÃO DEFINITIVA — st.components.v1.html() nunca falha
# ══════════════════════════════════════════════════════════════

def render_html_chat(html_content: str, height: int = 420):
    """
    Renderiza HTML estilizado dentro do contexto de chat.
    Usa st.components.v1.html() que funciona em qualquer contexto do Streamlit.
    """
    full_html = f"""
    <html><head>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
      * {{ box-sizing:border-box; margin:0; padding:0; font-family:'Poppins',sans-serif; }}
      body {{ background:transparent; padding:4px 2px; }}
    </style>
    </head><body>{html_content}</body></html>
    """
    components.html(full_html, height=height, scrolling=False)


# ══════════════════════════════════════════════════════════════
#  FUNÇÕES DE ANÁLISE — SIDEBAR (100% pandas, zero API)
# ══════════════════════════════════════════════════════════════

def _hc_medio_12m(df, mes_fim):
    """
    ✅ FIX: Cálculo canônico de HC Médio dos últimos 12 meses.
    Usa exatamente os mesmos 12 meses mensais — mesmo método usado
    em analise_turnover_yoy e nas perguntas livres do agente.
    mes_fim: último mês do período (inclusive).
    Retorna: (hc_medio, lista_de_tuplas[(mes, hc)])
    """
    meses = pd.date_range(
        start=(mes_fim - pd.DateOffset(months=11)).replace(day=1),
        end=mes_fim,
        freq="MS"
    )
    dados = []
    for mes in meses:
        hc = len(df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes)])
        dados.append((mes, hc))
    hcs = [hc for _, hc in dados if hc > 0]
    media = round(sum(hcs) / len(hcs), 1) if hcs else 0
    return media, dados


def analise_turnover_yoy(df):
    df = _prep(df)
    mes_max = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()

    def _periodo(mes_fim_offset, meses_janela=12):
        mes_fim = mes_max - pd.DateOffset(months=mes_fim_offset)
        mes_ini = mes_fim - pd.DateOffset(months=meses_janela - 1)
        mes_ini = mes_ini.replace(day=1)
        mes_fim = mes_fim.replace(day=1)

        # ✅ HC Médio: média dos HCs mensais dos 12 meses do período
        hc_med, _ = _hc_medio_12m(df, mes_fim)

        inat = df[
            (df["STATUS_TIPO"] == "INATIVO") &
            (df["_D"] >= mes_ini) &
            (df["_D"] <= mes_fim)
        ]
        inv = int(inat["INICIATIVA"].str.upper().str.contains("EMPRESA", na=False).sum())
        vol = int(inat["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False).sum())
        ti = _pct(inv, hc_med); tv = _pct(vol, hc_med); tt = _pct(inv + vol, hc_med)
        label = f"{mes_ini.strftime('%b/%y').upper()} → {mes_fim.strftime('%b/%y').upper()}"
        return label, round(hc_med, 1), inv, vol, ti, tv, tt

    l0, hc0, i0, v0, ti0, tv0, tt0 = _periodo(mes_fim_offset=12)
    l1, hc1, i1, v1, ti1, tv1, tt1 = _periodo(mes_fim_offset=0)

    var_total = _var(tt1, tt0); var_vol = _var(tv1, tv0); var_inv = _var(ti1, ti0)
    s_total = "crescimento" if var_total >= 0 else "redução"
    narrativa = (
        f"\n\n---\n**📊 Análise:** No período atual o turnover total ficou em **{tt1}%**, "
        f"representando {s_total} de **{abs(var_total)}%** vs período anterior ({tt0}%). "
        f"O turnover voluntário ({'▲' if var_vol>=0 else '▼'} {abs(var_vol)}%) "
        f"{'merece atenção' if tv1 > tv0 else 'apresentou melhora'}, "
        f"enquanto o involuntário ({'▲' if var_inv>=0 else '▼'} {abs(var_inv)}%) "
        f"{'aumentou' if ti1 > ti0 else 'reduziu'} no comparativo."
    )
    tabela = (
        f"| Métrica | {l0} | {l1} |\n|---|---|---|\n"
        f"| HC Médio (12 meses) | {hc0} | {hc1} |\n"
        f"| Desligamentos Involuntários | {i0} | {i1} |\n"
        f"| Desligamentos Voluntários | {v0} | {v1} |\n"
        f"| Turnover % Involuntário | {ti0}% | {ti1}% |\n"
        f"| Turnover % Voluntário | {tv0}% | {tv1}% |\n"
        f"| Turnover % Total | {tt0}% | {tt1}% |\n"
    )
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
    mes_yoy = mes_ref - pd.DateOffset(years=1)

    def _m(sub):
        hc   = len(sub)
        masc = int(sub["GENERO"].str.upper().str.contains("MASCULINO", na=False).sum()) if "GENERO" in sub.columns else 0
        fem  = int(sub["GENERO"].str.upper().str.contains("FEMININO", na=False).sum())  if "GENERO" in sub.columns else 0
        pret = int(sub["ETNIA"].str.upper().str.contains("^PRETO$", na=False).sum())    if "ETNIA" in sub.columns else 0
        pp   = int(sub["ETNIA"].str.upper().str.contains("PRETO|PARDO", na=False).sum()) if "ETNIA" in sub.columns else 0
        pcd  = int((sub["PCD"] == "SIM").sum())  if "PCD" in sub.columns else 0
        m46  = int((sub["+46"] == "SIM").sum())  if "+46" in sub.columns else 0
        return [hc, masc, fem, pret, pp, pcd, m46]

    r = _m(df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)])
    y = _m(df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_yoy)])

    specs = [
        ("HEADCOUNT",       r[0], y[0], None),
        ("MASCULINO",       r[1], y[1], r[0]),
        ("FEMININO",        r[2], y[2], r[0]),
        ("PRETOS",          r[3], y[3], r[0]),
        ("PRETOS & PARDOS", r[4], y[4], r[0]),
        ("PCD",             r[5], y[5], r[0]),
        ("FAIXA +46",       r[6], y[6], r[0]),
    ]

    cards_html = ""
    for label, vr, vy, total in specs:
        pct_str = f"{_pct(vr, total)}%" if total else ""
        yoy_delta = _var(vr, vy)
        yoy_cor   = "#2ecc71" if yoy_delta >= 0 else "#e74c3c"
        yoy_sinal = "▲" if yoy_delta >= 0 else "▼"
        yoy_str   = f'<span style="color:{yoy_cor};font-size:9px;font-weight:600">{yoy_sinal} {abs(yoy_delta)}% YoY ({vy})</span>'
        pct_badge = f'<div style="position:absolute;top:12px;right:14px;font-size:10px;font-weight:700;color:#ccc;background:#f5f5f5;border-radius:4px;padding:2px 6px">{pct_str}</div>' if pct_str else ""

        cards_html += f"""
        <div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:14px 16px;position:relative">
          <div style="font-size:9px;font-weight:700;letter-spacing:1.2px;color:#aaa;text-transform:uppercase;margin-bottom:6px">{label}</div>
          {pct_badge}
          <div style="font-size:32px;font-weight:800;color:#111;line-height:1;margin-bottom:8px">{vr:,}</div>
          <div style="border-top:1px solid #f0f0f0;padding-top:6px">{yoy_str}</div>
        </div>"""

    html = f"""
    <div style="font-family:Poppins,sans-serif;padding:4px 0 12px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px">
        <div style="width:3px;height:18px;background:#F2214B;border-radius:2px"></div>
        <span style="font-size:11px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">Diversidade — {mes_ref.strftime("%b/%y").upper()}</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">
        {cards_html}
      </div>
    </div>"""
    # ✅ retorna tupla especial para indicar HTML com altura
    return ("__HTML__", html, 460), None

def analise_tempo_casa_ativos(df):
    df = _prep(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    df_ref = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)].copy()
    df_ref["_ADM"] = pd.to_datetime(df_ref["DATA DE ADMISSAO"], dayfirst=True, errors="coerce")
    df_ref["_ANOS"] = (mes_ref - df_ref["_ADM"]).dt.days / 365.25
    df_ref = df_ref.dropna(subset=["_ANOS"]); total = len(df_ref); media = df_ref["_ANOS"].mean()
    faixas = [("<1 ano", df_ref[df_ref["_ANOS"] < 1]),
              ("1-2 anos", df_ref[(df_ref["_ANOS"] >= 1) & (df_ref["_ANOS"] < 2)]),
              ("2-5 anos", df_ref[(df_ref["_ANOS"] >= 2) & (df_ref["_ANOS"] < 5)]),
              ("5-10 anos", df_ref[(df_ref["_ANOS"] >= 5) & (df_ref["_ANOS"] < 10)]),
              (">10 anos", df_ref[df_ref["_ANOS"] >= 10])]
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
    faixas = [("<1 ano", df_in[df_in["_ANOS"] < 1]),
              ("1-2 anos", df_in[(df_in["_ANOS"] >= 1) & (df_in["_ANOS"] < 2)]),
              ("2-5 anos", df_in[(df_in["_ANOS"] >= 2) & (df_in["_ANOS"] < 5)]),
              ("5-10 anos", df_in[(df_in["_ANOS"] >= 5) & (df_in["_ANOS"] < 10)]),
              (">10 anos", df_in[df_in["_ANOS"] >= 10])]
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


# ── NOVAS FUNÇÕES — Internal Movement + Diversidade Detalhada ─────────────

def analise_internal_movement(df_hc, df_rs=None, mes_sel=None):
    """
    Lógica espelha exatamente o ETL (RS_ETL.py / _calcular_internal_movement):
    • Vagas Abertas → "Data do Alinhamento\n(Indicador Stop)" cai no mês
    • Internal Movement (POI) → "Data de Fechamento (Indicador Stop)" cai no mês
                                 E Fonte ∈ FONTES_POI
    • IM % → POI / Vagas × 100
    • Comparativo: mês vigente vs mesmo mês ano anterior (YoY)
    """
    COL_FONTE  = "Fonte"
    # Espelha FONTES_POI do ETL exatamente
    FONTES_POI = {"POI", "POI - EFETIVAÇÃO", "POI - CLTZAÇÃO",
                  "POI - EFETIVACAO", "POI - CLTZACAO",
                  "POI - CLTIZAÇÃO", "POI - CLTIZACAO"}

    df_hc = _prep(df_hc)
    ativos = df_hc[df_hc["STATUS_TIPO"] == "ATIVO"]
    _max_hc = ativos["_D"].max().replace(day=1) if not ativos.empty else pd.Timestamp.today().replace(day=1)
    # Respeita filtro global: usa mes_sel se fornecido, senão usa máximo do HC
    mes_vigente = mes_sel if mes_sel is not None else _max_hc
    mes_vigente = mes_vigente.replace(day=1)
    # YoY = mesmo mês do ano anterior
    mes_yoy = (mes_vigente - pd.DateOffset(years=1)).replace(day=1)

    def _hc(mes):
        return len(df_hc[(df_hc["_D"] == mes) & (df_hc["STATUS_TIPO"] == "ATIVO")])

    if df_rs is None or df_rs.empty:
        html_aviso = f"""
        <div style="font-family:Poppins,sans-serif;padding:4px 0 16px">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
            <div style="width:3px;height:18px;background:#F2214B;border-radius:2px"></div>
            <span style="font-size:11px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">
              Internal Movement — {mes_vigente.strftime("%b/%y").upper()}</span>
          </div>
          <div style="background:#fff8f0;border:1px solid #f5c842;border-radius:8px;padding:14px 16px;font-size:12px;color:#7a5c00">
            ⚠️ <b>RS_Consolidado.parquet</b> não encontrado no GitHub.<br><br>
            Execute o <b>RS_ETL.py</b> para gerar e publicar o arquivo.
          </div>
          <div style="margin-top:12px;background:#fafafa;border-radius:8px;padding:10px 14px">
            <div style="font-size:10px;font-weight:700;color:#888;text-transform:uppercase;margin-bottom:6px">HC Vigente</div>
            <div style="font-size:28px;font-weight:800;color:#111">{_hc(mes_vigente):,}</div>
          </div>
        </div>"""
        return ("__HTML__", html_aviso, 260), None

    df_rs = df_rs.copy()

    # ── Detecta coluna "Data do Alinhamento (Indicador Stop)" ─────────────
    col_alin = next(
        (c for c in df_rs.columns if "alinhamento" in c.lower()), None
    )
    # ── Detecta coluna "Data de Fechamento (Indicador Stop)" ──────────────
    col_fech = next(
        (c for c in df_rs.columns if "fechamento" in c.lower() and "indicador" in c.lower()), None
    )
    # Fallback: procura qualquer coluna de fechamento
    if col_fech is None:
        col_fech = next(
            (c for c in df_rs.columns if "fechamento" in c.lower()), None
        )

    # ── Parseia datas com pd.to_datetime robusto ─────────────────────────
    # Usa year+month em vez de Timestamp — imune a dtype/timezone/ns-vs-us
    if col_alin:
        _alin_raw = pd.to_datetime(df_rs[col_alin], dayfirst=True, errors="coerce")
        if _alin_raw.dt.tz is not None:
            _alin_raw = _alin_raw.dt.tz_localize(None)
        df_rs["_ALIN_ANO"] = _alin_raw.dt.year
        df_rs["_ALIN_MES"] = _alin_raw.dt.month
    else:
        df_rs["_ALIN_ANO"] = pd.NA
        df_rs["_ALIN_MES"] = pd.NA

    if col_fech:
        _fech_raw = pd.to_datetime(df_rs[col_fech], dayfirst=True, errors="coerce")
        if _fech_raw.dt.tz is not None:
            _fech_raw = _fech_raw.dt.tz_localize(None)
        df_rs["_FECH_ANO"] = _fech_raw.dt.year
        df_rs["_FECH_MES"] = _fech_raw.dt.month
    else:
        df_rs["_FECH_ANO"] = pd.NA
        df_rs["_FECH_MES"] = pd.NA

    # Normaliza Fonte
    if COL_FONTE in df_rs.columns:
        df_rs["_FONTE_UP"] = df_rs[COL_FONTE].fillna("").astype(str).str.upper().str.strip()
    else:
        df_rs["_FONTE_UP"] = ""

    def _stats_rs(mes_ts):
        """Compara por (ano, mês) — imune a dtype/timezone."""
        ano, mes = mes_ts.year, mes_ts.month

        # Vagas abertas = Data do Alinhamento no mês
        vagas = int(((df_rs["_ALIN_ANO"] == ano) & (df_rs["_ALIN_MES"] == mes)).sum())

        # Internal Movement = fechamentos no mês com Fonte = POI
        poi_mask = (
            (df_rs["_FECH_ANO"] == ano) &
            (df_rs["_FECH_MES"] == mes) &
            (df_rs["_FONTE_UP"].isin(FONTES_POI))
        )
        mov = int(poi_mask.sum())

        pct = _pct(mov, vagas)
        return {"hc": _hc(mes_ts), "vagas": vagas, "mov": mov, "pct": pct}

    cur = _stats_rs(mes_vigente)
    ant = _stats_rs(mes_yoy)

    # Debug info para rodapé
    alin_ok  = int(df_rs["_ALIN_ANO"].notna().sum())
    fech_ok  = int(df_rs["_FECH_ANO"].notna().sum())
    fonte_ok = int((df_rs["_FONTE_UP"] != "").sum())

    def _varcor(a, b):
        if b == 0: return '<span style="color:#aaa">—</span>'
        d = (a - b) / b * 100
        c = "#2ecc71" if d >= 0 else "#e74c3c"
        s = "▲" if d >= 0 else "▼"
        return f'<span style="color:{c};font-weight:600">{s} {abs(d):.1f}%</span>'

    nm_cur = mes_vigente.strftime("%b/%y").upper()
    nm_yoy = mes_yoy.strftime("%b/%y").upper()

    linhas_html = ""
    for label, vc, va in [
        ("HC – Mês Vigente",                          cur["hc"],    ant["hc"]),
        ("Vagas Abertas (Data do Alinhamento)",        cur["vagas"], ant["vagas"]),
        ("Internal Movement (Fechamento POI no mês)", cur["mov"],   ant["mov"]),
    ]:
        linhas_html += f"""
        <div style="display:grid;grid-template-columns:2fr 1fr 1fr;gap:6px;margin-bottom:6px">
          <div style="font-size:12px;color:#444;padding:8px 10px;background:#fafafa;border-radius:6px">{label}</div>
          <div style="font-size:13px;font-weight:600;color:#666;padding:8px;text-align:center;background:#fafafa;border-radius:6px">{va:,}</div>
          <div style="font-size:13px;font-weight:700;color:#111;padding:8px;text-align:center;background:#fff;border:1px solid #eee;border-radius:6px">{vc:,}</div>
        </div>"""

    # Nota metodológica sobre as colunas usadas
    nota_alin = col_alin if col_alin else "coluna não encontrada"
    nota_fech = col_fech if col_fech else "coluna não encontrada"

    html = f"""
    <div style="font-family:Poppins,sans-serif;padding:4px 0 16px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <div style="width:3px;height:18px;background:#F2214B;border-radius:2px"></div>
        <span style="font-size:11px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">
          Internal Movement — {nm_cur}</span>
        <span style="font-size:9px;color:#aaa;margin-left:4px">vs {nm_yoy} (YoY)</span>
      </div>
      <div style="display:grid;grid-template-columns:2fr 1fr 1fr;gap:6px;margin-bottom:8px">
        <div style="font-size:9px;font-weight:700;color:#bbb;text-transform:uppercase;padding:4px 10px;letter-spacing:.8px">Métrica</div>
        <div style="font-size:9px;font-weight:700;color:#bbb;text-transform:uppercase;padding:4px;text-align:center;letter-spacing:.8px">{nm_yoy}</div>
        <div style="font-size:9px;font-weight:700;color:#111;text-transform:uppercase;padding:4px;text-align:center;background:#f5f5f5;border-radius:4px;letter-spacing:.8px">{nm_cur}</div>
      </div>
      {linhas_html}
      <div style="display:grid;grid-template-columns:2fr 1fr 1fr;gap:6px;margin-top:4px;margin-bottom:14px">
        <div style="font-size:11px;font-weight:700;color:#fff;padding:10px 12px;background:#111;border-radius:6px;letter-spacing:.5px">INTERNAL MOVEMENT %</div>
        <div style="font-size:14px;font-weight:700;color:#fff;padding:10px;text-align:center;background:#333;border-radius:6px">{ant['pct']:.0f}%</div>
        <div style="font-size:18px;font-weight:800;color:#F2214B;padding:10px;text-align:center;background:#111;border-radius:6px">{cur['pct']:.0f}%</div>
      </div>
      <div style="background:#f5f5f5;border-radius:6px;padding:10px 14px;font-size:11px;color:#555;line-height:1.9">
        <b style="font-size:10px;letter-spacing:.5px;text-transform:uppercase">Variação YoY</b><br>
        Vagas abertas: {_varcor(cur['vagas'], ant['vagas'])} &nbsp;|&nbsp;
        POIs fechados: {_varcor(cur['mov'], ant['mov'])} &nbsp;|&nbsp;
        IM%: {_varcor(cur['pct'], ant['pct'])}
      </div>
      <div style="margin-top:8px;font-size:9px;color:#ccc;font-style:italic;letter-spacing:.3px">
        Vagas: col "{nota_alin}" ({alin_ok} datas) · POI: col "{nota_fech}" ({fech_ok} datas) · Fonte: {fonte_ok} linhas
      </div>
    </div>"""
    return ("__HTML__", html, 400), None


def analise_mulheres_empresa(df):
    df = _prep(df)
    ativos  = df[df["STATUS_TIPO"] == "ATIVO"]
    mes_ref = ativos["_D"].max()
    mes_ant = (mes_ref - pd.DateOffset(months=1)).replace(day=1)
    def _pct_f(sub):
        total = len(sub)
        fem   = len(sub[sub["GENERO"].str.upper() == "FEMININO"]) if "GENERO" in sub.columns else 0
        return total, fem, _pct(fem, total)
    hc_a, f_a, pct_a = _pct_f(ativos[ativos["_D"] == mes_ref])
    hc_b, f_b, pct_b = _pct_f(ativos[ativos["_D"] == mes_ant])
    delta = pct_a - pct_b
    cor   = "#2ecc71" if delta >= 0 else "#e74c3c"
    sinal = "▲" if delta >= 0 else "▼"
    html = f"""
    <div style="font-family:Poppins,sans-serif;padding:4px 0 12px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <div style="width:4px;height:22px;background:#F2214B;border-radius:2px"></div>
        <span style="font-size:13px;font-weight:700;letter-spacing:.5px;color:#111;text-transform:uppercase">% Mulheres na Empresa</span>
      </div>
      <div style="text-align:center;padding:24px 16px;background:#fafafa;border-radius:12px;margin-bottom:12px">
        <div style="font-size:56px;font-weight:800;color:#F2214B;line-height:1">{pct_a:.1f}%</div>
        <div style="font-size:13px;color:#666;margin-top:8px">{f_a} mulheres de {hc_a} colaboradores</div>
        <div style="font-size:12px;color:{cor};margin-top:8px;font-weight:600">
          {sinal} {abs(delta):.1f}pp vs mês anterior ({pct_b:.1f}%)</div>
      </div>
    </div>"""
    return ("__HTML__", html, 240), None


def analise_diversidade_detalhada(df):
    df = _prep(df)
    ativos    = df[df["STATUS_TIPO"] == "ATIVO"]
    mes_ref   = ativos["_D"].max()
    mes_ant12 = (mes_ref - pd.DateOffset(months=12)).replace(day=1)
    atual     = ativos[ativos["_D"] == mes_ref]
    ano_atras = ativos[ativos["_D"] == mes_ant12]

    def _etnia(sub, val):
        return len(sub[sub["ETNIA"].str.upper() == val]) if "ETNIA" in sub.columns else 0
    def _pcd_(sub):
        return len(sub[sub["PCD"].astype(str).str.upper().isin(["SIM","S","1","TRUE"])]) \
               if "PCD" in sub.columns else 0
    def _faixa(sub, mn):
        if "+46" in sub.columns:
            return len(sub[sub["+46"].astype(str).str.upper() == "SIM"])
        if "FAIXA_ETARIA" in sub.columns:
            return len(sub[sub["FAIXA_ETARIA"].astype(str).str.contains(rf"\+{mn}|{mn}\+", na=False)])
        return 0

    metricas = [
        ("✊", "Pretos",         _etnia(atual,"PRETO"),  _etnia(ano_atras,"PRETO")),
        ("✊", "Pretos+Pardos",  _etnia(atual,"PRETO") + _etnia(atual,"PARDO"),
                                  _etnia(ano_atras,"PRETO") + _etnia(ano_atras,"PARDO")),
        ("♿", "PCD",            _pcd_(atual),           _pcd_(ano_atras)),
        ("👴", "+46 anos",       _faixa(atual, 46),      _faixa(ano_atras, 46)),
    ]
    cards = ""
    for icon, label, vc, va in metricas:
        delta = vc - va
        cor   = "#2ecc71" if delta >= 0 else "#e74c3c"
        sinal = "▲" if delta >= 0 else "▼"
        cards += f"""
        <div style="background:#fafafa;border-radius:10px;padding:16px;text-align:center;border:1px solid #eee">
          <div style="font-size:20px;margin-bottom:4px">{icon}</div>
          <div style="font-size:10px;font-weight:700;color:#888;text-transform:uppercase;margin-bottom:8px">{label}</div>
          <div style="font-size:36px;font-weight:800;color:#111">{vc}</div>
          <div style="font-size:10px;color:{cor};font-weight:600;margin-top:6px">
            {sinal} {abs(delta)} vs mesmo mês ano anterior</div>
        </div>"""
    html = f"""
    <div style="font-family:Poppins,sans-serif;padding:4px 0 12px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <div style="width:4px;height:22px;background:#F2214B;border-radius:2px"></div>
        <span style="font-size:13px;font-weight:700;letter-spacing:.5px;color:#111;text-transform:uppercase">Diversidade — Recortes</span>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">{cards}</div>
    </div>"""
    return ("__HTML__", html, 320), None


def analise_mulheres_lideranca_yoy(df):
    df = _prep(df)
    ativos    = df[df["STATUS_TIPO"] == "ATIVO"]
    mes_ref   = ativos["_D"].max()
    mes_ant12 = (mes_ref - pd.DateOffset(months=12)).replace(day=1)
    COL_CARGO = next((c for c in df.columns if c.upper() in ("CARGO","FUNCAO","SENIORIDADE","NIVEL")), None)
    VALS_LIDER = {"GERENTE","DIRETOR","COORDENADOR","SUPERVISOR","HEAD","VP","C-LEVEL","LIDER","MANAGER"}
    def _lf(mes):
        sub = ativos[ativos["_D"] == mes]
        if COL_CARGO:
            sub = sub[sub[COL_CARGO].str.upper().str.strip().apply(lambda x: any(v in x for v in VALS_LIDER))]
        total = len(sub)
        fem   = len(sub[sub["GENERO"].str.upper() == "FEMININO"]) if "GENERO" in sub.columns else 0
        return total, fem, _pct(fem, total)
    tl_a, ml_a, pct_a = _lf(mes_ref)
    tl_b, ml_b, pct_b = _lf(mes_ant12)
    delta = pct_a - pct_b
    cor   = "#2ecc71" if delta >= 0 else "#e74c3c"
    sinal = "▲" if delta >= 0 else "▼"
    html = f"""
    <div style="font-family:Poppins,sans-serif;padding:4px 0 12px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <div style="width:4px;height:22px;background:#F2214B;border-radius:2px"></div>
        <span style="font-size:13px;font-weight:700;letter-spacing:.5px;color:#111;text-transform:uppercase">Mulheres em Liderança (YoY)</span>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px">
        <div style="background:#fafafa;border-radius:10px;padding:16px;text-align:center">
          <div style="font-size:10px;font-weight:700;color:#bbb;text-transform:uppercase;margin-bottom:8px">{mes_ant12.strftime("%b/%y").upper()}</div>
          <div style="font-size:32px;font-weight:800;color:#666">{pct_b:.1f}%</div>
          <div style="font-size:11px;color:#aaa;margin-top:4px">{ml_b} de {tl_b} líderes</div>
        </div>
        <div style="background:#111;border-radius:10px;padding:16px;text-align:center">
          <div style="font-size:10px;font-weight:700;color:#888;text-transform:uppercase;margin-bottom:8px">{mes_ref.strftime("%b/%y").upper()}</div>
          <div style="font-size:32px;font-weight:800;color:#F2214B">{pct_a:.1f}%</div>
          <div style="font-size:11px;color:#aaa;margin-top:4px">{ml_a} de {tl_a} líderes</div>
        </div>
      </div>
      <div style="background:#f0f0f0;border-radius:8px;padding:10px 14px;font-size:12px;text-align:center">
        Variação YoY: <span style="color:{cor};font-weight:700">{sinal} {abs(delta):.1f}pp</span>
      </div>
    </div>"""
    return ("__HTML__", html, 280), None


def analise_pretos_lideranca_yoy(df):
    df = _prep(df)
    ativos    = df[df["STATUS_TIPO"] == "ATIVO"]
    mes_ref   = ativos["_D"].max()
    mes_ant12 = (mes_ref - pd.DateOffset(months=12)).replace(day=1)
    COL_CARGO = next((c for c in df.columns if c.upper() in ("CARGO","FUNCAO","SENIORIDADE","NIVEL")), None)
    VALS_LIDER = {"GERENTE","DIRETOR","COORDENADOR","SUPERVISOR","HEAD","VP","C-LEVEL","LIDER","MANAGER"}
    def _lp(mes):
        sub = ativos[ativos["_D"] == mes]
        if COL_CARGO:
            sub = sub[sub[COL_CARGO].str.upper().str.strip().apply(lambda x: any(v in x for v in VALS_LIDER))]
        total  = len(sub)
        pretos = len(sub[sub["ETNIA"].str.upper() == "PRETO"]) if "ETNIA" in sub.columns else 0
        return total, pretos, _pct(pretos, total)
    tl_a, pr_a, pct_a = _lp(mes_ref)
    tl_b, pr_b, pct_b = _lp(mes_ant12)
    delta = pct_a - pct_b
    cor   = "#2ecc71" if delta >= 0 else "#e74c3c"
    sinal = "▲" if delta >= 0 else "▼"
    html = f"""
    <div style="font-family:Poppins,sans-serif;padding:4px 0 12px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <div style="width:4px;height:22px;background:#F2214B;border-radius:2px"></div>
        <span style="font-size:13px;font-weight:700;letter-spacing:.5px;color:#111;text-transform:uppercase">Pretos em Liderança (YoY)</span>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px">
        <div style="background:#fafafa;border-radius:10px;padding:16px;text-align:center">
          <div style="font-size:10px;font-weight:700;color:#bbb;text-transform:uppercase;margin-bottom:8px">{mes_ant12.strftime("%b/%y").upper()}</div>
          <div style="font-size:32px;font-weight:800;color:#666">{pct_b:.1f}%</div>
          <div style="font-size:11px;color:#aaa;margin-top:4px">{pr_b} de {tl_b} líderes</div>
        </div>
        <div style="background:#111;border-radius:10px;padding:16px;text-align:center">
          <div style="font-size:10px;font-weight:700;color:#888;text-transform:uppercase;margin-bottom:8px">{mes_ref.strftime("%b/%y").upper()}</div>
          <div style="font-size:32px;font-weight:800;color:#F2214B">{pct_a:.1f}%</div>
          <div style="font-size:11px;color:#aaa;margin-top:4px">{pr_a} de {tl_a} líderes</div>
        </div>
      </div>
      <div style="background:#f0f0f0;border-radius:8px;padding:10px 14px;font-size:12px;text-align:center">
        Variação YoY: <span style="color:{cor};font-weight:700">{sinal} {abs(delta):.1f}pp</span>
      </div>
    </div>"""
    return ("__HTML__", html, 280), None


# ══════════════════════════════════════════════════════════════
#  FUNÇÕES DE ANÁLISE — R&S (usa df_rs = RS_Consolidado.parquet)
# ══════════════════════════════════════════════════════════════

def _rs_prep(df_rs):
    """Prepara o DataFrame RS: parseia datas e normaliza colunas-chave."""
    df = df_rs.copy()
    COL_FECH  = "Data de Fechamento (Indicador Stop)"
    COL_ALIGN = "Data do Alinhamento\n(Indicador Stop)"
    for col in (COL_FECH, COL_ALIGN):
        if col in df.columns:
            raw = pd.to_datetime(df[col], errors="coerce")
            if raw.dt.tz is not None:
                raw = raw.dt.tz_localize(None)
            df[f"_ANO_{col[:4].upper()}"] = raw.dt.year
            df[f"_MES_{col[:4].upper()}"] = raw.dt.month
            df[col] = raw
    # TTH / TTF / TTD: converte para numérico preservando zeros válidos.
    # NaN = célula vazia na planilha = excluída automaticamente pelo pandas na média.
    # Zero = TTD/TTH genuinamente 0 (fechamento no mesmo dia) = INCLUÍDO na média.
    # Isso replica o comportamento do Excel: 337 / 18 = 18.7 ≈ 18.8 dias (Mai/26).
    for c in ("Time to Hire (Indicador Stop)", "Time to Fill (O inicio)", "Tempo em Definição"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
            # NÃO filtra zeros — apenas NaN são excluídos na média
    return df


def _rs_mes_vigente(df_rs):
    """Retorna o mês mais recente com vagas fechadas."""
    COL_FECH = "Data de Fechamento (Indicador Stop)"
    if COL_FECH not in df_rs.columns:
        return pd.Timestamp.today().replace(day=1)
    raw = pd.to_datetime(df_rs[COL_FECH], errors="coerce")
    if raw.dt.tz is not None:
        raw = raw.dt.tz_localize(None)
    mx = raw.max()
    return mx.replace(day=1) if pd.notna(mx) else pd.Timestamp.today().replace(day=1)


def _rs_vagas_fechadas(df_rs, ano, mes):
    """Filtra vagas fechadas em determinado mês/ano."""
    COL_FECH = "Data de Fechamento (Indicador Stop)"
    if COL_FECH not in df_rs.columns:
        return df_rs.iloc[0:0]
    raw = pd.to_datetime(df_rs[COL_FECH], errors="coerce")
    if raw.dt.tz is not None:
        raw = raw.dt.tz_localize(None)
    mask = (raw.dt.year == ano) & (raw.dt.month == mes)
    return df_rs[mask]


def _var_str(atual, ant):
    """Formata variação MoM/YoY com seta e cor HTML."""
    if ant == 0:
        return '<span style="color:#aaa">—</span>'
    v = round((atual - ant) / ant * 100, 1)
    cor = "#2ecc71" if v >= 0 else "#e74c3c"
    s   = "▲" if v >= 0 else "▼"
    return f'<span style="color:{cor};font-weight:700">{s} {abs(v):.1f}%</span>'


def _var_abs_str(atual, ant):
    """Variação absoluta com seta e cor."""
    d = atual - ant
    cor = "#2ecc71" if d >= 0 else "#e74c3c"
    s   = "▲" if d >= 0 else "▼"
    return f'<span style="color:{cor}">{s} {abs(d)}</span>'


def analise_rs_vagas_fechadas(df_rs, mes_sel=None):
    """Card: Total de Vagas Fechadas com MoM e YoY."""
    if df_rs is None or df_rs.empty:
        return ("__HTML__", "<div style='font-family:Poppins,sans-serif;padding:16px;color:#888'>⚠️ RS_Consolidado.parquet não carregado.</div>", 80), None

    df_rs = _rs_prep(df_rs)
    mv    = mes_sel if mes_sel is not None else _rs_mes_vigente(df_rs)
    ano, mes = mv.year, mv.month

    # Mês anterior e mesmo mês ano anterior
    mv_ant = (mv - pd.DateOffset(months=1)).replace(day=1)
    mv_yoy = (mv - pd.DateOffset(years=1)).replace(day=1)

    cur = len(_rs_vagas_fechadas(df_rs, ano, mes))
    ant = len(_rs_vagas_fechadas(df_rs, mv_ant.year, mv_ant.month))
    yoy = len(_rs_vagas_fechadas(df_rs, mv_yoy.year, mv_yoy.month))

    nm_cur = mv.strftime("%b/%y").upper()
    nm_ant = mv_ant.strftime("%b/%y").upper()
    nm_yoy = mv_yoy.strftime("%b/%y").upper()

    # TTH / TTF / TTD médio
    def _media(df_sub, col):
        if col not in df_sub.columns: return None
        v = pd.to_numeric(df_sub[col], errors="coerce").dropna()
        return round(v.mean(), 1) if len(v) > 0 else None

    def _media_mes(a, m, col):
        return _media(_rs_vagas_fechadas(df_rs, a, m), col)

    tth_c = _media_mes(ano, mes, "Time to Hire (Indicador Stop)")
    tth_a = _media_mes(mv_ant.year, mv_ant.month, "Time to Hire (Indicador Stop)")
    tth_y = _media_mes(mv_yoy.year, mv_yoy.month, "Time to Hire (Indicador Stop)")

    ttf_c = _media_mes(ano, mes, "Time to Fill (O inicio)")
    ttf_a = _media_mes(mv_ant.year, mv_ant.month, "Time to Fill (O inicio)")
    ttf_y = _media_mes(mv_yoy.year, mv_yoy.month, "Time to Fill (O inicio)")

    ttd_c = _media_mes(ano, mes, "Tempo em Definição")
    ttd_a = _media_mes(mv_ant.year, mv_ant.month, "Tempo em Definição")
    ttd_y = _media_mes(mv_yoy.year, mv_yoy.month, "Tempo em Definição")

    def _metric_card(titulo, valor, ant_v, yoy_v, nm_a, nm_y, sufixo=" dias"):
        v_str   = f"{valor:.0f}{sufixo}" if valor is not None else "—"
        mom_str = _var_str(valor or 0, ant_v or 0) if ant_v is not None else '<span style="color:#aaa">—</span>'
        yoy_str = _var_str(valor or 0, yoy_v or 0) if yoy_v is not None else '<span style="color:#aaa">—</span>'
        return f"""
        <div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:14px 16px;flex:1;min-width:130px">
          <div style="font-size:9px;font-weight:700;letter-spacing:1px;color:#aaa;text-transform:uppercase;margin-bottom:6px">{titulo}</div>
          <div style="font-size:30px;font-weight:800;color:#111;line-height:1;margin-bottom:10px">{v_str}</div>
          <div style="border-top:1px solid #f0f0f0;padding-top:6px;display:flex;flex-direction:column;gap:3px">
            <div style="font-size:9px;color:#888">{mom_str} vs {nm_a}</div>
            <div style="font-size:9px;color:#888">{yoy_str} vs {nm_y}</div>
          </div>
        </div>"""

    # Card principal Vagas Fechadas
    card_vagas = f"""
    <div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:14px 16px;flex:1;min-width:160px">
      <div style="font-size:9px;font-weight:700;letter-spacing:1px;color:#aaa;text-transform:uppercase;margin-bottom:6px">Vagas Fechadas</div>
      <div style="font-size:42px;font-weight:800;color:#C0003C;line-height:1;margin-bottom:10px">{cur}</div>
      <div style="border-top:1px solid #f0f0f0;padding-top:6px;display:flex;flex-direction:column;gap:3px">
        <div style="font-size:9px;color:#888">{_var_str(cur, ant)} vs {nm_ant} ({ant})</div>
        <div style="font-size:9px;color:#888">{_var_str(cur, yoy)} vs {nm_yoy} ({yoy})</div>
      </div>
    </div>"""

    html = f"""
    <div style="font-family:Poppins,sans-serif;padding:4px 0 12px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px">
        <div style="width:3px;height:18px;background:#C0003C;border-radius:2px"></div>
        <span style="font-size:11px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">R&amp;S — Visão Geral · {nm_cur}</span>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        {card_vagas}
        {_metric_card("TTH (Time to Hire)", tth_c, tth_a, tth_y, nm_ant, nm_yoy)}
        {_metric_card("TTF (Time to Fill)", ttf_c, ttf_a, ttf_y, nm_ant, nm_yoy)}
        {_metric_card("TTD (Tempo Definição)", ttd_c, ttd_a, ttd_y, nm_ant, nm_yoy)}
      </div>
    </div>"""
    return ("__HTML__", html, 220), None


def analise_rs_por_diretoria(df_rs, mes_sel=None):
    """Tabela: Vagas fechadas no mês por Diretoria."""
    if df_rs is None or df_rs.empty:
        return ("__HTML__", "<div style='padding:16px;color:#888'>⚠️ RS não carregado.</div>", 80), None

    df_rs = _rs_prep(df_rs)
    mv    = mes_sel if mes_sel is not None else _rs_mes_vigente(df_rs)
    df_m  = _rs_vagas_fechadas(df_rs, mv.year, mv.month)
    nm_cur = mv.strftime("%b/%y").upper()

    COL = "Diretoria"
    if COL not in df_m.columns or len(df_m) == 0:
        return f"⚠️ Coluna '{COL}' não encontrada ou sem dados em {nm_cur}.", None

    tabela = df_m.groupby(COL).size().sort_values(ascending=False).reset_index()
    tabela.columns = ["Diretoria", "Vagas Fechadas"]
    total = tabela["Vagas Fechadas"].sum()

    rows = ""
    for i, row in tabela.iterrows():
        pct = round(row["Vagas Fechadas"] / total * 100, 1) if total > 0 else 0
        bg  = "#f9f9f9" if i % 2 == 0 else "#fff"
        bar = f'<div style="background:#C0003C;height:6px;border-radius:3px;width:{pct:.0f}%;margin-top:4px"></div>'
        rows += f"""
        <tr style="background:{bg}">
          <td style="padding:8px 12px;font-size:12px;color:#333">{row["Diretoria"]}</td>
          <td style="padding:8px 12px;text-align:center;font-weight:700;color:#111;font-size:13px">{row["Vagas Fechadas"]}</td>
          <td style="padding:8px 12px;font-size:11px;color:#888">{pct}%{bar}</td>
        </tr>"""

    html = f"""
    <div style="font-family:Poppins,sans-serif;padding:4px 0 12px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <div style="width:3px;height:18px;background:#C0003C;border-radius:2px"></div>
        <span style="font-size:11px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">Vagas Fechadas por Diretoria · {nm_cur}</span>
        <span style="font-size:10px;color:#aaa;margin-left:4px">Total: {total}</span>
      </div>
      <table style="width:100%;border-collapse:collapse;border-radius:8px;overflow:hidden;border:1px solid #eee">
        <thead>
          <tr style="background:#C0003C">
            <th style="padding:10px 12px;text-align:left;font-size:10px;font-weight:700;color:#fff;letter-spacing:.8px;text-transform:uppercase">Diretoria</th>
            <th style="padding:10px 12px;text-align:center;font-size:10px;font-weight:700;color:#fff;letter-spacing:.8px;text-transform:uppercase">Qtd</th>
            <th style="padding:10px 12px;font-size:10px;font-weight:700;color:#fff;letter-spacing:.8px;text-transform:uppercase">%</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""
    altura = max(200, 100 + len(tabela) * 42)
    return ("__HTML__", html, altura), None


def analise_rs_por_responsavel(df_rs, mes_sel=None):
    """Tabela: Vagas fechadas no mês por Analista Responsável."""
    if df_rs is None or df_rs.empty:
        return ("__HTML__", "<div style='padding:16px;color:#888'>⚠️ RS não carregado.</div>", 80), None

    df_rs = _rs_prep(df_rs)
    mv    = mes_sel if mes_sel is not None else _rs_mes_vigente(df_rs)
    df_m  = _rs_vagas_fechadas(df_rs, mv.year, mv.month)
    nm_cur = mv.strftime("%b/%y").upper()

    # Tenta ambos os nomes possíveis da coluna
    COL = next((c for c in ("Analista Responsável ", "Analista Responsável", "ANALISTA RESPONSÁVEL") if c in df_m.columns), None)
    if not COL or len(df_m) == 0:
        return f"⚠️ Coluna 'Analista Responsável' não encontrada ou sem dados em {nm_cur}.", None

    tabela = df_m.groupby(COL).size().sort_values(ascending=False).reset_index()
    tabela.columns = ["Analista", "Vagas Fechadas"]
    total = tabela["Vagas Fechadas"].sum()

    rows = ""
    for i, row in tabela.iterrows():
        pct = round(row["Vagas Fechadas"] / total * 100, 1) if total > 0 else 0
        bg  = "#f9f9f9" if i % 2 == 0 else "#fff"
        bar = f'<div style="background:#C0003C;height:6px;border-radius:3px;width:{pct:.0f}%;margin-top:4px"></div>'
        rows += f"""
        <tr style="background:{bg}">
          <td style="padding:8px 12px;font-size:12px;color:#333">{row["Analista"]}</td>
          <td style="padding:8px 12px;text-align:center;font-weight:700;color:#111;font-size:13px">{row["Vagas Fechadas"]}</td>
          <td style="padding:8px 12px;font-size:11px;color:#888">{pct}%{bar}</td>
        </tr>"""

    html = f"""
    <div style="font-family:Poppins,sans-serif;padding:4px 0 12px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <div style="width:3px;height:18px;background:#C0003C;border-radius:2px"></div>
        <span style="font-size:11px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">Vagas Fechadas por Analista · {nm_cur}</span>
        <span style="font-size:10px;color:#aaa;margin-left:4px">Total: {total}</span>
      </div>
      <table style="width:100%;border-collapse:collapse;border-radius:8px;overflow:hidden;border:1px solid #eee">
        <thead>
          <tr style="background:#C0003C">
            <th style="padding:10px 12px;text-align:left;font-size:10px;font-weight:700;color:#fff;letter-spacing:.8px;text-transform:uppercase">Analista</th>
            <th style="padding:10px 12px;text-align:center;font-size:10px;font-weight:700;color:#fff;letter-spacing:.8px;text-transform:uppercase">Qtd</th>
            <th style="padding:10px 12px;font-size:10px;font-weight:700;color:#fff;letter-spacing:.8px;text-transform:uppercase">%</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""
    altura = max(200, 100 + len(tabela) * 42)
    return ("__HTML__", html, altura), None


def analise_rs_por_bp(df_rs, mes_sel=None):
    """Tabela: Vagas fechadas no mês por BP."""
    if df_rs is None or df_rs.empty:
        return ("__HTML__", "<div style='padding:16px;color:#888'>⚠️ RS não carregado.</div>", 80), None

    df_rs = _rs_prep(df_rs)
    mv    = mes_sel if mes_sel is not None else _rs_mes_vigente(df_rs)
    df_m  = _rs_vagas_fechadas(df_rs, mv.year, mv.month)
    nm_cur = mv.strftime("%b/%y").upper()

    COL = next((c for c in ("BP", "Bp") if c in df_m.columns), None)
    if not COL or len(df_m) == 0:
        return f"⚠️ Coluna 'BP' não encontrada ou sem dados em {nm_cur}.", None

    tabela = df_m[df_m[COL].fillna("").str.strip() != ""].groupby(COL).size().sort_values(ascending=False).reset_index()
    tabela.columns = ["BP", "Vagas Fechadas"]
    total = tabela["Vagas Fechadas"].sum()

    rows = ""
    for i, row in tabela.iterrows():
        pct = round(row["Vagas Fechadas"] / total * 100, 1) if total > 0 else 0
        bg  = "#f9f9f9" if i % 2 == 0 else "#fff"
        bar = f'<div style="background:#C0003C;height:6px;border-radius:3px;width:{pct:.0f}%;margin-top:4px"></div>'
        rows += f"""
        <tr style="background:{bg}">
          <td style="padding:8px 12px;font-size:12px;color:#333">{row["BP"]}</td>
          <td style="padding:8px 12px;text-align:center;font-weight:700;color:#111;font-size:13px">{row["Vagas Fechadas"]}</td>
          <td style="padding:8px 12px;font-size:11px;color:#888">{pct}%{bar}</td>
        </tr>"""

    html = f"""
    <div style="font-family:Poppins,sans-serif;padding:4px 0 12px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <div style="width:3px;height:18px;background:#C0003C;border-radius:2px"></div>
        <span style="font-size:11px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">Vagas Fechadas por BP · {nm_cur}</span>
        <span style="font-size:10px;color:#aaa;margin-left:4px">Total: {total}</span>
      </div>
      <table style="width:100%;border-collapse:collapse;border-radius:8px;overflow:hidden;border:1px solid #eee">
        <thead>
          <tr style="background:#C0003C">
            <th style="padding:10px 12px;text-align:left;font-size:10px;font-weight:700;color:#fff;letter-spacing:.8px;text-transform:uppercase">BP</th>
            <th style="padding:10px 12px;text-align:center;font-size:10px;font-weight:700;color:#fff;letter-spacing:.8px;text-transform:uppercase">Qtd</th>
            <th style="padding:10px 12px;font-size:10px;font-weight:700;color:#fff;letter-spacing:.8px;text-transform:uppercase">%</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""
    altura = max(180, 100 + len(tabela) * 42)
    return ("__HTML__", html, altura), None


def analise_rs_status_vagas(df_rs, mes_sel=None):
    """
    Visão estratégica — 4 cards + narrativas automáticas.
    Cards: Vagas Fechadas+MoM+YoY | Vagas Abertas+MoM+YoY | TTH | TTF
    Narrativas: frases geradas dinamicamente com os números reais.
    """
    if df_rs is None or df_rs.empty:
        return ("__HTML__", "<div style='padding:16px;color:#888'>⚠️ RS não carregado.</div>", 80), None

    df_rs = _rs_prep(df_rs)
    mv     = (mes_sel if mes_sel is not None else _rs_mes_vigente(df_rs)).replace(day=1)
    mv_ant = (mv - pd.DateOffset(months=1)).replace(day=1)
    mv_yoy = (mv - pd.DateOffset(years=1)).replace(day=1)
    nm  = mv.strftime("%b/%Y")
    nm_ant = mv_ant.strftime("%b/%y").upper()
    nm_yoy = mv_yoy.strftime("%b/%y").upper()

    def _mc(df_sub, col):
        if col not in df_sub.columns or len(df_sub)==0: return None
        v = pd.to_numeric(df_sub[col], errors="coerce").dropna()
        return round(v.mean(), 0) if len(v)>0 else None

    def _pct(a, b): return round((a-b)/b*100, 0) if b and b!=0 else 0
    def _seta_vf(v):  # vagas fechadas: ▲ = bom (mais)
        return ("▲","#16a34a") if v>=0 else ("▼","#dc2626")
    def _seta_tth(v): # TTH: ▼ = bom (menor é melhor)
        return ("▼","#16a34a") if v<=0 else ("▲","#dc2626")

    # ── Vagas fechadas ────────────────────────────────────────
    vf_c = len(_rs_vagas_fechadas(df_rs, mv.year, mv.month))
    vf_a = len(_rs_vagas_fechadas(df_rs, mv_ant.year, mv_ant.month))
    vf_y = len(_rs_vagas_fechadas(df_rs, mv_yoy.year, mv_yoy.month))
    vf_mom = _pct(vf_c, vf_a); vf_yoy_p = _pct(vf_c, vf_y)
    s_vf_m, c_vf_m = _seta_vf(vf_mom)
    s_vf_y, c_vf_y = _seta_vf(vf_yoy_p)

    # ── Vagas abertas (alinhamento no mês) ────────────────────
    COL_ALIGN = next((c for c in df_rs.columns if "alinhamento" in c.lower()), None)
    def _va_mes(a, m):
        if not COL_ALIGN: return df_rs.iloc[0:0]
        raw = pd.to_datetime(df_rs[COL_ALIGN], errors="coerce")
        if raw.dt.tz is not None: raw = raw.dt.tz_localize(None)
        return df_rs[(raw.dt.year==a) & (raw.dt.month==m)]

    va_c = len(_va_mes(mv.year, mv.month))
    va_a = len(_va_mes(mv_ant.year, mv_ant.month))
    va_y = len(_va_mes(mv_yoy.year, mv_yoy.month))
    va_mom = _pct(va_c, va_a); va_yoy_p = _pct(va_c, va_y)
    s_va_m, c_va_m = _seta_vf(va_mom)
    s_va_y, c_va_y = _seta_vf(va_yoy_p)

    # ── TTH e TTF ─────────────────────────────────────────────
    df_fc = _rs_vagas_fechadas(df_rs, mv.year, mv.month)
    df_fa = _rs_vagas_fechadas(df_rs, mv_ant.year, mv_ant.month)
    df_fy = _rs_vagas_fechadas(df_rs, mv_yoy.year, mv_yoy.month)

    tth_c = _mc(df_fc,"Time to Hire (Indicador Stop)")
    tth_a = _mc(df_fa,"Time to Hire (Indicador Stop)")
    tth_y = _mc(df_fy,"Time to Hire (Indicador Stop)")
    ttf_c = _mc(df_fc,"Time to Fill (O inicio)")
    ttf_a = _mc(df_fa,"Time to Fill (O inicio)")
    ttf_y = _mc(df_fy,"Time to Fill (O inicio)")

    tth_mp = _pct(tth_c, tth_a) if tth_c and tth_a else None
    tth_yp = _pct(tth_c, tth_y) if tth_c and tth_y else None
    ttf_mp = _pct(ttf_c, ttf_a) if ttf_c and ttf_a else None
    ttf_yp = _pct(ttf_c, ttf_y) if ttf_c and ttf_y else None

    # ── Motivo de abertura ────────────────────────────────────
    df_va = _va_mes(mv.year, mv.month)
    COL_MOT = next((c for c in ("Motivo Abertura","MOTIVO ABERTURA") if c in df_va.columns), None)
    motivo_txt = ""
    if COL_MOT and len(df_va)>0:
        mot_cnt = df_va[COL_MOT].fillna("").str.upper().str.strip().value_counts()
        total_mot = mot_cnt.sum()
        subs_kws = ["SUBSTITUIÇÃO","SUBSTITUICAO","TURNOVER","REPOSIÇÃO"]
        n_subs = sum(v for k,v in mot_cnt.items() if any(w in k for w in subs_kws))
        pct_subs = round(n_subs/total_mot*100,0) if total_mot>0 else 0
        motivo_txt = f"{int(pct_subs)}% relativas a substituição/turnover" if pct_subs>0 else ""

    # ── Helper de var string ──────────────────────────────────
    def _vs(val, pct, seta_fn, sfx=" dias"):
        if val is None: return "—"
        v_str = f"{int(val)}{sfx}"
        if pct is None: return v_str
        s,c = seta_fn(pct)
        return f'{v_str} &nbsp;<span style="color:{c};font-weight:700">{s} {abs(int(pct))}%</span>'

    def _card4(titulo, valor_str, mom_v, mom_p, yoy_v, yoy_p, seta_fn, big_cor="#111"):
        def _row(label, v, p, fn):
            if v is None or p is None: return ""
            s,c = fn(p)
            return f'<div style="display:flex;justify-content:space-between;padding:4px 0;border-top:1px solid #f5f5f5">'+                    f'<span style="font-size:10px;color:#aaa">vs. {label}</span>'+                    f'<span style="font-size:11px;font-weight:700;color:{c}">{s} {abs(int(p))}% ({v})</span></div>'
        return f"""
        <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px 18px;flex:1;min-width:180px">
          <div style="font-size:9px;font-weight:700;color:#9ca3af;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:8px">{titulo}</div>
          <div style="font-size:38px;font-weight:800;color:{big_cor};line-height:1;margin-bottom:10px">{valor_str}</div>
          {_row("Mês", mom_v, mom_p, seta_fn)}
          {_row("Ano", yoy_v, yoy_p, seta_fn)}
        </div>"""

    # ── Vagas Fechadas: 3 cards em linha ─────────────────────
    cards_fech = (
        _card4("Vagas Fechadas", str(vf_c),
               f"{vf_a}", vf_mom, f"{vf_y}", vf_yoy_p, _seta_vf, "#C0003C")
        + _card4("TTH — Time to Hire",
                 f"{int(tth_c)} dias" if tth_c else "—",
                 f"{int(tth_a)} dias" if tth_a else None, tth_mp,
                 f"{int(tth_y)} dias" if tth_y else None, tth_yp, _seta_tth)
        + _card4("TTF — Time to Fill",
                 f"{int(ttf_c)} dias" if ttf_c else "—",
                 f"{int(ttf_a)} dias" if ttf_a else None, ttf_mp,
                 f"{int(ttf_y)} dias" if ttf_y else None, ttf_yp, _seta_tth)
    )

    # ── TTH/TTF das vagas abertas (sem fechamento = usa df_va) ─
    tth_va_c = _mc(_va_mes(mv.year, mv.month),    "Time to Hire (Indicador Stop)")
    ttf_va_c = _mc(_va_mes(mv.year, mv.month),    "Time to Fill (O inicio)")

    # ── Vagas Abertas: 3 cards em linha ──────────────────────
    cards_aber = (
        _card4("Vagas Abertas", str(va_c),
               f"{va_a}", va_mom, f"{va_y}", va_yoy_p, _seta_vf)
        + _card4("TTH Médio",
                 f"{int(tth_va_c)} dias" if tth_va_c else "—",
                 None, None, None, None, _seta_tth)
        + _card4("TTF Médio",
                 f"{int(ttf_va_c)} dias" if ttf_va_c else "—",
                 None, None, None, None, _seta_tth)
    )

    # ── Narrativas por bloco ──────────────────────────────────
    def _narr_fech():
        if not vf_c: return "Sem vagas fechadas no período."
        tth_txt = f"Méd. {int(tth_c)} dias" if tth_c else ""
        partes = [f"<b>{vf_c} vagas fechadas em {nm}</b>"]
        if tth_txt: partes[0] += f" ({tth_txt})"
        if tth_c and tth_y:
            p=_pct(tth_c,tth_y); s,c=_seta_tth(p)
            partes.append(f'<span style="color:{c};font-weight:600">{s} {abs(int(p))}%</span> na média de dias vs {nm_yoy} ({int(tth_y)} dias)')
        if vf_y:
            sv,cv=_seta_vf(vf_yoy_p)
            partes.append(f'<span style="color:{cv};font-weight:600">{sv} {abs(int(vf_yoy_p))}%</span> no volume vs {nm_yoy} ({vf_y} vagas)')
        return ". ".join(partes)

    def _narr_aber():
        if not va_c: return "Sem vagas abertas no período."
        linha = f"<b>{va_c} vagas abertas</b> com alinhamento em {nm}"
        if motivo_txt: linha += f", sendo {motivo_txt}"
        if va_y:
            sv,cv=_seta_vf(va_yoy_p)
            linha += f' · <span style="color:{cv};font-weight:600">{sv} {abs(int(va_yoy_p))}%</span> vs {nm_yoy} ({va_y} vagas)'
        return linha

    html = f"""
    <div style="font-family:Poppins,sans-serif;padding:4px 0 8px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <div style="width:3px;height:18px;background:#C0003C;border-radius:2px"></div>
        <span style="font-size:11px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">
          R&amp;S — Visão Estratégica · {nm}</span>
      </div>

      <!-- Bloco Vagas Fechadas -->
      <div style="background:#fff8f8;border:1px solid #fecdd3;border-radius:10px;padding:14px 16px;margin-bottom:12px">
        <div style="font-size:9px;font-weight:700;color:#9ca3af;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:10px">
          VAGAS FECHADAS</div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px">{cards_fech}</div>
        <div style="font-size:12px;color:#374151;line-height:1.8;padding:10px 12px;
                    background:#fff;border-radius:8px;border:1px solid #fde8e8">
          {_narr_fech()}
        </div>
      </div>

      <!-- Bloco Vagas Abertas -->
      <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:14px 16px">
        <div style="font-size:9px;font-weight:700;color:#9ca3af;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:10px">
          VAGAS ABERTAS</div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px">{cards_aber}</div>
        <div style="font-size:12px;color:#374151;line-height:1.8;padding:10px 12px;
                    background:#fff;border-radius:8px;border:1px solid #d1fae5">
          {_narr_aber()}
        </div>
      </div>
    </div>"""
    return ("__HTML__", html, 700), None



# ══════════════════════════════════════════════════════════════
#  R&S — VAGAS ABERTAS (visão completa com Plotly)
# ══════════════════════════════════════════════════════════════

def analise_rs_vagas_abertas(df_rs, mes_sel=None):
    """Visão completa de Vagas Abertas — fundo branco, colunas, funil Gupy."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import re as _re

    if df_rs is None or df_rs.empty:
        return "⚠️ RS_Consolidado.parquet não carregado.", None

    df_rs = _rs_prep(df_rs)
    mv     = (mes_sel if mes_sel is not None else _rs_mes_vigente(df_rs)).replace(day=1)
    mv_ant = (mv - pd.DateOffset(months=1)).replace(day=1)
    mv_yoy = (mv - pd.DateOffset(years=1)).replace(day=1)
    nm     = mv.strftime("%b/%Y").upper()

    # ── helpers tema claro ─────────────────────────────────────
    BG   = "white";  PBG  = "white"
    FC   = "#1a1a1a"; GC   = "rgba(0,0,0,.06)"; BAR  = "#C0003C"

    def _lay(title, h, ml=40, mr=40, mt=52, mb=50):
        return dict(
            title=dict(text=title, font=dict(size=13, color=FC, family="Poppins"), x=.5),
            paper_bgcolor=PBG, plot_bgcolor=BG,
            font=dict(color=FC, family="Poppins"),
            height=h, margin=dict(l=ml, r=mr, t=mt, b=mb),
        )

    def _media_col(df_sub, col):
        if col not in df_sub.columns or len(df_sub)==0: return None
        v = pd.to_numeric(df_sub[col], errors="coerce").dropna()
        return round(v.mean(),1) if len(v)>0 else None

    def _pct(a,b): return round((a-b)/b*100,0) if b and b!=0 else 0
    def _seta(v,inv=False):
        pos = v>=0
        if inv: pos = not pos
        return ("▲","#16a34a") if pos else ("▼","#dc2626")

    # Vagas abertas = alinhamento preenchido no mês
    COL_ALIGN = next((c for c in df_rs.columns if "alinhamento" in c.lower()), None)
    def _va_mes(a, m):
        if not COL_ALIGN: return df_rs.iloc[0:0]
        raw = pd.to_datetime(df_rs[COL_ALIGN], errors="coerce")
        if raw.dt.tz is not None: raw = raw.dt.tz_localize(None)
        return df_rs[(raw.dt.year==a) & (raw.dt.month==m)]

    df_cur = _va_mes(mv.year, mv.month)
    df_ant = _va_mes(mv_ant.year, mv_ant.month)
    df_yoy = _va_mes(mv_yoy.year, mv_yoy.month)
    tot_c, tot_a, tot_y = len(df_cur), len(df_ant), len(df_yoy)
    tth_c = _media_col(df_cur,"Time to Hire (Indicador Stop)")
    tth_a = _media_col(df_ant,"Time to Hire (Indicador Stop)")
    tth_y = _media_col(df_yoy,"Time to Hire (Indicador Stop)")
    ttf_c = _media_col(df_cur,"Time to Fill (O inicio)")
    ttf_a = _media_col(df_ant,"Time to Fill (O inicio)")
    ttf_y = _media_col(df_yoy,"Time to Fill (O inicio)")

    nm_ant = mv_ant.strftime("%b/%y").upper()
    nm_yoy = mv_yoy.strftime("%b/%y").upper()

    def _card(titulo, val, ant, yoy, sufixo=" dias", inv=False, big=False):
        v_str = f"{int(val)}{sufixo}" if val is not None else "—"
        cor_n = "#C0003C" if big else "#111"
        rows  = ""
        if ant is not None and val is not None:
            p=_pct(val,ant); s,c=_seta(p,inv)
            rows += f'<div style="font-size:10px;color:#888">vs. Mês &nbsp;<span style="color:{c};font-weight:700">{s} {abs(int(p))}% ({int(ant)}{sufixo})</span></div>'
        if yoy is not None and val is not None:
            p=_pct(val,yoy); s,c=_seta(p,inv)
            rows += f'<div style="font-size:10px;color:#888">vs. Ano &nbsp;<span style="color:{c};font-weight:700">{s} {abs(int(p))}% ({int(yoy)}{sufixo})</span></div>'
        return f"""<div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:14px 16px;flex:1;min-width:120px">
          <div style="font-size:9px;font-weight:700;color:#aaa;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px">{titulo}</div>
          <div style="font-size:34px;font-weight:800;color:{cor_n};line-height:1;margin-bottom:8px">{v_str}</div>
          <div style="border-top:1px solid #f0f0f0;padding-top:6px">{rows}</div>
        </div>"""

    cards_html = (
        _card("Total Vagas Abertas", tot_c, tot_a, tot_y, sufixo="")
        + _card("TTH — Time to Hire", tth_c, tth_a, tth_y, inv=True)
        + _card("TTF — Time to Fill", ttf_c, ttf_a, ttf_y, inv=True)
    )

    figs = []

    # ── 1. Por Diretoria — barras horizontais (nomes legíveis, sem rotação) ──
    COL_DIR = next((c for c in ("Diretoria","DIRETORIA") if c in df_cur.columns), None)
    if COL_DIR and len(df_cur)>0:
        # sort ascending=False + head(10) + autorange=reversed → maior no topo
        df_d = df_cur.groupby(COL_DIR).size().sort_values(ascending=False).head(10)
        tth_d = {d: round(pd.to_numeric(g.get("Time to Hire (Indicador Stop)",pd.Series()),
                 errors="coerce").where(lambda s: s>0).dropna().mean(),0)
                 for d,g in df_cur.groupby(COL_DIR)}
        text_d = [f" {v}  |  TTH: {int(tth_d.get(d,0))} dias " for d,v in df_d.items()]
        fig1 = go.Figure(go.Bar(
            y=list(df_d.index), x=list(df_d.values),
            orientation="h",
            marker_color=BAR,
            text=text_d,
            textposition="inside",
            insidetextanchor="start",
            textfont=dict(size=12, color="white", family="Poppins"),
            width=0.6,
        ))
        fig1.update_layout(
            title=dict(text=f"Vagas Abertas por Diretoria · {nm}",
                       font=dict(size=13,color=FC,family="Poppins"),x=.5),
            paper_bgcolor=PBG, plot_bgcolor=BG,
            font=dict(color=FC,family="Poppins"),
            xaxis=dict(showgrid=True,gridcolor=GC,color=FC,tickfont=dict(size=11)),
            yaxis=dict(showgrid=False,color=FC,
                       tickfont=dict(size=11,family="Poppins"),
                       autorange="reversed"),
            height=max(280, 70+len(df_d)*40),
            margin=dict(l=200,r=30,t=55,b=40),
        )
        figs.append(fig1)

    # ── 2. Roscas: Motivo + Prazos ────────────────────────────
    COL_MOT = next((c for c in ("Motivo Abertura","MOTIVO ABERTURA","Motivo") if c in df_cur.columns), None)
    COL_PRZ = next((c for c in ("Prazos","Prazo","PRAZOS") if c in df_cur.columns), None)
    if (COL_MOT or COL_PRZ) and len(df_cur)>0:
        ncols = (1 if COL_MOT else 0)+(1 if COL_PRZ else 0)
        fig2  = make_subplots(rows=1,cols=ncols,specs=[[{"type":"pie"}]*ncols])
        ci    = 1
        for cn,tit in [(COL_MOT,"Motivo Abertura"),(COL_PRZ,"Prazos")]:
            if cn and cn in df_cur.columns:
                cnt = df_cur[cn].fillna("NÃO INF.").str.upper().str.strip().value_counts()
                fig2.add_trace(go.Pie(
                    labels=list(cnt.index), values=list(cnt.values),
                    name=tit, hole=.55,
                    marker_colors=["#C0003C","#374151","#e0284a","#6b7280","#9ca3af"],
                    textfont=dict(size=11,family="Poppins",color="#1a1a1a"),
                    title=dict(text=f"<b>{tit}</b>",font=dict(size=12,color="#1a1a1a")),
                ), row=1,col=ci); ci+=1
        fig2.update_layout(
            paper_bgcolor=PBG, font=dict(color=FC,family="Poppins"),
            height=300, margin=dict(l=20,r=20,t=40,b=20),
            showlegend=False,
        )
        # Adiciona rótulos percentuais dentro das fatias
        fig2.update_traces(textposition="inside", textinfo="label+percent",
                           insidetextorientation="radial")
        figs.append(fig2)

    # ── 3. Colunas: Por Recrutador ────────────────────────────
    COL_REC = next((c for c in ("Analista Responsável ","Analista Responsável","ANALISTA RESPONSÁVEL") if c in df_cur.columns), None)
    if COL_REC and len(df_cur)>0:
        df_r = df_cur.groupby(COL_REC).size().sort_values(ascending=False).head(8)
        tth_r = {r: round(pd.to_numeric(g.get("Time to Hire (Indicador Stop)",pd.Series()),errors="coerce").dropna().mean(),0)
                 for r,g in df_cur.groupby(COL_REC)}
        fig3 = go.Figure(go.Bar(
            y=list(df_r.index), x=list(df_r.values),
            orientation="h",
            marker_color=BAR,
            text=[f" {v}  |  TTH: {int(tth_r.get(r,0))} dias " for r,v in df_r.items()],
            textposition="inside",
            insidetextanchor="start",
            textfont=dict(size=12, color="white", family="Poppins"),
            width=0.6,
        ))
        fig3.update_layout(
            title=dict(text="Por Recrutador",font=dict(size=13,color=FC,family="Poppins"),x=.5),
            paper_bgcolor=PBG,plot_bgcolor=BG,font=dict(color=FC,family="Poppins"),
            xaxis=dict(showgrid=True,gridcolor=GC,color=FC,tickfont=dict(size=11)),
            yaxis=dict(showgrid=False,color=FC,tickfont=dict(size=12,family="Poppins"),
                       autorange="reversed"),
            height=max(260, 60+len(df_r)*44),
            margin=dict(l=120,r=30,t=55,b=30),
        )
        figs.append(fig3)

    # ── 4. Colunas lado a lado: Cluster + Senioridade ─────────
    COL_CL = next((c for c in ("Nível Agrupado","NÍVEL AGRUPADO","Cluster") if c in df_cur.columns), None)
    COL_SN = next((c for c in ("Nível","NÍVEL","Senioridade") if c in df_cur.columns), None)
    if (COL_CL or COL_SN) and len(df_cur)>0:
        ncols2 = (1 if COL_CL else 0)+(1 if COL_SN else 0)
        fig4   = make_subplots(rows=1,cols=ncols2,
                               subplot_titles=[t for c,t in [(COL_CL,"Cluster"),(COL_SN,"Senioridade")] if c],
                               horizontal_spacing=0.18)
        ci2    = 1
        for cn,tit in [(COL_CL,"Cluster"),(COL_SN,"Senioridade")]:
            if cn and cn in df_cur.columns:
                grp = df_cur.groupby(cn).size().sort_values(ascending=False)
                tth_g = {k: round(pd.to_numeric(g.get("Time to Hire (Indicador Stop)",pd.Series()),
                         errors="coerce").replace(0,pd.NA).dropna().mean(),0)
                         for k,g in df_cur.groupby(cn)}
                fig4.add_trace(go.Bar(
                    x=list(grp.index), y=list(grp.values),
                    marker_color=BAR,
                    text=[f"{v} | TTH: {int(tth_g.get(k,0))}d" for k,v in grp.items()],
                    textposition="inside", insidetextanchor="middle",
                    textfont=dict(size=12, color="white", family="Poppins"),
                    name=tit, width=0.6,
                ), row=1,col=ci2); ci2+=1
        fig4.update_layout(
            paper_bgcolor=PBG, plot_bgcolor=BG,
            font=dict(color=FC,family="Poppins"),
            height=340, margin=dict(l=30,r=30,t=55,b=60),
            showlegend=False,
        )
        for i in range(1,ci2):
            fig4.update_xaxes(showgrid=False,tickfont=dict(size=11),color=FC,tickangle=0,row=1,col=i)
            fig4.update_yaxes(showgrid=True,gridcolor=GC,color=FC,tickfont=dict(size=11),row=1,col=i)
        figs.append(fig4)

    # ── 5. Funil REAL (go.Funnel) — % sobre total de vagas abertas ──
    COL_ETAPA = next((c for c in ("Etapa","ETAPA","Etapas R&S") if c in df_cur.columns), None)
    if COL_ETAPA and len(df_cur)>0:
        etapas_raw = df_cur[COL_ETAPA].fillna("").astype(str).str.strip()
        etapas_raw = etapas_raw[etapas_raw!=""]
        if len(etapas_raw)>0:
            def _n(s):
                m = _re.match(r"(\d+)", s.strip())
                return int(m.group(1)) if m else 99
            cnt        = etapas_raw.value_counts()
            cnt_sorted = cnt.sort_index(key=lambda x: x.map(_n))
            total_geral = int(df_cur.shape[0]) or 1

            etapas  = list(cnt_sorted.index)
            valores = list(cnt_sorted.values)
            # % sobre o total de vagas — não sobre etapa anterior
            textos  = [f"{v}  ({round(v/total_geral*100,1):.1f}%)" for v in valores]

            fig5 = go.Figure(go.Funnel(
                y=etapas,
                x=valores,
                textinfo="text",
                text=textos,
                textposition="inside",
                textfont=dict(size=11, color="white", family="Poppins"),
                marker=dict(
                    color=["#C0003C" if i%2==0 else "#374151" for i in range(len(etapas))],
                    line=dict(color="white", width=1),
                ),
                connector=dict(
                    line=dict(color="#e5e7eb", width=2, dash="dot"),
                    fillcolor="rgba(229,231,235,0.3)",
                ),
                hovertemplate="%{y}<br>%{x} vagas<extra></extra>",
            ))
            fig5.update_layout(
                title=dict(text="Funil de Etapas — Vagas em Aberto",
                           font=dict(size=13, color=FC, family="Poppins"), x=.5),
                paper_bgcolor=PBG,
                font=dict(color=FC, family="Poppins"),
                height=max(360, 80+len(etapas)*42),
                margin=dict(l=30, r=30, t=55, b=30),
                funnelmode="stack",
            )
            figs.append(fig5)

    header_html = f"""
    <div style="font-family:Poppins,sans-serif;padding:4px 0 8px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <div style="width:3px;height:18px;background:#C0003C;border-radius:2px"></div>
        <span style="font-size:12px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">
          Vagas Abertas · {nm}</span>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:4px">{cards_html}</div>
    </div>"""
    return ("__HTML__", header_html, 185), figs


# ══════════════════════════════════════════════════════════════
#  R&S — VAGAS FECHADAS (visão completa com Plotly)
# ══════════════════════════════════════════════════════════════

def analise_rs_vagas_fechadas_rich(df_rs, mes_sel=None):
    """Visão completa de Vagas Fechadas — fundo branco, colunas."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    if df_rs is None or df_rs.empty:
        return "⚠️ RS_Consolidado.parquet não carregado.", None

    df_rs = _rs_prep(df_rs)
    mv     = (mes_sel if mes_sel is not None else _rs_mes_vigente(df_rs)).replace(day=1)
    mv_ant = (mv - pd.DateOffset(months=1)).replace(day=1)
    mv_yoy = (mv - pd.DateOffset(years=1)).replace(day=1)
    nm     = mv.strftime("%b/%Y").upper()
    nm_ant = mv_ant.strftime("%b/%y").upper()
    nm_yoy = mv_yoy.strftime("%b/%y").upper()

    BG="white"; PBG="white"; FC="#1a1a1a"; GC="rgba(0,0,0,.06)"; BAR="#C0003C"

    def _lay(title, h, ml=40, mr=40, mt=52, mb=50):
        return dict(
            title=dict(text=title,font=dict(size=13,color=FC,family="Poppins"),x=.5),
            paper_bgcolor=PBG,plot_bgcolor=BG,
            font=dict(color=FC,family="Poppins"),
            height=h,margin=dict(l=ml,r=mr,t=mt,b=mb),
        )

    def _mc(df_sub,col):
        if col not in df_sub.columns or len(df_sub)==0: return None
        v=pd.to_numeric(df_sub[col],errors="coerce").dropna()
        return round(v.mean(),1) if len(v)>0 else None

    def _pct(a,b): return round((a-b)/b*100,0) if b and b!=0 else 0
    def _seta(v,inv=False):
        pos=v>=0
        if inv: pos=not pos
        return ("▲","#16a34a") if pos else ("▼","#dc2626")

    df_cur = _rs_vagas_fechadas(df_rs, mv.year, mv.month)
    df_ant = _rs_vagas_fechadas(df_rs, mv_ant.year, mv_ant.month)
    df_yoy = _rs_vagas_fechadas(df_rs, mv_yoy.year, mv_yoy.month)
    tot_c,tot_a,tot_y = len(df_cur),len(df_ant),len(df_yoy)
    tth_c=_mc(df_cur,"Time to Hire (Indicador Stop)"); tth_a=_mc(df_ant,"Time to Hire (Indicador Stop)"); tth_y=_mc(df_yoy,"Time to Hire (Indicador Stop)")
    ttf_c=_mc(df_cur,"Time to Fill (O inicio)");       ttf_a=_mc(df_ant,"Time to Fill (O inicio)");       ttf_y=_mc(df_yoy,"Time to Fill (O inicio)")
    ttd_c=_mc(df_cur,"Tempo em Definição");             ttd_a=_mc(df_ant,"Tempo em Definição");             ttd_y=_mc(df_yoy,"Tempo em Definição")

    def _card(titulo,val,ant,yoy,sufixo=" dias",inv=False,big=False):
        v_str=f"{int(val)}{sufixo}" if val is not None else "—"
        cor_n="#C0003C" if big else "#111"
        rows=""
        if ant is not None and val is not None:
            p=_pct(val,ant);s,c=_seta(p,inv)
            rows+=f'<div style="font-size:10px;color:#888">vs. Mês &nbsp;<span style="color:{c};font-weight:700">{s} {abs(int(p))}% ({int(ant)}{sufixo})</span></div>'
        if yoy is not None and val is not None:
            p=_pct(val,yoy);s,c=_seta(p,inv)
            rows+=f'<div style="font-size:10px;color:#888">vs. Ano &nbsp;<span style="color:{c};font-weight:700">{s} {abs(int(p))}% ({int(yoy)}{sufixo})</span></div>'
        return f"""<div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:14px 16px;flex:1;min-width:120px">
          <div style="font-size:9px;font-weight:700;color:#aaa;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px">{titulo}</div>
          <div style="font-size:34px;font-weight:800;color:{cor_n};line-height:1;margin-bottom:8px">{v_str}</div>
          <div style="border-top:1px solid #f0f0f0;padding-top:6px">{rows}</div>
        </div>"""

    cards_html=(
        _card("Vagas Fechadas",tot_c,tot_a,tot_y,sufixo="",big=True)
        +_card("TTD",ttd_c,ttd_a,ttd_y,inv=True)
        +_card("TTH — Time to Hire",tth_c,tth_a,tth_y,inv=True)
        +_card("TTF — Time to Fill",ttf_c,ttf_a,ttf_y,inv=True)
    )

    figs=[]

    # 1. Por Empresa — gráfico individual, fonte grande, sem rotação
    COL_EMP=next((c for c in ("Empresas","EMPRESAS","Empresa") if c in df_cur.columns),None)
    if COL_EMP and len(df_cur)>0:
        df_e=df_cur.groupby(COL_EMP).size().sort_values(ascending=False)
        # Abrevia nomes longos para caber horizontalmente
        def _abrev(s, maxlen=14):
            s = str(s)
            return s if len(s) <= maxlen else s[:maxlen-1] + "…"
        labels_e = [_abrev(x) for x in df_e.index]
        f_emp = go.Figure(go.Bar(
            x=labels_e, y=list(df_e.values),
            marker_color=BAR,
            text=list(df_e.values),
            textposition="outside",      # sempre acima da barra — sempre visível
            textfont=dict(size=14, color="#1a1a1a", family="Poppins"),
            width=0.55,
        ))
        f_emp.update_layout(
            title=dict(text=f"Vagas Fechadas por Empresa · {nm}",
                       font=dict(size=13,color=FC,family="Poppins"),x=.5),
            paper_bgcolor=PBG, plot_bgcolor=BG,
            font=dict(color=FC,family="Poppins"),
            xaxis=dict(
                showgrid=False,
                tickfont=dict(size=12, color=FC, family="Poppins"),
                tickangle=0,          # HORIZONTAL — sem rotação
                color=FC,
            ),
            yaxis=dict(showgrid=True, gridcolor=GC, color=FC,
                       tickfont=dict(size=11)),
            height=300, margin=dict(l=30,r=30,t=55,b=50),
        )
        figs.append(f_emp)

    # 2. Por Diretoria — barras horizontais para acomodar nomes longos sem rotação
    COL_DIR=next((c for c in ("Diretoria","DIRETORIA") if c in df_cur.columns),None)
    if COL_DIR and len(df_cur)>0:
        # Ordenar: maior valor em cima → ascending=False + head(10) + autorange=reversed
        df_d=df_cur.groupby(COL_DIR).size().sort_values(ascending=False).head(10)
        tth_d={d:round(pd.to_numeric(g.get("Time to Hire (Indicador Stop)",pd.Series()),
               errors="coerce").where(lambda s: s>0).dropna().mean(),0)
               for d,g in df_cur.groupby(COL_DIR)}
        text_d=[f" {v}  |  TTH: {int(tth_d.get(d,0))} dias " for d,v in df_d.items()]
        f_dir = go.Figure(go.Bar(
            y=list(df_d.index),
            x=list(df_d.values),
            orientation="h",
            marker_color=BAR,
            text=text_d,
            textposition="inside",
            insidetextanchor="start",
            textfont=dict(size=12, color="white", family="Poppins"),
            width=0.6,
        ))
        f_dir.update_layout(
            title=dict(text="Vagas Fechadas por Diretoria",
                       font=dict(size=13,color=FC,family="Poppins"),x=.5),
            paper_bgcolor=PBG, plot_bgcolor=BG,
            font=dict(color=FC,family="Poppins"),
            xaxis=dict(showgrid=True, gridcolor=GC, color=FC,
                       tickfont=dict(size=11)),
            yaxis=dict(showgrid=False, color=FC,
                       tickfont=dict(size=11, family="Poppins"),
                       autorange="reversed"),   # maior valor no topo
            height=max(280, 70+len(df_d)*40),
            margin=dict(l=200,r=30,t=55,b=40),
        )
        figs.append(f_dir)

    # 3. Roscas: Motivo + Prazos
    COL_MOT=next((c for c in ("Motivo Abertura","MOTIVO ABERTURA") if c in df_cur.columns),None)
    COL_PRZ=next((c for c in ("Prazos","Prazo","PRAZOS") if c in df_cur.columns),None)
    if (COL_MOT or COL_PRZ) and len(df_cur)>0:
        ncols=(1 if COL_MOT else 0)+(1 if COL_PRZ else 0)
        f3=make_subplots(rows=1,cols=ncols,specs=[[{"type":"pie"}]*ncols])
        ci=1
        for cn,tit in [(COL_MOT,"Motivo Abertura"),(COL_PRZ,"Prazos")]:
            if cn and cn in df_cur.columns:
                cnt=df_cur[cn].fillna("NÃO INF.").str.upper().str.strip().value_counts()
                f3.add_trace(go.Pie(labels=list(cnt.index),values=list(cnt.values),name=tit,hole=.55,
                    marker_colors=["#C0003C","#374151","#e0284a","#6b7280","#9ca3af"],
                    textfont=dict(size=11,family="Poppins",color="white"),
                    textinfo="label+percent",
                    insidetextorientation="radial",
                    title=dict(text=f"<b>{tit}</b>",font=dict(size=12,color="#1a1a1a"))),row=1,col=ci); ci+=1
        f3.update_layout(paper_bgcolor=PBG,font=dict(color=FC,family="Poppins"),
            height=300,margin=dict(l=20,r=20,t=40,b=20),
            showlegend=False)
        figs.append(f3)

    # 4. Colunas: Por Recrutador
    COL_REC=next((c for c in ("Analista Responsável ","Analista Responsável","ANALISTA RESPONSÁVEL") if c in df_cur.columns),None)
    if COL_REC and len(df_cur)>0:
        df_r=df_cur.groupby(COL_REC).size().sort_values(ascending=False).head(8)
        tth_r={r:round(pd.to_numeric(g.get("Time to Hire (Indicador Stop)",pd.Series()),errors="coerce").dropna().mean(),0) for r,g in df_cur.groupby(COL_REC)}
        f4=go.Figure(go.Bar(
            y=list(df_r.index), x=list(df_r.values),
            orientation="h", marker_color=BAR,
            text=[f" {v}  |  TTH: {int(tth_r.get(r,0))} dias " for r,v in df_r.items()],
            textposition="inside", insidetextanchor="start",
            textfont=dict(size=12,color="white",family="Poppins"),
            width=0.6,
        ))
        f4.update_layout(
            title=dict(text="Por Recrutador",font=dict(size=13,color=FC,family="Poppins"),x=.5),
            paper_bgcolor=PBG,plot_bgcolor=BG,font=dict(color=FC,family="Poppins"),
            xaxis=dict(showgrid=True,gridcolor=GC,color=FC,tickfont=dict(size=11)),
            yaxis=dict(showgrid=False,color=FC,tickfont=dict(size=12,family="Poppins"),
                       autorange="reversed"),
            height=max(260,60+len(df_r)*44),
            margin=dict(l=120,r=30,t=55,b=30),
        )
        figs.append(f4)

    # 5+6. Colunas lado a lado: Cluster + Senioridade
    COL_CL=next((c for c in ("Nível Agrupado","NÍVEL AGRUPADO") if c in df_cur.columns),None)
    COL_SN=next((c for c in ("Nível","NÍVEL") if c in df_cur.columns),None)
    if (COL_CL or COL_SN) and len(df_cur)>0:
        n2=(1 if COL_CL else 0)+(1 if COL_SN else 0)
        f5=make_subplots(rows=1,cols=n2,
                         subplot_titles=[t for c,t in [(COL_CL,"Cluster"),(COL_SN,"Senioridade")] if c],
                         horizontal_spacing=0.18)
        ci2=1
        for cn,tit in [(COL_CL,"Cluster"),(COL_SN,"Senioridade")]:
            if cn and cn in df_cur.columns:
                grp=df_cur.groupby(cn).size().sort_values(ascending=False)
                tth_g={k:round(pd.to_numeric(g.get("Time to Hire (Indicador Stop)",pd.Series()),
                       errors="coerce").replace(0,pd.NA).dropna().mean(),0)
                       for k,g in df_cur.groupby(cn)}
                f5.add_trace(go.Bar(
                    x=list(grp.index),y=list(grp.values),marker_color=BAR,
                    text=[f"{v} | TTH: {int(tth_g.get(k,0))}d" for k,v in grp.items()],
                    textposition="inside", insidetextanchor="middle",
                    textfont=dict(size=12,color="white",family="Poppins"),
                    name=tit, width=0.6,
                ),row=1,col=ci2); ci2+=1
        f5.update_layout(paper_bgcolor=PBG,plot_bgcolor=BG,font=dict(color=FC,family="Poppins"),
            height=340,margin=dict(l=30,r=30,t=55,b=60),showlegend=False)
        for i in range(1,ci2):
            f5.update_xaxes(showgrid=False,tickfont=dict(size=11),color=FC,
                            tickangle=0,row=1,col=i)
            f5.update_yaxes(showgrid=True,gridcolor=GC,color=FC,
                            tickfont=dict(size=11),row=1,col=i)
        figs.append(f5)

    header_html=f"""
    <div style="font-family:Poppins,sans-serif;padding:4px 0 8px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <div style="width:3px;height:18px;background:#C0003C;border-radius:2px"></div>
        <span style="font-size:12px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">
          Vagas Fechadas · {nm}</span>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:4px">{cards_html}</div>
    </div>"""
    return ("__HTML__", header_html, 200), figs



def analise_rs_vagas_consolidadas(df_rs, mes_sel=None):
    """
    Tabela consolidada mês a mês — FY | Mês | Vagas Fechadas | TTD | TTH | TTF.
    Ordenada do mês mais atual para o mais antigo.
    """
    if df_rs is None or df_rs.empty:
        return "⚠️ RS_Consolidado.parquet não carregado.", None

    df_rs = _rs_prep(df_rs)

    COL_FECH = "Data de Fechamento (Indicador Stop)"
    if COL_FECH not in df_rs.columns:
        return "⚠️ Coluna de fechamento não encontrada.", None

    # Extrai todos os meses com vagas fechadas
    raw = pd.to_datetime(df_rs[COL_FECH], errors="coerce")
    if raw.dt.tz is not None: raw = raw.dt.tz_localize(None)
    df_rs = df_rs.copy()
    df_rs["_ANO_FECH"]  = raw.dt.year
    df_rs["_MES_FECH"]  = raw.dt.month
    df_rs = df_rs.dropna(subset=["_ANO_FECH"])

    # Meses únicos, ordenados do mais recente para o mais antigo
    periodos = (df_rs[["_ANO_FECH","_MES_FECH"]]
                .drop_duplicates()
                .sort_values(["_ANO_FECH","_MES_FECH"], ascending=[False,False]))

    MESES_PT = {1:"JANEIRO",2:"FEVEREIRO",3:"MARÇO",4:"ABRIL",5:"MAIO",
                6:"JUNHO",7:"JULHO",8:"AGOSTO",9:"SETEMBRO",
                10:"OUTUBRO",11:"NOVEMBRO",12:"DEZEMBRO"}

    def _fy(ano, mes):
        fy_ano = ano+1 if mes>=7 else ano
        return f"FY{str(fy_ano)[-2:]}"

    def _mc(df_sub, col):
        if col not in df_sub.columns or len(df_sub)==0: return "—"
        v = pd.to_numeric(df_sub[col], errors="coerce").dropna()
        return str(int(round(v.mean(),0))) if len(v)>0 else "—"

    rows_html = ""
    fy_anterior = None
    for _, row in periodos.iterrows():
        a, m = int(row["_ANO_FECH"]), int(row["_MES_FECH"])
        df_m = df_rs[(df_rs["_ANO_FECH"]==a) & (df_rs["_MES_FECH"]==m)]
        fy = _fy(a, m)
        mes_nome = MESES_PT.get(m, str(m))
        total = len(df_m)
        ttd = _mc(df_m, "Tempo em Definição")
        tth = _mc(df_m, "Time to Hire (Indicador Stop)")
        ttf = _mc(df_m, "Time to Fill (O inicio)")

        # Cor de fundo alterna por FY
        bg = "#fff" if fy_anterior is None or fy == fy_anterior else "#fafafa"
        fy_anterior = fy

        rows_html += f"""
        <tr style="background:{bg}">
          <td style="padding:9px 14px;font-size:11px;font-weight:700;color:#C0003C;border-bottom:1px solid #f3f4f6">{fy}</td>
          <td style="padding:9px 14px;font-size:11px;color:#374151;border-bottom:1px solid #f3f4f6">{mes_nome}</td>
          <td style="padding:9px 14px;font-size:12px;font-weight:700;color:#111;text-align:center;border-bottom:1px solid #f3f4f6">{total}</td>
          <td style="padding:9px 14px;font-size:11px;color:#6b7280;text-align:center;border-bottom:1px solid #f3f4f6">{ttd}</td>
          <td style="padding:9px 14px;font-size:11px;color:#6b7280;text-align:center;border-bottom:1px solid #f3f4f6">{tth}</td>
          <td style="padding:9px 14px;font-size:11px;color:#6b7280;text-align:center;border-bottom:1px solid #f3f4f6">{ttf}</td>
        </tr>"""

    html = f"""
    <div style="font-family:Poppins,sans-serif;padding:4px 0 8px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <div style="width:3px;height:18px;background:#C0003C;border-radius:2px"></div>
        <span style="font-size:11px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">
          Vagas Fechadas — Consolidado Histórico</span>
      </div>
      <div style="border:1px solid #e5e7eb;border-radius:12px;overflow:hidden">
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="background:#C0003C">
              <th style="padding:10px 14px;text-align:left;font-size:10px;font-weight:700;color:white;letter-spacing:1px;text-transform:uppercase">FY</th>
              <th style="padding:10px 14px;text-align:left;font-size:10px;font-weight:700;color:white;letter-spacing:1px;text-transform:uppercase">Mês Vigente</th>
              <th style="padding:10px 14px;text-align:center;font-size:10px;font-weight:700;color:white;letter-spacing:1px;text-transform:uppercase">Vagas Fechadas</th>
              <th style="padding:10px 14px;text-align:center;font-size:10px;font-weight:700;color:white;letter-spacing:1px;text-transform:uppercase">TTD (dias)</th>
              <th style="padding:10px 14px;text-align:center;font-size:10px;font-weight:700;color:white;letter-spacing:1px;text-transform:uppercase">TTH (dias)</th>
              <th style="padding:10px 14px;text-align:center;font-size:10px;font-weight:700;color:white;letter-spacing:1px;text-transform:uppercase">TTF (dias)</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
      </div>
    </div>"""

    n = len(periodos)
    altura = max(300, 80 + n * 40)
    return ("__HTML__", html, altura), None


def _df_mes_filtrado(df):
    """
    Retorna df com o mês selecionado globalmente (st.session_state["global_mes_ts"]).
    Mantém TODOS os registros de outros meses para cálculos históricos,
    mas marca o mês de referência. As funções de análise usam _D.max() dos ATIVOS,
    então basta garantir que o mês escolhido seja o máximo disponível no df filtrado.
    """
    mes_ts = st.session_state.get("global_mes_ts")
    if mes_ts is None:
        return df
    df2 = df.copy()
    if "DATA" not in df2.columns:
        return df2
    df2["_D_tmp"] = pd.to_datetime(df2["DATA"], dayfirst=True, errors="coerce")
    # Remove meses posteriores ao selecionado (assim max() retorna o mês certo)
    df2 = df2[df2["_D_tmp"] <= mes_ts]
    df2 = df2.drop(columns=["_D_tmp"])
    return df2


def executar_analise(tipo, df, df_hp=None, df_rs=None):
    try:
        mapa = {
            # ── Filtro global: todos os temas usam o mesmo mês selecionado ──
            # _gm = mês selecionado no filtro global da sidebar
            # _df_g = df do HC truncado até o mês selecionado
            # Isso garante que _D.max() em cada função retorna o mês certo.
            "turnover_yoy":          lambda: analise_turnover_yoy(_df_mes_filtrado(df)),
            "hc_empresa":            lambda: analise_hc_empresa(_df_mes_filtrado(df)),
            "tipo_contrato":         lambda: analise_tipo_contrato(_df_mes_filtrado(df)),
            "top5_areas":            lambda: analise_top5_areas(_df_mes_filtrado(df)),
            "senioridade":           lambda: analise_senioridade(_df_mes_filtrado(df)),
            "inativos":              lambda: analise_inativos(_df_mes_filtrado(df)),
            "to_mensal":             lambda: analise_to_mensal(_df_mes_filtrado(df)),
            "diversidade":           lambda: analise_diversidade(_df_mes_filtrado(df)),
            "tempo_casa_ativos":     lambda: analise_tempo_casa_ativos(_df_mes_filtrado(df)),
            "tempo_casa_inativos":   lambda: analise_tempo_casa_inativos(_df_mes_filtrado(df)),
            "regrettable":           lambda: analise_regrettable_turnover(_df_mes_filtrado(df), df_hp if df_hp is not None else pd.DataFrame()),
            "to_grafico":            lambda: analise_to_grafico(_df_mes_filtrado(df)),
            "internal_movement":     lambda: analise_internal_movement(_df_mes_filtrado(df), df_rs, st.session_state.get("global_mes_ts")),
            "mulheres_empresa":      lambda: analise_mulheres_empresa(_df_mes_filtrado(df)),
            "diversidade_detalhada": lambda: analise_diversidade_detalhada(_df_mes_filtrado(df)),
            "mulheres_lideranca":    lambda: analise_mulheres_lideranca_yoy(_df_mes_filtrado(df)),
            "pretos_lideranca":      lambda: analise_pretos_lideranca_yoy(_df_mes_filtrado(df)),
            # ── R&S — usa o mesmo mês global ───────────────────────────────
            "rs_vagas_abertas":       lambda: analise_rs_vagas_abertas(df_rs, st.session_state.get("global_mes_ts")),
            "rs_vagas_fechadas_rich": lambda: analise_rs_vagas_fechadas_rich(df_rs, st.session_state.get("global_mes_ts")),
            "rs_vagas_fechadas":     lambda: analise_rs_vagas_fechadas(df_rs, st.session_state.get("global_mes_ts")),
            "rs_por_diretoria":      lambda: analise_rs_por_diretoria(df_rs, st.session_state.get("global_mes_ts")),
            "rs_por_responsavel":    lambda: analise_rs_por_responsavel(df_rs, st.session_state.get("global_mes_ts")),
            "rs_por_bp":             lambda: analise_rs_por_bp(df_rs, st.session_state.get("global_mes_ts")),
            "rs_status_vagas":       lambda: analise_rs_status_vagas(df_rs, st.session_state.get("global_mes_ts")),
            "rs_vagas_consolidadas":  lambda: analise_rs_vagas_consolidadas(df_rs),
        }
        if tipo in mapa:
            return mapa[tipo]()
    except Exception as e:
        return f"❌ **Erro:** `{str(e)[:300]}`", None


# ══════════════════════════════════════════════════════════════
#  AGENTE GROQ — perguntas livres
# ══════════════════════════════════════════════════════════════

def rodar_agente_livre(pergunta, historico, df, df_hp, contexto="", df_rs=None):
    """
    Agente em dois estágios:
    1. Tenta executar código Python para resposta precisa (dados reais)
    2. Se falhar ou produzir resultado vazio → resposta direta em linguagem natural
    """
    api_key = GROQ_API_KEY
    if not api_key:
        return [("markdown", "GROQ_API_KEY não configurada.")]
    import re

    df2 = df.copy()
    df2["_D"] = pd.to_datetime(df2["DATA"], dayfirst=True, errors="coerce")
    df2["STATUS_TIPO"] = df2["STATUS_TIPO"].str.upper().str.strip()
    # Respeita filtro global de mês
    _gm = st.session_state.get("global_mes_ts")
    if _gm is not None:
        df2 = df2[df2["_D"] <= _gm]
    mes_ref   = df2[df2["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    mes_ref_s = mes_ref.strftime("%b/%Y").upper() if pd.notna(mes_ref) else "N/A"

    emp_disp  = sorted(df2["EMPRESA"].dropna().unique().tolist())   if "EMPRESA"    in df2.columns else []
    dir_disp  = sorted(df2["DIRETORIA"].dropna().unique().tolist()) if "DIRETORIA"  in df2.columns else []
    gen_disp  = sorted(df2["GENERO"].dropna().unique().tolist())    if "GENERO"     in df2.columns else []
    etn_disp  = sorted(df2["ETNIA"].dropna().unique().tolist())     if "ETNIA"      in df2.columns else []

    # Pré-calcula resumo do mês vigente para fornecer contexto ao modelo
    df_mes = df2[(df2["STATUS_TIPO"] == "ATIVO") & (df2["_D"] == mes_ref)]
    hc_total = len(df_mes)
    hc_masc  = int(df_mes["GENERO"].str.upper().str.contains("MASCULINO", na=False).sum()) if "GENERO" in df_mes.columns else 0
    hc_fem   = hc_total - hc_masc
    hc_pret  = int((df_mes["ETNIA"].str.upper() == "PRETO").sum())  if "ETNIA" in df_mes.columns else 0
    hc_pardo = int((df_mes["ETNIA"].str.upper() == "PARDO").sum())  if "ETNIA" in df_mes.columns else 0
    hc_pcd   = int((df_mes["PCD"].astype(str).str.upper() == "SIM").sum()) if "PCD" in df_mes.columns else 0

    # ── Pré-calcula dados R&S para todos os meses disponíveis ─────────────
    rs_contexto = ""
    if df_rs is not None and not df_rs.empty:
        try:
            _df_rs_prep = _rs_prep(df_rs.copy())
            COL_FECH_RS = "Data de Fechamento (Indicador Stop)"
            COL_ALIN_RS = "Data do Alinhamento\n(Indicador Stop)"
            _fech_raw = pd.to_datetime(_df_rs_prep.get(COL_FECH_RS), errors="coerce")
            if _fech_raw.dt.tz is not None:
                _fech_raw = _fech_raw.dt.tz_localize(None)
            _alin_raw = pd.to_datetime(_df_rs_prep.get(COL_ALIN_RS), errors="coerce")
            if hasattr(_alin_raw.dt, "tz") and _alin_raw.dt.tz is not None:
                _alin_raw = _alin_raw.dt.tz_localize(None)

            # ── Pré-calcula dados RS com MoM e YoY para cada mês ──────────────
            def _rs_n(a, m):
                mask = (_fech_raw.dt.year == a) & (_fech_raw.dt.month == m)
                return int(mask.sum()), _df_rs_prep[mask.values]

            def _rs_media(df_sub, col):
                v = pd.to_numeric(df_sub.get(col, pd.Series()), errors="coerce").dropna()
                return round(v.mean(), 1) if len(v) > 0 else None

            def _pct_var(cur, ant):
                if ant and ant != 0:
                    p = round((cur - ant) / ant * 100, 0)
                    s = "▲" if p >= 0 else "▼"
                    return f"{s}{abs(int(p))}%"
                return "—"

            _rs_resumo_linhas = []
            for _delta in range(0, 13):  # últimos 12 meses
                _mv    = (mes_ref - pd.DateOffset(months=_delta)).replace(day=1)
                _mv_m  = (_mv - pd.DateOffset(months=1)).replace(day=1)   # MoM
                _mv_y  = (_mv - pd.DateOffset(years=1)).replace(day=1)    # YoY

                _n,   _df_m  = _rs_n(_mv.year,   _mv.month)
                _n_m, _df_mm = _rs_n(_mv_m.year, _mv_m.month)
                _n_y, _df_my = _rs_n(_mv_y.year, _mv_y.month)

                if _n == 0: continue

                _tth_c = _rs_media(_df_m,  "Time to Hire (Indicador Stop)")
                _ttf_c = _rs_media(_df_m,  "Time to Fill (O inicio)")
                _ttd_c = _rs_media(_df_m,  "Tempo em Definição")
                _tth_m_v = _rs_media(_df_mm, "Time to Hire (Indicador Stop)")
                _tth_y_v = _rs_media(_df_my, "Time to Hire (Indicador Stop)")

                _mes_label = _mv.strftime("%b/%Y").upper()
                _mom_n = _pct_var(_n, _n_m)
                _yoy_n = _pct_var(_n, _n_y)
                _mom_tth = _pct_var(_tth_c or 0, _tth_m_v or 0) if _tth_c and _tth_m_v else "—"
                _yoy_tth = _pct_var(_tth_c or 0, _tth_y_v or 0) if _tth_c and _tth_y_v else "—"

                _tth_s = f"{_tth_c}" if _tth_c else "—"
                _ttf_s = f"{_ttf_c}" if _ttf_c else "—"
                _ttd_s = f"{_ttd_c}" if _ttd_c else "—"

                _rs_resumo_linhas.append(
                    f"  {_mes_label}: fechadas={_n} (MoM:{_mom_n} vs {_n_m}; YoY:{_yoy_n} vs {_n_y}) | "
                    f"TTD:{_ttd_s} TTH:{_tth_s}(MoM:{_mom_tth};YoY:{_yoy_tth}) TTF:{_ttf_s} dias"
                )

                # Vagas abertas (alinhamento) apenas do mês vigente
                _mask_a = (_alin_raw.dt.year == _mv.year) & (_alin_raw.dt.month == _mv.month)
                _n_aber = int(_mask_a.sum())
                if _n_aber > 0:
                    _mask_am = (_alin_raw.dt.year == _mv_m.year) & (_alin_raw.dt.month == _mv_m.month)
                    _mask_ay = (_alin_raw.dt.year == _mv_y.year) & (_alin_raw.dt.month == _mv_y.month)
                    _n_am = int(_mask_am.sum()); _n_ay = int(_mask_ay.sum())
                    _rs_resumo_linhas.append(
                        f"  {_mes_label}: abertas={_n_aber} (MoM:{_pct_var(_n_aber,_n_am)} vs {_n_am}; YoY:{_pct_var(_n_aber,_n_ay)} vs {_n_ay})"
                    )

            rs_contexto = "\nDADOS R&S (com MoM e YoY):\n" + "\n".join(_rs_resumo_linhas) if _rs_resumo_linhas else ""
        except Exception:
            rs_contexto = ""

    client = Groq(api_key=api_key)

    # ══════════════════════════════════════════════════════════════
    # ESTÁGIO 1 — Detecta se a pergunta precisa de código
    # ══════════════════════════════════════════════════════════════
    prompt_classif = f"""Você é um assistente de People Analytics da Webmotors. Responda APENAS com dados reais fornecidos abaixo.

DADOS DISPONÍVEIS (mês filtrado: {mes_ref_s}):
- Headcount ativo: {hc_total} | Masc: {hc_masc} | Fem: {hc_fem}
- Pretos: {hc_pret} | Pardos: {hc_pardo} | PCD: {hc_pcd}
- Empresas: {emp_disp}{rs_contexto}

REGRAS OBRIGATÓRIAS:
1. Use SOMENTE os números dos DADOS DISPONÍVEIS acima. NUNCA invente.
2. Se a pergunta mencionar um mês/período ESPECÍFICO, localize o dado exato.
   Encontrou → responda com o formato abaixo.
   Não encontrou → responda APENAS: PRECISA_CODIGO
3. Perguntas sobre vagas abertas, fechadas, TTH, TTF, TTD → só responda se o mês estiver nos dados acima.
4. PRECISA_CODIGO para: turnover, por área, por cargo, análises não listadas.

FORMATO OBRIGATÓRIO DE RESPOSTA (sempre que tiver o número):
- Total: use o valor atual + MoM + YoY com o número do período comparado.
  Exemplo: "Total de Vagas Fechadas: **16** | ▼9% (18) MoM | ▲0% (21) YoY"
  Exemplo TTH: "Time to Hire (TTH): **24 dias** | ▼5% (25 dias) MoM | ▲10% (22 dias) YoY"
- Sempre use ▲ para aumento e ▼ para redução.
- Resposta em português, máx 3 linhas, sem introdução, direto ao número.

PERGUNTA: "{pergunta}"

Responda no formato acima OU com PRECISA_CODIGO:"""

    try:
        r_classif = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt_classif}],
            temperature=0.1,
            max_tokens=512,
        )
        resposta_direta = r_classif.choices[0].message.content.strip()

        # Se o modelo respondeu diretamente (sem pedir código)
        if "PRECISA_CODIGO" not in resposta_direta and len(resposta_direta) > 10:
            return [("markdown", resposta_direta)]

    except Exception:
        pass  # Cai no estágio 2

    # ══════════════════════════════════════════════════════════════
    # ESTÁGIO 2 — Gera e executa código Python para análise precisa
    # ══════════════════════════════════════════════════════════════
    # Prepara informações RS para o prompt
    _rs_disp = "df_rs disponível" if df_rs is not None and not df_rs.empty else "df_rs vazio"

    prompt_codigo = f"""Você é analista Python de RH da Webmotors. Escreva código Python PRECISO.

DADOS HEADCOUNT (df):
- STATUS_TIPO: "ATIVO"/"INATIVO" | DATA: "DD/MM/YYYY"
- EMPRESA: {emp_disp} | GENERO: {gen_disp} | ETNIA: {etn_disp}
- SENIORIDADE, AREA, CARGO, TIPO CONTRATACAO
- PCD: "SIM"/"NAO" | INICIATIVA: "EMPRESA"(involunt.)/"EMPREGADO"(volunt.)
- Mês filtrado: {mes_ref_s}

PREPARAÇÃO HC:
df_c = df.copy()
df_c["_D"] = pd.to_datetime(df_c["DATA"], dayfirst=True, errors="coerce")
df_c["STATUS_TIPO"] = df_c["STATUS_TIPO"].str.upper().str.strip()
mes_ref = df_c[df_c["STATUS_TIPO"]=="ATIVO"]["_D"].max()

DADOS R&S ({_rs_disp}):
df_rs contém dados de vagas. Colunas:
  "Data de Fechamento (Indicador Stop)": Timestamp, data de fechamento
  "Data do Alinhamento\n(Indicador Stop)": Timestamp, data de abertura
  "Time to Hire (Indicador Stop)": TTH em dias (numérico)
  "Time to Fill (O inicio)": TTF em dias (numérico)
  "Tempo em Definição": TTD em dias (numérico, NaN = sem dado)
  "Status": FECHADA / ABERTA / CANCELADA / CONGELADA
  "Diretoria", "Empresas", "Analista Responsável ", "Nível", "Nível Agrupado"
  "Motivo Abertura": SUBSTITUIÇÃO / AUMENTO DE QUADRO

FILTRAR VAGAS FECHADAS EM MÊS ESPECÍFICO:
col_fech = "Data de Fechamento (Indicador Stop)"
raw_f = pd.to_datetime(df_rs[col_fech], errors="coerce")
mask = (raw_f.dt.year == ANO) & (raw_f.dt.month == MES)
df_fech = df_rs[mask]
total = len(df_fech)
media_tth = pd.to_numeric(df_fech["Time to Hire (Indicador Stop)"], errors="coerce").dropna().mean()
media_ttd = pd.to_numeric(df_fech["Tempo em Definição"], errors="coerce").dropna().mean()

MESES (int): jan=1, fev=2, mar=3, abr=4, mai=5, jun=6, jul=7, ago=8, set=9, out=10, nov=11, dez=12

SAÍDAS (defina sempre "resultado"):
- resultado: string markdown com números reais calculados
- tabela_dados: lista de dicts [{{"col": val}}]
- tabela_titulo: string
- grafico_dados: lista de tuplas [("LABEL", valor)]
- grafico_titulo: string

FORMATO DE RESULTADO OBRIGATÓRIO:
Para perguntas de total/contagem/média com comparativo:
resultado = f"**[Métrica]:** {{valor}} | {{seta}}{{pct_mom}}% ({{val_mom}}) MoM | {{seta}}{{pct_yoy}}% ({{val_yoy}}) YoY"

Onde:
- seta = "▲" se aumentou, "▼" se reduziu
- pct = percentual de variação (abs)
- val_mom = valor do mês anterior, val_yoy = valor do mesmo mês do ano anterior

REGRAS CRÍTICAS:
1. Para R&S: use df_rs, nunca df.
2. Interprete o mês da PERGUNTA literalmente (ex: "abril 2026" → year=2026, month=4).
3. resultado deve ter os números calculados (nunca estimados).
4. Não use o filtro global — use o mês da pergunta.
5. NÃO defina grafico_dados para perguntas de total simples (total, contagem, média).
   grafico_dados = None  # para respostas de um único número
6. Sempre calcule MoM (mês anterior) e YoY (mesmo mês ano anterior).

PERGUNTA: {pergunta}

Código Python APENAS (sem markdown):"""

    try:
        r_cod = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt_codigo}],
            temperature=0.1,
            max_tokens=2500,
        )
        codigo = re.sub(r"```python|```", "", r_cod.choices[0].message.content).strip()

        _df_rs_exec = df_rs.copy() if df_rs is not None and not df_rs.empty else pd.DataFrame()
        # Aplica _rs_prep ao df_rs para que o modelo trabalhe com dados limpos
        if not _df_rs_exec.empty:
            try:
                _df_rs_exec = _rs_prep(_df_rs_exec)
            except Exception:
                pass
        local_vars = {
            "df": df.copy(),
            "df_rs": _df_rs_exec,
            "df_hp": df_hp.copy() if not isinstance(df_hp, pd.DataFrame) or not df_hp.empty else pd.DataFrame(),
            "pd": pd,
            "resultado": "", "fig": None,
            "tabela_dados": None, "tabela_titulo": "",
            "grafico_dados": None, "grafico_titulo": "",
        }
        exec(codigo, {"pd": pd}, local_vars)

        resultado      = str(local_vars.get("resultado", "")).strip()
        tabela_dados   = local_vars.get("tabela_dados")
        tabela_titulo  = local_vars.get("tabela_titulo", "")
        grafico_dados  = local_vars.get("grafico_dados")
        grafico_titulo = local_vars.get("grafico_titulo", "")

        output_parts = []

        # Gráfico Plotly
        if grafico_dados and isinstance(grafico_dados, list) and len(grafico_dados) > 0:
            try:
                import plotly.graph_objects as go
                labels = [str(x[0]) for x in grafico_dados]
                values = [float(x[1]) for x in grafico_dados]
                fig = go.Figure(go.Bar(
                    x=labels, y=values,
                    marker_color="#C0003C",
                    text=[str(round(v, 1)) for v in values],
                    textposition="outside",
                    textfont=dict(size=11, color="white", family="Poppins"),
                ))
                fig.update_layout(
                    title=dict(text=grafico_titulo, font=dict(size=14, color="white", family="Poppins"), x=0.5),
                    paper_bgcolor="#111111", plot_bgcolor="#111111",
                    font=dict(color="white", family="Poppins"),
                    xaxis=dict(showgrid=False, tickfont=dict(size=10)),
                    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", tickfont=dict(size=10)),
                    height=340, margin=dict(l=40, r=40, t=50, b=40),
                )
                output_parts.append(("plotly", fig))
            except Exception:
                pass

        # Tabela markdown
        if tabela_dados and isinstance(tabela_dados, list) and len(tabela_dados) > 0:
            try:
                cols   = list(tabela_dados[0].keys())
                header = "| " + " | ".join(cols) + " |"
                sep    = "|" + "|".join(["---"] * len(cols)) + "|"
                rows   = "\n".join(
                    "| " + " | ".join(str(row.get(c, "")) for c in cols) + " |"
                    for row in tabela_dados
                )
                md = f"**{tabela_titulo}**\n\n{header}\n{sep}\n{rows}" if tabela_titulo else f"{header}\n{sep}\n{rows}"
                output_parts.append(("markdown", md))
            except Exception:
                pass

        # Texto markdown
        if resultado and len(resultado) > 5:
            output_parts.append(("markdown", resultado))

        if output_parts:
            return output_parts

    except Exception as e:
        err_str = str(e).lower()
        if any(k in err_str for k in ("429", "quota", "rate", "limit")):
            return [("markdown", "⏱️ Limite da API Groq atingido. Aguarde alguns segundos e tente novamente.")]

    # ══════════════════════════════════════════════════════════════
    # ESTÁGIO 3 — Fallback: resposta conversacional direta
    # ══════════════════════════════════════════════════════════════
    try:
        prompt_fallback = f"""Você é analista de People Analytics da Webmotors.
Responda à pergunta abaixo em português, de forma direta e objetiva (máximo 3 parágrafos).
Use os dados disponíveis:
- Mês de referência: {mes_ref_s}
- Headcount total: {hc_total}
- Masculino: {hc_masc} ({round(hc_masc/hc_total*100,1) if hc_total else 0}%) | Feminino: {hc_fem} ({round(hc_fem/hc_total*100,1) if hc_total else 0}%)
- Pretos: {hc_pret} | Pretos+Pardos: {hc_pret+hc_pardo} | PCD: {hc_pcd}
- Empresas: {emp_disp}

PERGUNTA: {pergunta}"""

        r_fall = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt_fallback}],
            temperature=0.2,
            max_tokens=800,
        )
        return [("markdown", r_fall.choices[0].message.content.strip())]

    except Exception as e:
        return [("markdown", f"Erro ao processar: {str(e)[:200]}")]


# ══════════════════════════════════════════════════════════════
#  HELPER: renderiza resultado (markdown, html, plotly)
#  ✅ Usado tanto na exibição nova quanto no histórico
# ══════════════════════════════════════════════════════════════

def _render_resultado(resultado, fig=None):
    """
    Renderiza resultado de executar_analise().
    fig pode ser: None | Figure plotly | lista de Figure
    resultado pode ser: str markdown | ("__HTML__", html, height)
    """
    # Renderiza HTML primeiro (cards, tabelas)
    if isinstance(resultado, tuple) and resultado[0] == "__HTML__":
        _, html_content, height = resultado
        render_html_chat(html_content, height=height)
        msg = {"tipo": "html", "content": html_content, "height": height}
    else:
        st.markdown(resultado)
        msg = {"tipo": "markdown", "content": resultado}

    # Renderiza figura(s) Plotly depois do HTML (com borda sutil)
    if fig is not None:
        figs_list = fig if isinstance(fig, list) else [fig]
        for f in figs_list:
            if f is not None:
                st.markdown("""<div style="border:1px solid #e5e7eb;border-radius:12px;
                    overflow:hidden;margin-bottom:8px"></div>""", unsafe_allow_html=True)
                st.plotly_chart(f, use_container_width=True)

    return msg


def _replay_msg(msg):
    """Reproduz uma mensagem do histórico."""
    if msg.get("tipo") == "plotly":
        import plotly.io as pio
        figs_json = msg.get("figs_json") or ([msg["fig_json"]] if msg.get("fig_json") else [])
        if msg.get("tipo") == "html":
            render_html_chat(msg["content"], height=msg.get("height", 420))
        elif msg.get("content"):
            st.markdown(msg["content"])
        for fj in figs_json:
            try:
                st.plotly_chart(pio.from_json(fj), use_container_width=True)
            except Exception:
                pass
    elif msg.get("tipo") == "html_plotly":
        render_html_chat(msg["content"], height=msg.get("height", 200))
        import plotly.io as pio
        for fj in msg.get("figs_json", []):
            try:
                st.plotly_chart(pio.from_json(fj), use_container_width=True)
            except Exception:
                pass
    elif msg.get("tipo") == "html":
        render_html_chat(msg["content"], height=msg.get("height", 420))
    elif msg.get("content"):
        st.markdown(msg["content"])


# ══════════════════════════════════════════════════════════════
#  TELA DE CHAT
# ══════════════════════════════════════════════════════════════

def tela_chat(df, df_hp, df_rs, user_name: str, user_email: str):
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
            padding:8px 12px !important; transition:all .2s !important; width:100% !important;
        }
        section[data-testid="stSidebar"] .stButton button:hover { background:rgba(230,57,70,.12) !important; border-color:rgba(230,57,70,.3) !important; color:white !important; }
        section[data-testid="stSidebar"] .streamlit-expanderHeader {
            background:rgba(255,255,255,.02) !important; border:none !important; border-bottom:1px solid rgba(255,255,255,.06) !important;
            border-radius:0 !important; color:rgba(255,255,255,.45) !important;
            font-size:9px !important; font-weight:700 !important; letter-spacing:1.8px !important; text-transform:uppercase !important;
            padding:8px 4px !important; margin-bottom:2px !important;
        }
        section[data-testid="stSidebar"] .streamlit-expanderHeader:hover { color:rgba(255,255,255,.75) !important; }
        section[data-testid="stSidebar"] .streamlit-expanderContent { background:transparent !important; border:none !important; padding:4px 0 8px !important; }
        section[data-testid="stSidebar"] .stExpander { border:none !important; margin-bottom:4px !important; }
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

        emp_disp = sorted(df["EMPRESA"].dropna().unique().tolist()) if "EMPRESA" in df.columns else []
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
            key="ms_empresa", label_visibility="collapsed", placeholder="Selecione empresas..."
        )
        st.session_state["_emp_default"] = emp_sel
        if emp_sel:
            df = df[df["EMPRESA"].isin(emp_sel)]

        # ══════════════════════════════════════════════════════
        # FILTRO GLOBAL DE MÊS — agrupa por FY, aplica a TUDO
        # ══════════════════════════════════════════════════════
        st.markdown("""
        <style>
        div[data-testid="stSelectbox"] > div > div {
            background:rgba(255,255,255,.07) !important;
            border:1px solid rgba(255,255,255,.15) !important;
            border-radius:8px !important;
        }
        div[data-testid="stSelectbox"] > div > div > div { color:white !important; font-size:12px !important; font-weight:600 !important; }
        div[data-testid="stSelectbox"] svg { fill:rgba(255,255,255,.6) !important; }
        div[data-testid="stSelectbox"] label { color:rgba(255,255,255,.35) !important; font-size:9px !important; font-weight:700 !important; letter-spacing:1.5px !important; text-transform:uppercase !important; }
        li[role="option"] { color:#111 !important; }
        </style>
        """, unsafe_allow_html=True)

        # Coleta meses disponíveis do HC (coluna DATA)
        _hc_meses_ts = []
        if "DATA" in df.columns and len(df) > 0:
            _dfd_all = _prep(df.copy())
            _hc_meses_ts = sorted(
                _dfd_all[_dfd_all["STATUS_TIPO"] == "ATIVO"]["_D"].dropna().unique().tolist(),
                reverse=True
            )

        def _mes_para_fy_label(ts):
            """Retorna FY australiano de um Timestamp."""
            ano_fy = ts.year + 1 if ts.month >= 7 else ts.year
            return f"FY{str(ano_fy)[-2:]}"

        # Monta labels agrupados: "FY26 · MAI/2026"
        _opcoes_label = []
        _opcoes_ts    = []
        _fy_atual = None
        for _ts in _hc_meses_ts:
            _fy = _mes_para_fy_label(_ts)
            _label = f"{_fy} · {_ts.strftime('%b/%Y').upper()}"
            _opcoes_label.append(_label)
            _opcoes_ts.append(_ts)

        if _opcoes_label:
            # Padrão: mês mais recente (índice 0)
            _prev_g = st.session_state.get("_global_mes_label", _opcoes_label[0])
            _default_g = _opcoes_label.index(_prev_g) if _prev_g in _opcoes_label else 0

            _sel_global = st.selectbox(
                "📅 Mês de Referência",
                options=_opcoes_label,
                index=_default_g,
                key="sb_global_mes",
            )
            st.session_state["_global_mes_label"] = _sel_global
            _mes_global_ts = _opcoes_ts[_opcoes_label.index(_sel_global)]
            st.session_state["global_mes_ts"] = _mes_global_ts
            # R&S usa o mesmo mês global (unificado)
            st.session_state["rs_mes_sel"] = _mes_global_ts
        else:
            _mes_global_ts = None
            st.session_state["global_mes_ts"] = None
            st.session_state["rs_mes_sel"] = None

        st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

        # Stats do mês selecionado (não apenas o máximo)
        mes_ref_label = ""
        atm = inm = 0
        if "DATA" in df.columns and len(df) > 0:
            dfd = _prep(df.copy())
            if _mes_global_ts is not None:
                mma = _mes_global_ts
            else:
                mma = dfd[dfd["STATUS_TIPO"] == "ATIVO"]["_D"].max()
            mes_ref_label = mma.strftime("%b/%y").upper() if pd.notna(mma) else ""
            dfm = dfd[dfd["_D"] == mma]
            atm = len(dfm[dfm["STATUS_TIPO"] == "ATIVO"])
            inm = len(dfm[dfm["STATUS_TIPO"] == "INATIVO"])

        etl = df["DATA_EXTRACAO"].iloc[0] if "DATA_EXTRACAO" in df.columns and len(df) > 0 else datetime.now().strftime("%d/%m %H:%M")
        proxima_etl = proximo_5_dia_util()
        hp_info = ""
        if not df_hp.empty and "FY_HP" in df_hp.columns:
            for fy, qtd in df_hp["FY_HP"].value_counts().items(): hp_info += f"{fy}: {qtd} | "
            hp_info = hp_info.rstrip(" | ")
        hp_status = hp_info if hp_info else ("✔ carregado" if not df_hp.empty else "⚠ não carregado")

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

        with st.expander("HEADCOUNT", expanded=False):
            if st.button("Headcount por Empresa",     use_container_width=True, key="btn_hc_empresa"):
                st.session_state["analise_rapida"] = "hc_empresa"
            if st.button("Tipo de Contrato",           use_container_width=True, key="btn_tipo_contrato"):
                st.session_state["analise_rapida"] = "tipo_contrato"
            if st.button("Headcount por Senioridade",  use_container_width=True, key="btn_senioridade"):
                st.session_state["analise_rapida"] = "senioridade"
            if st.button("Top 5 Áreas",               use_container_width=True, key="btn_top5"):
                st.session_state["analise_rapida"] = "top5_areas"
            if st.button("Tempo de Casa (Ativos)",     use_container_width=True, key="btn_tempo_ativos"):
                st.session_state["analise_rapida"] = "tempo_casa_ativos"

        with st.expander("DESLIGAMENTOS", expanded=False):
            if st.button("Inativos",                   use_container_width=True, key="btn_inativos"):
                st.session_state["analise_rapida"] = "inativos"
            if st.button("TO% Mensal (Tabela)",         use_container_width=True, key="btn_to_mensal"):
                st.session_state["analise_rapida"] = "to_mensal"
            if st.button("TO% Gráfico + Tabela",        use_container_width=True, key="btn_to_grafico"):
                st.session_state["analise_rapida"] = "to_grafico"
            if st.button("Tempo de Casa (Inativos)",   use_container_width=True, key="btn_tempo_inativos"):
                st.session_state["analise_rapida"] = "tempo_casa_inativos"

        with st.expander("CAR GROUP", expanded=False):
            if st.button("Turnover (12m)",              use_container_width=True, key="btn_turnover"):
                st.session_state["analise_rapida"] = "turnover_yoy"
            if st.button("Regrettable Turnover",        use_container_width=True, key="btn_regrettable"):
                st.session_state["analise_rapida"] = "regrettable"
            if st.button("Internal Movement (Mês)",     use_container_width=True, key="btn_internal_movement"):
                st.session_state["analise_rapida"] = "internal_movement"

        with st.expander("R&S", expanded=False):
            if st.button("Vagas Abertas",            use_container_width=True, key="btn_rs_abertas"):
                st.session_state["analise_rapida"] = "rs_vagas_abertas"
            if st.button("Vagas Fechadas",            use_container_width=True, key="btn_rs_fech_rich"):
                st.session_state["analise_rapida"] = "rs_vagas_fechadas_rich"
            if st.button("Status das Vagas (resumo)",   use_container_width=True, key="btn_rs_status"):
                st.session_state["analise_rapida"] = "rs_status_vagas"
            if st.button("Vagas Fechadas Consolidadas",  use_container_width=True, key="btn_rs_consol"):
                st.session_state["analise_rapida"] = "rs_vagas_consolidadas"

        with st.expander("DIVERSIDADE", expanded=False):
            if st.button("Visão Geral",                 use_container_width=True, key="btn_diversidade"):
                st.session_state["analise_rapida"] = "diversidade"
            if st.button("% Mulheres na Empresa",       use_container_width=True, key="btn_mulheres"):
                st.session_state["analise_rapida"] = "mulheres_empresa"
            if st.button("Pretos | Pardos | PCD | +46", use_container_width=True, key="btn_recortes"):
                st.session_state["analise_rapida"] = "diversidade_detalhada"
            if st.button("Mulheres em Liderança (YoY)", use_container_width=True, key="btn_mulheres_lider"):
                st.session_state["analise_rapida"] = "mulheres_lideranca"
            if st.button("Pretos em Liderança (YoY)",   use_container_width=True, key="btn_pretos_lider"):
                st.session_state["analise_rapida"] = "pretos_lideranca"

        st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sb-section">Sessão</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("↺ Nova conversa", use_container_width=True, key="btn_nova_conversa"):
                st.session_state.update({"historico": [], "mensagens": []}); st.rerun()
        with c2:
            if st.button("→ Sair", use_container_width=True, key="btn_sair"):
                st.logout()

    # ── Área principal ─────────────────────────────────────────────────────
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

    # ── Boas-vindas ─────────────────────────────────────────────────────────
    if not st.session_state.get("mensagens"):
        import random, pytz
        from datetime import datetime as dt_
        tz_br = pytz.timezone("America/Sao_Paulo")
        hora = dt_.now(tz_br).hour
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
        st.markdown(f"""
        <div style="text-align:center;padding:48px 20px 24px">
            <div style="font-size:28px;font-weight:800;color:#c0003c;font-family:Poppins,sans-serif">
                {saudacao}, {primeiro_nome}! 👋
            </div>
            <div style="font-size:14px;color:#666;margin-top:10px;font-style:italic;font-family:Poppins,sans-serif">
                {random.choice(frases)}
            </div>
            <div style="margin-top:20px;font-size:12px;color:#aaa;font-family:Poppins,sans-serif">
                Use o sidebar para análises rápidas ou faça uma pergunta abaixo
            </div>
        </div>
        """, unsafe_allow_html=True)

    LABEL_MAP = {
        "turnover_yoy":          "Turnover (12m)",
        "regrettable":           "Regrettable Turnover",
        "hc_empresa":            "Headcount por Empresa",
        "tipo_contrato":         "Tipo de Contrato",
        "top5_areas":            "Top 5 Áreas",
        "senioridade":           "Headcount por Senioridade",
        "inativos":              "Inativos",
        "to_mensal":             "TO% Mensal (Tabela)",
        "to_grafico":            "TO% Gráfico + Tabela",
        "diversidade":           "Diversidade — Visão Geral",
        "tempo_casa_ativos":     "Tempo de Casa (Ativos)",
        "tempo_casa_inativos":   "Tempo de Casa (Inativos)",
        "internal_movement":     "Internal Movement (Mês)",
        "mulheres_empresa":      "% Mulheres na Empresa",
        "diversidade_detalhada": "Pretos | Pardos | PCD | +46",
        "mulheres_lideranca":    "Mulheres em Liderança (YoY)",
        "pretos_lideranca":      "Pretos em Liderança (YoY)",
        # R&S
        "rs_vagas_abertas":       "R&S — Vagas Abertas",
        "rs_vagas_fechadas_rich": "R&S — Vagas Fechadas",
        "rs_vagas_fechadas":     "R&S — Vagas Fechadas (Mês)",
        "rs_por_diretoria":      "R&S — Por Diretoria",
        "rs_por_responsavel":    "R&S — Por Analista Responsável",
        "rs_por_bp":             "R&S — Por BP",
        "rs_status_vagas":       "R&S — Status das Vagas",
        "rs_vagas_consolidadas":  "R&S — Vagas Fechadas Consolidadas",
    }

    # ── Histórico ──────────────────────────────────────────────────────────
    for msg in st.session_state.get("mensagens", []):
        avatar = "🧑" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar):
            _replay_msg(msg)

    # ── Análise rápida ─────────────────────────────────────────────────────
    analise_tipo = st.session_state.pop("analise_rapida", None)
    if analise_tipo:
        label = LABEL_MAP.get(analise_tipo, analise_tipo)
        st.session_state["mensagens"].append({"role": "user", "content": label})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(label)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Calculando..."):
                resultado, fig = executar_analise(analise_tipo, df, df_hp, df_rs)

            # Renderiza (HTML + figs)
            msg_dict = _render_resultado(resultado, fig)
            msg_dict["role"] = "assistant"

            # Persiste figs no histórico para replay
            if fig is not None:
                import plotly.io as pio
                figs_list = fig if isinstance(fig, list) else [fig]
                figs_json = []
                for f in figs_list:
                    try: figs_json.append(pio.to_json(f))
                    except Exception: pass
                if isinstance(resultado, tuple) and resultado[0] == "__HTML__":
                    msg_dict["tipo"] = "html_plotly"
                    msg_dict["figs_json"] = figs_json
                else:
                    msg_dict["tipo"] = "plotly"
                    msg_dict["figs_json"] = figs_json
                    msg_dict["content"] = resultado if isinstance(resultado, str) else ""

            st.session_state["mensagens"].append(msg_dict)

        st.session_state.setdefault("historico", []).extend([
            {"role": "user", "content": label},
            {"role": "assistant", "content": label + " (análise executada)"}
        ])

    # ── Pergunta livre ─────────────────────────────────────────────────────
    pergunta = st.chat_input("Faça uma pergunta livre sobre os dados...")
    if pergunta:
        st.session_state["mensagens"].append({"role": "user", "content": pergunta})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(pergunta)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Consultando agente..."):
                ctx = (f"Empresas: {sorted(df['EMPRESA'].dropna().unique().tolist())} | "
                       f"Ativos: {len(df[df['STATUS_TIPO']=='ATIVO'])} | "
                       f"Inativos: {len(df[df['STATUS_TIPO']=='INATIVO'])} | Mês ref: {mes_ref_label}") if "EMPRESA" in df.columns else ""
                try:
                    partes = rodar_agente_livre(pergunta, st.session_state.get("historico", []), df, df_hp, ctx, df_rs=df_rs)
                    if isinstance(partes, str):
                        partes = [("markdown", partes)]
                except Exception as e:
                    partes = [("markdown", f"Erro: {str(e)[:200]}")]

            resposta_texto = ""
            for tipo_p, conteudo in partes:
                if tipo_p == "html":
                    render_html_chat(conteudo)
                elif tipo_p == "plotly":
                    st.plotly_chart(conteudo, use_container_width=True)
                elif tipo_p == "markdown":
                    st.markdown(conteudo)
                    resposta_texto += conteudo + "\n"
            if not resposta_texto:
                resposta_texto = "(visualização gerada)"

        st.session_state["mensagens"].append({"role": "assistant", "content": resposta_texto})
        st.session_state.setdefault("historico", []).extend([
            {"role": "user", "content": pergunta},
            {"role": "assistant", "content": resposta_texto}
        ])
        if len(st.session_state.get("historico", [])) > 20:
            st.session_state["historico"] = st.session_state["historico"][-20:]


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def main():
    if not st.user.is_logged_in:
        tela_login()
        return

    user_email = getattr(st.user, "email", "") or ""
    user_name  = getattr(st.user, "name", "Colaborador") or "Colaborador"

    if not user_email.lower().endswith(f"@{DOMINIO_PERMITIDO}"):
        tela_acesso_negado(user_email)
        return

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
    df_rs = carregar_rs()
    tela_chat(df, df_hp, df_rs, user_name=user_name, user_email=user_email)


if __name__ == "__main__":
    main()
