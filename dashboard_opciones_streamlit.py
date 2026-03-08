"""
Dashboard de Criptomonedas con Streamlit:
- Dos pestañas: una para Bitcoin y otra para Ethereum
- Cada pestaña contiene:
  - Izquierda: Velas cada 15 minutos (usando Plotly)
  - Derecha: Soporte y Resistencia por Opciones
"""

import streamlit as st
import ccxt
import pandas as pd
import plotly.graph_objects as go
import time
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="Dashboard Cripto - Opciones", layout="wide")

# Variables globales
number_of_data = 5

@st.cache_data(ttl=30)  # Cache por 30 segundos
def obtener_datos_cripto(symbol):
    """Obtiene datos OHLCV de una criptomoneda cada 15 minutos"""
    try:
        exchange = ccxt.binance()
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=96)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        price = df['close'].iloc[-1]
        return df, price
    except Exception as e:
        st.error(f"Error obteniendo datos de {symbol}: {e}")
        return None, None

@st.cache_data
def calcular_soportes_resistencias():
    """Calcula los top 3 soportes y resistencias para BTC y ETH basado en opciones"""
    btc_soportes, btc_resistencias = [], []
    eth_soportes, eth_resistencias = [], []
    
    try:
        st.info("Calculando soportes y resistencias desde opciones...")
        deribit = ccxt.deribit()
        markets = deribit.fetch_markets()
        
        # Procesar Bitcoin
        btc_options = [m for m in markets if 'BTC' in m['symbol'] and '-' in m['symbol']]
        btc_datos = _procesar_opciones(btc_options, deribit, 'BTC')
        btc_soportes = btc_datos['soportes']
        btc_resistencias = btc_datos['resistencias']
        
        # Procesar Ethereum
        eth_options = [m for m in markets if 'ETH' in m['symbol'] and '-' in m['symbol']]
        eth_datos = _procesar_opciones(eth_options, deribit, 'ETH')
        eth_soportes = eth_datos['soportes']
        eth_resistencias = eth_datos['resistencias']
        
        st.success("Cálculo completado para ambas criptomonedas")
        
    except Exception as e:
        st.error(f"Error calculando soportes/resistencias: {e}")
    
    return btc_soportes, btc_resistencias, eth_soportes, eth_resistencias

def _procesar_opciones(opciones, exchange, simbolo):
    """Procesa los datos de opciones para una criptomoneda específica"""
    soportes = []
    resistencias = []
    
    try:
        options_data = []
        
        for opt in opciones:
            try:
                parts = opt['symbol'].split('-')
                if len(parts) >= 4:
                    fecha = parts[1]
                    strike = float(parts[2])
                    tipo = 'put' if parts[3] == 'P' else 'call'
                    
                    order_book = exchange.fetch_order_book(opt['symbol'])
                    bids = order_book.get('bids', [])
                    asks = order_book.get('asks', [])
                    volumen = sum([bid[1] for bid in bids]) + sum([ask[1] for ask in asks])
                    
                    options_data.append({
                        'type': tipo,
                        'strike': strike,
                        'open_interest': volumen,
                        'expiration': fecha,
                        'symbol': opt['symbol']
                    })
            except Exception as e:
                continue
        
        if len(options_data) > 0:
            df = pd.DataFrame(options_data)
            df["strike"] = pd.to_numeric(df["strike"])
            df["open_interest"] = pd.to_numeric(df["open_interest"])
            
            grouped = (
                df.groupby(["type", "strike"])["open_interest"]
                .sum()
                .reset_index()
            )
            
            # Top puts (soportes)
            puts = grouped[grouped["type"] == "put"]
            if len(puts) > 0:
                puts_sorted = puts.sort_values("open_interest", ascending=False).head(number_of_data)
                soportes = puts_sorted.to_dict('records')
            
            # Top calls (resistencias)
            calls = grouped[grouped["type"] == "call"]
            if len(calls) > 0:
                calls_sorted = calls.sort_values("open_interest", ascending=False).head(number_of_data)
                resistencias = calls_sorted.to_dict('records')
    
    except Exception as e:
        st.error(f"Error procesando opciones de {simbolo}: {e}")
    
    return {'soportes': soportes, 'resistencias': resistencias}

