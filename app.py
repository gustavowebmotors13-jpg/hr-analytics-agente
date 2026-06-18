# =============================================================
#  AGENTE ANALÍTICO DE HR — Webmotors
#  Backend: Groq Llama 3.3 70B  |  Auth: Microsoft SSO
# =============================================================

import os
import re
import io
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from groq import Groq

# ── CONFIGURAÇÕES ──────────────────────────────────────────────
st.set_page_config(
    page_title="HR Analytics · Webmotors",
    page_icon="https://raw.githubusercontent.com/gustavowebmotors13-jpg/hr-analytics-agente/main/webmotors_icon.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── SPLASH SCREEN ──────────────────────────────────────────────
_SPLASH_HTML = """<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>*{margin:0;padding:0;box-sizing:border-box}html,body{width:100%;height:100%;background:transparent;overflow:hidden}</style>
</head><body><script>
(function(){
  var doc=window.parent.document,head=doc.head||doc.getElementsByTagName('head')[0];
  var style=doc.createElement('style');
  style.id='wm-splash-style';
  style.textContent=[
    '@import url("https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap");',
    '#wm-splash-overlay{position:fixed;top:0;left:0;width:100vw;height:100vh;',
    'background:radial-gradient(ellipse at 25% 75%,rgba(192,0,60,.6) 0%,transparent 50%),',
    'radial-gradient(ellipse at 78% 18%,rgba(100,0,30,.45) 0%,transparent 50%),',
    'linear-gradient(150deg,#110509 0%,#1c0910 40%,#100716 70%,#07080f 100%);',
    'display:flex;flex-direction:column;align-items:center;justify-content:center;',
    'z-index:2147483647;opacity:1;transition:opacity .55s ease;}',
    '#wm-splash-overlay.out{opacity:0;pointer-events:none;}',
    '.wms-row{display:flex;align-items:center;gap:22px;margin-bottom:26px;}',
    '.wms-icon-box{width:72px;height:72px;border-radius:18px;background:rgba(255,255,255,.07);',
    'border:1px solid rgba(255,255,255,.13);display:flex;align-items:center;justify-content:center;',
    'box-shadow:0 0 40px rgba(192,0,60,.4);}',
    '.wms-word{font-family:"Poppins",sans-serif!important;font-size:40px;font-weight:800;',
    'color:#fff;letter-spacing:3px;text-transform:uppercase;line-height:1;}',
    '.wms-sub{font-family:"Poppins",sans-serif;font-size:11px;font-weight:600;',
    'color:rgba(255,255,255,.35);letter-spacing:5px;text-transform:uppercase;margin-bottom:52px;}',
    '.wms-track{width:200px;height:2px;background:rgba(255,255,255,.08);border-radius:2px;overflow:hidden;}',
    '.wms-fill{height:2px;background:linear-gradient(90deg,#8b001f,#C0003C,#e8385a);',
    'border-radius:2px;width:0%;animation:wmFill 2.4s cubic-bezier(.4,0,.2,1) forwards;}',
    '@keyframes wmFill{0%{width:0%}50%{width:68%}85%{width:90%}100%{width:100%}}',
  ].join('');
  head.appendChild(style);
  var div=doc.createElement('div');div.id='wm-splash-overlay';
  div.innerHTML='<div class="wms-row"><div class="wms-icon-box"><svg width="38" height="38" viewBox="0 0 38 38" fill="none"><rect x="3" y="22" width="6" height="13" rx="2" fill="#C0003C"/><rect x="11" y="15" width="6" height="20" rx="2" fill="#e0284a" opacity=".9"/><rect x="19" y="7" width="6" height="28" rx="2" fill="#C0003C"/><polyline points="6,26 14,18 22,10 30,4" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" opacity=".75"/><circle cx="30" cy="4" r="2.2" fill="white" opacity=".95"/></svg></div><span class="wms-word">WEBMOTORS</span></div><div class="wms-sub">Agente IA &nbsp;|&nbsp; HR Analytics</div><div class="wms-track"><div class="wms-fill"></div></div>';
  doc.body.appendChild(div);
  function hide(){var el=doc.getElementById('wm-splash-overlay');if(!el)return;el.classList.add('out');setTimeout(function(){if(el.parentNode)el.parentNode.removeChild(el);},600);}
  var t0=Date.now(),obs=new MutationObserver(function(){
    var s=doc.querySelector('[data-testid="stSidebar"] [data-testid="stButton"]')||doc.querySelector('[data-testid="stChatInput"]')||doc.querySelector('.sb-user');
    if(s){obs.disconnect();setTimeout(hide,600);return;}
    if(Date.now()-t0>12000){obs.disconnect();hide();}
  });
  obs.observe(doc.body,{childList:true,subtree:true});
  setTimeout(function(){obs.disconnect();hide();},12000);
})();
</script></body></html>"""
components.html(_SPLASH_HTML, height=0)

DOMINIO_PERMITIDO = "webmotors.com.br"

PARQUET_URL    = "https://raw.githubusercontent.com/gustavowebmotors13-jpg/hr-analytics-agente/main/Headcount_Consolidado.parquet?v=20260603"
HP_PARQUET_URL = "https://raw.githubusercontent.com/gustavowebmotors13-jpg/hr-analytics-agente/main/HighPerformance_Consolidado.parquet?v=20260603"
RS_PARQUET_URL = "https://raw.githubusercontent.com/gustavowebmotors13-jpg/hr-analytics-agente/main/RS_Consolidado.parquet"

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))

# ── UTILITÁRIOS ────────────────────────────────────────────────
def mes_para_fy(data: pd.Timestamp) -> str:
    if pd.isnull(data): return "OTHERS"
    ano_fy = data.year + 1 if data.month >= 7 else data.year
    return f"FY{str(ano_fy)[-2:]}"

def proximo_5_dia_util() -> str:
    import holidays
    from datetime import date, timedelta
    hoje = date.today()
    if hoje.month == 12:
        primeiro = date(hoje.year + 1, 1, 1)
    else:
        primeiro = date(hoje.year, hoje.month + 1, 1)
    feriados = holidays.Brazil(years=primeiro.year)
    count = 0; d = primeiro
    while True:
        if d.weekday() < 5 and d not in feriados:
            count += 1
            if count == 5: return d.strftime("%d/%m/%Y")
        d += timedelta(days=1)

@st.cache_data(ttl=3600)
def carregar_dados() -> pd.DataFrame:
    import requests
    r = requests.get(PARQUET_URL, timeout=60); r.raise_for_status()
    return pd.read_parquet(io.BytesIO(r.content))

@st.cache_data(ttl=3600)
def carregar_high_performance() -> pd.DataFrame:
    import requests
    try:
        r = requests.get(HP_PARQUET_URL, timeout=60)
        if r.status_code == 404: return pd.DataFrame()
        r.raise_for_status()
        return pd.read_parquet(io.BytesIO(r.content))
    except Exception: return pd.DataFrame()

@st.cache_data(ttl=3600)
def carregar_rs() -> pd.DataFrame:
    import requests
    try:
        r = requests.get(RS_PARQUET_URL, timeout=60)
        if r.status_code == 404: return pd.DataFrame()
        r.raise_for_status()
        return pd.read_parquet(io.BytesIO(r.content))
    except Exception: return pd.DataFrame()

# ══════════════════════════════════════════════════════════════
#  TELAS: LOGIN e ACESSO NEGADO
# ══════════════════════════════════════════════════════════════

