"""
Лабораторная работа №5: Захват видеопотока и выделение скелетной модели человека
Библиотеки: OpenCV, MediaPipe Pose, NumPy, Matplotlib

Шаги работы:
 1. Захват видеопотока с веб-камеры / видеофайла
 2. Инициализация MediaPipe Pose
 3. Обработка кадра (BGR -> RGB) и визуализация скелета
 4. Извлечение 33 координат (x, y, z, visibility) и вывод ключевых точек
 5. Экспорт извлеченных данных в skeleton_data.json
 6. Запись видео с наложенным скелетом в output_skeleton.mp4
"""

import argparse
import json
import os
import sys
import time
import cv2
import mediapipe as mp
import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(
        description="Захват видеопотока и выделение скелетной модели человека (MediaPipe Pose)"
    )
    parser.add_argument(
        "--source",
        type=str,
        default="0",
        help="Источник видео: индекс камеры (0, 1, ...) или путь к видеофайлу (по умолчанию '0')",
    )
    parser.add_argument(
        "--output-video",
        type=str,
        default="output_skeleton.mp4",
        help="Путь для сохранения видео с наложенным скелетом (по умолчанию 'output_skeleton.mp4')",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default="skeleton_data.json",
        help="Путь для сохранения координат скелета (по умолчанию 'skeleton_data.json')",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="skeleton_data.csv",
        help="Путь для сохранения координат в CSV (по умолчанию 'skeleton_data.csv', '' для отключения)",
    )
    parser.add_argument(
        "--stream-port",
        type=int,
        default=9099,
        help="UDP порт для прямой трансляции координат в 3D GUI в реальном времени (по умолчанию 9099, 0 = отключено)",
    )
    parser.add_argument(
        "--complexity",
        type=int,
        choices=[0, 1, 2],
        default=1,
        help="Сложность модели BlazePose: 0 (быстро), 1 (баланс), 2 (точно). По умолчанию 1.",
    )
    parser.add_argument(
        "--no-record",
        action="store_true",
        help="Отключить автоматическую запись видео в файл",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Максимальное число кадров для обработки (0 = бесконечно до нажатия 'q')",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Не открывать графическое окно (для фонового/пакетного режима)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Желаемая ширина кадра камеры (по умолчанию 1280)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=720,
        help="Желаемая высота кадра камеры (по умолчанию 720)",
    )
    return parser.parse_args()


def init_camera(source_str: str, req_width: int, req_height: int):
    # Если передано целое число, открываем как индекс камеры
    try:
        source_id = int(source_str)
    except ValueError:
        source_id = source_str

    cap = cv2.VideoCapture(source_id)

    # Если камера 0 не открылась, проверяем индексы 1 и 2
    if not cap.isOpened() and isinstance(source_id, int):
        print(f"[ПРЕДУПРЕЖДЕНИЕ] Камера {source_id} не открылась, пробуем другие индексы...")
        for fallback_id in [1, 2, 0]:
            if fallback_id == source_id:
                continue
            cap = cv2.VideoCapture(fallback_id)
            if cap.isOpened():
                print(f"[ИНФО] Успешно подключена камера с индексом {fallback_id}")
                source_id = fallback_id
                break

    if not cap.isOpened():
        raise RuntimeError(
            f"Не удалось открыть источник видео: {source_str}. "
            "Проверьте подключение веб-камеры или корректность пути к видеофайлу."
        )

    # Для веб-камеры задаем разрешение кадра
    if isinstance(source_id, int):
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, req_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, req_height)

    return cap


