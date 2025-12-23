"""
AquaTrack MVP - Générateur de données synthétiques
===================================================

Ce script génère 3 datasets CSV pour le MVP :
1. baseline.csv : Situation actuelle (WUR = 1.65)
2. anomaly.csv : Avec anomalies (fuites, sur-rinçage)
3. optimized.csv : Après optimisations (WUR = 1.33)

Auteur: AquaTrack Team
Date: Décembre 2024
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Configuration de la génération aléatoire (reproductibilité)
np.random.seed(42)
random.seed(42)

# ============================================================
# PARAMÈTRES GLOBAUX
# ============================================================

# Période de simulation
START_DATE = datetime(2025, 1, 1, 0, 0, 0)
DAYS = 30
INTERVAL_MINUTES = 5
TOTAL_POINTS = DAYS * 24 * (60 // INTERVAL_MINUTES)  # 8640 points

# Production
PRODUCTION_NOMINAL = 1000  # L/h en fonctionnement
PRODUCTION_NIGHT_FACTOR = 0.7  # Réduction production la nuit

# Consommation eau - BASELINE
WUR_TARGET_BASELINE = 1.65
INLET_FLOW_BASE = 1450  # L/h moyen
TREATMENT_LOSS_PCT = 15  # % pertes au traitement
RINSE_FLOW_BASE = 185  # L/h moyen
RINSE_DURATION_MIN = 8  # minutes par cycle
CIP_DURATION_HOURS = 1.5
CIP_FLOW_RATE = 1000  # L/h pendant CIP
CIP_FREQUENCY_DAYS = 3.5  # Tous les 3-4 jours (2x/semaine)

# Qualité eau
CONDUCTIVITY_MEAN = 245
CONDUCTIVITY_STD = 5
TURBIDITY_MEAN = 0.6
TURBIDITY_STD = 0.1
TEMPERATURE_MEAN = 22
TEMPERATURE_STD = 2

# Bruit de mesure (réalisme capteurs)
NOISE_FACTOR = 0.05  # ±5%

# ============================================================
# FONCTIONS AUXILIAIRES
# ============================================================

def add_noise(value, factor=NOISE_FACTOR):
    """Ajoute du bruit gaussien pour simuler variabilité capteurs"""
    return value * (1 + np.random.normal(0, factor))

def get_shift(hour):
    """Détermine l'équipe selon l'heure"""
    if 6 <= hour < 14:
        return "morning"
    elif 14 <= hour < 22:
        return "afternoon"
    else:
        return "night"

def is_cip_time(timestamp, cip_schedule):
    """Vérifie si un CIP est en cours à ce timestamp"""
    for cip_start, cip_end in cip_schedule:
        if cip_start <= timestamp < cip_end:
            return True
    return False

def generate_cip_schedule(start_date, days, frequency_days=CIP_FREQUENCY_DAYS):
    """Génère le planning des CIP (Clean-In-Place)"""
    cip_schedule = []
    current_date = start_date
    
    while current_date < start_date + timedelta(days=days):
        # CIP commence à 14h (début après-midi, production réduite)
        cip_start = current_date.replace(hour=14, minute=0, second=0)
        cip_end = cip_start + timedelta(hours=CIP_DURATION_HOURS)
        
        if cip_start < start_date + timedelta(days=days):
            cip_schedule.append((cip_start, cip_end))
        
        current_date += timedelta(days=frequency_days)
    
    return cip_schedule

# ============================================================
# GÉNÉRATION DATASET BASELINE
# ============================================================

def generate_baseline_data():
    """
    Génère le dataset BASELINE (situation actuelle)
    WUR cible : 1.65 L/L
    """
    print("🔄 Génération du dataset BASELINE...")
    
    # Timestamps
    timestamps = [START_DATE + timedelta(minutes=INTERVAL_MINUTES * i) 
                  for i in range(TOTAL_POINTS)]
    
    # Planning CIP
    cip_schedule = generate_cip_schedule(START_DATE, DAYS)
    print(f"   📅 {len(cip_schedule)} événements CIP planifiés")
    
    data = {
        'timestamp': [],
        'scenario': [],
        'inlet_flow_lph': [],
        'post_treatment_flow_lph': [],
        'rinse_flow_lph': [],
        'cip_flow_lph': [],
        'production_lph': [],
        'conductivity_uS_cm': [],
        'turbidity_NTU': [],
        'temperature_C': [],
        'cip_active': [],
        'shift': [],
        'line_status': [],
        'wur': []
    }
    
    for ts in timestamps:
        hour = ts.hour
        shift = get_shift(hour)
        
        # Production (réduite la nuit)
        if shift == "night":
            production = PRODUCTION_NOMINAL * PRODUCTION_NIGHT_FACTOR
        else:
            production = PRODUCTION_NOMINAL
        production = add_noise(production, 0.03)
        
        # CIP en cours ?
        cip_active = is_cip_time(ts, cip_schedule)
        
        if cip_active:
            # Pendant CIP : forte consommation d'eau, production réduite
            cip_flow = CIP_FLOW_RATE
            inlet_flow = INLET_FLOW_BASE + cip_flow
            rinse_flow = RINSE_FLOW_BASE * 0.5  # Rinçage réduit pendant CIP
            production = production * 0.8  # Production ralentie
        else:
            cip_flow = 0
            inlet_flow = INLET_FLOW_BASE
            rinse_flow = RINSE_FLOW_BASE
        
        # Ajouter bruit réaliste
        inlet_flow = add_noise(inlet_flow, 0.04)
        rinse_flow = add_noise(rinse_flow, 0.06)
        
        # Post-traitement (pertes selon %)
        post_treatment_flow = inlet_flow * (1 - TREATMENT_LOSS_PCT / 100)
        post_treatment_flow = add_noise(post_treatment_flow, 0.03)
        
        # Qualité eau
        conductivity = add_noise(CONDUCTIVITY_MEAN, 0.02)
        turbidity = max(0.1, add_noise(TURBIDITY_MEAN, 0.15))
        temperature = add_noise(TEMPERATURE_MEAN, 0.05)
        
        # WUR
        wur = inlet_flow / production if production > 0 else 0
        
        # État ligne
        line_status = "running" if production > 500 else "stopped"
        
        # Ajouter au dataset
        data['timestamp'].append(ts)
        data['scenario'].append('baseline')
        data['inlet_flow_lph'].append(round(inlet_flow, 2))
        data['post_treatment_flow_lph'].append(round(post_treatment_flow, 2))
        data['rinse_flow_lph'].append(round(rinse_flow, 2))
        data['cip_flow_lph'].append(round(cip_flow, 2))
        data['production_lph'].append(round(production, 2))
        data['conductivity_uS_cm'].append(round(conductivity, 2))
        data['turbidity_NTU'].append(round(turbidity, 2))
        data['temperature_C'].append(round(temperature, 1))
        data['cip_active'].append(1 if cip_active else 0)
        data['shift'].append(shift)
        data['line_status'].append(line_status)
        data['wur'].append(round(wur, 3))
    
    df = pd.DataFrame(data)
    
    # Statistiques
    avg_wur = df['wur'].mean()
    total_water = df['inlet_flow_lph'].sum() / 1000  # en m³
    total_production = df['production_lph'].sum() / 1000  # en m³
    
    print(f"   ✅ WUR moyen : {avg_wur:.3f} L/L")
    print(f"   💧 Eau totale : {total_water:.1f} m³ ({total_water/DAYS:.1f} m³/jour)")
    print(f"   🏭 Production totale : {total_production:.1f} m³")
    
    return df

# ============================================================
# GÉNÉRATION DATASET AVEC ANOMALIES
# ============================================================

def generate_anomaly_data():
    """
    Génère le dataset ANOMALY (avec anomalies)
    Anomalies injectées :
    - Jour 16 : Fuite (+20% débit)
    - Jour 22 : Sur-rinçage (+50% durée)
    - Jour 28 : CIP non planifié
    """
    print("\n🔄 Génération du dataset ANOMALY...")
    
    # Partir du baseline
    df = generate_baseline_data()
    df['scenario'] = 'anomaly'
    
    # ANOMALIE 1 : Fuite jour 16, 14h00-22h00
    leak_start = START_DATE + timedelta(days=15, hours=14)
    leak_end = START_DATE + timedelta(days=15, hours=22)
    leak_mask = (df['timestamp'] >= leak_start) & (df['timestamp'] < leak_end)
    
    df.loc[leak_mask, 'inlet_flow_lph'] *= 1.20  # +20% débit
    print(f"   ⚠️  ANOMALIE 1 : Fuite injectée (jour 16, 14h-22h, +20% débit)")
    
    # ANOMALIE 2 : Sur-rinçage jour 22, 09h00-17h00
    overrinse_start = START_DATE + timedelta(days=21, hours=9)
    overrinse_end = START_DATE + timedelta(days=21, hours=17)
    overrinse_mask = (df['timestamp'] >= overrinse_start) & (df['timestamp'] < overrinse_end)
    
    df.loc[overrinse_mask, 'rinse_flow_lph'] *= 1.50  # +50% rinçage
    df.loc[overrinse_mask, 'inlet_flow_lph'] += df.loc[overrinse_mask, 'rinse_flow_lph'] * 0.3
    print(f"   ⚠️  ANOMALIE 2 : Sur-rinçage (jour 22, 09h-17h, +50% débit)")
    
    # ANOMALIE 3 : CIP non planifié jour 28, 15h30
    unplanned_cip_start = START_DATE + timedelta(days=27, hours=15, minutes=30)
    unplanned_cip_end = unplanned_cip_start + timedelta(hours=CIP_DURATION_HOURS)
    unplanned_cip_mask = (df['timestamp'] >= unplanned_cip_start) & (df['timestamp'] < unplanned_cip_end)
    
    df.loc[unplanned_cip_mask, 'cip_flow_lph'] = CIP_FLOW_RATE
    df.loc[unplanned_cip_mask, 'cip_active'] = 1
    df.loc[unplanned_cip_mask, 'inlet_flow_lph'] += CIP_FLOW_RATE
    df.loc[unplanned_cip_mask, 'production_lph'] *= 0.8
    print(f"   ⚠️  ANOMALIE 3 : CIP non planifié (jour 28, 15h30)")
    
    # Recalculer WUR
    df['wur'] = df['inlet_flow_lph'] / df['production_lph']
    df['wur'] = df['wur'].round(3)
    
    # Statistiques
    avg_wur = df['wur'].mean()
    print(f"   ✅ WUR moyen (avec anomalies) : {avg_wur:.3f} L/L")
    
    return df

# ============================================================
# GÉNÉRATION DATASET OPTIMISÉ
# ============================================================

def generate_optimized_data():
    """
    Génère le dataset OPTIMIZED (situation optimisée)
    Optimisations appliquées :
    - Réduction rinçage : -25%
    - Amélioration traitement : pertes 15% → 12%
    - Optimisation CIP : -10% consommation
    WUR cible : 1.33 L/L
    """
    print("\n🔄 Génération du dataset OPTIMIZED...")
    
    # Partir du baseline
    df = generate_baseline_data()
    df['scenario'] = 'optimized'
    
    # OPTIMISATION 1 : Réduction rinçage -25%
    df['rinse_flow_lph'] *= 0.75
    print(f"   ✅ OPTIMISATION 1 : Rinçage réduit de 25%")
    
    # OPTIMISATION 2 : Amélioration récupération traitement (12% pertes vs 15%)
    # On augmente le post_treatment en gardant inlet constant
    improvement_factor = (100 - 12) / (100 - 15)  # 88/85 = 1.035
    df['post_treatment_flow_lph'] *= improvement_factor
    
    # Réduire légèrement inlet pour compenser (meilleure efficacité)
    df['inlet_flow_lph'] *= 0.97
    print(f"   ✅ OPTIMISATION 2 : Pertes traitement réduites (15% → 12%)")
    
    # OPTIMISATION 3 : CIP optimisé -10%
    df.loc[df['cip_active'] == 1, 'cip_flow_lph'] *= 0.90
    df.loc[df['cip_active'] == 1, 'inlet_flow_lph'] -= df.loc[df['cip_active'] == 1, 'cip_flow_lph'] * 0.1
    print(f"   ✅ OPTIMISATION 3 : CIP optimisé (-10% consommation)")
    
    # OPTIMISATION 4 : Réduction pertes diverses (ajustement inlet global)
    df['inlet_flow_lph'] *= 0.90
    
    # Recalculer WUR
    df['wur'] = df['inlet_flow_lph'] / df['production_lph']
    df['wur'] = df['wur'].round(3)
    
    # Statistiques
    avg_wur = df['wur'].mean()
    total_water = df['inlet_flow_lph'].sum() / 1000
    baseline_water = 13200 * DAYS / 1000  # Estimation baseline
    savings = baseline_water - total_water
    
    print(f"   ✅ WUR moyen (optimisé) : {avg_wur:.3f} L/L")
    print(f"   💧 Économie d'eau : {savings:.1f} m³ sur {DAYS} jours")
    print(f"   📊 Réduction WUR : {((1.65 - avg_wur) / 1.65 * 100):.1f}%")
    
    return df

# ============================================================
# VALIDATION DES DATASETS
# ============================================================

def validate_dataset(df, scenario_name):
    """Valide la cohérence d'un dataset"""
    print(f"\n🔍 Validation du dataset {scenario_name.upper()}...")
    
    errors = []
    warnings = []
    
    # Test 1 : Plages de valeurs
    if (df['wur'] < 1.0).any() or (df['wur'] > 3.0).any():
        errors.append(f"WUR hors plage [1.0, 3.0] détecté")
    
    if (df['production_lph'] < 0).any() or (df['production_lph'] > 1500).any():
        errors.append(f"Production hors plage [0, 1500] détectée")
    
    if (df['conductivity_uS_cm'] < 100).any() or (df['conductivity_uS_cm'] > 400).any():
        warnings.append(f"Conductivité hors plage typique [100, 400]")
    
    # Test 2 : Bilan de masse approximatif
    df['total_out'] = df['post_treatment_flow_lph'] + df['rinse_flow_lph'] + df['cip_flow_lph']
    df['balance_error'] = abs(df['inlet_flow_lph'] - df['total_out']) / df['inlet_flow_lph']
    
    high_error = (df['balance_error'] > 0.30).sum()
    if high_error > len(df) * 0.05:  # Si > 5% des points ont erreur > 30%
        warnings.append(f"{high_error} points avec erreur bilan de masse > 30%")
    
    # Test 3 : Valeurs manquantes
    if df.isnull().sum().sum() > 0:
        errors.append(f"Valeurs manquantes détectées")
    
    # Résultats
    if len(errors) == 0 and len(warnings) == 0:
        print(f"   ✅ Dataset valide - Aucune erreur")
    else:
        if errors:
            print(f"   ❌ ERREURS détectées :")
            for e in errors:
                print(f"      - {e}")
        if warnings:
            print(f"   ⚠️  Avertissements :")
            for w in warnings:
                print(f"      - {w}")
    
    return len(errors) == 0

