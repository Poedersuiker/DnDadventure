import sqlite3
import json
import os
from flask import Blueprint, jsonify, request, abort

# Blueprint definition
open5e_bp = Blueprint('open5e_bp', __name__)

# Database path: app/api/open5e_api.py -> instance/open5e.db
# os.path.dirname(__file__) is app/api
# os.path.join(os.path.dirname(__file__), '..', '..', 'instance', 'open5e.db')
# app/api/../../instance/open5e.db  => instance/open5e.db
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'instance', 'open5e.db'))

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    if not os.path.exists(DB_PATH):
        # This case should ideally be handled by ensuring create_db.py has run
        print(f"Database file not found at {DB_PATH}")
        abort(500, description="Database not found. Please initialize the database.")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Access columns by name
    return conn

def get_paginated_results(table_name, base_url_path):
    """Helper function to get paginated results for a given table."""
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    offset = (page - 1) * limit

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get total count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_count_row = cursor.fetchone()
    total_count = total_count_row[0] if total_count_row else 0

    # Get paginated results
    query = f"SELECT data FROM {table_name} LIMIT ? OFFSET ?"
    cursor.execute(query, (limit, offset))
    rows = cursor.fetchall()
    conn.close()

    results_list = [json.loads(row['data']) for row in rows]

    # Construct next and previous URLs
    next_url = None
    if (page * limit) < total_count:
        next_url = f"{request.host_url.rstrip('/')}{base_url_path}?page={page + 1}&limit={limit}"

    previous_url = None
    if page > 1:
        previous_url = f"{request.host_url.rstrip('/')}{base_url_path}?page={page - 1}&limit={limit}"
        if page == 2 and offset == limit : # First page if page was 2 and limit is also the offset
             previous_url = f"{request.host_url.rstrip('/')}{base_url_path}?limit={limit}"


    return {
        'count': total_count,
        'next': next_url,
        'previous': previous_url,
        'results': results_list
    }

