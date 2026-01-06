import os

file_path = 'templates/base.html'

# 1. Define content to insert
new_button_html = """
                        <button id="syncAllButton" class="btn btn-outline-sync-primary ms-2" onclick="syncAllData()">
                            <i class="bi bi-cloud-arrow-up"></i> Sync All
                        </button>
"""

new_modal_js = """
<!-- Sync Results Modal -->
<div class="modal fade" id="syncResultsModal" tabindex="-1">
  <div class="modal-dialog modal-lg">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">Sync All Vessels</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <div id="syncAllProgress" class="text-center py-4">
             <div class="spinner-border text-primary" role="status"></div>
             <p class="mt-2">Syncing all vessels... This may take a moment.</p>
        </div>
        <div id="syncAllResults" style="display:none;">
            <div class="alert alert-info">
                <strong>Status:</strong> <span id="syncAllStatusText">Completed</span>
            </div>
            <table class="table table-sm">
                <thead>
                    <tr>
                        <th>Vessel</th>
                        <th>Status</th>
                        <th>Message</th>
                    </tr>
                </thead>
                <tbody id="syncAllResultsBody">
                </tbody>
            </table>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" onclick="window.location.reload()">Close & Reload</button>
      </div>
    </div>
  </div>
</div>

<script>
async function syncAllData() {
    const modal = new bootstrap.Modal(document.getElementById('syncResultsModal'));
    const progressDiv = document.getElementById('syncAllProgress');
    const resultsDiv = document.getElementById('syncAllResults');
    const tbody = document.getElementById('syncAllResultsBody');
    
    // Reset UI
    progressDiv.style.display = 'block';
    resultsDiv.style.display = 'none';
    tbody.innerHTML = '';
    modal.show();
    
    try {
        const response = await fetch('/sync_all_vessels', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        // Hide progress, show results
        progressDiv.style.display = 'none';
        resultsDiv.style.display = 'block';
        
        if (response.ok && data.success) {
            document.getElementById('syncAllStatusText').textContent = `Synced ${data.success_count} / ${data.total} vessels successfully.`;
            
            data.results.forEach(res => {
                const row = document.createElement('tr');
                const statusIcon = res.success ? '<span class="badge bg-success">Success</span>' : '<span class="badge bg-danger">Failed</span>';
                row.innerHTML = `
                    <td>${res.vessel_name}</td>
                    <td>${statusIcon}</td>
                    <td class="small text-muted">${res.message}</td>
                `;
                tbody.appendChild(row);
            });
        } else {
            document.getElementById('syncAllStatusText').textContent = 'Error: ' + (data.message || 'Unknown error');
            document.getElementById('syncAllStatusText').className = 'text-danger';
        }
        
    } catch (error) {
        console.error('Error:', error);
        progressDiv.style.display = 'none';
        resultsDiv.style.display = 'block';
        document.getElementById('syncAllStatusText').textContent = 'Critical Network Error';
    }
}
</script>
"""

with open(file_path, 'r') as f:
    lines = f.readlines()

# 2. Insert Button
# Find existing sync button and insert after
btn_insert_idx = -1
for i, line in enumerate(lines):
    if 'id="syncButton"' in line:
        btn_insert_idx = i + 1 # Insert after the button line
        break

if btn_insert_idx != -1:
    lines.insert(btn_insert_idx, new_button_html)

# 3. Insert Modal/JS
# Find </body> and insert before
js_insert_idx = -1
for i, line in enumerate(lines):
    if '</body>' in line:
        js_insert_idx = i
        break

if js_insert_idx != -1:
    lines.insert(js_insert_idx, new_modal_js)

with open(file_path, 'w') as f:
    f.writelines(lines)

print("Frontend modification complete.")
