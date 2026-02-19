import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- 頁面配置 ---
st.set_page_config(page_title="專業級多股實時監控", layout="wide")
st.title("🚀 專業實時趨勢監控 (含 VIX 與 RSI 多重預警)")

# --- 側邊欄 ---
st.sidebar.header("核心設定")
default_symbols = "AAPL, NVDA, TSLA, 2330.TW, ^VIX"
input_symbols = st.sidebar.text_input("監控列表 (逗號分隔)", "AAPL, NVDA, TSLA, QQQ")
symbols = [s.strip().upper() for s in input_symbols.split(",")]

interval = st.sidebar.selectbox("資料頻率", ("1m", "2m", "5m"), index=0)
ema_fast_val = st.sidebar.slider("快速 EMA", 5, 20, 9)
ema_slow_val = st.sidebar.slider("慢速 EMA", 21, 50, 21)

# --- 核心運算函數 ---
def fetch_data(ticker, interval):
    try:
        data = yf.download(ticker, period="1d", interval=interval, progress=False)
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
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_vix_info():
    vix = fetch_data("^VIX", "2m")
    if vix is None or len(vix) < 2: return 20.0, 0.0
    return float(vix['Close'].iloc[-1]), float(vix['Close'].iloc[-1] - vix['Close'].iloc[-2])

def analyze_stock(df, vix_chg):
    if df is None or len(df) < 25:
        return None, {}
    
    # 計算指標
    df['EMA_F'] = df['Close'].ewm(span=ema_fast_val, adjust=False).mean()
    df['EMA_S'] = df['Close'].ewm(span=ema_slow_val, adjust=False).mean()
    df['RSI'] = calculate_rsi(df['Close'])
    df['Vol_MA'] = df['Volume'].rolling(window=10).mean()
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 數值提取
    curr_p = float(last['Close'])
    prev_p = float(prev['Close'])
    p_chg_pct = ((curr_p - prev_p) / prev_p) * 100
    curr_rsi = float(last['RSI'])
    vol_ratio = float(last['Volume'] / last['Vol_MA'])
    
    # 訊號判斷
    signal = "穩定"
    alert_level = "success" # success, warning, error
    
    # 趨勢反轉邏輯
    is_gold = prev['EMA_F'] <= prev['EMA_S'] and last['EMA_F'] > last['EMA_S']
    is_death = prev['EMA_F'] >= prev['EMA_S'] and last['EMA_F'] < last['EMA_S']
    
    msg = ""
    if is_gold:
        msg = "🚀 黃金交叉"
        alert_level = "error" if vix_chg < 0 else "warning"
    elif is_death:
        msg = "💀 死亡交叉"
        alert_level = "error"
    elif curr_rsi > 75:
        msg = "⚠️ RSI 超買"
        alert_level = "warning"
    elif curr_rsi < 25:
        msg = "📉 RSI 超賣"
        alert_level = "warning"
    
    # 量能
    vol_msg = "🔥 爆量" if vol_ratio > 2.0 else "正常"
    
    info = {
        "price": curr_p,
        "pct": p_chg_pct,
        "rsi": curr_rsi,
        "vol_ratio": vol_ratio,
        "trend": "多頭" if last['EMA_F'] > last['EMA_S'] else "空頭",
        "msg": msg,
        "alert_level": alert_level,
        "vol_msg": vol_msg
    }
    return df, info

# --- 主體介面 ---
placeholder = st.empty()

while True:
    with placeholder.container():
        # 1. VIX 全局風險提示
        vix_val, vix_chg = get_vix_info()
        v_col1, v_col2 = st.columns([1, 4])
        v_col1.metric("VIX 指數", f"{vix_val:.2f}", f"{v_chg:.2f}", delta_color="inverse")
        with v_col2:
            if vix_chg > 0.5:
                st.error(f"🚨 市場恐慌升溫中！當前 VIX 變動: +{v_chg:.2f}。建議縮減個股多單。")
            else:
                st.info("✅ 市場情緒相對穩定，技術面訊號參考價值高。")

        # 2. 即時警報摘要 (強化版內容)
        st.subheader("🔔 即時警報摘要")
        alert_cols = st.columns(len(symbols))
        
        stock_results = {}

        for idx, sym in enumerate(symbols):
            df_raw = fetch_data(sym, interval)
            df, info = analyze_stock(df_raw, vix_chg)
            stock_results[sym] = (df, info)
            
            with alert_cols[idx]:
                if info:
                    # 根據警報等級顯示顏色
                    if info['alert_level'] == "error":
                        st.error(f"**{sym} | {info['msg']}**")
                    elif info['alert_level'] == "warning":
                        st.warning(f"**{sym} | {info['msg']}**")
                    else:
                        st.success(f"**{sym} | 趨勢{info['trend']}**")
                    
                    # 摘要內容填充
                    st.caption(f"價格: {info['price']:.2f} ({info['pct']:+.2f}%)")
                    st.caption(f"RSI: {info['rsi']:.1f} | 量比: {info['vol_ratio']:.1f}x")
                    if info['vol_ratio'] > 2:
                        st.markdown(f"<span style='color:red; font-size:12px;'>{info['vol_msg']}偵測</span>", unsafe_allow_html=True)
                else:
                    st.write(f"{sym}\n載入中...")

        st.divider()
        st.subheader("📈 詳細技術走勢")

        for sym in symbols:
            df, info = stock_results[sym]
            if df is not None:
                with st.expander(f"查看 {sym} 詳情分析表", expanded=True):
                    c_left, c_right = st.columns([1, 4])
                    with c_left:
                        st.write(f"**核心數據**")
                        st.write(f"趨勢: `{info['trend']}`")
                        st.write(f"RSI(14): `{info['rsi']:.2f}`")
                        st.write(f"成交量比: `{info['vol_ratio']:.2f}x`平衡")
                        if vix_chg > 0 and info['trend'] == "空頭":
                            st.write("🆘 **聯動警告: VIX與股價同步看跌**")
                    
                    with c_right:
                        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
                        # K線
                        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_F'], name="EMA快", line=dict(color='orange', width=1.5)), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_S'], name="EMA慢", line=dict(color='cyan', width=1.5)), row=1, col=1)
                        
                        # 成交量
                        v_colors = ['red' if df['Close'].iloc[i] < df['Open'].iloc[i] else 'green' for i in range(len(df))]
                        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=v_colors), row=2, col=1)
                        
                        fig.update_layout(height=400, margin=dict(t=0, b=0), xaxis_rangeslider_visible=False, showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)

        time.sleep(60)
        st.rerun()
