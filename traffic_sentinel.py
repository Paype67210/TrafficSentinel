#!/usr/bin/env python3
import subprocess
import sqlite3
import requests
import json
import os
import time
import hashlib
import hmac
import logging
from datetime import datetime

# Configuration via variables d'environnement
DB_PATH = os.getenv('DB_PATH', '/var/lib/mac_filter/database.db')
INTERFACE = os.getenv('INTERFACE', 'enp0s5')
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', '')
SCAN_INTERVAL = int(os.getenv('SCAN_INTERVAL', '300'))  # 5 minutes par défaut

# Configuration des logs
def setup_logging():
    """Configuration du système de logging"""
    # Créer le répertoire de logs s'il n'existe pas
    log_dir = "/var/log/traffic_sentinel"
    
    try:
        os.makedirs(log_dir, exist_ok=True)
    except PermissionError:
        # Fallback sur le répertoire courant si pas de permissions
        log_dir = "."
    
    # Configuration du logger principal
    logger = logging.getLogger('traffic_sentinel')
    logger.setLevel(logging.INFO)
    
    # Éviter la duplication des handlers
    if not logger.handlers:
        # Handler console (toujours disponible)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Format des logs
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Essayer d'ajouter les handlers de fichiers
        try:
            # Handler pour fichier principal
            file_handler = logging.FileHandler(f"{log_dir}/traffic_sentinel.log")
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            # Handler pour fichier Freebox spécifique
            freebox_handler = logging.FileHandler(f"{log_dir}/freebox_operations.log")
            freebox_handler.setLevel(logging.INFO)
            freebox_handler.setFormatter(formatter)
            
            # Logger spécifique pour Freebox
            freebox_logger = logging.getLogger('traffic_sentinel.freebox')
            freebox_logger.setLevel(logging.INFO)
            freebox_logger.addHandler(freebox_handler)
            freebox_logger.addHandler(console_handler)
            
        except PermissionError:
            # Si pas de permissions, logs seulement sur la console
            logger.warning("Permissions insuffisantes pour écrire les logs fichiers - console seulement")
    
    return logger

# Initialiser le logging
logger = setup_logging()
freebox_logger = logging.getLogger('traffic_sentinel.freebox')

