# Traffic Sentinel

## 📋 Vue d'ensemble

**Traffic Sentinel** est un système de monitoring et de contrôle d'accès réseau avec intégration Freebox. Il permet de détecter automatiquement les nouveaux appareils sur votre réseau et de contrôler leur accès WiFi directement via l'API de votre Freebox.

### ✨ Fonctionnalités principales

- 🔍 **Détection automatique** des nouveaux appareils sur le réseau
- 🚫 **Blocage/déblocage immédiat** via le filtre MAC WiFi de la Freebox
- 🌐 **Interface web** intuitive pour gérer les appareils
- 📊 **Surveillance en temps réel** du trafic réseau
- 📝 **Logging complet** de toutes les opérations
- 🔔 **Notifications Slack** pour les nouveaux appareils (optionnel)

### 🏗️ Architecture

```
┌─────────────────────────┐
│   Interface Web Flask   │  ← Gestion des appareils
│   (Port 5000)           │
└───────────┬─────────────┘
            │
┌───────────▼─────────────┐
│  Traffic Sentinel       │  ← Service de monitoring
│  (Python)               │
└───────────┬─────────────┘
            │
            ├──► Base de données SQLite (appareils)
            ├──► API Freebox (blocage/déblocage)
            └──► Logs (/var/log/traffic_sentinel/)
```

---

## 🚀 Installation et Déploiement

### Prérequis

- **VM cible** : Ubuntu/Debian avec Python 3
- **Ansible** installé sur la machine de déploiement
- **Accès SSH** à la VM cible
- **Freebox** avec API activée (Freebox v6 ou supérieure)

### Déploiement automatique

```bash
# 1. Cloner le projet
git clone <repository-url>
cd VM_NetViewer_VLigne

# 2. Configurer l'inventaire Ansible
# Éditer inventory.ini avec l'IP de votre VM
nano inventory.ini

# 3. Lancer le déploiement
./deploy.sh
```

Le script de déploiement va :
- Installer les dépendances Python
- Créer les répertoires nécessaires
- Copier les scripts sur la VM
- Configurer les services systemd
- Générer les certificats SSL
- Configurer le pare-feu

### Configuration manuelle (alternative)

Si vous préférez un déploiement manuel :

```bash
# Sur la VM cible
sudo apt update
sudo apt install python3 python3-pip sqlite3 nginx

# Installer les dépendances Python
pip3 install flask requests

# Créer les répertoires
sudo mkdir -p /opt/traffic_sentinel
sudo mkdir -p /var/lib/mac_filter
sudo mkdir -p /var/log/traffic_sentinel

# Copier les fichiers
sudo cp traffic_sentinel.py /opt/traffic_sentinel/
sudo cp web_interface.py /opt/traffic_sentinel/
sudo cp freebox_auth.py /opt/traffic_sentinel/
sudo cp freebox_reauth.py /opt/traffic_sentinel/
sudo cp freebox_integration.py /opt/traffic_sentinel/
sudo cp freebox_sync_service.py /opt/traffic_sentinel/
sudo cp log_viewer.py /opt/traffic_sentinel/
sudo cp -r templates /opt/traffic_sentinel/

# Configurer les services (voir playbook.yml pour les fichiers systemd)
```

---

## 🔧 Configuration

### 1. Authentification Freebox

**Première étape obligatoire** : autoriser l'application sur votre Freebox.

```bash
# Sur la VM
sudo python3 /opt/traffic_sentinel/freebox_auth.py
```

Pendant l'exécution :
1. Le script affiche un message demandant l'autorisation
2. **Appuyez sur le bouton ► de votre Freebox** (voyant qui clignote)
3. Les tokens sont sauvegardés automatiquement

Les tokens sont stockés dans `/etc/traffic_sentinel_tokens.json` avec un système de fallback multi-emplacements pour une meilleure résilience.

### 2. Configuration des variables d'environnement

Le système utilise des variables d'environnement (configurées dans les fichiers systemd) :

- `DB_PATH` : Chemin de la base de données (défaut: `/var/lib/mac_filter/database.db`)
- `INTERFACE` : Interface réseau à surveiller (défaut: `enp0s5`)
- `SLACK_WEBHOOK_URL` : URL du webhook Slack (optionnel)
- `SCAN_INTERVAL` : Intervalle entre les scans en secondes (défaut: `300`)

### 3. Démarrage des services

