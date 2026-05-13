# =============================================================
#  AGENTE ANALÍTICO DE HR — Webmotors
#  Backend: Google Gemini 1.5 Flash (gratuito)
#
#  Estratégia: cálculos pandas executados direto no Python.
#  O Gemini recebe apenas os dados prontos e formata a resposta.
#  Isso reduz chamadas à API de 4-5 para 1-2 por análise.
#
#  Secrets necessários no Streamlit Cloud:
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


# ── GEMINI — FORMATAÇÃO SIMPLES (1 chamada) ───────────────────
def formatar_com_gemini(dados_texto: str, instrucao: str) -> str:
    """
    Envia dados já calculados ao Gemini para formatar a resposta.
    Apenas 1 chamada à API — sem loop agêntico.
    """
    MAX_RETRIES = 4
    BASE_WAIT   = 15

    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=(
            "Você é um assistente de HR Analytics da Webmotors. "
            "Formate os dados recebidos exatamente como solicitado. "
            "Use apenas markdown puro — NUNCA use HTML. "
            "Responda em português brasileiro."
        )
    )

    prompt = f"{instrucao}\n\nDADOS CALCULADOS:\n{dados_texto}"

    for tentativa in range(MAX_RETRIES):
        try:
            resposta = model.generate_content(prompt)
            return resposta.text
        except Exception as e:
            erro_str = str(e).lower()
            if any(k in erro_str for k in ("429", "quota", "rate", "resource_exhausted")):
                if tentativa < MAX_RETRIES - 1:
                    espera = BASE_WAIT * (2 ** tentativa)
                    st.toast(f"⏳ Limite da API atingido. Aguardando {espera}s...", icon="⏳")
                    time.sleep(espera)
                else:
                    raise
            else:
                raise


# ── AGENTE LIVRE (para perguntas digitadas pelo usuário) ──────
SYSTEM_PROMPT = """Você é um assistente especializado em análise de dados de RH da Webmotors.

Você tem acesso ao dataframe 'df' com dados de colaboradores ATIVOS e INATIVOS da Webmotors, CAR10, LOOP, Revenda Mais e Syonet.

ESTRUTURA DO DATAFRAME:
- STATUS_TIPO: "ATIVO" ou "INATIVO"
- EMPRESA: WEBMOTORS, CAR10, LOOP, REVENDA MAIS, SYONET
- NOME COMPLETO, AREA, DIRETORIA, CARGO, SENIORIDADE
- TIPO CONTRATACAO: CLT, PJ, ESTÁGIO, APRENDIZ, etc.
- GENERO: MASCULINO, FEMININO
- ETNIA: BRANCO, PRETO, PARDO, etc.
- DATA: primeiro dia do mês de referência
- DATA DESLIGAMENTO: data de desligamento (inativos)
- DATA DE ADMISSAO: data de admissão
- INICIATIVA: "INICIATIVA DA EMPRESA" (involuntário) ou "INICIATIVA DO EMPREGADO" (voluntário)
- FY: ano fiscal (FY26, FY25, FY24, FY23, OTHERS)
- DATA_EXTRACAO: timestamp do ETL

Regras:
1. Sempre consulte o schema antes de qualquer consulta.
2. Responda em português brasileiro, claro e objetivo.
3. Para INICIATIVA, SEMPRE use .str.upper().str.contains().
4. Salve o resultado na variável 'resultado'.
5. Para ativos: df[df['STATUS_TIPO'] == 'ATIVO']
6. Para inativos: df[df['STATUS_TIPO'] == 'INATIVO']
7. NUNCA use HTML — apenas markdown puro.
"""

FERRAMENTAS_GEMINI = [
    {
        "name": "obter_schema",
        "description": "Retorna o schema do dataframe. Use SEMPRE como primeiro passo.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "executar_pandas",
        "description": "Executa código Python/pandas no dataframe 'df'. Salve em 'resultado'.",
        "parameters": {
            "type": "object",
            "properties": {
                "codigo": {"type": "string", "description": "Código Python/pandas válido."}
            },
            "required": ["codigo"]
        }
    }
]


def obter_schema(df: pd.DataFrame) -> str:
    linhas = []
    for col in df.columns:
        dtype    = str(df[col].dtype)
        exemplos = df[col].dropna().unique()[:3]
        ex_str   = ", ".join(str(e) for e in exemplos)
        linhas.append(f"  {col} ({dtype}): ex. {ex_str}")
    ativos   = len(df[df["STATUS_TIPO"] == "ATIVO"])   if "STATUS_TIPO" in df.columns else "?"
    inativos = len(df[df["STATUS_TIPO"] == "INATIVO"]) if "STATUS_TIPO" in df.columns else "?"
    ultima   = f"\nÚltima atualização ETL: {df['DATA_EXTRACAO'].iloc[0]}" if "DATA_EXTRACAO" in df.columns else ""
    return (
        f"Total: {len(df)} | Ativos: {ativos} | Inativos: {inativos}{ultima}\n\n"
        "Colunas:\n" + "\n".join(linhas)
    )


