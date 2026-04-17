# LiveRuler Web Version

This is a **serverless** version of the **LiveRuler** calibration tool. It runs entirely in your web browser using **PyScript** and **WebAssembly**.

## Features
- **Zero Server Cost**: Can be hosted for free on GitHub Pages.
- **Privacy**: Images are processed locally on your computer. They are never uploaded to any server.
- **Full Power**: Uses the same Python logic (OpenCV, NumPy, SciPy) as the desktop version.

## How to host on GitHub Pages

1. **Push your code to GitHub**:
   If you haven't already, push this entire project to a GitHub repository.

2. **Enable GitHub Pages**:
   - Go to your repository on GitHub.
   - Click on **Settings** (top tab).
   - Click on **Pages** (left sidebar).
   - Under **Build and deployment** > **Branch**:
     - Select your main branch (e.g., `main`).
     - Change the folder from `/ (root)` to `/web_version` (if GitHub allows it) or just keep `/ (root)` if you move these files to the root.
   - Click **Save**.

3. **Visit your site**:
   GitHub will provide a URL (usually `https://username.github.io/repo-name/`).

   > [!NOTE]
   > For the web version to work, the files `index.html`, `calibration_core.py`, and the `static/` folder must be in the same directory on GitHub Pages.

## Why use this?
People who visit your GitHub can use the tool immediately without installing Python, Docker, or any dependencies. They just open their browser, upload an image, and get the results.
