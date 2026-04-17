import os
import time
import json
import webbrowser
from threading import Timer
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')
app.config['MEMORY_FILE'] = os.path.join(basedir, '..', 'calibration_memory.json')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def history_scale(item):
    """Return a usable scale value from a history record, or None."""
    raw = item.get('scale_um_per_px', item.get('mean_scale', item.get('scale_x')))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(value):
        return None
    # Reject stale outliers from the previous broken calibration logic.
    if not (0.5 <= value <= 2.0):
        return None
    return value

def estimate_global_rotation(gray):
    """Detect dominant lines and return a rough angle in degrees."""
    # Downsample slightly for speed
    h, w = gray.shape
    if w > 1000:
        gray = cv2.resize(gray, (0, 0), fx=0.5, fy=0.5)
    
    edges = cv2.Canny(gray.astype(np.uint8), 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi/180, 80)
    
    if lines is None:
        return 0.0
        
    angles = []
    for rho, theta in lines[:, 0]:
        deg = np.degrees(theta)
        # Normalize to [-45, 45] relative to vertical (0) or horizontal (90/180) axis
        if deg > 45 and deg < 135:
            angles.append(deg - 90)
        elif deg >= 135:
            angles.append(deg - 180)
        else:
            angles.append(deg)
            
    return float(np.median(angles))

def estimate_period_autocorr(profile, max_fraction=0.4):
    """Estimate the fundamental period from the first strong autocorrelation peak.

    This is more stable than picking the strongest FFT peak because it tends to
    reject harmonics/subharmonics and returns a single physical spacing.
    """
    x = np.asarray(profile, dtype=np.float32)
    n = len(x)
    if n < 8:
        return None

    x = x - np.mean(x)
    if np.allclose(x, 0):
        return None

    # High-pass detrend to suppress illumination gradients.
    sigma = max(3.0, n / 30)
    blur = cv2.GaussianBlur(x.reshape(1, -1), (0, 0), sigma).flatten()
    x = (x - blur) * np.hanning(n)

    # Autocorrelation via FFT, normalized so lag 0 is 1.0.
    ac = np.fft.irfft(np.abs(np.fft.rfft(x)) ** 2)
    ac = ac[: max(4, int(n * max_fraction))]
    if len(ac) < 4:
        return None
    if abs(ac[0]) < 1e-12:
        return None
    ac = ac / ac[0]
    ac[0] = 0.0

    from scipy.signal import find_peaks

    # Search for the first meaningful positive peak after a few pixels.
    min_lag = 3
    peaks, props = find_peaks(ac[min_lag:], prominence=max(0.02, float(np.max(ac[min_lag:])) * 0.08))
    if len(peaks) > 0:
        peaks = peaks + min_lag
        prominences = props.get('prominences', np.ones(len(peaks)))
        # Prefer the earliest peak that is still strong.
        best_idx = int(peaks[np.argmax(prominences / np.maximum(peaks, 1))])
        return float(best_idx)

    # Fallback: look for the strongest FFT candidate, but bias toward longer periods
    # so that harmonics are less likely to win.
    P = np.abs(np.fft.rfft(x))
    f = np.fft.rfftfreq(n)
    P[f < 1.0 / (max_fraction * n)] = 0
    if len(P) < 3:
        return None

    peaks, _ = find_peaks(P, height=float(np.max(P)) * 0.1, distance=3)
    if len(peaks) == 0:
        return None

    candidates = []
    for p_idx in peaks:
        if 0 < p_idx < len(P) - 1:
            vals = [max(1e-12, float(P[i])) for i in (p_idx - 1, p_idx, p_idx + 1)]
            y1, y2, y3 = np.log(vals)
            denom = (y1 - 2 * y2 + y3)
            ref_idx = p_idx + 0.5 * (y1 - y3) / denom if abs(denom) > 1e-12 else float(p_idx)
            period = 1.0 / (float(ref_idx) / n)
            power = float(P[p_idx])
            candidates.append((period, power))

    if not candidates:
        return None

    # Bias toward the fundamental by preferring longer periods when power is similar.
    candidates.sort(key=lambda item: (-item[1], -item[0]))
    return float(candidates[0][0])