def executar_pandas(codigo: str, df: pd.DataFrame) -> str:
    try:
        local_vars = {"df": df, "pd": pd}
        exec(codigo, {}, local_vars)
        resultado = local_vars.get("resultado", "Sem variável 'resultado'.")
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


def rodar_agente_livre(pergunta: str, historico: list, df: pd.DataFrame, contexto: str = "") -> str:
    """Agente com tool_use para perguntas livres do usuário."""
    system = SYSTEM_PROMPT + ("\n" + contexto if contexto else "")
    model  = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=system,
        tools=[{"function_declarations": FERRAMENTAS_GEMINI}]
    )

    gemini_history = []
    for msg in historico:
        role = "user" if msg["role"] == "user" else "model"
        gemini_history.append({"role": role, "parts": [msg["content"]]})

    chat = model.start_chat(history=gemini_history)

    MAX_RETRIES = 4
    BASE_WAIT   = 15

    def enviar(mensagem):
        for tentativa in range(MAX_RETRIES):
            try:
                return chat.send_message(mensagem)
            except Exception as e:
                erro_str = str(e).lower()
                if any(k in erro_str for k in ("429", "quota", "rate", "resource_exhausted")):
                    if tentativa < MAX_RETRIES - 1:
                        espera = BASE_WAIT * (2 ** tentativa)
                        st.toast(f"⏳ Aguardando {espera}s...", icon="⏳")
                        time.sleep(espera)
                    else:
                        raise
                else:
                    raise

    resposta = enviar(pergunta)

    for _ in range(6):
        tool_calls = [
            p.function_call for p in resposta.parts
            if hasattr(p, "function_call") and p.function_call.name
        ]
        if not tool_calls:
            try:
                return resposta.text
            except Exception:
                return "(sem resposta)"

        tool_results = []
        for call in tool_calls:
            nome = call.name
            args = dict(call.args) if call.args else {}
            if nome == "obter_schema":
                res = obter_schema(df)
            elif nome == "executar_pandas":
                res = executar_pandas(args.get("codigo", ""), df)
            else:
                res = "Ferramenta não encontrada."
            tool_results.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=nome, response={"result": res}
                    )
                )
            )
        resposta = enviar(tool_results)

    return "O agente não conseguiu completar a análise."


# ══════════════════════════════════════════════════════════════
#  CÁLCULOS PANDAS DIRETOS — um por análise rápida
# ══════════════════════════════════════════════════════════════

def _prep_datas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["_D"] = pd.to_datetime(df["DATA"], dayfirst=True, errors="coerce")
    return df


def calcular_turnover_yoy(df: pd.DataFrame) -> str:
    df = _prep_datas(df)
    mes_max = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()

    def periodo(ini_off, fim_off=0):
        ini = mes_max - pd.DateOffset(months=ini_off)
        fim = mes_max - pd.DateOffset(months=fim_off)
        at   = df[(df["STATUS_TIPO"] == "ATIVO")   & (df["_D"] >= ini) & (df["_D"] <= fim)]
        inat = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] >= ini) & (df["_D"] <= fim)]
        hc_med = at.groupby("_D").size().mean() if len(at) > 0 else 0
        inv = inat["INICIATIVA"].str.upper().str.contains("EMPRESA",  na=False).sum()
        vol = inat["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False).sum()
        to_inv  = round(inv / hc_med * 100, 1) if hc_med > 0 else 0
        to_vol  = round(vol / hc_med * 100, 1) if hc_med > 0 else 0
        to_tot  = round((inv + vol) / hc_med * 100, 1) if hc_med > 0 else 0
        label   = f"{ini.strftime('%b/%y').upper()} → {fim.strftime('%b/%y').upper()}"
        return label, round(hc_med, 1), int(inv), int(vol), to_inv, to_vol, to_tot

    l_ant, hc_ant, inv_ant, vol_ant, ti_ant, tv_ant, tt_ant = periodo(23, 12)
    l_atu, hc_atu, inv_atu, vol_atu, ti_atu, tv_atu, tt_atu = periodo(11, 0)

    return (
        f"PERÍODO ANTERIOR: {l_ant}\n"
        f"PERÍODO ATUAL:    {l_atu}\n\n"
        f"HC Médio (12m):               {hc_ant} | {hc_atu}\n"
        f"Desligamentos Involuntários:  {inv_ant} | {inv_atu}\n"
        f"Desligamentos Voluntários:    {vol_ant} | {vol_atu}\n"
        f"Turnover % Involuntário:      {ti_ant}% | {ti_atu}%\n"
        f"Turnover % Voluntário:        {tv_ant}% | {tv_atu}%\n"
        f"Turnover % Total:             {tt_ant}% | {tt_atu}%\n"
    )


def calcular_headcount_empresa(df: pd.DataFrame) -> str:
    df = _prep_datas(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    mes_yoy = mes_ref - pd.DateOffset(years=1)
    ref = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)].groupby("EMPRESA").size()
    yoy = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_yoy)].groupby("EMPRESA").size()
    linhas = [f"Mês atual: {mes_ref.strftime('%b/%y').upper()} | YoY: {mes_yoy.strftime('%b/%y').upper()}\n"]
    for emp in ref.index:
        atual = ref[emp]
        ant   = yoy.get(emp, 0)
        var   = round((atual - ant) / ant * 100, 1) if ant > 0 else 0
        sinal = "▲" if var >= 0 else "▼"
        linhas.append(f"{emp}: {atual} colaboradores | {sinal} {var}% YoY (anterior: {ant})")
    return "\n".join(linhas)


