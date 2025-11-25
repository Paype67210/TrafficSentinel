#!/usr/bin/env python3
"""
Intégration avec l'API Freebox pour blocage direct sur le routeur
Plus efficace que les règles iptables sur la VM
"""

import requests
import json
import hashlib
import hmac
import time
import sqlite3
import os

class FreeboxAPI:
    def __init__(self):
        self.app_id = "traffic_sentinel"
        self.app_name = "Traffic Sentinel"
        self.app_version = "1.0.0"
        self.device_name = "VM Traffic Monitor"
        self.freebox_url = "http://192.168.0.254"  # IP directe pour éviter DNS
        self.freebox_fallback_url = "http://mafreebox.freebox.fr"  # Fallback
        self.session_token = None
        self.app_token = None
        self.api_version = "v15"  # Version par défaut
        
    def get_api_version(self):
        """Obtenir la version de l'API Freebox et l'ajuster automatiquement"""
        # Essayer d'abord avec l'IP directe
        for url in [self.freebox_url, self.freebox_fallback_url]:
            try:
                response = requests.get(f"{url}/api_version", timeout=5)
                api_info = response.json()
                
                if "api_version" in api_info:
                    # Utiliser la version majeure de l'API
                    major_version = api_info["api_version"].split(".")[0]
                    self.api_version = f"v{major_version}"
                    print(f"🔧 API Freebox détectée: {self.api_version} via {url}")
                    # Utiliser cette URL qui fonctionne
                    self.freebox_url = url
                
                return api_info
            except Exception as e:
                print(f"⚠️ Échec connexion {url}: {e}")
                continue
        
        print(f"⚠️ Erreur détection API version, utilisation de v8")
        return None
    
    def request_authorization(self):
        """Demander l'autorisation d'accès à la Freebox"""
        auth_data = {
            "app_id": self.app_id,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "device_name": self.device_name
        }
        
        try:
            response = requests.post(
                f"{self.freebox_url}/api/{self.api_version}/login/authorize",
                json=auth_data
            )
            result = response.json()
            
            if result["success"]:
                self.app_token = result["result"]["app_token"]
                track_id = result["result"]["track_id"]
                print(f"🔑 Token d'app: {self.app_token}")
                print(f"📱 Appuyez sur le bouton de votre Freebox pour autoriser l'accès")
                print(f"🔍 Track ID: {track_id}")
                
                # Attendre l'autorisation
                return self.wait_for_authorization(track_id)
            else:
                print(f"❌ Erreur lors de la demande d'autorisation: {result}")
                return False
                
        except Exception as e:
            print(f"❌ Erreur de connexion: {e}")
            return False
    
    def wait_for_authorization(self, track_id):
        """Attendre que l'utilisateur autorise l'accès"""
        print("⏳ En attente de l'autorisation...")
        
        for i in range(60):  # Attendre 60 secondes max
            try:
                response = requests.get(
                    f"{self.freebox_url}/api/{self.api_version}/login/authorize/{track_id}"
                )
                result = response.json()
                
                if result["success"]:
                    status = result["result"]["status"]
                    if status == "granted":
                        print("✅ Autorisation accordée!")
                        return True
                    elif status == "denied":
                        print("❌ Autorisation refusée")
                        return False
                    elif status == "timeout":
                        print("⏰ Timeout de l'autorisation")
                        return False
                    else:
                        print(f"⏳ Statut: {status}")
                        
            except Exception as e:
                print(f"❌ Erreur lors de la vérification: {e}")
                
            time.sleep(2)
        
        print("⏰ Timeout d'attente de l'autorisation")
        return False
    
    def login(self):
        """Se connecter à la Freebox avec le token"""
        if not self.app_token:
            print("❌ Token d'application manquant")
            return False
        
        try:
            # Obtenir le challenge
            response = requests.get(f"{self.freebox_url}/api/{self.api_version}/login")
            result = response.json()
            
            if not result["success"]:
                print(f"❌ Erreur lors de l'obtention du challenge: {result}")
                return False
            
            challenge = result["result"]["challenge"]
            
            # Calculer la signature
            password_hash = hmac.new(
                self.app_token.encode(),
                challenge.encode(),
                hashlib.sha1
            ).hexdigest()
            
            # Se connecter
            login_data = {
                "app_id": self.app_id,
                "password": password_hash
            }
            
            response = requests.post(
                f"{self.freebox_url}/api/{self.api_version}/login/session",
                json=login_data
            )
            result = response.json()
            
            if result["success"]:
                self.session_token = result["result"]["session_token"]
                print("✅ Connexion réussie à la Freebox")
                return True
            else:
                print(f"❌ Erreur de connexion: {result}")
                return False
                
        except Exception as e:
            print(f"❌ Erreur de connexion: {e}")
            return False
    
    def get_parental_filter_profiles(self):
        """Obtenir les profils de contrôle parental"""
        if not self.session_token:
            print("❌ Session non établie")
            return None
        
        headers = {"X-Fbx-App-Auth": self.session_token}
        
        try:
            response = requests.get(
                f"{self.freebox_url}/api/v15/parental/profile/",
                headers=headers
            )
            result = response.json()
            
            if result["success"]:
                return result["result"]
            else:
                print(f"❌ Erreur profils: {result}")
                return None
                
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return None
    
    def block_mac_address(self, mac_address, reason="Blocked by Traffic Sentinel"):
        """Bloquer une adresse MAC via l'access control de la Freebox"""
        if not self.session_token:
            print("❌ Session non établie")
            return False
        
        headers = {"X-Fbx-App-Auth": self.session_token}
        
        try:
            # Utiliser l'API lan/browser pour identifier l'appareil
            response = requests.get(
                f"{self.freebox_url}/api/v15/lan/browser/pub/",
                headers=headers
            )
            
            if not response.json()["success"]:
                print(f"❌ Erreur lors de l'accès au browser: {response.json()}")
                return False
            
            # Chercher l'appareil avec cette MAC
            devices = response.json()["result"]
            target_device = None
            
            for device in devices:
                if device.get("l2ident", {}).get("id", "").lower() == mac_address.lower():
                    target_device = device
                    break
            
            if not target_device:
                print(f"⚠️ Appareil {mac_address} non trouvé sur le réseau")
                # Créer une règle d'access control générique
                return self.create_access_rule(mac_address, reason)
            
            # Utiliser l'API lan/browser pour bloquer l'appareil
            device_id = target_device["id"]
            block_data = {
                "access": False  # Bloquer l'accès
            }
            
            response = requests.put(
                f"{self.freebox_url}/api/v15/lan/browser/pub/{device_id}",
                json=block_data,
                headers=headers
            )
            
            result = response.json()
            if result["success"]:
                print(f"✅ MAC {mac_address} bloquée via Freebox (device ID: {device_id})")
                return True
            else:
                print(f"❌ Erreur blocage device: {result}")
                # Fallback sur access control
                return self.create_access_rule(mac_address, reason)
                
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return False
    
    def create_access_rule(self, mac_address, reason):
        """Créer une règle d'access control pour bloquer une MAC"""
        if not self.session_token:
            return False
        
        headers = {"X-Fbx-App-Auth": self.session_token}
        
        try:
            # Créer une règle d'access control
            rule_data = {
                "comment": reason,
                "enabled": True,
                "mac_address": mac_address.upper().replace(':', ':'),
                "action": "drop"  # Bloquer le trafic
            }
            
            response = requests.post(
                f"{self.freebox_url}/api/v15/fw/redir/",
                json=rule_data,
                headers=headers
            )
            
            result = response.json()
            if result["success"]:
                print(f"✅ Règle de blocage créée pour {mac_address}")
                return True
            else:
                print(f"❌ Erreur création règle: {result}")
                # Dernier recours : access control simple
                return self.simple_access_control(mac_address)
                
        except Exception as e:
            print(f"❌ Erreur règle access: {e}")
            return False
    
    def simple_access_control(self, mac_address):
        """Méthode de blocage simple via access control"""
        if not self.session_token:
            return False
        
        headers = {"X-Fbx-App-Auth": self.session_token}
        
        try:
            # Essayer l'API access control directe
            access_data = {
                "comment": f"Blocked by Traffic Sentinel - {mac_address}",
                "enabled": True,
                "host": {
                    "type": "mac_address",
                    "value": mac_address.upper()
                },
                "action": "drop"
            }
            
            response = requests.post(
                f"{self.freebox_url}/api/v15/fw/access/",
                json=access_data,
                headers=headers
            )
            
            result = response.json()
            if result["success"]:
                print(f"✅ Access control créé pour {mac_address}")
                return True
            else:
                print(f"⚠️ Impossible de créer la règle automatiquement: {result}")
                print(f"💡 Veuillez bloquer manuellement {mac_address} dans l'interface Freebox")
                return False
                
        except Exception as e:
            print(f"❌ Erreur access control: {e}")
            return False