```bash
# Démarrer les services
sudo systemctl start traffic-sentinel          # Interface web
sudo systemctl start traffic-sentinel-monitor  # Monitoring réseau

# Activer le démarrage automatique
sudo systemctl enable traffic-sentinel
sudo systemctl enable traffic-sentinel-monitor

# Vérifier l'état
sudo systemctl status traffic-sentinel
sudo systemctl status traffic-sentinel-monitor
```

---

## 💻 Utilisation

### Interface Web

L'interface web est accessible via :
- **HTTP** : `http://<ip-vm>:5000`
- **HTTPS** : `https://<ip-vm>` (si nginx est configuré)

#### Fonctionnalités de l'interface

1. **Liste des appareils** : Affiche tous les appareils détectés avec :
   - Adresse MAC
   - Statut (autorisé, banni, quarantaine)
   - Dates de première/dernière détection
   - Commentaire

2. **Changer le statut** :
   - Sélectionner un statut dans le menu déroulant
   - Cliquer sur "Mettre à jour"
   - **L'action est appliquée immédiatement** sur la Freebox
   - Un message de confirmation s'affiche

3. **Ajouter un appareil** :
   - Entrer l'adresse MAC
   - Choisir le statut
   - Ajouter un commentaire (optionnel)

4. **Modifier le commentaire** :
   - Utile pour identifier les appareils ("iPhone de Pierre", "Imprimante bureau", etc.)

### Statuts des appareils

- **✅ Autorisé** (`authorized`) : Accès WiFi complet
- **❌ Banni** (`banned`) : Bloqué via le filtre MAC WiFi Freebox
- **⚠️ Quarantaine** (`quarantine`) : Nouveau appareil détecté, **bloqué automatiquement** en attendant validation

### Workflow typique

1. **Détection** : Un nouvel appareil se connecte au réseau
2. **Blocage automatique** : Le système le met en quarantaine et le bloque immédiatement
3. **Notification** : Une alerte Slack est envoyée (si configuré) avec le nom et la MAC
4. **Décision manuelle** : L'administrateur consulte l'interface web
5. **Autorisation ou bannissement** : 
   - Si c'est un appareil légitime → statut "Autorisé" → déblocage immédiat
   - Si c'est un intrus → statut "Banni" → reste bloqué définitivement

---

## 🔍 Surveillance et Logs

### Visualiser les logs

```bash
# Logs en temps réel de l'interface web
sudo journalctl -u traffic-sentinel -f

# Logs en temps réel du monitoring
sudo journalctl -u traffic-sentinel-monitor -f

# Logs détaillés dans les fichiers
sudo tail -f /var/log/traffic_sentinel/traffic_sentinel.log
sudo tail -f /var/log/traffic_sentinel/freebox_operations.log
```

### Utiliser le visualiseur de logs

```bash
# Analyser les logs
python3 /opt/traffic_sentinel/log_viewer.py

# Filtrer par appareil
sudo journalctl -u traffic-sentinel | grep "aa:bb:cc:dd:ee:ff"
```

### Structure des logs

Les logs sont organisés par type :
- **traffic_sentinel.log** : Événements principaux (détection, scan réseau)
- **freebox_operations.log** : Opérations API Freebox (blocage, déblocage, session)

Rotation automatique :
- Quotidienne
- Conservation 30 jours
- Compression automatique

---

## 🛠️ Fonctionnement Technique

### Détection des appareils

Le service `traffic-sentinel-monitor` scanne régulièrement le réseau :

```python
# Scan ARP pour détecter les appareils actifs
arp -a -i <interface>

# Extraction des adresses MAC
# Mise à jour de la base de données
# Application des règles selon le statut
```

### Blocage via Freebox

Le système utilise l'**API Freebox v15** pour bloquer les appareils :

**Endpoint utilisé** : `/api/v15/wifi/mac_filter/`

**Blocage** :
```python
POST /api/v15/wifi/mac_filter/
{
    "mac": "XX:XX:XX:XX:XX:XX",
    "type": "blacklist"
}
```

**Déblocage** :
```python
DELETE /api/v15/wifi/mac_filter/{mac}-blacklist
```

**Avantages** :
- ✅ Blocage au niveau du routeur (impossible à contourner depuis le réseau)
- ✅ Déconnexion immédiate (< 3 secondes)
- ✅ Pas de règles iptables complexes à gérer
- ✅ Visible dans l'interface Freebox

