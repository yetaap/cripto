"""
Dashboard gráfico en tiempo real:
- Dos ventanas separadas: una para Bitcoin y otra para Ethereum
- Cada ventana contiene:
  - Izquierda: Velas cada 15 minutos
  - Derecha: Soporte y Resistencia por Opciones (calculado una sola vez)
"""

import ccxt
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Rectangle
import threading
import time
from datetime import datetime, timedelta

# Variables globales
number_of_data = 5

# Bitcoin
btc_data = None
btc_price = 0
btc_soportes = []
btc_resistencias = []

# Ethereum
eth_data = None
eth_price = 0
eth_soportes = []
eth_resistencias = []

lock = threading.Lock()

def obtener_datos_bitcoin():
    """Obtiene datos OHLCV de Bitcoin cada 15 minutos"""
    global btc_data, btc_price
    
    exchange = ccxt.binance()
    
    while True:
        try:
            # Obtener datos de últimas 24 horas en frames de 15 minutos
            ohlcv = exchange.fetch_ohlcv('BTC/USDT', timeframe='15m', limit=96)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            btc_price = df['close'].iloc[-1]
            
            with lock:
                btc_data = df
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Datos de Bitcoin actualizados - Precio: ${btc_price:,.2f}")
            
        except Exception as e:
            print(f"Error obteniendo datos de Bitcoin: {e}")
        
        time.sleep(30)  # Actualizar cada 30 segundos

def obtener_datos_ethereum():
    """Obtiene datos OHLCV de Ethereum cada 15 minutos"""
    global eth_data, eth_price
    
    exchange = ccxt.binance()
    
    while True:
        try:
            # Obtener datos de últimas 24 horas en frames de 15 minutos
            ohlcv = exchange.fetch_ohlcv('ETH/USDT', timeframe='15m', limit=96)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            eth_price = df['close'].iloc[-1]
            
            with lock:
                eth_data = df
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Datos de Ethereum actualizados - Precio: ${eth_price:,.2f}")
            
        except Exception as e:
            print(f"Error obteniendo datos de Ethereum: {e}")
        
        time.sleep(30)  # Actualizar cada 30 segundos

def calcular_soportes_resistencias():
    """Calcula los top 3 soportes y resistencias para BTC y ETH basado en opciones (ejecutar una sola vez)"""
    global btc_soportes, btc_resistencias, eth_soportes, eth_resistencias
    
    try:
        print("Calculando soportes y resistencias desde opciones...")
        deribit = ccxt.deribit()
        markets = deribit.fetch_markets()
        
        # Procesar Bitcoin
        print("  Procesando Bitcoin...")
        btc_options = [m for m in markets if 'BTC' in m['symbol'] and '-' in m['symbol']]
        btc_datos = _procesar_opciones(btc_options, deribit, 'BTC')
        btc_soportes = btc_datos['soportes']
        btc_resistencias = btc_datos['resistencias']
        
        # Procesar Ethereum
        print("  Procesando Ethereum...")
        eth_options = [m for m in markets if 'ETH' in m['symbol'] and '-' in m['symbol']]
        eth_datos = _procesar_opciones(eth_options, deribit, 'ETH')
        eth_soportes = eth_datos['soportes']
        eth_resistencias = eth_datos['resistencias']
        
        print("✓ Cálculo completado para ambas criptomonedas")
        
    except Exception as e:
        print(f"Error calculando soportes/resistencias: {e}")

def _procesar_opciones(opciones, exchange, simbolo):
    """Procesa los datos de opciones para una criptomoneda específica"""
    soportes = []
    resistencias = []
    
    try:
        options_data = []
        
        for opt in opciones:
            try:
                # Extraer información del símbolo
                parts = opt['symbol'].split('-')
                if len(parts) >= 4:
                    fecha = parts[1]
                    strike = float(parts[2])
                    tipo = 'put' if parts[3] == 'P' else 'call'
                    
                    # Obtener el libro de órdenes para estimar interés abierto (volumen)
                    order_book = exchange.fetch_order_book(opt['symbol'])
                    bids = order_book.get('bids', [])
                    asks = order_book.get('asks', [])
                    
                    # Calcular volumen como proxy de open interest
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
        
        # Crear DataFrame
        if len(options_data) > 0:
            df = pd.DataFrame(options_data)
            
            # Convertir a numérico
            df["strike"] = pd.to_numeric(df["strike"])
            df["open_interest"] = pd.to_numeric(df["open_interest"])
            
            # Agrupar por strike y tipo
            grouped = (
                df.groupby(["type", "strike"])["open_interest"]
                .sum()
                .reset_index()
            )
            
            # Top 3 puts (soportes)
            puts = grouped[grouped["type"] == "put"]
            if len(puts) > 0:
                puts_sorted = puts.sort_values("open_interest", ascending=False).head(number_of_data)
                soportes = puts_sorted.to_dict('records')
            
            # Top 3 calls (resistencias)
            calls = grouped[grouped["type"] == "call"]
            if len(calls) > 0:
                calls_sorted = calls.sort_values("open_interest", ascending=False).head(number_of_data)
                resistencias = calls_sorted.to_dict('records')
            
            if soportes and resistencias:
                soportes_str = ', '.join([f'${s["strike"]:,.0f}' for s in soportes])
                resistencias_str = ', '.join([f'${r["strike"]:,.0f}' for r in resistencias])
                print(f"    Soportes ({simbolo}): {soportes_str}")
                print(f"    Resistencias ({simbolo}): {resistencias_str}")
        
    except Exception as e:
        print(f"Error procesando opciones de {simbolo}: {e}")
    
    return {'soportes': soportes, 'resistencias': resistencias}