# ============================================================
# EXPORT CSV
# ============================================================

def export_to_csv(df, filename):
    """Exporte le dataframe en CSV"""
    df.to_csv(filename, index=False, date_format='%Y-%m-%d %H:%M:%S')
    file_size = len(df) * df.memory_usage(deep=True).sum() / 1024 / 1024
    print(f"   💾 Exporté : {filename} ({len(df)} lignes, ~{file_size:.2f} MB)")

# ============================================================
# STATISTIQUES RÉCAPITULATIVES
# ============================================================

def print_summary_stats(df_baseline, df_anomaly, df_optimized):
    """Affiche un tableau récapitulatif des 3 scénarios"""
    print("\n" + "="*70)
    print("📊 RÉCAPITULATIF DES 3 SCÉNARIOS")
    print("="*70)
    
    scenarios = [
        ("BASELINE", df_baseline),
        ("ANOMALY", df_anomaly),
        ("OPTIMIZED", df_optimized)
    ]
    
    print(f"\n{'Indicateur':<30} {'Baseline':<15} {'Anomaly':<15} {'Optimized':<15}")
    print("-" * 75)
    
    for label, df in scenarios:
        wur = df['wur'].mean()
        water = df['inlet_flow_lph'].sum() / 1000
        prod = df['production_lph'].sum() / 1000
        
        if label == "BASELINE":
            baseline_wur = wur
            baseline_water = water
    
    # WUR
    print(f"{'WUR moyen (L/L)':<30} "
          f"{df_baseline['wur'].mean():<15.3f} "
          f"{df_anomaly['wur'].mean():<15.3f} "
          f"{df_optimized['wur'].mean():<15.3f}")
    
    # Eau totale
    print(f"{'Eau totale (m³)':<30} "
          f"{df_baseline['inlet_flow_lph'].sum()/1000:<15.1f} "
          f"{df_anomaly['inlet_flow_lph'].sum()/1000:<15.1f} "
          f"{df_optimized['inlet_flow_lph'].sum()/1000:<15.1f}")
    
    # Production
    print(f"{'Production (m³)':<30} "
          f"{df_baseline['production_lph'].sum()/1000:<15.1f} "
          f"{df_anomaly['production_lph'].sum()/1000:<15.1f} "
          f"{df_optimized['production_lph'].sum()/1000:<15.1f}")
    
    # Économie vs baseline
    baseline_water = df_baseline['inlet_flow_lph'].sum() / 1000
    optimized_water = df_optimized['inlet_flow_lph'].sum() / 1000
    savings = baseline_water - optimized_water
    savings_pct = (savings / baseline_water) * 100
    
    print("-" * 75)
    print(f"{'Économie optimisé vs baseline':<30} "
          f"-- "
          f"{'':15} "
          f"{savings:.1f} m³ (-{savings_pct:.1f}%)")
    
    print("="*70 + "\n")

