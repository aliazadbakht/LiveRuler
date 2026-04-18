<p align="center">
  <img src="static/precisometer_logo.png" width="400" alt="LiveRuler Logo">
</p>

# 📏 LiveRuler — *High-Precision Calibration Dashboard*

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Framework-Flask-lightgrey.svg)](https://flask.palletsprojects.com/)
[![WebAssembly](https://img.shields.io/badge/Runtime-PyScript-orange.svg)](https://pyscript.net/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

### 🔗 [Try the Live Web Version](https://aliazadbakht.github.io/LiveRuler/)

**LiveRuler** is a professional-grade microscope calibration suite designed by **Precisometer**. It automates the tedious process of calculating the **pixel-to-micron scale** (µm/px) for optical microscopy and material science imaging.

By combining traditional computer vision with frequency-domain analysis, LiveRuler provides robust, sub-pixel accuracy that resists lighting noise and sample tilt.

---

## ✨ Key Features

- **🎯 Automated Alignment**: Uses Hough Transform and FFT power maximization to automatically detect and correct sample rotation.
- **🔬 Precise Calibration Engine**: Employs **Autocorrelation (ACF)** for stable period detection, significantly reducing errors from harmonics.
- **📊 Power Spectrum Visualization**: Real-time FFT preview allows users to visually verify the detected frequency peaks.
- **🧪 Dual Mode Support**: Pre-configured profiles for **10µm Stage Micrometers** and **100µm Grids**.
- **🌐 Live Web Version**: Available at [aliazadbakht.github.io/LiveRuler](https://aliazadbakht.github.io/LiveRuler/)—runs entirely in the browser via **WebAssembly (PyScript)**.
- **📅 History Tracking**: Built-in persistence to track calibration records across sessions.

---

## 🧠 The Science of Precision

LiveRuler doesn't just "count pixels." It uses a multi-stage signal processing pipeline to ensure consistency:

1.  **Orientation Estimation**: A global scan using `Canny` edges and `HoughLines` provides a rough tilt angle.
2.  **Rotation Refinement**: The image is iteratively rotated in 0.1° increments to maximize the density of the FFT power spectrum peaks.
3.  **Artifact Removal**: High-pass filtering suppresses uneven illumination and surface reflections.
4.  **Autocorrelation Analysis**: Unlike raw FFT which can be sensitive to noise, autocorrelation identifies the fundamental physical spacing of your ruler markings, making it immune to DC bias and local defects.

---

## 🚀 Getting Started (Local Desktop)
For laboratory environments requiring local image storage.

1.  **Clone & Prepare**:
    ```bash
    git clone https://github.com/Precisometer/LiveRuler.git
    cd LiveRuler
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Launch**:
    ```bash
    python app.py
    ```
    *The dashboard will automatically open at `http://127.0.0.1:5001`.*

---

## 🛠 Tech Stack

- **Backend Logic**: OpenCV, NumPy, SciPy, Matplotlib
- **Web Interface**: Vanilla JS, Glassmorphism CSS, HTML5
- **Server**: Flask (Desktop) / PyScript (Web)

---

## 🏢 About Precisometer
Precisometer specializes in high-accuracy measurement solutions for microscopy and micro-fabrication. We bridge the gap between academic research and industrial reliability.

---
<p align="center">
  Released under the MIT License • Built with ❤️ by <b>Precisometer</b>
</p>

