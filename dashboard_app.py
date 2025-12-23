"""
AquaTrack MVP - Dashboard Principal
====================================

Dashboard interactif avec simulation temps réel pour monitoring
de la consommation d'eau dans une ligne de production Coca-Cola

Auteur: AquaTrack Team
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import numpy as np

# ============================================================
# CONFIGURATION DE LA PAGE
# ============================================================

st.set_page_config(
    page_title="AquaTrack - Water Monitoring",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .kpi-value {
        font-size: 2.5rem;
        font-weight: bold;
    }
    .kpi-label {
        font-size: 1rem;
        opacity: 0.9;
    }
    .alert-high {
        background-color: #ff4444;
        color: white;
        padding: 1rem;
        border-radius: 5px;
        margin: 0.5rem 0;
    }
    .alert-medium {
        background-color: #ffbb33;
        color: white;
        padding: 1rem;
        border-radius: 5px;
        margin: 0.5rem 0;
    }
    .success-box {
        background-color: #00C851;
        color: white;
        padding: 1rem;
        border-radius: 5px;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# CHARGEMENT DES DONNÉES
# ============================================================

@st.cache_data
def load_data(scenario):
    """Charge le dataset correspondant au scénario"""
    try:
        filename = f"{scenario}.csv"
        df = pd.read_csv(filename, parse_dates=['timestamp'])
        return df
    except FileNotFoundError:
        st.error(f"❌ Fichier {filename} introuvable. Veuillez d'abord exécuter generate_data.py")
        st.stop()

@st.cache_data
def get_daily_aggregates(df):
    """Calcule les agrégations quotidiennes"""
    df['date'] = df['timestamp'].dt.date
    daily = df.groupby('date').agg({
        'inlet_flow_lph': 'sum',
        'production_lph': 'sum',
        'wur': 'mean',
        'rinse_flow_lph': 'sum',
        'cip_flow_lph': 'sum'
    }).reset_index()
    
    daily['inlet_flow_m3'] = daily['inlet_flow_lph'] / 1000
    daily['production_L'] = daily['production_lph']
    
    return daily

# ============================================================
# DÉTECTION D'ALERTES
# ============================================================

def detect_alerts(df_current):
    """Détecte les alertes sur les données actuelles"""
    alerts = []
    
    # Alerte WUR élevé
    if df_current['wur'].iloc[-1] > 1.85:
        alerts.append({
            'type': 'WUR Critique',
            'severity': 'HIGH',
            'message': f"WUR actuel : {df_current['wur'].iloc[-1]:.2f} L/L (> 1.85)",
            'time': df_current['timestamp'].iloc[-1]
        })
    elif df_current['wur'].iloc[-1] > 1.70:
        alerts.append({
            'type': 'WUR Élevé',
            'severity': 'MEDIUM',
            'message': f"WUR actuel : {df_current['wur'].iloc[-1]:.2f} L/L (> 1.70)",
            'time': df_current['timestamp'].iloc[-1]
        })
    
    # Alerte débit anormal (fuite potentielle)
    if len(df_current) > 12:  # Au moins 1h de données
        baseline_inlet = df_current['inlet_flow_lph'].iloc[-13:-1].mean()
        current_inlet = df_current['inlet_flow_lph'].iloc[-1]
        deviation = ((current_inlet - baseline_inlet) / baseline_inlet) * 100
        
        if deviation > 15:
            alerts.append({
                'type': 'Fuite Suspectée',
                'severity': 'HIGH',
                'message': f"Débit entrée +{deviation:.1f}% vs moyenne (fuite possible)",
                'time': df_current['timestamp'].iloc[-1]
            })
    
    # Alerte sur-rinçage
    if df_current['rinse_flow_lph'].iloc[-1] > 250:
        alerts.append({
            'type': 'Sur-rinçage',
            'severity': 'MEDIUM',
            'message': f"Débit rinçage : {df_current['rinse_flow_lph'].iloc[-1]:.0f} L/h (> 250)",
            'time': df_current['timestamp'].iloc[-1]
        })
    
    return alerts

# ============================================================
# INITIALISATION SESSION STATE
# ============================================================

if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'is_playing' not in st.session_state:
    st.session_state.is_playing = False
if 'playback_speed' not in st.session_state:
    st.session_state.playback_speed = 1

# ============================================================
# SIDEBAR - CONTRÔLES
# ============================================================

st.sidebar.markdown("# 💧 AquaTrack")
st.sidebar.markdown("### Monitoring Consommation Eau")
st.sidebar.markdown("---")

# Sélection scénario
scenario = st.sidebar.selectbox(
    "📊 Scénario",
    ["baseline", "anomaly", "optimized"],
    format_func=lambda x: {
        "baseline": "📍 Baseline (WUR 1.65)",
        "anomaly": "⚠️ Avec anomalies",
        "optimized": "✅ Optimisé (WUR 1.33)"
    }[x]
)

# Charger données
df = load_data(scenario)
total_points = len(df)

st.sidebar.markdown("---")
st.sidebar.markdown("### ⏯️ Contrôles Temps Réel")

# Slider temporel
col1, col2 = st.sidebar.columns([3, 1])
with col1:
    st.session_state.current_index = st.slider(
        "Position temporelle",
        0,
        total_points - 1,
        st.session_state.current_index,
        label_visibility="collapsed"
    )

# Boutons Play/Pause
col_play, col_pause, col_reset = st.sidebar.columns(3)
with col_play:
    if st.button("▶️"):
        st.session_state.is_playing = True
with col_pause:
    if st.button("⏸️"):
        st.session_state.is_playing = False
with col_reset:
    if st.button("🔄"):
        st.session_state.current_index = 0
        st.session_state.is_playing = False

# Vitesse de lecture
st.session_state.playback_speed = st.sidebar.select_slider(
    "⏩ Vitesse",
    options=[0.5, 1, 2, 5, 10],
    value=st.session_state.playback_speed,
    format_func=lambda x: f"{x}x"
)

# Affichage temps actuel
current_timestamp = df.iloc[st.session_state.current_index]['timestamp']
st.sidebar.markdown(f"**🕐 Temps actuel:**")
st.sidebar.info(f"{current_timestamp.strftime('%Y-%m-%d %H:%M')}")

progress = st.session_state.current_index / total_points
st.sidebar.progress(progress)
st.sidebar.caption(f"Point {st.session_state.current_index + 1} / {total_points}")

# ============================================================
# DONNÉES ACTUELLES (jusqu'à current_index)
# ============================================================

df_current = df.iloc[:st.session_state.current_index + 1].copy()

# ============================================================
# HEADER PRINCIPAL
# ============================================================

st.markdown('<h1 class="main-header">💧 AquaTrack - Monitoring de la consommation d\'eau en Temps Réel</h1>', 
            unsafe_allow_html=True)
st.markdown(f"**Ligne de production:** PET Casablanca | **Scénario:** {scenario.upper()}")
st.markdown("---")

# ============================================================
# KPIs PRINCIPAUX
# ============================================================

col1, col2, col3, col4 = st.columns(4)

# KPI 1 : WUR actuel
with col1:
    current_wur = df_current['wur'].iloc[-1] if len(df_current) > 0 else 0
    wur_color = "🔴" if current_wur > 1.85 else "🟡" if current_wur > 1.70 else "🟢"
    st.metric(
        label="💧 WUR Actuel",
        value=f"{current_wur:.2f} L/L",
        delta=f"{wur_color}",
        delta_color="off"
    )

# KPI 2 : Eau consommée aujourd'hui
with col2:
    if len(df_current) > 0:
        current_date = df_current['timestamp'].iloc[-1].date()
        today_data = df_current[df_current['timestamp'].dt.date == current_date]
        water_today = today_data['inlet_flow_lph'].sum() / 1000
    else:
        water_today = 0
    
    st.metric(
        label="🚰 Eau Aujourd'hui",
        value=f"{water_today:.1f} m³",
        delta=None
    )

# KPI 3 : Production aujourd'hui
with col3:
    if len(df_current) > 0:
        prod_today = today_data['production_lph'].sum()
    else:
        prod_today = 0
    
    st.metric(
        label="🏭 Production Aujourd'hui",
        value=f"{prod_today:.0f} L",
        delta=None
    )

# KPI 4 : Économie potentielle
with col4:
    if scenario == "optimized" and len(df_current) > 0:
        # Comparer avec baseline
        df_baseline = load_data("baseline")
        df_baseline_current = df_baseline.iloc[:st.session_state.current_index + 1]
        baseline_water = df_baseline_current['inlet_flow_lph'].sum() / 1000
        current_water = df_current['inlet_flow_lph'].sum() / 1000
        savings = baseline_water - current_water
        
        st.metric(
            label="💰 Économie vs Baseline",
            value=f"{savings:.1f} m³",
            delta=f"-{(savings/baseline_water*100):.1f}%",
            delta_color="normal"
        )
    else:
        st.metric(
            label="🎯 WUR Cible",
            value="1.45 L/L",
            delta=None
        )

st.markdown("---")

# ============================================================
# GRAPHIQUE TEMPS RÉEL
# ============================================================

st.markdown("### 📈 Consommation et Production - Temps Réel")

if len(df_current) > 0:
    # Créer graphique avec dernières 24h (288 points)
    window_size = min(288, len(df_current))
    df_window = df_current.iloc[-window_size:]
    
    fig = go.Figure()
    
    # Ligne inlet
    fig.add_trace(go.Scatter(
        x=df_window['timestamp'],
        y=df_window['inlet_flow_lph'],
        name='Eau Entrée',
        line=dict(color='#1f77b4', width=2),
        fill='tozeroy',
        fillcolor='rgba(31, 119, 180, 0.1)'
    ))
    
    # Ligne production
    fig.add_trace(go.Scatter(
        x=df_window['timestamp'],
        y=df_window['production_lph'],
        name='Production',
        line=dict(color='#2ca02c', width=2)
    ))
    
    # Ligne rinçage
    fig.add_trace(go.Scatter(
        x=df_window['timestamp'],
        y=df_window['rinse_flow_lph'],
        name='Rinçage',
        line=dict(color='#ff7f0e', width=1, dash='dot')
    ))
    
    # Marqueurs CIP
    cip_data = df_window[df_window['cip_active'] == 1]
    if len(cip_data) > 0:
        fig.add_trace(go.Scatter(
            x=cip_data['timestamp'],
            y=cip_data['inlet_flow_lph'],
            name='CIP',
            mode='markers',
            marker=dict(color='red', size=8, symbol='diamond')
        ))
    
    fig.update_layout(
        height=400,
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_title="Temps",
        yaxis_title="Débit (L/h)",
        template="plotly_white"
    )
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("⏳ En attente de données...")

# ============================================================
# ALERTES EN TEMPS RÉEL
# ============================================================

st.markdown("### ⚠️ Alertes et Notifications")

if len(df_current) > 12:  # Au moins 1h de données
    alerts = detect_alerts(df_current)
    
    if len(alerts) > 0:
        for alert in alerts:
            if alert['severity'] == 'HIGH':
                st.markdown(f'<div class="alert-high">🚨 <strong>{alert["type"]}</strong><br>{alert["message"]}</div>', 
                           unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="alert-medium">⚠️ <strong>{alert["type"]}</strong><br>{alert["message"]}</div>', 
                           unsafe_allow_html=True)
    else:
        st.markdown('<div class="success-box">✅ Aucune alerte - Fonctionnement normal</div>', 
                   unsafe_allow_html=True)
else:
    st.info("ℹ️ Collecte de données en cours... (minimum 1h requis pour détection)")

# ============================================================
# STATISTIQUES RÉCENTES
# ============================================================

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 📊 Statistiques dernières 24h")
    if len(df_current) >= 288:
        last_24h = df_current.iloc[-288:]
        stats_df = pd.DataFrame({
            'Indicateur': ['WUR moyen', 'WUR min', 'WUR max', 'Eau totale', 'Production totale'],
            'Valeur': [
                f"{last_24h['wur'].mean():.2f} L/L",
                f"{last_24h['wur'].min():.2f} L/L",
                f"{last_24h['wur'].max():.2f} L/L",
                f"{last_24h['inlet_flow_lph'].sum() / 1000:.1f} m³",
                f"{last_24h['production_lph'].sum():.0f} L"
            ]
        })
        st.dataframe(stats_df, use_container_width=True, hide_index=True)
    else:
        st.info("⏳ Données insuffisantes (< 24h)")

with col2:
    st.markdown("#### 🎯 Comparaison avec Objectifs")
    target_wur = 1.45
    current_avg_wur = df_current['wur'].mean() if len(df_current) > 0 else 0
    gap = current_avg_wur - target_wur
    
    comparison_df = pd.DataFrame({
        'Métrique': ['WUR Actuel', 'WUR Cible', 'Écart'],
        'Valeur': [
            f"{current_avg_wur:.2f} L/L",
            f"{target_wur:.2f} L/L",
            f"{gap:+.2f} L/L ({'🔴' if gap > 0 else '🟢'})"
        ]
    })
    st.dataframe(comparison_df, use_container_width=True, hide_index=True)

# ============================================================
# AUTO-REFRESH (mode Play)
# ============================================================

if st.session_state.is_playing and st.session_state.current_index < total_points - 1:
    # Calculer le délai en fonction de la vitesse
    delay = 0.5 / st.session_state.playback_speed
    time.sleep(delay)
    st.session_state.current_index += 1
    st.rerun()

# ============================================================
# FOOTER
# ============================================================

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; padding: 1rem;'>
    💧 AquaTrack MVP | Développé pour l'optimisation de la consommation d'eau | 2024-2025
</div>
""", unsafe_allow_html=True)