# ============================================================
# FONCTION PRINCIPALE
# ============================================================

def main():
    """Fonction principale - Génère les 3 datasets"""
    print("\n" + "="*70)
    print("🚀 AQUATRACK MVP - GÉNÉRATEUR DE DONNÉES SYNTHÉTIQUES")
    print("="*70)
    print(f"📅 Période : {DAYS} jours ({TOTAL_POINTS} points)")
    print(f"⏱️  Résolution : {INTERVAL_MINUTES} minutes")
    print("="*70 + "\n")
    
    # Générer les 3 datasets
    df_baseline = generate_baseline_data()
    df_anomaly = generate_anomaly_data()
    df_optimized = generate_optimized_data()
    
    # Valider
    validate_dataset(df_baseline, "baseline")
    validate_dataset(df_anomaly, "anomaly")
    validate_dataset(df_optimized, "optimized")
    
    # Exporter
    print("\n📦 Export des fichiers CSV...")
    export_to_csv(df_baseline, "baseline.csv")
    export_to_csv(df_anomaly, "anomaly.csv")
    export_to_csv(df_optimized, "optimized.csv")
    
    # Statistiques finales
    print_summary_stats(df_baseline, df_anomaly, df_optimized)
    
    print("✅ Génération terminée avec succès !")
    print("\n📁 Fichiers générés :")
    print("   - baseline.csv")
    print("   - anomaly.csv")
    print("   - optimized.csv")
    print("\n💡 Prochaine étape : Charger ces fichiers dans le dashboard\n")

if __name__ == "__main__":
    main()