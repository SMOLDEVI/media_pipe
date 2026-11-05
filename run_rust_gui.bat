@echo off
chcp 65001 > nul
echo Запуск MediaPipe Pose Studio (Rust GUI)...
if exist "gui\target\release\lab5_mediapipe_gui.exe" (
    start "" "gui\target\release\lab5_mediapipe_gui.exe"
) else (
    echo Бинарный файл не найден, компилирую...
    cd gui
    cargo run --release
)
