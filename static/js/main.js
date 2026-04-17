document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const runBtn = document.getElementById('run-btn');
    const historyList = document.getElementById('history-list');
    
    let selectedFile = null;

    // --- History Loading ---
    const loadHistory = async () => {
        try {
            const res = await fetch('/history');
            const data = await res.json();
            renderHistory(data);
        } catch (e) { console.error('History load failed', e); }
    };

    let allHistory = [];

    const renderHistory = (data) => {
        allHistory = data || [];
        if (allHistory.length === 0) {
            historyList.innerHTML = '<div class="empty-msg">No calibration yet</div>';
            return;
        }
        historyList.innerHTML = allHistory.map((item, index) => `
            <div class="history-item" onclick="loadHistoryItem(${index})">
                <div class="ts">${item.timestamp}</div>
                <div class="file-name">${item.file}</div>
                <div class="ts">${getScale(item).toFixed(4)} \u00b5m/px</div>
                <div class="delete-action" onclick="event.stopPropagation(); deleteHistory('${item.timestamp}')">
                    <span class="trash-icon"></span>
                </div>
            </div>
        `).join('');
    };

    const getScale = (itemOrData) => {
        const scale = itemOrData?.scale_um_per_px ?? itemOrData?.mean_scale ?? itemOrData?.SCALE_UM_PER_PX ?? itemOrData?.SCALE_X ?? itemOrData?.scale_x ?? 0;
        return Number.isFinite(scale) ? scale : 0;
    };

    window.loadHistoryItem = (index) => {
        const item = allHistory[index];
        if (!item) return;
        
        // Mock a data object for showResults
        const data = {
            SCALE_X: getScale(item),
            SCALE_Y: getScale(item),
            SCALE_UM_PER_PX: getScale(item),
            tilt_angle: item.tilt_angle || 0,
            width: item.width || 0,
            height: item.height || 0,
            debug_url: item.debug_url
        };
        showResults(data);
        showToast('Loaded measurement from ' + item.timestamp);
    };

    loadHistory();

    // --- Drag and Drop ---
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(name => {
        dropZone.addEventListener(name, e => {
            e.preventDefault();
            e.stopPropagation();
        });
    });

    dropZone.addEventListener('dragover', () => dropZone.classList.add('dragover'));
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));

    dropZone.addEventListener('drop', (e) => {
        dropZone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });

    fileInput.addEventListener('change', () => handleFiles(fileInput.files));

    const handleFiles = (files) => {
        if (files.length > 0) {
            selectedFile = files[0];
            dropZone.querySelector('h3').textContent = selectedFile.name;
            dropZone.querySelector('p').textContent = `File selected (${(selectedFile.size/1024).toFixed(1)} KB)`;
        }
    };

    // --- Analysis ---
    runBtn.addEventListener('click', async () => {
        if (!selectedFile) {
            alert('Please select an image first.');
            return;
        }

        runBtn.textContent = 'Analyzing...';
        runBtn.disabled = true;

        const type = document.querySelector('input[name="target-type"]:checked').value;
        const spacing = document.getElementById('spacing-input').value;

        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('type', type);
        formData.append('spacing', spacing);

        try {
            const res = await fetch('/analyze', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            
            if (data.error) {
                alert('Error: ' + data.error);
            } else {
                showResults(data);
                renderHistory(data.history);
            }
        } catch (e) {
            alert('Server error: ' + e);
        } finally {
            runBtn.textContent = 'Run Analysis';
            runBtn.disabled = false;
        }
    });

    const showResults = (data) => {
        document.getElementById('results-view').style.display = 'block';
        updateScaleDisplay(getScale(data));
        
        document.getElementById('tilt-angle-val').textContent = (data.tilt_angle || 0).toFixed(2) + '\u00b0';
        document.getElementById('resolution-val').textContent = `${data.width || 0} x ${data.height || 0}`;
        document.getElementById('debug-img').src = data.debug_url;
        
        // Scroll to results
        document.getElementById('results-view').scrollIntoView({ behavior: 'smooth' });
    };

    const updateScaleDisplay = (scale) => {
        const text = getScale({ SCALE_UM_PER_PX: scale }).toFixed(6);
        const newEl = document.getElementById('scale-val');
        if (newEl) newEl.textContent = text;

        const oldX = document.getElementById('scale-x-val');
        const oldY = document.getElementById('scale-y-val');
        if (oldX) oldX.textContent = text;
        if (oldY) oldY.textContent = text;
    };
});

// --- Utilities ---
const showToast = (msg) => {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2000);
};

function copyText(id) {
    const el = document.getElementById(id);
    if (!el) return;
    const text = el.textContent;
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!');
    });
}

async function deleteHistory(ts) {
    if (!confirm('Are you sure you want to delete this calibration record?')) return;
    
    try {
        const res = await fetch('/history/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ timestamp: ts })
        });
        const data = await res.json();
        
        if (data.error) {
            alert('Error: ' + data.error);
        } else {
            // Re-render history list with the new data
            const historyList = document.getElementById('history-list');
            if (data.history.length === 0) {
                historyList.innerHTML = '<div class="empty-msg">No calibration yet</div>';
            } else {
                historyList.innerHTML = data.history.map(item => `
                    <div class="history-item">
                        <div class="ts">${item.timestamp}</div>
                        <div class="file-name">${item.file}</div>
                        <div class="ts">${(item.scale_um_per_px ?? item.mean_scale ?? item.scale_x ?? 0).toFixed(4)} \u00b5m/px</div>
                        <div class="delete-action" onclick="deleteHistory('${item.timestamp}')">
                            <span class="trash-icon"></span>
                        </div>
                    </div>
                `).join('');
            }
            showToast('Record deleted.');
        }
    } catch (e) {
        alert('Server error: ' + e);
    }
}