def crear_dashboard():
    """Crea dos dashboards gráficos separados (uno para BTC, otro para ETH)"""
    
    # Crear dos figuras separadas
    fig_btc = plt.figure(figsize=(16, 8))
    fig_btc.suptitle('Bitcoin Dashboard - Velas + Análisis de Opciones', fontsize=16, fontweight='bold')
    
    fig_eth = plt.figure(figsize=(16, 8))
    fig_eth.suptitle('Ethereum Dashboard - Velas + Análisis de Opciones', fontsize=16, fontweight='bold')
    
    # Crear subplots para Bitcoin
    ax_velas_btc = fig_btc.add_subplot(121)
    ax_analisis_btc = fig_btc.add_subplot(122)
    
    # Crear subplots para Ethereum
    ax_velas_eth = fig_eth.add_subplot(121)
    ax_analisis_eth = fig_eth.add_subplot(122)
    
    def actualizar_grafico_btc(frame):
        """Función que se ejecuta cada actualización para Bitcoin"""
        _actualizar_grafico_cripto(ax_velas_btc, ax_analisis_btc, btc_data, btc_price, 
                                   btc_soportes, btc_resistencias, 'Bitcoin', 'BTC')
        return ax_velas_btc, ax_analisis_btc
    
    def actualizar_grafico_eth(frame):
        """Función que se ejecuta cada actualización para Ethereum"""
        _actualizar_grafico_cripto(ax_velas_eth, ax_analisis_eth, eth_data, eth_price, 
                                   eth_soportes, eth_resistencias, 'Ethereum', 'ETH')
        return ax_velas_eth, ax_analisis_eth
    
    # Crear animaciones (actualizar cada 10 segundos)
    ani_btc = FuncAnimation(fig_btc, actualizar_grafico_btc, interval=10000, cache_frame_data=False)
    ani_eth = FuncAnimation(fig_eth, actualizar_grafico_eth, interval=10000, cache_frame_data=False)
    
    fig_btc.tight_layout()
    fig_eth.tight_layout()
    
    plt.show()

