# =============================================================
#  AGENTE ANALÍTICO DE HR — Webmotors
#  v2.1 — Fix RateLimitError + Gráficos nativos no Streamlit
#
#  Mudanças v2.1:
#  - TO% Gráfico: calculado 100% em Python/Streamlit — ZERO tokens de API
#    → sem RateLimitError, sem dependência de Plotly, gráfico sempre funciona
#  - Diversidade: cards visuais gerados em Python nativo (sem API)
#  - rodar_agente(): max_tokens por tipo de análise (leve=2048, médio=4096)
#  - Botões especiais (TO% Gráfico, Diversidade) chamam funções Python diretas
#    e só usam o agente para o texto de análise (sem HTML na resposta do LLM)
#  - FY australiano corrigido (inclui FY27)
# =============================================================

import os
import hashlib
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
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

PARQUET_URL = (
    "https://raw.githubusercontent.com/gustavowebmotors13-jpg/"
    "hr-analytics-agente/main/Headcount_Consolidado.parquet"
)

APP_PASSWORD_HASH = st.secrets.get(
    "APP_PASSWORD_HASH",
    hashlib.md5("demo123".encode()).hexdigest()
)

ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))


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
        return str(resultado)
    except Exception as e:
        return f"ERRO: {e}"


# ── SYSTEM PROMPT ─────────────────────────────────────────────
SYSTEM_PROMPT = """Você é um assistente especializado em análise de dados de RH da Webmotors.

Você tem acesso ao dataframe 'df' com dados de colaboradores ATIVOS e INATIVOS.

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
- FY: FY27, FY26, FY25, FY24, FY23, FY22, OTHERS
- DATA_EXTRACAO: timestamp da última execução do ETL
- +46: "SIM" ou "NÃO" (colaboradores com 46+ anos)
- AGRUPAMENTO IDADE: faixas de idade
- PCD: "SIM" ou "NÃO"

FY AUSTRALIANO (Jul → Jun):
- FY27: 01/07/2026 a 30/06/2027
- FY26: 01/07/2025 a 30/06/2026
- FY25: 01/07/2024 a 30/06/2025
- FY24: 01/07/2023 a 30/06/2024
- FY23: 01/07/2022 a 30/06/2023
- FY22: 01/07/2021 a 30/06/2022

REGRAS GERAIS:
1. Consulte o schema antes de qualquer consulta.
2. Responda em português brasileiro.
3. Para filtros de texto, use .str.upper().str.contains() — nunca == com texto fixo para INICIATIVA.
4. Salve sempre o resultado final em 'resultado'.
5. Para ativos: df[df['STATUS_TIPO'] == 'ATIVO']
6. Para inativos: df[df['STATUS_TIPO'] == 'INATIVO']
7. NUNCA use tags HTML nas respostas de texto — use apenas markdown puro.
8. Nunca invente dados — se não souber, diga claramente.

REGRA ESPECIAL — GRÁFICOS VIA HTML:
Quando precisar gerar um gráfico, NÃO use Plotly nem matplotlib.
Em vez disso, gere um bloco HTML usando Chart.js com este formato EXATO:

__HTML__
<!DOCTYPE html>
<html>
<head>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
  body { margin: 0; padding: 12px; background: #111; font-family: Poppins, sans-serif; }
  canvas { max-width: 100%; }
</style>
</head>
<body>
<div style="position:relative;height:380px;">
  <canvas id="grafico"></canvas>
</div>
<script>
  // SEU CÓDIGO Chart.js AQUI
  // Use fundo #111, cores da WM (#C0003C), fonte Poppins
  // Paleta: linha principal #C0003C, involuntário #ff6b6b, voluntário #ffa94d
  new Chart(document.getElementById('grafico'), {
    type: 'line', // ou 'bar'
    data: { ... },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: '#fff', font: { family: 'Poppins', size: 11 } } } },
      scales: {
        x: { ticks: { color: '#aaa', font: { size: 11 } }, grid: { color: 'rgba(255,255,255,0.06)' } },
        y: { ticks: { color: '#aaa', font: { size: 11 }, callback: v => v + '%' }, grid: { color: 'rgba(255,255,255,0.08)' } }
      }
    }
  });
</script>
</body>
</html>
__END_HTML__

REGRA ESPECIAL — CARDS VISUAIS DE DIVERSIDADE:
Quando o usuário pedir análise de Diversidade, gere cards HTML com este formato EXATO:

__HTML__
<!DOCTYPE html>
<html>
<head>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: Poppins, sans-serif; background: #0f0f11; padding: 16px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
  .card { background: #1a1a1f; border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 14px 12px; }
  .card-label { font-size: 9px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: rgba(255,255,255,0.4); margin-bottom: 2px; }
  .card-pct { font-size: 11px; font-weight: 600; color: rgba(255,255,255,0.35); margin-bottom: 4px; }
  .card-value { font-size: 32px; font-weight: 800; color: #fff; line-height: 1; margin-bottom: 10px; }
  .card-divider { height: 1px; background: rgba(255,255,255,0.07); margin-bottom: 8px; }
  .card-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
  .card-period { font-size: 9px; color: rgba(255,255,255,0.3); letter-spacing: 0.5px; }
  .card-delta { font-size: 11px; font-weight: 600; }
  .card-delta.up { color: #51cf66; }
  .card-delta.down { color: #ff6b6b; }
  .card-delta.neutral { color: rgba(255,255,255,0.4); }
  .card-sub { font-size: 9px; color: rgba(255,255,255,0.25); }
  .accent-line { height: 2px; border-radius: 2px; margin-bottom: 10px; }
</style>
</head>
<body>
<div class="grid">
  <!-- REPITA ESTE BLOCO POR CADA MÉTRICA -->
  <div class="card">
    <div class="card-label">HEADCOUNT</div>
    <div class="card-pct"></div>
    <div class="accent-line" style="background:#C0003C;width:100%"></div>
    <div class="card-value">546</div>
    <div class="card-divider"></div>
    <div class="card-row">
      <span class="card-period">Vs. Mês</span>
      <span class="card-delta down">▼ 0,5% (-3)</span>
    </div>
    <div class="card-row">
      <span class="card-period">Vs. Ano</span>
      <span class="card-delta up">▲ 5,6% (+29)</span>
    </div>
  </div>
  <!-- ... mais cards ... -->
</div>
</body>
</html>
__END_HTML__

IMPORTANTE: Sempre que usar __HTML__...__END_HTML__, o conteúdo HTML completo deve estar entre essas tags. O texto de análise pode vir antes ou depois do bloco HTML em markdown normal.
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
            "NUNCA importe plotly ou matplotlib aqui — apenas pandas e operações de dados. "
            "Para gráficos, retorne os dados processados em 'resultado' e gere o HTML Chart.js na resposta final."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "codigo": {
                    "type": "string",
                    "description": "Código Python/pandas válido com o resultado em 'resultado'. SEM imports de plotly/matplotlib."
                }
            },
            "required": ["codigo"]
        }
    }
]


# ── RENDER HTML BLOCKS ────────────────────────────────────────
def render_resposta(resposta: str):
    """
    Processa a resposta do agente.
    Blocos __HTML__...__END_HTML__ são renderizados via st.components.v1.html.
    O restante é renderizado como markdown normal.
    """
    import re
    partes = re.split(r'(__HTML__.*?__END_HTML__)', resposta, flags=re.DOTALL)

    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue

        if parte.startswith('__HTML__') and parte.endswith('__END_HTML__'):
            html_content = parte[len('__HTML__'):].rstrip('__END_HTML__').strip()
            # Remove __END_HTML__ do final de forma segura
            if '__END_HTML__' in html_content:
                html_content = html_content[:html_content.rfind('__END_HTML__')].strip()
            # Altura dinâmica: cards de diversidade menores, gráficos maiores
            altura = 220 if 'grid' in html_content and 'card' in html_content else 420
            components.html(html_content, height=altura, scrolling=False)
        else:
            # Remove __END_HTML__ orphan se sobrar
            parte_limpa = parte.replace('__END_HTML__', '').strip()
            if parte_limpa:
                st.markdown(parte_limpa)


def rodar_agente(pergunta: str, historico: list, df: pd.DataFrame,
                 contexto_filtros: str = "", max_tokens: int = 4096) -> str:
    """
    max_tokens guide:
      - Análises simples (headcount, top5, tipo contrato): 2048
      - Análises médias (turnover 12m, inativos, diversidade texto): 3072
      - Análises longas (tabela mensal 24m): 4096
      - NUNCA pedir HTML/gráficos via agente → usar funções Python nativas
    """
    client    = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    mensagens = historico + [{"role": "user", "content": pergunta}]

    system_com_contexto = SYSTEM_PROMPT
    if contexto_filtros:
        system_com_contexto = SYSTEM_PROMPT + "\n" + contexto_filtros

    while True:
        resposta = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system_com_contexto,
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


# ══════════════════════════════════════════════════════════════
#  FUNÇÕES NATIVAS — Gráfico TO% e Cards Diversidade
#  Calculadas 100% em Python/Streamlit, sem consumir tokens de API
# ══════════════════════════════════════════════════════════════

def calcular_dados_turnover(df: pd.DataFrame, n_meses: int = 24) -> list:
    """Retorna lista de dicts com dados mensais de turnover."""
    df2 = df.copy()
    df2["_D"] = pd.to_datetime(df2["DATA"], dayfirst=True, errors="coerce")
    mes_max = df2[df2["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    if pd.isna(mes_max):
        return []
    mes_ini = mes_max - pd.DateOffset(months=n_meses - 1)
    meses   = pd.date_range(start=mes_ini.replace(day=1), end=mes_max, freq="MS")
    dados   = []
    for mes in meses:
        at   = df2[(df2["STATUS_TIPO"] == "ATIVO")   & (df2["_D"] == mes)]
        inat = df2[(df2["STATUS_TIPO"] == "INATIVO") & (df2["_D"] == mes)]
        hc   = len(at)
        if hc == 0:
            continue
        inv     = int(inat["INICIATIVA"].str.upper().str.contains("EMPRESA",  na=False).sum())
        vol     = int(inat["INICIATIVA"].str.upper().str.contains("EMPREGADO", na=False).sum())
        total_d = inv + vol
        fy_vals = df2[df2["_D"] == mes]["FY"]
        fy      = fy_vals.iloc[0] if len(fy_vals) > 0 else ""
        dados.append({
            "mes":     mes.strftime("%b/%y").upper(),
            "mes_dt":  mes,
            "hc":      hc,
            "inv":     inv,
            "vol":     vol,
            "total":   total_d,
            "to_pct":  round(total_d / hc * 100, 1),
            "to_inv":  round(inv     / hc * 100, 1),
            "to_vol":  round(vol     / hc * 100, 1),
            "fy":      fy,
        })
    return dados


def render_grafico_turnover(df: pd.DataFrame):
    """Renderiza gráfico de TO% mensal (barras Inv/Vol + linha TO% Total) via Chart.js."""
    dados = calcular_dados_turnover(df, n_meses=24)
    if not dados:
        st.warning("Sem dados suficientes para o gráfico.")
        return

    labels  = [d["mes"]    for d in dados]
    inv_d   = [d["inv"]    for d in dados]
    vol_d   = [d["vol"]    for d in dados]
    to_pct  = [d["to_pct"] for d in dados]
    to_inv  = [d["to_inv"] for d in dados]
    to_vol  = [d["to_vol"] for d in dados]
    fy_list = [d["fy"]     for d in dados]

    import json
    labels_js  = json.dumps(labels)
    inv_js     = json.dumps(inv_d)
    vol_js     = json.dumps(vol_d)
    topct_js   = json.dumps(to_pct)
    to_inv_js  = json.dumps(to_inv)
    to_vol_js  = json.dumps(to_vol)
    fy_js      = json.dumps(fy_list)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #111; font-family: Poppins, sans-serif; padding: 12px 16px 8px; }}
  .title {{ color: #fff; font-size: 13px; font-weight: 700; letter-spacing: 0.5px;
            margin-bottom: 10px; text-transform: uppercase; }}
  .legend {{ display: flex; gap: 18px; margin-bottom: 12px; flex-wrap: wrap; }}
  .leg-item {{ display: flex; align-items: center; gap: 5px; font-size: 10px;
               color: rgba(255,255,255,0.55); letter-spacing: 0.3px; }}
  .leg-dot {{ width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }}
  canvas {{ max-width: 100%; }}
</style>
</head>
<body>
<div class="title">Turnover Mensal — Últimos 24 meses</div>
<div class="legend">
  <div class="leg-item"><div class="leg-dot" style="background:#ff6b6b"></div>Involuntário (qtd)</div>
  <div class="leg-item"><div class="leg-dot" style="background:#ffa94d"></div>Voluntário (qtd)</div>
  <div class="leg-item"><div class="leg-dot" style="background:#fff;border-radius:50%"></div>TO% Total</div>
</div>
<div style="position:relative;height:340px;">
  <canvas id="g"></canvas>
</div>
<script>
const labels  = {labels_js};
const invData = {inv_js};
const volData = {vol_js};
const toData  = {topct_js};
const toInv   = {to_inv_js};
const toVol   = {to_vol_js};
const fyData  = {fy_js};

new Chart(document.getElementById('g'), {{
  data: {{
    labels,
    datasets: [
      {{
        type: 'bar',
        label: 'Involuntário',
        data: invData,
        backgroundColor: 'rgba(255,107,107,0.80)',
        borderRadius: 3,
        yAxisID: 'yQtd',
        order: 2,
      }},
      {{
        type: 'bar',
        label: 'Voluntário',
        data: volData,
        backgroundColor: 'rgba(255,169,77,0.80)',
        borderRadius: 3,
        yAxisID: 'yQtd',
        order: 2,
      }},
      {{
        type: 'line',
        label: 'TO% Total',
        data: toData,
        borderColor: '#ffffff',
        backgroundColor: 'rgba(255,255,255,0.08)',
        borderWidth: 2.5,
        borderDash: [5,3],
        pointBackgroundColor: '#C0003C',
        pointBorderColor: '#fff',
        pointBorderWidth: 1.5,
        pointRadius: 5,
        pointHoverRadius: 7,
        fill: false,
        yAxisID: 'yPct',
        order: 1,
        datalabels: {{ display: false }},
      }}
    ]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    interaction: {{ mode: 'index', intersect: false }},
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        backgroundColor: '#1a1a1f',
        borderColor: 'rgba(255,255,255,0.1)',
        borderWidth: 1,
        titleColor: '#fff',
        bodyColor: 'rgba(255,255,255,0.7)',
        padding: 10,
        callbacks: {{
          title: ctx => ctx[0].label + '  ·  ' + fyData[ctx[0].dataIndex],
          afterBody: ctx => {{
            const i = ctx[0].dataIndex;
            return [
              'Inv: ' + invData[i] + ' (' + toInv[i] + '%)',
              'Vol: ' + volData[i] + ' (' + toVol[i] + '%)',
              'TO% Total: ' + toData[i] + '%',
            ];
          }},
          label: () => null,
        }}
      }}
    }},
    scales: {{
      x: {{
        ticks: {{ color: 'rgba(255,255,255,0.45)', font: {{ size: 10, family: 'Poppins' }}, maxRotation: 45 }},
        grid:  {{ color: 'rgba(255,255,255,0.04)' }},
      }},
      yQtd: {{
        position: 'left',
        title: {{ display: true, text: 'Desligamentos', color: 'rgba(255,255,255,0.3)', font: {{ size: 10 }} }},
        ticks: {{ color: 'rgba(255,255,255,0.4)', font: {{ size: 10 }} }},
        grid:  {{ color: 'rgba(255,255,255,0.06)' }},
        beginAtZero: true,
      }},
      yPct: {{
        position: 'right',
        title: {{ display: true, text: 'TO%', color: 'rgba(255,255,255,0.3)', font: {{ size: 10 }} }},
        ticks: {{ color: 'rgba(255,255,255,0.4)', font: {{ size: 10 }},
                  callback: v => v.toFixed(1) + '%' }},
        grid:  {{ drawOnChartArea: false }},
        beginAtZero: true,
      }}
    }}
  }}
}});
</script>
</body>
</html>"""

    components.html(html, height=440, scrolling=False)

    # Tabela markdown abaixo do gráfico
    linhas = ["| FY | Mês | HC | Inv | Vol | TO% Inv | TO% Vol | TO% Total |",
              "|---|---|---|---|---|---|---|---|"]
    for d in reversed(dados):
        linhas.append(
            f"| {d['fy']} | {d['mes']} | {d['hc']} | {d['inv']} | {d['vol']} "
            f"| {d['to_inv']}% | {d['to_vol']}% | {d['to_pct']}% |"
        )
    st.markdown("\n".join(linhas))


