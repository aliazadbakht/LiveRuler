import cv2
import numpy as np
import matplotlib.pyplot as plt
import io
import base64
from scipy.signal import find_peaks

def estimate_global_rotation(gray):
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
        if deg > 45 and deg < 135:
            angles.append(deg - 90)
        elif deg >= 135:
            angles.append(deg - 180)
        else:
            angles.append(deg)
            
    return float(np.median(angles))

def estimate_period_autocorr(profile, max_fraction=0.4):
    x = np.asarray(profile, dtype=np.float32)
    n = len(x)
    if n < 8: return None
    x = x - np.mean(x)
    if np.allclose(x, 0): return None

    sigma = max(3.0, n / 30)
    blur = cv2.GaussianBlur(x.reshape(1, -1), (0, 0), sigma).flatten()
    x = (x - blur) * np.hanning(n)

    ac = np.fft.irfft(np.abs(np.fft.rfft(x)) ** 2)
    ac = ac[: max(4, int(n * max_fraction))]
    if len(ac) < 4: return None
    if abs(ac[0]) < 1e-12: return None
    ac = ac / ac[0]
    ac[0] = 0.0

    min_lag = 3
    peaks, props = find_peaks(ac[min_lag:], prominence=max(0.02, float(np.max(ac[min_lag:])) * 0.08))
    if len(peaks) > 0:
        peaks = peaks + min_lag
        prominences = props.get('prominences', np.ones(len(peaks)))
        best_idx = int(peaks[np.argmax(prominences / np.maximum(peaks, 1))])
        return float(best_idx)
    return None

def find_exact_rotation(roi, rough_angle):
    best_angle = rough_angle
    max_peak = 0
    h, w = roi.shape
    center = (w/2, h/2)
    for angle in np.linspace(rough_angle - 1.5, rough_angle + 1.5, 31):
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(roi, M, (w, h), flags=cv2.INTER_LINEAR)
        prof_x = rotated.mean(axis=0)
        P_x = np.max(np.abs(np.fft.rfft(prof_x - prof_x.mean()))[1:])
        prof_y = rotated.mean(axis=1)
        P_y = np.max(np.abs(np.fft.rfft(prof_y - prof_y.mean()))[1:])
        peak = max(P_x, P_y)
        if peak > max_peak:
            max_peak = peak
            best_angle = angle
    return best_angle

def dominant_period(profile):
    n = len(profile)
    sigma = max(3.0, n / 30)
    blur = cv2.GaussianBlur(profile.reshape(1, -1), (0, 0), sigma).flatten()
    hp_profile = profile - blur
    p = hp_profile * np.hanning(n)
    P = np.abs(np.fft.rfft(p))
    f = np.fft.rfftfreq(n)
    max_p = np.max(P)
    peaks, _ = find_peaks(P, height=max_p * 0.1, distance=5)
    if len(peaks) == 0: return None, None, None, []
    candidates = []
    for p_idx in peaks:
        if 0 < p_idx < len(P) - 1:
            vals = [max(1e-12, float(P[i])) for i in (p_idx - 1, p_idx, p_idx + 1)]
            y1, y2, y3 = np.log(vals)
            denom = (y1 - 2 * y2 + y3)
            ref_idx = p_idx + 0.5 * (y1 - y3) / denom if abs(denom) > 1e-12 else float(p_idx)
            per = 1.0 / (float(ref_idx) / n)
            candidates.append({"period": float(per), "power": float(P[p_idx]), "frequency": float(ref_idx / n)})
    candidates = sorted(candidates, key=lambda x: x['power'], reverse=True)
    return candidates[0]['period'], f, P, candidates[:5]

def process_image_data(image_bytes, spacing_um):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None: return {"error": "Could not read image file."}
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = gray.shape
    rough_angle = estimate_global_rotation(gray)
    roi_small = gray[h//4:3*h//4, w//4:3*w//4]
    final_angle = find_exact_rotation(roi_small, rough_angle)
    M = cv2.getRotationMatrix2D((w/2, h/2), final_angle, 1.0)
    img_rot = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC)
    gray_rot = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC)
    roi = gray_rot[int(h*0.2):int(h*0.8), int(w*0.2):int(w*0.8)]
    prof_x = roi.mean(axis=0)
    prof_y = roi.mean(axis=1)
    
    px_fft, f_x, P_x, cand_x = dominant_period(prof_x)
    py_fft, f_y, P_y, cand_y = dominant_period(prof_y)

    all_candidates = []
    for axis_name, cands in (('X', cand_x), ('Y', cand_y)):
        for c in cands:
            all_candidates.append({'axis': axis_name, 'period': c['period'], 'scale': float(spacing_um / c['period']), 'power': c['power'], 'frequency': c['frequency']})

    plausible = [c for c in all_candidates if 0.4 <= c['scale'] <= 2.0]
    if plausible:
        best = max(plausible, key=lambda c: (c['power'] / (1.0 + abs(c['scale'] - 0.95) / 0.25), c['power']))
    elif all_candidates:
        best = max(all_candidates, key=lambda c: c['power'])
    else:
        return {"error": "No ruler or grid divisions detected."}

    scale = float(best['scale'])
    f_spec, P_spec = (f_y, P_y) if best['axis'] == 'Y' else (f_x, P_x)

    # Generate debug plot
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={'height_ratios': [2, 1]})
    ax1.imshow(cv2.cvtColor(img_rot, cv2.COLOR_BGR2RGB))
    ax1.set_title(f"Aligned ({final_angle:.2f}\u00b0) | {scale:.6f} \u00b5m/px", color='#007aff')
    ax1.axis('off')
    ax2.plot(f_spec, P_spec, color='#007aff')
    ax2.set_xlim(0, 0.2)
    ax2.set_title("Power Spectrum")
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    plt.close()
    img_str = base64.b64encode(buf.getvalue()).decode('utf-8')

    return {
        "scale": scale,
        "tilt_angle": final_angle,
        "width": w,
        "height": h,
        "debug_img": "data:image/png;base64," + img_str
    }