def calcular_tipo_contrato(df: pd.DataFrame) -> str:
    df = _prep_datas(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    mes_yoy = mes_ref - pd.DateOffset(years=1)
    ref = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)].groupby("TIPO CONTRATACAO").size()
    yoy = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_yoy)].groupby("TIPO CONTRATACAO").size()
    linhas = [f"Mês atual: {mes_ref.strftime('%b/%y').upper()} | YoY: {mes_yoy.strftime('%b/%y').upper()}\n"]
    for tp in ref.index:
        atual = ref[tp]
        ant   = yoy.get(tp, 0)
        var   = round((atual - ant) / ant * 100, 1) if ant > 0 else 0
        sinal = "▲" if var >= 0 else "▼"
        linhas.append(f"{tp}: atual={atual} | yoy={ant} | var={sinal}{var}%")
    linhas.append(f"TOTAL: atual={ref.sum()} | yoy={yoy.sum()}")
    return "\n".join(linhas)


def calcular_top5_areas(df: pd.DataFrame) -> str:
    df = _prep_datas(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    df_ref  = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)]
    top5    = df_ref.groupby("AREA").size().sort_values(ascending=False).head(5)
    total   = len(df_ref)
    linhas  = [f"Mês: {mes_ref.strftime('%b/%y').upper()} | Total ativos: {total}\n"]
    for i, (area, qtd) in enumerate(top5.items(), 1):
        pct = round(qtd / total * 100, 1)
        linhas.append(f"{i}. {area}: {qtd} colaboradores ({pct}%)")
    return "\n".join(linhas)


def calcular_senioridade(df: pd.DataFrame) -> str:
    df = _prep_datas(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    df_ref  = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)]
    sen     = df_ref.groupby("SENIORIDADE").size().sort_index()
    total   = len(df_ref)
    linhas  = [f"Mês: {mes_ref.strftime('%b/%y').upper()} | Total ativos: {total}\n"]
    for s, qtd in sen.items():
        pct = round(qtd / total * 100, 1)
        linhas.append(f"{s}: {qtd} ({pct}%)")
    return "\n".join(linhas)


