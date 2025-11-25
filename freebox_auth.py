#!/usr/bin/env python3
"""
Script d'authentification Freebox pour obtenir les tokens
Ce script de guidage pas à pas pour l'authentification avec la Freebox
"""

import requests
import json
import hashlib
import hmac
import time
import os

class FreeboxAuth:
    def __init__(self):
        self.app_id = "traffic_sentinel"
        self.app_name = "Traffic Sentinel Network Monitor"
        self.app_version = "1.0.0"
        self.device_name = "VM Traffic Monitor"
        self.freebox_url = "http://mafreebox.freebox.fr"
        self.api_version = "v15"
        
    def step1_detect_freebox(self):
        """Étape 1 : Détecter et vérifier la Freebox"""
        print("🔍 ÉTAPE 1 : Détection de la Freebox")
        print("=" * 50)
        
        try:
            print("🌐 Test de connexion à votre Freebox...")
            response = requests.get(f"{self.freebox_url}/api_version", timeout=5)
            api_info = response.json()
            
            print("✅ Freebox détectée !")
            print(f"📦 Modèle : {api_info.get('device_name', 'Inconnu')}")
            print(f"🔢 Version API : {api_info.get('api_version', 'Inconnue')}")
            print(f"🌐 URL : {self.freebox_url}")
            
            # Ajuster la version de l'API
            if "api_version" in api_info:
                major_version = api_info["api_version"].split(".")[0]
                self.api_version = f"v{major_version}"
                print(f"🔧 Version API utilisée : {self.api_version}")
            
            return True
            
        except requests.exceptions.RequestException as e:
            print("❌ Impossible de contacter la Freebox")
            print("💡 Vérifiez que :")
            print("   • Vous êtes sur le même réseau que la Freebox")
            print("   • L'adresse http://mafreebox.freebox.fr est accessible")
            print(f"   • Erreur technique : {e}")
            return False
    
    def step2_request_authorization(self):
        """Étape 2 : Demander l'autorisation d'accès"""
        print("\n🔑 ÉTAPE 2 : Demande d'autorisation")
        print("=" * 50)
        
        auth_data = {
            "app_id": self.app_id,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "device_name": self.device_name
        }
        
        try:
            print("📡 Envoi de la demande d'autorisation...")
            response = requests.post(
                f"{self.freebox_url}/api/{self.api_version}/login/authorize",
                json=auth_data,
                timeout=10
            )
            result = response.json()
            
            if not result.get("success", False):
                print(f"❌ Erreur lors de la demande : {result}")
                return None, None
            
            app_token = result["result"]["app_token"]
            track_id = result["result"]["track_id"]
            
            print("✅ Demande envoyée avec succès !")
            print(f"🔑 Token d'application généré : {app_token[:16]}...")
            print(f"🆔 ID de suivi : {track_id}")
            
            return app_token, track_id
            
        except Exception as e:
            print(f"❌ Erreur de connexion : {e}")
            return None, None
    
    def step3_wait_user_validation(self, track_id):
        """Étape 3 : Attendre la validation utilisateur"""
        print("\n📱 ÉTAPE 3 : Validation utilisateur")
        print("=" * 50)
        print("🚨 ACTION REQUISE :")
        print("   1️⃣ Allez près de votre Freebox")
        print("   2️⃣ Appuyez sur le bouton frontal (flèche droite)")
        print("   3️⃣ L'écran affichera une demande d'autorisation")
        print("   4️⃣ Validez en appuyant à nouveau sur le bouton")
        print()
        print("⏱️ Vous avez 2 minutes pour valider...")
        print("⏳ Attente en cours", end="")
        
        for i in range(120):  # 120 secondes = 2 minutes
            try:
                response = requests.get(
                    f"{self.freebox_url}/api/{self.api_version}/login/authorize/{track_id}",
                    timeout=5
                )
                result = response.json()
                
                if result.get("success", False):
                    status = result["result"]["status"]
                    
                    if status == "granted":
                        print("\n✅ Autorisation accordée !")
                        return True
                    elif status == "denied":
                        print("\n❌ Autorisation refusée")
                        print("💡 Réessayez et validez sur la Freebox")
                        return False
                    elif status == "timeout":
                        print("\n⏰ Délai d'autorisation dépassé")
                        return False
                    elif status == "pending":
                        print(".", end="", flush=True)
                    else:
                        print(f"\n🔄 Statut : {status}")
                        
            except Exception as e:
                print(f"\n❌ Erreur lors de la vérification : {e}")
                
            time.sleep(1)
        
        print("\n⏰ Timeout - Autorisation non reçue dans les temps")
        return False
    
    def step4_get_session_token(self, app_token):
        """Étape 4 : Obtenir le token de session"""
        print("\n🎟️ ÉTAPE 4 : Obtention du token de session")
        print("=" * 50)
        
        try:
            # Obtenir le challenge
            print("🔐 Récupération du challenge d'authentification...")
            response = requests.get(f"{self.freebox_url}/api/{self.api_version}/login", timeout=5)
            result = response.json()
            
            if not result.get("success", False):
                print(f"❌ Erreur challenge : {result}")
                return None
            
            challenge = result["result"]["challenge"]
            print(f"✅ Challenge reçu : {challenge[:16]}...")
            
            # Calculer la signature HMAC
            print("🔑 Calcul de la signature HMAC...")
            password_hash = hmac.new(
                app_token.encode(),
                challenge.encode(),
                hashlib.sha1
            ).hexdigest()
            
            # Demander le token de session
            login_data = {
                "app_id": self.app_id,
                "password": password_hash
            }
            
            print("🚪 Demande du token de session...")
            response = requests.post(
                f"{self.freebox_url}/api/{self.api_version}/login/session",
                json=login_data,
                timeout=10
            )
            result = response.json()
            
            if result.get("success", False):
                session_token = result["result"]["session_token"]
                print("✅ Token de session obtenu !")
                print(f"🎫 Session token : {session_token[:16]}...")
                return session_token
            else:
                print(f"❌ Erreur session : {result}")
                return None
                
        except Exception as e:
            print(f"❌ Erreur : {e}")
            return None
    
    def step5_test_access(self, session_token):
        """Étape 5 : Tester l'accès avec les tokens"""
        print("\n🧪 ÉTAPE 5 : Test d'accès")
        print("=" * 50)
        
        headers = {"X-Fbx-App-Auth": session_token}
        
        try:
            # Test 1 : Informations système
            print("🔍 Test 1 : Informations système...")
            response = requests.get(
                f"{self.freebox_url}/api/{self.api_version}/system",
                headers=headers,
                timeout=5
            )
            result = response.json()
            
            if result.get("success", False):
                print("✅ Accès système : OK")
                uptime = result["result"].get("uptime", "Inconnu")
                print(f"⏱️ Uptime Freebox : {uptime} secondes")
            else:
                print(f"⚠️ Accès système limité : {result}")
            
            # Test 2 : Appareils réseau
            print("🌐 Test 2 : Scan des appareils réseau...")
            response = requests.get(
                f"{self.freebox_url}/api/{self.api_version}/lan/browser/pub/",
                headers=headers,
                timeout=10
            )
            result = response.json()
            
            if result.get("success", False):
                devices = result["result"]
                print(f"✅ Scan réseau : {len(devices)} appareils détectés")
                
                # Afficher quelques appareils
                print("📱 Exemples d'appareils :")
                for device in devices[:3]:
                    name = device.get("primary_name", "Inconnu")
                    mac = device.get("l2ident", {}).get("id", "Inconnu")
                    print(f"   • {name} ({mac})")
                    
                if len(devices) > 3:
                    print(f"   ... et {len(devices) - 3} autres")
                    
            else:
                print(f"⚠️ Accès réseau limité : {result}")
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur test : {e}")
            return False
    
    def save_tokens(self, app_token, session_token):
        """Sauvegarder les tokens"""
        print("\n💾 ÉTAPE 6 : Sauvegarde des tokens")
        print("=" * 50)
        
        tokens_data = {
            "app_token": app_token,
            "session_token": session_token,
            "api_version": self.api_version,
            "generated_date": time.strftime('%Y-%m-%d %H:%M:%S'),
            "freebox_url": self.freebox_url
        }
        
        # Sauvegarder dans le fichier système
        try:
            with open("/etc/traffic_sentinel_tokens.json", "w") as f:
                json.dump(tokens_data, f, indent=2)
            print("✅ Tokens sauvegardés dans : /etc/traffic_sentinel_tokens.json")
        except Exception as e:
            print(f"⚠️ Erreur sauvegarde système : {e}")
        
        # Sauvegarder aussi en local pour debug
        try:
            with open("/var/log/freebox_tokens.json", "w") as f:
                json.dump(tokens_data, f, indent=2)
            print("✅ Copie sauvegardée dans : /var/log/freebox_tokens.json")
        except Exception as e:
            print(f"⚠️ Erreur sauvegarde log : {e}")
        
        # Ancien format pour compatibilité
        try:
            with open("/etc/traffic_sentinel_token", "w") as f:
                f.write(app_token)
            print("✅ App token sauvegardé (ancien format) : /etc/traffic_sentinel_token")
        except Exception as e:
            print(f"⚠️ Erreur sauvegarde ancien format : {e}")
        
        print("\n📋 RÉSUMÉ DES TOKENS :")
        print(f"🔑 App Token : {app_token}")
        print(f"🎫 Session Token : {session_token}")
        print(f"🔧 Version API : {self.api_version}")

