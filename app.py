# =============================================================
#  AGENTE ANALÍTICO DE HR — Webmotors
#  Backend: Google Gemini 1.5 Flash (gratuito)
#
#  Arquitetura:
#  - Botões sidebar: 100% Python/pandas — ZERO chamadas à API
#  - Perguntas livres: Gemini 1.5 Flash (1-3 chamadas)
#
#  Lógica Regrettable Turnover:
#    ABR/26 → inativos voluntários de ABR/26 × HP onde FY_HP == "FY26"
#    ABR/25 → inativos voluntários de ABR/25 × HP onde FY_HP == "FY25"
#    Regrettable TO% = talentos desligados / HC do mês
#
#  Secrets no Streamlit Cloud:
#    GEMINI_API_KEY    = "AIzaSy..."
#    APP_PASSWORD_HASH = "hash_md5_da_sua_senha"
#    GITHUB_TOKEN      = "ghp_..."
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
HP_PARQUET_URL = (
    "https://raw.githubusercontent.com/gustavowebmotors13-jpg/"
    "hr-analytics-agente/main/HighPerformance_Consolidado.parquet"
)

APP_PASSWORD_HASH = st.secrets.get(
    "APP_PASSWORD_HASH",
    hashlib.md5("demo123".encode()).hexdigest()
)

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
genai.configure(api_key=GEMINI_API_KEY)

# Mapa de mês → FY (jul/ano-1 a jun/ano)
def mes_para_fy(data: pd.Timestamp) -> str:
    """Retorna o FY de uma data. Ex: ABR/26 → FY26, ABR/25 → FY25."""
    if pd.isnull(data): return "OTHERS"
    ano_fy = data.year if data.month >= 7 else data.year
    # Ajuste: jul–dez do ano X pertence ao FY do ano X+1
    if data.month >= 7:
        ano_fy = data.year + 1
    else:
        ano_fy = data.year
    return f"FY{str(ano_fy)[-2:]}"


# ── CARREGAMENTO DOS DADOS ────────────────────────────────────
@st.cache_data(ttl=3600)
def carregar_dados() -> pd.DataFrame:
    import requests, io
    token   = st.secrets.get("GITHUB_TOKEN", "")
    headers = {"Authorization": f"token {token}"} if token else {}
    r = requests.get(PARQUET_URL, headers=headers, timeout=60)
    r.raise_for_status()
    return pd.read_parquet(io.BytesIO(r.content))


@st.cache_data(ttl=3600)
def carregar_high_performance() -> pd.DataFrame:
    import requests, io
    token   = st.secrets.get("GITHUB_TOKEN", "")
    headers = {"Authorization": f"token {token}"} if token else {}
    try:
        r = requests.get(HP_PARQUET_URL, headers=headers, timeout=60)
        if r.status_code == 404: return pd.DataFrame()
        r.raise_for_status()
        return pd.read_parquet(io.BytesIO(r.content))
    except Exception:
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════
#  UTILITÁRIOS
# ══════════════════════════════════════════════════════════════

def _prep(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["_D"] = pd.to_datetime(df["DATA"], dayfirst=True, errors="coerce")
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
    s = re.sub(r'[.\-\s]', '', str(v).strip())
    s = re.sub(r'\.0$', '', s)
    return s.zfill(11)


# ══════════════════════════════════════════════════════════════
#  CÁLCULOS — BOTÕES SIDEBAR (100% Python, zero API)
# ══════════════════════════════════════════════════════════════

def analise_turnover_yoy(df: pd.DataFrame) -> str:
    df = _prep(df)
    mes_max = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()

    def _periodo(ini_off, fim_off):
        ini  = mes_max - pd.DateOffset(months=ini_off)
        fim  = mes_max - pd.DateOffset(months=fim_off)
        at   = df[(df["STATUS_TIPO"] == "ATIVO")   & (df["_D"] >= ini) & (df["_D"] <= fim)]
        inat = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] >= ini) & (df["_D"] <= fim)]
        hc_med = at.groupby("_D").size().mean() if len(at) > 0 else 0
        inv = int(inat["INICIATIVA"].str.upper().str.contains("EMPRESA",   na=False).sum())
        vol = int(inat["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False).sum())
        ti  = _pct(inv, hc_med); tv = _pct(vol, hc_med); tt = _pct(inv + vol, hc_med)
        label = f"{ini.strftime('%b/%y').upper()} → {fim.strftime('%b/%y').upper()}"
        return label, round(hc_med, 1), inv, vol, ti, tv, tt

    l0, hc0, i0, v0, ti0, tv0, tt0 = _periodo(23, 12)
    l1, hc1, i1, v1, ti1, tv1, tt1 = _periodo(11,  0)

    return (
        f"| Métrica | {l0} | {l1} |\n"
        f"|---|---|---|\n"
        f"| HC Médio (12 meses) | {hc0} | {hc1} |\n"
        f"| Desligamentos Involuntários | {i0} | {i1} |\n"
        f"| Desligamentos Voluntários | {v0} | {v1} |\n"
        f"| Turnover % Involuntário | {ti0}% | {ti1}% |\n"
        f"| Turnover % Voluntário | {tv0}% | {tv1}% |\n"
        f"| Turnover % Total | {tt0}% | {tt1}% |\n"
    )


def analise_hc_empresa(df: pd.DataFrame) -> str:
    df = _prep(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    mes_yoy = mes_ref - pd.DateOffset(years=1)
    ref = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)].groupby("EMPRESA").size()
    yoy = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_yoy)].groupby("EMPRESA").size()
    linhas = [f"**Headcount por Empresa — {mes_ref.strftime('%b/%y').upper()}**\n"]
    for emp in ref.index:
        atual = int(ref[emp]); ant = int(yoy.get(emp, 0))
        v = _var(atual, ant); s = _sinal(v)
        linhas.append(
            f"Temos **{atual} colaboradores** na empresa **{emp}**. "
            f"{s} **{abs(v)}% YoY** ({mes_yoy.strftime('%b/%y').upper()}: {ant} colaboradores)"
        )
    return "\n\n".join(linhas)