def calcular_inativos(df: pd.DataFrame) -> str:
    df = _prep_datas(df)
    mes_ref_inat = df[df["STATUS_TIPO"] == "INATIVO"]["_D"].max()
    mes_ant      = mes_ref_inat - pd.DateOffset(months=1)
    mes_ref_ativ = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()

    inat_mes = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] == mes_ref_inat)]
    inat_ant = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] == mes_ant)]
    hc_ref   = len(df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref_ativ)])

    total = len(inat_mes)
    inv   = inat_mes["INICIATIVA"].str.upper().str.contains("EMPRESA",  na=False).sum()
    vol   = inat_mes["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False).sum()
    to_pct = round(total / hc_ref * 100, 1) if hc_ref > 0 else 0
    var_mom = total - len(inat_ant)
    sinal   = "▲" if var_mom >= 0 else "▼"

    return (
        f"Mês de referência inativos: {mes_ref_inat.strftime('%b/%y').upper()}\n"
        f"Total desligamentos: {total} ({sinal} {abs(var_mom)} vs mês anterior: {len(inat_ant)})\n"
        f"Involuntários (Iniciativa da Empresa): {int(inv)}\n"
        f"Voluntários (Iniciativa do Empregado): {int(vol)}\n"
        f"HC referência ativos: {hc_ref}\n"
        f"TO% do mês: {to_pct}%\n"
    )


def calcular_to_mensal(df: pd.DataFrame) -> str:
    df = _prep_datas(df)
    mes_max = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    mes_ini = mes_max - pd.DateOffset(months=11)
    meses   = pd.date_range(start=mes_ini.replace(day=1), end=mes_max, freq="MS")

    linhas = []
    total_inv = total_vol = total_hc_list = 0
    hc_list = []

    for mes in meses:
        at   = df[(df["STATUS_TIPO"] == "ATIVO")   & (df["_D"] == mes)]
        inat = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] == mes)]
        hc   = len(at)
        inv  = int(inat["INICIATIVA"].str.upper().str.contains("EMPRESA",  na=False).sum())
        vol  = int(inat["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False).sum())
        to_inv = round(inv / hc * 100, 1) if hc > 0 else 0
        to_vol = round(vol / hc * 100, 1) if hc > 0 else 0
        to_tot = round((inv + vol) / hc * 100, 1) if hc > 0 else 0
        linhas.append(f"{mes.strftime('%b/%Y').upper()} | HC={hc} | Inv={inv} | Vol={vol} | TO%Inv={to_inv}% | TO%Vol={to_vol}% | TO%Tot={to_tot}%")
        total_inv += inv
        total_vol += vol
        if hc > 0:
            hc_list.append(hc)

    hc_med   = round(sum(hc_list) / len(hc_list), 1) if hc_list else 0
    to_ac_inv = round(total_inv / hc_med * 100, 1) if hc_med > 0 else 0
    to_ac_vol = round(total_vol / hc_med * 100, 1) if hc_med > 0 else 0
    to_ac_tot = round((total_inv + total_vol) / hc_med * 100, 1) if hc_med > 0 else 0
    linhas.append(f"\nACUMULADO 12m | HC_med={hc_med} | Inv={total_inv} | Vol={total_vol} | TO%Inv={to_ac_inv}% | TO%Vol={to_ac_vol}% | TO%Tot={to_ac_tot}%")

    return "\n".join(linhas)


def calcular_to_grafico(df: pd.DataFrame):
    """Retorna figura Plotly diretamente — sem Gemini."""
    import plotly.graph_objects as go
    df = _prep_datas(df)
    mes_max = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    mes_ini = mes_max - pd.DateOffset(months=23)
    meses   = pd.date_range(start=mes_ini.replace(day=1), end=mes_max, freq="MS")

    dados = []
    for mes in meses:
        at   = df[(df["STATUS_TIPO"] == "ATIVO")   & (df["_D"] == mes)]
        inat = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] == mes)]
        hc   = len(at)
        inv  = int(inat["INICIATIVA"].str.upper().str.contains("EMPRESA",  na=False).sum())
        vol  = int(inat["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False).sum())
        total_inat = inv + vol
        to_pct = round(total_inat / hc * 100, 1) if hc > 0 else 0
        to_inv = round(inv / hc * 100, 1) if hc > 0 else 0
        to_vol = round(vol / hc * 100, 1) if hc > 0 else 0
        fy     = df[df["_D"] == mes]["FY"].iloc[0] if len(df[df["_D"] == mes]) > 0 else ""
        dados.append({"mes": mes, "hc": hc, "inv": inv, "vol": vol,
                      "total": total_inat, "to_pct": to_pct,
                      "to_inv": to_inv, "to_vol": to_vol, "fy": fy})

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
        title=dict(text="Turnover Mensal", font=dict(size=16, color="white", family="Poppins"), x=0.5),
        paper_bgcolor="#111111", plot_bgcolor="#111111",
        font=dict(color="white", family="Poppins"),
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", ticksuffix="%", tickfont=dict(size=11)),
        height=380, margin=dict(l=40, r=40, t=50, b=40), hovermode="x unified"
    )
    return fig, df_to


def calcular_diversidade(df: pd.DataFrame) -> str:
    df = _prep_datas(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    mes_mom = mes_ref - pd.DateOffset(months=1)
    mes_yoy = mes_ref - pd.DateOffset(years=1)

    def metricas(subset):
        hc   = len(subset)
        masc = subset["GENERO"].str.upper().str.contains("MASCULINO", na=False).sum() if "GENERO" in subset.columns else 0
        fem  = subset["GENERO"].str.upper().str.contains("FEMININO",  na=False).sum() if "GENERO" in subset.columns else 0
        pret = subset["ETNIA"].str.upper().str.contains("PRETO",       na=False).sum() if "ETNIA" in subset.columns else 0
        pp   = subset["ETNIA"].str.upper().str.contains("PRETO|PARDO", na=False).sum() if "ETNIA" in subset.columns else 0
        pcd  = (subset["PCD"] == "SIM").sum() if "PCD" in subset.columns else 0
        m46  = (subset["+46"] == "SIM").sum() if "+46" in subset.columns else 0
        return hc, int(masc), int(fem), int(pret), int(pp), int(pcd), int(m46)

    def pct(v, t): return round(v / t * 100, 1) if t > 0 else 0
    def var(a, b): return round((a - b) / b * 100, 1) if b > 0 else 0
    def sinal(v): return "▲" if v >= 0 else "▼"

    r   = metricas(df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)])
    mom = metricas(df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_mom)])
    yoy = metricas(df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_yoy)])

    nomes = ["HC", "MASCULINO", "FEMININO", "PRETOS", "PRETOS & PARDOS", "PCD", "FAIXA +46"]
    linhas = [f"Mês: {mes_ref.strftime('%b/%y').upper()} | MoM: {mes_mom.strftime('%b/%y').upper()} | YoY: {mes_yoy.strftime('%b/%y').upper()}\n"]
    for i, nome in enumerate(nomes):
        v_r, v_m, v_y = r[i], mom[i], yoy[i]
        p_r = pct(v_r, r[0]) if i > 0 else 100
        vm  = var(v_r, v_m); vy = var(v_r, v_y)
        linhas.append(
            f"{nome}: {v_r} ({p_r}%) | MoM: {sinal(vm)}{abs(vm)}% ({v_m}) | YoY: {sinal(vy)}{abs(vy)}% ({v_y})"
        )
    return "\n".join(linhas)


