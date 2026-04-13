# Agente Analítico de HR — Webmotors

## Arquivos
```
agente_hr_app/
├── app.py            ← app principal
├── requirements.txt  ← dependências Python
└── LEIAME.md         ← este guia
```

---

## Passo 1 — Gerar o hash da senha

Escolha uma senha para o time de RH e rode no terminal:

```bash
python -c "import hashlib; print(hashlib.md5('SUA_SENHA_AQUI'.encode()).hexdigest())"
```

Guarde o hash gerado — você vai precisar no Passo 3.

---

## Passo 2 — Subir no GitHub

1. Crie uma conta em https://github.com (se não tiver)
2. Crie um repositório novo — pode ser privado
3. Faça upload dos 3 arquivos: app.py, requirements.txt, LEIAME.md

---

## Passo 3 — Publicar no Streamlit Cloud

1. Acesse https://share.streamlit.io e conecte sua conta GitHub
2. Clique em "New app" e selecione o repositório criado
3. Em "Advanced settings" → "Secrets", cole:

```toml
ANTHROPIC_API_KEY = "sk-ant-SUA_CHAVE_AQUI"
APP_PASSWORD_HASH = "hash_gerado_no_passo_1"
```

4. Clique em Deploy — em ~2 minutos o link estará disponível

---

## Passo 4 — Compartilhar com o time

Envie o link gerado + a senha para as 13 pessoas do RH.
Exemplo de mensagem:

> Olá! Nosso agente de HR Analytics está disponível.
> Link: https://SEU-APP.streamlit.app
> Senha: (a senha que você definiu)
> Basta abrir no navegador e digitar a senha. Qualquer dúvida, me chama!

---

## Como trocar a senha no futuro

1. Gere um novo hash (Passo 1) com a nova senha
2. Acesse o app no Streamlit Cloud → Settings → Secrets
3. Atualize o valor de APP_PASSWORD_HASH
4. Salve — o app reinicia automaticamente em segundos

Não precisa mexer no código nem no GitHub.

---

## Quando adicionar perfis (gestores vs analistas)

Quando quiser expandir para outros times com controle de acesso,
é só avisar que o código da versão com perfis já está pronto
e a migração é simples.
