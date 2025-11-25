#!/usr/bin/env python3
"""
Service de synchronisation automatique avec la Freebox
Lance la synchronisation des appareils bannis toutes les 10 minutes
"""

import time
import subprocess
import sys
import os
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/freebox_sync.log'),
        logging.StreamHandler()
    ]
)

def sync_with_freebox():
    """Lancer la synchronisation avec la Freebox"""
    try:
        logging.info("🔄 Démarrage de la synchronisation Freebox...")
        result = subprocess.run([
            "python3", 
            "/opt/traffic_sentinel/freebox_integration.py"
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            logging.info("✅ Synchronisation Freebox réussie")
            if result.stdout:
                logging.info(f"Output: {result.stdout}")
        else:
            logging.error(f"❌ Erreur synchronisation: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        logging.error("⏰ Timeout lors de la synchronisation")
    except Exception as e:
        logging.error(f"❌ Exception: {e}")

def main():
    """Boucle principale du service de synchronisation"""
    logging.info("🚀 Démarrage du service de synchronisation Freebox")
    
    # Synchronisation initiale
    sync_with_freebox()
    
    # Boucle de synchronisation périodique
    while True:
        try:
            # Attendre 10 minutes
            time.sleep(600)  # 600 secondes = 10 minutes
            sync_with_freebox()
            
        except KeyboardInterrupt:
            logging.info("🛑 Arrêt du service de synchronisation")
            break
        except Exception as e:
            logging.error(f"❌ Erreur dans la boucle principale: {e}")
            time.sleep(60)  # Attendre 1 minute avant de réessayer

if __name__ == "__main__":
    main()