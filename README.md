# TrafficSentinel

Ce projet consiste en la mise en place d'une machine virtuelle Ubuntu sur un serveur Freebox pour surveiller et sécuriser le trafic réseau domestique. Il inclut la gestion d'une liste blanche d'adresses MAC autorisées en connexion filaire, la surveillance des accès Wi-Fi invités, et la détection d'activités suspectes sur le réseau local privé avec envoi d'alertes via webhook sur Slack. Une interface web d'administration est également prévue pour gérer les adresses MAC et surveiller le réseau.

## Fonctionnalités

| Fonctionnalité | Description |
| - | - |
| Surveillance du trafic réseau | Analyse et surveillance du trafic entrant et sortant de la Freebox. |
| Liste blanche des adresses MAC | Autorisation des connexions filaires uniquement pour les adresses MAC enregistrées. |
| Surveillance Wi-Fi invité | Suivi et journalisation des accès au réseau Wi-Fi invité. |
| Détection d'activités suspectes | Identification et alerte en cas d'activités inhabituelles ou suspectes sur le réseau. |
| Alertes Slack | Envoi d'alertes en temps réel sur un canal Slack via webhook. |
| Interface Web d'Administration | Page web sécurisée pour ajouter ou supprimer des adresses MAC et surveiller le réseau. |

## Prérequis

| Prérequis | Description |
| - | - |
| Freebox Server | Un serveur Freebox avec capacité de virtualisation. |
| VM Ubuntu | Une machine virtuelle avec Ubuntu installée et configurée. |
| Accès réseau | Accès administrateur au réseau local et à la Freebox. |
| Compte Slack | Un compte Slack avec permissions pour configurer des webhooks. |
| Nginx | Pour servir l'interface web et ajouter une couche de sécurité supplémentaire. |

## Installation

1. **Créer la VM Ubuntu sur Freebox Server :**
   - Suivre les instructions de Freebox pour créer une nouvelle VM.
   - Installer Ubuntu Server sur la VM.

2. **Configurer la surveillance réseau :**
   - Installer les outils nécessaires pour la surveillance réseau (ex: Wireshark, ntopng).
     `sudo apt install arp-scan ebtables net-tools -y`
   - Configurer les scripts de surveillance pour analyser le trafic.

3. **Mettre en place la liste blanche des adresses MAC :**
   - Modifier les paramètres du serveur DHCP pour n'autoriser que les adresses MAC enregistrées.

4. **Configurer la surveillance Wi-Fi invité :**
   - Utiliser des outils comme `hostapd` pour surveiller les connexions au Wi-Fi invité.

5. **Configurer les alertes Slack :**
   - Créer un webhook entrant sur Slack.
   - Configurer les scripts d'alerte pour envoyer des notifications via le webhook.

6. **Configurer l'interface web d'administration :**
   - Développer une application web avec un framework moderne (React, Vue.js, Angular).
   - Configurer Nginx pour servir l'application web et sécuriser l'accès avec MFA.

## Configuration

1. **Configurer les outils de surveillance :**
   - Modifier les fichiers de configuration des outils de surveillance pour s'adapter au réseau.

2. **Ajouter des adresses MAC à la liste blanche :**
   - Éditer le fichier de configuration de la liste blanche pour ajouter ou supprimer des adresses MAC.

3. **Configurer les alertes :**
   - Personnaliser les messages d'alerte et les conditions de déclenchement dans les scripts d'alerte.

4. **Configurer Nginx :**
   - Configurer Nginx comme reverse-proxy pour gérer le trafic entrant et ajouter une couche de sécurité supplémentaire.

## Utilisation

- **Lancer la surveillance :** Exécuter les scripts de surveillance pour commencer à analyser le trafic réseau.
- **Vérifier les alertes :** Consulter le canal Slack configuré pour recevoir les alertes en temps réel.
- **Gérer la liste blanche :** Utiliser l'interface web pour mettre à jour la liste blanche des adresses MAC autorisées.

## Contribution

Les contributions sont les bienvenues ! Pour contribuer à ce projet, veuillez suivre ces étapes :

1. Fork le projet.
2. Créer une nouvelle branche (`git checkout -b feature/ma-nouvelle-fonctionnalite`).
3. Commiter vos modifications (`git commit -am 'Ajout d'une nouvelle fonctionnalité'`).
4. Pousser la branche (`git push origin feature/ma-nouvelle-fonctionnalite`).
5. Ouvrir une Pull Request.

## Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

## Contact

Pour toute question ou suggestion, n'hésitez pas à ouvrir une issue ou à me contacter directement.