def analise_tipo_contrato(df: pd.DataFrame) -> str:
    df = _prep(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    mes_yoy = mes_ref - pd.DateOffset(years=1)
    ref = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)].groupby("TIPO CONTRATACAO").size()
    yoy = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_yoy)].groupby("TIPO CONTRATACAO").size()
    linhas = [
        f"**Tipo de Contratação — {mes_ref.strftime('%b/%y').upper()} vs {mes_yoy.strftime('%b/%y').upper()}**\n",
        "| Tipo de Contratação | Qtd Atual | Qtd YoY | Var % |",
        "|---|---|---|---|",
    ]
    for tp in ref.index:
        atual = int(ref[tp]); ant = int(yoy.get(tp, 0))
        v = _var(atual, ant); s = _sinal(v)
        linhas.append(f"| {tp} | {atual} | {ant} | {s} {abs(v)}% |")
    tot_v = _var(ref.sum(), yoy.sum())
    linhas.append(f"| **TOTAL** | **{int(ref.sum())}** | **{int(yoy.sum())}** | {_sinal(tot_v)} {abs(tot_v)}% |")
    return "\n".join(linhas)


def analise_top5_areas(df: pd.DataFrame) -> str:
    df = _prep(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    df_ref  = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)]
    top5    = df_ref.groupby("AREA").size().sort_values(ascending=False).head(5)
    total   = len(df_ref)
    linhas  = [
        f"**Top 5 Áreas por Headcount — {mes_ref.strftime('%b/%y').upper()}** (Total: {total} ativos)\n",
        "| # | Área | Headcount | % do Total |",
        "|---|---|---|---|",
    ]
    for i, (area, qtd) in enumerate(top5.items(), 1):
        linhas.append(f"| {i}º | {area} | {int(qtd)} | {_pct(qtd, total)}% |")
    return "\n".join(linhas)


def analise_senioridade(df: pd.DataFrame) -> str:
    df = _prep(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    df_ref  = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)]
    sen     = df_ref.groupby("SENIORIDADE").size().sort_index()
    total   = len(df_ref)
    linhas  = [
        f"**Headcount por Senioridade — {mes_ref.strftime('%b/%y').upper()}** (Total: {total})\n",
        "| Senioridade | Headcount | % |",
        "|---|---|---|",
    ]
    for s, qtd in sen.items():
        linhas.append(f"| {s} | {int(qtd)} | {_pct(qtd, total)}% |")
    return "\n".join(linhas)


