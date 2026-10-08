#!/usr/bin/env python3
"""
RE:TRACE Offline Environment Bootstrapper.

Discovers cached binary wheels in ~/Library/Caches/pip/http/,
extracts and reconstructs standard PEP 427 wheel files into .wheelhouse/,
and installs necessary dependencies (pydantic, fastapi, uvicorn, pytest, numpy, etc.)
offline without internet access.
"""

import io
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path


def clean_dist_name(name: str) -> str:
    """Normalize package distribution name per PEP 427 / PEP 503."""
    return re.sub(r"[-_.]+", "_", name).strip("_")


def discover_and_extract_wheels(cache_dir: Path, wheelhouse_dir: Path) -> list:
    """
    Scans the pip HTTP cache directory, locates zip/wheel payloads,
    determines distribution name, version, and wheel tags, and copies
    them to .wheelhouse/.
    """
    wheelhouse_dir.mkdir(parents=True, exist_ok=True)
    extracted_wheels = []
    seen_names = set()

    if not cache_dir.exists():
        print(f"[ERROR] Pip cache directory not found at: {cache_dir}")
        return extracted_wheels

    print(f"Scanning pip cache at {cache_dir}...")
    for root, _, files in os.walk(cache_dir):
        for filename in files:
            file_path = Path(root) / filename
            try:
                with open(file_path, "rb") as f:
                    data = f.read()

                # Find zip magic bytes PK\x03\x04
                zip_offset = data.find(b"PK\x03\x04")
                if zip_offset == -1:
                    continue

                zip_payload = data[zip_offset:]
                zf = zipfile.ZipFile(io.BytesIO(zip_payload))
                namelist = zf.namelist()

                wheel_entries = [n for n in namelist if n.endswith(".dist-info/WHEEL")]
                meta_entries = [n for n in namelist if n.endswith(".dist-info/METADATA")]

                if not wheel_entries or not meta_entries:
                    continue

                wheel_text = zf.read(wheel_entries[0]).decode("utf-8", errors="ignore")
                meta_text = zf.read(meta_entries[0]).decode("utf-8", errors="ignore")

                dist_name = None
                version = None
                tags = []

                for line in meta_text.splitlines():
                    if line.startswith("Name:") and dist_name is None:
                        dist_name = line.split(":", 1)[1].strip()
                    elif line.startswith("Version:") and version is None:
                        version = line.split(":", 1)[1].strip()

                for line in wheel_text.splitlines():
                    if line.startswith("Tag:"):
                        tags.append(line.split(":", 1)[1].strip())

                if not dist_name or not version or not tags:
                    continue

                safe_name = clean_dist_name(dist_name)
                safe_version = version.replace("-", "_")

                # Reconstruct wheel file for each tag
                for tag in tags:
                    whl_filename = f"{safe_name}-{safe_version}-{tag}.whl"
                    out_path = wheelhouse_dir / whl_filename
                    if whl_filename not in seen_names:
                        with open(out_path, "wb") as out_f:
                            out_f.write(zip_payload)
                        seen_names.add(whl_filename)
                        extracted_wheels.append(out_path)

            except Exception:
                # Skip invalid or corrupted cache chunks
                continue

    print(f"Successfully extracted {len(extracted_wheels)} wheels into {wheelhouse_dir}.")
    return extracted_wheels


def ensure_venv(workspace_root: Path) -> Path:
    """Ensures .venv exists with system-site-packages enabled."""
    venv_dir = workspace_root / ".venv"
    if not (venv_dir / "bin" / "pip").exists():
        print(f"Creating virtual environment with system site packages at {venv_dir}...")
        subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(venv_dir)], check=True)
    return venv_dir


