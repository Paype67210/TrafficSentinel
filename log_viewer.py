#!/usr/bin/env python3
"""
Script de visualisation des logs Traffic Sentinel
Permet de suivre les logs en temps réel et d'analyser les opérations Freebox
"""

import os
import time
import argparse
from datetime import datetime, timedelta
import subprocess

def tail_log(log_file, lines=50):
    """Afficher les dernières lignes d'un fichier de log"""
    if not os.path.exists(log_file):
        print(f"❌ Fichier de log non trouvé: {log_file}")
        return
    
    try:
        result = subprocess.run(['tail', '-n', str(lines), log_file], 
                              capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        print(f"❌ Erreur lecture du log: {e}")
        return None

def follow_log(log_file):
    """Suivre un fichier de log en temps réel"""
    if not os.path.exists(log_file):
        print(f"❌ Fichier de log non trouvé: {log_file}")
        return
    
    print(f"📋 Suivi en temps réel de: {log_file}")
    print("   (Ctrl+C pour arrêter)")
    print("=" * 60)
    
    try:
        subprocess.run(['tail', '-f', log_file])
    except KeyboardInterrupt:
        print("\n✋ Arrêt du suivi des logs")

def analyze_freebox_logs(hours=24):
    """Analyser les logs Freebox des dernières heures"""
    log_file = "/var/log/traffic_sentinel/freebox_operations.log"
    
    if not os.path.exists(log_file):
        print(f"❌ Fichier de log Freebox non trouvé: {log_file}")
        return
    
    print(f"📊 Analyse des logs Freebox des dernières {hours}h")
    print("=" * 60)
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        # Filtrer les logs des dernières heures
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_logs = []
        
        for line in lines:
            try:
                # Extraire le timestamp (format: 2025-10-04 15:30:25)
                date_str = line.split(' - ')[0]
                log_time = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                if log_time >= cutoff_time:
                    recent_logs.append(line.strip())
            except:
                continue  # Ignorer les lignes mal formatées
        
        if not recent_logs:
            print("ℹ️ Aucun log Freebox récent trouvé")
            return
        
        # Statistiques
        total_ops = len(recent_logs)
        connections = len([l for l in recent_logs if "Connexion Freebox API établie" in l])
        blocks = len([l for l in recent_logs if "BLOQUÉE avec succès" in l])
        allows = len([l for l in recent_logs if "AUTORISÉE avec succès" in l])
        errors = len([l for l in recent_logs if "ERROR" in l])
        
        print(f"📈 Statistiques ({hours}h):")
        print(f"   🔄 Total opérations: {total_ops}")
        print(f"   🔌 Connexions API: {connections}")
        print(f"   🚫 Blocages réussis: {blocks}")
        print(f"   ✅ Autorisations réussies: {allows}")
        print(f"   ❌ Erreurs: {errors}")
        
        if errors > 0:
            print(f"\n⚠️ Dernières erreurs:")
            error_logs = [l for l in recent_logs if "ERROR" in l][-5:]
            for error in error_logs:
                print(f"   {error}")
        
        # Dernières opérations significatives
        print(f"\n📝 Dernières opérations:")
        significant_logs = [l for l in recent_logs if any(keyword in l for keyword in 
                          ["BLOQUÉE", "AUTORISÉE", "établie", "ERROR"])][-10:]
        
        for log in significant_logs:
            # Coloriser selon le type
            if "BLOQUÉE" in log:
                print(f"   🚫 {log}")
            elif "AUTORISÉE" in log:
                print(f"   ✅ {log}")
            elif "établie" in log:
                print(f"   🔌 {log}")
            elif "ERROR" in log:
                print(f"   ❌ {log}")
            else:
                print(f"   ℹ️ {log}")
        
    except Exception as e:
        print(f"❌ Erreur analyse des logs: {e}")

def check_log_health():
    """Vérifier l'état des fichiers de logs"""
    log_dir = "/var/log/traffic_sentinel"
    logs = {
        "Principal": f"{log_dir}/traffic_sentinel.log",
        "Freebox": f"{log_dir}/freebox_operations.log"
    }
    
    print("🏥 État des logs Traffic Sentinel")
    print("=" * 50)
    
    for name, path in logs.items():
        if os.path.exists(path):
            stat = os.stat(path)
            size = stat.st_size
            modified = datetime.fromtimestamp(stat.st_mtime)
            
            # Vérifier si le fichier a été modifié récemment
            age = datetime.now() - modified
            status = "🟢 Actif" if age < timedelta(minutes=10) else "🟡 Ancien" if age < timedelta(hours=1) else "🔴 Inactif"
            
            print(f"📄 {name}:")
            print(f"   📍 Chemin: {path}")
            print(f"   📏 Taille: {size:,} bytes")
            print(f"   🕐 Modifié: {modified.strftime('%Y-%m-%d %H:%M:%S')} ({age})")
            print(f"   📊 Statut: {status}")
            
            # Dernières lignes
            last_lines = tail_log(path, 3)
            if last_lines:
                print(f"   📝 Dernières entrées:")
                for line in last_lines.strip().split('\n')[-2:]:
                    if line.strip():
                        print(f"      {line}")
        else:
            print(f"❌ {name}: Fichier non trouvé ({path})")
        
        print()

def main():
    parser = argparse.ArgumentParser(description="Visualisation des logs Traffic Sentinel")
    parser.add_argument('action', choices=['tail', 'follow', 'analyze', 'health'], 
                       help="Action à effectuer")
    parser.add_argument('--log', choices=['main', 'freebox'], default='main',
                       help="Fichier de log à consulter")
    parser.add_argument('--lines', type=int, default=50,
                       help="Nombre de lignes à afficher (pour tail)")
    parser.add_argument('--hours', type=int, default=24,
                       help="Nombre d'heures à analyser (pour analyze)")
    
    args = parser.parse_args()
    
    log_files = {
        'main': '/var/log/traffic_sentinel/traffic_sentinel.log',
        'freebox': '/var/log/traffic_sentinel/freebox_operations.log'
    }
    
    if args.action == 'tail':
        log_file = log_files[args.log]
        print(f"📋 Dernières {args.lines} lignes de {log_file}")
        print("=" * 60)
        content = tail_log(log_file, args.lines)
        if content:
            print(content)
    
    elif args.action == 'follow':
        log_file = log_files[args.log]
        follow_log(log_file)
    
    elif args.action == 'analyze':
        analyze_freebox_logs(args.hours)
    
    elif args.action == 'health':
        check_log_health()

if __name__ == "__main__":
    main()