class FreeboxAPI:
    def __init__(self):
        self.app_id = "traffic_sentinel"
        self.app_name = "Traffic Sentinel Network Monitor"
        self.app_version = "1.0.0"
        self.device_name = "VM Traffic Monitor"
        self.freebox_url = "http://mafreebox.freebox.fr"
        self.session_token = None
        self.app_token = None
        self.api_version = "v8"  # Version par défaut, sera détectée automatiquement
        self.connected = False
        
    def get_api_version(self):
        """Détecter automatiquement la version de l'API Freebox supportée"""
        freebox_logger.info("🔍 Détection de la version de l'API Freebox...")
        
        # URLs à tester selon la Freebox
        test_urls = [
            "http://mafreebox.freebox.fr",
            "http://192.168.1.1",
            "http://192.168.0.1"
        ]
        
        for base_url in test_urls:
            try:
                freebox_logger.debug(f"🧪 Test de connexion à {base_url}")
                response = requests.get(f"{base_url}/api_version", timeout=5)
                
                if response.status_code == 200:
                    api_info = response.json()
                    api_version = api_info.get("api_version")
                    device_name = api_info.get("device_name", "Freebox")
                    
                    if api_version:
                        self.freebox_url = base_url
                        # CORRECTION: Extraire seulement la version majeure et préfixer avec 'v'
                        major_version = str(api_version).split('.')[0]
                        self.api_version = f"v{major_version}"
                        freebox_logger.info(f"✅ Freebox trouvée: {device_name} à {base_url}")
                        freebox_logger.info(f"📋 Version API supportée: {api_version}")
                        freebox_logger.info(f"🔧 Version API utilisée: {self.api_version}")
                        return True
                        
            except Exception as e:
                freebox_logger.debug(f"❌ Échec connexion à {base_url}: {e}")
                continue
        
        freebox_logger.error("❌ Impossible de détecter la Freebox et sa version API")
        return False
        
    def load_tokens_from_file(self):
        """Charger les tokens depuis le fichier JSON avec gestion des permissions"""
        # Emplacements possibles pour les tokens (par ordre de priorité)
        possible_locations = [
            "/etc/traffic_sentinel_tokens.json",
            "/opt/traffic_sentinel/tokens.json",
            "/tmp/traffic_sentinel_tokens.json",
            "./traffic_sentinel_tokens.json"
        ]
        
        self.token_file = None
        self.tokens_data = None
        
        for location in possible_locations:
            freebox_logger.debug(f"🔍 Test de chargement depuis {location}")
            
            try:
                with open(location, 'r') as f:
                    self.tokens_data = json.load(f)
                
                self.token_file = location
                freebox_logger.info(f"✅ Tokens chargés depuis: {location}")
                break
                
            except FileNotFoundError:
                freebox_logger.debug(f"📁 Fichier non trouvé: {location}")
                continue
            except PermissionError:
                freebox_logger.debug(f"🔒 Permissions insuffisantes: {location}")
                continue
            except json.JSONDecodeError as e:
                freebox_logger.warning(f"⚠️ Erreur JSON dans {location}: {e}")
                continue
            except Exception as e:
                freebox_logger.debug(f"❌ Erreur avec {location}: {e}")
                continue
        
        if not self.tokens_data:
            freebox_logger.error("❌ Aucun fichier de tokens accessible")
            freebox_logger.info("💡 Exécutez setup_gateway.py pour configurer l'accès Freebox")
            return False
        
        self.app_token = self.tokens_data.get("app_token")
        self.session_token = self.tokens_data.get("session_token")
        
        if self.app_token:
            freebox_logger.info(f"✅ App token chargé - Longueur: {len(self.app_token)} caractères")
        else:
            freebox_logger.warning("⚠️ Aucun app token trouvé dans le fichier")
            return False
        
        if self.session_token:
            freebox_logger.info(f"✅ Session token chargé - Longueur: {len(self.session_token)} caractères")
        else:
            freebox_logger.info("ℹ️ Aucun session token - sera généré automatiquement")
        
        # Log des informations utiles
        created_at = self.tokens_data.get("created_at", "Date inconnue")
        freebox_logger.info(f"🔧 API version: {self.api_version}")
        freebox_logger.info(f"🌐 URL Freebox: {self.freebox_url}")
        freebox_logger.info(f"📅 Tokens générés le: {created_at}")
        
        return True
    
    def save_session_token_to_file(self):
        """Sauvegarder le nouveau session token avec gestion des permissions"""
        if not hasattr(self, 'tokens_data'):
            freebox_logger.warning("⚠️ Impossible de sauvegarder - données manquantes")
            return
        
        # Emplacements pour la sauvegarde (par ordre de priorité)
        save_locations = []
        
        # Si on a un fichier existant, essayer d'abord celui-ci
        if hasattr(self, 'token_file') and self.token_file:
            save_locations.append(self.token_file)
        
        # Ajouter les alternatives
        save_locations.extend([
            "/opt/traffic_sentinel/tokens.json",
            "/tmp/traffic_sentinel_tokens.json",
            "./traffic_sentinel_tokens.json"
        ])
        
        # Mettre à jour les données
        self.tokens_data["session_token"] = self.session_token
        self.tokens_data["last_session_update"] = datetime.now().isoformat()
        
        saved = False
        for location in save_locations:
            try:
                # Créer le répertoire si nécessaire
                import os
                os.makedirs(os.path.dirname(location), exist_ok=True)
                
                with open(location, 'w') as f:
                    json.dump(self.tokens_data, f, indent=2)
                
                freebox_logger.info(f"✅ Session token sauvegardé dans {location}")
                self.token_file = location  # Mettre à jour l'emplacement de référence
                saved = True
                break
                
            except PermissionError:
                freebox_logger.debug(f"🔒 Permissions insuffisantes pour {location}")
                continue
            except Exception as e:
                freebox_logger.debug(f"❌ Erreur sauvegarde {location}: {e}")
                continue
        
        if not saved:
            freebox_logger.warning("⚠️ Impossible de sauvegarder le session token - aucun emplacement accessible")
            freebox_logger.info("💡 Le token reste en mémoire pour cette session")
    
    def get_new_session_token(self):
        """Obtenir un nouveau token de session avec l'app_token"""
        if not self.app_token:
            freebox_logger.error("❌ App token manquant pour obtenir session token")
            return False
        
        freebox_logger.info(f"🔐 Demande de nouveau token de session via {self.freebox_url}")
        
        try:
            # Obtenir le challenge
            freebox_logger.debug(f"📡 GET {self.freebox_url}/api/{self.api_version}/login")
            response = requests.get(f"{self.freebox_url}/api/{self.api_version}/login", timeout=5)
            
            freebox_logger.debug(f"📊 Réponse challenge - Status: {response.status_code}")
            result = response.json()
            
            if not result.get("success", False):
                freebox_logger.error(f"❌ Erreur challenge: {result}")
                return False
            
            challenge = result["result"]["challenge"]
            freebox_logger.info(f"✅ Challenge reçu: {challenge[:8]}...{challenge[-8:]}")
            
            # Calculer la signature HMAC
            password_hash = hmac.new(
                self.app_token.encode(),
                challenge.encode(),
                hashlib.sha1
            ).hexdigest()
            freebox_logger.debug(f"🔑 Signature HMAC calculée: {password_hash[:16]}...")
            
            # Demander le token de session
            login_data = {
                "app_id": self.app_id,
                "password": password_hash
            }
            
            freebox_logger.debug(f"📡 POST {self.freebox_url}/api/{self.api_version}/login/session")
            response = requests.post(
                f"{self.freebox_url}/api/{self.api_version}/login/session",
                json=login_data,
                timeout=10
            )
            
            freebox_logger.debug(f"📊 Réponse session - Status: {response.status_code}")
            result = response.json()
            
            if result.get("success", False):
                self.session_token = result["result"]["session_token"]
                freebox_logger.info(f"✅ Token de session obtenu: {self.session_token[:16]}...")
                freebox_logger.info("🎫 Authentification Freebox réussie")
                
                # Sauvegarder le nouveau session token
                self.save_session_token_to_file()
                
                return True
            else:
                freebox_logger.error(f"❌ Erreur session: {result}")
                return False
                
        except requests.exceptions.Timeout as e:
            freebox_logger.error(f"⏰ Timeout connexion Freebox: {e}")
            return False
        except requests.exceptions.ConnectionError as e:
            freebox_logger.error(f"🌐 Erreur réseau Freebox: {e}")
            return False
        except Exception as e:
            freebox_logger.error(f"❌ Erreur inattendue connexion Freebox: {e}")
            return False
    
    def test_connection(self):
        """Tester la connexion à la Freebox"""
        if not self.session_token:
            freebox_logger.error("❌ Aucun token de session pour tester la connexion")
            return False
        
        freebox_logger.info("🧪 Test de connexion à l'API Freebox")
        headers = {"X-Fbx-App-Auth": self.session_token}
        
        try:
            freebox_logger.debug(f"📡 GET {self.freebox_url}/api/{self.api_version}/system")
            response = requests.get(
                f"{self.freebox_url}/api/{self.api_version}/system",
                headers=headers,
                timeout=5
            )
            
            freebox_logger.debug(f"📊 Réponse test - Status: {response.status_code}")
            result = response.json()
            
            if result.get("success", False):
                system_info = result.get("result", {})
                uptime = system_info.get("uptime", "Inconnu")
                temp = system_info.get("temp", {}).get("cpum", "Inconnue")
                
                freebox_logger.info("✅ Connexion Freebox API établie avec succès")
                freebox_logger.info(f"⏱️ Uptime Freebox: {uptime} secondes")
                freebox_logger.info(f"🌡️ Température CPU: {temp}°C")
                
                self.connected = True
                return True
            else:
                freebox_logger.warning(f"⚠️ Test connexion API échoué: {result}")
                return False
                
        except requests.exceptions.Timeout as e:
            freebox_logger.error(f"⏰ Timeout test connexion: {e}")
            return False
        except Exception as e:
            freebox_logger.error(f"❌ Erreur test connexion: {e}")
            return False

    def is_session_valid(self):
        """Vérifier si le token de session est encore valide"""
        if not self.session_token:
            freebox_logger.debug("❌ Aucun session token à valider")
            return False
        
        headers = {"X-Fbx-App-Auth": self.session_token}
        
        try:
            # Test avec l'endpoint login qui est toujours disponible
            response = requests.get(
                f"{self.freebox_url}/api/{self.api_version}/login/",
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success", False):
                    freebox_logger.debug("✅ Session token valide")
                    return True
                else:
                    error_code = result.get("error_code", "unknown")
                    if error_code in ["auth_required", "invalid_session"]:
                        freebox_logger.info("🔄 Session token expiré, renouvellement nécessaire")
                    else:
                        freebox_logger.warning(f"⚠️ Erreur validation session: {result}")
                    return False
            else:
                freebox_logger.debug(f"❌ Erreur HTTP validation session: {response.status_code}")
                return False
                    
        except Exception as e:
            freebox_logger.debug(f"❌ Erreur validation session: {e}")
            return False
    
    def ensure_valid_session(self):
        """S'assurer d'avoir une session valide, la renouveler si nécessaire"""
        # Vérifier d'abord si on a un session token
        if not self.session_token:
            freebox_logger.info("🔄 Aucun session token, demande d'un nouveau")
            return self.get_new_session_token()
        
        # Tester la validité du token actuel
        if self.is_session_valid():
            freebox_logger.debug("✅ Session token toujours valide")
            return True
        
        freebox_logger.info("🔄 Session token expiré, renouvellement nécessaire")
        if self.get_new_session_token():
            freebox_logger.info("✅ Token de session renouvelé avec succès")
            return True
        else:
            freebox_logger.error("❌ Échec critique du renouvellement de session")
            self.connected = False
            return False
    
    def initialize(self):
        """Initialiser la connexion Freebox"""
        # Détecter d'abord la version de l'API
        if not self.get_api_version():
            print("❌ Impossible de détecter la Freebox")
            return False
            
        # Charger les tokens
        if not self.load_tokens_from_file():
            print("❌ Impossible de charger les tokens Freebox")
            return False
        
        # Obtenir un nouveau token de session
        if not self.get_new_session_token():
            print("❌ Impossible d'obtenir un token de session")
            return False
        
        # Tester la connexion
        if not self.test_connection():
            print("❌ Test de connexion échoué")
            return False
        
        print("🎉 Freebox API initialisée avec succès")
        return True
    
    def get_network_devices(self):
        """Récupérer la liste des appareils connectés au réseau"""
        if not self.connected:
            freebox_logger.error("❌ Tentative de récupération des appareils sans connexion Freebox")
            return []
        
        # S'assurer d'avoir une session valide - CRITIQUE
        freebox_logger.debug("🔐 Validation de session avant récupération des appareils")
        if not self.ensure_valid_session():
            freebox_logger.error("❌ Session invalide - impossible de récupérer les appareils")
            return []
        
        freebox_logger.debug("🔍 Récupération de la liste des appareils Freebox...")
        headers = {"X-Fbx-App-Auth": self.session_token}
        
        try:
            response = requests.get(
                f"{self.freebox_url}/api/{self.api_version}/lan/browser/pub/",
                headers=headers,
                timeout=10
            )
            
            freebox_logger.debug(f"📊 Status récupération appareils: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success", False):
                    devices = result.get("result", [])
                    connected_devices = [d for d in devices if d.get("active", False)]
                    
                    freebox_logger.info(f"📱 {len(connected_devices)} appareils connectés trouvés sur la Freebox")
                    freebox_logger.debug(f"🔢 Total appareils dans la base: {len(devices)}")
                    
                    # Log quelques exemples d'appareils pour debug
                    for i, device in enumerate(connected_devices[:3]):  # Premiers 3 seulement
                        name = device.get("primary_name", "Appareil inconnu")
                        mac = device.get("l2ident", {}).get("id", "MAC inconnue")
                        ip = device.get("l3connectivities", [{}])[0].get("addr", "IP inconnue") if device.get("l3connectivities") else "IP inconnue"
                        freebox_logger.debug(f"📱 Appareil {i+1}: {name} (MAC: {mac}, IP: {ip})")
                    
                    if len(connected_devices) > 3:
                        freebox_logger.debug(f"... et {len(connected_devices) - 3} autres appareils")
                    
                    return devices  # Retourner TOUS les appareils, pas seulement connectés
                else:
                    freebox_logger.error(f"❌ Échec récupération appareils: {result}")
                    return []
            else:
                freebox_logger.error(f"❌ Erreur HTTP récupération appareils: {response.status_code}")
                return []
                
        except requests.exceptions.Timeout as e:
            freebox_logger.error(f"⏰ Timeout récupération appareils: {e}")
            return []
        except Exception as e:
            freebox_logger.error(f"❌ Erreur récupération appareils: {e}")
            return []
    
    def block_device_by_mac(self, mac_address):
        """Bloquer un appareil via le filtre MAC WiFi de la Freebox"""
        if not self.connected:
            freebox_logger.error(f"❌ Tentative de blocage {mac_address} sans connexion Freebox")
            return False
        
        # S'assurer d'avoir une session valide AVANT toute opération
        freebox_logger.debug(f"🔐 Validation de session avant blocage de {mac_address}")
        if not self.ensure_valid_session():
            freebox_logger.error(f"❌ Impossible de valider la session pour bloquer {mac_address}")
            return False
        
        freebox_logger.info(f"🚫 Blocage WiFi de l'appareil MAC: {mac_address.upper()}")
        headers = {"X-Fbx-App-Auth": self.session_token}
        
        try:
            # Vérifier si la MAC est déjà dans le filtre
            freebox_logger.debug(f"🔍 Vérification du filtre MAC WiFi")
            response = requests.get(
                f"{self.freebox_url}/api/{self.api_version}/wifi/mac_filter/",
                headers=headers,
                timeout=5
            )
            
            result = response.json()
            if result.get("success", False):
                existing_filters = result.get("result", [])
                # Le résultat peut être une liste ou un dict
                if isinstance(existing_filters, list):
                    for f in existing_filters:
                        if f.get("mac", "").lower() == mac_address.lower():
                            freebox_logger.info(f"ℹ️ MAC {mac_address.upper()} déjà dans le filtre WiFi blacklist")
                            return True
                elif isinstance(existing_filters, dict):
                    for existing_mac in existing_filters.keys():
                        if existing_mac.lower() == mac_address.lower():
                            freebox_logger.info(f"ℹ️ MAC {mac_address.upper()} déjà dans le filtre WiFi blacklist")
                            return True
            
            # Ajouter la MAC au filtre WiFi blacklist
            freebox_logger.debug(f"📡 Ajout de {mac_address.upper()} au filtre MAC WiFi blacklist")
            block_data = {
                "mac": mac_address.upper(),
                "type": "blacklist"
            }
            
            response = requests.post(
                f"{self.freebox_url}/api/{self.api_version}/wifi/mac_filter/",
                json=block_data,
                headers=headers,
                timeout=5
            )
            
            result = response.json()
            
            if result.get("success", False):
                device_name = result.get("result", {}).get("hostname", "Appareil")
                freebox_logger.info(f"✅ MAC {mac_address.upper()} BLOQUÉE dans le filtre WiFi")
                freebox_logger.info(f"🚫 Appareil {device_name} déconnecté du WiFi et bloqué")
                return True
            else:
                error_msg = result.get("msg", "Erreur inconnue")
                error_code = result.get("error_code", "")
                freebox_logger.error(f"❌ Échec ajout au filtre WiFi: {error_msg} ({error_code})")
                return False
                
        except requests.exceptions.Timeout as e:
            freebox_logger.error(f"⏰ Timeout lors du blocage WiFi de {mac_address}: {e}")
            return False
        except Exception as e:
            freebox_logger.error(f"❌ Erreur blocage WiFi MAC {mac_address}: {e}")
            import traceback
            freebox_logger.error(traceback.format_exc())
            return False
    
    def allow_device_by_mac(self, mac_address):
        """Débloquer un appareil en le retirant du filtre MAC WiFi"""
        if not self.connected:
            freebox_logger.error(f"❌ Tentative de déblocage {mac_address} sans connexion Freebox")
            return False
        
        # S'assurer d'avoir une session valide AVANT toute opération
        freebox_logger.debug(f"🔐 Validation de session avant déblocage de {mac_address}")
        if not self.ensure_valid_session():
            freebox_logger.error(f"❌ Impossible de valider la session pour débloquer {mac_address}")
            return False
        
        freebox_logger.info(f"✅ Déblocage WiFi de l'appareil MAC: {mac_address.upper()}")
        headers = {"X-Fbx-App-Auth": self.session_token}
        
        try:
            # Vérifier que la MAC est dans le filtre
            freebox_logger.debug(f"🔍 Recherche de {mac_address.upper()} dans le filtre MAC WiFi")
            response = requests.get(
                f"{self.freebox_url}/api/{self.api_version}/wifi/mac_filter/",
                headers=headers,
                timeout=5
            )
            
            result = response.json()
            if not result.get("success", False):
                freebox_logger.error(f"❌ Échec récupération filtre MAC WiFi: {result}")
                return False
            
            filter_id = None
            existing_filters = result.get("result", [])
            
            # Le résultat peut être une liste ou un dict
            if isinstance(existing_filters, list):
                for f in existing_filters:
                    if f.get("mac", "").lower() == mac_address.lower():
                        filter_id = f.get("id")
                        freebox_logger.debug(f"🎯 Filtre trouvé avec ID: {filter_id}")
                        break
            elif isinstance(existing_filters, dict):
                for existing_mac, info in existing_filters.items():
                    if existing_mac.lower() == mac_address.lower():
                        filter_id = info.get("id") if isinstance(info, dict) else f"{existing_mac}-blacklist"
                        freebox_logger.debug(f"🎯 Filtre trouvé avec ID: {filter_id}")
                        break
            
            if not filter_id:
                freebox_logger.info(f"ℹ️ MAC {mac_address.upper()} n'est pas dans le filtre WiFi (déjà autorisée)")
                return True
            
            # Supprimer la MAC du filtre
            freebox_logger.debug(f"📡 Suppression du filtre ID: {filter_id}")
            response = requests.delete(
                f"{self.freebox_url}/api/{self.api_version}/wifi/mac_filter/{filter_id}",
                headers=headers,
                timeout=5
            )
            
            result = response.json()
            
            if result.get("success", False):
                freebox_logger.info(f"✅ MAC {mac_address.upper()} RETIRÉE du filtre WiFi")
                freebox_logger.info(f"🌐 Appareil autorisé à se reconnecter au WiFi")
                return True
            else:
                error_msg = result.get("msg", "Erreur inconnue")
                error_code = result.get("error_code", "")
                freebox_logger.error(f"❌ Échec suppression du filtre: {error_msg} ({error_code})")
                return False
                
        except requests.exceptions.Timeout as e:
            freebox_logger.error(f"⏰ Timeout lors du déblocage WiFi de {mac_address}: {e}")
            return False
        except Exception as e:
            freebox_logger.error(f"❌ Erreur déblocage WiFi MAC {mac_address}: {e}")
            import traceback
            freebox_logger.error(traceback.format_exc())
            return False

            freebox_logger.error(f"❌ Erreur déblocage MAC {mac_address}: {e}")
            return False

# Instance globale de l'API Freebox
freebox_api = FreeboxAPI()

def sync_banned_devices_with_freebox():
    """Synchroniser tous les appareils bannis avec la Freebox"""
    if not freebox_api.connected:
        logger.warning("⚠️ Synchronisation impossible: Freebox API non connectée")
        return
    
    logger.info("🔄 Début de la synchronisation des appareils bannis avec Freebox")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT mac_address, comment FROM mac_addresses WHERE status = 'banned'")
        banned_devices = c.fetchall()
        conn.close()
        
        if banned_devices:
            logger.info(f"� {len(banned_devices)} appareil(s) banni(s) trouvé(s) en base de données")
            
            success_count = 0
            for mac, comment in banned_devices:
                logger.info(f"🚫 Synchronisation du blocage pour {mac} - {comment or 'Pas de commentaire'}")
                if freebox_api.block_device_by_mac(mac):
                    success_count += 1
                
            logger.info(f"✅ Synchronisation terminée: {success_count}/{len(banned_devices)} appareils synchronisés")
        else:
            logger.info("ℹ️ Aucun appareil banni à synchroniser")
            
    except Exception as e:
        logger.error(f"❌ Erreur synchronisation Freebox: {e}")

def check_status_changes():
    """
    Vérifier les changements de statut en BDD et les appliquer immédiatement
    Cette fonction est appelée périodiquement pour capturer les changements
    faits via l'interface web, même si l'appareil n'est pas actif
    """
    if not freebox_api.connected:
        return
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Récupérer tous les appareils de la BDD
        c.execute("SELECT mac_address, status FROM mac_addresses")
        db_devices = c.fetchall()
        conn.close()
        
        # Récupérer l'état actuel sur la Freebox
        freebox_devices = freebox_api.get_network_devices()
        if not freebox_devices:
            return
        
        # Créer un dictionnaire des états Freebox
        freebox_states = {}
        for device in freebox_devices:
            mac = device.get("l2ident", {}).get("id", "").lower()
            if mac:
                freebox_states[mac] = device.get("access", True)
        
        # Vérifier chaque appareil en BDD
        for mac, db_status in db_devices:
            if mac not in freebox_states:
                # Appareil pas visible sur la Freebox (déconnecté)
                continue
            
            current_access = freebox_states[mac]
            
            # Déterminer l'état attendu selon le statut BDD
            if db_status == "banned" or db_status == "quarantine":
                expected_access = False
            elif db_status == "authorized":
                expected_access = True
            else:
                continue
            
            # Si l'état ne correspond pas, corriger
            if current_access != expected_access:
                if (db_status == "banned" or db_status == "quarantine") and current_access:
                    logger.warning(f"🔄 Incohérence détectée: {mac} devrait être bloqué (statut: {db_status}) mais est autorisé - correction en cours")
                    freebox_api.block_device_by_mac(mac)
                elif db_status == "authorized" and not current_access:
                    logger.warning(f"🔄 Incohérence détectée: {mac} devrait être autorisé mais est bloqué - correction en cours")
                    freebox_api.allow_device_by_mac(mac)
    
    except Exception as e:
        logger.error(f"❌ Erreur lors de la vérification des changements de statut: {e}")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS mac_addresses (
            mac_address TEXT PRIMARY KEY,
            status TEXT CHECK(status IN ('authorized', 'quarantine', 'banned')),
            first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            comment TEXT
        )
    """)
    conn.commit()
    conn.close()

def scan_network():
    try:
        result = subprocess.run(["arp-scan", "--interface", INTERFACE, "--localnet", "--quiet"], 
                              capture_output=True, text=True, timeout=30)
        devices = set()
        for line in result.stdout.splitlines():
            if ":" in line and len(line.split()) >= 2:
                mac = line.split()[1].lower()
                if len(mac.split(":")) == 6:  # Validation format MAC
                    devices.add(mac)
        return devices
    except subprocess.TimeoutExpired:
        print("Timeout lors du scan réseau")
        return set()
    except Exception as e:
        print(f"Erreur lors du scan réseau: {e}")
        return set()

def update_mac_status(mac, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Vérifier si l'appareil existe déjà
    c.execute("SELECT first_seen, comment FROM mac_addresses WHERE mac_address = ?", (mac,))
    existing = c.fetchone()
    
    if existing:
        # Mise à jour en préservant first_seen et comment
        c.execute("""
            UPDATE mac_addresses 
            SET status = ?, last_seen = ? 
            WHERE mac_address = ?
        """, (status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), mac))
    else:
        # Nouvel enregistrement
        c.execute("""
            INSERT INTO mac_addresses (mac_address, status, first_seen, last_seen, comment)
            VALUES (?, ?, ?, ?, ?)
        """, (mac, status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ''))
    
    conn.commit()
    conn.close()

def get_mac_status(mac):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT status FROM mac_addresses WHERE mac_address = ?", (mac,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def block_mac(mac):
    """Bloquer une adresse MAC via Freebox API puis iptables pour déconnexion immédiate"""
    logger.info(f"🚫 BLOCAGE demandé pour MAC: {mac.upper()}")
    freebox_blocked = False
    
    # Essayer d'abord le blocage via Freebox API
    if freebox_api.connected:
        logger.info(f"🌐 Tentative de blocage via Freebox API pour {mac}")
        try:
            if freebox_api.block_device_by_mac(mac):
                logger.info(f"✅ MAC {mac} bloquée avec succès via Freebox WiFi filter")
                # Envoyer notification de blocage
                send_blocking_alert(mac)
            else:
                logger.warning(f"⚠️ Échec blocage Freebox WiFi pour {mac}")
        except Exception as e:
            logger.error(f"❌ Erreur Freebox API WiFi pour {mac}: {e}")
    else:
        logger.warning("⚠️ Freebox API non connectée")

def allow_mac(mac):
    """Autoriser une adresse MAC en la retirant du filtre WiFi Freebox"""
    logger.info(f"✅ AUTORISATION demandée pour MAC: {mac.upper()}")
    
    # Autoriser via Freebox API WiFi filter
    if freebox_api.connected:
        logger.info(f"🌐 Retrait de {mac} du filtre WiFi Freebox")
        try:
            if freebox_api.allow_device_by_mac(mac):
                logger.info(f"✅ MAC {mac} retirée du filtre WiFi - Appareil peut se reconnecter")
            else:
                logger.warning(f"⚠️ Échec retrait du filtre WiFi pour {mac}")
        except Exception as e:
            logger.error(f"❌ Erreur Freebox API WiFi pour {mac}: {e}")
    else:
        logger.warning("⚠️ Freebox API non connectée")

def get_device_hostname(mac):
    """Récupérer le hostname d'un appareil depuis la Freebox"""
    if not freebox_api.connected:
        return "Appareil inconnu"
    
    try:
        devices = freebox_api.get_network_devices()
        for device in devices:
            device_mac = device.get("l2ident", {}).get("id", "").lower()
            if device_mac == mac.lower():
                return device.get("primary_name", "Appareil inconnu")
    except Exception as e:
        logger.error(f"Erreur récupération hostname pour {mac}: {e}")
    
    return "Appareil inconnu"

def send_blocking_alert(mac):
    """Envoyer une alerte Slack quand un appareil est effectivement bloqué"""
    hostname = get_device_hostname(mac)
    
    if not SLACK_WEBHOOK_URL:
        print(f"Alerte: Appareil {hostname} ({mac}) maintenant BLOQUÉ sur le réseau")
        return
    
    try:
        payload = {
            "text": f"🚫 **Traffic Sentinel - Appareil BLOQUÉ**",
            "attachments": [{
                "color": "#ff0000",
                "fields": [
                    {
                        "title": "Appareil",
                        "value": f"**{hostname}**",
                        "short": True
                    },
                    {
                        "title": "Adresse MAC",
                        "value": f"`{mac.upper()}`",
                        "short": True
                    },
                    {
                        "title": "Action",
                        "value": "🚫 BLOQUÉ WiFi Freebox",
                        "short": True
                    },
                    {
                        "title": "Blocage effectif",
                        "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "short": True
                    }
                ],
                "footer": "Traffic Sentinel - Blocage actif",
                "footer_icon": "🚫",
                "ts": int(datetime.now().timestamp())
            }]
        }
        
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"Erreur Slack HTTP {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Erreur lors de l'envoi Slack: {e}")

