import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# 1. Configuração do caminho de destino
PASTA_DESTINO = r"C:\Users\GustavoPereiradasNev\OneDrive - Webmotors S.A\HR ANALYTICS\PBI\13. Glassdoor\01. Bases"
ARQUIVO_FINAL = os.path.join(PASTA_DESTINO, "consolidado_glassdoor.xlsx")

empresas_urls = {
    "Webmotors": "https://www.glassdoor.com.br/Avaliacoes/Webmotors-Avaliacoes-E664121.htm",
    "Car10": "https://www.glassdoor.com.br/Avalia%C3%A7%C3%B5es/Car10-Avalia%C3%A7%C3%B5es-E2669926.htm",
    "Loop": "https://www.glassdoor.com.br/Avalia%C3%A7%C3%B5es/Loop-Brasil-Avalia%C3%A7%C3%B5es-E2795878.htm",
    "Syonet": "https://www.glassdoor.com.br/Avalia%C3%A7%C3%B5es/Syonet-Avalia%C3%A7%C3%B5es-E2492025.htm",
    "Revenda Mais": "https://www.glassdoor.com.br/Avalia%C3%A7%C3%B5es/Revenda-Mais-Avalia%C3%A7%C3%B5es-E2857612.htm",
    "iCarros": "https://www.glassdoor.com.br/Avalia%C3%A7%C3%B5es/iCarros-Avalia%C3%A7%C3%B5es-E784395.htm",
    "Mercado Livre": "https://www.glassdoor.com.br/Avalia%C3%A7%C3%B5es/Mercado-Livre-Avalia%C3%A7%C3%B5es-E2372230.htm",
    "OLX": "https://www.glassdoor.com.br/Avalia%C3%A7%C3%B5es/Grupo-OLX-Avalia%C3%A7%C3%B5es-E2500798.htm"
}

chrome_options = Options()
usuario_windows = os.getlogin()

# Vincula ao seu perfil real para aproveitar os cookies de login
chrome_options.add_argument(f"--user-data-dir=C:\\Users\\{usuario_windows}\\AppData\\Local\\Google\\Chrome\\User Data")
chrome_options.add_argument("--profile-directory=Default") 

# Parâmetros cruciais para mitigar bloqueios de robô (Cloudflare) do Glassdoor
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-extensions")

# OBRIGATÓRIO: Feche todas as janelas do seu Chrome antes de apertar o PLAY
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
wait = WebDriverWait(driver, 15)

dados_consolidados = []

for empresa, url in empresas_urls.items():
    try:
        print(f"Acessando {empresa}...")
        driver.get(url)
        time.sleep(5)  # Tempo para renderização e comportamento humano
        
        # 🔄 CORREÇÃO AQUI: Sintaxe correta para Selenium 4 utilizando tupla interna
        elemento_nota = wait.until(
            EC.presence_of_element_located((By.XPATH, '//div[contains(@class, "rating-headline")] | //span[contains(@class, "rating")]'))
        )
        nota_geral = elemento_nota.text.strip()
        
        # Tratamento individual para sub-elementos para evitar que a falta de um deles quebre o loop da empresa
        try:
            recomendacao = driver.find_element(By.XPATH, '//span[contains(text(), "recomendariam")]/ancestor::div[1]//span[contains(text(), "%")] | //div[contains(text(), "recomendariam")]/preceding-sibling::span').text.strip()
        except Exception:
            recomendacao = "N/A"
            
        try:
            perspectiva = driver.find_element(By.XPATH, '//span[contains(text(), "Perspectiva")]/ancestor::div[1]//span[contains(text(), "%")] | //div[contains(text(), "Perspectiva")]/preceding-sibling::span').text.strip()
        except Exception:
            perspectiva = "N/A"
        
        dados_consolidados.append({
            "Data Extração": pd.Timestamp.now().strftime("%Y-%m-%d"),
            "Empresa": empresa,
            "Grupo/Concorrente": "Grupo" if empresa in ["Webmotors", "Car10", "Loop", "Syonet", "Revenda Mais"] else "Concorrente",
            "Nota Geral": nota_geral,
            "Recomendação Amigos": recomendacao,
            "Perspectiva Positiva": perspectiva
        })
        print(f"✓ {empresa} coletada com sucesso! Nota: {nota_geral}")
        
    except Exception as e:
        print(f"✕ Erro crítico ao coletar dados de {empresa}.")
        print(f"Detalhe do erro: {str(e)[:120]}")

driver.quit()

# Gravação dos dados coletados
if dados_consolidados:
    df = pd.DataFrame(dados_consolidados)
    os.makedirs(PASTA_DESTINO, exist_ok=True)
    df.to_excel(ARQUIVO_FINAL, index=False)
    print(f"\n[Sucesso] Processo concluído! Base atualizada em:\n--> {ARQUIVO_FINAL}")
else:
    print("\n⚠️ Nenhuma informação pôde ser extraída nesta execução.")
