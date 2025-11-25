#!/usr/bin/env python3
"""
Script de réinitialisation des permissions Freebox
Ce script aide à reconfigurer l'application avec toutes les permissions nécessaires
"""

import os
import json
import requests
import time
import hashlib
import hmac
from datetime import datetime

class FreeboxReauth:
    def __init__(self):
        self.freebox_url = "http://192.168.1.1"
        self.api_version = "v15"
        self.app_id = "traffic_sentinel"
        self.app_name = "Traffic Sentinel"
        self.app_version = "2.0"
        self.device_name = "VM Traffic Sentinel"
        
    def get_api_version(self):
        """Récupérer la version de l'API Freebox"""
        try:
            response = requests.get(f"{self.freebox_url}/api_version", timeout=5)
            if response.status_code == 200:
                api_info = response.json()
                return api_info.get("api_version", "v15")
        except:
            pass
        return "v15"
    
    def request_authorization(self):
        """Demander une nouvelle autorisation avec TOUTES les permissions"""
        print("🔐 Demande d'autorisation Freebox avec permissions étendues...")
        
        # Permissions maximales
        permissions = {
            "settings": True,      # CRITIQUE: Paramètres système et réseau (blocage d'appareils)
            "contacts": False,     # Contacts (non nécessaire)
            "calls": False,        # Historique des appels (non nécessaire)
            "explorer": False,     # Explorateur de fichiers (non nécessaire)
            "downloader": False,   # Téléchargements (non nécessaire)
            "parental": True,      # CRITIQUE: Contrôle parental (blocage alternatif)
            "pvr": False,         # Enregistreur TV (non nécessaire)
            "camera": False,      # Caméras (non nécessaire)
            "home": False         # Domotique (non nécessaire)
        }
        
        auth_data = {
            "app_id": self.app_id,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "device_name": self.device_name,
            "permissions": permissions
        }
        
        print(f"📱 Application: {self.app_name}")
        print(f"🆔 ID: {self.app_id}")
        print(f"📋 Permissions demandées:")
        for perm, granted in permissions.items():
            if granted:
                print(f"   ✅ {perm}: Activé")
        
        try:
            response = requests.post(
                f"{self.freebox_url}/api/{self.api_version}/login/authorize/",
                json=auth_data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success", False):
                    app_token = result["result"]["app_token"]
                    track_id = result["result"]["track_id"]
                    
                    print(f"✅ Demande d'autorisation envoyée")
                    print(f"🎫 Token app: {app_token}")
                    print(f"🔢 Track ID: {track_id}")
                    
                    return app_token, track_id
                else:
                    print(f"❌ Échec autorisation: {result}")
            else:
                print(f"❌ Erreur HTTP: {response.status_code}")
        except Exception as e:
            print(f"❌ Erreur demande autorisation: {e}")
        
        return None, None
    
    def wait_for_authorization(self, app_token, track_id):
        """Attendre la validation de l'autorisation"""
        print("\n⏳ En attente de la validation sur la Freebox...")
        print("🔔 ALLEZ SUR VOTRE FREEBOX ET APPUYEZ SUR LE BOUTON POUR AUTORISER")
        print("   Vous avez 30 secondes pour valider...")
        
        for i in range(30):
            try:
                response = requests.get(
                    f"{self.freebox_url}/api/{self.api_version}/login/authorize/{track_id}",
                    timeout=5
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success", False):
                        status = result["result"]["status"]
                        
                        if status == "granted":
                            print("\n✅ Autorisation accordée!")
                            return True
                        elif status == "pending":
                            print(f"⏳ En attente... {30-i}s restantes", end="\r")
                        elif status == "denied":
                            print("\n❌ Autorisation refusée")
                            return False
                        elif status == "timeout":
                            print("\n⏰ Timeout de l'autorisation")
                            return False
                            
            except Exception as e:
                print(f"Erreur vérification: {e}")
            
            time.sleep(1)
        
        print("\n⏰ Timeout - Autorisation non validée dans les temps")
        return False
    
    def create_session(self, app_token):
        """Créer une session avec le token d'application"""
        print("\n🔑 Création d'une session...")
        
        try:
            # Récupérer le challenge
            response = requests.get(
                f"{self.freebox_url}/api/{self.api_version}/login/",
                timeout=5
            )
            
            if response.status_code != 200:
                print(f"❌ Erreur récupération challenge: {response.status_code}")
                return None
            
            result = response.json()
            if not result.get("success", False):
                print(f"❌ Échec récupération challenge: {result}")
                return None
            
            challenge = result["result"]["challenge"]
            print(f"🎯 Challenge reçu: {challenge[:16]}...")
            
            # Calculer la signature HMAC
            app_token_bytes = bytes.fromhex(app_token)
            signature = hmac.new(app_token_bytes, challenge.encode(), hashlib.sha1).hexdigest()
            
            # Demander la session
            session_data = {
                "app_id": self.app_id,
                "password": signature
            }
            
            response = requests.post(
                f"{self.freebox_url}/api/{self.api_version}/login/session/",
                json=session_data,
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success", False):
                    session_token = result["result"]["session_token"]
                    permissions = result["result"]["permissions"]
                    
                    print("✅ Session créée avec succès!")
                    print(f"🎫 Session token: {session_token[:16]}...")
                    
                    print("\n📋 Permissions accordées:")
                    granted_count = 0
                    for perm, granted in permissions.items():
                        status = "✅" if granted else "❌"
                        print(f"   {status} {perm}")
                        if granted:
                            granted_count += 1
                    
                    print(f"\n📊 {granted_count}/{len(permissions)} permissions accordées")
                    
                    return session_token, permissions
                else:
                    print(f"❌ Échec création session: {result}")
            else:
                print(f"❌ Erreur HTTP session: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Erreur création session: {e}")
        
        return None, None
    
    def save_tokens(self, app_token, session_token):
        """Sauvegarder les tokens"""
        tokens = {
            "app_token": app_token,
            "session_token": session_token,
            "created_at": datetime.now().isoformat(),
            "app_id": self.app_id
        }
        
        # Sauvegarder dans le fichier système
        system_file = "/etc/traffic_sentinel_tokens.json"
        local_file = "traffic_sentinel_tokens.json"
        
        for filepath in [local_file, system_file]:
            try:
                with open(filepath, 'w') as f:
                    json.dump(tokens, f, indent=2)
                print(f"✅ Tokens sauvegardés: {filepath}")
            except Exception as e:
                print(f"❌ Erreur sauvegarde {filepath}: {e}")
    
    def remove_old_authorization(self):
        """Supprimer l'ancienne autorisation si elle existe"""
        print("🗑️ Suppression de l'ancienne autorisation...")
        
        # Charger les anciens tokens
        try:
            with open('/etc/traffic_sentinel_tokens.json', 'r') as f:
                old_tokens = json.load(f)
            
            old_app_token = old_tokens.get("app_token")
            if old_app_token:
                print(f"🔍 Ancien app token trouvé: {old_app_token[:16]}...")
                
                # Tenter de supprimer (nécessite une session valide)
                # Pour l'instant on supprime juste le fichier
                os.remove('/etc/traffic_sentinel_tokens.json')
                print("✅ Ancien fichier de tokens supprimé")
            
        except FileNotFoundError:
            print("ℹ️ Aucun ancien fichier de tokens trouvé")
        except Exception as e:
            print(f"⚠️ Erreur suppression anciens tokens: {e}")
    
    def run_reauthorization(self):
        """Processus complet de réautorisation"""
        print("🔄 PROCESSUS DE RÉAUTORISATION FREEBOX")
        print("=" * 50)
        
        # Étape 1: Supprimer l'ancienne autorisation
        self.remove_old_authorization()
        
        # Étape 2: Vérifier la version API
        api_version = self.get_api_version()
        self.api_version = api_version
        print(f"🔌 Version API Freebox: {api_version}")
        
        # Étape 3: Demander une nouvelle autorisation
        app_token, track_id = self.request_authorization()
        if not app_token or not track_id:
            print("❌ Impossible de demander l'autorisation")
            return False
        
        # Étape 4: Attendre la validation
        if not self.wait_for_authorization(app_token, track_id):
            print("❌ Autorisation non validée")
            return False
        
        # Étape 5: Créer une session
        session_token, permissions = self.create_session(app_token)
        if not session_token:
            print("❌ Impossible de créer une session")
            return False
        
        # Étape 6: Sauvegarder les tokens
        self.save_tokens(app_token, session_token)
        
        # Étape 7: Vérifier les permissions critiques
        critical_perms = ["settings", "parental"]
        missing_perms = []
        
        for perm in critical_perms:
            if not permissions.get(perm, False):
                missing_perms.append(perm)
        
        if missing_perms:
            print(f"\n⚠️ ATTENTION: Permissions critiques manquantes: {missing_perms}")
            print("   Le blocage d'appareils pourrait ne pas fonctionner")
            print("   Relancez ce script et accordez TOUTES les permissions")
        else:
            print("\n🎉 Toutes les permissions critiques sont accordées!")
            print("   Le système de blocage devrait fonctionner correctement")
        
        return len(missing_perms) == 0

def main():
    print("🛠️ SCRIPT DE RÉAUTORISATION FREEBOX")
    print("Ce script va reconfigurer l'accès à la Freebox avec toutes les permissions")
    print()
    
    response = input("Continuer? (y/N): ")
    if response.lower() != 'y':
        print("❌ Opération annulée")
        return
    
    reauth = FreeboxReauth()
    
    if reauth.run_reauthorization():
        print("\n✅ Réautorisation réussie!")
        print("Vous pouvez maintenant redémarrer Traffic Sentinel")
    else:
        print("\n❌ Réautorisation échouée")
        print("Vérifiez la connectivité avec la Freebox et réessayez")

if __name__ == "__main__":
    main()