def get_device_hostname(mac):
    """Récupérer le hostname d'un appareil depuis la Freebox"""
    if not freebox_api.connected:
        return "Appareil inconnu"
    
    try:
        devices = freebox_api.get_network_devices()
        for device in devices:
            device_mac = device.get("l2ident", {}).get("id", "").lower()
            if device_mac == mac.lower():
                return device.get("primary_name", "Appareil inconnu")
    except Exception as e:
        logger.error(f"Erreur récupération hostname pour {mac}: {e}")
    
    return "Appareil inconnu"

def send_slack_alert(mac, status):
    hostname = get_device_hostname(mac)
    
    if not SLACK_WEBHOOK_URL:
        print(f"Alerte: Nouvel appareil {hostname} ({mac}) - {status}")
        return
    
    try:
        # Déterminer les couleurs et émojis selon le statut
        if status == "quarantine":
            color = "#ff9900"
            status_emoji = "⚠️"
            status_text = "En quarantaine (bloqué)"
        elif status == "banned":
            color = "#ff0000"
            status_emoji = "❌"
            status_text = "Interdit"
        else:
            color = "#36a64f"
            status_emoji = "✅"
            status_text = "Autorisé"
        
        payload = {
            "text": f"🚨 **Traffic Sentinel - Nouvel appareil détecté**",
            "attachments": [{
                "color": color,
                "fields": [
                    {
                        "title": "Appareil",
                        "value": f"**{hostname}**",
                        "short": True
                    },
                    {
                        "title": "Adresse MAC",
                        "value": f"`{mac.upper()}`",
                        "short": True
                    },
                    {
                        "title": "Statut",
                        "value": f"{status_emoji} {status_text}",
                        "short": True
                    },
                    {
                        "title": "Détection",
                        "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "short": True
                    }
                ],
                "footer": "Traffic Sentinel Network Monitor",
                "footer_icon": "🔍",
                "ts": int(datetime.now().timestamp())
            }]
        }
        
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"Erreur Slack HTTP {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Erreur lors de l'envoi Slack: {e}")