### Vérification des incohérences

Tous les 3 scans (~90 secondes), le système vérifie que l'état des appareils en base de données correspond à leur état sur la Freebox :

```python
# Récupérer l'état BDD
# Récupérer l'état Freebox
# Comparer et corriger les différences automatiquement
```

Cela garantit la cohérence même si :
- Un changement manuel est fait dans l'interface Freebox
- Une erreur API se produit temporairement
- Un appareil était déconnecté lors du changement de statut

---

## 🔐 Sécurité

### Gestion des tokens Freebox

Les tokens d'authentification sont stockés de manière sécurisée avec un système multi-emplacements :

1. `/etc/traffic_sentinel_tokens.json` (prioritaire)
2. `/opt/traffic_sentinel/tokens.json` (fallback)
3. `/tmp/traffic_sentinel_tokens.json` (fallback temporaire)
4. `./traffic_sentinel_tokens.json` (dernier recours)

Permissions automatiques : `666` avec propriétaire `www-data`

### Renouvellement de session

Les sessions Freebox expirent après quelques heures. Le système :
- Détecte automatiquement l'expiration
- Renouvelle la session sans intervention
- Continue les opérations sans interruption

En cas de problème :
```bash
# Forcer un renouvellement manuel
sudo python3 /opt/traffic_sentinel/freebox_reauth.py
```

### Pare-feu

Le déploiement configure automatiquement UFW :
- Port 22 (SSH)
- Port 80 (HTTP)
- Port 443 (HTTPS)
- Port 5000 (Flask) - À restreindre selon vos besoins

---

## 📊 API et Intégrations

### Notifications Slack

Pour activer les notifications Slack :

1. Créer un webhook Slack dans votre workspace
2. Ajouter l'URL dans les variables d'environnement du service :

```bash
# Éditer le fichier systemd
sudo systemctl edit traffic-sentinel-monitor

# Ajouter :
[Service]
Environment="SLACK_WEBHOOK_URL=https://hooks.slack.com/services/..."
```

3. Redémarrer le service :
```bash
sudo systemctl daemon-reload
sudo systemctl restart traffic-sentinel-monitor
```

Les alertes Slack incluent :
- **Nom de l'appareil** (hostname récupéré via Freebox)
- Adresse MAC
- Statut
- Date de détection

### Base de données

Structure SQLite (`/var/lib/mac_filter/database.db`) :

```sql
CREATE TABLE mac_addresses (
    mac_address TEXT PRIMARY KEY,
    status TEXT NOT NULL,           -- 'authorized', 'banned', 'quarantine'
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    comment TEXT
);
```

Accès direct :
```bash
sqlite3 /var/lib/mac_filter/database.db
SELECT * FROM mac_addresses;
```

---

## 🐛 Dépannage

### Problèmes courants

#### 1. L'API Freebox ne répond pas

**Symptômes** : Erreurs `auth_required` dans les logs

**Solutions** :
```bash
# Vérifier les tokens
sudo cat /etc/traffic_sentinel_tokens.json

# Régénérer l'autorisation
sudo python3 /opt/traffic_sentinel/freebox_reauth.py

# Vérifier la connexion réseau
ping 192.168.0.254  # IP Freebox par défaut
```

#### 2. Le blocage ne fonctionne pas

**Vérifications** :
```bash
# Vérifier que le filtre MAC est activé sur la Freebox
# Interface Freebox > Paramètres WiFi > Filtrage MAC

# Vérifier les permissions de l'application
# L'app doit avoir les permissions "settings" et "lan"

# Consulter les logs
sudo journalctl -u traffic-sentinel-monitor | grep "BLOQUÉ"
```

#### 3. Interface web inaccessible

**Solutions** :
```bash
# Vérifier l'état du service
sudo systemctl status traffic-sentinel

# Redémarrer
sudo systemctl restart traffic-sentinel

# Vérifier les ports
sudo ss -tlnp | grep 5000

# Vérifier les logs
sudo journalctl -u traffic-sentinel -n 50
```

#### 4. Permissions denied sur les tokens

Le système gère automatiquement les permissions avec fallback, mais si nécessaire :

```bash
# Corriger les permissions manuellement
sudo chmod 666 /etc/traffic_sentinel_tokens.json
sudo chown www-data:www-data /etc/traffic_sentinel_tokens.json
```