def calcular_tempo_casa_ativos(df: pd.DataFrame) -> str:
    df = _prep_datas(df)
    mes_ref = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    df_ref  = df[(df["STATUS_TIPO"] == "ATIVO") & (df["_D"] == mes_ref)].copy()
    df_ref["_ADM"] = pd.to_datetime(df_ref["DATA DE ADMISSAO"], dayfirst=True, errors="coerce")
    df_ref["_ANOS"] = (mes_ref - df_ref["_ADM"]).dt.days / 365.25
    df_ref = df_ref.dropna(subset=["_ANOS"])

    media   = df_ref["_ANOS"].mean()
    anos_m  = int(media)
    meses_m = int((media - anos_m) * 12)

    faixas = {
        "<1 ano":    df_ref[df_ref["_ANOS"] < 1],
        "1-2 anos":  df_ref[(df_ref["_ANOS"] >= 1) & (df_ref["_ANOS"] < 2)],
        "2-5 anos":  df_ref[(df_ref["_ANOS"] >= 2) & (df_ref["_ANOS"] < 5)],
        "5-10 anos": df_ref[(df_ref["_ANOS"] >= 5) & (df_ref["_ANOS"] < 10)],
        ">10 anos":  df_ref[df_ref["_ANOS"] >= 10],
    }

    total = len(df_ref)
    linhas = [
        f"Mês: {mes_ref.strftime('%b/%y').upper()} | Total analisados: {total}",
        f"Média geral: {anos_m} anos e {meses_m} meses\n",
        "DISTRIBUIÇÃO POR FAIXA:"
    ]
    for faixa, sub in faixas.items():
        pct = round(len(sub) / total * 100, 1) if total > 0 else 0
        linhas.append(f"{faixa}: {len(sub)} ({pct}%)")

    if "AREA" in df_ref.columns:
        top3 = df_ref.groupby("AREA")["_ANOS"].mean().sort_values(ascending=False).head(3)
        linhas.append("\nTOP 3 ÁREAS COM MAIOR TEMPO MÉDIO:")
        for area, anos in top3.items():
            a = int(anos); m = int((anos - a) * 12)
            linhas.append(f"{area}: {a} anos e {m} meses")

    return "\n".join(linhas)


