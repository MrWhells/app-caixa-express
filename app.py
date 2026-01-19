import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import json

# --- CONFIGURAÇÃO ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

if "gcp_service_account" in st.secrets:
    info_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(info_dict, scope)
else:
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)

client = gspread.authorize(creds)

def preparar_planilha():
    ss = client.open("sistema_pagamentos")
    fuso_br = pytz.timezone('America/Sao_Paulo')
    nome_hoje = datetime.now(fuso_br).strftime("%d-%m-%Y")
    try:
        return ss.worksheet(nome_hoje)
    except gspread.exceptions.WorksheetNotFound:
        modelo = ss.worksheet("MODELO")
        return ss.duplicate_sheet(modelo.id, insert_sheet_index=1, new_sheet_name=nome_hoje)

# FUNÇÃO QUE CONVERTE VÍRGULA EM PONTO E FAZ CALCULOS (Ex: 10+5)
def calcular_valor(texto):
    if not texto:
        return 0.0
    try:
        # Remove R$, espaços e troca vírgula por ponto
        texto_limpo = str(texto).replace("R$", "").replace(" ", "").replace(",", ".")
        # O eval permite que você digite contas como 10+5.50 e ele entenda o resultado
        return float(eval(texto_limpo))
    except:
        return 0.0

sheet = preparar_planilha()

# --- CÁLCULO DOS TOTAIS DO DIA ---
todas_linhas = sheet.get_all_values()
dados_existentes = todas_linhas[6:] if len(todas_linhas) > 6 else []
total_veiculos = len(dados_existentes)
total_boletos = sum(int(linha[2]) for linha in dados_existentes if len(linha) > 2 and str(linha[2]).isdigit())

# --- INTERFACE ---
st.set_page_config(page_title="Caixa Express 8x", layout="wide")

st.title("⚡ Lançamento de pagamentos")
col_res1, col_res2, col_res3 = st.columns(3)
with col_res1:
    st.metric("Veículos Hoje", total_veiculos)
with col_res2:
    st.metric("Total Boletos Hoje", total_boletos)
with col_res3:
    fuso_br = pytz.timezone('America/Sao_Paulo')
    st.metric("Data", datetime.now(fuso_br).strftime("%d/%m/%Y"))

st.divider()

with st.form("lote_8", clear_on_submit=True):
    lista_entradas = []
    cols_tit = st.columns([2, 1, 2, 1.2, 1.2, 1.2, 2])
    cols_tit[0].write("**Placa**")
    cols_tit[1].write("**Qtd**")
    cols_tit[2].write("**Valor (Soma: 10+20)**")
    cols_tit[3].write("**Taxa**")
    cols_tit[4].write("**Add**")
    cols_tit[5].write("**Saiu**")
    cols_tit[6].write("**Forma**")

    for i in range(8):
        c = st.columns([2, 1, 2, 1.2, 1.2, 1.2, 2])
        p = c[0].text_input(f"P{i}", label_visibility="collapsed", key=f"p{i}").upper()
        q = c[1].text_input(f"Q{i}", value="1", label_visibility="collapsed", key=f"q{i}")
        v = c[2].text_input(f"V{i}", value="", label_visibility="collapsed", key=f"v{i}")
        t = c[3].text_input(f"T{i}", value="", label_visibility="collapsed", key=f"t{i}")
        a = c[4].text_input(f"A{i}", value="", label_visibility="collapsed", key=f"a{i}")
        s = c[5].text_input(f"S{i}", value="", label_visibility="collapsed", key=f"s{i}")
        f = c[6].selectbox(f"F{i}", ["Pix", "Dinheiro", "Débito", "Crédito"], label_visibility="collapsed", key=f"f{i}")
        
        lista_entradas.append({"p": p, "q": q, "v": v, "t": t, "a": a, "s": s, "f": f})

    if st.form_submit_button("🚀 ENVIAR"):
        fuso_br = pytz.timezone('America/Sao_Paulo')
        agora = datetime.now(fuso_br)
        lote_final = []
        
        for item in lista_entradas:
            # Envia se tiver Placa OU se tiver Valor
            if item["p"] or item["v"]:
                linha = [
                    agora.strftime("%d/%m/%Y"), 
                    agora.strftime("%H:%M:%S"),
                    int(item["q"]) if item["q"].isdigit() else 1,
                    calcular_valor(item["v"]), 
                    calcular_valor(item["t"]),
                    calcular_valor(item["a"]), 
                    calcular_valor(item["s"]),
                    item["f"], 
                    item["p"] if item["p"] else "S/P"
                ]
                lote_final.append(linha)

        if lote_final:
            try:
                coluna_placa = sheet.col_values(9) 
                proxima_linha = len(coluna_placa) + 1
                if proxima_linha < 7:
                    proxima_linha = 7
                
                sheet.insert_rows(lote_final, row=proxima_linha)
                st.success(f"✅ {len(lote_final)} registros enviados com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao enviar: {e}")