---

## 🔄 Maintenance

### Mise à jour du code

```bash
# Sur la machine de déploiement
git pull

# Redéployer
./deploy.sh

# Ou copier manuellement les fichiers modifiés
scp traffic_sentinel.py user@vm:/tmp/
ssh user@vm 'sudo mv /tmp/traffic_sentinel.py /opt/traffic_sentinel/ && sudo systemctl restart traffic-sentinel-monitor'
```

### Sauvegarde

Fichiers critiques à sauvegarder régulièrement :

```bash
# Tokens Freebox
/etc/traffic_sentinel_tokens.json

# Base de données
/var/lib/mac_filter/database.db

# Logs (optionnel)
/var/log/traffic_sentinel/
```

Script de sauvegarde automatique :
```bash
#!/bin/bash
BACKUP_DIR="/backup/traffic_sentinel/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR
cp /etc/traffic_sentinel_tokens.json $BACKUP_DIR/
cp /var/lib/mac_filter/database.db $BACKUP_DIR/
```

### Surveillance

```bash
# État des services
sudo systemctl status traffic-sentinel traffic-sentinel-monitor

# Utilisation des ressources
top -p $(pgrep -f traffic_sentinel)

# Espace disque logs
du -sh /var/log/traffic_sentinel/

# Taille de la base
du -h /var/lib/mac_filter/database.db
```

---

## 📚 Fichiers du Projet

```
.
├── traffic_sentinel.py          # Service principal de monitoring
├── web_interface.py             # Interface web Flask
├── freebox_auth.py              # Script d'authentification initial
├── freebox_reauth.py            # Renouvellement d'authentification
├── freebox_integration.py       # Intégration API Freebox
├── freebox_sync_service.py      # Service de synchronisation
├── log_viewer.py                # Visualiseur de logs
├── templates/
│   └── index.html               # Template de l'interface web
├── deploy.sh                    # Script de déploiement
├── playbook.yml                 # Playbook Ansible
├── inventory.ini                # Inventaire Ansible
├── vault.yml                    # Variables Ansible chiffrées
└── README.md                    # Ce fichier
```

---

## 🎓 Cas d'Usage

### Contrôle parental

Bloquer automatiquement les appareils des enfants pendant certaines heures (à implémenter via cron) :

```bash
# Bloquer le soir
0 22 * * * python3 /opt/traffic_sentinel/block_device.py AA:BB:CC:DD:EE:FF

# Débloquer le matin
0 8 * * * python3 /opt/traffic_sentinel/allow_device.py AA:BB:CC:DD:EE:FF
```

### Réseau invité sécurisé

Mettre tous les nouveaux appareils en quarantaine par défaut, autoriser manuellement uniquement les invités de confiance.

### Détection d'intrusion

Recevoir immédiatement une notification Slack quand un appareil inconnu tente de se connecter au réseau.

### Gestion multi-sites

Déployer sur plusieurs VM pour gérer plusieurs sites, centraliser les logs via un serveur de logs central.

---

## 🤝 Contribution

Le projet est ouvert aux contributions. Pour proposer des améliorations :

1. Identifier le besoin
2. Tester localement
3. Documenter les changements
4. Créer un commit avec description claire

---

## 📝 Changelog

### Version 2.1 (Décembre 2025)
- ✅ Blocage immédiat des appareils en quarantaine
- ✅ Hostname dans les alertes Slack
- ✅ Nettoyage du code et documentation consolidée

### Version 2.0 (Novembre 2025)
- ✅ Utilisation du filtre MAC WiFi Freebox (API v15)
- ✅ Application immédiate des changements depuis l'interface web
- ✅ Vérification périodique des incohérences
- ✅ Système de fallback multi-emplacements pour les tokens

### Version 1.0 (Octobre 2025)
- ✅ Version initiale
- ✅ Détection automatique des appareils
- ✅ Interface web de gestion
- ✅ Intégration Freebox via API

---

## 📞 Support

Pour toute question ou problème :

1. Consulter les logs : `sudo journalctl -u traffic-sentinel -f`
2. Vérifier la documentation ci-dessus
3. Tester avec le script de diagnostic : `python3 /opt/traffic_sentinel/log_viewer.py`

---

**Auteur** : Philippe DESON
**Licence** : MIT  
**Version** : 2.1  
**Dernière mise à jour** : Décembre 2025
