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
    @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500&display=swap');
    section[data-testid="stMain"] { background: #f7f6f2; }
    .bloco-login {
        max-width: 400px;
        margin: 80px auto 0;
        background: #ffffff;
        border: 1px solid #e8e6df;
        border-radius: 16px;
        padding: 40px 36px 36px;
    }
    .login-logo {
        font-family: 'DM Serif Display', serif;
        font-size: 1.7rem;
        color: #1a1a2e;
        margin-bottom: 2px;
    }
    .login-sub {
        font-family: 'DM Sans', sans-serif;
        font-size: 0.85rem;
        color: #888;
        margin-bottom: 28px;
    }
    </style>
    """, unsafe_allow_html=True)

    col = st.columns([1, 2, 1])[1]
    with col:
        st.markdown('<div class="bloco-login">', unsafe_allow_html=True)
        st.markdown('<div class="login-logo">HR Analytics</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Webmotors · Dados de colaboradores</div>', unsafe_allow_html=True)

        senha = st.text_input("Senha de acesso", type="password", placeholder="Digite a senha do time")

        if st.button("Entrar", use_container_width=True, type="primary"):
            if hashlib.md5(senha.encode()).hexdigest() == APP_PASSWORD_HASH:
                st.session_state["autenticado"] = True
                st.session_state["historico"]   = []
                st.session_state["mensagens"]   = []
                st.rerun()
            else:
                st.error("Senha incorreta. Solicite ao responsável pelo HR Analytics.")

        st.markdown('</div>', unsafe_allow_html=True)

# ── TELA DE CHAT ──────────────────────────────────────────────
def tela_chat(df: pd.DataFrame):

    # SIDEBAR ─────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### HR Analytics")
        st.caption("Webmotors · Agente de dados")
        st.divider()

        st.markdown("**Sugestões de perguntas**")
        exemplos = [
            "Qual o headcount total por empresa?",
            "Quantos colaboradores ativos temos hoje?",
            "Distribuição por gênero em cada empresa",
            "Quais as 5 áreas com mais colaboradores?",
            "Quantos foram contratados este mês?",
            "Colaboradores afastados no momento",
            "Headcount por tipo de contratação",
            "Distribuição por faixa de tempo de casa",
        ]
        for ex in exemplos:
            if st.button(ex, use_container_width=True, key=f"ex_{ex[:25]}"):
                st.session_state["pergunta_rapida"] = ex

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Nova conversa", use_container_width=True):
                st.session_state["historico"]  = []
                st.session_state["mensagens"]  = []
                st.rerun()
        with col2:
            if st.button("Sair", use_container_width=True):
                st.session_state.clear()
                st.rerun()

        st.divider()
        ultima_atualizacao = datetime.now().strftime("%d/%m/%Y %H:%M")
        st.caption(f"Dados extraídos em: {ultima_atualizacao}")
        total = len(df)
        ativos = len(df[df["Status"] == "ATIVO"]) if "Status" in df.columns else "—"
        st.caption(f"Total: {total:,} registros · Ativos: {ativos:,}")

    # ÁREA PRINCIPAL ──────────────────────────────────────────
    st.markdown("### Agente de HR Analytics")
    st.caption("Faça perguntas sobre os dados de colaboradores em linguagem natural.")

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
