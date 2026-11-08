"""Build TactLab-win-x64.zip from the Windows release virtual environment."""
import argparse
import hashlib
import importlib.metadata
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import urllib.request
import zipfile

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_NAME = "TactLab-win-x64.zip"
ARTIFACTS = {
    "python-3.12.10-embed-amd64.zip": (
        "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip",
        "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"),
    "webview2-1.0.3537.50.zip": (
        "https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/1.0.3537.50/microsoft.web.webview2.1.0.3537.50.nupkg",
        "5ea526bbd728adda0da4d31219267e96460494a427e4894c4e09d9f320f4b9aa"),
}

def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def download(cache, name):
    path = cache / name
    url, expected = ARTIFACTS[name]
    if not path.exists() or digest(path) != expected:
        with urllib.request.urlopen(url, timeout=180) as response, path.open("wb") as stream:
            shutil.copyfileobj(response, stream)
    if digest(path) != expected:
        raise RuntimeError("Unexpected SDK archive hash: " + name)
    return zipfile.ZipFile(path)

def icon(path):
    img = Image.new("RGBA", (256, 256))
    brush = ImageDraw.Draw(img)
    brush.rounded_rectangle((6, 6, 250, 250), radius=55, fill="#304955")
    brush.ellipse((48, 55, 208, 203), fill="#142f3c")
    brush.ellipse((52, 51, 204, 187), fill="#b85630")
    brush.ellipse((52, 42, 204, 176), fill="#ed8352")
    img.save(path, sizes=[(n,n) for n in (16,24,32,48,64,128,256)])

def copy_packages(destination):
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("Build from the isolated release venv.")
    lock = (ROOT / "windows/requirements-win64.lock").read_text().splitlines()
    for entry in lock:
        name, version = entry.split("==")
        if importlib.metadata.version(name) != version:
            raise RuntimeError("Install windows/requirements-win64.lock before building: " + name)
    site_dir = Path(sysconfig.get_path("purelib"))
    def ignore(folder, names):
        skipped = set(shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")(folder, names))
        if Path(folder) == site_dir:
            skipped.update(n for n in names if n == "pip" or n.startswith("pip-"))
        if Path(folder) == site_dir / "casadi":
            # TactLab needs the core Python binding; external solver plugins and SDK headers
            # do not participate in building, meshing, or exporting its solids.
            core = {"_casadi.pyd", "libcasadi.dll", "libwinpthread-1.dll",
                    "libgcc_s_seh-1.dll", "libstdc++-6.dll"}
            skipped.update(n for n in names if n.endswith((".dll", ".a", ".lib", ".exe")) and n not in core)
            skipped.update(("include", "cmake", "pkgconfig"))
        return skipped
    shutil.copytree(site_dir, destination, ignore=ignore)

def package(args):
    if sys.platform != "win32" or sys.maxsize <= 2**32 or sys.version_info[:2] != (3,12):
        raise RuntimeError("Use Windows x64 and Python 3.12 x64.")
    args.cache.mkdir(exist_ok=True, parents=True)
    args.output.mkdir(exist_ok=True, parents=True)
    with tempfile.TemporaryDirectory(dir=args.output) as scratch:
        temp = Path(scratch)
        app_root = temp / "TactLab"
        runtime = app_root / "runtime"
        desktop = runtime / "desktop"
        app = app_root / "app"
        app.mkdir(parents=True)
        desktop.mkdir(parents=True)
        for name in ("app.py","model.py","outputs.py"):
            shutil.copy2(ROOT / name, app)
        shutil.copy2(ROOT / "windows/desktop_server.py", app)
        shutil.copytree(ROOT / "public", app / "public")
        shutil.copy2(ROOT / "LICENSE", app_root / "LICENSE.txt")
        shutil.copy2(ROOT / "windows/Portable.txt", app_root / "Прочитать.txt")
        with download(args.cache, "python-3.12.10-embed-amd64.zip") as z:
            z.extractall(runtime)
        (runtime / "python312._pth").write_text("python312.zip\n.\nLib/site-packages\n../app\nimport site\n", encoding="ascii")
        copy_packages(runtime / "Lib/site-packages")
        with download(args.cache, "webview2-1.0.3537.50.zip") as z:
            for member in ["lib/net462/Microsoft.Web.WebView2.Core.dll","lib/net462/Microsoft.Web.WebView2.WinForms.dll",
                           "runtimes/win-x64/native/WebView2Loader.dll","LICENSE.txt","NOTICE.txt"]:
                (desktop / Path(member).name).write_bytes(z.read(member))
        compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        icon(temp / "TactLab.ico")
        subprocess.run([str(compiler), "/nologo", "/target:winexe", "/platform:x64", "/optimize+",
                        "/utf8output", "/codepage:65001", "/win32icon:" + str(temp / "TactLab.ico"),
                        "/reference:System.Windows.Forms.dll", "/reference:System.Drawing.dll",
                        "/reference:" + str(desktop / "Microsoft.Web.WebView2.Core.dll"),
                        "/reference:" + str(desktop / "Microsoft.Web.WebView2.WinForms.dll"),
                        "/out:" + str(app_root / "TactLab.exe"), str(ROOT / "windows/Desktop.cs")], check=True)
        shutil.copy2(ROOT / "windows/TactLab.exe.config", app_root)
        out = args.output / PACKAGE_NAME
        staged = temp / PACKAGE_NAME
        with zipfile.ZipFile(staged, "w", zipfile.ZIP_DEFLATED, compresslevel=5) as z:
            for path in sorted(app_root.rglob("*")):
                if path.is_file():
                    z.write(path,path.relative_to(temp))
        staged.replace(out)
        checksum = digest(out)
        (args.output / "SHA256SUMS.txt").write_text(checksum + "  " + out.name + "\n", encoding="ascii")
        print(out, out.stat().st_size, checksum)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    package(parser.parse_args())
