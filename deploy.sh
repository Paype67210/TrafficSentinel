#!/bin/bash
"""
Script de déploiement Traffic Sentinel
Facilite l'exécution du playbook Ansible avec les bonnes options
"""

set -e

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonctions d'affichage
print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║               DÉPLOIEMENT TRAFFIC SENTINEL                   ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Vérifications préalables
check_requirements() {
    print_info "Vérification des prérequis..."
    
    # Vérifier ansible
    if ! command -v ansible-playbook &> /dev/null; then
        print_error "Ansible n'est pas installé"
        exit 1
    fi
    
    # Vérifier les fichiers nécessaires
    required_files=(
        "inventory.ini"
        "playbook.yml"
        "vault.yml"
        "traffic_sentinel.py"
        "freebox_auth.py"
        "log_viewer.py"
        "freebox_diagnostic.py"
        "test_freebox_integration.py"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            print_error "Fichier manquant: $file"
            exit 1
        fi
    done
    
    print_success "Tous les prérequis sont satisfaits"
}

# Afficher le menu des options
show_menu() {
    echo ""
    print_info "Options de déploiement:"
    echo "  1) 🚀 Déploiement complet (recommandé)"
    echo "  2) 📦 Scripts seulement (mise à jour)"
    echo "  3) 🔍 Validation seulement"
    echo "  4) 🩺 Test de connexion post-déploiement"
    echo "  5) 📋 Afficher l'inventaire"
    echo "  6) ❌ Annuler"
    echo ""
}

# Exécuter le playbook complet
deploy_full() {
    print_info "🚀 Démarrage du déploiement complet..."
    
    ansible-playbook -i inventory.ini playbook.yml \
        --ask-vault-pass \
        --verbose \
        || {
            print_error "Échec du déploiement"
            exit 1
        }
    
    print_success "Déploiement complet terminé !"
}

# Mettre à jour seulement les scripts
deploy_scripts() {
    print_info "📦 Mise à jour des scripts uniquement..."
    
    ansible-playbook -i inventory.ini playbook.yml \
        --ask-vault-pass \
        --tags "script_copy" \
        --verbose \
        || {
            print_error "Échec de la mise à jour des scripts"
            exit 1
        }
    
    print_success "Scripts mis à jour !"
}

# Validation seulement
deploy_validate() {
    print_info "🔍 Validation de l'installation..."
    
    # D'abord s'assurer que les scripts sont copiés
    print_info "Copie des scripts de validation..."
    ansible-playbook -i inventory.ini playbook.yml \
        --ask-vault-pass \
        --tags "scripts" \
        || {
            print_error "Échec de la copie des scripts"
            exit 1
        }
    
    # Puis validation
    print_info "Exécution de la validation..."
    ansible-playbook -i inventory.ini playbook.yml \
        --ask-vault-pass \
        --tags "validate" \
        || {
            print_error "Échec de la validation"
            exit 1
        }
    
    print_success "Validation réussie !"
}

# Test de connexion
test_connection() {
    print_info "🩺 Test de connexion à la VM..."
    
    ansible all -i inventory.ini -m ping \
        --ask-vault-pass \
        || {
            print_error "Impossible de se connecter à la VM"
            exit 1
        }
    
    print_success "Connexion à la VM réussie !"
    
    # Test du diagnostic Freebox
    print_info "Test du diagnostic Freebox sur la VM..."
    ansible all -i inventory.ini \
        -m shell \
        -a "/usr/local/bin/traffic-diagnostic || true" \
        --ask-vault-pass \
        || {
            print_warning "Le diagnostic Freebox n'est pas encore disponible"
        }
}

# Afficher l'inventaire
show_inventory() {
    print_info "📋 Inventaire Ansible:"
    cat inventory.ini
}

# Menu principal
main_menu() {
    while true; do
        show_menu
        read -p "Choisissez une option (1-6): " choice
        
        case $choice in
            1)
                deploy_full
                break
                ;;
            2)
                deploy_scripts
                break
                ;;
            3)
                deploy_validate
                break
                ;;
            4)
                test_connection
                break
                ;;
            5)
                show_inventory
                ;;
            6)
                print_info "Déploiement annulé"
                exit 0
                ;;
            *)
                print_warning "Option invalide. Veuillez choisir entre 1 et 6."
                ;;
        esac
    done
}

# Post-déploiement
post_deployment() {
    echo ""
    print_success "🎉 DÉPLOIEMENT TERMINÉ !"
    echo ""
    print_info "📋 PROCHAINES ÉTAPES:"
    echo "   1. Connectez-vous à votre VM"
    echo "   2. Exécutez: traffic-help"
    echo "   3. Testez: traffic-diagnostic"
    echo "   4. Surveillez: traffic-logs follow --log freebox"
    echo ""
    print_info "🔗 COMMANDES UTILES:"
    echo "   • ssh <votre-vm>              # Se connecter à la VM"
    echo "   • systemctl status traffic-sentinel-monitor"
    echo "   • traffic-logs health         # État des logs"
    echo ""
}

# Script principal
main() {
    print_header
    check_requirements
    
    # Si des arguments sont passés, les traiter directement
    if [[ $# -gt 0 ]]; then
        case $1 in
            "full")
                deploy_full
                ;;
            "scripts")
                deploy_scripts
                ;;
            "validate")
                deploy_validate
                ;;
            "test")
                test_connection
                ;;
            "inventory")
                show_inventory
                ;;
            *)
                print_error "Argument invalide: $1"
                print_info "Utilisation: $0 [full|scripts|validate|test|inventory]"
                exit 1
                ;;
        esac
    else
        main_menu
    fi
    
    post_deployment
}

# Gestion des signaux
trap 'echo -e "\n"; print_warning "Déploiement interrompu"; exit 1' INT TERM

# Exécution
main "$@"