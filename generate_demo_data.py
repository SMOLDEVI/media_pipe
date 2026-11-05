"""
Генератор демонстрационных данных скелета для проверки 3D визуализации
и тестирования пайплайна без обязательного наличия человека перед камерой.
"""

import json
import math
import numpy as np
import mediapipe as mp

mp_pose = mp.solutions.pose

def generate_sample_skeleton_json(output_path="sample_skeleton_data.json", num_frames=60):
    """
    Генерирует реалистичную последовательность движения человека (33 точки BlazePose).
    Человек стоит и совершает приветственное движение рукой.
    """
    frames = []

    for f_idx in range(num_frames):
        t = f_idx / num_frames * 2 * math.pi
        arm_wave = 0.15 * math.sin(t * 3)

        # Базовые координаты точек (x, y, z) в системе координат кадра [0, 1]
        landmarks_dict = {
            0: (0.50, 0.20, -0.05),   # Nose
            1: (0.49, 0.19, -0.04),   # Left eye inner
            2: (0.48, 0.19, -0.04),   # Left eye
            3: (0.47, 0.19, -0.04),   # Left eye outer
            4: (0.51, 0.19, -0.04),   # Right eye inner
            5: (0.52, 0.19, -0.04),   # Right eye
            6: (0.53, 0.19, -0.04),   # Right eye outer
            7: (0.45, 0.20, 0.00),    # Left ear
            8: (0.55, 0.20, 0.00),    # Right ear
            9: (0.48, 0.23, -0.03),   # Mouth left
            10: (0.52, 0.23, -0.03),  # Mouth right
            11: (0.42, 0.30, 0.00),   # Left shoulder
            12: (0.58, 0.30, 0.00),   # Right shoulder
            # Руки: правая опущена, левая машет
            13: (0.35 + arm_wave * 0.5, 0.40 - arm_wave * 0.2, 0.05),  # Left elbow
            14: (0.64, 0.42, 0.00),   # Right elbow
            15: (0.32 + arm_wave, 0.25 - arm_wave * 0.5, 0.10),        # Left wrist
            16: (0.67, 0.55, 0.00),   # Right wrist
            17: (0.31 + arm_wave, 0.22 - arm_wave * 0.5, 0.11),        # Left pinky
            18: (0.68, 0.58, 0.00),   # Right pinky
            19: (0.30 + arm_wave, 0.23 - arm_wave * 0.5, 0.11),        # Left index
            20: (0.69, 0.57, 0.00),   # Right index
            21: (0.33 + arm_wave, 0.24 - arm_wave * 0.5, 0.10),        # Left thumb
            22: (0.66, 0.56, 0.00),   # Right thumb
            23: (0.44, 0.55, 0.00),   # Left hip
            24: (0.56, 0.55, 0.00),   # Right hip
            25: (0.43, 0.72, -0.02),  # Left knee
            26: (0.57, 0.72, -0.02),  # Right knee
            27: (0.42, 0.90, 0.02),   # Left ankle
            28: (0.58, 0.90, 0.02),   # Right ankle
            29: (0.41, 0.93, 0.05),   # Left heel
            30: (0.59, 0.93, 0.05),   # Right heel
            31: (0.40, 0.92, -0.05),  # Left foot index
            32: (0.60, 0.92, -0.05),  # Right foot index
        }

        lm_list = []
        for idx in range(33):
            x, y, z = landmarks_dict.get(idx, (0.5, 0.5, 0.0))
            name = mp_pose.PoseLandmark(idx).name
            lm_list.append({
                "id": idx,
                "name": name,
                "x": round(x, 4),
                "y": round(y, 4),
                "z": round(z, 4),
                "v": 0.99,
            })

        frames.append({
            "frame": f_idx,
            "timestamp": 1700000000.0 + f_idx * (1.0 / 30.0),
            "landmarks": lm_list,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(frames, f, indent=1, ensure_ascii=False)

    csv_path = output_path.replace(".json", ".csv")
    import csv
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "timestamp", "landmark_id", "landmark_name", "x", "y", "z", "visibility"])
        for fr in frames:
            for lm in fr["landmarks"]:
                writer.writerow([
                    fr["frame"],
                    f"{fr['timestamp']:.4f}",
                    lm["id"],
                    lm["name"],
                    lm["x"],
                    lm["y"],
                    lm["z"],
                    lm["v"],
                ])

    print(f"[УСПЕХ] Сгенерированы демо-данные: {len(frames)} кадров -> '{output_path}' и '{csv_path}'")


if __name__ == "__main__":
    generate_sample_skeleton_json("sample_skeleton_data.json", num_frames=60)