def analise_inativos(df: pd.DataFrame) -> str:
    df = _prep(df)
    mes_ref_inat = df[df["STATUS_TIPO"] == "INATIVO"]["_D"].max()
    mes_ant      = mes_ref_inat - pd.DateOffset(months=1)
    mes_ref_ativ = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    inat_mes = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] == mes_ref_inat)]
    inat_ant = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] == mes_ant)]
    hc_ref   = len(df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref_ativ)])
    total = len(inat_mes); ant = len(inat_ant)
    inv   = int(inat_mes["INICIATIVA"].str.upper().str.contains("EMPRESA",   na=False).sum())
    vol   = int(inat_mes["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False).sum())
    to_pct  = _pct(total, hc_ref)
    var_mom = total - ant; s = _sinal(var_mom)
    return (
        f"**Desligamentos — {mes_ref_inat.strftime('%b/%y').upper()}**\n\n"
        f"- **Total de desligamentos:** {total} ({s} {abs(var_mom)} vs mês anterior: {ant})\n"
        f"- **Involuntários (Iniciativa da Empresa):** {inv}\n"
        f"- **Voluntários (Iniciativa do Empregado):** {vol}\n"
        f"- **TO% do mês:** {to_pct}%\n"
    )


def analise_to_mensal(df: pd.DataFrame) -> str:
    df = _prep(df)
    mes_max = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    meses   = pd.date_range(
        start=(mes_max - pd.DateOffset(months=11)).replace(day=1),
        end=mes_max, freq="MS"
    )
    linhas = [
        "**TO% Mensal — Últimos 12 meses**\n",
        "| Mês/Ano | HC | Inv | Vol | TO% Inv | TO% Vol | TO% Total |",
        "|---|---|---|---|---|---|---|",
    ]
    t_inv = t_vol = 0; hc_list = []
    for mes in meses:
        at   = df[(df["STATUS_TIPO"] == "ATIVO")   & (df["_D"] == mes)]
        inat = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] == mes)]
        hc   = len(at)
        inv  = int(inat["INICIATIVA"].str.upper().str.contains("EMPRESA",   na=False).sum())
        vol  = int(inat["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False).sum())
        ti   = _pct(inv, hc); tv = _pct(vol, hc); tt = _pct(inv + vol, hc)
        linhas.append(f"| {mes.strftime('%b/%Y').upper()} | {hc} | {inv} | {vol} | {ti}% | {tv}% | {tt}% |")
        t_inv += inv; t_vol += vol
        if hc > 0: hc_list.append(hc)
    hc_med = round(sum(hc_list) / len(hc_list), 1) if hc_list else 0
    ti_ac  = _pct(t_inv, hc_med); tv_ac = _pct(t_vol, hc_med); tt_ac = _pct(t_inv + t_vol, hc_med)
    linhas.append(f"| **ACUMULADO 12m** | **{hc_med}** | **{t_inv}** | **{t_vol}** | **{ti_ac}%** | **{tv_ac}%** | **{tt_ac}%** |")
    return "\n".join(linhas)


def analise_to_grafico(df: pd.DataFrame):
    import plotly.graph_objects as go
    df = _prep(df)
    mes_max = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    meses   = pd.date_range(
        start=(mes_max - pd.DateOffset(months=23)).replace(day=1),
        end=mes_max, freq="MS"
    )
    dados = []
    for mes in meses:
        at   = df[(df["STATUS_TIPO"] == "ATIVO")   & (df["_D"] == mes)]
        inat = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] == mes)]
        hc   = len(at)
        inv  = int(inat["INICIATIVA"].str.upper().str.contains("EMPRESA",   na=False).sum())
        vol  = int(inat["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False).sum())
        tot  = inv + vol
        fy   = df[df["_D"] == mes]["FY"].iloc[0] if len(df[df["_D"] == mes]) > 0 else ""
        dados.append({"mes": mes, "hc": hc, "inv": inv, "vol": vol, "total": tot,
                      "to_pct": _pct(tot, hc), "to_inv": _pct(inv, hc), "to_vol": _pct(vol, hc), "fy": fy})
    df_to  = pd.DataFrame(dados)
    df_to  = df_to[df_to["hc"] > 0]
    labels = [m.strftime("%b/%y").upper() for m in df_to["mes"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=labels, y=df_to["to_pct"],
        fill="tozeroy", fillcolor="rgba(192,0,60,0.15)",
        line=dict(color="#C0003C", width=2.5),
        mode="lines+markers+text",
        text=[f"{v}%" for v in df_to["to_pct"]],
        textposition="top center",
        textfont=dict(size=11, color="white", family="Poppins"),
        marker=dict(size=8, color="#C0003C", line=dict(color="white", width=1.5)),
        name="TO% Total",
        hovertemplate="<b>%{x}</b><br>TO%: %{y}%<extra></extra>"
    ))
    fig.update_layout(
        title=dict(text="Turnover Mensal (24 meses)", font=dict(size=16, color="white", family="Poppins"), x=0.5),
        paper_bgcolor="#111111", plot_bgcolor="#111111",
        font=dict(color="white", family="Poppins"),
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", ticksuffix="%", tickfont=dict(size=11)),
        height=380, margin=dict(l=40, r=40, t=50, b=40), hovermode="x unified"
    )
    tabela = [
        "**Detalhamento por FY**\n",
        "| FY | Mês | HC | Inativos | TO% Inv | TO% Vol | TO% Total |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, row in df_to.sort_values("mes", ascending=False).iterrows():
        tabela.append(
            f"| {row['fy']} | {row['mes'].strftime('%b/%Y').upper()} | "
            f"{int(row['hc'])} | {int(row['total'])} | "
            f"{row['to_inv']}% | {row['to_vol']}% | {row['to_pct']}% |"
        )
    return "\n".join(tabela), fig


def analise_diversidade(df: pd.DataFrame) -> str:
    df = _prep(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    mes_mom = mes_ref - pd.DateOffset(months=1)
    mes_yoy = mes_ref - pd.DateOffset(years=1)
    def _m(sub):
        hc   = len(sub)
        masc = int(sub["GENERO"].str.upper().str.contains("MASCULINO", na=False).sum()) if "GENERO" in sub.columns else 0
        fem  = int(sub["GENERO"].str.upper().str.contains("FEMININO",  na=False).sum()) if "GENERO" in sub.columns else 0
        pret = int(sub["ETNIA"].str.upper().str.contains("PRETO$|PRETO ", na=False).sum()) if "ETNIA" in sub.columns else 0
        pp   = int(sub["ETNIA"].str.upper().str.contains("PRETO|PARDO",  na=False).sum()) if "ETNIA" in sub.columns else 0
        pcd  = int((sub["PCD"] == "SIM").sum()) if "PCD" in sub.columns else 0
        m46  = int((sub["+46"] == "SIM").sum()) if "+46" in sub.columns else 0
        return [hc, masc, fem, pret, pp, pcd, m46]
    r = _m(df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)])
    m = _m(df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_mom)])
    y = _m(df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_yoy)])
    nomes  = ["HEADCOUNT", "MASCULINO", "FEMININO", "PRETOS", "PRETOS & PARDOS", "PCD", "FAIXA +46"]
    linhas = [
        f"**Diversidade — {mes_ref.strftime('%b/%y').upper()}** "
        f"| MoM: {mes_mom.strftime('%b/%y').upper()} "
        f"| YoY: {mes_yoy.strftime('%b/%y').upper()}\n"
    ]
    for i, nome in enumerate(nomes):
        vr = r[i]; vm = m[i]; vy = y[i]
        p  = _pct(vr, r[0]) if i > 0 else 100
        vm_v = _var(vr, vm); vy_v = _var(vr, vy)
        linhas.append(
            f"**{nome}**: {vr} ({p}%) "
            f"| MoM: {_sinal(vm_v)} {abs(vm_v)}% ({vm}) "
            f"| YoY: {_sinal(vy_v)} {abs(vy_v)}% ({vy})"
        )
    return "\n\n".join(linhas)


def analise_tempo_casa_ativos(df: pd.DataFrame) -> str:
    df = _prep(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    df_ref  = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)].copy()
    df_ref["_ADM"]  = pd.to_datetime(df_ref["DATA DE ADMISSAO"], dayfirst=True, errors="coerce")
    df_ref["_ANOS"] = (mes_ref - df_ref["_ADM"]).dt.days / 365.25
    df_ref = df_ref.dropna(subset=["_ANOS"]); total = len(df_ref); media = df_ref["_ANOS"].mean()
    faixas = [
        ("<1 ano",    df_ref[df_ref["_ANOS"] < 1]),
        ("1-2 anos",  df_ref[(df_ref["_ANOS"] >= 1) & (df_ref["_ANOS"] < 2)]),
        ("2-5 anos",  df_ref[(df_ref["_ANOS"] >= 2) & (df_ref["_ANOS"] < 5)]),
        ("5-10 anos", df_ref[(df_ref["_ANOS"] >= 5) & (df_ref["_ANOS"] < 10)]),
        (">10 anos",  df_ref[df_ref["_ANOS"] >= 10]),
    ]
    linhas = [
        f"**Tempo de Casa — Ativos ({mes_ref.strftime('%b/%y').upper()})**\n",
        f"- **Média geral:** {_fmt_anos(media)} | Total: {total}\n",
        "**Distribuição por Faixa:**\n",
        "| Faixa | Quantidade | % |", "|---|---|---|",
    ]
    for nome, sub in faixas:
        linhas.append(f"| {nome} | {len(sub)} | {_pct(len(sub), total)}% |")
    if "AREA" in df_ref.columns:
        top3 = df_ref.groupby("AREA")["_ANOS"].mean().sort_values(ascending=False).head(3)
        linhas.append("\n**Top 3 Áreas com Maior Tempo Médio:**\n")
        for i, (area, anos) in enumerate(top3.items(), 1):
            linhas.append(f"{i}. **{area}**: {_fmt_anos(anos)}")
    return "\n".join(linhas)