def _actualizar_grafico_cripto(ax_velas, ax_analisis, data, price, soportes, resistencias, nombre, simbolo):
    """Función auxiliar para actualizar gráficos de cualquier criptomoneda"""
    
    with lock:
        # Actualizar gráfico de velas
        ax_velas.clear()
        
        if data is not None and len(data) > 0:
            df = data.tail(50)  # Últimas 50 velas (12.5 horas)
            
            for idx_pos, (idx, row) in enumerate(df.iterrows()):
                timestamp = idx_pos
                open_price = row['open']
                high_price = row['high']
                low_price = row['low']
                close_price = row['close']
                
                # Color: verde si cierra arriba, rojo si cierra abajo
                color = 'green' if close_price >= open_price else 'red'
                
                # Dibujar línea (high-low)
                ax_velas.plot([timestamp, timestamp], [low_price, high_price], color='black', linewidth=0.5)
                
                # Dibujar cuerpo (open-close)
                height = abs(close_price - open_price)
                bottom = min(open_price, close_price)
                rect = Rectangle((timestamp - 0.3, bottom), 0.6, height if height > 0 else 0.1, 
                                facecolor=color, edgecolor='black', linewidth=0.5)
                ax_velas.add_patch(rect)
            
            ax_velas.set_title(f'{nombre} - Velas 15 min', fontweight='bold', fontsize=12)
            ax_velas.set_xlabel('Fecha/Hora')
            ax_velas.set_ylabel('Precio USD')
            ax_velas.grid(True, alpha=0.3)
            ax_velas.set_ylim([df['low'].min() - 500, df['high'].max() + 500])
            
            # Configurar etiquetas del eje x con fechas
            num_ticks = 6
            tick_positions = [int(i * len(df) / num_ticks) for i in range(num_ticks)]
            tick_labels = [df.iloc[pos]['timestamp'].strftime('%H:%M') if pos < len(df) else '' for pos in tick_positions]
            ax_velas.set_xticks(tick_positions)
            ax_velas.set_xticklabels(tick_labels, rotation=45, ha='right')
            
            # Líneas de soporte y resistencia en el gráfico de velas
            if soportes:
                ax_velas.axhline(y=soportes[0]['strike'], color='green', linestyle='--', linewidth=2, alpha=0.9, label=f"Soporte 1: ${soportes[0]['strike']:,.0f}")
                if len(soportes) > 1:
                    ax_velas.axhline(y=soportes[1]['strike'], color='green', linestyle='--', linewidth=1.5, alpha=0.6)
                if len(soportes) > 2:
                    ax_velas.axhline(y=soportes[2]['strike'], color='green', linestyle='--', linewidth=1, alpha=0.4)
                if len(soportes) > 3:
                    ax_velas.axhline(y=soportes[3]['strike'], color='green', linestyle='--', linewidth=1, alpha=0.4)
                if len(soportes) > 4:
                    ax_velas.axhline(y=soportes[4]['strike'], color='green', linestyle='--', linewidth=1, alpha=0.4)
                    
            if resistencias:
                ax_velas.axhline(y=resistencias[0]['strike'], color='red', linestyle='--', linewidth=2, alpha=0.9, label=f"Resistencia 1: ${resistencias[0]['strike']:,.0f}")
                if len(resistencias) > 1:
                    ax_velas.axhline(y=resistencias[1]['strike'], color='red', linestyle='--', linewidth=1.5, alpha=0.6)
                if len(resistencias) > 2:
                    ax_velas.axhline(y=resistencias[2]['strike'], color='red', linestyle='--', linewidth=1, alpha=0.4)
                if len(resistencias) > 3:
                    ax_velas.axhline(y=resistencias[3]['strike'], color='red', linestyle='--', linewidth=1, alpha=0.4)
                if len(resistencias) > 4:
                    ax_velas.axhline(y=resistencias[4]['strike'], color='red', linestyle='--', linewidth=1, alpha=0.4)
            
            ax_velas.legend(loc='upper left', fontsize=10)
        
        # Actualizar análisis de opciones
        ax_analisis.clear()
        ax_analisis.axis('off')
        
        y_position = 0.95
        titulo = f"Análisis de Opciones - {simbolo}: ${price:,.0f}"
        ax_analisis.text(0.5, y_position, titulo, ha='center', fontsize=13, fontweight='bold',
                       transform=ax_analisis.transAxes)
        y_position -= 0.06
        
        # Mostrar soportes
        if soportes:
            ax_analisis.text(0.5, y_position, "SOPORTES (Puts)", ha='center', fontsize=11, fontweight='bold',
                           transform=ax_analisis.transAxes, color='darkgreen')
            y_position -= 0.045
            
            for i, soporte in enumerate(soportes, 1):
                color_bg = 'lightgreen' if i == 1 else ('lightseagreen' if i == 2 else 'lightcyan')
                alpha_val = 0.9 if i == 1 else (0.7 if i == 2 else 0.5)
                
                ax_analisis.text(0.5, y_position, f"#{i}: ${soporte['strike']:,.0f}", ha='center', fontsize=11, fontweight='bold',
                               transform=ax_analisis.transAxes, 
                               bbox=dict(boxstyle='round', facecolor=color_bg, alpha=alpha_val),
                               color='darkgreen')
                y_position -= 0.035
                
                ax_analisis.text(0.5, y_position, f"OI: {soporte['open_interest']:.0f}", 
                               ha='center', fontsize=8, transform=ax_analisis.transAxes, style='italic')
                y_position -= 0.03
        
        y_position -= 0.02
        
        # Mostrar resistencias
        if resistencias:
            ax_analisis.text(0.5, y_position, "RESISTENCIAS (Calls)", ha='center', fontsize=11, fontweight='bold',
                           transform=ax_analisis.transAxes, color='darkred')
            y_position -= 0.045
            
            for i, resistencia in enumerate(resistencias, 1):
                color_bg = 'lightcoral' if i == 1 else ('lightsalmon' if i == 2 else 'mistyrose')
                alpha_val = 0.9 if i == 1 else (0.7 if i == 2 else 0.5)
                
                ax_analisis.text(0.5, y_position, f"#{i}: ${resistencia['strike']:,.0f}", ha='center', fontsize=11, fontweight='bold',
                               transform=ax_analisis.transAxes, 
                               bbox=dict(boxstyle='round', facecolor=color_bg, alpha=alpha_val),
                               color='darkred')
                y_position -= 0.035
                
                ax_analisis.text(0.5, y_position, f"OI: {resistencia['open_interest']:.0f}", 
                               ha='center', fontsize=8, transform=ax_analisis.transAxes, style='italic')
                y_position -= 0.03
        
        # Actualizar timestamp
        ax_analisis.text(0.5, 0.02, f"Actualizado: {datetime.now().strftime('%H:%M:%S')}", 
                       ha='center', fontsize=9, style='italic',
                       transform=ax_analisis.transAxes)

if __name__ == "__main__":
    print("Iniciando Dashboard de Bitcoin y Ethereum...")
    print("Conectando a Binance y Deribit...\n")
    
    # Iniciar threads para obtener datos
    thread_btc = threading.Thread(target=obtener_datos_bitcoin, daemon=True)
    thread_eth = threading.Thread(target=obtener_datos_ethereum, daemon=True)
    thread_btc.start()
    thread_eth.start()
    
    # Calcular soportes y resistencias una sola vez (bloqueante, espera a terminar)
    calcular_soportes_resistencias()
    
    # Esperar un poco para que los datos iniciales se carguen
    time.sleep(3)
    
    # Crear dashboards (dos ventanas separadas)
    crear_dashboard()
