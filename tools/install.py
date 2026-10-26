"""Install Capri's Windows dependencies and Russian Vosk model."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parent.parent
MODEL = "vosk-model-small-ru-0.22"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL}.zip"


def model_complete(folder):
    return all((folder / name).is_file() for name in
               ("am/final.mdl", "conf/mfcc.conf", "conf/model.conf",
                "graph/HCLr.fst", "graph/Gr.fst"))


def extract_model(archive, destination):
    """Validate the archive before extracting into a temporary directory."""
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            path = Path(member.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != MODEL:
                raise ValueError("Unexpected path in Vosk archive")
            if not (destination / path).resolve().is_relative_to(destination):
                raise ValueError("Unsafe path in Vosk archive")
        if source.testzip() is not None:
            raise ValueError("Corrupt Vosk archive")
        source.extractall(destination)
    if not model_complete(destination / MODEL):
        raise ValueError("Vosk archive is missing required model files")


def install_model(root=ROOT):
    root = Path(root)
    models = root / "models"
    target = models / MODEL
    if model_complete(target):
        print("[Capri] Vosk model is already installed.")
        return
    if target.exists():
        raise RuntimeError(f"Incomplete model: {target}. Move that folder aside and retry.")
    models.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="capri-install-", dir=models) as temporary:
        staging = Path(temporary)
        bundled = root / "bundled" / f"{MODEL}.zip"
        if bundled.is_file():
            archive = bundled
        else:
            archive = staging / "model.zip"
            print(f"[Capri] Downloading Russian speech model from {MODEL_URL}")
            with urllib.request.urlopen(MODEL_URL, timeout=120) as response:
                with archive.open("wb") as output:
                    shutil.copyfileobj(response, output)
        extract_model(archive, staging)
        shutil.move(str(staging / MODEL), str(target))


def main():
    if sys.platform != "win32":
        print("[Capri] Full installation requires Windows 10/11.", file=sys.stderr)
        return 1
    if not (3, 11) <= sys.version_info[:2] < (3, 15):
        print("[Capri] Please use Python 3.11-3.14.", file=sys.stderr)
        return 1
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r",
                        str(ROOT / "requirements.txt")], cwd=ROOT, check=True)
        install_model()
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        print(f"[Capri] Installation failed: {exc}", file=sys.stderr)
        return 1
    print("[Capri] Ready! Start run.bat. Your config.json has not been changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