def find_exact_rotation(roi, rough_angle):
    """Fine-tune the rotation by maximizing the FFT power peak."""
    best_angle = rough_angle
    max_peak = 0
    
    h, w = roi.shape
    center = (w/2, h/2)
    
    # Scan in 0.1 degree increments around the rough estimate
    for angle in np.linspace(rough_angle - 1.5, rough_angle + 1.5, 31):
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(roi, M, (w, h), flags=cv2.INTER_LINEAR)
        
        # Test X projection peak
        prof_x = rotated.mean(axis=0)
        P_x = np.max(np.abs(np.fft.rfft(prof_x - prof_x.mean()))[1:])
        
        # Test Y projection peak
        prof_y = rotated.mean(axis=1)
        P_y = np.max(np.abs(np.fft.rfft(prof_y - prof_y.mean()))[1:])
        
        peak = max(P_x, P_y)
        if peak > max_peak:
            max_peak = peak
            best_angle = angle
            
    return best_angle

def dominant_period(profile, max_fraction=0.4):
    """FFT-based candidate extraction for debug display.

    The returned period is only used for candidate previews. The main calibration
    value is computed with autocorrelation so that one clean value is reported.
    """
    n = len(profile)

    sigma = max(3.0, n / 30)
    blur = cv2.GaussianBlur(profile.reshape(1, -1), (0, 0), sigma).flatten()
    hp_profile = profile - blur

    p = hp_profile * np.hanning(n)

    P = np.abs(np.fft.rfft(p))
    f = np.fft.rfftfreq(n)

    from scipy.signal import find_peaks
    max_p = np.max(P)
    peaks, props = find_peaks(P, height=max_p * 0.1, distance=5)

    if len(peaks) == 0:
        return None, None, None, []

    candidates = []
    for p_idx in peaks:
        if 0 < p_idx < len(P) - 1:
            vals = [max(1e-12, float(P[i])) for i in (p_idx - 1, p_idx, p_idx + 1)]
            y1, y2, y3 = np.log(vals)
            denom = (y1 - 2 * y2 + y3)
            ref_idx = p_idx + 0.5 * (y1 - y3) / denom if abs(denom) > 1e-12 else float(p_idx)
            per = 1.0 / (float(ref_idx) / n)
            candidates.append({
                "period": float(per),
                "power": float(P[p_idx]),
                "frequency": float(ref_idx / n)
            })

    candidates = sorted(candidates, key=lambda x: x['power'], reverse=True)
    best = candidates[0]
    return best['period'], f, P, candidates[:5]