def main():
    """Fonction principale d'authentification"""
    print("🚀 AUTHENTIFICATION FREEBOX POUR TRAFFIC SENTINEL")
    print("=" * 60)
    print("Ce script va vous guider pour obtenir les tokens d'accès")
    print("à votre Freebox Server.")
    print()
    
    auth = FreeboxAuth()
    
    # Étape 1 : Détecter la Freebox
    if not auth.step1_detect_freebox():
        return False
    
    # Étape 2 : Demander l'autorisation
    app_token, track_id = auth.step2_request_authorization()
    if not app_token:
        return False
    
    # Étape 3 : Attendre la validation utilisateur
    if not auth.step3_wait_user_validation(track_id):
        return False
    
    # Étape 4 : Obtenir le token de session
    session_token = auth.step4_get_session_token(app_token)
    if not session_token:
        return False
    
    # Étape 5 : Tester l'accès
    if not auth.step5_test_access(session_token):
        print("⚠️ Tests partiellement réussis")
    
    # Étape 6 : Sauvegarder les tokens
    auth.save_tokens(app_token, session_token)
    
    print("\n🎉 AUTHENTIFICATION TERMINÉE AVEC SUCCÈS !")
    print("=" * 60)
    print("Vous pouvez maintenant utiliser les scripts d'intégration Freebox.")
    print()
    
    return True

if __name__ == "__main__":
    main()