def main():
    print(f"🚀 Démarrage du Traffic Sentinel - Interface: {INTERFACE}")
    print("=" * 60)
    
    # Initialiser la base de données
    init_db()
    
    # Initialiser la connexion Freebox
    logger.info("🔌 Initialisation de la connexion Freebox...")
    if freebox_api.initialize():
        logger.info("✅ Freebox API prête - blocage via routeur activé")
        
        # Synchronisation initiale des appareils bannis
        logger.info("🔄 Démarrage de la synchronisation initiale...")
        sync_banned_devices_with_freebox()
    else:
        logger.warning("⚠️ Freebox API indisponible - fallback sur iptables uniquement")
        logger.info("💡 Vérifiez que les tokens sont présents dans /etc/traffic_sentinel_tokens.json")
    
    print("=" * 60)
    
    # Compteur pour la vérification périodique des changements de statut
    status_check_counter = 0
    STATUS_CHECK_INTERVAL = 3  # Vérifier les changements tous les 3 scans (ex: toutes les 90s si scan = 30s)
    
    while True:
        try:
            logger.info(f"🔍 Scan du réseau à {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            detected_macs = scan_network()
            logger.info(f"📊 {len(detected_macs)} appareil(s) détecté(s) sur l'interface {INTERFACE}")
            
            if len(detected_macs) == 0:
                print("Aucun appareil détecté - vérification interface réseau")
                time.sleep(SCAN_INTERVAL)
                continue
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT mac_address, status FROM mac_addresses")
            known_macs = {row[0]: row[1] for row in c.fetchall()}
            conn.close()

            for mac in detected_macs:
                status = known_macs.get(mac)
                if status is None:
                    logger.warning(f"🆕 NOUVEL APPAREIL détecté: {mac.upper()} - Mise en quarantaine et blocage immédiat")
                    update_mac_status(mac, "quarantine")
                    # Bloquer immédiatement les nouveaux appareils en quarantaine
                    block_mac(mac)
                    send_slack_alert(mac, "quarantine")
                elif status == "banned":
                    logger.info(f"🚫 Appareil banni détecté: {mac} - Application du blocage")
                    block_mac(mac)
                elif status == "quarantine":
                    logger.info(f"⚠️ Appareil en quarantaine détecté: {mac} - Application du blocage")
                    block_mac(mac)
                elif status == "authorized":
                    logger.debug(f"✅ Appareil autorisé détecté: {mac} - Vérification accès")
                    allow_mac(mac)
                else:
                    logger.debug(f"ℹ️ Appareil détecté: {mac} - statut: {status}")
                
                # Mettre à jour last_seen pour les appareils connus
                if status:
                    update_mac_status(mac, status)
            
            # Vérifier périodiquement les incohérences de statut
            # Ceci capture les changements faits via l'interface web même si l'appareil n'est pas actif
            status_check_counter += 1
            if status_check_counter >= STATUS_CHECK_INTERVAL:
                logger.debug("🔍 Vérification des incohérences de statut entre BDD et Freebox")
                check_status_changes()
                status_check_counter = 0
            
            print(f"⏱️ Attente de {SCAN_INTERVAL} secondes...")
            time.sleep(SCAN_INTERVAL)
            
        except KeyboardInterrupt:
            print("Arrêt du Traffic Sentinel")
            break
        except Exception as e:
            print(f"Erreur dans la boucle principale: {e}")
            time.sleep(30)  # Attendre avant de réessayer

if __name__ == "__main__":
    main()
    