def draw_info_overlay(frame, fps, frame_idx, lm_detected, nose_info, is_recording):
    """
    Отображение информационного оверлея (HUD):
    FPS, статус трекинга, координаты носа, статус видеозаписи и подсказки по клавишам.
    """
    h, w = frame.shape[:2]

    # Полупрозрачная плашка в левом верхнем углу
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (450, 150), (20, 20, 20), -1)
    alpha = 0.65
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    # Заголовок и FPS
    cv2.putText(
        frame,
        f"MediaPipe Pose | FPS: {fps:4.1f} | Frame: {frame_idx}",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    # Статус детекции
    status_text = "Tracking: Human Detected" if lm_detected else "Tracking: Searching..."
    status_color = (0, 255, 0) if lm_detected else (0, 0, 255)
    cv2.putText(
        frame,
        status_text,
        (20, 65),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        status_color,
        2,
        cv2.LINE_AA,
    )

    # Координаты носа (Landmark 0)
    if nose_info:
        nose_str = (
            f"Nose: x={nose_info['x']:.2f} y={nose_info['y']:.2f} "
            f"z={nose_info['z']:.2f} vis={nose_info['v']:.2f}"
        )
    else:
        nose_str = "Nose: N/A"
    cv2.putText(
        frame,
        nose_str,
        (20, 95),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (220, 220, 220),
        1,
        cv2.LINE_AA,
    )

    # Статус записи и управление
    rec_text = "[REC ON]" if is_recording else "[REC OFF]"
    rec_color = (0, 0, 255) if is_recording else (150, 150, 150)
    cv2.putText(
        frame,
        f"{rec_text} Keys: [Q] Exit & Save | [R] Toggle Rec | [S] Screenshot",
        (20, 130),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        rec_color,
        1,
        cv2.LINE_AA,
    )

    # Индикатор записи (мигающая красная точка)
    if is_recording and int(time.time() * 2) % 2 == 0:
        cv2.circle(frame, (w - 30, 30), 10, (0, 0, 255), -1)
        cv2.putText(
            frame,
            "REC",
            (w - 75, 36),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )


def main():
    args = parse_args()
    print("=" * 60)
    print("   Лабораторная работа №5: MediaPipe Pose Skeleton Detection")
    print("=" * 60)

    # Шаг 1. Захват видеопотока
    cap = init_camera(args.source, args.width, args.height)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps_prop = cap.get(cv2.CAP_PROP_FPS)
    fps_val = fps_prop if fps_prop > 0 and fps_prop <= 60 else 30.0

    print(f"[ИНФО] Разрешение видео: {actual_w}x{actual_h}, FPS: {fps_val:.1f}")

    # Шаг 2. Инициализация MediaPipe Pose
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils

    # UDP сокет для прямой трансляции координат в GUI (3D Stream)
    udp_sock = None
    if args.stream_port > 0:
        import socket
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print(f"[ИНФО] Прямая 3D-трансляция активирована на 127.0.0.1:{args.stream_port}")

    # Стилизация точек и связей согласно методичке
    # Зеленые точки суставов (толщина 2, радиус 3)
    # Синие линии скелета (толщина 2)
    landmark_drawing_spec = mp_drawing.DrawingSpec(
        color=(0, 255, 0), thickness=2, circle_radius=3
    )
    connection_drawing_spec = mp_drawing.DrawingSpec(
        color=(255, 0, 0), thickness=2
    )

    pose = mp_pose.Pose(
        static_image_mode=False,        # видеопоток с трекингом между кадрами
        model_complexity=args.complexity, # 0 – быстро, 1 – баланс, 2 – точно
        smooth_landmarks=True,          # сглаживание дрожания точек
        min_detection_confidence=0.5,   # порог уверенности детекции
        min_tracking_confidence=0.5,    # порог уверенности трекинга
    )

    # Инициализация VideoWriter для сохранения результата
    video_writer = None
    is_recording = not args.no_record
    if is_recording:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(
            args.output_video, fourcc, fps_val, (actual_w, actual_h)
        )
        print(f"[ИНФО] Запись видео будет сохранена в: {args.output_video}")

    frames_data = []
    frame_idx = 0
    prev_time = time.time()
    fps_smooth = fps_val

    print("\n[УПРАВЛЕНИЕ]")
    print("  'q' - Выход из программы и сохранение данных")
    print("  'r' - Включить / выключить запись видео")
    print("  's' - Сохранить скриншот текущего кадра со скелетом")
    print("  'h' - Скрыть / показать HUD оверлей\n")

    show_hud = True
    window_name = "MediaPipe Pose - Skeleton Tracking"
    if not args.no_display:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, min(1280, actual_w), min(720, actual_h))

    try:
        while True:
            if args.max_frames > 0 and frame_idx >= args.max_frames:
                print(f"\n[ИНФО] Достигнут лимит кадров ({args.max_frames}). Завершение работы...")
                break

            ret, frame = cap.read()
            if not ret:
                print("\n[ИНФО] Видеопоток завершен или кадр не получен.")
                break

            cur_time = time.time()
            dt = cur_time - prev_time
            prev_time = cur_time
            if dt > 0:
                fps_smooth = 0.9 * fps_smooth + 0.1 * (1.0 / dt)

            # Шаг 3. Обработка кадра и визуализация скелета
            # 1. BGR -> RGB (обязательно!)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False  # оптимизация: ускорение обработки

            results = pose.process(rgb)

            rgb.flags.writeable = True

            nose_info = None

            # Шаг 4. Извлечение координат точек
            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark

                # Извлечение координат носа (Landmark 0)
                nose = landmarks[mp_pose.PoseLandmark.NOSE]
                nose_info = {
                    "x": nose.x,
                    "y": nose.y,
                    "z": nose.z,
                    "v": nose.visibility,
                }

                # Периодический вывод ключевой информации в консоль (раз в ~30 кадров)
                if frame_idx % 30 == 0:
                    # Примеры ключевых точек
                    left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
                    right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
                    print(
                        f"[Кадр {frame_idx:04d}] "
                        f"Nose: x={nose.x:.3f} y={nose.y:.3f} z={nose.z:.3f} vis={nose.visibility:.2f} | "
                        f"L_Shoulder: x={left_shoulder.x:.3f} y={left_shoulder.y:.3f} | "
                        f"R_Shoulder: x={right_shoulder.x:.3f} y={right_shoulder.y:.3f}"
                    )

                # Шаг 5. Сбор данных в структуру для сохранения в JSON
                frame_landmarks_list = []
                for idx, p in enumerate(landmarks):
                    frame_landmarks_list.append({
                        "id": idx,
                        "name": mp_pose.PoseLandmark(idx).name,
                        "x": float(p.x),
                        "y": float(p.y),
                        "z": float(p.z),
                        "v": float(p.visibility),
                    })

                frames_data.append({
                    "frame": frame_idx,
                    "timestamp": cur_time,
                    "landmarks": frame_landmarks_list,
                })

                # Прямая трансляция в Rust GUI в реальном времени (без задержки)
                if udp_sock is not None:
                    try:
                        stream_payload = json.dumps({
                            "frame": frame_idx,
                            "timestamp": cur_time,
                            "landmarks": frame_landmarks_list,
                        }).encode("utf-8")
                        udp_sock.sendto(stream_payload, ("127.0.0.1", args.stream_port))
                    except Exception:
                        pass

                # 2. Отрисовка скелета поверх оригинального BGR-кадра
                mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=landmark_drawing_spec,
                    connection_drawing_spec=connection_drawing_spec,
                )

            # Сохранение кадра в видео (до нанесения UI-оверлея или с ним)
            frame_for_save = frame.copy()

            # Отображение HUD
            if show_hud:
                draw_info_overlay(
                    frame,
                    fps_smooth,
                    frame_idx,
                    results.pose_landmarks is not None,
                    nose_info,
                    is_recording,
                )

            if is_recording and video_writer is not None:
                video_writer.write(frame)

            # Отображение окна пользователю
            if not args.no_display:
                cv2.imshow(window_name, frame)

                # Проверка закрытия окна пользователем по крестику [X]
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                    print("\n[ИНФО] Окно закрыто пользователем ([X]). Завершение работы...")
                    break

                # Обработка нажатий клавиш
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("\n[ИНФО] Получен сигнал завершения (клавиша 'q').")
                    break
                elif key == ord("r"):
                    is_recording = not is_recording
                    state_str = "ВКЛЮЧЕНА" if is_recording else "ВЫКЛЮЧЕНА"
                    print(f"[ИНФО] Запись видео: {state_str}")
                elif key == ord("h"):
                    show_hud = not show_hud
                elif key == ord("s"):
                    screenshot_name = f"screenshot_frame_{frame_idx:04d}.png"
                    cv2.imwrite(screenshot_name, frame)
                    print(f"[ИНФО] Скриншот сохранен: {screenshot_name}")
            frame_idx += 1

    except KeyboardInterrupt:
        print("\n[ИНФО] Получен сигнал прерывания (Ctrl+C). Сохраняю записанные данные...")

    finally:
        # Освобождение ресурсов
        cap.release()
        if video_writer is not None:
            video_writer.release()
        if udp_sock is not None:
            udp_sock.close()
        cv2.destroyAllWindows()
        pose.close()

    # Шаг 5. Сохранение данных в JSON и CSV
    if frames_data:
        if args.output_json:
            tmp_json = args.output_json + ".tmp"
            with open(tmp_json, "w", encoding="utf-8") as f:
                json.dump(frames_data, f, indent=1, ensure_ascii=False)
            if os.path.exists(args.output_json):
                os.remove(args.output_json)
            os.rename(tmp_json, args.output_json)
            print(f"[УСПЕХ] Сохранено {len(frames_data)} кадров скелета в JSON: '{args.output_json}'.")

        if args.output_csv:
            import csv
            tmp_csv = args.output_csv + ".tmp"
            with open(tmp_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["frame", "timestamp", "landmark_id", "landmark_name", "x", "y", "z", "visibility"])
                for frame_item in frames_data:
                    f_id = frame_item["frame"]
                    ts = frame_item["timestamp"]
                    for lm in frame_item["landmarks"]:
                        writer.writerow([
                            f_id,
                            f"{ts:.4f}",
                            lm["id"],
                            lm["name"],
                            f"{lm['x']:.6f}",
                            f"{lm['y']:.6f}",
                            f"{lm['z']:.6f}",
                            f"{lm['v']:.4f}",
                        ])
            if os.path.exists(args.output_csv):
                os.remove(args.output_csv)
            os.rename(tmp_csv, args.output_csv)
            print(f"[УСПЕХ] Данные также экспортированы в CSV: '{args.output_csv}'.")
    else:
        print("[ПРЕДУПРЕЖДЕНИЕ] Человек не был обнаружен в кадре, файлы JSON/CSV не созданы.")

    if is_recording and os.path.exists(args.output_video):
        size_mb = os.path.getsize(args.output_video) / (1024 * 1024)
        print(f"[УСПЕХ] Видео с наложенным скелетом сохранено в '{args.output_video}' ({size_mb:.2f} МБ).")


if __name__ == "__main__":
    main()
