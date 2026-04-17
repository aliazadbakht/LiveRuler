# LiveRuler 📏 — *by Precisometer*

**LiveRuler** is a high-precision microscope calibration dashboard. It helps you calculate the exact **pixel-to-micron scale** of your microscope images using automated image processing (FFT and Autocorrelation).

![LiveRuler Logo](static/precisometer_logo.png)

## 🌟 Key Features
- **Automated Alignment**: Automatically detects the rotation/tilt of your ruler or grid.
- **Precision Calculation**: Uses frequency-domain analysis (FFT) to find the exact spacing of microscopic markings.
- **Visual Verification**: Provides a power spectrum visualization and an aligned debug view to guarantee accuracy.
- **Dual Mode**: Works for both 10µm line rulers and 100µm grids.
- **Web Version**: Host it on GitHub Pages for a zero-install, serverless experience.

## 🚀 Quick Start (Local Desktop)

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the dashboard**:
   ```bash
   python app.py
   ```
   The dashboard will automatically open in your web browser at `http://127.0.0.1:5001`.

## 🌐 Web Version (GitHub Pages)

You can view the web-ready version in the `/web_version` folder. This version uses **PyScript** to run the Python processing entirely in the visitor's browser.

**To host on GitHub:**
1. Push this repo to GitHub.
2. Go to **Settings > Pages**.
3. Point it to the `/web_version` directory.

## 🛠 Tech Stack
- **Backend**: Python, Flask (for desktop), OpenCV, NumPy, SciPy, Matplotlib.
- **Web Frontend**: HTML5, Vanilla CSS (Glassmorphism), JavaScript.
- **WebAssembly**: PyScript (for the serverless version).

---
*Developed by **Precisometer** for precision microscopy and material science calibration.*
