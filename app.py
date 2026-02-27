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

def calcular_valor(texto):
    if not texto: return 0.0
    try:
        texto_limpo = str(texto).replace("R$", "").replace(" ", "").replace(",", ".")
        return float(eval(texto_limpo))
    except: return 0.0

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
with col_res1: st.metric("Veículos Hoje", total_veiculos)
with col_res2: st.metric("Total Boletos Hoje", total_boletos)
with col_res3:
    fuso_br = pytz.timezone('America/Sao_Paulo')
    st.metric("Data", datetime.now(fuso_br).strftime("%d/%m/%Y"))

st.divider()

with st.form("lote_8", clear_on_submit=True):
    lista_entradas = []
    
    # Toggle para trocar o visual
    modo_celular = st.toggle("📱 Ativar Modo Celular (Cartões)", value=False)

    # LOOP ÚNICO PARA CRIAR OS 8 VEÍCULOS
    for i in range(8):
        if modo_celular:
            # --- VISUAL CELULAR (EXPANSORES) ---
            with st.expander(f"🚗 VEÍCULO {i+1}", expanded=(i==0)):
                # No celular, agrupamos em pequenas colunas para não ficar gigante
                c1, c2 = st.columns([2, 1])
                p = c1.text_input("Placa", key=f"p{i}").upper()
                q = c2.text_input("Qtd", value="1", key=f"q{i}")
                
                v = st.text_input("Valor Total", key=f"v{i}", help="Pode somar ex: 10+20")
                
                col_f = st.columns(3)
                t = col_f[0].text_input("Taxa", key=f"t{i}")
                a = col_f[1].text_input("Add", key=f"a{i}")
                s = col_f[2].text_input("Saiu", key=f"s{i}")
                
                f = st.selectbox("Forma de Pagamento", ["Pix", "Dinheiro", "Débito", "Crédito", "PIX+DIN", "DIN+CARTAO", "PIX+CARTAO"], key=f"f{i}")
        else:
            # --- VISUAL PC (TABELA HORIZONTAL) ---
            if i == 0:
                cols_tit = st.columns([2, 1, 2, 1.2, 1.2, 1.2, 2])
                cols_tit[0].write("**Placa**")
                cols_tit[1].write("**Qtd**")
                cols_tit[2].write("**Valor**")
                cols_tit[3].write("**Taxa**")
                cols_tit[4].write("**Add**")
                cols_tit[5].write("**Saiu**")
                cols_tit[6].write("**Forma**")

            c = st.columns([2, 1, 2, 1.2, 1.2, 1.2, 2])
            p = c[0].text_input(f"P{i}", label_visibility="collapsed", key=f"pc_p{i}").upper()
            q = c[1].text_input(f"Q{i}", value="1", label_visibility="collapsed", key=f"pc_q{i}")
            v = c[2].text_input(f"V{i}", value="", label_visibility="collapsed", key=f"pc_v{i}")
            t = c[3].text_input(f"T{i}", value="", label_visibility="collapsed", key=f"pc_t{i}")
            a = c[4].text_input(f"A{i}", value="", label_visibility="collapsed", key=f"pc_a{i}")
            s = c[5].text_input(f"S{i}", value="", label_visibility="collapsed", key=f"pc_s{i}")
            f = c[6].selectbox(f"F{i}", ["Pix", "Dinheiro", "Débito", "Crédito", "PIX+DIN", "PIX+CARTÃO"], label_visibility="collapsed", key=f"pc_f{i}")
        
        # Adiciona à lista independente do modo visual escolhido
        lista_entradas.append({"p": p, "q": q, "v": v, "t": t, "a": a, "s": s, "f": f})

    st.markdown("---")
    enviar = st.form_submit_button("🚀 ENVIAR LOTE PARA PLANILHA", use_container_width=True)

    if enviar:
        fuso_br = pytz.timezone('America/Sao_Paulo')
        agora = datetime.now(fuso_br)
        lote_final = []
        
        for item in lista_entradas:
            if item["p"] or item["v"]:
                linha = [
                    agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M:%S"),
                    int(item["q"]) if item["q"].isdigit() else 1,
                    calcular_valor(item["v"]), calcular_valor(item["t"]),
                    calcular_valor(item["a"]), calcular_valor(item["s"]),
                    item["f"], item["p"] if item["p"] else "S/P"
                ]
                lote_final.append(linha)

        if lote_final:
            try:
                coluna_placa = sheet.col_values(9)
                proxima_linha = max(len(coluna_placa) + 1, 7)
                sheet.insert_rows(lote_final, row=proxima_linha)
                st.success(f"✅ {len(lote_final)} registros enviados com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao enviar: {e}")