def calcular_tempo_casa_inativos(df: pd.DataFrame) -> str:
    df = _prep_datas(df)
    mes_max = df[df["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    mes_ini = mes_max - pd.DateOffset(months=11)
    df_in   = df[(df["STATUS_TIPO"] == "INATIVO") & (df["_D"] >= mes_ini) & (df["_D"] <= mes_max)].copy()
    df_in["_ADM"]  = pd.to_datetime(df_in["DATA DE ADMISSAO"],   dayfirst=True, errors="coerce")
    df_in["_DESL"] = pd.to_datetime(df_in["DATA DESLIGAMENTO"],  dayfirst=True, errors="coerce")
    df_in["_ANOS"] = (df_in["_DESL"] - df_in["_ADM"]).dt.days / 365.25
    df_in = df_in.dropna(subset=["_ANOS"])

    media  = df_in["_ANOS"].mean()
    anos_m = int(media); meses_m = int((media - anos_m) * 12)

    faixas = {
        "<1 ano":    df_in[df_in["_ANOS"] < 1],
        "1-2 anos":  df_in[(df_in["_ANOS"] >= 1) & (df_in["_ANOS"] < 2)],
        "2-5 anos":  df_in[(df_in["_ANOS"] >= 2) & (df_in["_ANOS"] < 5)],
        "5-10 anos": df_in[(df_in["_ANOS"] >= 5) & (df_in["_ANOS"] < 10)],
        ">10 anos":  df_in[df_in["_ANOS"] >= 10],
    }
    total = len(df_in)
    linhas = [
        f"Período: {mes_ini.strftime('%b/%y').upper()} → {mes_max.strftime('%b/%y').upper()} | Total analisados: {total}",
        f"Média geral: {anos_m} anos e {meses_m} meses\n",
        "DISTRIBUIÇÃO POR FAIXA:"
    ]
    for faixa, sub in faixas.items():
        pct = round(len(sub) / total * 100, 1) if total > 0 else 0
        linhas.append(f"{faixa}: {len(sub)} ({pct}%)")

    inv = df_in[df_in["INICIATIVA"].str.upper().str.contains("EMPRESA",  na=False)]
    vol = df_in[df_in["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False)]
    med_inv = inv["_ANOS"].mean() if len(inv) > 0 else 0
    med_vol = vol["_ANOS"].mean() if len(vol) > 0 else 0
    linhas += [
        "\nCOMPARATIVO POR INICIATIVA:",
        f"Involuntários ({len(inv)}): média {int(med_inv)} anos e {int((med_inv - int(med_inv)) * 12)} meses",
        f"Voluntários   ({len(vol)}): média {int(med_vol)} anos e {int((med_vol - int(med_vol)) * 12)} meses",
    ]
    return "\n".join(linhas)


# ══════════════════════════════════════════════════════════════
#  INSTRUÇÕES DE FORMATAÇÃO — enviadas ao Gemini junto com dados
# ══════════════════════════════════════════════════════════════

INSTRUCAO_TURNOVER = """
Formate os dados abaixo em uma tabela markdown exatamente neste modelo:

| Métrica | [período anterior] | [período atual] |
|---|---|---|
| HC Médio (12 meses) | X | X |
| Desligamentos Involuntários | X | X |
| Desligamentos Voluntários | X | X |
| Turnover % Involuntário | X% | X% |
| Turnover % Voluntário | X% | X% |
| Turnover % Total | X% | X% |

Substitua [período anterior] e [período atual] pelos intervalos reais dos dados.
Use apenas markdown — sem HTML.
"""

INSTRUCAO_HC_EMPRESA = """
Para cada empresa nos dados, escreva uma linha no formato:
"Temos **X colaboradores** na empresa **NOME**. [▲/▼] **X% YoY** ([mês_yoy]: Y colaboradores)"
Use apenas markdown — sem HTML.
"""

INSTRUCAO_TIPO_CONTRATO = """
Formate em tabela markdown:
| Tipo de Contratação | Qtd Atual | Qtd YoY | Var % |
|---|---|---|---|
(linhas por tipo + linha TOTAL ao final)
Use ▲ para crescimento e ▼ para queda. Apenas markdown — sem HTML.
"""

INSTRUCAO_TOP5 = """
Formate em tabela markdown com ranking:
| # | Área | Headcount | % do Total |
|---|---|---|---|
Use apenas markdown — sem HTML.
"""

INSTRUCAO_SENIORIDADE = """
Formate em tabela markdown:
| Senioridade | Headcount | % |
|---|---|---|
Ordene do menor para o maior nível. Use apenas markdown — sem HTML.
"""

INSTRUCAO_INATIVOS = """
Apresente os dados no formato:
- **Total de desligamentos em [mês]:** X ([▲/▼] vs mês anterior: Y)
- **Involuntários (Iniciativa da Empresa):** X
- **Voluntários (Iniciativa do Empregado):** X
- **TO% do mês:** X%

Use apenas markdown — sem HTML.
"""

INSTRUCAO_TO_MENSAL = """
Formate em tabela markdown:
| Mês/Ano | HC | Inv | Vol | TO% Inv | TO% Vol | TO% Total |
|---|---|---|---|---|---|---|
(uma linha por mês + linha ACUMULADO 12 meses ao final)
Use apenas markdown — sem HTML.
"""

INSTRUCAO_DIVERSIDADE = """
Apresente cada indicador no formato:
**NOME**: X (X%) | MoM: [▲/▼] X% (Y) | YoY: [▲/▼] X% (Z)

Inclua: HEADCOUNT, MASCULINO, FEMININO, PRETOS, PRETOS & PARDOS, PCD, FAIXA +46.
Use apenas markdown — sem HTML.
"""

INSTRUCAO_TEMPO_CASA_AT = """
Apresente:
1. **Média geral:** X anos e X meses
2. Tabela markdown de distribuição por faixa:
| Faixa | Quantidade | % |
|---|---|---|
3. **Top 3 áreas com maior tempo médio de casa**
Use apenas markdown — sem HTML.
"""

INSTRUCAO_TEMPO_CASA_IN = """
Apresente:
1. **Média geral dos desligados:** X anos e X meses
2. Tabela markdown de distribuição por faixa:
| Faixa | Quantidade | % |
|---|---|---|
3. **Comparativo por iniciativa** (Involuntários vs Voluntários — tempo médio de cada grupo)
Use apenas markdown — sem HTML.
"""


# ══════════════════════════════════════════════════════════════
#  DISPATCHER — executa cálculo + formatação para cada botão
# ══════════════════════════════════════════════════════════════

def executar_analise_rapida(tipo: str, df: pd.DataFrame):
    """
    Retorna (resposta_str, figura_plotly_ou_None).
    Para TO% Gráfico, retorna também a figura e a tabela formatada.
    """
    try:
        if tipo == "turnover_yoy":
            dados = calcular_turnover_yoy(df)
            return formatar_com_gemini(dados, INSTRUCAO_TURNOVER), None

        elif tipo == "hc_empresa":
            dados = calcular_headcount_empresa(df)
            return formatar_com_gemini(dados, INSTRUCAO_HC_EMPRESA), None

        elif tipo == "tipo_contrato":
            dados = calcular_tipo_contrato(df)
            return formatar_com_gemini(dados, INSTRUCAO_TIPO_CONTRATO), None

        elif tipo == "top5_areas":
            dados = calcular_top5_areas(df)
            return formatar_com_gemini(dados, INSTRUCAO_TOP5), None

        elif tipo == "senioridade":
            dados = calcular_senioridade(df)
            return formatar_com_gemini(dados, INSTRUCAO_SENIORIDADE), None

        elif tipo == "inativos":
            dados = calcular_inativos(df)
            return formatar_com_gemini(dados, INSTRUCAO_INATIVOS), None

        elif tipo == "to_mensal":
            dados = calcular_to_mensal(df)
            return formatar_com_gemini(dados, INSTRUCAO_TO_MENSAL), None

        elif tipo == "to_grafico":
            fig, df_to = calcular_to_grafico(df)
            # Tabela formatada via Gemini
            linhas = []
            for _, row in df_to.iterrows():
                linhas.append(
                    f"{row['fy']} | {row['mes'].strftime('%b/%Y').upper()} | "
                    f"HC={int(row['hc'])} | Inat={int(row['total'])} | "
                    f"TO%Inv={row['to_inv']}% | TO%Vol={row['to_vol']}% | TO%Tot={row['to_pct']}%"
                )
            tabela_str = formatar_com_gemini(
                "\n".join(linhas),
                "Formate em tabela markdown:\n"
                "| FY | Mês | HC | Inativos | TO% Inv | TO% Vol | TO% Total |\n"
                "|---|---|---|---|---|---|---|\n"
                "Ordene do mais recente para o mais antigo. Use apenas markdown."
            )
            return tabela_str, fig

        elif tipo == "diversidade":
            dados = calcular_diversidade(df)
            return formatar_com_gemini(dados, INSTRUCAO_DIVERSIDADE), None

        elif tipo == "tempo_casa_ativos":
            dados = calcular_tempo_casa_ativos(df)
            return formatar_com_gemini(dados, INSTRUCAO_TEMPO_CASA_AT), None

        elif tipo == "tempo_casa_inativos":
            dados = calcular_tempo_casa_inativos(df)
            return formatar_com_gemini(dados, INSTRUCAO_TEMPO_CASA_IN), None

    except Exception as e:
        erro_str = str(e).lower()
        if any(k in erro_str for k in ("429", "quota", "rate", "resource_exhausted")):
            return (
                "⚠️ **Limite de requisições da API Gemini atingido.**\n\n"
                "Aguarde **1 minuto** e tente novamente.", None
            )
        return f"❌ **Erro:** `{str(e)[:300]}`", None


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
        min-height: 100vh; display: flex !important; align-items: center !important; justify-content: center !important;
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
    div[data-testid="stTextInput"] input { background:rgba(255,255,255,0.05) !important; border:1px solid rgba(255,255,255,0.08) !important; border-radius:10px !important; color:white !important; letter-spacing:3px !important; font-size:15px !important; padding:12px 16px !important; }
    div[data-testid="stTextInput"] input:focus { border-color:rgba(210,45,65,0.5) !important; background:rgba(210,45,65,0.04) !important; box-shadow:none !important; }
    div[data-testid="stTextInput"] label { color:rgba(255,255,255,0.3) !important; font-size:9px !important; font-weight:700 !important; letter-spacing:2px !important; text-transform:uppercase !important; }
    small, .st-emotion-cache-1gulkj5, [data-testid="InputInstructions"], div[class*="InputInstructions"], div[class*="inputInstructions"], div[data-testid="stTextInput"] > div > div > div:last-child { display: none !important; }
    div[data-testid="stFormSubmitButton"] > button { background: rgba(210,45,65,0.35) !important; border: 1px solid rgba(210,45,65,0.55) !important; border-radius:10px !important; color: rgba(255,255,255,0.75) !important; font-size:11px !important; font-weight:700 !important; letter-spacing:1.5px !important; text-transform:uppercase !important; padding:12px !important; width:100% !important; transition:all 0.2s !important; }
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
        senha  = st.text_input("Senha de Acesso", type="password", placeholder="••••••••••")
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


# ── TELA DE CHAT ──────────────────────────────────────────────
def tela_chat(df: pd.DataFrame):

    with st.sidebar:
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
        section[data-testid="stSidebar"] { background: #0d0d0f !important; border-right: 1px solid rgba(255,255,255,0.06) !important; }
        section[data-testid="stSidebar"] * { font-family: 'Poppins', sans-serif !important; color: white !important; }
        button[data-testid="collapsedControl"], section[data-testid="stSidebarCollapseButton"],
        div[data-testid="stSidebarCollapseButton"], button[kind="header"],
        [title="keyboard_double_arrow_left"], [aria-label="keyboard_double_arrow_left"],
        button[title*="keyboard"], span[class*="material"] { display: none !important; }
        section[data-testid="stSidebar"] .stButton button {
            background: rgba(255,255,255,0.04) !important; border: 1px solid rgba(255,255,255,0.08) !important;
            border-radius: 8px !important; color: rgba(255,255,255,0.6) !important;
            font-size: 11px !important; font-weight: 500 !important; text-align: left !important;
            padding: 8px 12px !important; transition: all 0.2s !important;
        }
        section[data-testid="stSidebar"] .stButton button:hover { background: rgba(230,57,70,0.12) !important; border-color: rgba(230,57,70,0.3) !important; color: white !important; }
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

        # ── Filtros ───────────────────────────────────────────
        st.markdown('<div class="sb-section" style="margin-top:4px">Filtros</div>', unsafe_allow_html=True)
        empresas_disponiveis  = sorted(df["EMPRESA"].dropna().unique().tolist()) if "EMPRESA" in df.columns else []
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

        # ── Cards ─────────────────────────────────────────────
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

        # ── Botões de análise rápida ──────────────────────────
        st.markdown("""
        <style>
        div[data-testid="stSidebar"] button[kind="secondary"]:first-of-type {
            background: rgba(230,57,70,0.15) !important;
            border: 1px solid rgba(230,57,70,0.4) !important;
            color: #ff8090 !important; font-weight: 700 !important;
        }
        </style>
        """, unsafe_allow_html=True)

        BOTOES = [
            ("📊 Relatório de Turnover (12m)", "turnover_yoy"),
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

        for label, tipo in BOTOES:
            if st.button(label, use_container_width=True, key=f"btn_{tipo}"):
                st.session_state["analise_rapida"] = tipo

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

    # ── Área principal ────────────────────────────────────────
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
    section[data-testid="stMain"] { background: #0f0f11 !important; }
    section[data-testid="stMain"] > div { background: #0f0f11 !important; }
    section[data-testid="stMain"] * { font-family: 'Poppins', sans-serif !important; }
    div[data-testid="stChatMessage"] { background: #ffffff !important; border: 1px solid rgba(0,0,0,0.06) !important; border-radius: 12px !important; margin-bottom: 12px !important; color: #1a1a1a !important; }
    div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li, div[data-testid="stChatMessage"] span { color: #1a1a1a !important; }
    div[data-testid="stChatMessage"] strong { color: #111111 !important; }
    div[data-testid="stChatInput"] textarea { background: #ffffff !important; border: 1px solid rgba(0,0,0,0.12) !important; border-radius: 12px !important; color: #1a1a1a !important; font-family: 'Poppins', sans-serif !important; font-size: 13px !important; }
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
            if msg.get("tipo") == "plotly":
                import plotly.io as pio
                st.plotly_chart(pio.from_json(msg["fig_json"]), use_container_width=True)
                if msg.get("content"):
                    st.markdown(msg["content"])
            else:
                st.markdown(msg["content"])

    # ── Análise rápida (botão sidebar) ────────────────────────
    analise_tipo = st.session_state.pop("analise_rapida", None)
    if analise_tipo:
        label_map = {b[1]: b[0] for b in [
            ("📊 Relatório de Turnover (12m)", "turnover_yoy"),
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
        ]}
        pergunta_label = label_map.get(analise_tipo, analise_tipo)

        st.session_state["mensagens"].append({"role": "user", "content": pergunta_label})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(pergunta_label)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Calculando e formatando..."):
                resposta, fig = executar_analise_rapida(analise_tipo, df)

            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)
                st.markdown(resposta)
                import plotly.io as pio
                st.session_state["mensagens"].append({
                    "role": "assistant", "tipo": "plotly",
                    "fig_json": pio.to_json(fig), "content": resposta
                })
            else:
                st.markdown(resposta)
                st.session_state["mensagens"].append({"role": "assistant", "content": resposta})

        st.session_state["historico"].append({"role": "user",      "content": pergunta_label})
        st.session_state["historico"].append({"role": "assistant", "content": resposta})
        if len(st.session_state["historico"]) > 20:
            st.session_state["historico"] = st.session_state["historico"][-20:]

    # ── Pergunta livre (chat input) ───────────────────────────
    pergunta = st.chat_input("Ex.: Quantos colaboradores ativos temos por área?")
    if pergunta:
        st.session_state["mensagens"].append({"role": "user", "content": pergunta})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(pergunta)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Analisando dados..."):
                empresas_ativas = df["EMPRESA"].dropna().unique().tolist() if "EMPRESA" in df.columns else []
                contexto = (
                    f"Empresas no df: {sorted(empresas_ativas)} | "
                    f"Total: {len(df)} | Ativos: {len(df[df['STATUS_TIPO']=='ATIVO'])} | "
                    f"Inativos: {len(df[df['STATUS_TIPO']=='INATIVO'])} | "
                    f"Mês ref: {mes_ref_label}"
                )
                try:
                    resposta = rodar_agente_livre(
                        pergunta  = pergunta,
                        historico = st.session_state.get("historico", []),
                        df        = df,
                        contexto  = contexto
                    )
                except Exception as e:
                    erro_str = str(e).lower()
                    if any(k in erro_str for k in ("429", "quota", "rate", "resource_exhausted")):
                        resposta = "⚠️ **Limite da API Gemini atingido.** Aguarde 1 minuto e tente novamente."
                    else:
                        resposta = f"❌ **Erro:** `{str(e)[:300]}`"

            if isinstance(resposta, str) and resposta.startswith("__PLOTLY__:"):
                import plotly.io as pio
                fig = pio.from_json(resposta.replace("__PLOTLY__:", ""))
                st.plotly_chart(fig, use_container_width=True)
                resposta_hist = "📉 *Gráfico gerado.*"
            else:
                st.markdown(resposta)
                resposta_hist = resposta

        st.session_state["mensagens"].append({"role": "assistant", "content": resposta_hist})
        st.session_state["historico"].append({"role": "user",      "content": pergunta})
        st.session_state["historico"].append({"role": "assistant", "content": resposta_hist})
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