def tela_login():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');
    [data-testid="stHeader"],[data-testid="stToolbar"],#MainMenu,footer{display:none!important;}
    section[data-testid="stMain"]{background:radial-gradient(ellipse at 15% 85%,rgba(180,30,60,.45) 0%,transparent 50%),radial-gradient(ellipse at 85% 15%,rgba(140,20,45,.3) 0%,transparent 50%),linear-gradient(150deg,#1a0d12 0%,#2a1020 40%,#1a0d20 70%,#0f1020 100%)!important;min-height:100vh;display:flex!important;align-items:center!important;justify-content:center!important;}
    .block-container{padding:2rem 1rem!important;max-width:460px!important;width:100%!important;}
    section[data-testid="stMain"] *{font-family:'Poppins',sans-serif!important;}
    .lc{width:100%;background:rgba(8,4,12,.85);border:1px solid rgba(255,255,255,.08);border-radius:20px;padding:36px 32px 32px;}
    .lc-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;}
    .lc-logo{display:flex;align-items:center;gap:10px;}
    .lc-icon{width:34px;height:34px;background:rgba(210,45,65,.15);border:1px solid rgba(210,45,65,.3);border-radius:9px;display:flex;align-items:center;justify-content:center;}
    .lc-name{font-size:16px;font-weight:800;color:white;letter-spacing:1.5px;text-transform:uppercase;}
    .lc-status{display:flex;align-items:center;gap:5px;font-size:10px;color:rgba(255,255,255,.25);text-transform:uppercase;}
    .lc-dot{width:6px;height:6px;background:#4ade80;border-radius:50%;display:inline-block;animation:pulse 2s infinite;}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
    .lc-div{height:1px;background:linear-gradient(90deg,transparent,rgba(210,45,65,.35),transparent);margin-bottom:24px;}
    .lc-title{font-size:28px;font-weight:800;color:white;letter-spacing:-.5px;line-height:1.1;margin-bottom:6px;text-transform:uppercase;}
    .lc-title span{color:#d9304f;}
    .lc-sub{font-size:10px;color:rgba(255,255,255,.28);margin-bottom:28px;letter-spacing:.8px;text-transform:uppercase;}
    .lc-info{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:12px 14px;margin-bottom:20px;font-size:11px;color:rgba(255,255,255,.45);line-height:1.6;}
    .lc-info strong{color:rgba(255,255,255,.65);}
    div[data-testid="stButton"]>button{background:rgba(255,255,255,.06)!important;border:1px solid rgba(255,255,255,.12)!important;border-radius:10px!important;color:white!important;font-size:13px!important;font-weight:600!important;padding:12px!important;width:100%!important;}
    div[data-testid="stButton"]>button:hover{background:rgba(0,120,212,.2)!important;border-color:rgba(0,120,212,.5)!important;}
    </style>""", unsafe_allow_html=True)
    st.markdown('''
    <div class="lc">
      <div class="lc-top">
        <div class="lc-logo">
          <div class="lc-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#d9304f" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg></div>
          <span class="lc-name">Webmotors</span>
        </div>
        <div class="lc-status"><span class="lc-dot"></span> Sistema Ativo</div>
      </div>
      <div class="lc-div"></div>
      <div class="lc-title">Pessoas<br>&amp; <span>Cultura</span></div>
      <div class="lc-sub">Dados de Ativos &amp; Inativos — Headcount ETL</div>
      <div class="lc-info">🔐 <strong>Acesso restrito</strong><br>Sistema exclusivo para colaboradores Webmotors.<br>Utilize seu e-mail corporativo <strong>@webmotors.com.br</strong> para autenticar.</div>
    </div>''', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Entrar com conta Microsoft", use_container_width=True): st.login()

def tela_acesso_negado(email: str):
    st.markdown("""<style>[data-testid="stHeader"],[data-testid="stToolbar"],#MainMenu,footer{display:none!important;}
    section[data-testid="stMain"]{background:#0f0f11!important;}</style>""", unsafe_allow_html=True)
    st.error("🚫 **Acesso negado**")
    st.markdown(f"O e-mail **`{email}`** não pertence ao domínio `@{DOMINIO_PERMITIDO}`.")
    if st.button("← Sair", key="btn_sair_login"): st.logout()

# ══════════════════════════════════════════════════════════════
#  UTILITÁRIOS DE CÁLCULO (compartilhados por todas as funções)
# ══════════════════════════════════════════════════════════════

def _prep(df):
    df = df.copy()
    if "DATA" in df.columns:
        df["_D"] = pd.to_datetime(df["DATA"], dayfirst=True, errors="coerce")
    else:
        df["_D"] = pd.NaT
    if "STATUS_TIPO" in df.columns:
        df["STATUS_TIPO"] = df["STATUS_TIPO"].fillna("").str.upper().str.strip()
    elif "STATUS" in df.columns:
        def _m(s):
            s = str(s).upper().strip()
            if s == "ATIVO": return "ATIVO"
            if s in ("INATIVO","DESLIGADO","DEMITIDO","RESCINDIDO"): return "INATIVO"
            return s
        df["STATUS_TIPO"] = df["STATUS"].fillna("").apply(_m)
    else:
        df["STATUS_TIPO"] = "ATIVO"
    if "INICIATIVA" in df.columns:
        ini = df["INICIATIVA"].fillna("").str.upper()
        df["_INI_INV"] = ini.str.contains("EMPRESA",  na=False)
        df["_INI_VOL"] = ini.str.contains("EMPREGADO", na=False)
    else:
        df["_INI_INV"] = False; df["_INI_VOL"] = False
    return df

def _pct(v, t):  return round(v / t * 100, 1) if t > 0 else 0
def _var(a, b):  return round((a - b) / b * 100, 1) if b > 0 else 0
def _sinal(v):   return "▲" if v >= 0 else "▼"
def _fmt_anos(a):
    anos = int(a); meses = int((a - anos) * 12)
    return f"{anos} anos e {meses} meses"
def _norm_cpf(v):
    if not v or str(v).strip().lower() in ("nan","none",""): return ""
    s = re.sub(r'[.\-\s]','',str(v).strip()); s = re.sub(r'\.0$','',s)
    return s.zfill(11)

def render_html_chat(html_content: str, height: int = 420):
    full_html = f"""<html><head>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>*{{box-sizing:border-box;margin:0;padding:0;font-family:'Poppins',sans-serif;}}body{{background:transparent;padding:4px 2px;}}</style>
    </head><body>{html_content}</body></html>"""
    components.html(full_html, height=height, scrolling=False)

def _rs_prep(df_rs):
    df = df_rs.copy()
    for col in ("Data de Fechamento (Indicador Stop)", "Data do Alinhamento\n(Indicador Stop)"):
        if col in df.columns:
            raw = pd.to_datetime(df[col], errors="coerce")
            if raw.dt.tz is not None: raw = raw.dt.tz_localize(None)
            df[col] = raw
    for c in ("Time to Hire (Indicador Stop)", "Time to Fill (O inicio)", "Tempo em Definição"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def _hc_medio_12m(df, mes_fim):
    meses = pd.date_range(start=(mes_fim - pd.DateOffset(months=11)).replace(day=1), end=mes_fim, freq="MS")
    dados = []
    for mes in meses:
        hc = len(df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes)])
        dados.append((mes, hc))
    hcs = [hc for _, hc in dados if hc > 0]
    return (round(sum(hcs)/len(hcs), 1) if hcs else 0), dados

def _df_mes_filtrado(df):
    mes_ts = st.session_state.get("global_mes_ts")
    if mes_ts is None: return df
    df2 = df.copy()
    df2["_D_tmp"] = pd.to_datetime(df2["DATA"], dayfirst=True, errors="coerce")
    df2 = df2[df2["_D_tmp"] <= mes_ts].drop(columns=["_D_tmp"])
    return df2

# ══════════════════════════════════════════════════════════════
#  FUNÇÕES DE ANÁLISE — SIDEBAR (100% pandas)
# ══════════════════════════════════════════════════════════════

def analise_hc_empresa(df):
    df = _prep(df)
    mes_ref = df[df["STATUS_TIPO"]=="ATIVO"]["_D"].max()
    mes_yoy = mes_ref - pd.DateOffset(years=1)
    ref = df[(df["STATUS_TIPO"]=="ATIVO")&(df["_D"]==mes_ref)].groupby("EMPRESA").size()
    yoy = df[(df["STATUS_TIPO"]=="ATIVO")&(df["_D"]==mes_yoy)].groupby("EMPRESA").size()
    linhas = [f"**Headcount por Empresa — {mes_ref.strftime('%b/%y').upper()}**\n"]
    for emp in ref.index:
        atual=int(ref[emp]); ant=int(yoy.get(emp,0)); v=_var(atual,ant); s=_sinal(v)
        linhas.append(f"**{emp}:** {atual} colaboradores · {s} **{abs(v)}% YoY** ({mes_yoy.strftime('%b/%y').upper()}: {ant})")
    total_atual=int(ref.sum()); total_ant=int(yoy.sum()); vg=_var(total_atual,total_ant)
    linhas.append(f"\n---\n**📊 Grupo:** {total_atual} ativos · {'crescimento' if vg>=0 else 'redução'} de **{abs(vg)}% YoY** vs {total_ant}")
    return "\n\n".join(linhas), None

def analise_tipo_contrato(df):
    df = _prep(df)
    mes_ref=df[df["STATUS_TIPO"]=="ATIVO"]["_D"].max(); mes_yoy=mes_ref-pd.DateOffset(years=1)
    ref=df[(df["STATUS_TIPO"]=="ATIVO")&(df["_D"]==mes_ref)].groupby("TIPO CONTRATACAO").size()
    yoy=df[(df["STATUS_TIPO"]=="ATIVO")&(df["_D"]==mes_yoy)].groupby("TIPO CONTRATACAO").size()
    linhas=[f"**Tipo de Contratação — {mes_ref.strftime('%b/%y').upper()} vs {mes_yoy.strftime('%b/%y').upper()}**\n",
            "| Tipo | Qtd | YoY | Var% |","|---|---|---|---|"]
    for tp in ref.index:
        atual=int(ref[tp]); ant=int(yoy.get(tp,0)); v=_var(atual,ant); s=_sinal(v)
        linhas.append(f"| {tp} | {atual} | {ant} | {s} {abs(v)}% |")
    tv=_var(ref.sum(),yoy.sum())
    linhas.append(f"| **TOTAL** | **{int(ref.sum())}** | **{int(yoy.sum())}** | {_sinal(tv)} {abs(tv)}% |")
    return "\n".join(linhas), None

def analise_top5_areas(df):
    df=_prep(df); mes_ref=df[df["STATUS_TIPO"]=="ATIVO"]["_D"].max()
    df_ref=df[(df["STATUS_TIPO"]=="ATIVO")&(df["_D"]==mes_ref)]
    top5=df_ref.groupby("AREA").size().sort_values(ascending=False).head(5); total=len(df_ref)
    linhas=[f"**Top 5 Áreas — {mes_ref.strftime('%b/%y').upper()}** (Total: {total})\n","| # | Área | HC | % |","|---|---|---|---|"]
    for i,(area,qtd) in enumerate(top5.items(),1):
        linhas.append(f"| {i}º | {area} | {int(qtd)} | {_pct(qtd,total)}% |")
    return "\n".join(linhas), None

def analise_senioridade(df):
    df=_prep(df); mes_ref=df[df["STATUS_TIPO"]=="ATIVO"]["_D"].max()
    df_ref=df[(df["STATUS_TIPO"]=="ATIVO")&(df["_D"]==mes_ref)]
    sen=df_ref.groupby("SENIORIDADE").size().sort_index(); total=len(df_ref)
    linhas=[f"**Headcount por Senioridade — {mes_ref.strftime('%b/%y').upper()}** (Total: {total})\n","| Senioridade | HC | % |","|---|---|---|"]
    for s,qtd in sen.items(): linhas.append(f"| {s} | {int(qtd)} | {_pct(qtd,total)}% |")
    return "\n".join(linhas), None

def analise_inativos(df):
    df=_prep(df)
    mes_ref_inat=df[df["STATUS_TIPO"]=="INATIVO"]["_D"].max()
    mes_ant=(mes_ref_inat-pd.DateOffset(months=1)).replace(day=1)
    mes_ref_ativ=df[df["STATUS_TIPO"]=="ATIVO"]["_D"].max()
    inat_mes=df[(df["STATUS_TIPO"]=="INATIVO")&(df["_D"]==mes_ref_inat)]
    inat_ant=df[(df["STATUS_TIPO"]=="INATIVO")&(df["_D"]==mes_ant)]
    hc_ref=len(df[(df["STATUS_TIPO"]=="ATIVO")&(df["_D"]==mes_ref_ativ)])
    total=len(inat_mes); ant=len(inat_ant)
    inv=int(inat_mes["INICIATIVA"].str.upper().str.contains("EMPRESA",na=False).sum())
    vol=int(inat_mes["INICIATIVA"].str.upper().str.contains("EMPREGADO",na=False).sum())
    to_pct=_pct(total,hc_ref); var_mom=total-ant; s=_sinal(var_mom)
    narrativa=f"\n---\n**📊** {'Involuntários' if inv>vol else 'Voluntários'} lideram. TO% de **{to_pct}%** {'⚠️ acima da faixa saudável' if to_pct>2 else '✅ dentro da faixa saudável'}. {'⚠️ Volume aumentou vs mês anterior.' if var_mom>0 else '✅ Volume reduziu vs mês anterior.'}"
    return (f"**Desligamentos — {mes_ref_inat.strftime('%b/%y').upper()}**\n\n"
            f"- **Total:** {total} ({s} {abs(var_mom)} vs mês anterior: {ant})\n"
            f"- **Involuntários:** {inv}\n- **Voluntários:** {vol}\n- **TO% do mês:** {to_pct}%\n"+narrativa), None

def analise_turnover_yoy(df):
    df=_prep(df); mes_max=df[df["STATUS_TIPO"]=="ATIVO"]["_D"].max()
    def _periodo(offset, janela=12):
        mes_fim=(mes_max-pd.DateOffset(months=offset)).replace(day=1)
        mes_ini=(mes_fim-pd.DateOffset(months=janela-1)).replace(day=1)
        hc_med,_=_hc_medio_12m(df,mes_fim)
        inat=df[(df["STATUS_TIPO"]=="INATIVO")&(df["_D"]>=mes_ini)&(df["_D"]<=mes_fim)]
        inv=int(inat["INICIATIVA"].str.upper().str.contains("EMPRESA",na=False).sum())
        vol=int(inat["INICIATIVA"].str.upper().str.contains("EMPREGADO",na=False).sum())
        ti=_pct(inv,hc_med); tv=_pct(vol,hc_med); tt=_pct(inv+vol,hc_med)
        label=f"{mes_ini.strftime('%b/%y').upper()} → {mes_fim.strftime('%b/%y').upper()}"
        return label,round(hc_med,1),inv,vol,ti,tv,tt
    l0,hc0,i0,v0,ti0,tv0,tt0=_periodo(12)
    l1,hc1,i1,v1,ti1,tv1,tt1=_periodo(0)
    var_total=_var(tt1,tt0); var_vol=_var(tv1,tv0); var_inv=_var(ti1,ti0)
    s_total="crescimento" if var_total>=0 else "redução"
    narrativa=(f"\n\n---\n**📊 Análise:** Turnover total **{tt1}%** — {s_total} de **{abs(var_total)}%** vs período anterior ({tt0}%). "
               f"Voluntário ({'▲' if var_vol>=0 else '▼'} {abs(var_vol)}%): {'atenção recomendada' if tv1>tv0 else 'melhora'}. "
               f"Involuntário ({'▲' if var_inv>=0 else '▼'} {abs(var_inv)}%): {'aumentou' if ti1>ti0 else 'reduziu'}.")
    tabela=(f"| Métrica | {l0} | {l1} |\n|---|---|---|\n"
            f"| HC Médio (12m) | {hc0} | {hc1} |\n"
            f"| Deslig. Involuntários | {i0} | {i1} |\n"
            f"| Deslig. Voluntários | {v0} | {v1} |\n"
            f"| Turnover % Inv | {ti0}% | {ti1}% |\n"
            f"| Turnover % Vol | {tv0}% | {tv1}% |\n"
            f"| Turnover % Total | {tt0}% | {tt1}% |\n")
    return tabela+narrativa, None

def analise_to_mensal(df):
    df=_prep(df); mes_max=df[df["STATUS_TIPO"]=="ATIVO"]["_D"].max()
    meses=pd.date_range(start=(mes_max-pd.DateOffset(months=11)).replace(day=1),end=mes_max,freq="MS")
    linhas=["**TO% Mensal — Últimos 12 meses**\n","| Mês/Ano | HC | Inv | Vol | TO% Inv | TO% Vol | TO% Total |","|---|---|---|---|---|---|---|"]
    t_inv=t_vol=0; hc_list=[]
    for mes in meses:
        at=df[(df["STATUS_TIPO"]=="ATIVO")&(df["_D"]==mes)]
        inat=df[(df["STATUS_TIPO"]=="INATIVO")&(df["_D"]==mes)]
        hc=len(at)
        inv=int(inat["INICIATIVA"].str.upper().str.contains("EMPRESA",na=False).sum())
        vol=int(inat["INICIATIVA"].str.upper().str.contains("EMPREGADO",na=False).sum())
        ti=_pct(inv,hc); tv=_pct(vol,hc); tt=_pct(inv+vol,hc)
        linhas.append(f"| {mes.strftime('%b/%Y').upper()} | {hc} | {inv} | {vol} | {ti}% | {tv}% | {tt}% |")
        t_inv+=inv; t_vol+=vol
        if hc>0: hc_list.append(hc)
    hc_med=round(sum(hc_list)/len(hc_list),1) if hc_list else 0
    ti_ac=_pct(t_inv,hc_med); tv_ac=_pct(t_vol,hc_med); tt_ac=_pct(t_inv+t_vol,hc_med)
    linhas.append(f"| **ACUMULADO 12m** | **{hc_med}** | **{t_inv}** | **{t_vol}** | **{ti_ac}%** | **{tv_ac}%** | **{tt_ac}%** |")
    return "\n".join(linhas), None

def analise_to_grafico(df):
    import plotly.graph_objects as go
    df=_prep(df); mes_max=df[df["STATUS_TIPO"]=="ATIVO"]["_D"].max()
    meses=pd.date_range(start=(mes_max-pd.DateOffset(months=23)).replace(day=1),end=mes_max,freq="MS")
    dados=[]
    for mes in meses:
        at=df[(df["STATUS_TIPO"]=="ATIVO")&(df["_D"]==mes)]
        inat=df[(df["STATUS_TIPO"]=="INATIVO")&(df["_D"]==mes)]
        hc=len(at)
        inv=int(inat["INICIATIVA"].str.upper().str.contains("EMPRESA",na=False).sum())
        vol=int(inat["INICIATIVA"].str.upper().str.contains("EMPREGADO",na=False).sum())
        fy=df[df["_D"]==mes]["FY"].iloc[0] if len(df[df["_D"]==mes])>0 and "FY" in df.columns else ""
        dados.append({"mes":mes,"hc":hc,"inv":inv,"vol":vol,"total":inv+vol,"to_pct":_pct(inv+vol,hc),"to_inv":_pct(inv,hc),"to_vol":_pct(vol,hc),"fy":fy})
    df_to=pd.DataFrame(dados); df_to=df_to[df_to["hc"]>0]
    labels=[m.strftime("%b/%y").upper() for m in df_to["mes"]]
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=labels,y=df_to["to_pct"],fill="tozeroy",fillcolor="rgba(192,0,60,0.15)",
        line=dict(color="#C0003C",width=2.5),mode="lines+markers+text",
        text=[f"{v}%" for v in df_to["to_pct"]],textposition="top center",
        textfont=dict(size=11,color="white",family="Poppins"),
        marker=dict(size=8,color="#C0003C",line=dict(color="white",width=1.5)),
        name="TO% Total",hovertemplate="<b>%{x}</b><br>TO%: %{y}%<extra></extra>"))
    fig.update_layout(title=dict(text="Turnover Mensal (24 meses)",font=dict(size=16,color="white",family="Poppins"),x=0.5),
        paper_bgcolor="#111111",plot_bgcolor="#111111",font=dict(color="white",family="Poppins"),
        xaxis=dict(showgrid=False,tickfont=dict(size=11)),
        yaxis=dict(showgrid=True,gridcolor="rgba(255,255,255,0.08)",ticksuffix="%",tickfont=dict(size=11)),
        height=380,margin=dict(l=40,r=40,t=50,b=40),hovermode="x unified")
    tabela=["**Detalhe por FY**\n","| FY | Mês | HC | Inativos | TO% Inv | TO% Vol | TO% Total |","|---|---|---|---|---|---|---|"]
    for _,row in df_to.sort_values("mes",ascending=False).iterrows():
        tabela.append(f"| {row['fy']} | {row['mes'].strftime('%b/%Y').upper()} | {int(row['hc'])} | {int(row['total'])} | {row['to_inv']}% | {row['to_vol']}% | {row['to_pct']}% |")
    return "\n".join(tabela), fig

def analise_diversidade(df):
    df=_prep(df); mes_ref=df[df["STATUS_TIPO"]=="ATIVO"]["_D"].max(); mes_yoy=mes_ref-pd.DateOffset(years=1)
    def _m(sub):
        hc=len(sub)
        masc=int(sub["GENERO"].str.upper().str.contains("MASCULINO",na=False).sum()) if "GENERO" in sub.columns else 0
        fem=int(sub["GENERO"].str.upper().str.contains("FEMININO",na=False).sum()) if "GENERO" in sub.columns else 0
        pret=int(sub["ETNIA"].str.upper().str.contains("^PRETO$",na=False).sum()) if "ETNIA" in sub.columns else 0
        pp=int(sub["ETNIA"].str.upper().str.contains("PRETO|PARDO",na=False).sum()) if "ETNIA" in sub.columns else 0
        pcd=int((sub["PCD"]=="SIM").sum()) if "PCD" in sub.columns else 0
        m46=int((sub["+46"]=="SIM").sum()) if "+46" in sub.columns else 0
        return [hc,masc,fem,pret,pp,pcd,m46]
    r=_m(df[(df["STATUS_TIPO"]=="ATIVO")&(df["_D"]==mes_ref)])
    y=_m(df[(df["STATUS_TIPO"]=="ATIVO")&(df["_D"]==mes_yoy)])
    specs=[("HEADCOUNT",r[0],y[0],None),("MASCULINO",r[1],y[1],r[0]),("FEMININO",r[2],y[2],r[0]),
           ("PRETOS",r[3],y[3],r[0]),("PRETOS & PARDOS",r[4],y[4],r[0]),("PCD",r[5],y[5],r[0]),("FAIXA +46",r[6],y[6],r[0])]
    cards_html=""
    for label,vr,vy,total in specs:
        pct_str=f"{_pct(vr,total)}%" if total else ""
        yoy_delta=_var(vr,vy); yoy_cor="#2ecc71" if yoy_delta>=0 else "#e74c3c"
        yoy_sinal="▲" if yoy_delta>=0 else "▼"
        yoy_str=f'<span style="color:{yoy_cor};font-size:9px;font-weight:600">{yoy_sinal} {abs(yoy_delta)}% YoY ({vy})</span>'
        pct_badge=f'<div style="position:absolute;top:12px;right:14px;font-size:10px;font-weight:700;color:#ccc;background:#f5f5f5;border-radius:4px;padding:2px 6px">{pct_str}</div>' if pct_str else ""
        cards_html+=f'<div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:14px 16px;position:relative"><div style="font-size:9px;font-weight:700;letter-spacing:1.2px;color:#aaa;text-transform:uppercase;margin-bottom:6px">{label}</div>{pct_badge}<div style="font-size:32px;font-weight:800;color:#111;line-height:1;margin-bottom:8px">{vr:,}</div><div style="border-top:1px solid #f0f0f0;padding-top:6px">{yoy_str}</div></div>'
    html=f'<div style="font-family:Poppins,sans-serif;padding:4px 0 12px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:16px"><div style="width:3px;height:18px;background:#F2214B;border-radius:2px"></div><span style="font-size:11px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">Diversidade — {mes_ref.strftime("%b/%y").upper()}</span></div><div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">{cards_html}</div></div>'
    return ("__HTML__",html,460), None

def analise_tempo_casa_ativos(df):
    df=_prep(df); mes_ref=df[df["STATUS_TIPO"]=="ATIVO"]["_D"].max()
    df_ref=df[(df["STATUS_TIPO"]=="ATIVO")&(df["_D"]==mes_ref)].copy()
    df_ref["_ADM"]=pd.to_datetime(df_ref["DATA DE ADMISSAO"],dayfirst=True,errors="coerce")
    df_ref["_ANOS"]=(mes_ref-df_ref["_ADM"]).dt.days/365.25
    df_ref=df_ref.dropna(subset=["_ANOS"]); total=len(df_ref); media=df_ref["_ANOS"].mean()
    faixas=[("<1 ano",df_ref[df_ref["_ANOS"]<1]),("1-2 anos",df_ref[(df_ref["_ANOS"]>=1)&(df_ref["_ANOS"]<2)]),
            ("2-5 anos",df_ref[(df_ref["_ANOS"]>=2)&(df_ref["_ANOS"]<5)]),("5-10 anos",df_ref[(df_ref["_ANOS"]>=5)&(df_ref["_ANOS"]<10)]),(">10 anos",df_ref[df_ref["_ANOS"]>=10])]
    linhas=[f"**Tempo de Casa — Ativos ({mes_ref.strftime('%b/%y').upper()})**\n",f"- **Média geral:** {_fmt_anos(media)} | Total: {total}\n","| Faixa | Qtd | % |","|---|---|---|"]
    for nome,sub in faixas: linhas.append(f"| {nome} | {len(sub)} | {_pct(len(sub),total)}% |")
    return "\n".join(linhas), None

def analise_tempo_casa_inativos(df):
    df=_prep(df); mes_max=df[df["STATUS_TIPO"]=="ATIVO"]["_D"].max(); mes_ini=mes_max-pd.DateOffset(months=11)
    df_in=df[(df["STATUS_TIPO"]=="INATIVO")&(df["_D"]>=mes_ini)&(df["_D"]<=mes_max)].copy()
    df_in["_ADM"]=pd.to_datetime(df_in["DATA DE ADMISSAO"],dayfirst=True,errors="coerce")
    df_in["_DESL"]=pd.to_datetime(df_in["DATA DESLIGAMENTO"],dayfirst=True,errors="coerce")
    df_in["_ANOS"]=(df_in["_DESL"]-df_in["_ADM"]).dt.days/365.25
    df_in=df_in.dropna(subset=["_ANOS"]); total=len(df_in); media=df_in["_ANOS"].mean() if total>0 else 0
    faixas=[("<1 ano",df_in[df_in["_ANOS"]<1]),("1-2 anos",df_in[(df_in["_ANOS"]>=1)&(df_in["_ANOS"]<2)]),
            ("2-5 anos",df_in[(df_in["_ANOS"]>=2)&(df_in["_ANOS"]<5)]),("5-10 anos",df_in[(df_in["_ANOS"]>=5)&(df_in["_ANOS"]<10)]),(">10 anos",df_in[df_in["_ANOS"]>=10])]
    linhas=[f"**Tempo de Casa — Inativos ({mes_ini.strftime('%b/%y').upper()} → {mes_max.strftime('%b/%y').upper()})**\n",f"- **Média geral:** {_fmt_anos(media)} | Total: {total}\n","| Faixa | Qtd | % |","|---|---|---|"]
    for nome,sub in faixas: linhas.append(f"| {nome} | {len(sub)} | {_pct(len(sub),total)}% |")
    return "\n".join(linhas), None

def analise_regrettable_turnover(df_hc,df_hp):
    if df_hp.empty: return "⚠️ **High Performance não encontrado.** Execute o ETL.", None
    if "CPF" not in df_hc.columns: return "⚠️ Coluna CPF não encontrada.", None
    df_hc=_prep(df_hc); df_hp=df_hp.copy()
    df_hc["_CPF"]=df_hc["CPF"].apply(_norm_cpf)
    df_hp["_CPF"]=df_hp["CPF"].apply(_norm_cpf) if "CPF" in df_hp.columns else ""
    mes_ref=df_hc[df_hc["STATUS_TIPO"]=="ATIVO"]["_D"].max(); mes_yoy=mes_ref-pd.DateOffset(years=1)
    def _calc(mes):
        fy_mes=mes_para_fy(mes)
        hp_fy=df_hp[df_hp["FY_HP"]==fy_mes] if "FY_HP" in df_hp.columns else df_hp
        cpfs_talentos=set(hp_fy[hp_fy["_CPF"]!=""]["_CPF"].unique())
        hc=len(df_hc[(df_hc["STATUS_TIPO"]=="ATIVO")&(df_hc["_D"]==mes)])
        inat_vol=df_hc[(df_hc["STATUS_TIPO"]=="INATIVO")&(df_hc["_D"]==mes)&(df_hc["INICIATIVA"].str.upper().str.contains("EMPREGADO",na=False))]
        talentos_deslig=inat_vol[inat_vol["_CPF"].isin(cpfs_talentos)]
        qtd=len(talentos_deslig); to_pct=_pct(qtd,hc)
        det=[f"{r.get('NOME COMPLETO','?')} ({hp_fy[hp_fy['_CPF']==r['_CPF']].iloc[0].get('H_P','') if r['_CPF'] in set(hp_fy['_CPF']) else ''})" for _,r in talentos_deslig.iterrows()]
        return hc,qtd,to_pct,det,fy_mes
    hc_r,reg_r,to_r,det_r,fy_r=_calc(mes_ref); hc_y,reg_y,to_y,det_y,fy_y=_calc(mes_yoy)
    var_yoy=_var(reg_r,reg_y); s=_sinal(var_yoy)
    linhas=[f"**Regrettable Turnover — {mes_ref.strftime('%b/%y').upper()}**\n","| Métrica | "+mes_yoy.strftime('%b/%y').upper()+f" ({fy_y}) | "+mes_ref.strftime('%b/%y').upper()+f" ({fy_r}) |",
            "|---|---|---|",f"| HC | {hc_y} | {hc_r} |",f"| Deslig. Vol. Talentos | {reg_y} | {reg_r} |",f"| Regrettable TO% | {to_y}% | {to_r}% |",
            "",f"**YoY:** {s} {abs(var_yoy)}% vs {mes_yoy.strftime('%b/%y').upper()}"]
    if det_r: linhas.append(f"\n**Talentos desligados em {mes_ref.strftime('%b/%y').upper()} ({fy_r}):**")
    for d in det_r: linhas.append(f"- {d}")
    if not det_r: linhas.append(f"\n✅ Nenhum talento {fy_r} desligado voluntariamente.")
    return "\n".join(linhas), None

# ══════════════════════════════════════════════════════════════
#  FUNÇÕES DIVERSIDADE + INTERNAL MOVEMENT
# ══════════════════════════════════════════════════════════════

def analise_mulheres_empresa(df):
    df=_prep(df); ativos=df[df["STATUS_TIPO"]=="ATIVO"]; mes_ref=ativos["_D"].max()
    mes_ant=(mes_ref-pd.DateOffset(months=1)).replace(day=1)
    def _pf(sub): t=len(sub); f=len(sub[sub["GENERO"].str.upper()=="FEMININO"]) if "GENERO" in sub.columns else 0; return t,f,_pct(f,t)
    hc_a,f_a,pct_a=_pf(ativos[ativos["_D"]==mes_ref]); hc_b,f_b,pct_b=_pf(ativos[ativos["_D"]==mes_ant])
    delta=pct_a-pct_b; cor="#2ecc71" if delta>=0 else "#e74c3c"; sinal="▲" if delta>=0 else "▼"
    html=f'<div style="font-family:Poppins,sans-serif;padding:4px 0 12px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:14px"><div style="width:4px;height:22px;background:#F2214B;border-radius:2px"></div><span style="font-size:13px;font-weight:700;letter-spacing:.5px;color:#111;text-transform:uppercase">% Mulheres na Empresa</span></div><div style="text-align:center;padding:24px 16px;background:#fafafa;border-radius:12px;margin-bottom:12px"><div style="font-size:56px;font-weight:800;color:#F2214B;line-height:1">{pct_a:.1f}%</div><div style="font-size:13px;color:#666;margin-top:8px">{f_a} mulheres de {hc_a} colaboradores</div><div style="font-size:12px;color:{cor};margin-top:8px;font-weight:600">{sinal} {abs(delta):.1f}pp vs mês anterior ({pct_b:.1f}%)</div></div></div>'
    return ("__HTML__",html,240), None

def analise_diversidade_detalhada(df):
    df=_prep(df); ativos=df[df["STATUS_TIPO"]=="ATIVO"]; mes_ref=ativos["_D"].max()
    mes_ant12=(mes_ref-pd.DateOffset(months=12)).replace(day=1)
    atual=ativos[ativos["_D"]==mes_ref]; ano_atras=ativos[ativos["_D"]==mes_ant12]
    def _etnia(sub,val): return len(sub[sub["ETNIA"].str.upper()==val]) if "ETNIA" in sub.columns else 0
    def _pcd_(sub): return len(sub[sub["PCD"].astype(str).str.upper().isin(["SIM","S","1","TRUE"])]) if "PCD" in sub.columns else 0
    def _faixa(sub): return len(sub[sub["+46"].astype(str).str.upper()=="SIM"]) if "+46" in sub.columns else 0
    metricas=[("✊","Pretos",_etnia(atual,"PRETO"),_etnia(ano_atras,"PRETO")),
              ("✊","Pretos+Pardos",_etnia(atual,"PRETO")+_etnia(atual,"PARDO"),_etnia(ano_atras,"PRETO")+_etnia(ano_atras,"PARDO")),
              ("♿","PCD",_pcd_(atual),_pcd_(ano_atras)),("👴","+46 anos",_faixa(atual),_faixa(ano_atras))]
    cards=""
    for icon,label,vc,va in metricas:
        delta=vc-va; cor="#2ecc71" if delta>=0 else "#e74c3c"; sinal="▲" if delta>=0 else "▼"
        cards+=f'<div style="background:#fafafa;border-radius:10px;padding:16px;text-align:center;border:1px solid #eee"><div style="font-size:20px;margin-bottom:4px">{icon}</div><div style="font-size:10px;font-weight:700;color:#888;text-transform:uppercase;margin-bottom:8px">{label}</div><div style="font-size:36px;font-weight:800;color:#111">{vc}</div><div style="font-size:10px;color:{cor};font-weight:600;margin-top:6px">{sinal} {abs(delta)} vs mesmo mês ano anterior</div></div>'
    html=f'<div style="font-family:Poppins,sans-serif;padding:4px 0 12px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:14px"><div style="width:4px;height:22px;background:#F2214B;border-radius:2px"></div><span style="font-size:13px;font-weight:700;letter-spacing:.5px;color:#111;text-transform:uppercase">Diversidade — Recortes</span></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">{cards}</div></div>'
    return ("__HTML__",html,320), None

def analise_mulheres_lideranca_yoy(df):
    df=_prep(df); ativos=df[df["STATUS_TIPO"]=="ATIVO"]; mes_ref=ativos["_D"].max(); mes_ant12=(mes_ref-pd.DateOffset(months=12)).replace(day=1)
    COL_CARGO=next((c for c in df.columns if c.upper() in ("CARGO","FUNCAO","SENIORIDADE","NIVEL")),None)
    VALS={"GERENTE","DIRETOR","COORDENADOR","SUPERVISOR","HEAD","VP","C-LEVEL","LIDER","MANAGER"}
    def _lf(mes):
        sub=ativos[ativos["_D"]==mes]
        if COL_CARGO: sub=sub[sub[COL_CARGO].str.upper().str.strip().apply(lambda x:any(v in x for v in VALS))]
        t=len(sub); f=len(sub[sub["GENERO"].str.upper()=="FEMININO"]) if "GENERO" in sub.columns else 0
        return t,f,_pct(f,t)
    tl_a,ml_a,pct_a=_lf(mes_ref); tl_b,ml_b,pct_b=_lf(mes_ant12)
    delta=pct_a-pct_b; cor="#2ecc71" if delta>=0 else "#e74c3c"; sinal="▲" if delta>=0 else "▼"
    html=f'<div style="font-family:Poppins,sans-serif;padding:4px 0 12px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:14px"><div style="width:4px;height:22px;background:#F2214B;border-radius:2px"></div><span style="font-size:13px;font-weight:700;letter-spacing:.5px;color:#111;text-transform:uppercase">Mulheres em Liderança (YoY)</span></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px"><div style="background:#fafafa;border-radius:10px;padding:16px;text-align:center"><div style="font-size:10px;font-weight:700;color:#bbb;text-transform:uppercase;margin-bottom:8px">{mes_ant12.strftime("%b/%y").upper()}</div><div style="font-size:32px;font-weight:800;color:#666">{pct_b:.1f}%</div><div style="font-size:11px;color:#aaa;margin-top:4px">{ml_b} de {tl_b} líderes</div></div><div style="background:#111;border-radius:10px;padding:16px;text-align:center"><div style="font-size:10px;font-weight:700;color:#888;text-transform:uppercase;margin-bottom:8px">{mes_ref.strftime("%b/%y").upper()}</div><div style="font-size:32px;font-weight:800;color:#F2214B">{pct_a:.1f}%</div><div style="font-size:11px;color:#aaa;margin-top:4px">{ml_a} de {tl_a} líderes</div></div></div><div style="background:#f0f0f0;border-radius:8px;padding:10px 14px;font-size:12px;text-align:center">YoY: <span style="color:{cor};font-weight:700">{sinal} {abs(delta):.1f}pp</span></div></div>'
    return ("__HTML__",html,280), None

def analise_pretos_lideranca_yoy(df):
    df=_prep(df); ativos=df[df["STATUS_TIPO"]=="ATIVO"]; mes_ref=ativos["_D"].max(); mes_ant12=(mes_ref-pd.DateOffset(months=12)).replace(day=1)
    COL_CARGO=next((c for c in df.columns if c.upper() in ("CARGO","FUNCAO","SENIORIDADE","NIVEL")),None)
    VALS={"GERENTE","DIRETOR","COORDENADOR","SUPERVISOR","HEAD","VP","C-LEVEL","LIDER","MANAGER"}
    def _lp(mes):
        sub=ativos[ativos["_D"]==mes]
        if COL_CARGO: sub=sub[sub[COL_CARGO].str.upper().str.strip().apply(lambda x:any(v in x for v in VALS))]
        t=len(sub); p=len(sub[sub["ETNIA"].str.upper()=="PRETO"]) if "ETNIA" in sub.columns else 0
        return t,p,_pct(p,t)
    tl_a,pr_a,pct_a=_lp(mes_ref); tl_b,pr_b,pct_b=_lp(mes_ant12)
    delta=pct_a-pct_b; cor="#2ecc71" if delta>=0 else "#e74c3c"; sinal="▲" if delta>=0 else "▼"
    html=f'<div style="font-family:Poppins,sans-serif;padding:4px 0 12px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:14px"><div style="width:4px;height:22px;background:#F2214B;border-radius:2px"></div><span style="font-size:13px;font-weight:700;letter-spacing:.5px;color:#111;text-transform:uppercase">Pretos em Liderança (YoY)</span></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px"><div style="background:#fafafa;border-radius:10px;padding:16px;text-align:center"><div style="font-size:10px;font-weight:700;color:#bbb;text-transform:uppercase;margin-bottom:8px">{mes_ant12.strftime("%b/%y").upper()}</div><div style="font-size:32px;font-weight:800;color:#666">{pct_b:.1f}%</div><div style="font-size:11px;color:#aaa;margin-top:4px">{pr_b} de {tl_b} líderes</div></div><div style="background:#111;border-radius:10px;padding:16px;text-align:center"><div style="font-size:10px;font-weight:700;color:#888;text-transform:uppercase;margin-bottom:8px">{mes_ref.strftime("%b/%y").upper()}</div><div style="font-size:32px;font-weight:800;color:#F2214B">{pct_a:.1f}%</div><div style="font-size:11px;color:#aaa;margin-top:4px">{pr_a} de {tl_a} líderes</div></div></div><div style="background:#f0f0f0;border-radius:8px;padding:10px 14px;font-size:12px;text-align:center">YoY: <span style="color:{cor};font-weight:700">{sinal} {abs(delta):.1f}pp</span></div></div>'
    return ("__HTML__",html,280), None

def analise_internal_movement(df_hc, df_rs=None, mes_sel=None):
    FONTES_POI={"POI","POI - EFETIVAÇÃO","POI - CLTZAÇÃO","POI - EFETIVACAO","POI - CLTZACAO","POI - CLTIZAÇÃO","POI - CLTIZACAO"}
    df_hc=_prep(df_hc); ativos=df_hc[df_hc["STATUS_TIPO"]=="ATIVO"]
    _max_hc=ativos["_D"].max().replace(day=1) if not ativos.empty else pd.Timestamp.today().replace(day=1)
    mes_vigente=(mes_sel if mes_sel is not None else _max_hc).replace(day=1)
    mes_yoy=(mes_vigente-pd.DateOffset(years=1)).replace(day=1)
    def _hc(mes): return len(df_hc[(df_hc["_D"]==mes)&(df_hc["STATUS_TIPO"]=="ATIVO")])
    if df_rs is None or df_rs.empty:
        html=f'<div style="font-family:Poppins,sans-serif;padding:16px"><div style="background:#fff8f0;border:1px solid #f5c842;border-radius:8px;padding:14px;font-size:12px;color:#7a5c00">⚠️ <b>RS_Consolidado.parquet</b> não encontrado. Execute o <b>RS_ETL.py</b>.</div><div style="margin-top:12px;background:#fafafa;border-radius:8px;padding:10px 14px"><div style="font-size:10px;font-weight:700;color:#888;text-transform:uppercase;margin-bottom:6px">HC Vigente</div><div style="font-size:28px;font-weight:800;color:#111">{_hc(mes_vigente):,}</div></div></div>'
        return ("__HTML__",html,200), None
    df_rs=df_rs.copy()
    col_alin=next((c for c in df_rs.columns if "alinhamento" in c.lower()),None)
    col_fech=next((c for c in df_rs.columns if "fechamento" in c.lower() and "indicador" in c.lower()),None) or next((c for c in df_rs.columns if "fechamento" in c.lower()),None)
    if col_alin:
        _r=pd.to_datetime(df_rs[col_alin],dayfirst=True,errors="coerce")
        if _r.dt.tz is not None: _r=_r.dt.tz_localize(None)
        df_rs["_ALIN_ANO"]=_r.dt.year; df_rs["_ALIN_MES"]=_r.dt.month
    else: df_rs["_ALIN_ANO"]=pd.NA; df_rs["_ALIN_MES"]=pd.NA
    if col_fech:
        _r=pd.to_datetime(df_rs[col_fech],dayfirst=True,errors="coerce")
        if _r.dt.tz is not None: _r=_r.dt.tz_localize(None)
        df_rs["_FECH_ANO"]=_r.dt.year; df_rs["_FECH_MES"]=_r.dt.month
    else: df_rs["_FECH_ANO"]=pd.NA; df_rs["_FECH_MES"]=pd.NA
    df_rs["_FONTE_UP"]=df_rs.get("Fonte",pd.Series([""])).fillna("").astype(str).str.upper().str.strip() if "Fonte" in df_rs.columns else ""
    def _stats(mes_ts):
        a,m=mes_ts.year,mes_ts.month
        vagas=int(((df_rs["_ALIN_ANO"]==a)&(df_rs["_ALIN_MES"]==m)).sum())
        poi=int(((df_rs["_FECH_ANO"]==a)&(df_rs["_FECH_MES"]==m)&(df_rs["_FONTE_UP"].isin(FONTES_POI))).sum())
        return {"hc":_hc(mes_ts),"vagas":vagas,"mov":poi,"pct":_pct(poi,vagas)}
    cur=_stats(mes_vigente); ant=_stats(mes_yoy)
    def _vc(a,b):
        if b==0: return '<span style="color:#aaa">—</span>'
        d=(a-b)/b*100; c="#2ecc71" if d>=0 else "#e74c3c"; s="▲" if d>=0 else "▼"
        return f'<span style="color:{c};font-weight:600">{s} {abs(d):.1f}%</span>'
    nm_c=mes_vigente.strftime("%b/%y").upper(); nm_y=mes_yoy.strftime("%b/%y").upper()
    linhas_html=""
    for label,vc,va in [("HC – Mês Vigente",cur["hc"],ant["hc"]),("Vagas Abertas",cur["vagas"],ant["vagas"]),("Internal Movement (POI)",cur["mov"],ant["mov"])]:
        linhas_html+=f'<div style="display:grid;grid-template-columns:2fr 1fr 1fr;gap:6px;margin-bottom:6px"><div style="font-size:12px;color:#444;padding:8px 10px;background:#fafafa;border-radius:6px">{label}</div><div style="font-size:13px;font-weight:600;color:#666;padding:8px;text-align:center;background:#fafafa;border-radius:6px">{va:,}</div><div style="font-size:13px;font-weight:700;color:#111;padding:8px;text-align:center;background:#fff;border:1px solid #eee;border-radius:6px">{vc:,}</div></div>'
    html=f'<div style="font-family:Poppins,sans-serif;padding:4px 0 16px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:14px"><div style="width:3px;height:18px;background:#F2214B;border-radius:2px"></div><span style="font-size:11px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">Internal Movement — {nm_c}</span><span style="font-size:9px;color:#aaa;margin-left:4px">vs {nm_y} (YoY)</span></div><div style="display:grid;grid-template-columns:2fr 1fr 1fr;gap:6px;margin-bottom:8px"><div style="font-size:9px;font-weight:700;color:#bbb;text-transform:uppercase;padding:4px 10px">Métrica</div><div style="font-size:9px;font-weight:700;color:#bbb;text-transform:uppercase;padding:4px;text-align:center">{nm_y}</div><div style="font-size:9px;font-weight:700;color:#111;text-transform:uppercase;padding:4px;text-align:center;background:#f5f5f5;border-radius:4px">{nm_c}</div></div>{linhas_html}<div style="display:grid;grid-template-columns:2fr 1fr 1fr;gap:6px;margin-top:4px;margin-bottom:14px"><div style="font-size:11px;font-weight:700;color:#fff;padding:10px 12px;background:#111;border-radius:6px">INTERNAL MOVEMENT %</div><div style="font-size:14px;font-weight:700;color:#fff;padding:10px;text-align:center;background:#333;border-radius:6px">{ant["pct"]:.0f}%</div><div style="font-size:18px;font-weight:800;color:#F2214B;padding:10px;text-align:center;background:#111;border-radius:6px">{cur["pct"]:.0f}%</div></div><div style="background:#f5f5f5;border-radius:6px;padding:10px 14px;font-size:11px;color:#555;line-height:1.9">Vagas: {_vc(cur["vagas"],ant["vagas"])} &nbsp;|&nbsp; POIs: {_vc(cur["mov"],ant["mov"])} &nbsp;|&nbsp; IM%: {_vc(cur["pct"],ant["pct"])}</div></div>'
    return ("__HTML__",html,400), None

# ══════════════════════════════════════════════════════════════
#  FUNÇÕES R&S (completas)
# ══════════════════════════════════════════════════════════════

def _rs_mes_vigente(df_rs):
    COL=("Data de Fechamento (Indicador Stop)")
    if COL not in df_rs.columns: return pd.Timestamp.today().replace(day=1)
    raw=pd.to_datetime(df_rs[COL],errors="coerce")
    if raw.dt.tz is not None: raw=raw.dt.tz_localize(None)
    mx=raw.max(); return mx.replace(day=1) if pd.notna(mx) else pd.Timestamp.today().replace(day=1)

def _rs_vagas_fechadas(df_rs,ano,mes):
    COL="Data de Fechamento (Indicador Stop)"
    if COL not in df_rs.columns: return df_rs.iloc[0:0]
    raw=pd.to_datetime(df_rs[COL],errors="coerce")
    if raw.dt.tz is not None: raw=raw.dt.tz_localize(None)
    return df_rs[(raw.dt.year==ano)&(raw.dt.month==mes)]

def _var_str(a,b):
    if b==0: return '<span style="color:#aaa">—</span>'
    v=round((a-b)/b*100,1); c="#2ecc71" if v>=0 else "#e74c3c"; s="▲" if v>=0 else "▼"
    return f'<span style="color:{c};font-weight:700">{s} {abs(v):.1f}%</span>'

def analise_rs_vagas_fechadas(df_rs,mes_sel=None):
    if df_rs is None or df_rs.empty: return ("__HTML__","<div style='padding:16px;color:#888'>⚠️ RS não carregado.</div>",80),None
    df_rs=_rs_prep(df_rs); mv=mes_sel if mes_sel is not None else _rs_mes_vigente(df_rs)
    ano,mes=mv.year,mv.month; mv_ant=(mv-pd.DateOffset(months=1)).replace(day=1); mv_yoy=(mv-pd.DateOffset(years=1)).replace(day=1)
    cur=len(_rs_vagas_fechadas(df_rs,ano,mes)); ant=len(_rs_vagas_fechadas(df_rs,mv_ant.year,mv_ant.month)); yoy=len(_rs_vagas_fechadas(df_rs,mv_yoy.year,mv_yoy.month))
    nm_c=mv.strftime("%b/%y").upper(); nm_a=mv_ant.strftime("%b/%y").upper(); nm_y=mv_yoy.strftime("%b/%y").upper()
    def _mc(df_sub,col):
        if col not in df_sub.columns: return None
        v=pd.to_numeric(df_sub[col],errors="coerce").dropna(); return round(v.mean(),1) if len(v)>0 else None
    def _mm(a,m,col): return _mc(_rs_vagas_fechadas(df_rs,a,m),col)
    tth_c=_mm(ano,mes,"Time to Hire (Indicador Stop)"); tth_a=_mm(mv_ant.year,mv_ant.month,"Time to Hire (Indicador Stop)"); tth_y=_mm(mv_yoy.year,mv_yoy.month,"Time to Hire (Indicador Stop)")
    ttf_c=_mm(ano,mes,"Time to Fill (O inicio)"); ttf_a=_mm(mv_ant.year,mv_ant.month,"Time to Fill (O inicio)"); ttf_y=_mm(mv_yoy.year,mv_yoy.month,"Time to Fill (O inicio)")
    ttd_c=_mm(ano,mes,"Tempo em Definição"); ttd_a=_mm(mv_ant.year,mv_ant.month,"Tempo em Definição"); ttd_y=_mm(mv_yoy.year,mv_yoy.month,"Tempo em Definição")
    def _card(titulo,valor,ant_v,yoy_v,nm_a2,nm_y2,sfx=" dias"):
        v_str=f"{valor:.0f}{sfx}" if valor is not None else "—"
        mom=_var_str(valor or 0,ant_v or 0) if ant_v is not None else '<span style="color:#aaa">—</span>'
        yoyr=_var_str(valor or 0,yoy_v or 0) if yoy_v is not None else '<span style="color:#aaa">—</span>'
        return f'<div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:14px 16px;flex:1;min-width:130px"><div style="font-size:9px;font-weight:700;letter-spacing:1px;color:#aaa;text-transform:uppercase;margin-bottom:6px">{titulo}</div><div style="font-size:30px;font-weight:800;color:#111;line-height:1;margin-bottom:10px">{v_str}</div><div style="border-top:1px solid #f0f0f0;padding-top:6px;display:flex;flex-direction:column;gap:3px"><div style="font-size:9px;color:#888">{mom} vs {nm_a2}</div><div style="font-size:9px;color:#888">{yoyr} vs {nm_y2}</div></div></div>'
    card_v=f'<div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:14px 16px;flex:1;min-width:160px"><div style="font-size:9px;font-weight:700;letter-spacing:1px;color:#aaa;text-transform:uppercase;margin-bottom:6px">Vagas Fechadas</div><div style="font-size:42px;font-weight:800;color:#C0003C;line-height:1;margin-bottom:10px">{cur}</div><div style="border-top:1px solid #f0f0f0;padding-top:6px;display:flex;flex-direction:column;gap:3px"><div style="font-size:9px;color:#888">{_var_str(cur,ant)} vs {nm_a} ({ant})</div><div style="font-size:9px;color:#888">{_var_str(cur,yoy)} vs {nm_y} ({yoy})</div></div></div>'
    html=f'<div style="font-family:Poppins,sans-serif;padding:4px 0 12px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:16px"><div style="width:3px;height:18px;background:#C0003C;border-radius:2px"></div><span style="font-size:11px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">R&amp;S — Visão Geral · {nm_c}</span></div><div style="display:flex;gap:8px;flex-wrap:wrap">{card_v}{_card("TTD",ttd_c,ttd_a,ttd_y,nm_a,nm_y)}{_card("TTH",tth_c,tth_a,tth_y,nm_a,nm_y)}{_card("TTF",ttf_c,ttf_a,ttf_y,nm_a,nm_y)}</div></div>'
    return ("__HTML__",html,220), None

def analise_rs_status_vagas(df_rs,mes_sel=None):
    if df_rs is None or df_rs.empty: return ("__HTML__","<div style='padding:16px;color:#888'>⚠️ RS não carregado.</div>",80),None
    df_rs=_rs_prep(df_rs); mv=(mes_sel if mes_sel is not None else _rs_mes_vigente(df_rs)).replace(day=1)
    mv_ant=(mv-pd.DateOffset(months=1)).replace(day=1); mv_yoy=(mv-pd.DateOffset(years=1)).replace(day=1)
    nm=mv.strftime("%b/%Y"); nm_ant=mv_ant.strftime("%b/%y").upper(); nm_yoy=mv_yoy.strftime("%b/%y").upper()
    def _mc(df_sub,col):
        if col not in df_sub.columns or len(df_sub)==0: return None
        v=pd.to_numeric(df_sub[col],errors="coerce").dropna(); return round(v.mean(),0) if len(v)>0 else None
    def _pct2(a,b): return round((a-b)/b*100,0) if b and b!=0 else 0
    def _seta_vf(v): return ("▲","#16a34a") if v>=0 else ("▼","#dc2626")
    def _seta_tth(v): return ("▼","#16a34a") if v<=0 else ("▲","#dc2626")
    vf_c=len(_rs_vagas_fechadas(df_rs,mv.year,mv.month)); vf_a=len(_rs_vagas_fechadas(df_rs,mv_ant.year,mv_ant.month)); vf_y=len(_rs_vagas_fechadas(df_rs,mv_yoy.year,mv_yoy.month))
    vf_mom=_pct2(vf_c,vf_a); vf_yoy_p=_pct2(vf_c,vf_y)
    s_vf_m,c_vf_m=_seta_vf(vf_mom); s_vf_y,c_vf_y=_seta_vf(vf_yoy_p)
    COL_ALIGN=next((c for c in df_rs.columns if "alinhamento" in c.lower()),None)
    def _va_mes(a,m):
        if not COL_ALIGN: return df_rs.iloc[0:0]
        raw=pd.to_datetime(df_rs[COL_ALIGN],errors="coerce")
        if raw.dt.tz is not None: raw=raw.dt.tz_localize(None)
        return df_rs[(raw.dt.year==a)&(raw.dt.month==m)]
    va_c=len(_va_mes(mv.year,mv.month)); va_a=len(_va_mes(mv_ant.year,mv_ant.month)); va_y=len(_va_mes(mv_yoy.year,mv_yoy.month))
    va_mom=_pct2(va_c,va_a); va_yoy_p=_pct2(va_c,va_y)
    df_fc=_rs_vagas_fechadas(df_rs,mv.year,mv.month); df_fa=_rs_vagas_fechadas(df_rs,mv_ant.year,mv_ant.month); df_fy=_rs_vagas_fechadas(df_rs,mv_yoy.year,mv_yoy.month)
    tth_c=_mc(df_fc,"Time to Hire (Indicador Stop)"); tth_a=_mc(df_fa,"Time to Hire (Indicador Stop)"); tth_y=_mc(df_fy,"Time to Hire (Indicador Stop)")
    ttf_c=_mc(df_fc,"Time to Fill (O inicio)"); ttf_a=_mc(df_fa,"Time to Fill (O inicio)"); ttf_y=_mc(df_fy,"Time to Fill (O inicio)")
    tth_mp=_pct2(tth_c,tth_a) if tth_c and tth_a else None; tth_yp=_pct2(tth_c,tth_y) if tth_c and tth_y else None
    ttf_mp=_pct2(ttf_c,ttf_a) if ttf_c and ttf_a else None; ttf_yp=_pct2(ttf_c,ttf_y) if ttf_c and ttf_y else None
    def _card4(titulo,valor_str,mom_v,mom_p,yoy_v,yoy_p,seta_fn,big_cor="#111"):
        def _row(label,v,p,fn):
            if v is None or p is None: return ""
            s,c=fn(p)
            return f'<div style="display:flex;justify-content:space-between;padding:4px 0;border-top:1px solid #f5f5f5"><span style="font-size:10px;color:#aaa">vs. {label}</span><span style="font-size:11px;font-weight:700;color:{c}">{s} {abs(int(p))}% ({v})</span></div>'
        return f'<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px 18px;flex:1;min-width:180px"><div style="font-size:9px;font-weight:700;color:#9ca3af;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:8px">{titulo}</div><div style="font-size:38px;font-weight:800;color:{big_cor};line-height:1;margin-bottom:10px">{valor_str}</div>{_row("Mês",mom_v,mom_p,seta_fn)}{_row("Ano",yoy_v,yoy_p,seta_fn)}</div>'
    cards_fech=(_card4("Vagas Fechadas",str(vf_c),f"{vf_a}",vf_mom,f"{vf_y}",vf_yoy_p,_seta_vf,"#C0003C")
               +_card4("TTH",f"{int(tth_c)} dias" if tth_c else "—",f"{int(tth_a)} dias" if tth_a else None,tth_mp,f"{int(tth_y)} dias" if tth_y else None,tth_yp,_seta_tth)
               +_card4("TTF",f"{int(ttf_c)} dias" if ttf_c else "—",f"{int(ttf_a)} dias" if ttf_a else None,ttf_mp,f"{int(ttf_y)} dias" if ttf_y else None,ttf_yp,_seta_tth))
    tth_va=_mc(_va_mes(mv.year,mv.month),"Time to Hire (Indicador Stop)"); ttf_va=_mc(_va_mes(mv.year,mv.month),"Time to Fill (O inicio)")
    cards_aber=(_card4("Vagas Abertas",str(va_c),f"{va_a}",va_mom,f"{va_y}",va_yoy_p,_seta_vf)
               +_card4("TTH Médio",f"{int(tth_va)} dias" if tth_va else "—",None,None,None,None,_seta_tth)
               +_card4("TTF Médio",f"{int(ttf_va)} dias" if ttf_va else "—",None,None,None,None,_seta_tth))
    html=f'<div style="font-family:Poppins,sans-serif;padding:4px 0 8px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:14px"><div style="width:3px;height:18px;background:#C0003C;border-radius:2px"></div><span style="font-size:11px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">R&amp;S — Visão Estratégica · {nm}</span></div><div style="background:#fff8f8;border:1px solid #fecdd3;border-radius:10px;padding:14px 16px;margin-bottom:12px"><div style="font-size:9px;font-weight:700;color:#9ca3af;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:10px">VAGAS FECHADAS</div><div style="display:flex;gap:10px;flex-wrap:wrap">{cards_fech}</div></div><div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:14px 16px"><div style="font-size:9px;font-weight:700;color:#9ca3af;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:10px">VAGAS ABERTAS</div><div style="display:flex;gap:10px;flex-wrap:wrap">{cards_aber}</div></div></div>'
    return ("__HTML__",html,640), None

def analise_rs_vagas_consolidadas(df_rs,mes_sel=None):
    if df_rs is None or df_rs.empty: return "⚠️ RS não carregado.", None
    df_rs=_rs_prep(df_rs)
    COL="Data de Fechamento (Indicador Stop)"
    if COL not in df_rs.columns: return "⚠️ Coluna de fechamento não encontrada.", None
    raw=pd.to_datetime(df_rs[COL],errors="coerce")
    if raw.dt.tz is not None: raw=raw.dt.tz_localize(None)
    df_rs=df_rs.copy(); df_rs["_ANO"]=raw.dt.year; df_rs["_MES"]=raw.dt.month; df_rs=df_rs.dropna(subset=["_ANO"])
    periodos=(df_rs[["_ANO","_MES"]].drop_duplicates().sort_values(["_ANO","_MES"],ascending=[False,False]))
    MESES_PT={1:"JANEIRO",2:"FEVEREIRO",3:"MARÇO",4:"ABRIL",5:"MAIO",6:"JUNHO",7:"JULHO",8:"AGOSTO",9:"SETEMBRO",10:"OUTUBRO",11:"NOVEMBRO",12:"DEZEMBRO"}
    def _fy(ano,mes): return f"FY{str(ano+1 if mes>=7 else ano)[-2:]}"
    def _mc(df_sub,col):
        if col not in df_sub.columns or len(df_sub)==0: return "—"
        v=pd.to_numeric(df_sub[col],errors="coerce").dropna(); return str(int(round(v.mean(),0))) if len(v)>0 else "—"
    rows=""
    for _,row in periodos.iterrows():
        a,m=int(row["_ANO"]),int(row["_MES"]); df_m=df_rs[(df_rs["_ANO"]==a)&(df_rs["_MES"]==m)]
        rows+=f'<tr style="border-bottom:1px solid #f3f4f6"><td style="padding:9px 14px;font-size:11px;font-weight:700;color:#C0003C">{_fy(a,m)}</td><td style="padding:9px 14px;font-size:11px;color:#374151">{MESES_PT.get(m,str(m))}</td><td style="padding:9px 14px;font-size:12px;font-weight:700;color:#111;text-align:center">{len(df_m)}</td><td style="padding:9px 14px;font-size:11px;color:#6b7280;text-align:center">{_mc(df_m,"Tempo em Definição")}</td><td style="padding:9px 14px;font-size:11px;color:#6b7280;text-align:center">{_mc(df_m,"Time to Hire (Indicador Stop)")}</td><td style="padding:9px 14px;font-size:11px;color:#6b7280;text-align:center">{_mc(df_m,"Time to Fill (O inicio)")}</td></tr>'
    html=f'<div style="font-family:Poppins,sans-serif;padding:4px 0 8px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:14px"><div style="width:3px;height:18px;background:#C0003C;border-radius:2px"></div><span style="font-size:11px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">Vagas Fechadas — Consolidado Histórico</span></div><div style="border:1px solid #e5e7eb;border-radius:12px;overflow:hidden"><table style="width:100%;border-collapse:collapse"><thead><tr style="background:#C0003C"><th style="padding:10px 14px;text-align:left;font-size:10px;font-weight:700;color:white;letter-spacing:1px;text-transform:uppercase">FY</th><th style="padding:10px 14px;text-align:left;font-size:10px;font-weight:700;color:white;letter-spacing:1px;text-transform:uppercase">Mês</th><th style="padding:10px 14px;text-align:center;font-size:10px;font-weight:700;color:white;letter-spacing:1px;text-transform:uppercase">Vagas</th><th style="padding:10px 14px;text-align:center;font-size:10px;font-weight:700;color:white;letter-spacing:1px;text-transform:uppercase">TTD</th><th style="padding:10px 14px;text-align:center;font-size:10px;font-weight:700;color:white;letter-spacing:1px;text-transform:uppercase">TTH</th><th style="padding:10px 14px;text-align:center;font-size:10px;font-weight:700;color:white;letter-spacing:1px;text-transform:uppercase">TTF</th></tr></thead><tbody>{rows}</tbody></table></div></div>'
    return ("__HTML__",html,max(300,80+len(periodos)*40)), None

def analise_rs_vagas_abertas(df_rs,mes_sel=None):
    import plotly.graph_objects as go; from plotly.subplots import make_subplots; import re as _re
    if df_rs is None or df_rs.empty: return "⚠️ RS não carregado.", None
    df_rs=_rs_prep(df_rs); mv=(mes_sel if mes_sel is not None else _rs_mes_vigente(df_rs)).replace(day=1)
    mv_ant=(mv-pd.DateOffset(months=1)).replace(day=1); mv_yoy=(mv-pd.DateOffset(years=1)).replace(day=1); nm=mv.strftime("%b/%Y").upper()
    BG="white"; FC="#1a1a1a"; GC="rgba(0,0,0,.06)"; BAR="#C0003C"
    def _mc2(df_sub,col):
        if col not in df_sub.columns or len(df_sub)==0: return None
        v=pd.to_numeric(df_sub[col],errors="coerce").dropna(); return round(v.mean(),1) if len(v)>0 else None
    def _p2(a,b): return round((a-b)/b*100,0) if b and b!=0 else 0
    def _seta2(v,inv=False): pos=v>=0; pos=(not pos) if inv else pos; return ("▲","#16a34a") if pos else ("▼","#dc2626")
    COL_ALIGN=next((c for c in df_rs.columns if "alinhamento" in c.lower()),None)
    def _va(a,m):
        if not COL_ALIGN: return df_rs.iloc[0:0]
        raw=pd.to_datetime(df_rs[COL_ALIGN],errors="coerce")
        if raw.dt.tz is not None: raw=raw.dt.tz_localize(None)
        return df_rs[(raw.dt.year==a)&(raw.dt.month==m)]
    df_cur=_va(mv.year,mv.month); df_ant=_va(mv_ant.year,mv_ant.month); df_yoy=_va(mv_yoy.year,mv_yoy.month)
    tot_c,tot_a,tot_y=len(df_cur),len(df_ant),len(df_yoy)
    tth_c=_mc2(df_cur,"Time to Hire (Indicador Stop)"); tth_a=_mc2(df_ant,"Time to Hire (Indicador Stop)"); tth_y=_mc2(df_yoy,"Time to Hire (Indicador Stop)")
    ttf_c=_mc2(df_cur,"Time to Fill (O inicio)"); ttf_a=_mc2(df_ant,"Time to Fill (O inicio)"); ttf_y=_mc2(df_yoy,"Time to Fill (O inicio)")
    nm_ant=mv_ant.strftime("%b/%y").upper(); nm_yoy=mv_yoy.strftime("%b/%y").upper()
    def _card2(titulo,val,ant,yoy,sfx=" dias",inv=False):
        v_str=f"{int(val)}{sfx}" if val is not None else "—"; cor_n="#C0003C" if sfx=="" else "#111"; rows=""
        if ant is not None and val is not None:
            p=_p2(val,ant); s,c=_seta2(p,inv); rows+=f'<div style="font-size:10px;color:#888">vs. Mês &nbsp;<span style="color:{c};font-weight:700">{s} {abs(int(p))}% ({int(ant)}{sfx})</span></div>'
        if yoy is not None and val is not None:
            p=_p2(val,yoy); s,c=_seta2(p,inv); rows+=f'<div style="font-size:10px;color:#888">vs. Ano &nbsp;<span style="color:{c};font-weight:700">{s} {abs(int(p))}% ({int(yoy)}{sfx})</span></div>'
        return f'<div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:14px 16px;flex:1;min-width:120px"><div style="font-size:9px;font-weight:700;color:#aaa;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px">{titulo}</div><div style="font-size:34px;font-weight:800;color:{cor_n};line-height:1;margin-bottom:8px">{v_str}</div><div style="border-top:1px solid #f0f0f0;padding-top:6px">{rows}</div></div>'
    cards=(_card2("Total Vagas Abertas",tot_c,tot_a,tot_y,sfx="")
          +_card2("TTH — Time to Hire",tth_c,tth_a,tth_y,inv=True)
          +_card2("TTF — Time to Fill",ttf_c,ttf_a,ttf_y,inv=True))
    figs=[]
    COL_DIR=next((c for c in ("Diretoria","DIRETORIA") if c in df_cur.columns),None)
    if COL_DIR and len(df_cur)>0:
        df_d=df_cur.groupby(COL_DIR).size().sort_values(ascending=False).head(10)
        f1=go.Figure(go.Bar(y=list(df_d.index),x=list(df_d.values),orientation="h",marker_color=BAR,
            text=[f" {v} " for v in df_d.values],textposition="inside",insidetextanchor="start",
            textfont=dict(size=12,color="white",family="Poppins"),width=0.6))
        f1.update_layout(title=dict(text=f"Vagas Abertas por Diretoria · {nm}",font=dict(size=13,color=FC,family="Poppins"),x=.5),
            paper_bgcolor=BG,plot_bgcolor=BG,font=dict(color=FC,family="Poppins"),
            xaxis=dict(showgrid=True,gridcolor=GC,color=FC,tickfont=dict(size=11)),
            yaxis=dict(showgrid=False,color=FC,tickfont=dict(size=11,family="Poppins"),autorange="reversed"),
            height=max(280,70+len(df_d)*40),margin=dict(l=200,r=30,t=55,b=40))
        figs.append(f1)
    COL_REC=next((c for c in df_cur.columns if "analista" in c.lower()),None)
    if COL_REC and len(df_cur)>0:
        df_r=df_cur.groupby(COL_REC).size().sort_values(ascending=False).head(8)
        f2=go.Figure(go.Bar(y=list(df_r.index),x=list(df_r.values),orientation="h",marker_color=BAR,
            text=[f" {v} " for v in df_r.values],textposition="inside",insidetextanchor="start",
            textfont=dict(size=12,color="white",family="Poppins"),width=0.6))
        f2.update_layout(title=dict(text="Por Recrutador",font=dict(size=13,color=FC,family="Poppins"),x=.5),
            paper_bgcolor=BG,plot_bgcolor=BG,font=dict(color=FC,family="Poppins"),
            xaxis=dict(showgrid=True,gridcolor=GC,tickfont=dict(size=11)),
            yaxis=dict(showgrid=False,tickfont=dict(size=12,family="Poppins"),autorange="reversed"),
            height=max(260,60+len(df_r)*44),margin=dict(l=120,r=30,t=55,b=30))
        figs.append(f2)
    header=f'<div style="font-family:Poppins,sans-serif;padding:4px 0 8px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:14px"><div style="width:3px;height:18px;background:#C0003C;border-radius:2px"></div><span style="font-size:12px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">Vagas Abertas · {nm}</span></div><div style="display:flex;gap:10px;flex-wrap:wrap">{cards}</div></div>'
    return ("__HTML__",header,185), figs

def analise_rs_vagas_fechadas_rich(df_rs,mes_sel=None):
    import plotly.graph_objects as go; from plotly.subplots import make_subplots
    if df_rs is None or df_rs.empty: return "⚠️ RS não carregado.", None
    df_rs=_rs_prep(df_rs); mv=(mes_sel if mes_sel is not None else _rs_mes_vigente(df_rs)).replace(day=1)
    mv_ant=(mv-pd.DateOffset(months=1)).replace(day=1); mv_yoy=(mv-pd.DateOffset(years=1)).replace(day=1); nm=mv.strftime("%b/%Y").upper()
    BG="white"; FC="#1a1a1a"; GC="rgba(0,0,0,.06)"; BAR="#C0003C"
    def _mc3(df_sub,col):
        if col not in df_sub.columns or len(df_sub)==0: return None
        v=pd.to_numeric(df_sub[col],errors="coerce").dropna(); return round(v.mean(),1) if len(v)>0 else None
    def _p3(a,b): return round((a-b)/b*100,0) if b and b!=0 else 0
    def _seta3(v,inv=False): pos=v>=0; pos=(not pos) if inv else pos; return ("▲","#16a34a") if pos else ("▼","#dc2626")
    df_cur=_rs_vagas_fechadas(df_rs,mv.year,mv.month); df_ant=_rs_vagas_fechadas(df_rs,mv_ant.year,mv_ant.month); df_yoy=_rs_vagas_fechadas(df_rs,mv_yoy.year,mv_yoy.month)
    tot_c,tot_a,tot_y=len(df_cur),len(df_ant),len(df_yoy)
    tth_c=_mc3(df_cur,"Time to Hire (Indicador Stop)"); tth_a=_mc3(df_ant,"Time to Hire (Indicador Stop)"); tth_y=_mc3(df_yoy,"Time to Hire (Indicador Stop)")
    ttf_c=_mc3(df_cur,"Time to Fill (O inicio)"); ttf_a=_mc3(df_ant,"Time to Fill (O inicio)"); ttf_y=_mc3(df_yoy,"Time to Fill (O inicio)")
    ttd_c=_mc3(df_cur,"Tempo em Definição"); ttd_a=_mc3(df_ant,"Tempo em Definição"); ttd_y=_mc3(df_yoy,"Tempo em Definição")
    def _card3(titulo,val,ant,yoy,sfx=" dias",inv=False,big=False):
        v_str=f"{int(val)}{sfx}" if val is not None else "—"; cor_n="#C0003C" if big else "#111"; rows=""
        if ant is not None and val is not None:
            p=_p3(val,ant); s,c=_seta3(p,inv); rows+=f'<div style="font-size:10px;color:#888">vs. Mês &nbsp;<span style="color:{c};font-weight:700">{s} {abs(int(p))}% ({int(ant)}{sfx})</span></div>'
        if yoy is not None and val is not None:
            p=_p3(val,yoy); s,c=_seta3(p,inv); rows+=f'<div style="font-size:10px;color:#888">vs. Ano &nbsp;<span style="color:{c};font-weight:700">{s} {abs(int(p))}% ({int(yoy)}{sfx})</span></div>'
        return f'<div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:14px 16px;flex:1;min-width:120px"><div style="font-size:9px;font-weight:700;color:#aaa;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px">{titulo}</div><div style="font-size:34px;font-weight:800;color:{cor_n};line-height:1;margin-bottom:8px">{v_str}</div><div style="border-top:1px solid #f0f0f0;padding-top:6px">{rows}</div></div>'
    cards=(_card3("Vagas Fechadas",tot_c,tot_a,tot_y,sfx="",big=True)
          +_card3("TTD",ttd_c,ttd_a,ttd_y,inv=True)+_card3("TTH",tth_c,tth_a,tth_y,inv=True)+_card3("TTF",ttf_c,ttf_a,ttf_y,inv=True))
    figs=[]
    COL_DIR=next((c for c in ("Diretoria","DIRETORIA") if c in df_cur.columns),None)
    if COL_DIR and len(df_cur)>0:
        df_d=df_cur.groupby(COL_DIR).size().sort_values(ascending=False).head(10)
        f1=go.Figure(go.Bar(y=list(df_d.index),x=list(df_d.values),orientation="h",marker_color=BAR,
            text=[f" {v} " for v in df_d.values],textposition="inside",insidetextanchor="start",
            textfont=dict(size=12,color="white",family="Poppins"),width=0.6))
        f1.update_layout(title=dict(text=f"Vagas Fechadas por Diretoria · {nm}",font=dict(size=13,color=FC,family="Poppins"),x=.5),
            paper_bgcolor=BG,plot_bgcolor=BG,font=dict(color=FC,family="Poppins"),
            xaxis=dict(showgrid=True,gridcolor=GC,tickfont=dict(size=11)),
            yaxis=dict(showgrid=False,tickfont=dict(size=11,family="Poppins"),autorange="reversed"),
            height=max(280,70+len(df_d)*40),margin=dict(l=200,r=30,t=55,b=40))
        figs.append(f1)
    COL_REC=next((c for c in df_cur.columns if "analista" in c.lower()),None)
    if COL_REC and len(df_cur)>0:
        df_r=df_cur.groupby(COL_REC).size().sort_values(ascending=False).head(8)
        f2=go.Figure(go.Bar(y=list(df_r.index),x=list(df_r.values),orientation="h",marker_color=BAR,
            text=[f" {v} " for v in df_r.values],textposition="inside",insidetextanchor="start",
            textfont=dict(size=12,color="white",family="Poppins"),width=0.6))
        f2.update_layout(title=dict(text="Por Recrutador",font=dict(size=13,color=FC,family="Poppins"),x=.5),
            paper_bgcolor=BG,plot_bgcolor=BG,font=dict(color=FC,family="Poppins"),
            xaxis=dict(showgrid=True,gridcolor=GC,tickfont=dict(size=11)),
            yaxis=dict(showgrid=False,tickfont=dict(size=12,family="Poppins"),autorange="reversed"),
            height=max(260,60+len(df_r)*44),margin=dict(l=120,r=30,t=55,b=30))
        figs.append(f2)
    header=f'<div style="font-family:Poppins,sans-serif;padding:4px 0 8px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:14px"><div style="width:3px;height:18px;background:#C0003C;border-radius:2px"></div><span style="font-size:12px;font-weight:700;letter-spacing:1px;color:#111;text-transform:uppercase">Vagas Fechadas · {nm}</span></div><div style="display:flex;gap:10px;flex-wrap:wrap">{cards}</div></div>'
    return ("__HTML__",header,200), figs

# ══════════════════════════════════════════════════════════════
#  DISPATCHER executar_analise + RENDER helpers
# ══════════════════════════════════════════════════════════════

def executar_analise(tipo, df, df_hp=None, df_rs=None):
    try:
        _gm = st.session_state.get("global_mes_ts")
        mapa = {
            "turnover_yoy":          lambda: analise_turnover_yoy(_df_mes_filtrado(df)),
            "hc_empresa":            lambda: analise_hc_empresa(_df_mes_filtrado(df)),
            "tipo_contrato":         lambda: analise_tipo_contrato(_df_mes_filtrado(df)),
            "top5_areas":            lambda: analise_top5_areas(_df_mes_filtrado(df)),
            "senioridade":           lambda: analise_senioridade(_df_mes_filtrado(df)),
            "inativos":              lambda: analise_inativos(_df_mes_filtrado(df)),
            "to_mensal":             lambda: analise_to_mensal(_df_mes_filtrado(df)),
            "to_grafico":            lambda: analise_to_grafico(_df_mes_filtrado(df)),
            "diversidade":           lambda: analise_diversidade(_df_mes_filtrado(df)),
            "tempo_casa_ativos":     lambda: analise_tempo_casa_ativos(_df_mes_filtrado(df)),
            "tempo_casa_inativos":   lambda: analise_tempo_casa_inativos(_df_mes_filtrado(df)),
            "regrettable":           lambda: analise_regrettable_turnover(_df_mes_filtrado(df), df_hp if df_hp is not None else pd.DataFrame()),
            "internal_movement":     lambda: analise_internal_movement(_df_mes_filtrado(df), df_rs, _gm),
            "mulheres_empresa":      lambda: analise_mulheres_empresa(_df_mes_filtrado(df)),
            "diversidade_detalhada": lambda: analise_diversidade_detalhada(_df_mes_filtrado(df)),
            "mulheres_lideranca":    lambda: analise_mulheres_lideranca_yoy(_df_mes_filtrado(df)),
            "pretos_lideranca":      lambda: analise_pretos_lideranca_yoy(_df_mes_filtrado(df)),
            "rs_vagas_abertas":       lambda: analise_rs_vagas_abertas(df_rs, _gm),
            "rs_vagas_fechadas_rich": lambda: analise_rs_vagas_fechadas_rich(df_rs, _gm),
            "rs_vagas_fechadas":     lambda: analise_rs_vagas_fechadas(df_rs, _gm),
            "rs_status_vagas":       lambda: analise_rs_status_vagas(df_rs, _gm),
            "rs_vagas_consolidadas": lambda: analise_rs_vagas_consolidadas(df_rs),
        }
        if tipo in mapa:
            return mapa[tipo]()
    except Exception as e:
        return f"❌ **Erro:** `{str(e)[:300]}`", None

def _render_resultado(resultado, fig=None):
    if isinstance(resultado, tuple) and resultado[0] == "__HTML__":
        _, html_content, height = resultado
        render_html_chat(html_content, height=height)
        msg = {"tipo": "html", "content": html_content, "height": height}
    else:
        st.markdown(resultado)
        msg = {"tipo": "markdown", "content": resultado}
    if fig is not None:
        figs_list = fig if isinstance(fig, list) else [fig]
        for f in figs_list:
            if f is not None:
                st.plotly_chart(f, use_container_width=True)
    return msg

def _replay_msg(msg):
    if msg.get("tipo") == "html_plotly":
        render_html_chat(msg["content"], height=msg.get("height", 200))
        import plotly.io as pio
        for fj in msg.get("figs_json", []):
            try: st.plotly_chart(pio.from_json(fj), use_container_width=True)
            except: pass
    elif msg.get("tipo") == "html":
        render_html_chat(msg["content"], height=msg.get("height", 420))
    elif msg.get("tipo") == "plotly":
        import plotly.io as pio
        if msg.get("content"): st.markdown(msg["content"])
        for fj in msg.get("figs_json", []):
            try: st.plotly_chart(pio.from_json(fj), use_container_width=True)
            except: pass
    elif msg.get("content"):
        st.markdown(msg["content"])

# ══════════════════════════════════════════════════════════════
#  AGENTE GROQ — TOTALMENTE REESCRITO PARA DIRETORES
#  Arquitetura: Estágio 0 (pandas puro) → Estágio 1 (LLM com
#  contexto rico) → Estágio 2 (código gerado, template seguro)
#  → Estágio 3 (fallback direto com dados pré-calculados)
# ══════════════════════════════════════════════════════════════

def rodar_agente_livre(pergunta, historico, df, df_hp, contexto="", df_rs=None):
    """
    Agente de People Analytics para diretores.
    Respostas precisas, objetivas e baseadas 100% em dados reais.
    Zero alucinação — se não tiver o dado, diz que não tem.
    """
    api_key = GROQ_API_KEY
    if not api_key:
        return [("markdown", "⚠️ GROQ_API_KEY não configurada.")]

    # ── PRÉ-PROCESSAMENTO COMPLETO ─────────────────────────────
    df2 = df.copy()
    df2["_D"] = pd.to_datetime(df2["DATA"], dayfirst=True, errors="coerce")
    df2["STATUS_TIPO"] = df2["STATUS_TIPO"].fillna("").str.upper().str.strip()
    _gm = st.session_state.get("global_mes_ts")
    if _gm is not None:
        df2 = df2[df2["_D"] <= _gm]

    ativos_df   = df2[df2["STATUS_TIPO"] == "ATIVO"]
    inativos_df = df2[df2["STATUS_TIPO"] == "INATIVO"]
    mes_ref     = ativos_df["_D"].max()
    mes_ref_s   = mes_ref.strftime("%b/%Y").upper() if pd.notna(mes_ref) else "N/A"

    # ── Pré-calcula 12 meses ────────────────────────────────────
    _meses_12 = pd.date_range(
        start=(mes_ref - pd.DateOffset(months=11)).replace(day=1),
        end=mes_ref, freq="MS"
    )
    _ctx = []
    for _m in _meses_12:
        _at  = ativos_df[ativos_df["_D"] == _m]
        _in  = inativos_df[inativos_df["_D"] == _m]
        _hc  = len(_at)
        _inv = int(_in["INICIATIVA"].str.upper().str.contains("EMPRESA",   na=False).sum()) if "INICIATIVA" in _in.columns else 0
        _vol = int(_in["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False).sum()) if "INICIATIVA" in _in.columns else 0
        _ctx.append({"mes": _m, "label": _m.strftime("%b/%Y").upper(),
                     "hc": _hc, "inv": _inv, "vol": _vol,
                     "total_in": len(_in), "to_pct": round((_inv+_vol)/_hc*100,1) if _hc>0 else 0})

    _cur = _ctx[-1]  if _ctx               else {}
    _ant = _ctx[-2]  if len(_ctx) >= 2     else {}
    _yoy = _ctx[0]   if _ctx               else {}

    hc_total  = _cur.get("hc", 0)
    hc_ant    = _ant.get("hc", 0)
    hc_yoy    = _yoy.get("hc", 0)
    inat_mes  = _cur.get("total_in", 0)
    inv_mes   = _cur.get("inv", 0)
    vol_mes   = _cur.get("vol", 0)
    to_mes    = _cur.get("to_pct", 0)

    # ── Trimestres ─────────────────────────────────────────────
    _tc = _ctx[-3:] if len(_ctx) >= 3 else _ctx
    _ta = _ctx[-6:-3] if len(_ctx) >= 6 else []
    _mc_tc = [x["hc"] for x in _tc if x["hc"]>0]
    _mc_ta = [x["hc"] for x in _ta if x["hc"]>0]
    med_trim_cur = round(sum(_mc_tc)/len(_mc_tc),1) if _mc_tc else 0
    med_trim_ant = round(sum(_mc_ta)/len(_mc_ta),1) if _mc_ta else 0
    lbl_tc = f"{_tc[0]['label']} → {_tc[-1]['label']}" if len(_tc)>=2 else mes_ref_s
    lbl_ta = f"{_ta[0]['label']} → {_ta[-1]['label']}" if len(_ta)>=2 else "—"

    # ── Dados do mês vigente ────────────────────────────────────
    _df_cur = ativos_df[ativos_df["_D"] == mes_ref]
    hc_masc = int(_df_cur["GENERO"].str.upper().str.contains("MASCULINO",na=False).sum()) if "GENERO" in _df_cur.columns else 0
    hc_fem  = hc_total - hc_masc
    hc_pret = int((_df_cur["ETNIA"].str.upper()=="PRETO").sum())  if "ETNIA" in _df_cur.columns else 0
    hc_pardo= int((_df_cur["ETNIA"].str.upper()=="PARDO").sum())  if "ETNIA" in _df_cur.columns else 0
    hc_pcd  = int((_df_cur["PCD"].astype(str).str.upper()=="SIM").sum()) if "PCD" in _df_cur.columns else 0
    _emp_hc = _df_cur.groupby("EMPRESA").size().to_dict() if "EMPRESA" in _df_cur.columns else {}
    _emp_str = " | ".join(f"{e}={v}" for e,v in sorted(_emp_hc.items()))
    _emp_disp= sorted(df2["EMPRESA"].dropna().unique().tolist()) if "EMPRESA" in df2.columns else []
    _serie   = "\n".join(f"  {x['label']}: HC={x['hc']} | Des={x['total_in']}(inv={x['inv']},vol={x['vol']}) | TO%={x['to_pct']}%" for x in _ctx)

    # Senioridade
    _sen_str = ""
    if "SENIORIDADE" in _df_cur.columns:
        _sen = _df_cur.groupby("SENIORIDADE").size().sort_values(ascending=False)
        _sen_str = " | ".join(f"{s}={v}" for s,v in _sen.items())

    # Top áreas
    _area_str = ""
    if "AREA" in _df_cur.columns:
        _areas = _df_cur.groupby("AREA").size().sort_values(ascending=False).head(5)
        _area_str = " | ".join(f"{a}={v}" for a,v in _areas.items())

    # Tipo contratação
    _tipo_str = ""
    if "TIPO CONTRATACAO" in _df_cur.columns:
        _tipos = _df_cur.groupby("TIPO CONTRATACAO").size()
        _tipo_str = " | ".join(f"{t}={v}" for t,v in _tipos.items())

    # ── Contexto R&S ────────────────────────────────────────────
    rs_ctx = ""
    _rs_resumo = {}  # mês → dict com dados RS (para uso no Estágio 0)
    if df_rs is not None and not df_rs.empty:
        try:
            _dfr = _rs_prep(df_rs.copy())
            COL_F = "Data de Fechamento (Indicador Stop)"
            COL_A = "Data do Alinhamento\n(Indicador Stop)"
            _fr = pd.to_datetime(_dfr.get(COL_F, pd.Series()), errors="coerce")
            if hasattr(_fr.dt,"tz") and _fr.dt.tz is not None: _fr = _fr.dt_localize(None)
            _ar = pd.to_datetime(_dfr.get(COL_A, pd.Series()), errors="coerce")
            if hasattr(_ar.dt,"tz") and _ar.dt.tz is not None: _ar = _ar.dt_localize(None)
            def _rn(a,m): mask=(_fr.dt.year==a)&(_fr.dt.month==m); return int(mask.sum()),_dfr[mask.values]
            def _rm(df_sub,col):
                v=pd.to_numeric(df_sub.get(col,pd.Series()),errors="coerce").dropna()
                return round(v.mean(),1) if len(v)>0 else None
            def _pv(c,a):
                if a and a!=0: p=round((c-a)/a*100,0); s="▲" if p>=0 else "▼"; return f"{s}{abs(int(p))}%"
                return "—"
            linhas=[]
            for _d in range(0,13):
                _mv=(mes_ref-pd.DateOffset(months=_d)).replace(day=1)
                _mv_m=(_mv-pd.DateOffset(months=1)).replace(day=1)
                _mv_y=(_mv-pd.DateOffset(years=1)).replace(day=1)
                _n,_dfm=_rn(_mv.year,_mv.month)
                if _n==0: continue
                _nm,_=_rn(_mv_m.year,_mv_m.month); _ny,_=_rn(_mv_y.year,_mv_y.month)
                _tth=_rm(_dfm,"Time to Hire (Indicador Stop)"); _ttf=_rm(_dfm,"Time to Fill (O inicio)"); _ttd=_rm(_dfm,"Tempo em Definição")
                _lbl=_mv.strftime("%b/%Y").upper()
                _rs_resumo[_lbl]={"n":_n,"tth":_tth,"ttf":_ttf,"ttd":_ttd,"n_m":_nm,"n_y":_ny}
                linhas.append(f"  {_lbl}: fechadas={_n}(MoM:{_pv(_n,_nm)}/{_nm};YoY:{_pv(_n,_ny)}/{_ny}) | TTD:{_ttd or '—'} TTH:{_tth or '—'} TTF:{_ttf or '—'} dias")
                _na=int(((_ar.dt.year==_mv.year)&(_ar.dt.month==_mv.month)).sum())
                if _na>0:
                    _nam=int(((_ar.dt.year==_mv_m.year)&(_ar.dt.month==_mv_m.month)).sum())
                    _nay=int(((_ar.dt.year==_mv_y.year)&(_ar.dt.month==_mv_y.month)).sum())
                    linhas.append(f"  {_lbl}: abertas={_na}(MoM:{_pv(_na,_nam)}/{_nam};YoY:{_pv(_na,_nay)}/{_nay})")
                if _d<3:
                    _cr=next((c for c in _dfm.columns if "analista" in c.lower()),None)
                    if _cr: linhas.append("    recrutadores: "+" | ".join(f"{r.strip()}={v}" for r,v in _dfm.groupby(_cr).size().sort_values(ascending=False).items()))
                    if "Diretoria" in _dfm.columns: linhas.append("    diretorias: "+" | ".join(f"{d}={v}" for d,v in _dfm.groupby("Diretoria").size().sort_values(ascending=False).head(5).items()))
            rs_ctx = "\nDADOS R&S:\n"+"\n".join(linhas) if linhas else ""
        except Exception: rs_ctx = ""

    _perg_l = pergunta.lower().strip()

    # ══════════════════════════════════════════════════════════
    # ESTÁGIO 0 — PANDAS PURO (zero LLM, resposta imediata)
    # ══════════════════════════════════════════════════════════

    def _vs(a,b,sfx=""):
        if b==0: return ""
        v=round((a-b)/b*100,1); s="▲" if v>=0 else "▼"
        return f" | {s}**{abs(v)}%** MoM ({b}{sfx})"
    def _ys(a,b,sfx=""):
        if b==0: return ""
        v=round((a-b)/b*100,1); s="▲" if v>=0 else "▼"
        return f" | {s}**{abs(v)}%** YoY ({b}{sfx})"

    # ─ HC total / ativos
    _is_hc = re.search(r"(quantos|total|headcount|hc\b|colaboradores|ativos|funcionarios|pessoas|quadro)", _perg_l)
    _no_detail = not re.search(r"(inativo|deslig|turnover|trimestre|area|cargo|senior|empresa|genero|diversidade|rs\b|vaga)", _perg_l)
    if _is_hc and _no_detail:
        resp = f"**Headcount Ativo — {mes_ref_s}**\n\n**{hc_total:,}** colaboradores ativos{_vs(hc_total,hc_ant)}{_ys(hc_total,hc_yoy)}"
        if _emp_hc:
            resp += "\n\n| Empresa | HC |\n|---|---|\n"
            for e,v in sorted(_emp_hc.items(),key=lambda x:-x[1]):
                resp += f"| {e} | {v:,} |\n"
        return [("markdown", resp)]

    # ─ Inativos / desligamentos
    if re.search(r"(inativo|deslig|demit|rescind|demiss)", _perg_l) and not re.search(r"(trimestre|tempo de casa|turno)", _perg_l):
        resp = (f"**Desligamentos — {mes_ref_s}**\n\n"
                f"- **Total:** {inat_mes}{_vs(inat_mes,_ant.get('total_in',0))}\n"
                f"- **Involuntários:** {inv_mes}\n- **Voluntários:** {vol_mes}\n"
                f"- **TO% do mês:** {to_mes}%")
        return [("markdown", resp)]

    # ─ Trimestre
    if re.search(r"(trimestre|quarter|q[1-4])", _perg_l):
        det = "\n".join(f"  • {x['label']}: **{x['hc']:,}** ativos | {x['total_in']} deslig | TO: {x['to_pct']}%" for x in _tc)
        resp = (f"**Headcount no Trimestre — {lbl_tc}**\n\n"
                f"- **HC Médio:** {med_trim_cur:,}\n"
                f"- **Trimestre anterior ({lbl_ta}):** {med_trim_ant:,}\n\n"
                f"**Detalhe:**\n{det}")
        return [("markdown", resp)]

    # ─ Turnover tabela rápida
    if re.search(r"(turnover|rotatividade|to%)", _perg_l) and not re.search(r"(empresa|area|cargo|regret)", _perg_l):
        linhas = ["**TO% Mensal — Últimos 12 meses**\n","| Mês | HC | Inv | Vol | TO% |","|---|---|---|---|---|"]
        for x in _ctx:
            linhas.append(f"| {x['label']} | {x['hc']} | {x['inv']} | {x['vol']} | {x['to_pct']}% |")
        return [("markdown", "\n".join(linhas))]

    # ─ Gênero / diversidade
    if re.search(r"(mulher|feminino|masculino|genero|gênero|diversidade|pcd|preto|pardo|negro)", _perg_l):
        resp = (f"**Diversidade — {mes_ref_s}**\n\n"
                f"- **Feminino:** {hc_fem:,} ({round(hc_fem/hc_total*100,1) if hc_total else 0}%)\n"
                f"- **Masculino:** {hc_masc:,} ({round(hc_masc/hc_total*100,1) if hc_total else 0}%)\n"
                f"- **Pretos:** {hc_pret:,} | **Pardos:** {hc_pardo:,} | **PCD:** {hc_pcd:,}")
        return [("markdown", resp)]

    # ─ HC por empresa
    if re.search(r"(empresa|car10|loop|revenda|syonet|webmotors)", _perg_l) and re.search(r"(headcount|hc\b|colaboradores|ativos|quantos)", _perg_l):
        linhas = [f"**Headcount por Empresa — {mes_ref_s}**\n","| Empresa | HC |\n|---|---|"]
        for e,v in sorted(_emp_hc.items(),key=lambda x:-x[1]):
            linhas.append(f"| {e} | {v:,} |")
        linhas.append(f"| **TOTAL** | **{hc_total:,}** |")
        return [("markdown", "\n".join(linhas))]

    # ─ Senioridade
    if re.search(r"(senior|seniori|nivel|pleno|junior|s[eê]nior)", _perg_l) and _sen_str:
        return [("markdown", f"**Headcount por Senioridade — {mes_ref_s}**\n\n{_sen_str}")]

    # ─ Top áreas
    if re.search(r"(area|áreas|top.*(5|cinco)|maiores.*(equipe|time|area))", _perg_l) and _area_str:
        return [("markdown", f"**Top Áreas — {mes_ref_s}**\n\n{_area_str}")]

    # ─ Tipo contratação
    if re.search(r"(clt|pj\b|estagi|contrat)", _perg_l) and _tipo_str:
        return [("markdown", f"**Tipo de Contratação — {mes_ref_s}**\n\n{_tipo_str}")]

    # ─ R&S básico (mês vigente)
    if re.search(r"(vagas?\s+fechadas?|recrutamento|rs\b|r&s)", _perg_l):
        _lbl_cur = mes_ref_s
        if _lbl_cur in _rs_resumo:
            _d = _rs_resumo[_lbl_cur]
            resp = (f"**Vagas Fechadas — {_lbl_cur}**\n\n"
                    f"**{_d['n']}** vagas fechadas{_vs(_d['n'],_d['n_m'],'')}{_ys(_d['n'],_d['n_y'],'')}\n"
                    f"- TTD: {_d['ttd'] or '—'} dias | TTH: {_d['tth'] or '—'} dias | TTF: {_d['ttf'] or '—'} dias")
            return [("markdown", resp)]

    # ══════════════════════════════════════════════════════════
    # ESTÁGIO 1 — LLM com contexto ultra-rico
    # ══════════════════════════════════════════════════════════

    client = Groq(api_key=api_key)

    _ctx_completo = f"""
=== DADOS PEOPLE ANALYTICS — WEBMOTORS ===
MÊS VIGENTE: {mes_ref_s}
HEADCOUNT ATIVO: {hc_total:,}  (ant={hc_ant:,}; yoy={hc_yoy:,})
INATIVOS MÊS: total={inat_mes} (inv={inv_mes}, vol={vol_mes}), TO%={to_mes}%
GÊNERO: Masc={hc_masc} ({round(hc_masc/hc_total*100,1) if hc_total else 0}%) | Fem={hc_fem} ({round(hc_fem/hc_total*100,1) if hc_total else 0}%)
DIVERSIDADE: Pretos={hc_pret} | Pardos={hc_pardo} | PCD={hc_pcd}
EMPRESAS: {_emp_str}
SENIORIDADE: {_sen_str or 'N/A'}
TOP ÁREAS: {_area_str or 'N/A'}
TIPO CONTRATAÇÃO: {_tipo_str or 'N/A'}
TRIMESTRE ATUAL ({lbl_tc}): HC médio={med_trim_cur:,}
TRIMESTRE ANTERIOR ({lbl_ta}): HC médio={med_trim_ant:,}

SÉRIE 12 MESES:
{_serie}{rs_ctx}
""".strip()

    _system_prompt = """Você é o Agente de People Analytics da Webmotors, assistindo diretores com dados precisos e objetivos.

REGRAS ABSOLUTAS:
1. Use SOMENTE dados do CONTEXTO fornecido. NUNCA estime, invente ou interpole.
2. Se o dado pedido não está no contexto → responda: PRECISA_CODIGO
3. Resposta em português, direta, máx 8 linhas, sem introduções desnecessárias.
4. Para números: sempre inclua variação MoM e YoY quando disponíveis.
5. Use ▲ para aumento, ▼ para redução.
6. Tom executivo: números primeiro, depois contexto.
7. Se a pergunta for sobre um mês/período específico não listado → PRECISA_CODIGO
8. NUNCA responda com estimativas ou "aproximadamente"."""

    _user_prompt = f"""CONTEXTO:
{_ctx_completo}

PERGUNTA DO DIRETOR: "{pergunta}"

Responda diretamente com os dados do contexto OU com PRECISA_CODIGO se necessitar de cálculo específico não disponível acima."""

    try:
        r1 = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": _system_prompt},
                {"role": "user",   "content": _user_prompt},
            ],
            temperature=0.0,
            max_tokens=600,
        )
        resp1 = r1.choices[0].message.content.strip()

        if "PRECISA_CODIGO" not in resp1 and len(resp1) > 10:
            # Valida coerência para perguntas de HC
            if re.search(r"(headcount|hc\b|colaboradores|ativos)", _perg_l) and hc_total > 50:
                _nums = [int(n) for n in re.findall(r'\b(\d+)\b', resp1)]
                if _nums and not any(abs(n-hc_total) < hc_total*0.35 for n in _nums):
                    pass  # cai para Estágio 2
                else:
                    return [("markdown", resp1)]
            else:
                return [("markdown", resp1)]
    except Exception: pass

    # ══════════════════════════════════════════════════════════
    # ESTÁGIO 2 — CÓDIGO PYTHON COM TEMPLATE OBRIGATÓRIO
    # ══════════════════════════════════════════════════════════

    _setup = """# === SETUP OBRIGATÓRIO — NÃO MODIFICAR ===
import pandas as _pd
df_c = df.copy()
df_c["_D"] = _pd.to_datetime(df_c["DATA"], dayfirst=True, errors="coerce")
df_c["STATUS_TIPO"] = df_c["STATUS_TIPO"].fillna("").str.upper().str.strip()
ativos_all   = df_c[df_c["STATUS_TIPO"] == "ATIVO"]
inativos_all = df_c[df_c["STATUS_TIPO"] == "INATIVO"]
mes_ref      = ativos_all["_D"].max()
df_mes       = ativos_all[ativos_all["_D"] == mes_ref]
hc_total     = len(df_mes)
# === FIM SETUP ==="""

    _code_system = """Você é engenheiro de dados Python especialista em People Analytics.
Escreva código Python preciso, sem markdown, sem backticks.
Sempre use o SETUP OBRIGATÓRIO fornecido no início.
Defina SEMPRE: resultado (str markdown), tabela_dados (list|None), tabela_titulo (str), grafico_dados (list of tuples|None), grafico_titulo (str).
Para totais simples: grafico_dados = None.
Formato resultado: "**[Métrica]:** {valor} | ▲/▼X% ({val_mom}) MoM | ▲/▼X% ({val_yoy}) YoY"
MESES int: jan=1 fev=2 mar=3 abr=4 mai=5 jun=6 jul=7 ago=8 set=9 out=10 nov=11 dez=12"""

    _code_user = f"""CONTEXTO VALIDAÇÃO:
{_ctx_completo}

SETUP OBRIGATÓRIO (copie exatamente no início do código):
{_setup}

COLUNAS HC: STATUS_TIPO, DATA, EMPRESA, GENERO, ETNIA, SENIORIDADE, AREA, CARGO, TIPO CONTRATACAO, PCD, INICIATIVA (EMPRESA=involuntário / EMPREGADO=voluntário), DATA DE ADMISSAO, DATA DESLIGAMENTO, FY
COLUNAS RS (df_rs): "Data de Fechamento (Indicador Stop)", "Data do Alinhamento\\n(Indicador Stop)", "Time to Hire (Indicador Stop)", "Time to Fill (O inicio)", "Tempo em Definição", "Analista Responsável", "Diretoria", "Empresas", "Nível", "Motivo Abertura"

Para filtrar RS por mês:
  raw = _pd.to_datetime(df_rs["Data de Fechamento (Indicador Stop)"], errors="coerce")
  df_m = df_rs[(raw.dt.year==ANO) & (raw.dt.month==MES)]

PERGUNTA: {pergunta}

Código Python APENAS:"""

    try:
        r2 = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": _code_system},
                {"role": "user",   "content": _code_user},
            ],
            temperature=0.0,
            max_tokens=2500,
        )
        codigo = re.sub(r"```python|```", "", r2.choices[0].message.content).strip()

        # Garante setup no código
        if "mes_ref" not in codigo or "hc_total" not in codigo:
            codigo = _setup + "\n\n" + codigo

        _df_rs_exec = pd.DataFrame()
        if df_rs is not None and not df_rs.empty:
            try: _df_rs_exec = _rs_prep(df_rs.copy())
            except: _df_rs_exec = df_rs.copy()

        local_vars = {
            "df": df.copy(), "df_rs": _df_rs_exec,
            "df_hp": df_hp.copy() if isinstance(df_hp, pd.DataFrame) and not df_hp.empty else pd.DataFrame(),
            "pd": pd, "resultado": "", "fig": None,
            "tabela_dados": None, "tabela_titulo": "",
            "grafico_dados": None, "grafico_titulo": "",
        }
        exec(codigo, {"pd": pd, "__builtins__": __builtins__}, local_vars)

        resultado     = str(local_vars.get("resultado", "")).strip()
        tabela_dados  = local_vars.get("tabela_dados")
        tabela_titulo = local_vars.get("tabela_titulo", "")
        grafico_dados = local_vars.get("grafico_dados")
        grafico_titulo= local_vars.get("grafico_titulo", "")

        # Valida coerência HC
        if re.search(r"(headcount|hc\b|colaboradores|ativos)", _perg_l) and hc_total>50 and resultado:
            _nums = [int(n) for n in re.findall(r'\b(\d+)\b', resultado)]
            if _nums and not any(abs(n-hc_total)<hc_total*0.35 for n in _nums):
                resultado = (f"**Headcount Ativo — {mes_ref_s}**\n\n**{hc_total:,}** colaboradores ativos"
                            f"{_vs(hc_total,hc_ant)}{_ys(hc_total,hc_yoy)}")
                return [("markdown", resultado)]

        output = []
        if grafico_dados and isinstance(grafico_dados, list) and len(grafico_dados)>0:
            try:
                import plotly.graph_objects as go
                labels=[str(x[0]) for x in grafico_dados]; values=[float(x[1]) for x in grafico_dados]
                fig_p=go.Figure(go.Bar(x=labels,y=values,marker_color="#C0003C",
                    text=[str(round(v,1)) for v in values],textposition="outside",
                    textfont=dict(size=11,color="white",family="Poppins")))
                fig_p.update_layout(title=dict(text=grafico_titulo,font=dict(size=14,color="white",family="Poppins"),x=0.5),
                    paper_bgcolor="#111111",plot_bgcolor="#111111",font=dict(color="white",family="Poppins"),
                    xaxis=dict(showgrid=False),yaxis=dict(showgrid=True,gridcolor="rgba(255,255,255,0.08)"),
                    height=340,margin=dict(l=40,r=40,t=50,b=40))
                output.append(("plotly", fig_p))
            except: pass

        if tabela_dados and isinstance(tabela_dados,list) and len(tabela_dados)>0:
            try:
                cols=list(tabela_dados[0].keys())
                md=("**"+tabela_titulo+"**\n\n" if tabela_titulo else "")
                md+="| "+" | ".join(cols)+" |\n|"+"---|"*len(cols)+"\n"
                md+="\n".join("| "+" | ".join(str(row.get(c,"")) for c in cols)+" |" for row in tabela_dados)
                output.append(("markdown", md))
            except: pass

        if resultado and len(resultado)>5:
            output.append(("markdown", resultado))

        if output: return output
    except Exception as e:
        if any(k in str(e).lower() for k in ("429","quota","rate","limit")):
            return [("markdown","⏱️ Limite Groq atingido. Aguarde alguns segundos.")]

    # ══════════════════════════════════════════════════════════
    # ESTÁGIO 3 — FALLBACK: dados pré-calculados direto
    # ══════════════════════════════════════════════════════════
    try:
        r3 = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Você é analista de People Analytics. Use SOMENTE os dados do contexto. Seja direto, máx 5 linhas."},
                {"role": "user", "content": f"CONTEXTO:\n{_ctx_completo}\n\nPERGUNTA: {pergunta}\n\nResponda usando APENAS os dados acima. Se não tiver o dado, informe o mais próximo disponível."},
            ],
            temperature=0.0, max_tokens=500,
        )
        return [("markdown", r3.choices[0].message.content.strip())]
    except Exception:
        return [("markdown",
            f"**{mes_ref_s}** — HC Ativo: **{hc_total:,}** | Inativos: **{inat_mes}** | TO%: **{to_mes}%**\n\n"
            f"*Não foi possível processar a análise completa. Dado básico exibido.*")]

