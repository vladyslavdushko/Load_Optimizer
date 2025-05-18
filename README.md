# 📦 3D Bin Packing Optimizer

Welcome to the **3D Bin Packing Optimizer** — your desktop toolkit for smartly packing boxes inside containers! 🚀

---

## 🎯 Project Overview

A Python-powered GUI application that helps you optimize the placement of 3D boxes in a container, visualize the result in 3D, and save your packing sessions to an embedded SQLite database.

* 🤖 **Algorithm**
  Greedy heuristic + discrete 3D grid + support & contact metrics
* 🖼️ **Visualization**
  Interactive 3D view with color-coded boxes & checkboxes
* 💾 **Persistence**
  Save/load sessions (JSON + pickle) in SQLite
* 🛠️ **Tech Stack**

  * Python 3.x
  * Tkinter for GUI
  * NumPy for math
  * Matplotlib (mplot3d) for 3D plots
  * SQLite for session storage

---

## 📂 Project Structure

```
bin_packing_app/
├── main.py              # 🏁 Entry point
├── gui.py               # 🖥️ GUI & visualization
├── optimizer.py         # 🤖 Packing logic
├── db.py                # 💾 SQLite session manager
├── requirements.txt     # 📦 Python deps
└── sessions/            # 🗄️ Folder for .db file & saved figures
```

---

## 🚀 Quick Start

### 1. Clone & Enter

```bash
git clone https://github.com/yourusername/3d-bin-packing.git
cd 3d-bin-packing/bin_packing_app
```

### 2. Setup Virtual Env & Install

```bash
python -m venv venv
# Windows
venv\Scripts\activate.bat
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Run the App

```bash
python main.py
```

🎉 Enjoy packing!

---

## 🛠️ Building a Windows Executable

Install **PyInstaller**:

```bash
pip install pyinstaller
```

Package into a single `.exe`:

```bash
python -m PyInstaller \
  --name "BinPackingApp" \
  --windowed \
  --add-data "sessions;sessions" \
  main.py
```

▶️ Find your executable in `dist/BinPackingApp/BinPackingApp.exe`.

---

## 🤓 Usage Tips

* **New Session**: Click “Почати пакування” to start fresh.
* **Add Boxes**: Enter dimensions, weight & quantity, then “Додати коробку”.
* **Load JSON**: Bulk-import container & box specs from a JSON file.
* **3D View**: Toggle box visibility by name for clear analysis.
* **History**: Reopen or delete past sessions from the main screen.

---

## 📖 JSON Input Format

```jsonc
[
  {
    "width": 1000,        // container width
    "height": 800,        // container height
    "depth": 600,         // container depth
    "max_weight": 500.0   // container max weight
  },
  {
    "name": "BoxA",
    "width": 200,
    "height": 150,
    "depth": 100,
    "weight": 10.0,
    "quantity": 5
  }
]
```

---

## 🛡️ Troubleshooting

* ❌ **“Error: sessions folder not found”**
  Ensure `sessions/` exists alongside `main.py`.

* ❌ **Tkinter import fails**
  On macOS, install Tcl/Tk via Homebrew and set:

  ```bash
  export TCL_LIBRARY="/opt/homebrew/opt/tcl-tk/lib/tcl8.6"
  export TK_LIBRARY="/opt/homebrew/opt/tcl-tk/lib/tk8.6"
  ```

* ❌ **PyInstaller command not found**
  Activate your venv and `pip install pyinstaller`.

---

## 🤝 Contributing

1. 🍴 Fork
2. ✨ Create a feature branch
3. 📥 Commit & push
4. 🔀 Open a PR

---

## 📜 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

Made with ❤️ by Vladyslav Dushko&#x20;