def sync_banned_devices():
    """Synchroniser les appareils bannis avec la Freebox"""
    DB_PATH = '/var/lib/mac_filter/database.db'
    
    if not os.path.exists(DB_PATH):
        print("❌ Base de données introuvable")
        return
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT mac_address FROM mac_addresses WHERE status = 'banned'")
    banned_macs = [row[0] for row in c.fetchall()]
    conn.close()
    
    if not banned_macs:
        print("ℹ️ Aucun appareil banni trouvé")
        return
    
    print(f"🔍 {len(banned_macs)} appareil(s) banni(s) trouvé(s)")
    
    # Initialiser l'API Freebox
    freebox = FreeboxAPI()
    
    # Détecter la version de l'API
    freebox.get_api_version()
    
    # Première utilisation : demander l'autorisation
    if not os.path.exists("/etc/traffic_sentinel_token"):
        print("🔑 Première utilisation - Autorisation requise")
        if freebox.request_authorization():
            # Sauvegarder le token pour les prochaines utilisations
            with open("/etc/traffic_sentinel_token", "w") as f:
                f.write(freebox.app_token)
        else:
            print("❌ Échec de l'autorisation")
            return
    else:
        # Charger le token existant
        with open("/etc/traffic_sentinel_token", "r") as f:
            freebox.app_token = f.read().strip()
    
    # Se connecter
    if not freebox.login():
        print("❌ Échec de la connexion")
        return
    
    # Bloquer chaque adresse MAC bannie
    for mac in banned_macs:
        print(f"🚫 Blocage de {mac}...")
        freebox.block_mac_address(mac)

if __name__ == "__main__":
    print("🚫 Synchronisation des appareils bannis avec la Freebox...")
    sync_banned_devices()