def analyze_image(img_path, target_type, spacing_um):
    img = cv2.imread(img_path)
    if img is None: return {"error": "Could not read image file."}
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = gray.shape
    
    # 1. Global Orientation
    rough_angle = estimate_global_rotation(gray)
    
    # 2. Refine Rotation
    # Use center area for rotation refinement to be robust to edges
    roi_small = gray[h//4:3*h//4, w//4:3*w//4]
    final_angle = find_exact_rotation(roi_small, rough_angle)
    
    # 3. Apply Rotation
    M = cv2.getRotationMatrix2D((w/2, h/2), final_angle, 1.0)
    img_rot = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC)
    gray_rot = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC)
    
    # 4. Extract ROI from rotated image
    roi = gray_rot[int(h*0.2):int(h*0.8), int(w*0.2):int(w*0.8)]
    prof_x = roi.mean(axis=0)
    prof_y = roi.mean(axis=1)
    
    res = {}
    res['tilt_angle'] = round(float(final_angle), 2)
    res['width'] = int(w)
    res['height'] = int(h)

    px_fft, f_x, P_x, cand_x = dominant_period(prof_x)
    py_fft, f_y, P_y, cand_y = dominant_period(prof_y)

    all_candidates = []
    for axis_name, cands in (('X', cand_x), ('Y', cand_y)):
        for c in cands:
            scale_val = float(spacing_um / c['period'])
            all_candidates.append({
                'axis': axis_name,
                'period': c['period'],
                'scale': scale_val,
                'power': c['power'],
                'frequency': c['frequency'],
            })

    # Prefer the calibration candidate that is both strong and physically plausible.
    plausible = [c for c in all_candidates if 0.4 <= c['scale'] <= 2.0]
    if plausible:
        expected_scale = 0.95
        best = max(
            plausible,
            key=lambda c: (
                c['power'] / (1.0 + abs(c['scale'] - expected_scale) / 0.25),
                c['power'],
            ),
        )
    elif all_candidates:
        best = max(all_candidates, key=lambda c: c['power'])
    else:
        # Final fallback: use the autocorrelation estimate from whichever axis has one.
        px = estimate_period_autocorr(prof_x)
        py = estimate_period_autocorr(prof_y)
        fallback_periods = [p for p in (px, py) if p and p > 0]
        if not fallback_periods:
            return {"error": "No ruler or grid divisions detected after alignment."}
        best_scale = float(np.median([spacing_um / p for p in fallback_periods]))
        best = {
            'axis': 'XY',
            'period': float(spacing_um / best_scale),
            'scale': best_scale,
            'power': 0.0,
            'frequency': 0.0,
        }

    scale = float(best['scale'])
    res.update({
        'SCALE_X': scale,
        'SCALE_Y': scale,
        'SCALE_UM_PER_PX': scale,
        'detected_axis': best['axis'],
    })

    # Spectrum preview from the axis that produced the chosen candidate.
    if best['axis'] == 'Y':
        f_spec, P_spec = f_y, P_y
    else:
        f_spec, P_spec = f_x, P_x
    res['candidates'] = []
    
    # 5. Save enhanced debug image (Dual Pane)
    debug_name = f"debug_{int(time.time())}.png"
    debug_path = os.path.join(app.config['UPLOAD_FOLDER'], debug_name)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 9), gridspec_kw={'height_ratios': [2, 1]})
    
    # Top: Rotated Image
    ax1.imshow(cv2.cvtColor(img_rot, cv2.COLOR_BGR2RGB))
    disp_scale = res['SCALE_UM_PER_PX']
    ax1.set_title(f"Aligned ({res['tilt_angle']}\u00b0) | Result: {disp_scale:.6f} \u00b5m/px", fontsize=14, color='#007aff')
    ax1.axis('off')
    
    # Bottom: Power Spectrum
    ax2.set_facecolor('#1a1a1a')
    ax2.plot(f_spec, P_spec, color='#007aff', linewidth=1.5, alpha=0.8, label='Spectrum')
    
    ax2.set_xlim(0, 0.2) # Zoom into resolution range
    ax2.set_title("Power Spectrum (Frequency Domain) - Click matching button below", fontsize=12, color='white')
    ax2.set_xlabel("Frequency (cycles/pixel)", color='white')
    ax2.set_ylabel("Power", color='white')
    ax2.tick_params(colors='white')
    ax2.grid(True, alpha=0.2, color='white')
    ax2.legend(loc='upper right')
    
    plt.tight_layout()
    plt.savefig(debug_path, bbox_inches='tight', dpi=120, facecolor='#121212')
    plt.close()
    
    # Remove results from server after a short delay (or immediately)
    # For now, we will return the result normally but stop saving to memory.
    res['debug_url'] = f"/static/uploads/{debug_name}"
    return res

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/history', methods=['GET'])
def history():
    memory_path = Path(app.config['MEMORY_FILE'])
    if not memory_path.exists():
        return jsonify([])

    try:
        raw_text = memory_path.read_text()
        memory = json.loads(raw_text.replace('NaN', '0.0'))
        cleaned = []
        for item in memory:
            if history_scale(item) is not None:
                cleaned.append(item)
        return jsonify(cleaned[::-1])
    except Exception:
        return jsonify([])

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    target_type = request.form.get('type', 'ruler')
    
    # Handle both comma and dot decimals
    spacing_raw = request.form.get('spacing', '10.0').replace(',', '.')
    try:
        spacing = float(spacing_raw)
    except ValueError:
        return jsonify({'error': 'Invalid spacing value'}), 400
    
    filename = secure_filename(file.filename)
    # Use absolute path from config
    save_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    file.save(save_path)
    
    results = analyze_image(save_path, target_type, spacing)
    if not results or 'error' in results:
        return jsonify(results if results else {'error': 'Analysis failed'}), 200
    
    # Final safety: Ensure no NaN values in JSON
    results = json.loads(json.dumps(results, default=lambda x: 0.0 if isinstance(x, float) and (np.isnan(x) or np.isinf(x)) else x))

    # Skip memory/history update
    return jsonify(results)

@app.route('/history/delete', methods=['POST'])
def delete_history():
    data = request.json
    ts = data.get('timestamp')
    if not ts: return jsonify({'error': 'No timestamp provided'}), 400
    
    memory_path = Path(app.config['MEMORY_FILE'])
    if not memory_path.exists(): return jsonify({'error': 'No history found'}), 404
    
    try:
        raw_text = memory_path.read_text()
        memory = json.loads(raw_text.replace('NaN', '0.0'))
        new_memory = [item for item in memory if item.get('timestamp') != ts and history_scale(item) is not None]
        memory_path.write_text(json.dumps(new_memory, indent=2))
        return jsonify({'success': True, 'history': new_memory[::-1]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def open_browser():
    webbrowser.open_new('http://127.0.0.1:5001/')

if __name__ == '__main__':
    Timer(1, open_browser).start()
    app.run(host='127.0.0.1', port=5001, debug=False)