def render_cards_diversidade(df: pd.DataFrame):
    """Renderiza cards visuais de diversidade — 100% Python, zero tokens de API."""
    df2 = df.copy()
    df2["_D"] = pd.to_datetime(df2["DATA"], dayfirst=True, errors="coerce")
    mes_ref = df2[df2["STATUS_TIPO"] == "ATIVO"]["_D"].max()
    if pd.isna(mes_ref):
        st.warning("Sem dados de ativos.")
        return

    mes_mom = mes_ref - pd.DateOffset(months=1)
    mes_yoy = mes_ref - pd.DateOffset(years=1)

    def _stats(mes):
        b = df2[(df2["STATUS_TIPO"] == "ATIVO") & (df2["_D"] == mes)]
        t = len(b)
        return {
            "total": t,
            "masc":  int(b["GENERO"].str.upper().str.contains("MASCULINO", na=False).sum()),
            "fem":   int(b["GENERO"].str.upper().str.contains("FEMININO",  na=False).sum()),
            "pret":  int(b["ETNIA"].str.upper().str.contains("PRETO", na=False).sum()),
            "pp":    int(b["ETNIA"].str.upper().str.contains("PRETO|PARDO", na=False).sum()),
            "pcd":   int(b["PCD"].str.upper().str.contains("SIM", na=False).sum()) if "PCD" in b.columns else 0,
            "f46":   int(b["+46"].str.upper().str.contains("SIM", na=False).sum()) if "+46" in b.columns else 0,
        }

    cur = _stats(mes_ref)
    mom = _stats(mes_mom)
    yoy = _stats(mes_yoy)

    lbl_ref = mes_ref.strftime("%b/%y").upper()
    lbl_mom = mes_mom.strftime("%b/%y").upper()
    lbl_yoy = mes_yoy.strftime("%b/%y").upper()

    def _pct(num, den):
        return f"{round(num / den * 100, 1)}%" if den > 0 else "—"

    def _delta(cur_v, cmp_v, label):
        diff = cur_v - cmp_v
        pct  = round(diff / cmp_v * 100, 1) if cmp_v > 0 else 0
        sign = "▲" if diff > 0 else ("▼" if diff < 0 else "—")
        cls  = "up" if diff > 0 else ("down" if diff < 0 else "neutral")
        txt  = f"{sign} {abs(pct)}% ({'+' if diff>0 else ''}{diff})"
        return f'<div class="card-row"><span class="lbl">{label}</span><span class="delta {cls}">{txt}</span></div>'

    metricas = [
        ("HEADCOUNT", "",       "#C0003C", "total", "total"),
        ("MASCULINO", "masc",   "#4dabf7", "masc",  "total"),
        ("FEMININO",  "fem",    "#f783ac", "fem",   "total"),
        ("PRETOS",    "pret",   "#ffa94d", "pret",  "total"),
        ("P&P",       "pp",     "#ffa94d", "pp",    "total"),
        ("PCD",       "pcd",    "#69db7c", "pcd",   "total"),
        ("FAIXA +46", "f46",    "#da77f2", "f46",   "total"),
    ]

    cards_html = ""
    for nome, pct_key, cor, key, den_key in metricas:
        val   = cur[key]
        pct_s = _pct(cur[pct_key], cur[den_key]) if pct_key else ""
        d_mom = _delta(val, mom[key], f"Vs. {lbl_mom}")
        d_yoy = _delta(val, yoy[key], f"Vs. {lbl_yoy}")
        cards_html += f"""
        <div class="card">
          <div class="card-label">{nome}</div>
          <div class="accent" style="background:{cor}"></div>
          <div class="card-pct">{pct_s}</div>
          <div class="card-value">{val}</div>
          <div class="divider"></div>
          {d_mom}
          {d_yoy}
        </div>"""

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap');
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: #0f0f11; font-family: Poppins, sans-serif; padding: 4px 4px 8px; }}
.ref {{ font-size: 10px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase;
        color: rgba(255,255,255,0.3); margin-bottom: 10px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; }}
