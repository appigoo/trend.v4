import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- 頁面配置 ---
st.set_page_config(page_title="VIX聯動-多股監控系統", layout="wide")
st.title("🚀 多股趨勢監控 (VIX 情緒聯動版)")

# --- 側邊欄 ---
st.sidebar.header("監控設定")
default_symbols = "AAPL, TSLA, NVDA, 2330.TW"
input_symbols = st.sidebar.text_input("輸入股票代碼 (逗號分隔)", default_symbols)
symbols = [s.strip().upper() for s in input_symbols.split(",")]

interval = st.sidebar.selectbox("資料頻率", ("1m", "2m", "5m"), index=0)
ema_fast = st.sidebar.slider("快速 EMA", 5, 20, 9)
ema_slow = st.sidebar.slider("慢速 EMA", 21, 50, 21)

# --- 核心函數 ---
def fetch_data(ticker, interval):
    try:
        data = yf.download(ticker, period="1d", interval=interval, progress=False)
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except:
        return None

def get_vix_data():
    """抓取 VIX 數據並判斷恐慌程度"""
    vix = fetch_data("^VIX", "2m")
    if vix is None or len(vix) < 2: return 20.0, 0.0, "穩定"
    curr_v = float(vix['Close'].iloc[-1])
    prev_v = float(vix['Close'].iloc[-2])
    v_change = curr_v - prev_v
    
    if curr_v > 25: status = "😨 恐慌"
    elif curr_v < 15: status = "😊 樂觀"
    else: status = "😐 中性"
    return curr_v, v_change, status

def analyze_trend(df, vix_change):
    if df is None or len(df) < ema_slow:
        return None, "數據不足", "等待", None, False
    
    # 指標計算
    df['EMA_Fast'] = df['Close'].ewm(span=ema_fast, adjust=False).mean()
    df['EMA_Slow'] = df['Close'].ewm(span=ema_slow, adjust=False).mean()
    df['Vol_MA'] = df['Volume'].rolling(window=10).mean()
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    curr_fast, curr_slow = float(last['EMA_Fast']), float(last['EMA_Slow'])
    prev_fast, prev_slow = float(prev['EMA_Fast']), float(prev['EMA_Slow'])
    
    # 趨勢與反轉邏輯
    signal = "持平"
    alert = None
    vol_spike = float(last['Volume']) > (float(last['Vol_MA']) * 1.8)
    
    if prev_fast <= prev_slow and curr_fast > curr_slow:
        signal = "↗️ 向上反轉"
        alert = "黃金交叉"
        if vix_change < 0: alert += " (VIX下降配合)"
    elif prev_fast >= prev_slow and curr_fast < curr_slow:
        signal = "↘️ 向下反轉"
        alert = "死亡交叉"
        if vix_change > 0: alert += " (注意:VIX同步上升!)"
    
    trend = "多頭 (Bullish)" if curr_fast > curr_slow else "空頭 (Bearish)"
    return df, trend, signal, alert, vol_spike

# --- 主體介面 ---
placeholder = st.empty()

while True:
    with placeholder.container():
        # 1. VIX 全局看板
        v_val, v_chg, v_status = get_vix_data()
        v_col1, v_col2 = st.columns([1, 4])
        with v_col1:
            st.metric("VIX 恐慌指數", f"{v_val:.2f}", f"{v_chg:.2f}", delta_color="inverse")
        with v_col2:
            st.info(f"**市場當前情緒:** {v_status} | **對策:** {'避險為主' if v_val > 25 else '順勢操作'}")

        # 2. 即時警報摘要 (UI 保持你喜歡的風格)
        st.subheader("🔔 即時警報摘要")
        alert_cols = st.columns(len(symbols))
        
        # 儲存分析結果以便下方繪圖使用，避免重複抓取
        results = {}

        for idx, sym in enumerate(symbols):
            df_raw = fetch_data(sym, interval)
            df, trend, signal, alert, vol_spike = analyze_trend(df_raw, v_chg)
            results[sym] = (df, trend, signal, alert, vol_spike)
            
            with alert_cols[idx]:
                if alert:
                    # 如果 VIX 也在漲，警報顏色更深（error），否則用 warning
                    st.error(f"**{sym}**\n\n{alert}!") if v_chg > 0 else st.warning(f"**{sym}**\n\n{alert}!")
                elif vol_spike:
                    st.warning(f"**{sym}**\n\n量能異常!")
                else:
                    st.success(f"**{sym}**\n\n趨勢穩定")

        st.divider()
        st.subheader("📈 詳細走勢分析")

        for sym in symbols:
            df, trend, signal, alert, vol_spike = results[sym]
            with st.expander(f"查看 {sym} 詳情 - {trend} | {signal}", expanded=True):
                if df is not None:
                    col_info, col_chart = st.columns([1, 3])
                    with col_info:
                        curr_p = df['Close'].iloc[-1]
                        diff = curr_p - df['Close'].iloc[-2]
                        st.metric("當前價格", f"{curr_p:.2f}", f"{diff:.2f}")
                        st.write(f"**量能:** {'🔥 爆量' if vol_spike else '正常'}")
                        if alert: st.write(f"**訊號:** {alert}")
                    
                    with col_chart:
                        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
                        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_Fast'], name="Fast", line=dict(color='orange', width=1)), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_Slow'], name="Slow", line=dict(color='cyan', width=1)), row=1, col=1)
                        
                        # 成交量變色邏輯
                        v_colors = ['#ef5350' if df['Close'].iloc[i] < df['Open'].iloc[i] else '#26a69a' for i in range(len(df))]
                        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=v_colors, name="成交量"), row=2, col=1)
                        
                        fig.update_layout(height=380, margin=dict(t=20, b=0), xaxis_rangeslider_visible=False, showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error(f"{sym} 獲取失敗")

        time.sleep(60)
        st.rerun()
