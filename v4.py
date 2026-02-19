import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- 頁面配置 ---
st.set_page_config(page_title="專業級多股實時監控", layout="wide")
st.title("🚀 專業實時趨勢監控 (含支撐壓力與 VIX 聯動)")

# --- 核心運算函數 ---
def fetch_data(ticker, interval):
    try:
        data = yf.download(ticker, period="2d", interval=interval, progress=False) # 取2天數據以計算精準Pivot
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except:
        return None

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    if loss.iloc[-1] == 0: return 100.0
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_vix_info():
    vix = fetch_data("^VIX", "2m")
    if vix is None or len(vix) < 2: return 20.0, 0.0
    curr_v = float(vix['Close'].iloc[-1])
    v_chg = curr_v - float(vix['Close'].iloc[-2])
    return curr_v, v_chg

def analyze_stock(df, v_chg, ema_fast_val, ema_slow_val):
    if df is None or len(df) < 25: return None, None
    
    # 1. 支撐壓力位計算 (基於前一根大週期或今日波動)
    high_p = float(df['High'].max())
    low_p = float(df['Low'].min())
    close_p = float(df['Close'].iloc[-1])
    
    pivot = (high_p + low_p + close_p) / 3
    res_1 = (2 * pivot) - low_p
    sup_1 = (2 * pivot) - high_p

    # 2. 指標計算
    df['EMA_F'] = df['Close'].ewm(span=ema_fast_val, adjust=False).mean()
    df['EMA_S'] = df['Close'].ewm(span=ema_slow_val, adjust=False).mean()
    df['RSI'] = calculate_rsi(df['Close'])
    df['Vol_MA'] = df['Volume'].rolling(window=10).mean()
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    curr_p = float(last['Close'])
    
    # 3. 警報邏輯
    msg = "趨勢穩定"
    alert_level = "success"
    
    if prev['EMA_F'] <= prev['EMA_S'] and last['EMA_F'] > last['EMA_S']:
        msg = "🚀 黃金交叉"; alert_level = "error" if v_chg > 0.2 else "warning"
    elif prev['EMA_F'] >= prev['EMA_S'] and last['EMA_F'] < last['EMA_S']:
        msg = "💀 死亡交叉"; alert_level = "error"
    elif curr_p >= res_1 * 0.995: # 距離壓力位 0.5% 以內
        msg = "🧱 接近壓力區"; alert_level = "warning"
    elif curr_p <= sup_1 * 1.005: # 距離支撐位 0.5% 以內
        msg = "🛡️ 接近支撐區"; alert_level = "success"

    info = {
        "price": curr_p,
        "day_pct": ((curr_p - df['Open'].iloc[0]) / df['Open'].iloc[0]) * 100,
        "rsi": float(last['RSI']),
        "vol_ratio": float(last['Volume'] / last['Vol_MA']),
        "res": res_1, "sup": sup_1,
        "msg": msg, "alert_level": alert_level
    }
    return df, info

# --- 主體介面 ---
st.sidebar.header("監控參數")
symbols = [s.strip().upper() for s in st.sidebar.text_input("監控列表", "AAPL, NVDA, TSLA, 2330.TW").split(",")]
interval = st.sidebar.selectbox("頻率", ("1m", "2m", "5m"), index=0)
ema_f_val = st.sidebar.slider("快速 EMA", 5, 20, 9)
ema_s_val = st.sidebar.slider("慢速 EMA", 21, 50, 21)

placeholder = st.empty()

while True:
    with placeholder.container():
        v_val, v_chg = get_vix_info()
        v_col1, v_col2 = st.columns([1, 4])
        v_col1.metric("VIX 恐慌指數", f"{v_val:.2f}", f"{v_chg:.2f}", delta_color="inverse")
        with v_col2:
            st.info(f"當前環境: {'🔴 風險較高，注意壓力位突破失敗' if v_chg > 0 else '🟢 環境穩定，支撐位有效性高'}")

        st.subheader("🔔 即時警報與支撐壓力摘要")
        cols = st.columns(len(symbols))
        stock_results = {}

        for idx, sym in enumerate(symbols):
            df_raw = fetch_data(sym, interval)
            df, info = analyze_stock(df_raw, v_chg, ema_f_val, ema_s_val)
            stock_results[sym] = (df, info)
            with cols[idx]:
                if info:
                    if info['alert_level'] == "error": st.error(f"**{sym} | {info['msg']}**")
                    elif info['alert_level'] == "warning": st.warning(f"**{sym} | {info['msg']}**")
                    else: st.success(f"**{sym} | {info['msg']}**")
                    st.caption(f"支撐: {info['sup']:.2f} | 壓力: {info['res']:.2f}")
                    st.caption(f"RSI: {info['rsi']:.1f} | 量比: {info['vol_ratio']:.1f}x")
        
        st.divider()
        for sym in symbols:
            df, info = stock_results[sym]
            if df is not None:
                with st.expander(f"查看 {sym} 詳情", expanded=True):
                    c1, c2 = st.columns([1, 4])
                    with c1:
                        st.metric("即時價", f"{info['price']:.2f}", f"{info['day_pct']:.2f}%")
                        dist_res = ((info['res'] - info['price']) / info['price']) * 100
                        st.write(f"距離壓力: `{dist_res:+.2f}%`")
                    with c2:
                        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
                        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K"), row=1, col=1)
                        # 畫出支撐壓力線
                        fig.add_hline(y=info['res'], line_dash="dash", line_color="red", annotation_text="壓力位 R1", row=1, col=1)
                        fig.add_hline(y=info['sup'], line_dash="dash", line_color="green", annotation_text="支撐位 S1", row=1, col=1)
                        
                        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_F'], name="EMA F", line=dict(color='orange', width=1)), row=1, col=1)
                        fig.update_layout(height=350, margin=dict(t=0, b=0), xaxis_rangeslider_visible=False, showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)

        time.sleep(60)
        st.rerun()
