"""
Визуализация 3D-скелета человека с помощью Matplotlib
на основе извлеченных координат (x, y, z) из файла skeleton_data.json.

Функционал:
 1. Интерактивный просмотр с ползунком выбора кадра (слайдер) и 3D-вращением мышь
 2. Режим анимации движения человека во времени
 3. Экспорт 3D-графика в изображение skeleton_3d_render.png для отчета
 4. Экспорт анимации в GIF (при наличии Pillow)
"""

import argparse
import json
import os
import sys
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider
import numpy as np


# Связи между суставами MediaPipe Pose (33 точки)
POSE_CONNECTIONS = frozenset([
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8), (9, 10),
    (11, 12), (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19),
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (24, 26), (25, 27), (26, 28), (27, 29), (28, 30),
    (29, 31), (30, 32), (27, 31), (28, 32)
])

# Имена основных суставов для отображения
KEY_LANDMARK_NAMES = {
    0: "Нос",
    11: "Л.плечо",
    12: "П.плечо",
    13: "Л.локоть",
    14: "П.локоть",
    15: "Л.кисть",
    16: "П.кисть",
    23: "Л.бедро",
    24: "П.бедро",
    25: "Л.колено",
    26: "П.колено",
    27: "Л.лодыжка",
    28: "П.лодыжка",
}


def try_repair_truncated_json(json_path: str):
    """
    Автоматическое восстановление оборванного JSON файла (например, если запись была
    прервана пользователем комбинацией Ctrl+C или закрытием терминала).
    """
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for idx in range(len(lines) - 1, 0, -1):
            if lines[idx].strip() in ("}", "},") and lines[idx - 1].strip() == "]":
                test_lines = lines[:idx]
                test_lines.append(" }\n]\n")
                recovered_str = "".join(test_lines)
                data = json.loads(recovered_str)
                with open(json_path, "w", encoding="utf-8") as out_f:
                    out_f.write(recovered_str)
                print(f"[УСПЕХ] Файл '{json_path}' успешно восстановлен! Загружено {len(data)} полных кадров.")
                return data
    except Exception as e:
        print(f"[ОШИБКА] Не удалось автоматически восстановить '{json_path}': {e}")
    return None