def setup_workspace_environment(workspace_root: Path, venv_dir: Path):
    """
    Creates sitecustomize.py in workspace root to automatically expose
    .venv/site-packages to system python when invoked in workspace.
    """
    sitecustomize_path = workspace_root / "sitecustomize.py"
    py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    content = f'''"""Automatic venv site-packages loader for RE:TRACE offline environment."""
import os
import sys

_ws = os.path.dirname(os.path.abspath(__file__))
_venv_site = os.path.join(_ws, ".venv", "lib", "{py_ver}", "site-packages")
if os.path.isdir(_venv_site) and _venv_site not in sys.path:
    sys.path.insert(0, _venv_site)
'''
    with open(sitecustomize_path, "w") as f:
        f.write(content)
    print(f"Created workspace sitecustomize at {sitecustomize_path}")


def install_dependencies(wheelhouse_dir: Path, venv_dir: Path):
    """
    Installs required dependencies from .wheelhouse into .venv using --no-index --find-links.
    """
    packages = [
        "typing-extensions",
        "annotated-types",
        "pydantic-core",
        "pydantic",
        "starlette",
        "fastapi",
        "uvicorn",
        "iniconfig",
        "pluggy",
        "pytest",
        "numpy",
        "python-multipart",
        "pyyaml",
    ]

    print("\nInstalling dependencies into virtualenv...")
    pip_path = str(venv_dir / "bin" / "pip")
    cmd = [
        pip_path,
        "install",
        "--no-index",
        f"--find-links={wheelhouse_dir}",
    ] + packages

    print(f"Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0:
        print(f"[WARNING] pip install had issues: {res.stderr}")
    else:
        print("[SUCCESS] All core dependencies installed into virtualenv.")


def verify_installation(workspace_root: Path, venv_dir: Path) -> bool:
    """Verify that required modules can be imported with venv python and system python (with PYTHONPATH)."""
    print("\nVerifying installation across interpreters...")

    # Test 1: venv python
    venv_python = str(venv_dir / "bin" / "python3")
    cmd_venv = [
        venv_python,
        "-c",
        "import pydantic, fastapi, pytest, numpy; print(f'VENV OK: pydantic {pydantic.__version__}, fastapi {fastapi.__version__}, pytest {pytest.__version__}, numpy {numpy.__version__}')",
    ]
    res_venv = subprocess.run(cmd_venv, capture_output=True, text=True, cwd=str(workspace_root))
    print(res_venv.stdout.strip())
    if res_venv.returncode != 0:
        print("VENV verification error:", res_venv.stderr.strip())
        return False

    # Test 2: system python with PYTHONPATH pointing to venv site-packages
    venv_site = str(venv_dir / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages")
    env = os.environ.copy()
    env["PYTHONPATH"] = venv_site
    cmd_sys = [
        sys.executable,
        "-c",
        "import pydantic, fastapi, pytest, numpy; print(f'SYSTEM PYTHON (with PYTHONPATH) OK: pydantic {pydantic.__version__}, fastapi {fastapi.__version__}, pytest {pytest.__version__}, numpy {numpy.__version__}')",
    ]
    res_sys = subprocess.run(cmd_sys, capture_output=True, text=True, cwd=str(workspace_root), env=env)
    print(res_sys.stdout.strip())
    if res_sys.returncode != 0:
        print("System python verification error:", res_sys.stderr.strip())
        return False

    return True


def main():
    workspace_root = Path(__file__).resolve().parent.parent
    cache_dir = Path.home() / "Library" / "Caches" / "pip" / "http"
    wheelhouse_dir = workspace_root / ".wheelhouse"

    print("=== RE:TRACE Offline Environment Bootstrapper ===")
    print(f"Workspace root : {workspace_root}")
    print(f"Pip cache dir  : {cache_dir}")
    print(f"Wheelhouse dir : {wheelhouse_dir}")

    extracted = discover_and_extract_wheels(cache_dir, wheelhouse_dir)
    if not extracted and not list(wheelhouse_dir.glob("*.whl")):
        print("[ERROR] No wheels extracted. Aborting.")
        sys.exit(1)

    venv_dir = ensure_venv(workspace_root)
    setup_workspace_environment(workspace_root, venv_dir)
    install_dependencies(wheelhouse_dir, venv_dir)

    success = verify_installation(workspace_root, venv_dir)
    if success:
        print("\n[SUCCESS] Offline environment setup complete and verified!")
    else:
        print("\n[ERROR] Verification failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
