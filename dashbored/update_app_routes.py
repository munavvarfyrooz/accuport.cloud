import os

file_path = 'app.py'

refactored_code = """
def run_sync_command(vessel_str_id):
    """Helper to run the sync script for a vessel"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.abspath(os.path.join(base_dir, '../datafetcher/src/fetch_and_store.py'))
    config_path = os.path.abspath(os.path.join(base_dir, '../datafetcher/config/vessels_config.yaml'))
    db_path = os.path.abspath(os.path.join(base_dir, '../datafetcher/data/accubase.sqlite'))
    
    cmd = [
        sys.executable,
        script_path,
        vessel_str_id,
        "30", # Default 30 days
        "--config", config_path,
        "--db", db_path
    ]
    
    try:
        # app.logger might not be available in this scope easily if strictly separated, 
        # but here it is in the same file.
        # app.logger.info(f"Running sync command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr
    except Exception as e:
        return False, str(e)

@app.route('/sync_vessel_data', methods=['POST'])
@login_required
def sync_vessel_data():
    """
    Trigger data fetch for the current vessel
    """
    vessel_id = session.get('selected_vessel_id')
    if not vessel_id:
        return jsonify({'success': False, 'message': 'No vessel selected'}), 400

    # Get vessel details to get the string ID (e.g., 'mv_racer')
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        return jsonify({'success': False, 'message': 'Vessel not found'}), 404
    
    vessel_str_id = vessel['vessel_id']
    
    app.logger.info(f"Syncing single vessel: {vessel_str_id}")
    success, output = run_sync_command(vessel_str_id)
    
    if success:
        return jsonify({
            'success': True, 
            'message': 'Data sync completed successfully',
            'details': output
        })
    else:
        app.logger.error(f"Sync failed: {output}")
        return jsonify({
            'success': False, 
            'message': 'Data sync failed',
            'error': output
        }), 500

@app.route('/sync_all_vessels', methods=['POST'])
@login_required
def sync_all_vessels():
    """
    Trigger data fetch for ALL accessible vessels
    """
    # Get all accessible vessels
    vessel_ids = current_user.get_accessible_vessels()
    if not vessel_ids:
        return jsonify({'success': False, 'message': 'No vessels found'}), 404
        
    vessels = get_vessels_by_ids(vessel_ids)
    
    results = []
    success_count = 0
    
    for vessel in vessels:
        vessel_name = vessel['vessel_name']
        vessel_str_id = vessel['vessel_id']
        
        app.logger.info(f"Syncing {vessel_name} ({vessel_str_id})...")
        
        success, output = run_sync_command(vessel_str_id)
        
        results.append({
            'vessel_name': vessel_name,
            'success': success,
            'message': 'Synced successfully' if success else f'Failed: {output[:100]}...'
        })
        
        if success:
            success_count += 1
            
    return jsonify({
        'success': True,
        'total': len(vessels),
        'success_count': success_count,
        'results': results
    })
"""

with open(file_path, 'r') as f:
    content = f.read()

start_marker = "@app.route('/sync_vessel_data', methods=['POST'])"
end_marker = "# ERROR HANDLERS"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx != -1 and end_idx != -1:
    # Be careful about newlines
    # Find the line before start_marker
    # Actually, refactored_code handles the imports and spacing itself mostly.
    
    # The search logic is naive, let's ensure we don't duplicate logic
    
    # Look backwards from start_idx to see if there are previous comments
    
    new_content = content[:start_idx] + refactored_code + "\n\n" + content[end_idx:]
    
    with open(file_path, 'w') as f:
        f.write(new_content)
    print("Backend modification complete.")
else:
    print("Could not find markers.")
    print(f"Start: {start_idx}, End: {end_idx}")