.card {{ background: #1a1a1f; border: 1px solid rgba(255,255,255,0.07);
         border-radius: 12px; padding: 12px 12px 10px; }}
.card-label {{ font-size: 9px; font-weight: 700; letter-spacing: 1.8px;
               text-transform: uppercase; color: rgba(255,255,255,0.35); margin-bottom: 6px; }}
.accent {{ height: 2px; border-radius: 2px; margin-bottom: 6px; }}
.card-pct {{ font-size: 11px; font-weight: 600; color: rgba(255,255,255,0.3);
             min-height: 16px; margin-bottom: 2px; }}
.card-value {{ font-size: 30px; font-weight: 800; color: #fff;
               line-height: 1; margin-bottom: 10px; }}
.divider {{ height: 1px; background: rgba(255,255,255,0.06); margin-bottom: 8px; }}
.card-row {{ display: flex; justify-content: space-between; align-items: center;
             margin-bottom: 4px; }}
.lbl {{ font-size: 9px; color: rgba(255,255,255,0.25); letter-spacing: 0.3px; }}
.delta {{ font-size: 10px; font-weight: 600; }}
.delta.up   {{ color: #51cf66; }}
.delta.down {{ color: #ff6b6b; }}
.delta.neutral {{ color: rgba(255,255,255,0.35); }}
</style>
</head>
<body>
<div class="ref">Referência: {lbl_ref} &nbsp;|&nbsp; MoM: {lbl_mom} &nbsp;|&nbsp; YoY: {lbl_yoy}</div>
<div class="grid">{cards_html}</div>
</body>
</html>"""

    components.html(html, height=260, scrolling=False)


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
    small, [data-testid="InputInstructions"], div[class*="InputInstructions"] { display: none !important; }
    div[data-testid="stFormSubmitButton"] > button {
        background: rgba(210,45,65,0.35) !important;
        border: 1px solid rgba(210,45,65,0.55) !important;
        border-radius:10px !important;
        color: rgba(255,255,255,0.75) !important;
        font-size:11px !important; font-weight:700 !important;
        letter-spacing:1.5px !important; text-transform:uppercase !important;
        padding:12px !important; width:100% !important;
    }
    div[data-testid="stFormSubmitButton"] > button:hover {
        background: #c8253f !important; border-color: #c8253f !important; color: white !important;
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


# ── TELA CHAT ─────────────────────────────────────────────────
def tela_chat(df: pd.DataFrame):

    with st.sidebar:
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
        section[data-testid="stSidebar"] {
            background: #0d0d0f !important;
            border-right: 1px solid rgba(255,255,255,0.06) !important;
        }
        section[data-testid="stSidebar"] * { font-family: 'Poppins', sans-serif !important; color: white !important; }
        button[data-testid="collapsedControl"],
        section[data-testid="stSidebarCollapseButton"],
        div[data-testid="stSidebarCollapseButton"],
        button[kind="header"],
        [title="keyboard_double_arrow_left"],
        [aria-label="keyboard_double_arrow_left"] { display: none !important; }
        section[data-testid="stSidebar"] .stButton button {
            background: rgba(255,255,255,0.04) !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            border-radius: 8px !important;
            color: rgba(255,255,255,0.6) !important;
            font-size: 11px !important;
            font-weight: 500 !important;
            text-align: left !important;
            padding: 8px 12px !important;
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

        # ── FILTROS ───────────────────────────────────────────
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

        # ── CARDS DO SIDEBAR ──────────────────────────────────
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

        # ── PROMPTS ───────────────────────────────────────────

        # --- Turnover Relatório 12m ---
        PROMPT_TURNOVER = """Calcule o relatório de Turnover com comparativo YoY (ano anterior vs ano atual).

Passos:
1. df['_DATA_DT'] = pd.to_datetime(df['DATA'], dayfirst=True, errors='coerce')
2. mes_max = df[df['STATUS_TIPO']=='ATIVO']['_DATA_DT'].max()
3. Período ATUAL: últimos 12 meses até mes_max
4. Período ANTERIOR: 12 meses antes do período atual
5. Para cada período calcule: HC Médio, Involuntários (INICIATIVA contém 'EMPRESA'), Voluntários (INICIATIVA contém 'EMPREGADO')
6. TO% = (desligamentos / HC Médio) * 100 — 1 casa decimal

Apresente tabela markdown:
| Métrica | Período Anterior | Período Atual |
|---|---|---|
Use apenas markdown — sem HTML."""

        # --- TO% Gráfico — gerado por função Python nativa (sem API) ---
        # --- Diversidade — gerado por função Python nativa (sem API) ---

        PROMPTS = {
            "🏢 Headcount por Empresa": """Analise o headcount atual das empresas no dataframe filtrado.
1. df['_D'] = pd.to_datetime(df['DATA'], dayfirst=True, errors='coerce')
2. mes_ref = df[df['STATUS_TIPO']=='ATIVO']['_D'].max()
3. df_ref = df[(df['STATUS_TIPO']=='ATIVO') & (df['_D']==mes_ref)]
4. HC atual por empresa e variação YoY
Apresente em markdown com variação % YoY para cada empresa. Sem HTML.""",

            "📋 Tipo de Contrato": """Distribua os ATIVOS por tipo de contratação no mês mais recente com comparativo YoY.
Use tabela markdown com: Tipo | Qtd Atual | Qtd YoY | Var %. Sem HTML.""",

            "🏆 Top 5 Áreas": """Liste as 5 áreas com maior headcount de ATIVOS no mês mais recente.
Tabela markdown com ranking, headcount e % do total. Sem HTML.""",

            "📊 Headcount por Senioridade": """Distribua ATIVOS por SENIORIDADE no mês mais recente.
Tabela markdown ordenada pelo número do nível, com headcount e %. Sem HTML.""",

            "🚪 Inativos do Mês": """Analise os desligamentos do mês mais recente.
Total, por iniciativa (Empresa vs Empregado), comparativo MoM. Sem HTML.""",

            "📈 TO% Mensal (Tabela)": """Calcule o Turnover mensal dos últimos 12 meses.
Tabela markdown: Mês/Ano | HC | Inv | Vol | TO% Inv | TO% Vol | TO% Total
Adicione linha de ACUMULADO. Sem HTML.""",

            "⏱️ Tempo de Casa (Ativos)": """Calcule o tempo médio de casa dos ATIVOS.
Média geral em anos e meses, distribuição por faixa (<1, 1-2, 2-5, 5-10, >10 anos), Top 3 áreas. Sem HTML.""",

            "⏱️ Tempo de Casa (Inativos)": """Calcule o tempo médio de casa dos inativos dos últimos 12 meses.
Média geral, distribuição por faixa, comparativo Involuntários vs Voluntários. Sem HTML.""",
        }

        # Botão especial de Turnover 12m
        if st.button("📊 Relatório de Turnover (12m)", use_container_width=True, key="btn_turnover"):
            st.session_state["pergunta_rapida"] = PROMPT_TURNOVER

        st.markdown('<div style="margin-bottom:4px"></div>', unsafe_allow_html=True)

        # Botão TO% Gráfico — chama função nativa Python (zero tokens de API para o gráfico)
        if st.button("📈 TO% Gráfico + Tabela", use_container_width=True, key="btn_to_grafico"):
            st.session_state["acao_nativa"] = "grafico_turnover"

        # Botão Diversidade — chama função nativa Python (zero tokens de API para os cards)
        if st.button("🌈 Diversidade (Cards Visuais)", use_container_width=True, key="btn_diversidade"):
            st.session_state["acao_nativa"] = "diversidade"

        st.markdown('<div style="margin-bottom:4px"></div>', unsafe_allow_html=True)

        for label, prompt in PROMPTS.items():
            if st.button(label, use_container_width=True, key=f"btn_{label[:20]}"):
                st.session_state["pergunta_rapida"] = prompt

        st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

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

    # ── ÁREA PRINCIPAL ────────────────────────────────────────
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
    section[data-testid="stMain"] { background: #0f0f11 !important; }
    section[data-testid="stMain"] > div { background: #0f0f11 !important; }
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
    section[data-testid="stMain"] * { font-family: 'Poppins', sans-serif !important; }
    div[data-testid="stChatInput"] textarea {
        background: #ffffff !important;
        border: 1px solid rgba(0,0,0,0.12) !important;
        border-radius: 12px !important;
        color: #1a1a1a !important;
        font-family: 'Poppins', sans-serif !important;
        font-size: 13px !important;
    }
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

    # ── CONTEXTO DOS FILTROS (compartilhado entre nativo e agente) ─
    empresas_ativas = df["EMPRESA"].dropna().unique().tolist() if "EMPRESA" in df.columns else []
    ativos_atual    = len(df[df["STATUS_TIPO"] == "ATIVO"])   if "STATUS_TIPO" in df.columns else 0
    inativos_atual  = len(df[df["STATUS_TIPO"] == "INATIVO"]) if "STATUS_TIPO" in df.columns else 0
    contexto_filtros = f"""
CONTEXTO DO DATAFRAME (após filtros ativos):
- Empresas: {sorted(empresas_ativas)}
- Total registros: {len(df)}
- Ativos: {ativos_atual}
- Inativos: {inativos_atual}
- Mês referência: {mes_ref_label}
Use estes números como referência principal para headcount atual.
"""

    # Renderiza histórico
    for msg in st.session_state.get("mensagens", []):
        avatar = "🧑" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar):
            if msg["role"] == "assistant":
                render_resposta(msg["content"])
            else:
                st.markdown(msg["content"])

    # ── AÇÕES NATIVAS (gráfico TO% e diversidade) ─────────────
    # Chamadas diretas ao Python — sem consumir tokens de API
    acao = st.session_state.pop("acao_nativa", None)
    if acao == "grafico_turnover":
        with st.chat_message("user", avatar="🧑"):
            st.markdown("📈 **TO% Gráfico + Tabela** — últimos 24 meses")
        with st.chat_message("assistant", avatar="🤖"):
            render_grafico_turnover(df)
        st.session_state["mensagens"].append({"role": "user",      "content": "📈 TO% Gráfico + Tabela"})
        st.session_state["mensagens"].append({"role": "assistant", "content": "[gráfico de turnover gerado]"})

    elif acao == "diversidade":
        with st.chat_message("user", avatar="🧑"):
            st.markdown("🌈 **Diversidade (Cards Visuais)**")
        with st.chat_message("assistant", avatar="🤖"):
            render_cards_diversidade(df)
            # Análise textual dos insights com tokens limitados
            with st.spinner("Gerando insights..."):
                prompt_insights = """Com base nos dados de diversidade dos ATIVOS, gere 4-5 bullets de insights
executivos em markdown, cobrindo: gênero, raça/etnia, PCD e faixa etária +46.
Seja direto e objetivo. Máximo 150 palavras. Sem HTML."""
                insights = rodar_agente(
                    pergunta=prompt_insights,
                    historico=[],
                    df=df,
                    contexto_filtros=contexto_filtros,
                    max_tokens=1024
                )
                st.markdown(insights)
        st.session_state["mensagens"].append({"role": "user",      "content": "🌈 Diversidade (Cards Visuais)"})
        st.session_state["mensagens"].append({"role": "assistant", "content": "[cards de diversidade gerados]"})

    # ── CHAT NORMAL ───────────────────────────────────────────
    # max_tokens por tipo de pergunta — evita RateLimitError
    MAX_TOKENS_MAP = {
        "top 5":          2048,
        "top5":           2048,
        "headcount":      2048,
        "empresa":        2048,
        "contrato":       2048,
        "senioridade":    2048,
        "inativos":       2048,
        "tempo de casa":  2048,
        "turnover":       3072,
        "tabela":         3072,
        "diversidade":    2048,
        "grafico":        2048,
        "gráfico":        2048,
    }

    def _max_tokens_para(pergunta: str) -> int:
        p = pergunta.lower()
        for kw, tks in MAX_TOKENS_MAP.items():
            if kw in p:
                return tks
        return 3072  # default seguro

    pergunta_rapida = st.session_state.pop("pergunta_rapida", None)
    pergunta = st.chat_input("Ex.: Quantos colaboradores ativos temos por área?") or pergunta_rapida

    if pergunta:
        st.session_state["mensagens"].append({"role": "user", "content": pergunta})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(pergunta)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Analisando dados..."):
                resposta = rodar_agente(
                    pergunta         = pergunta,
                    historico        = st.session_state.get("historico", []),
                    df               = df,
                    contexto_filtros = contexto_filtros,
                    max_tokens       = _max_tokens_para(pergunta),
                )
            render_resposta(resposta)

        import re as _re
        resposta_limpa = _re.sub(r'__HTML__.*?__END_HTML__', '[visual gerado]', resposta, flags=_re.DOTALL)
        st.session_state["mensagens"].append({"role": "assistant", "content": resposta})
        st.session_state["historico"].append({"role": "user",      "content": pergunta})
        st.session_state["historico"].append({"role": "assistant", "content": resposta_limpa})

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
        st.info("Verifique se o Parquet foi enviado ao GitHub e se o GITHUB_TOKEN está configurado.")
        return

    tela_chat(df)


if __name__ == "__main__":
    main()
