import os

file_path = 'app.py'
routes_file = 'new_routes.txt'

with open(routes_file, 'r') as f:
    new_routes_code = f.read()

with open(file_path, 'r') as f:
    content = f.read()

start_marker = "@app.route('/sync_vessel_data', methods=['POST'])"
end_marker = "# ERROR HANDLERS"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx != -1 and end_idx != -1:
    # Look for the line specific header above the start marker if it exists
    header_marker = "# SYNC DATA ROUTE"
    header_start = content.rfind(header_marker, 0, start_idx)
    
    if header_start != -1:
         start_idx = header_start - 1 # Go back a bit to capture previous newline
         # Actually let's just use start_marker logic but look up lines
    
    new_content = content[:start_idx] + "\n" + new_routes_code + "\n\n" + content[end_idx:]
    
    with open(file_path, 'w') as f:
        f.write(new_content)
    print("Backend modification complete.")
else:
    print("Could not find markers.")
    print(f"Start: {start_idx}, End: {end_idx}")
