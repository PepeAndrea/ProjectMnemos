"""Build the pinned native speech runtime inside the repository, without global installs."""

import hashlib
import json
import platform
import shutil
import subprocess
import tarfile
import urllib.request

from .runtime import ROOT, RuntimeLayout


def main() -> None:
    if platform.system() != "Darwin":
        raise RuntimeError("this native build recipe targets the official macOS profile")
    if not shutil.which("cmake") or not shutil.which("c++"):
        raise RuntimeError("existing CMake and Apple C++ toolchain required")
    layout = RuntimeLayout()
    layout.configure()
    record = json.loads((ROOT / "docs/native-tools.json").read_text())["whisper"]
    url = "https://codeload.github.com/ggml-org/whisper.cpp/tar.gz/" + record["revision"]
    if record["url"] != url:
        raise ValueError("unregistered source origin")
    archive = layout.path("tmp/whisper-source.tar.gz")
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != record["sha256"]:
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read(32 * 1024 * 1024 + 1)
        if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise ValueError("native source archive checksum/size mismatch")
        archive.write_bytes(data)
    tools = layout.path("tools")
    tools.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tar:
        tar.extractall(tools, filter="data")
    source = tools / ("whisper.cpp-" + record["revision"])
    build = layout.path("tools/whisper-build")
    subprocess.run(
        ["cmake", "-S", str(source), "-B", str(build)] + record["cmake_flags"],
        check=True,
        timeout=120,
    )
    subprocess.run(
        [
            "cmake",
            "--build",
            str(build),
            "--config",
            "Release",
            "--target",
            "whisper",
            "whisper-cli",
            "-j",
            "4",
        ],
        check=True,
        timeout=300,
    )
    bridge = ROOT / "apps/core/native/whisper_bridge.cpp"
    subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-O2",
            "-dynamiclib",
            str(bridge),
            "-I",
            str(source / "include"),
            "-I",
            str(source / "ggml/include"),
            "-L",
            str(build / "bin"),
            "-lwhisper",
            "-Wl,-rpath,@loader_path",
            "-o",
            str(build / "bin/libmnemos-whisper.dylib"),
        ],
        check=True,
        timeout=60,
    )
    artifacts = [
        {
            "runtime_path": str(path.relative_to(layout.runtime)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in (build / "bin").glob("*.dylib")
        if not path.is_symlink()
    ]
    (build / "manifest.json").write_text(
        json.dumps(
            {
                "revision": record["revision"],
                "version": record["version"],
                "bridge_source_sha256": hashlib.sha256(bridge.read_bytes()).hexdigest(),
                "artifacts": artifacts,
            },
            indent=2,
        )
        + "\n"
    )
    print("native speech runtime built and checksummed under runtime/tools/whisper-build")


if __name__ == "__main__":
    main()