def crear_grafico_cripto(data, price, soportes, resistencias, nombre, simbolo):
    """Crea el gráfico de velas con Plotly"""
    if data is None or len(data) == 0:
        return go.Figure()
    
    df = data.tail(50)  # Últimas 50 velas
    
    fig = go.Figure(data=[go.Candlestick(
        x=df['timestamp'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Velas'
    )])
    
    # Agregar líneas de soporte
    if soportes:
        for i, soporte in enumerate(soportes):
            color = 'green'
            width = 3 if i == 0 else (2 if i == 1 else 1)
            opacity = 1.0 if i == 0 else (0.7 if i == 1 else 0.5)
            fig.add_hline(y=soporte['strike'], line_color=color, line_width=width, opacity=opacity,
                         annotation_text=f"Soporte {i+1}: ${soporte['strike']:,.0f}")
    
    # Agregar líneas de resistencia
    if resistencias:
        for i, resistencia in enumerate(resistencias):
            color = 'red'
            width = 3 if i == 0 else (2 if i == 1 else 1)
            opacity = 1.0 if i == 0 else (0.7 if i == 1 else 0.5)
            fig.add_hline(y=resistencia['strike'], line_color=color, line_width=width, opacity=opacity,
                         annotation_text=f"Resistencia {i+1}: ${resistencia['strike']:,.0f}")
    
    fig.update_layout(
        title=f'{nombre} - Velas 15 min | Precio: ${price:,.2f}',
        xaxis_title='Fecha/Hora',
        yaxis_title='Precio USD',
        xaxis_rangeslider_visible=False
    )
    
    return fig

def mostrar_analisis_opciones(price, soportes, resistencias, simbolo):
    """Muestra el análisis de opciones en el sidebar derecho"""
    st.subheader(f"Análisis de Opciones - {simbolo}")
    st.metric("Precio Actual", f"${price:,.2f}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**SOPORTES (Puts)**")
        if soportes:
            for i, soporte in enumerate(soportes, 1):
                st.markdown(f"#{i}: **${soporte['strike']:,.0f}** (OI: {soporte['open_interest']:.0f})")
        else:
            st.write("No disponible")
    
    with col2:
        st.markdown("**RESISTENCIAS (Calls)**")
        if resistencias:
            for i, resistencia in enumerate(resistencias, 1):
                st.markdown(f"#{i}: **${resistencia['strike']:,.0f}** (OI: {resistencia['open_interest']:.0f})")
        else:
            st.write("No disponible")
    
    st.caption(f"Actualizado: {datetime.now().strftime('%H:%M:%S')}")

# Main app
def main():
    st.title("📊 Dashboard Cripto - Análisis de Opciones")
    
    # Calcular soportes y resistencias (solo una vez)
    if 'sop_res' not in st.session_state:
        btc_sop, btc_res, eth_sop, eth_res = calcular_soportes_resistencias()
        st.session_state.sop_res = (btc_sop, btc_res, eth_sop, eth_res)
    else:
        btc_sop, btc_res, eth_sop, eth_res = st.session_state.sop_res
    
    # Crear pestañas
    tab_btc, tab_eth = st.tabs(["🪙 Bitcoin", "💎 Ethereum"])
    
    with tab_btc:
        st.header("Bitcoin (BTC/USDT)")
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Obtener datos
            btc_data, btc_price = obtener_datos_cripto('BTC/USDT')
            if btc_data is not None:
                fig_btc = crear_grafico_cripto(btc_data, btc_price, btc_sop, btc_res, 'Bitcoin', 'BTC')
                st.plotly_chart(fig_btc, use_container_width=True)
        
        with col2:
            if btc_price:
                mostrar_analisis_opciones(btc_price, btc_sop, btc_res, 'BTC')
    
    with tab_eth:
        st.header("Ethereum (ETH/USDT)")
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Obtener datos
            eth_data, eth_price = obtener_datos_cripto('ETH/USDT')
            if eth_data is not None:
                fig_eth = crear_grafico_cripto(eth_data, eth_price, eth_sop, eth_res, 'Ethereum', 'ETH')
                st.plotly_chart(fig_eth, use_container_width=True)
        
        with col2:
            if eth_price:
                mostrar_analisis_opciones(eth_price, eth_sop, eth_res, 'ETH')
    
    # Botón para actualizar
    if st.button("🔄 Actualizar Datos"):
        st.cache_data.clear()
        st.rerun()
    
    # Auto-refresh cada 30 segundos
    time.sleep(30)
    st.rerun()

if __name__ == "__main__":
    main()