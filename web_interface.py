#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
import sys

# Importer la classe FreeboxAPI depuis traffic_sentinel
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from traffic_sentinel import FreeboxAPI, freebox_logger

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Pour les messages flash
DB_PATH = os.getenv('DB_PATH', '/var/lib/mac_filter/database.db')
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
INTERFACE = os.getenv('INTERFACE')

# Initialiser l'API Freebox pour les actions immédiates
freebox_api = FreeboxAPI()
freebox_initialized = False

def ensure_freebox_connection():
    """S'assurer que la connexion Freebox est établie"""
    global freebox_initialized
    if not freebox_initialized:
        if freebox_api.initialize():
            freebox_initialized = True
            freebox_logger.info("✅ Connexion Freebox établie pour l'interface web")
        else:
            freebox_logger.warning("⚠️ Impossible d'établir la connexion Freebox")
    return freebox_initialized

def get_db_connection():
    """Créer une connexion à la base de données"""
    return sqlite3.connect(DB_PATH)

@app.route("/")
def index():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT mac_address, status, first_seen, last_seen, comment FROM mac_addresses")
    macs = c.fetchall()
    conn.close()
    return render_template("index.html", macs=macs)

@app.route("/update", methods=["POST"])
def update():
    mac_address = request.form["mac_address"]
    new_status = request.form["status"]
    
    # Récupérer l'ancien statut
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT status FROM mac_addresses WHERE mac_address = ?", (mac_address,))
    old_status_row = c.fetchone()
    old_status = old_status_row[0] if old_status_row else None
    
    # Mettre à jour la BDD
    c.execute("UPDATE mac_addresses SET status = ? WHERE mac_address = ?", (new_status, mac_address))
    conn.commit()
    conn.close()
    
    # CORRECTION CRITIQUE: Appliquer immédiatement le changement sur la Freebox
    if old_status != new_status:
        ensure_freebox_connection()
        
        if freebox_api.connected:
            freebox_logger.info(f"🔄 Changement de statut pour {mac_address}: {old_status} → {new_status}")
            
            if new_status == "banned":
                # Bloquer immédiatement sur la Freebox
                freebox_logger.info(f"🚫 Application immédiate du blocage pour {mac_address}")
                if freebox_api.block_device_by_mac(mac_address):
                    flash(f"✅ Appareil {mac_address} bloqué avec succès sur la Freebox", "success")
                    freebox_logger.info(f"✅ {mac_address} bloqué avec succès via interface web")
                else:
                    flash(f"⚠️ Appareil {mac_address} marqué comme banni mais le blocage Freebox a échoué", "warning")
                    freebox_logger.warning(f"⚠️ Échec du blocage Freebox pour {mac_address}")
            
            elif new_status == "authorized":
                # Débloquer immédiatement sur la Freebox
                freebox_logger.info(f"✅ Application immédiate de l'autorisation pour {mac_address}")
                if freebox_api.allow_device_by_mac(mac_address):
                    flash(f"✅ Appareil {mac_address} autorisé avec succès sur la Freebox", "success")
                    freebox_logger.info(f"✅ {mac_address} autorisé avec succès via interface web")
                else:
                    flash(f"⚠️ Appareil {mac_address} marqué comme autorisé mais le déblocage Freebox a échoué", "warning")
                    freebox_logger.warning(f"⚠️ Échec du déblocage Freebox pour {mac_address}")
            
            elif new_status == "quarantine":
                # Pour la quarantaine, on peut laisser tel quel (pas d'action Freebox)
                flash(f"ℹ️ Appareil {mac_address} mis en quarantaine", "info")
                freebox_logger.info(f"ℹ️ {mac_address} mis en quarantaine")
        else:
            flash(f"⚠️ Statut modifié en BDD mais Freebox API non disponible. Le changement sera appliqué au prochain scan.", "warning")
            freebox_logger.warning(f"⚠️ Changement de statut pour {mac_address} en BDD uniquement - Freebox API non connectée")
    
    return redirect(url_for("index"))

@app.route("/add", methods=["POST"])
def add_mac():
    """Ajouter une nouvelle adresse MAC"""
    mac_address = request.form.get("mac_address", "").lower()
    if mac_address:
        status = request.form.get("status", "quarantine")
        comment = request.form.get("comment", "")
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Vérifier si l'appareil existe déjà
        c.execute("SELECT first_seen, comment FROM mac_addresses WHERE mac_address = ?", (mac_address,))
        existing = c.fetchone()
        
        if existing:
            # Mise à jour en préservant first_seen et en gardant le commentaire si pas vide
            existing_comment = existing[1] if existing[1] else ""
            final_comment = comment if comment else existing_comment
            c.execute("""
                UPDATE mac_addresses 
                SET status = ?, last_seen = datetime('now'), comment = ? 
                WHERE mac_address = ?
            """, (status, final_comment, mac_address))
        else:
            # Nouvel enregistrement
            c.execute("""
                INSERT INTO mac_addresses 
                (mac_address, status, first_seen, last_seen, comment) 
                VALUES (?, ?, datetime('now'), datetime('now'), ?)
            """, (mac_address, status, comment))
        
        conn.commit()
        conn.close()
    
    return redirect(url_for("index"))

@app.route("/delete", methods=["POST"])
def delete_mac():
    """Supprimer une adresse MAC"""
    mac_address = request.form.get("mac_address", "")
    if mac_address:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM mac_addresses WHERE mac_address = ?", (mac_address,))
        conn.commit()
        conn.close()
        print(f"Adresse MAC supprimée : {mac_address}")
    
    return redirect(url_for("index"))

@app.route("/update_comment", methods=["POST"])
def update_comment():
    """Modifier le commentaire d'une adresse MAC"""
    mac_address = request.form.get("mac_address", "")
    comment = request.form.get("comment", "")
    if mac_address:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE mac_addresses SET comment = ? WHERE mac_address = ?", (comment, mac_address))
        conn.commit()
        conn.close()
        print(f"Commentaire mis à jour pour {mac_address}: {comment}")
    
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)