def get_single_item(table_name, slug):
    """Helper function to get a single item by slug."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = f"SELECT data FROM {table_name} WHERE slug = ?"
    cursor.execute(query, (slug,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return json.loads(row['data'])
    else:
        abort(404, description=f"{table_name[:-1].capitalize()} with slug '{slug}' not found.")

# --- Monsters Endpoints ---
@open5e_bp.route('/v1/monsters/', methods=['GET'])
def list_monsters():
    # The base_url_path needs to be relative to the blueprint's url_prefix
    # If blueprint is at /api, then this path is /api/v1/monsters/
    # request.path gives the full path including the blueprint prefix
    return jsonify(get_paginated_results('monsters', request.path))

@open5e_bp.route('/v1/monsters/<string:slug>/', methods=['GET'])
def get_monster(slug):
    return jsonify(get_single_item('monsters', slug))

# --- Spells Endpoints ---
@open5e_bp.route('/v2/spells/', methods=['GET'])
def list_spells():
    return jsonify(get_paginated_results('spells', request.path))

@open5e_bp.route('/v2/spells/<string:slug>/', methods=['GET'])
def get_spell(slug):
    # Slug here corresponds to the 'key' from the API, which was stored as 'slug'
    return jsonify(get_single_item('spells', slug))

# --- Spell List Endpoints ---
@open5e_bp.route('/v1/spelllist/', methods=['GET'])
def list_spelllist():
    return jsonify(get_paginated_results('spelllist', request.path))

@open5e_bp.route('/v1/spelllist/<string:slug>/', methods=['GET'])
def get_spelllist(slug):
    return jsonify(get_single_item('spelllist', slug))

# --- Documents Endpoints ---
@open5e_bp.route('/v2/documents/', methods=['GET'])
def list_documents():
    return jsonify(get_paginated_results('documents', request.path))

@open5e_bp.route('/v2/documents/<string:slug>/', methods=['GET'])
def get_document(slug):
    return jsonify(get_single_item('documents', slug))

# --- Backgrounds Endpoints ---
@open5e_bp.route('/v2/backgrounds/', methods=['GET'])
def list_backgrounds():
    return jsonify(get_paginated_results('backgrounds', request.path))

@open5e_bp.route('/v2/backgrounds/<string:slug>/', methods=['GET'])
def get_background(slug):
    return jsonify(get_single_item('backgrounds', slug))

# --- Planes Endpoints ---
@open5e_bp.route('/v1/planes/', methods=['GET'])
def list_planes():
    return jsonify(get_paginated_results('planes', request.path))

@open5e_bp.route('/v1/planes/<string:slug>/', methods=['GET'])
def get_plane(slug):
    return jsonify(get_single_item('planes', slug))

# --- Sections Endpoints ---
@open5e_bp.route('/v1/sections/', methods=['GET'])
def list_sections():
    return jsonify(get_paginated_results('sections', request.path))

@open5e_bp.route('/v1/sections/<string:slug>/', methods=['GET'])
def get_section(slug):
    return jsonify(get_single_item('sections', slug))

# --- Feats Endpoints ---
@open5e_bp.route('/v2/feats/', methods=['GET'])
def list_feats():
    return jsonify(get_paginated_results('feats', request.path))

@open5e_bp.route('/v2/feats/<string:slug>/', methods=['GET'])
def get_feat(slug):
    return jsonify(get_single_item('feats', slug))

# --- Conditions Endpoints ---
@open5e_bp.route('/v2/conditions/', methods=['GET'])
def list_conditions():
    return jsonify(get_paginated_results('conditions', request.path))

@open5e_bp.route('/v2/conditions/<string:slug>/', methods=['GET'])
def get_condition(slug):
    return jsonify(get_single_item('conditions', slug))

# --- Races Endpoints ---
@open5e_bp.route('/v2/races/', methods=['GET'])
def list_races():
    return jsonify(get_paginated_results('races', request.path))

@open5e_bp.route('/v2/races/<string:slug>/', methods=['GET'])
def get_race(slug):
    return jsonify(get_single_item('races', slug))

# --- Classes Endpoints ---
@open5e_bp.route('/v1/classes/', methods=['GET'])
def list_classes():
    return jsonify(get_paginated_results('classes', request.path))

@open5e_bp.route('/v1/classes/<string:slug>/', methods=['GET'])
def get_class(slug):
    return jsonify(get_single_item('classes', slug))

# --- Magic Items Endpoints ---
@open5e_bp.route('/v1/magicitems/', methods=['GET'])
def list_magicitems():
    return jsonify(get_paginated_results('magicitems', request.path))

@open5e_bp.route('/v1/magicitems/<string:slug>/', methods=['GET'])
def get_magicitem(slug):
    return jsonify(get_single_item('magicitems', slug))

# --- Weapons Endpoints ---
@open5e_bp.route('/v2/weapons/', methods=['GET'])
def list_weapons():
    return jsonify(get_paginated_results('weapons', request.path))

@open5e_bp.route('/v2/weapons/<string:slug>/', methods=['GET'])
def get_weapon(slug):
    return jsonify(get_single_item('weapons', slug))

# --- Armor Endpoints ---
@open5e_bp.route('/v2/armor/', methods=['GET'])
def list_armor():
    return jsonify(get_paginated_results('armor', request.path))

@open5e_bp.route('/v2/armor/<string:slug>/', methods=['GET'])
def get_armor(slug):
    return jsonify(get_single_item('armor', slug))

# --- Manifest Endpoint (Special Handling) ---
@open5e_bp.route('/v1/manifest/', methods=['GET'])
def get_manifest():
    conn = get_db_connection()
    cursor = conn.cursor()
    # The harvester script stores the manifest with a fixed slug
    query = "SELECT data FROM manifest WHERE slug = 'open5e_manifest_v1'"
    cursor.execute(query)
    row = cursor.fetchone()
    conn.close()

    if row:
        return json.loads(row['data']) # Directly return the parsed JSON object
    else:
        abort(404, description="Manifest data not found. Ensure harvesting script has run.")

# --- Error Handler for 404 ---
@open5e_bp.app_errorhandler(404)
def handle_404(err):
    response = jsonify({'error': 'Not found', 'message': err.description})
    response.status_code = 404
    return response

# --- Error Handler for 500 ---
@open5e_bp.app_errorhandler(500) # More general for blueprint specific 500s if needed
def handle_500(err):
    response = jsonify({'error': 'Internal server error', 'message': err.description})
    response.status_code = 500
    return response
