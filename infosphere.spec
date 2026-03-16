# infosphere.spec
# ================
# PyInstaller build specification.
#
# Build commands:
#   Mac:     pyinstaller infosphere.spec
#   Windows: pyinstaller infosphere.spec
#
# Output:
#   dist/Infosphere.app   (Mac)
#   dist/Infosphere.exe   (Windows, one-file mode)

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ── Collect all data files ────────────────────────────────────────────────────

datas = [
    # Game UI
    (os.path.join("infosphere", "static", "game.html"),
     os.path.join("infosphere", "static")),
    # networkx ships JSON data files we must include
    *collect_data_files("networkx"),
    # Flask templates and static (jinja2 etc.)
    *collect_data_files("flask"),
    *collect_data_files("jinja2"),
]

# ── Hidden imports ────────────────────────────────────────────────────────────
# PyInstaller can miss dynamically-imported modules. List them explicitly.

hidden_imports = [
    # infosphere package
    "infosphere",
    "infosphere.env.world",
    "infosphere.env.actions",
    "infosphere.env.observation",
    "infosphere.engine.engine",
    "infosphere.agents.agents",
    "infosphere.scenarios.scenarios",
    # Flask internals
    "flask",
    "flask.templating",
    "werkzeug",
    "werkzeug.serving",
    "werkzeug.routing",
    "werkzeug.exceptions",
    "jinja2",
    "jinja2.ext",
    "click",
    "itsdangerous",
    # networkx
    "networkx",
    "networkx.algorithms",
    "networkx.classes",
    "networkx.drawing",
    # stdlib modules sometimes missed
    "email.mime.text",
    "email.mime.multipart",
    "logging.handlers",
    "threading",
    "socket",
    "webbrowser",
]

# Also collect all networkx and flask submodules dynamically
hidden_imports += collect_submodules("networkx")
hidden_imports += collect_submodules("flask")

# ── Analysis ──────────────────────────────────────────────────────────────────

a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy unused packages to keep bundle size down
        "matplotlib", "scipy", "pandas", "PIL", "cv2",
        "IPython", "notebook", "pytest", "numpy",
        "tkinter",   # optional — include if you want the splash window
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── Platform-specific build config ───────────────────────────────────────────

if sys.platform == "darwin":
    # Mac: build a .app bundle
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="Infosphere",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,          # no terminal window on Mac
        disable_windowed_traceback=False,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas,
        strip=False, upx=True,
        upx_exclude=[],
        name="Infosphere",
    )
    app = BUNDLE(
        coll,
        name="Infosphere.app",
        icon=None,              # add icon.icns here if you have one
        bundle_identifier="com.coldalchemy.infosphere",
        info_plist={
            "NSPrincipalClass": "NSApplication",
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "0.1.0",
            "LSUIElement": False,
        },
    )

else:
    # Windows: single .exe file (easier to distribute)
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="Infosphere",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,          # no console window on Windows
        disable_windowed_traceback=False,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,              # add icon.ico here if you have one
        version=None,
    )