def analise_tempo_casa_inativos(df: pd.DataFrame) -> str:
    df = _prep(df)
    mes_max = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    mes_ini = mes_max - pd.DateOffset(months=11)
    df_in   = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] >= mes_ini) & (df["_D"] <= mes_max)].copy()
    df_in["_ADM"]  = pd.to_datetime(df_in["DATA DE ADMISSAO"],  dayfirst=True, errors="coerce")
    df_in["_DESL"] = pd.to_datetime(df_in["DATA DESLIGAMENTO"], dayfirst=True, errors="coerce")
    df_in["_ANOS"] = (df_in["_DESL"] - df_in["_ADM"]).dt.days / 365.25
    df_in = df_in.dropna(subset=["_ANOS"]); total = len(df_in)
    media = df_in["_ANOS"].mean() if total > 0 else 0
    faixas = [
        ("<1 ano",    df_in[df_in["_ANOS"] < 1]),
        ("1-2 anos",  df_in[(df_in["_ANOS"] >= 1) & (df_in["_ANOS"] < 2)]),
        ("2-5 anos",  df_in[(df_in["_ANOS"] >= 2) & (df_in["_ANOS"] < 5)]),
        ("5-10 anos", df_in[(df_in["_ANOS"] >= 5) & (df_in["_ANOS"] < 10)]),
        (">10 anos",  df_in[df_in["_ANOS"] >= 10]),
    ]
    linhas = [
        f"**Tempo de Casa — Inativos ({mes_ini.strftime('%b/%y').upper()} → {mes_max.strftime('%b/%y').upper()})**\n",
        f"- **Média geral dos desligados:** {_fmt_anos(media)} | Total: {total}\n",
        "**Distribuição por Faixa:**\n",
        "| Faixa | Quantidade | % |", "|---|---|---|",
    ]
    for nome, sub in faixas:
        linhas.append(f"| {nome} | {len(sub)} | {_pct(len(sub), total)}% |")
    inv = df_in[df_in["INICIATIVA"].str.upper().str.contains("EMPRESA",   na=False)]
    vol = df_in[df_in["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False)]
    mi  = inv["_ANOS"].mean() if len(inv) > 0 else 0
    mv  = vol["_ANOS"].mean() if len(vol) > 0 else 0
    linhas += [
        "\n**Comparativo por Iniciativa:**\n",
        f"- **Involuntários** ({len(inv)}): média {_fmt_anos(mi)}",
        f"- **Voluntários** ({len(vol)}): média {_fmt_anos(mv)}",
    ]
    return "\n".join(linhas)


# ══════════════════════════════════════════════════════════════
#  REGRETTABLE TURNOVER
#  Lógica: para cada mês analisado, filtra a base HP pelo FY
#  correspondente ao mês antes de cruzar via CPF.
#
#  Exemplo:
#    ABR/26 → FY26 (jul/25–jun/26) → busca HP onde FY_HP == "FY26"
#    ABR/25 → FY25 (jul/24–jun/25) → busca HP onde FY_HP == "FY25"
#
#  Regrettable TO% = talentos desligados voluntariamente / HC do mês
# ══════════════════════════════════════════════════════════════

def analise_regrettable_turnover(df_hc: pd.DataFrame, df_hp: pd.DataFrame) -> str:
    if df_hp.empty:
        return (
            "⚠️ **Arquivo High Performance não encontrado no GitHub.**\n\n"
            "Execute o ETL (`Ativo_e_Inativos.py`) para gerar e subir o "
            "`HighPerformance_Consolidado.parquet`."
        )

    if "CPF" not in df_hc.columns:
        return "⚠️ Coluna CPF não encontrada no Headcount. Verifique o ETL."

    df_hc = df_hc.copy()
    df_hp = df_hp.copy()

    # Normaliza CPF em ambos
    df_hc["_CPF"] = df_hc["CPF"].apply(_norm_cpf)
    df_hp["_CPF"] = df_hp["CPF"].apply(_norm_cpf) if "CPF" in df_hp.columns else ""

    # Prepara datas do headcount
    df_hc["_D"] = pd.to_datetime(df_hc["DATA"], dayfirst=True, errors="coerce")

    # Mês de referência = mês mais recente dos ativos
    mes_ref = df_hc[df_hc["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    mes_yoy = mes_ref - pd.DateOffset(years=1)   # YoY

    def _calcular(mes: pd.Timestamp):
        """
        Para um mês específico:
        1. Determina o FY do mês
        2. Filtra base HP pelo FY correspondente
        3. Cruza inativos voluntários do mês com talentos HP do FY
        4. Calcula Regrettable TO%
        """
        fy_mes = mes_para_fy(mes)

        # Talentos HP do FY correto — considera APENAS H_P == "HP" (exclui POTENCIAL)
        hp_fy = df_hp[df_hp["FY_HP"] == fy_mes] if "FY_HP" in df_hp.columns else df_hp
        hp_fy = hp_fy[hp_fy["H_P"] == "HP"] if "H_P" in hp_fy.columns else hp_fy
        cpfs_talentos = set(hp_fy[hp_fy["_CPF"] != ""]["_CPF"].unique())

        # HC do mês (ativos)
        hc = len(df_hc[(df_hc["STATUS_TIPO"] == "ATIVO") & (df_hc["_D"] == mes)])

        # Inativos voluntários do mês
        inat_vol = df_hc[
            (df_hc["STATUS_TIPO"] == "INATIVO") &
            (df_hc["_D"] == mes) &
            (df_hc["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False))
        ]

        # Cruza com talentos do FY
        talentos_deslig = inat_vol[inat_vol["_CPF"].isin(cpfs_talentos)]
        qtd = len(talentos_deslig)
        to_pct = _pct(qtd, hc)

        # Detalhe: nome + classificação HP/Potencial
        detalhes = []
        for _, row in talentos_deslig.iterrows():
            cpf    = row["_CPF"]
            hp_row = hp_fy[hp_fy["_CPF"] == cpf]
            if not hp_row.empty:
                hp_tipo = hp_row.iloc[0].get("H_P",     "")
                nome_hp = hp_row.iloc[0].get("NOME_HP", row.get("NOME COMPLETO", ""))
            else:
                hp_tipo = ""
                nome_hp = row.get("NOME COMPLETO", "")
            detalhes.append(f"{nome_hp} ({hp_tipo})" if hp_tipo else nome_hp)

        return hc, qtd, to_pct, detalhes, fy_mes

    hc_ref, reg_ref, to_ref, det_ref, fy_ref = _calcular(mes_ref)
    hc_yoy, reg_yoy, to_yoy, det_yoy, fy_yoy = _calcular(mes_yoy)

    var_yoy = _var(reg_ref, reg_yoy); s_yoy = _sinal(var_yoy)

    linhas = [
        f"**Regrettable Turnover — {mes_ref.strftime('%b/%y').upper()}**\n",
        f"*Desligamentos voluntários de talentos High Performance (HP) — filtrado por FY*\n",
        "---",
        f"| Métrica | {mes_yoy.strftime('%b/%y').upper()} ({fy_yoy}) | {mes_ref.strftime('%b/%y').upper()} ({fy_ref}) |",
        "|---|---|---|",
        f"| Base HP utilizada | {fy_yoy} | {fy_ref} |",
        f"| HC Mês Vigente | {hc_yoy} | {hc_ref} |",
        f"| Desligamentos Vol. de Talentos | {reg_yoy} | {reg_ref} |",
        f"| Regrettable TO% | {to_yoy}% | {to_ref}% |",
        "",
        f"**Variação YoY:** {s_yoy} {abs(var_yoy)}% vs {mes_yoy.strftime('%b/%y').upper()} ({reg_yoy} talentos desligados)",
    ]

    # Detalhe mês atual
    if det_ref:
        linhas += [
            f"\n**Talentos HP desligados voluntariamente em {mes_ref.strftime('%b/%y').upper()} ({fy_ref}):**\n"
        ]
        for d in det_ref:
            linhas.append(f"- {d}")
    else:
        linhas.append(
            f"\n✅ Nenhum talento HP de {fy_ref} se desligou voluntariamente em {mes_ref.strftime('%b/%y').upper()}."
        )

    # Detalhe YoY
    if det_yoy:
        linhas += [
            f"\n**Talentos HP desligados em {mes_yoy.strftime('%b/%y').upper()} ({fy_yoy}) — YoY:**\n"
        ]
        for d in det_yoy:
            linhas.append(f"- {d}")
    else:
        linhas.append(
            f"\n✅ Nenhum talento HP de {fy_yoy} se desligou voluntariamente em {mes_yoy.strftime('%b/%y').upper()}."
        )

    return "\n".join(linhas)


# ── Dispatcher ────────────────────────────────────────────────
def executar_analise(tipo: str, df: pd.DataFrame, df_hp: pd.DataFrame = None):
    try:
        if tipo == "turnover_yoy":         return analise_turnover_yoy(df), None
        if tipo == "hc_empresa":           return analise_hc_empresa(df), None
        if tipo == "tipo_contrato":        return analise_tipo_contrato(df), None
        if tipo == "top5_areas":           return analise_top5_areas(df), None
        if tipo == "senioridade":          return analise_senioridade(df), None
        if tipo == "inativos":             return analise_inativos(df), None
        if tipo == "to_mensal":            return analise_to_mensal(df), None
        if tipo == "diversidade":          return analise_diversidade(df), None
        if tipo == "tempo_casa_ativos":    return analise_tempo_casa_ativos(df), None
        if tipo == "tempo_casa_inativos":  return analise_tempo_casa_inativos(df), None
        if tipo == "regrettable":
            return analise_regrettable_turnover(df, df_hp if df_hp is not None else pd.DataFrame()), None
        if tipo == "to_grafico":
            tabela, fig = analise_to_grafico(df)
            return tabela, fig
    except Exception as e:
        return f"❌ **Erro no cálculo:** `{str(e)[:300]}`", None


# ══════════════════════════════════════════════════════════════
#  AGENTE LIVRE — Gemini apenas para perguntas digitadas
# ══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Você é um assistente especializado em análise de dados de RH da Webmotors.

DATAFRAMES DISPONÍVEIS:

df (Headcount — ativos e inativos):
- STATUS_TIPO: "ATIVO" ou "INATIVO"
- EMPRESA, AREA, DIRETORIA, CARGO, SENIORIDADE
- TIPO CONTRATACAO, GENERO, ETNIA
- DATA: primeiro dia do mês de referência
- DATA DESLIGAMENTO, DATA DE ADMISSAO
- INICIATIVA: "INICIATIVA DA EMPRESA" ou "INICIATIVA DO EMPREGADO"
- CPF: chave de cruzamento com df_hp
- FY: ano fiscal do registro

df_hp (High Performance — talentos HP e Potencial):
- CPF: chave de cruzamento com df
- NOME_HP, DIRETORIA_HP, CARGO_HP, REGIME
- H_P: "HP" ou "POTENCIAL" — para Regrettable Turnover usar APENAS H_P == "HP"
- FY_HP: ano fiscal da avaliação (FY25, FY26...) — use para filtrar o cruzamento
- DATA_DESLIGAMENTO_HP: data de desligamento se houver
- MOTIVO_HP: motivo do desligamento
- DPO_2022, DPO_2023, DPO_2024, DPO_2025: notas de desempenho

REGRA IMPORTANTE para cruzamento Regrettable:
  - Para analisar um mês, determine o FY do mês (jul→jun)
  - Filtre df_hp onde FY_HP == FY do mês ANTES de cruzar via CPF
  - ABR/26 → FY26; ABR/25 → FY25
  - Normalize CPF com .str.zfill(11) antes do merge

Regras gerais:
1. Para INICIATIVA use .str.upper().str.contains().
2. Responda em português brasileiro, apenas markdown puro.
3. Salve resultado na variável 'resultado'.
"""

FERRAMENTAS = [
    {"name": "obter_schema",
     "description": "Retorna o schema de df e df_hp. Use SEMPRE como primeiro passo.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"name": "executar_pandas",
     "description": "Executa código Python/pandas em df e df_hp. Salve em 'resultado'.",
     "parameters": {"type": "object",
                    "properties": {"codigo": {"type": "string"}},
                    "required": ["codigo"]}}
]


def _schema(df, df_hp):
    def _cols(d):
        return "\n".join(
            f"  {c} ({d[c].dtype}): ex. {', '.join(str(e) for e in d[c].dropna().unique()[:3])}"
            for c in d.columns
        )
    at = len(df[df["STATUS_TIPO"] == "ATIVO"])   if "STATUS_TIPO" in df.columns else "?"
    it = len(df[df["STATUS_TIPO"] == "INATIVO"]) if "STATUS_TIPO" in df.columns else "?"
    hp_fy = df_hp["FY_HP"].value_counts().to_dict() if "FY_HP" in df_hp.columns else {}
    return (
        f"=== df (Headcount) ===\nTotal: {len(df)} | Ativos: {at} | Inativos: {it}\n{_cols(df)}\n\n"
        f"=== df_hp (High Performance) ===\nTotal: {len(df_hp)} | por FY: {hp_fy}\n{_cols(df_hp)}"
    )


def _exec_pandas(codigo, df, df_hp):
    try:
        lv = {"df": df, "df_hp": df_hp, "pd": pd}
        exec(codigo, {}, lv)
        res = lv.get("resultado", "Sem variável 'resultado'.")
        if isinstance(res, pd.DataFrame): return res.to_string(index=False, max_rows=50)
        if isinstance(res, pd.Series):    return res.to_string(max_rows=50)
        try:
            import plotly.graph_objects as go
            if isinstance(res, go.Figure): return "__PLOTLY__:" + res.to_json()
        except Exception: pass
        return str(res)
    except Exception as e:
        return f"ERRO: {e}"


def rodar_agente_livre(pergunta, historico, df, df_hp, contexto=""):
    system = SYSTEM_PROMPT + ("\n" + contexto if contexto else "")
    model  = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=system,
        tools=[{"function_declarations": FERRAMENTAS}]
    )
    hist_gemini = [
        {"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]}
        for m in historico
    ]
    chat = model.start_chat(history=hist_gemini)
    MAX_RETRIES = 4; BASE_WAIT = 15

    def _enviar(msg):
        for t in range(MAX_RETRIES):
            try:
                return chat.send_message(msg)
            except Exception as e:
                es = str(e).lower()
                if any(k in es for k in ("429", "quota", "rate", "resource_exhausted")):
                    if t < MAX_RETRIES - 1:
                        w = BASE_WAIT * (2 ** t)
                        st.toast(f"⏳ Aguardando {w}s...", icon="⏳")
                        time.sleep(w)
                    else: raise
                else: raise

    resp = _enviar(pergunta)
    for _ in range(6):
        calls = [p.function_call for p in resp.parts if hasattr(p, "function_call") and p.function_call.name]
        if not calls:
            try:    return resp.text
            except: return "(sem resposta)"
        results = []
        for call in calls:
            nome = call.name; args = dict(call.args) if call.args else {}
            res  = _schema(df, df_hp) if nome == "obter_schema" else _exec_pandas(args.get("codigo", ""), df, df_hp)
            results.append(genai.protos.Part(
                function_response=genai.protos.FunctionResponse(name=nome, response={"result": res})
            ))
        resp = _enviar(results)
    return "O agente não conseguiu completar a análise."


# ── TELA DE LOGIN ─────────────────────────────────────────────
def tela_login():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap');
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
    .lc { width:100%; background:rgba(8,4,12,.75); border:1px solid rgba(255,255,255,.08); border-radius:20px; padding:36px 32px 32px; }
    .lc-top { display:flex; align-items:center; justify-content:space-between; margin-bottom:24px; }
    .lc-logo { display:flex; align-items:center; gap:10px; }
    .lc-icon { width:34px; height:34px; background:rgba(210,45,65,.15); border:1px solid rgba(210,45,65,.3); border-radius:9px; display:flex; align-items:center; justify-content:center; }
    .lc-name { font-size:16px; font-weight:800; color:white; letter-spacing:1.5px; text-transform:uppercase; }
    .lc-status { display:flex; align-items:center; gap:5px; font-family:'Space Mono',monospace; font-size:10px; color:rgba(255,255,255,.25); text-transform:uppercase; }
    .lc-dot { width:6px; height:6px; background:#4ade80; border-radius:50%; display:inline-block; animation:pulse 2s infinite; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
    .lc-div { height:1px; background:linear-gradient(90deg,transparent,rgba(210,45,65,.35),transparent); margin-bottom:24px; }
    .lc-tag { display:inline-flex; align-items:center; gap:6px; background:rgba(210,45,65,.1); border:1px solid rgba(210,45,65,.2); border-radius:6px; padding:4px 10px; font-size:10px; font-weight:600; color:#e05070; letter-spacing:1px; text-transform:uppercase; margin-bottom:14px; }
    .lc-title { font-size:28px; font-weight:800; color:white; letter-spacing:-.5px; line-height:1.1; margin-bottom:6px; text-transform:uppercase; }
    .lc-title span { color:#d9304f; }
    .lc-sub { font-size:10px; color:rgba(255,255,255,.28); margin-bottom:28px; letter-spacing:.8px; text-transform:uppercase; }
    .lc-foot { margin-top:20px; padding-top:16px; border-top:1px solid rgba(255,255,255,.04); }
    .lc-foot-l1 { font-size:9px; font-weight:600; color:rgba(255,255,255,.18); text-transform:uppercase; letter-spacing:.8px; margin-bottom:2px; }
    .lc-foot-l2 { font-size:9px; color:rgba(200,37,63,.4); text-transform:uppercase; letter-spacing:.5px; }
    div[data-testid="stForm"] { border:none !important; padding:0 !important; background:transparent !important; }
    div[data-testid="stTextInput"] input { background:rgba(255,255,255,.05) !important; border:1px solid rgba(255,255,255,.08) !important; border-radius:10px !important; color:white !important; letter-spacing:3px !important; font-size:15px !important; padding:12px 16px !important; }
    div[data-testid="stTextInput"] input:focus { border-color:rgba(210,45,65,.5) !important; background:rgba(210,45,65,.04) !important; box-shadow:none !important; }
    div[data-testid="stTextInput"] label { color:rgba(255,255,255,.3) !important; font-size:9px !important; font-weight:700 !important; letter-spacing:2px !important; text-transform:uppercase !important; }
    small,.st-emotion-cache-1gulkj5,[data-testid="InputInstructions"],div[class*="InputInstructions"],div[class*="inputInstructions"],div[data-testid="stTextInput"]>div>div>div:last-child { display:none !important; }
    div[data-testid="stFormSubmitButton"]>button { background:rgba(210,45,65,.35) !important; border:1px solid rgba(210,45,65,.55) !important; border-radius:10px !important; color:rgba(255,255,255,.75) !important; font-size:11px !important; font-weight:700 !important; letter-spacing:1.5px !important; text-transform:uppercase !important; padding:12px !important; width:100% !important; transition:all .2s !important; }
    div[data-testid="stFormSubmitButton"]>button:hover { background:#c8253f !important; border-color:#c8253f !important; color:white !important; }
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
        senha  = st.text_input("Senha de Acesso", type="password", placeholder="••••••••••")
        submit = st.form_submit_button("🔒  Acessar Plataforma", use_container_width=True)
        if submit:
            if hashlib.md5(senha.encode()).hexdigest() == APP_PASSWORD_HASH:
                st.session_state.update({"autenticado": True, "historico": [], "mensagens": []})
                st.rerun()
            else:
                st.error("Senha incorreta. Solicite ao responsável pelo HR Analytics.")

    st.markdown('''
    <div class="lc-foot">
      <div class="lc-foot-l1">HR Analytics &amp; Operations | Webmotors SA</div>
      <div class="lc-foot-l2">Owner: Gustavo Pereira das Neves</div>
    </div>
    ''', unsafe_allow_html=True)


# ── TELA DE CHAT ──────────────────────────────────────────────
def tela_chat(df: pd.DataFrame, df_hp: pd.DataFrame):

    with st.sidebar:
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
        section[data-testid="stSidebar"] { background:#0d0d0f !important; border-right:1px solid rgba(255,255,255,.06) !important; }
        section[data-testid="stSidebar"] * { font-family:'Poppins',sans-serif !important; color:white !important; }
        button[data-testid="collapsedControl"],section[data-testid="stSidebarCollapseButton"],
        div[data-testid="stSidebarCollapseButton"],button[kind="header"],
        [title="keyboard_double_arrow_left"],[aria-label="keyboard_double_arrow_left"],
        button[title*="keyboard"],span[class*="material"] { display:none !important; }
        section[data-testid="stSidebar"] .stButton button {
            background:rgba(255,255,255,.04) !important; border:1px solid rgba(255,255,255,.08) !important;
            border-radius:8px !important; color:rgba(255,255,255,.6) !important;
            font-size:11px !important; font-weight:500 !important; text-align:left !important;
            padding:8px 12px !important; transition:all .2s !important;
        }
        section[data-testid="stSidebar"] .stButton button:hover { background:rgba(230,57,70,.12) !important; border-color:rgba(230,57,70,.3) !important; color:white !important; }
        .sb-logo { display:flex; align-items:center; gap:8px; padding:4px 0 16px; }
        .sb-logo-icon { width:30px; height:30px; background:rgba(230,57,70,.15); border:1px solid rgba(230,57,70,.3); border-radius:8px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
        .sb-logo-name { font-size:15px; font-weight:800; letter-spacing:.8px; text-transform:uppercase; }
        .sb-divider { height:1px; background:linear-gradient(90deg,transparent,rgba(230,57,70,.3),transparent); margin:12px 0; }
        .sb-section { font-size:9px; font-weight:700; letter-spacing:2px; text-transform:uppercase; color:rgba(255,255,255,.25) !important; margin:16px 0 8px; }
        .sb-stat { background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.06); border-radius:8px; padding:10px 12px; margin-bottom:8px; }
        .sb-stat-label { font-size:9px; font-weight:600; letter-spacing:1px; text-transform:uppercase; color:rgba(255,255,255,.3) !important; margin-bottom:2px; }
        .sb-stat-value { font-size:18px; font-weight:800; color:white !important; }
        .sb-stat-sub { font-size:10px; color:rgba(255,255,255,.3) !important; }
        </style>
        """, unsafe_allow_html=True)

        # Filtros
        st.markdown('<div class="sb-section" style="margin-top:4px">Filtros</div>', unsafe_allow_html=True)
        emp_disp = sorted(df["EMPRESA"].dropna().unique().tolist()) if "EMPRESA" in df.columns else []
        emp_sel  = st.multiselect("Empresa", options=emp_disp, default=emp_disp,
                                  key="filtro_empresa", label_visibility="collapsed",
                                  placeholder="Selecione empresas...")
        if emp_sel:
            df = df[df["EMPRESA"].isin(emp_sel)]
        if st.button("✕  Limpar filtros", use_container_width=True, key="btn_limpar"):
            st.session_state.pop("filtro_empresa", None); st.rerun()
        if emp_sel and len(emp_sel) < len(emp_disp):
            st.markdown(f'<div style="font-size:9px;color:rgba(230,57,70,.8);margin-top:2px">🔴 {", ".join(emp_sel)}</div>', unsafe_allow_html=True)

        st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

        # Cards
        mes_ref_label = ""
        if "DATA" in df.columns and "STATUS_TIPO" in df.columns and len(df) > 0:
            dfd = df.copy()
            dfd["_D"] = pd.to_datetime(dfd["DATA"], dayfirst=True, errors="coerce")
            mma = dfd[dfd["STATUS_TIPO"] == "ATIVO"]["_D"].max()
            mes_ref_label = mma.strftime("%b/%y").upper() if pd.notna(mma) else ""
            dfm = dfd[dfd["_D"] == mma]
            atm = len(dfm[dfm["STATUS_TIPO"] == "ATIVO"])
            inm = len(dfm[dfm["STATUS_TIPO"] == "INATIVO"])
            tot = atm + inm
        else:
            atm = inm = tot = 0

        etl      = df["DATA_EXTRACAO"].iloc[0] if "DATA_EXTRACAO" in df.columns and len(df) > 0 else datetime.now().strftime("%d/%m %H:%M")
        hp_info  = ""
        if not df_hp.empty and "FY_HP" in df_hp.columns:
            for fy, qtd in df_hp["FY_HP"].value_counts().items():
                hp_info += f"{fy}: {qtd} | "
            hp_info = hp_info.rstrip(" | ")
        hp_status = hp_info if hp_info else ("✔ carregado" if not df_hp.empty else "⚠ não carregado")

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
        <div style="font-size:9px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:rgba(255,255,255,.25);margin-bottom:6px">{mes_ref_label}</div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:8px">
            <div class="sb-stat"><div class="sb-stat-label">Total</div><div class="sb-stat-value">{tot:,}</div></div>
            <div class="sb-stat"><div class="sb-stat-label">Ativos</div><div class="sb-stat-value">{atm:,}</div></div>
            <div class="sb-stat"><div class="sb-stat-label">Inativos</div><div class="sb-stat-value">{inm:,}</div></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:0">
            <div class="sb-stat"><div class="sb-stat-label">Última ETL</div><div class="sb-stat-sub">{etl}</div></div>
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
            if st.button("↺ Nova conversa", use_container_width=True):
                st.session_state.update({"historico": [], "mensagens": []}); st.rerun()
        with c2:
            if st.button("→ Sair", use_container_width=True):
                st.session_state.clear(); st.rerun()

    # Área principal
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
    section[data-testid="stMain"] { background:#0f0f11 !important; }
    section[data-testid="stMain"]>div { background:#0f0f11 !important; }
    section[data-testid="stMain"] * { font-family:'Poppins',sans-serif !important; }
    div[data-testid="stChatMessage"] { background:#ffffff !important; border:1px solid rgba(0,0,0,.06) !important; border-radius:12px !important; margin-bottom:12px !important; color:#1a1a1a !important; }
    div[data-testid="stChatMessage"] p,div[data-testid="stChatMessage"] li,div[data-testid="stChatMessage"] span { color:#1a1a1a !important; }
    div[data-testid="stChatMessage"] strong { color:#111111 !important; }
    div[data-testid="stChatInput"] textarea { background:#ffffff !important; border:1px solid rgba(0,0,0,.12) !important; border-radius:12px !important; color:#1a1a1a !important; font-family:'Poppins',sans-serif !important; font-size:13px !important; }
    div[data-testid="stChatInput"] textarea::placeholder { color:#888 !important; }
    div[data-testid="stChatInput"] textarea:focus { border-color:rgba(210,45,65,.5) !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('''
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

    # Renderiza histórico
    for msg in st.session_state.get("mensagens", []):
        avatar = "🧑" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar):
            if msg.get("tipo") == "plotly":
                import plotly.io as pio
                st.plotly_chart(pio.from_json(msg["fig_json"]), use_container_width=True)
            if msg.get("content"):
                st.markdown(msg["content"])

    # Análise rápida (botão) — zero API
    analise_tipo = st.session_state.pop("analise_rapida", None)
    if analise_tipo:
        label = LABEL_MAP.get(analise_tipo, analise_tipo)
        st.session_state["mensagens"].append({"role": "user", "content": label})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(label)
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Calculando..."):
                texto, fig = executar_analise(analise_tipo, df, df_hp)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)
                st.markdown(texto)
                import plotly.io as pio
                st.session_state["mensagens"].append({
                    "role": "assistant", "tipo": "plotly",
                    "fig_json": pio.to_json(fig), "content": texto
                })
            else:
                st.markdown(texto)
                st.session_state["mensagens"].append({"role": "assistant", "content": texto})
        st.session_state["historico"].append({"role": "user",      "content": label})
        st.session_state["historico"].append({"role": "assistant", "content": texto})
        if len(st.session_state["historico"]) > 20:
            st.session_state["historico"] = st.session_state["historico"][-20:]

    # Pergunta livre (Gemini)
    pergunta = st.chat_input("Faça uma pergunta livre sobre os dados...")
    if pergunta:
        st.session_state["mensagens"].append({"role": "user", "content": pergunta})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(pergunta)
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Consultando Gemini..."):
                ctx = (
                    f"Empresas: {sorted(df['EMPRESA'].dropna().unique().tolist())} | "
                    f"Total HC: {len(df)} | Ativos: {len(df[df['STATUS_TIPO']=='ATIVO'])} | "
                    f"Inativos: {len(df[df['STATUS_TIPO']=='INATIVO'])} | "
                    f"HP por FY: {df_hp['FY_HP'].value_counts().to_dict() if 'FY_HP' in df_hp.columns else 'não carregado'} | "
                    f"Mês ref: {mes_ref_label}"
                ) if "EMPRESA" in df.columns else ""
                try:
                    resposta = rodar_agente_livre(pergunta, st.session_state.get("historico", []), df, df_hp, ctx)
                except Exception as e:
                    es = str(e).lower()
                    if any(k in es for k in ("429", "quota", "rate", "resource_exhausted")):
                        resposta = "⚠️ **Limite da API Gemini atingido.** Aguarde 1 minuto e tente novamente."
                    else:
                        resposta = f"❌ **Erro:** `{str(e)[:300]}`"
            if isinstance(resposta, str) and resposta.startswith("__PLOTLY__:"):
                import plotly.io as pio
                fig = pio.from_json(resposta.replace("__PLOTLY__:", ""))
                st.plotly_chart(fig, use_container_width=True)
                resposta = "📉 *Gráfico gerado.*"
            else:
                st.markdown(resposta)
        st.session_state["mensagens"].append({"role": "assistant", "content": resposta})
        st.session_state["historico"].append({"role": "user",      "content": pergunta})
        st.session_state["historico"].append({"role": "assistant", "content": resposta})
        if len(st.session_state["historico"]) > 20:
            st.session_state["historico"] = st.session_state["historico"][-20:]


# ── MAIN ──────────────────────────────────────────────────────
def main():
    if not st.session_state.get("autenticado"):
        tela_login(); return
    try:
        df = carregar_dados()
    except Exception as e:
        st.error(f"Erro ao carregar Headcount: {e}")
        st.info("Verifique se o Parquet foi enviado ao GitHub e se o GITHUB_TOKEN está configurado.")
        return
    df_hp = carregar_high_performance()
    tela_chat(df, df_hp)


if __name__ == "__main__":
    main()
