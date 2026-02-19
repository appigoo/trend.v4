import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- 頁面配置 ---
st.set_page_config(page_title="VIX 聯動-多股監控系統", layout="wide")
st.title("📊 VIX 恐慌指數聯動 - 實時趨勢預警系統")

# --- 側邊欄配置 ---
st.sidebar.header("設定")
input_symbols = st.sidebar.text_input("監控股票 (逗號分隔)", "AAPL, NVDA, TSLA, QQQ")
symbols = [s.strip().upper() for s in input_symbols.split(",")]
interval = st.sidebar.selectbox("頻率", ("1m", "2m", "5m"), index=0)

# --- 數據獲取函數 ---
def fetch_data(ticker, interval):
    try:
        data = yf.download(ticker, period="1d", interval=interval, progress=False)
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except:
        return None

def get_vix_status():
    """獲取 VIX 狀態並判斷市場風險"""
    vix_data = fetch_data("^VIX", "2m")
    if vix_data is None or len(vix_data) < 2:
        return 0, 0, "未知"
    
    current_vix = float(vix_data['Close'].iloc[-1])
    prev_vix = float(vix_data['Close'].iloc[-2])
    vix_change = ((current_vix - prev_vix) / prev_vix) * 100
    
    # 判斷風險等級
    if current_vix > 30 or vix_change > 5:
        risk = "🔴 高風險 (恐慌飆升)"
    elif current_vix > 20:
        risk = "🟡 中風險 (波動增加)"
    else:
        risk = "🟢 低風險 (市場穩定)"
    
    return current_vix, vix_change, risk

def analyze_combined(stock_df, vix_val, vix_chg):
    if stock_df is None or len(stock_df) < 21:
        return None, "數據不足", "等待", None, False
    
    # 技術指標
    stock_df['EMA_Fast'] = stock_df['Close'].ewm(span=9, adjust=False).mean()
    stock_df['EMA_Slow'] = stock_df['Close'].ewm(span=21, adjust=False).mean()
    stock_df['Vol_MA'] = stock_df['Volume'].rolling(window=10).mean()
    
    last = stock_df.iloc[-1]
    prev = stock_df.iloc[-2]
    
    # 反轉訊號
    signal = "穩定"
    alert = None
    
    # 核心邏輯：結合 VIX 的反轉警告
    # 如果 VIX 大漲且個股出現死叉，則是強烈賣出警告
    if prev['EMA_Fast'] >= prev['EMA_Slow'] and last['EMA_Fast'] < last['EMA_Slow']:
        signal = "↘️ 向下反轉"
        alert = "⚠️ 死亡交叉"
        if vix_chg > 3:
            alert += " + VIX 飆升 (強烈預警!)"
            
    elif prev['EMA_Fast'] <= prev['EMA_Slow'] and last['EMA_Fast'] > last['EMA_Slow']:
        signal = "↗️ 向上反轉"
        alert = "✅ 黃金交叉"
        if vix_chg < -2:
            alert += " + VIX 回落 (確認訊號)"

    vol_spike = float(last['Volume']) > (float(last['Vol_MA']) * 1.8)
    trend = "多頭" if last['EMA_Fast'] > last['EMA_Slow'] else "空頭"
    
    return stock_df, trend, signal, alert, vol_spike

# --- 主程式介面 ---
placeholder = st.empty()

while True:
    with placeholder.container():
        # 1. VIX 頂部資訊列
        v_val, v_chg, v_risk = get_vix_status()
        v_col1, v_col2, v_col3 = st.columns([1, 1, 2])
        v_col1.metric("VIX 指數", f"{v_val:.2f}", f"{v_chg:.2f}%", delta_color="inverse")
        v_col2.write(f"**市場風險狀況:**\n### {v_risk}")
        if v_chg > 5:
            st.error("🚨 全球市場警報：VIX 正在飆升，請注意個股多單風險！")
        
        st.divider()

        # 2. 個股監控清單
        for sym in symbols:
            df_stock = fetch_data(sym, interval)
            df, trend, signal, alert, vol_spike = analyze_combined(df_stock, v_val, v_chg)
            
            with st.expander(f"{sym} - 狀態: {trend} | 訊號: {signal}", expanded=True):
                if df is not None:
                    c1, c2 = st.columns([1, 4])
                    with c1:
                        st.metric(sym, f"{df['Close'].iloc[-1]:.2f}", f"{df['Close'].iloc[-1]-df['Close'].iloc[-2]:.2f}")
                        if alert: st.info(alert)
                        if vol_spike: st.warning("成交量異常放大")
                    
                    with c2:
                        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
                        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="股價"), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_Fast'], name="EMA9", line=dict(color='orange')), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_Slow'], name="EMA21", line=dict(color='cyan')), row=1, col=1)
                        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="成交量", marker_color='gray', opacity=0.5), row=2, col=1)
                        fig.update_layout(height=350, margin=dict(t=0, b=0), xaxis_rangeslider_visible=False, showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.write(f"正在等待 {sym} 數據...")

        time.sleep(60)
        st.rerun()