def load_skeleton_data(json_path: str):
    if not os.path.exists(json_path):
        if json_path == "skeleton_data.json" and os.path.exists("sample_skeleton_data.json"):
            print(f"[ИНФО] Файл '{json_path}' еще не создан. Загружаю демо-данные 'sample_skeleton_data.json'.")
            json_path = "sample_skeleton_data.json"
        else:
            raise FileNotFoundError(
                f"Файл '{json_path}' не найден. "
                "Сначала выполните захват видеопотока командой: python capture_skeleton.py"
            )

    data = None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as err:
        print(f"[ПРЕДУПРЕЖДЕНИЕ] Файл '{json_path}' был некорректно завершен ({err}).")
        print("[ИНФО] Выполняю автоматическое восстановление неповрежденных кадров...")
        data = try_repair_truncated_json(json_path)
        if data is None:
            if os.path.exists("sample_skeleton_data.json"):
                print("[ИНФО] Использую резервные демо-данные 'sample_skeleton_data.json'.")
                with open("sample_skeleton_data.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                raise

    if not data:
        if json_path != "sample_skeleton_data.json" and os.path.exists("sample_skeleton_data.json"):
            print(f"[ИНФО] Файл '{json_path}' пуст (не было человека в кадре). Использую 'sample_skeleton_data.json'.")
            with open("sample_skeleton_data.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            raise ValueError(f"Файл '{json_path}' пуст (не содержит записанных кадров).")
    return data


def extract_frame_coords(frame_data):
    """
    Преобразует список landmarks кадра в numpy-массив [33, 3] и массив visibility [33].
    Инвертирует ось Y (-y), чтобы координаты соответствовали человеческому восприятию
    (в изображении ось Y направлена вниз, в 3D графике - вверх).
    """
    landmarks = frame_data["landmarks"]
    coords = np.zeros((len(landmarks), 3), dtype=np.float32)
    visibilities = np.zeros(len(landmarks), dtype=np.float32)

    for p in landmarks:
        idx = p["id"]
        # x: влево-вправо, y: вверх-вниз (инвертируем для 3D), z: глубина
        coords[idx] = [p["x"], -p["y"], -p["z"]]
        visibilities[idx] = p.get("v", 1.0)

    return coords, visibilities


def setup_3d_axes(ax, all_coords):
    """Настройка масштабов и меток осей для согласованного отображения."""
    x_all = all_coords[:, :, 0]
    y_all = all_coords[:, :, 1]
    z_all = all_coords[:, :, 2]

    # Центрирование и пропорциональный масштаб
    x_mid = (x_all.max() + x_all.min()) / 2.0
    y_mid = (y_all.max() + y_all.min()) / 2.0
    z_mid = (z_all.max() + z_all.min()) / 2.0
    max_range = max(
        x_all.max() - x_all.min(),
        y_all.max() - y_all.min(),
        z_all.max() - z_all.min(),
        0.5
    ) / 2.0

    ax.set_xlim(x_mid - max_range, x_mid + max_range)
    ax.set_ylim(y_mid - max_range, y_mid + max_range)
    ax.set_zlim(z_mid - max_range, z_mid + max_range)

    ax.set_xlabel("X (Ширина)")
    ax.set_ylabel("Y (Высота)")
    ax.set_zlabel("Z (Глубина)")
    ax.view_init(elev=15, azim=-75)


def render_single_frame(coords, vis, ax, show_labels=False):
    """Отрисовка точек и связей скелета для одного кадра."""
    # Отрисовка костей (линий)
    for p1, p2 in POSE_CONNECTIONS:
        if p1 < len(coords) and p2 < len(coords):
            # Пропускаем кость, если уверенность одной из точек слишком мала
            if vis[p1] < 0.25 or vis[p2] < 0.25:
                continue

            # Цвет линий: разделяем туловище/голову и конечности
            if p1 in (11, 12, 23, 24) and p2 in (11, 12, 23, 24):
                color = "darkblue"
                lw = 2.5
            elif p1 % 2 == 1 and p2 % 2 == 1:  # левая сторона тела (нечетные)
                color = "crimson"
                lw = 2.0
            else:  # правая сторона тела
                color = "teal"
                lw = 2.0

            xs = [coords[p1, 0], coords[p2, 0]]
            ys = [coords[p1, 1], coords[p2, 1]]
            zs = [coords[p1, 2], coords[p2, 2]]
            ax.plot(xs, ys, zs, color=color, linewidth=lw)

    # Отрисовка точек суставов
    ax.scatter(
        coords[:, 0],
        coords[:, 1],
        coords[:, 2],
        c="lime",
        edgecolors="darkgreen",
        s=35,
        alpha=0.9,
    )

    # Подписи ключевых точек при необходимости
    if show_labels:
        for idx, name in KEY_LANDMARK_NAMES.items():
            if idx < len(coords) and vis[idx] >= 0.5:
                ax.text(
                    coords[idx, 0] + 0.015,
                    coords[idx, 1],
                    coords[idx, 2],
                    name,
                    fontsize=8,
                    color="black",
                )


def interactive_slider_mode(frames_data, all_coords, output_png):
    """Интерактивный режим с ползунком выбора кадра."""
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")
    plt.subplots_adjust(bottom=0.2)

    total_frames = len(frames_data)

    def update_plot(val):
        frame_idx = int(slider.val)
        ax.cla()
        setup_3d_axes(ax, all_coords)
        coords, vis = extract_frame_coords(frames_data[frame_idx])
        render_single_frame(coords, vis, ax, show_labels=True)
        orig_frame_id = frames_data[frame_idx].get("frame", frame_idx)
        ax.set_title(
            f"3D Скелет MediaPipe Pose | Кадр: {orig_frame_id} ({frame_idx + 1}/{total_frames})",
            fontsize=12,
            fontweight="bold",
        )
        fig.canvas.draw_idle()

    ax_slider = plt.axes([0.15, 0.06, 0.7, 0.04])
    slider = Slider(
        ax_slider,
        "Кадр",
        0,
        total_frames - 1,
        valinit=0,
        valstep=1,
        valfmt="%d",
    )
    slider.on_changed(update_plot)

    # Первая отрисовка
    update_plot(0)

    # Сохраняем первый/текущий кадр в PNG для отчета
    if output_png:
        plt.savefig(output_png, dpi=300, bbox_inches="tight")
        print(f"[УСПЕХ] 3D-график скелета сохранен в: '{output_png}'")

    print("[ИНФО] Открыто интерактивное 3D-окно. Используйте слайдер внизу или вращайте мышь.")
    plt.show()


def animation_mode(frames_data, all_coords, save_gif=None):
    """Режим анимации движения человека."""
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    total_frames = len(frames_data)

    def animate(i):
        ax.cla()
        setup_3d_axes(ax, all_coords)
        coords, vis = extract_frame_coords(frames_data[i])
        render_single_frame(coords, vis, ax, show_labels=False)
        orig_frame_id = frames_data[i].get("frame", i)
        ax.set_title(
            f"3D Анимация Скелета | Кадр: {orig_frame_id} ({i + 1}/{total_frames})",
            fontsize=12,
            fontweight="bold",
        )

    anim = FuncAnimation(
        fig,
        animate,
        frames=total_frames,
        interval=50,
        repeat=True,
    )

    if save_gif:
        print(f"[ИНФО] Сохранение 3D анимации в '{save_gif}'...")
        anim.save(save_gif, writer="pillow", fps=20)
        print(f"[УСПЕХ] Анимация сохранена в '{save_gif}'")

    print("[ИНФО] Запуск воспроизведения 3D-анимации...")
    plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Визуализация 3D-скелета MediaPipe Pose в Matplotlib"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="skeleton_data.json",
        help="Путь к файлу skeleton_data.json (по умолчанию 'skeleton_data.json')",
    )
    parser.add_argument(
        "--mode",
        choices=["interactive", "animate", "export_only"],
        default="interactive",
        help="Режим визуализации: interactive (слайдер), animate (анимация), export_only (сохранить PNG и выйти)",
    )
    parser.add_argument(
        "--output-png",
        type=str,
        default="skeleton_3d_render.png",
        help="Путь к файлу для сохранения статического 3D графика (по умолчанию 'skeleton_3d_render.png')",
    )
    parser.add_argument(
        "--output-gif",
        type=str,
        default=None,
        help="Путь к файлу для сохранения GIF анимации (например, 'skeleton_3d.gif')",
    )
    parser.add_argument(
        "--frame-idx",
        type=int,
        default=0,
        help="Индекс кадра для сохранения в режиме export_only (по умолчанию 0)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("   3D Визуализация скелета человека (Matplotlib + MediaPipe)")
    print("=" * 60)

    frames_data = load_skeleton_data(args.input)
    print(f"[ИНФО] Загружено {len(frames_data)} кадров из '{args.input}'")

    # Собираем координаты всех кадров для настройки пропорций осей
    coords_list = []
    for f in frames_data:
        c, _ = extract_frame_coords(f)
        coords_list.append(c)
    all_coords = np.stack(coords_list, axis=0)

    if args.mode == "export_only":
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection="3d")
        setup_3d_axes(ax, all_coords)
        idx = max(0, min(args.frame_idx, len(frames_data) - 1))
        coords, vis = extract_frame_coords(frames_data[idx])
        render_single_frame(coords, vis, ax, show_labels=True)
        ax.set_title(
            f"3D Скелет MediaPipe Pose | Кадр {idx}",
            fontsize=12,
            fontweight="bold",
        )
        plt.savefig(args.output_png, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"[УСПЕХ] 3D-график кадра {idx} сохранен в: '{args.output_png}'")
    elif args.mode == "animate":
        animation_mode(frames_data, all_coords, save_gif=args.output_gif)
    else:
        interactive_slider_mode(frames_data, all_coords, output_png=args.output_png)


if __name__ == "__main__":
    main()