# ══════════════════════════════════════════════════════════════
#  TELA DE CHAT (sidebar + área principal)
# ══════════════════════════════════════════════════════════════

def tela_chat(df, df_hp, df_rs, user_name: str, user_email: str):
    # ── SIDEBAR ────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("""<style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
        section[data-testid="stSidebar"]{background:#0d0d0f!important;border-right:1px solid rgba(255,255,255,.06)!important;}
        section[data-testid="stSidebar"] *{font-family:'Poppins',sans-serif!important;color:white!important;}
        section[data-testid="stSidebar"] .stButton button{background:rgba(255,255,255,.04)!important;border:1px solid rgba(255,255,255,.08)!important;border-radius:8px!important;color:rgba(255,255,255,.6)!important;font-size:11px!important;font-weight:500!important;text-align:left!important;padding:8px 12px!important;transition:all .2s!important;width:100%!important;}
        section[data-testid="stSidebar"] .stButton button:hover{background:rgba(230,57,70,.12)!important;border-color:rgba(230,57,70,.3)!important;color:white!important;}
        section[data-testid="stSidebar"] .streamlit-expanderHeader{background:rgba(255,255,255,.02)!important;border:none!important;border-bottom:1px solid rgba(255,255,255,.06)!important;border-radius:0!important;color:rgba(255,255,255,.45)!important;font-size:9px!important;font-weight:700!important;letter-spacing:1.8px!important;text-transform:uppercase!important;padding:8px 4px!important;}
        section[data-testid="stSidebar"] .streamlit-expanderHeader:hover{color:rgba(255,255,255,.75)!important;}
        section[data-testid="stSidebar"] .streamlit-expanderContent{background:transparent!important;border:none!important;padding:4px 0 8px!important;}
        section[data-testid="stSidebar"] .stExpander{border:none!important;margin-bottom:4px!important;}
        .sb-divider{height:1px;background:linear-gradient(90deg,transparent,rgba(230,57,70,.3),transparent);margin:12px 0;}
        .sb-section{font-size:9px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,.25)!important;margin:16px 0 8px;}
        .sb-stat{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px 12px;margin-bottom:8px;}
        .sb-stat-label{font-size:9px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:rgba(255,255,255,.3)!important;margin-bottom:2px;}
        .sb-stat-value{font-size:18px;font-weight:800;color:white!important;}
        .sb-stat-sub{font-size:10px;color:rgba(255,255,255,.3)!important;}
        .sb-user{background:rgba(192,0,60,.08);border:1px solid rgba(192,0,60,.2);border-radius:8px;padding:10px 12px;margin-bottom:8px;}
        .sb-user-name{font-size:12px;font-weight:700;color:white!important;}
        .sb-user-email{font-size:10px;color:rgba(255,255,255,.4)!important;}
        div[data-testid="stSelectbox"]>div>div{background:rgba(255,255,255,.07)!important;border:1px solid rgba(255,255,255,.15)!important;border-radius:8px!important;}
        div[data-testid="stSelectbox"]>div>div>div{color:white!important;font-size:12px!important;font-weight:600!important;}
        div[data-testid="stSelectbox"] label{color:rgba(255,255,255,.35)!important;font-size:9px!important;font-weight:700!important;letter-spacing:1.5px!important;text-transform:uppercase!important;}
        </style>""", unsafe_allow_html=True)

        emp_disp = sorted(df["EMPRESA"].dropna().unique().tolist()) if "EMPRESA" in df.columns else []
        _wm_default = ["WEBMOTORS"] if "WEBMOTORS" in emp_disp else emp_disp[:1]
        if st.button("✕  Limpar filtros", use_container_width=True, key="btn_limpar"):
            for k in list(st.session_state.keys()):
                if "empresa" in k.lower(): del st.session_state[k]
            st.session_state["_emp_default"] = _wm_default
            st.rerun()

        _default_sel = [e for e in st.session_state.get("_emp_default", _wm_default) if e in emp_disp] or _wm_default
        emp_sel = st.multiselect("Empresa", options=emp_disp, default=_default_sel,
            key="ms_empresa", label_visibility="collapsed", placeholder="Selecione empresas...")
        st.session_state["_emp_default"] = emp_sel
        if emp_sel: df = df[df["EMPRESA"].isin(emp_sel)]

        # ── Filtro Global de Mês ────────────────────────────────
        _hc_meses = []
        if "DATA" in df.columns and len(df)>0:
            _dfd = _prep(df.copy())
            _hc_meses = sorted(_dfd[_dfd["STATUS_TIPO"]=="ATIVO"]["_D"].dropna().unique().tolist(), reverse=True)

        def _fy_lbl(ts): return f"FY{str(ts.year+1 if ts.month>=7 else ts.year)[-2:]}"
        _opcoes_lbl = [f"{_fy_lbl(t)} · {t.strftime('%b/%Y').upper()}" for t in _hc_meses]
        _opcoes_ts  = list(_hc_meses)

        if _opcoes_lbl:
            _prev = st.session_state.get("_global_mes_label", _opcoes_lbl[0])
            _def  = _opcoes_lbl.index(_prev) if _prev in _opcoes_lbl else 0
            _sel  = st.selectbox("📅 Mês de Referência", options=_opcoes_lbl, index=_def, key="sb_global_mes")
            st.session_state["_global_mes_label"] = _sel
            _gts  = _opcoes_ts[_opcoes_lbl.index(_sel)]
            st.session_state["global_mes_ts"]   = _gts
            st.session_state["rs_mes_sel"]       = _gts
        else:
            st.session_state["global_mes_ts"] = None
            st.session_state["rs_mes_sel"]    = None
            _gts = None

        st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

        # ── Stats ───────────────────────────────────────────────
        atm=inm=0; mes_ref_label=""
        if "DATA" in df.columns and len(df)>0:
            dfd = _prep(df.copy())
            mma = _gts if _gts is not None else dfd[dfd["STATUS_TIPO"]=="ATIVO"]["_D"].max()
            mes_ref_label = mma.strftime("%b/%y").upper() if pd.notna(mma) else ""
            dfm = dfd[dfd["_D"]==mma]
            atm = len(dfm[dfm["STATUS_TIPO"]=="ATIVO"]); inm = len(dfm[dfm["STATUS_TIPO"]=="INATIVO"])

        etl = df["DATA_EXTRACAO"].iloc[0] if "DATA_EXTRACAO" in df.columns and len(df)>0 else datetime.now().strftime("%d/%m %H:%M")
        proxima_etl = proximo_5_dia_util()
        hp_status = "✔ carregado" if not df_hp.empty else "⚠ não carregado"
        if not df_hp.empty and "FY_HP" in df_hp.columns:
            hp_status = " | ".join(f"{fy}:{qtd}" for fy,qtd in df_hp["FY_HP"].value_counts().items())

        st.markdown(f"""<div style="display:flex;align-items:center;gap:8px;padding:4px 0 8px">
            <div style="width:30px;height:30px;background:rgba(192,0,60,.15);border:1px solid rgba(192,0,60,.3);border-radius:8px;display:flex;align-items:center;justify-content:center;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#E63946" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
            </div><span style="font-size:15px;font-weight:800;letter-spacing:.8px;text-transform:uppercase;color:white">Webmotors</span></div>
        <div class="sb-user"><div class="sb-user-name">👤 {user_name}</div><div class="sb-user-email">{user_email}</div></div>
        <div class="sb-divider"></div>
        <div style="font-size:9px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:rgba(255,255,255,.25);margin-bottom:6px">{mes_ref_label}</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">
            <div class="sb-stat"><div class="sb-stat-label">Ativos</div><div class="sb-stat-value">{atm:,}</div></div>
            <div class="sb-stat"><div class="sb-stat-label">Inativos</div><div class="sb-stat-value">{inm:,}</div></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
            <div class="sb-stat"><div class="sb-stat-label">Última ETL</div><div class="sb-stat-sub">{etl}</div><div style="font-size:9px;color:rgba(192,0,60,.7);margin-top:2px">Próx: {proxima_etl}</div></div>
            <div class="sb-stat"><div class="sb-stat-label">High Perf.</div><div class="sb-stat-sub">{hp_status}</div></div>
        </div>
        <div class="sb-divider"></div><div class="sb-section">Análises Rápidas</div>""", unsafe_allow_html=True)

        with st.expander("HEADCOUNT", expanded=False):
            for k,lbl in [("hc_empresa","Headcount por Empresa"),("tipo_contrato","Tipo de Contrato"),
                          ("senioridade","Por Senioridade"),("top5_areas","Top 5 Áreas"),("tempo_casa_ativos","Tempo de Casa (Ativos)")]:
                if st.button(lbl, use_container_width=True, key=f"btn_{k}"): st.session_state["analise_rapida"]=k

        with st.expander("DESLIGAMENTOS", expanded=False):
            for k,lbl in [("inativos","Inativos do Mês"),("to_mensal","TO% Mensal (Tabela)"),
                          ("to_grafico","TO% Gráfico 24m"),("tempo_casa_inativos","Tempo de Casa (Inativos)")]:
                if st.button(lbl, use_container_width=True, key=f"btn_{k}"): st.session_state["analise_rapida"]=k

        with st.expander("CAR GROUP", expanded=False):
            for k,lbl in [("turnover_yoy","Turnover YoY (12m)"),("regrettable","Regrettable Turnover"),
                          ("internal_movement","Internal Movement")]:
                if st.button(lbl, use_container_width=True, key=f"btn_{k}"): st.session_state["analise_rapida"]=k

        with st.expander("R&S", expanded=False):
            for k,lbl in [("rs_vagas_abertas","Vagas Abertas"),("rs_vagas_fechadas_rich","Vagas Fechadas"),
                          ("rs_status_vagas","Status das Vagas"),("rs_vagas_consolidadas","Consolidado Histórico")]:
                if st.button(lbl, use_container_width=True, key=f"btn_{k}"): st.session_state["analise_rapida"]=k

        with st.expander("DIVERSIDADE", expanded=False):
            for k,lbl in [("diversidade","Visão Geral"),("mulheres_empresa","% Mulheres"),
                          ("diversidade_detalhada","Pretos|PCD|+46"),("mulheres_lideranca","Mulheres Liderança"),
                          ("pretos_lideranca","Pretos Liderança")]:
                if st.button(lbl, use_container_width=True, key=f"btn_{k}"): st.session_state["analise_rapida"]=k

        st.markdown('<div class="sb-divider"></div><div class="sb-section">Sessão</div>', unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        with c1:
            if st.button("↺ Nova conversa", use_container_width=True, key="btn_nova"):
                st.session_state.update({"historico":[],"mensagens":[]}); st.rerun()
        with c2:
            if st.button("→ Sair", use_container_width=True, key="btn_sair"): st.logout()

    # ── ÁREA PRINCIPAL ─────────────────────────────────────────
    st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
    section[data-testid="stMain"]{background:#0f0f11!important;}
    section[data-testid="stMain"] *{font-family:'Poppins',sans-serif!important;}
    div[data-testid="stChatMessage"]{background:#ffffff!important;border:1px solid rgba(0,0,0,.06)!important;border-radius:12px!important;margin-bottom:12px!important;}
    div[data-testid="stChatMessage"] p,div[data-testid="stChatMessage"] li,div[data-testid="stChatMessage"] span{color:#1a1a1a!important;}
    div[data-testid="stChatInput"] textarea{background:#ffffff!important;border:1px solid rgba(0,0,0,.12)!important;border-radius:12px!important;color:#1a1a1a!important;}
    </style>""", unsafe_allow_html=True)

    st.markdown(f'''<div style="background:linear-gradient(135deg,#7a0a1e 0%,#a0102a 40%,#6b0a1a 100%);padding:20px 28px 16px;margin-bottom:8px;border-radius:12px">
        <div style="font-family:Poppins,sans-serif;font-size:20px;font-weight:800;text-transform:uppercase;letter-spacing:.5px;line-height:1.2;color:#ffffff">
            Pessoas &amp; Cultura<span style="font-size:11px;font-weight:500;color:rgba(255,255,255,.55);letter-spacing:2px;margin-left:10px">| HR Analytics</span></div>
        <div style="font-family:Poppins,sans-serif;font-size:10px;color:rgba(255,255,255,.5);letter-spacing:1px;text-transform:uppercase;margin-top:4px">
            Análises rápidas na sidebar · Perguntas livres no chat abaixo</div></div>''', unsafe_allow_html=True)

    # ── Boas-vindas ─────────────────────────────────────────────
    if not st.session_state.get("mensagens"):
        import random, pytz
        from datetime import datetime as dt_
        tz_br = pytz.timezone("America/Sao_Paulo"); hora = dt_.now(tz_br).hour
        saudacao = "Bom dia" if hora<12 else "Boa tarde" if hora<18 else "Boa noite"
        primeiro_nome = user_name.split()[0] if user_name else ""
        frases = ["Dados são o novo RH — e você está no controle. 🚀",
                  "Decisões baseadas em dados começam aqui. 📊",
                  "Insights de People Analytics em segundos. ⚡",
                  "O que não é medido, não é gerenciado. 🎯",
                  "People Analytics: onde ciência encontra estratégia. 🔬"]
        st.markdown(f"""<div style="text-align:center;padding:48px 20px 24px">
            <div style="font-size:28px;font-weight:800;color:#c0003c;font-family:Poppins,sans-serif">{saudacao}, {primeiro_nome}! 👋</div>
            <div style="font-size:14px;color:#666;margin-top:10px;font-style:italic;font-family:Poppins,sans-serif">{random.choice(frases)}</div>
            <div style="margin-top:20px;font-size:12px;color:#aaa;font-family:Poppins,sans-serif">Use o sidebar para análises rápidas ou faça uma pergunta abaixo</div></div>""", unsafe_allow_html=True)

    LABEL_MAP = {
        "turnover_yoy":"Turnover YoY (12m)","regrettable":"Regrettable Turnover","hc_empresa":"Headcount por Empresa",
        "tipo_contrato":"Tipo de Contrato","top5_areas":"Top 5 Áreas","senioridade":"Por Senioridade",
        "inativos":"Inativos do Mês","to_mensal":"TO% Mensal","to_grafico":"TO% Gráfico 24m",
        "diversidade":"Diversidade — Visão Geral","tempo_casa_ativos":"Tempo de Casa (Ativos)",
        "tempo_casa_inativos":"Tempo de Casa (Inativos)","internal_movement":"Internal Movement",
        "mulheres_empresa":"% Mulheres na Empresa","diversidade_detalhada":"Pretos|PCD|+46",
        "mulheres_lideranca":"Mulheres em Liderança","pretos_lideranca":"Pretos em Liderança",
        "rs_vagas_abertas":"R&S — Vagas Abertas","rs_vagas_fechadas_rich":"R&S — Vagas Fechadas",
        "rs_vagas_fechadas":"R&S — Vagas Fechadas (Mês)","rs_status_vagas":"R&S — Status das Vagas",
        "rs_vagas_consolidadas":"R&S — Consolidado Histórico",
    }

    # Histórico
    for msg in st.session_state.get("mensagens", []):
        avatar = "🧑" if msg["role"]=="user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar): _replay_msg(msg)

    # Análise rápida
    analise_tipo = st.session_state.pop("analise_rapida", None)
    if analise_tipo:
        label = LABEL_MAP.get(analise_tipo, analise_tipo)
        st.session_state["mensagens"].append({"role":"user","content":label})
        with st.chat_message("user", avatar="🧑"): st.markdown(label)
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Calculando..."):
                resultado, fig = executar_analise(analise_tipo, df, df_hp, df_rs)
            msg_dict = _render_resultado(resultado, fig)
            msg_dict["role"] = "assistant"
            if fig is not None:
                import plotly.io as pio
                figs_list = fig if isinstance(fig,list) else [fig]
                fjs = []
                for f in figs_list:
                    try: fjs.append(pio.to_json(f))
                    except: pass
                msg_dict["tipo"] = "html_plotly" if isinstance(resultado,tuple) and resultado[0]=="__HTML__" else "plotly"
                msg_dict["figs_json"] = fjs
                if msg_dict["tipo"] == "plotly": msg_dict["content"] = resultado if isinstance(resultado,str) else ""
            st.session_state["mensagens"].append(msg_dict)
        st.session_state.setdefault("historico",[]).extend([
            {"role":"user","content":label},
            {"role":"assistant","content":label+" (análise executada)"}])

    # Pergunta livre
    pergunta = st.chat_input("Faça uma pergunta sobre os dados...")
    if pergunta:
        st.session_state["mensagens"].append({"role":"user","content":pergunta})
        with st.chat_message("user", avatar="🧑"): st.markdown(pergunta)
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Analisando..."):
                ctx = (f"Empresas: {sorted(df['EMPRESA'].dropna().unique().tolist())} | Ativos: {atm} | Inativos: {inm} | Mês: {mes_ref_label}") if "EMPRESA" in df.columns else ""
                try:
                    partes = rodar_agente_livre(pergunta, st.session_state.get("historico",[]), df, df_hp, ctx, df_rs=df_rs)
                    if isinstance(partes,str): partes=[("markdown",partes)]
                except Exception as e:
                    partes=[("markdown",f"Erro: {str(e)[:200]}")]
            resposta_texto = ""
            for tipo_p,conteudo in partes:
                if tipo_p=="html": render_html_chat(conteudo)
                elif tipo_p=="plotly": st.plotly_chart(conteudo, use_container_width=True)
                elif tipo_p=="markdown": st.markdown(conteudo); resposta_texto+=conteudo+"\n"
            if not resposta_texto: resposta_texto="(visualização gerada)"
        st.session_state["mensagens"].append({"role":"assistant","content":resposta_texto})
        st.session_state.setdefault("historico",[]).extend([
            {"role":"user","content":pergunta},{"role":"assistant","content":resposta_texto}])
        if len(st.session_state.get("historico",[]))>20:
            st.session_state["historico"]=st.session_state["historico"][-20:]

# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def main():
    if not st.user.is_logged_in:
        tela_login()
        return

    user_email = getattr(st.user, "email", "") or ""
    user_name  = getattr(st.user, "name",  "Colaborador") or "Colaborador"

    if not user_email.lower().endswith(f"@{DOMINIO_PERMITIDO}"):
        tela_acesso_negado(user_email)
        return

    if "historico"  not in st.session_state: st.session_state["historico"]  = []
    if "mensagens"  not in st.session_state: st.session_state["mensagens"]  = []

    try:
        df = carregar_dados()
    except Exception as e:
        st.error(f"Erro ao carregar Headcount: {e}")
        st.info("Verifique se o Parquet foi enviado ao GitHub e o GITHUB_TOKEN está configurado.")
        return

    df_hp = carregar_high_performance()
    df_rs = carregar_rs()
    tela_chat(df, df_hp, df_rs, user_name=user_name, user_email=user_email)


if __name__ == "__main__":
    main()
