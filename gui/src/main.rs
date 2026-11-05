#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use eframe::egui::{self, Color32, Pos2, Rect, Stroke, Vec2};
use serde::{Deserialize, Serialize};
use std::fs::File;
use std::io::BufReader;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::time::Instant;

/// Связи скелета BlazePose (33 точки)
const POSE_CONNECTIONS: &[(usize, usize)] = &[
    // Голова / Лицо
    (0, 1), (1, 2), (2, 3), (3, 7),
    (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10),
    // Плечевой пояс и туловище
    (11, 12), (11, 23), (12, 24), (23, 24),
    // Левая рука
    (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19),
    // Правая рука
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20),
    // Левая нога
    (23, 25), (25, 27), (27, 29), (29, 31), (27, 31),
    // Правая нога
    (24, 26), (26, 28), (28, 30), (30, 32), (28, 32),
];

fn landmark_name_ru(idx: usize) -> &'static str {
    match idx {
        0 => "Нос",
        1 => "Внутр. угол л.глаза",
        2 => "Лев. глаз",
        3 => "Внеш. угол л.глаза",
        4 => "Внутр. угол п.глаза",
        5 => "Прав. глаз",
        6 => "Внеш. угол п.глаза",
        7 => "Левое ухо",
        8 => "Правое ухо",
        9 => "Левый угол рта",
        10 => "Правый угол рта",
        11 => "Левое плечо",
        12 => "Правое плечо",
        13 => "Левый локоть",
        14 => "Правый локоть",
        15 => "Левое запястье",
        16 => "Правое запястье",
        17 => "Левый мизинец",
        18 => "Правый мизинец",
        19 => "Левый указательный",
        20 => "Правый указательный",
        21 => "Левый большой палец",
        22 => "Правый большой палец",
        23 => "Левое бедро",
        24 => "Правое бедро",
        25 => "Левое колено",
        26 => "Правое колено",
        27 => "Левая лодыжка",
        28 => "Правая лодыжка",
        29 => "Левая пятка",
        30 => "Правая пятка",
        31 => "Левый носок",
        32 => "Правый носок",
        _ => "Сустав",
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Landmark {
    pub id: usize,
    #[serde(default)]
    pub name: String,
    pub x: f32,
    pub y: f32,
    pub z: f32,
    #[serde(default = "default_vis")]
    pub v: f32,
}

fn default_vis() -> f32 {
    1.0
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FrameData {
    pub frame: usize,
    #[serde(default)]
    pub timestamp: f64,
    pub landmarks: Vec<Landmark>,
}

pub struct Camera3D {
    pub pitch: f32,
    pub yaw: f32,
    pub zoom: f32,
    pub pan: Vec2,
}

impl Default for Camera3D {
    fn default() -> Self {
        Self {
            pitch: 0.15,
            yaw: -0.35,
            zoom: 1.0,
            pan: Vec2::ZERO,
        }
    }
}

struct AppState {
    // Данные скелета
    frames: Vec<FrameData>,
    current_frame: usize,
    is_playing: bool,
    playback_speed: f32,
    last_frame_tick: Instant,

    // 3D Камера
    camera: Camera3D,
    show_labels: bool,
    show_floor_grid: bool,

    // Управление Python-процессом (захват видео)
    python_process: Option<Child>,
    camera_index: String,
    model_complexity: usize,
    record_video: bool,
    status_message: String,
    status_is_error: bool,

    // Пути к файлам
    json_path: PathBuf,
    csv_path: PathBuf,
    video_path: PathBuf,
    python_exe: PathBuf,

    // Прямая 3D-трансляция через UDP сокет
    udp_socket: Option<std::net::UdpSocket>,
    live_landmarks: Option<Vec<Landmark>>,
    live_fps: f32,
    live_frames_count: usize,
    last_fps_time: Instant,

    // Вкладки интерфейса
    show_table: bool,
}

impl AppState {
    fn new(_cc: &eframe::CreationContext<'_>) -> Self {
        let base_dir = PathBuf::from("..");
        let json_path = if Path::new("skeleton_data.json").exists() {
            PathBuf::from("skeleton_data.json")
        } else if base_dir.join("skeleton_data.json").exists() {
            base_dir.join("skeleton_data.json")
        } else if Path::new("sample_skeleton_data.json").exists() {
            PathBuf::from("sample_skeleton_data.json")
        } else {
            base_dir.join("sample_skeleton_data.json")
        };

        let csv_path = if Path::new("skeleton_data.csv").exists() {
            PathBuf::from("skeleton_data.csv")
        } else {
            base_dir.join("skeleton_data.csv")
        };

        let video_path = if Path::new("output_skeleton.mp4").exists() {
            PathBuf::from("output_skeleton.mp4")
        } else {
            base_dir.join("output_skeleton.mp4")
        };

        let python_exe = if Path::new(r".venv\Scripts\python.exe").exists() {
            PathBuf::from(r".venv\Scripts\python.exe")
        } else if base_dir.join(r".venv\Scripts\python.exe").exists() {
            base_dir.join(r".venv\Scripts\python.exe")
        } else {
            PathBuf::from("python")
        };

        let udp_socket = match std::net::UdpSocket::bind("127.0.0.1:9099") {
            Ok(sock) => {
                let _ = sock.set_nonblocking(true);
                Some(sock)
            }
            Err(e) => {
                eprintln!("[ПРЕДУПРЕЖДЕНИЕ] Не удалось открыть UDP сокет 127.0.0.1:9099: {e}");
                None
            }
        };

        let mut app = Self {
            frames: Vec::new(),
            current_frame: 0,
            is_playing: false,
            playback_speed: 1.0,
            last_frame_tick: Instant::now(),
            camera: Camera3D::default(),
            show_labels: true,
            show_floor_grid: true,
            python_process: None,
            camera_index: "0".to_string(),
            model_complexity: 1,
            record_video: true,
            status_message: "Готово к работе".to_string(),
            status_is_error: false,
            json_path,
            csv_path,
            video_path,
            python_exe,
            udp_socket,
            live_landmarks: None,
            live_fps: 0.0,
            live_frames_count: 0,
            last_fps_time: Instant::now(),
            show_table: false,
        };

        app.load_json_data();
        app
    }

    fn load_json_data(&mut self) {
        if !self.json_path.exists() {
            self.status_message = format!("Файл '{}' не найден", self.json_path.display());
            self.status_is_error = true;
            return;
        }

        match File::open(&self.json_path) {
            Ok(file) => {
                let reader = BufReader::new(file);
                match serde_json::from_reader::<_, Vec<FrameData>>(reader) {
                    Ok(loaded) => {
                        self.status_message = format!(
                            "Загружено {} кадров из '{}'",
                            loaded.len(),
                            self.json_path.file_name().unwrap_or_default().to_string_lossy()
                        );
                        self.status_is_error = false;
                        self.frames = loaded;
                        self.current_frame = 0;
                    }
                    Err(e) => {
                        self.status_message = format!("Ошибка парсинга JSON: {e}");
                        self.status_is_error = true;
                    }
                }
            }
            Err(e) => {
                self.status_message = format!("Не удалось открыть файл: {e}");
                self.status_is_error = true;
            }
        }
    }

    fn start_tracking(&mut self) {
        if self.python_process.is_some() {
            self.status_message = "Процесс захвата уже запущен!".to_string();
            return;
        }

        let script_path = if Path::new("capture_skeleton.py").exists() {
            PathBuf::from("capture_skeleton.py")
        } else {
            PathBuf::from("..").join("capture_skeleton.py")
        };

        let mut cmd = Command::new(&self.python_exe);
        cmd.arg(&script_path);
        cmd.arg("--source").arg(&self.camera_index);
        cmd.arg("--complexity").arg(self.model_complexity.to_string());

        if !self.record_video {
            cmd.arg("--no-record");
        }

        if let Some(parent) = script_path.parent() {
            if parent.as_os_str() != "" {
                cmd.current_dir(parent);
            }
        }

        match cmd.spawn() {
            Ok(child) => {
                self.status_message = format!("Запущен захват видео (PID: {})", child.id());
                self.status_is_error = false;
                self.python_process = Some(child);
            }
            Err(e) => {
                self.status_message = format!("Ошибка запуска Python: {e}");
                self.status_is_error = true;
            }
        }
    }

    fn stop_tracking(&mut self) {
        if let Some(mut child) = self.python_process.take() {
            let _ = child.kill();
            self.status_message = "Процесс захвата остановлен. Обновление данных...".to_string();
            self.status_is_error = false;
            self.live_landmarks = None;
            self.load_json_data();
        }
    }

    fn check_process_status(&mut self) {
        if let Some(child) = &mut self.python_process {
            match child.try_wait() {
                Ok(Some(status)) => {
                    self.status_message = format!("Процесс захвата завершился ({status}). Данные обновлены.");
                    self.status_is_error = false;
                    self.python_process = None;
                    self.live_landmarks = None;
                    self.load_json_data();
                }
                Ok(None) => {}
                Err(e) => {
                    self.status_message = format!("Ошибка проверки процесса: {e}");
                    self.python_process = None;
                    self.live_landmarks = None;
                }
            }
        }
    }
}

impl eframe::App for AppState {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.check_process_status();

        // Прием потока координат 33 точек скелета через неблокирующий UDP сокет
        if let Some(sock) = &self.udp_socket {
            let mut buf = [0u8; 65535];
            while let Ok((len, _)) = sock.recv_from(&mut buf) {
                if let Ok(record) = serde_json::from_slice::<FrameData>(&buf[..len]) {
                    self.live_landmarks = Some(record.landmarks);
                    self.live_frames_count += 1;
                    if self.last_fps_time.elapsed().as_secs_f32() >= 1.0 {
                        self.live_fps = self.live_frames_count as f32 / self.last_fps_time.elapsed().as_secs_f32();
                        self.live_frames_count = 0;
                        self.last_fps_time = Instant::now();
                    }
                    ctx.request_repaint();
                }
            }
        }

        if self.is_playing && !self.frames.is_empty() {
            let interval = (1.0 / (30.0 * self.playback_speed)).max(0.01);
            if self.last_frame_tick.elapsed().as_secs_f32() >= interval {
                self.current_frame = (self.current_frame + 1) % self.frames.len();
                self.last_frame_tick = Instant::now();
            }
            ctx.request_repaint();
        }

        // ВЕРХНЯЯ ПАНЕЛЬ
        egui::TopBottomPanel::top("top_bar").show(ctx, |ui| {
            ui.add_space(4.0);
            ui.horizontal(|ui| {
                ui.heading("⚡ MediaPipe Pose Studio (Rust)");
                ui.separator();

                let is_running = self.python_process.is_some();
                let is_streaming = is_running && self.live_landmarks.is_some();
                let (badge_text, badge_color) = if is_streaming {
                    (format!("● ПРЯМАЯ 3D-ТРАНСЛЯЦИЯ ({:4.1} FPS)", self.live_fps), Color32::from_rgb(0, 255, 120))
                } else if is_running {
                    ("● КАМЕРА АКТИВНА (ПОДКЛЮЧЕНИЕ...)".to_string(), Color32::from_rgb(40, 200, 80))
                } else if !self.frames.is_empty() {
                    ("✓ ДАННЫЕ ЗАГРУЖЕНЫ".to_string(), Color32::from_rgb(80, 160, 240))
                } else {
                    ("○ ОЖИДАНИЕ".to_string(), Color32::GRAY)
                };

                ui.colored_label(badge_color, badge_text);

                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    egui::widgets::global_dark_light_mode_buttons(ui);
                    ui.label(format!("Всего кадров: {}", self.frames.len()));
                });
            });
            ui.add_space(4.0);
        });

        // ЛЕВАЯ ПАНЕЛЬ: Управление и настройки
        egui::SidePanel::left("left_controls").min_width(280.0).max_width(320.0).show(ctx, |ui| {
            ui.add_space(8.0);
            ui.heading("Параметры захвата");
            ui.separator();

            ui.group(|ui| {
                ui.label("Источник видео:");
                ui.text_edit_singleline(&mut self.camera_index);
                ui.small("Индекс веб-камеры (0, 1) или путь к .mp4");

                ui.add_space(4.0);
                ui.label("Точность модели BlazePose:");
                ui.horizontal(|ui| {
                    ui.radio_value(&mut self.model_complexity, 0, "Быстро (0)");
                    ui.radio_value(&mut self.model_complexity, 1, "Баланс (1)");
                    ui.radio_value(&mut self.model_complexity, 2, "Точно (2)");
                });

                ui.add_space(4.0);
                ui.checkbox(&mut self.record_video, "Записывать видео (output_skeleton.mp4)");
            });

            ui.add_space(8.0);
            let is_running = self.python_process.is_some();
            if !is_running {
                let btn = egui::Button::new("▶  Запустить захват с камеры")
                    .fill(Color32::from_rgb(30, 140, 60))
                    .min_size(Vec2::new(ui.available_width(), 38.0));
                if ui.add(btn).clicked() {
                    self.start_tracking();
                }
            } else {
                let btn = egui::Button::new("⏹  Остановить захват")
                    .fill(Color32::from_rgb(180, 40, 40))
                    .min_size(Vec2::new(ui.available_width(), 38.0));
                if ui.add(btn).clicked() {
                    self.stop_tracking();
                }
            }

            ui.add_space(12.0);
            ui.heading("Действия с файлами");
            ui.separator();

            if ui.button("🔄 Перезагрузить JSON данные").clicked() {
                self.load_json_data();
            }

            if ui.button("🎬 Открыть сохраненное видео (MP4)").clicked() {
                let path = self.video_path.canonicalize().unwrap_or_else(|_| self.video_path.clone());
                let _ = Command::new("cmd").args(["/C", "start", "", &path.to_string_lossy()]).spawn();
            }

            if ui.button("📊 Открыть таблицу координат (CSV)").clicked() {
                let path = self.csv_path.canonicalize().unwrap_or_else(|_| self.csv_path.clone());
                let _ = Command::new("cmd").args(["/C", "start", "", &path.to_string_lossy()]).spawn();
            }

            ui.add_space(12.0);
            ui.heading("3D Вид");
            ui.separator();
            ui.checkbox(&mut self.show_labels, "Подписи ключевых суставов");
            ui.checkbox(&mut self.show_floor_grid, "Отображать сетку пола");
            if ui.button("Сбросить положение камеры").clicked() {
                self.camera = Camera3D::default();
            }

            ui.add_space(12.0);
            ui.checkbox(&mut self.show_table, "Показать таблицу суставов");

            ui.with_layout(egui::Layout::bottom_up(egui::Align::LEFT), |ui| {
                ui.add_space(8.0);
                let color = if self.status_is_error {
                    Color32::from_rgb(240, 80, 80)
                } else {
                    Color32::from_rgb(100, 200, 120)
                };
                ui.colored_label(color, &self.status_message);
                ui.separator();
            });
        });

        // НИЖНЯЯ ПАНЕЛЬ: Таймлайн и управление анимацией
        egui::TopBottomPanel::bottom("bottom_timeline").min_height(70.0).show(ctx, |ui| {
            ui.add_space(6.0);
            let total = self.frames.len();
            ui.horizontal(|ui| {
                let play_icon = if self.is_playing { "⏸ Пауза" } else { "▶ Воспроизведение" };
                if ui.button(play_icon).clicked() {
                    self.is_playing = !self.is_playing;
                    self.last_frame_tick = Instant::now();
                }

                if ui.button("⏮").on_hover_text("Первый кадр").clicked() {
                    self.current_frame = 0;
                }
                if ui.button("◀").on_hover_text("Кадр назад").clicked() {
                    if self.current_frame > 0 {
                        self.current_frame -= 1;
                    }
                }
                if ui.button("▶").on_hover_text("Кадр вперед").clicked() {
                    if total > 0 && self.current_frame + 1 < total {
                        self.current_frame += 1;
                    }
                }
                if ui.button("⏭").on_hover_text("Последний кадр").clicked() {
                    if total > 0 {
                        self.current_frame = total - 1;
                    }
                }

                ui.separator();
                ui.label("Скорость:");
                ui.selectable_value(&mut self.playback_speed, 0.5, "0.5x");
                ui.selectable_value(&mut self.playback_speed, 1.0, "1x");
                ui.selectable_value(&mut self.playback_speed, 2.0, "2x");

                ui.separator();
                if total > 0 {
                    let cur_sec = (self.current_frame as f32) / 30.0;
                    let tot_sec = (total as f32) / 30.0;
                    ui.monospace(format!(
                        "Кадр: {:04} / {:04} ({:04.1}s / {:04.1}s)",
                        self.current_frame + 1,
                        total,
                        cur_sec,
                        tot_sec
                    ));
                } else {
                    ui.label("Нет доступных кадров для анимации");
                }
            });

            if total > 0 {
                let mut slider_val = self.current_frame;
                if ui.add(
                    egui::Slider::new(&mut slider_val, 0..=total.saturating_sub(1))
                        .show_value(false)
                ).changed() {
                    self.current_frame = slider_val;
                }
            }
            ui.add_space(4.0);
        });

        // НИЖНЯЯ ВСПЛЫВАЮЩАЯ ТАБЛИЦА СУСТАВОВ
        if self.show_table {
            let is_streaming = self.python_process.is_some() && self.live_landmarks.is_some();
            let table_landmarks: Option<&[Landmark]> = if is_streaming {
                self.live_landmarks.as_deref()
            } else if !self.frames.is_empty() {
                let cur = &self.frames[self.current_frame.min(self.frames.len() - 1)];
                Some(&cur.landmarks)
            } else {
                None
            };

            if let Some(lms) = table_landmarks {
                egui::TopBottomPanel::bottom("landmarks_table").resizable(true).min_height(140.0).show(ctx, |ui| {
                    let title = if is_streaming { "Значения 33 точек (ОНЛАЙН ТРАНСЛЯЦИЯ):" } else { "Значения 33 точек текущего кадра:" };
                    ui.heading(title);
                    egui::ScrollArea::vertical().show(ui, |ui| {
                        egui::Grid::new("lm_grid").striped(true).min_col_width(70.0).show(ui, |ui| {
                            ui.label("ID");
                            ui.label("Анатомическая точка");
                            ui.label("X (Ширина)");
                            ui.label("Y (Высота)");
                            ui.label("Z (Глубина)");
                            ui.label("Видимость (V)");
                            ui.end_row();

                            for p in lms {
                                ui.label(p.id.to_string());
                                ui.label(landmark_name_ru(p.id));
                                ui.monospace(format!("{:.4}", p.x));
                                ui.monospace(format!("{:.4}", p.y));
                                ui.monospace(format!("{:.4}", p.z));
                                let v_color = if p.v > 0.6 {
                                    Color32::from_rgb(60, 200, 60)
                                } else if p.v > 0.3 {
                                    Color32::from_rgb(220, 180, 40)
                                } else {
                                    Color32::from_rgb(200, 60, 60)
                                };
                                ui.colored_label(v_color, format!("{:.1}%", p.v * 100.0));
                                ui.end_row();
                            }
                        });
                    });
                });
            }
        }

        // ЦЕНТРАЛЬНАЯ ПАНЕЛЬ: 3D Скелетный видовой экран
        egui::CentralPanel::default().show(ctx, |ui| {
            self.draw_3d_viewport(ui);
        });
    }
}

impl AppState {
    fn draw_3d_viewport(&mut self, ui: &mut egui::Ui) {
        let (rect, response) = ui.allocate_exact_size(ui.available_size(), egui::Sense::drag());

        if response.dragged_by(egui::PointerButton::Primary) {
            let delta = response.drag_delta();
            self.camera.yaw += delta.x * 0.008;
            self.camera.pitch = (self.camera.pitch + delta.y * 0.008).clamp(-1.4, 1.4);
        } else if response.dragged_by(egui::PointerButton::Secondary) {
            self.camera.pan += response.drag_delta();
        }

        let scroll = ui.input(|i| i.smooth_scroll_delta.y);
        if scroll != 0.0 {
            self.camera.zoom = (self.camera.zoom * (1.0 + scroll * 0.002)).clamp(0.2, 5.0);
        }

        let painter = ui.painter_at(rect);
        painter.rect_filled(rect, 4.0, Color32::from_rgb(18, 20, 26));

        if self.show_floor_grid {
            self.draw_floor_grid(&painter, rect);
        }

        let is_streaming = self.python_process.is_some() && self.live_landmarks.is_some();
        let current_landmarks: Option<&[Landmark]> = if is_streaming {
            self.live_landmarks.as_deref()
        } else if !self.frames.is_empty() {
            let cur_frame_idx = self.current_frame.min(self.frames.len() - 1);
            Some(&self.frames[cur_frame_idx].landmarks)
        } else {
            None
        };

        let landmarks = match current_landmarks {
            Some(lms) => lms,
            None => {
                painter.text(
                    rect.center(),
                    egui::Align2::CENTER_CENTER,
                    "Нет загруженных данных скелета.\nНажмите 'Запустить захват с камеры' для онлайн 3D-трансляции.",
                    egui::FontId::proportional(18.0),
                    Color32::from_rgb(160, 170, 190),
                );
                return;
            }
        };

        // Бейдж активной онлайн 3D трансляции
        if is_streaming {
            painter.rect_filled(
                Rect::from_min_size(rect.left_top() + Vec2::new(14.0, 36.0), Vec2::new(260.0, 26.0)),
                4.0,
                Color32::from_black_alpha(180),
            );
            painter.text(
                rect.left_top() + Vec2::new(22.0, 42.0),
                egui::Align2::LEFT_TOP,
                format!("● ОНЛАЙН 3D-ТРАНСЛЯЦИЯ ({:4.1} FPS)", self.live_fps),
                egui::FontId::proportional(13.0),
                Color32::from_rgb(40, 240, 120),
            );
        }

        let mut center = [0.5f32, 0.5f32, 0.0f32];
        if landmarks.len() > 24 {
            let l_hip = &landmarks[23];
            let r_hip = &landmarks[24];
            center[0] = (l_hip.x + r_hip.x) * 0.5;
            center[1] = (l_hip.y + r_hip.y) * 0.5;
            center[2] = (l_hip.z + r_hip.z) * 0.5;
        }

        let projected: Vec<(Pos2, f32, f32)> = landmarks
            .iter()
            .map(|lm| {
                let p = self.project_3d(lm.x - center[0], -(lm.y - center[1]), -lm.z + center[2], rect);
                (p.0, p.1, lm.v)
            })
            .collect();

        // 1. Кости
        for &(p1, p2) in POSE_CONNECTIONS {
            if p1 < projected.len() && p2 < projected.len() {
                let (pt1, _, v1) = projected[p1];
                let (pt2, _, v2) = projected[p2];

                if v1 < 0.2 || v2 < 0.2 {
                    continue;
                }

                let alpha = ((v1.min(v2)) * 255.0) as u8;

                let color = if (p1 == 11 && p2 == 12) || (p1 == 23 && p2 == 24) || (p1 == 11 && p2 == 23) || (p1 == 12 && p2 == 24) {
                    Color32::from_rgba_premultiplied(80, 140, 255, alpha)
                } else if p1 % 2 == 1 && p2 % 2 == 1 {
                    Color32::from_rgba_premultiplied(240, 60, 60, alpha)
                } else if p1 % 2 == 0 && p2 % 2 == 0 {
                    Color32::from_rgba_premultiplied(40, 210, 200, alpha)
                } else {
                    Color32::from_rgba_premultiplied(240, 200, 50, alpha)
                };

                let stroke_width = 3.2_f32 * self.camera.zoom.clamp(0.6, 2.0);
                painter.line_segment([pt1, pt2], Stroke::new(stroke_width, color));
            }
        }

        // 2. Суставы
        for (idx, &(pos, _, vis)) in projected.iter().enumerate() {
            if vis < 0.2 {
                continue;
            }

            let radius = (4.5_f32 * self.camera.zoom).clamp(2.0, 12.0);
            let alpha = (vis * 255.0) as u8;
            let fill_color = Color32::from_rgba_premultiplied(70, 240, 90, alpha);
            let stroke_color = Color32::from_rgba_premultiplied(10, 80, 20, alpha);

            painter.circle(pos, radius, fill_color, Stroke::new(1.2_f32, stroke_color));

            if self.show_labels && vis >= 0.5 {
                let name = match idx {
                    0 => Some("Нос"),
                    11 => Some("Л.плечо"),
                    12 => Some("П.плечо"),
                    13 => Some("Л.локоть"),
                    14 => Some("П.локоть"),
                    15 => Some("Л.кисть"),
                    16 => Some("П.кисть"),
                    23 => Some("Л.бедро"),
                    24 => Some("П.бедро"),
                    25 => Some("Л.колено"),
                    26 => Some("П.колено"),
                    27 => Some("Л.лодыжка"),
                    28 => Some("П.лодыжка"),
                    _ => None,
                };

                if let Some(label) = name {
                    painter.text(
                        pos + Vec2::new(8.0, -4.0),
                        egui::Align2::LEFT_CENTER,
                        label,
                        egui::FontId::proportional(11.0),
                        Color32::from_rgb(220, 220, 230),
                    );
                }
            }
        }

        painter.text(
            rect.left_top() + Vec2::new(14.0, 14.0),
            egui::Align2::LEFT_TOP,
            "ЛКМ: Вращение 3D | ПКМ: Сдвиг | Колесико: Масштаб",
            egui::FontId::proportional(12.0),
            Color32::from_rgb(140, 150, 170),
        );
    }

    fn project_3d(&self, x: f32, y: f32, z: f32, rect: Rect) -> (Pos2, f32) {
        let cos_y = self.camera.yaw.cos();
        let sin_y = self.camera.yaw.sin();
        let x1 = x * cos_y + z * sin_y;
        let z1 = -x * sin_y + z * cos_y;

        let cos_p = self.camera.pitch.cos();
        let sin_p = self.camera.pitch.sin();
        let y2 = y * cos_p - z1 * sin_p;
        let z2 = y * sin_p + z1 * cos_p;

        let dist = 2.2_f32;
        let fov = 500.0_f32 * self.camera.zoom;
        let depth = (z2 + dist).max(0.1_f32);
        let screen_x = rect.center().x + self.camera.pan.x + (x1 / depth) * fov;
        let screen_y = rect.center().y + self.camera.pan.y - (y2 / depth) * fov;

        (Pos2::new(screen_x, screen_y), depth)
    }

    fn draw_floor_grid(&self, painter: &egui::Painter, rect: Rect) {
        let grid_size = 5;
        let step = 0.2f32;
        let y_floor = -0.7f32;
        let grid_color = Color32::from_rgb(35, 40, 52);

        for i in -grid_size..=grid_size {
            let coord = (i as f32) * step;
            let (p1, _) = self.project_3d(coord, y_floor, -grid_size as f32 * step, rect);
            let (p2, _) = self.project_3d(coord, y_floor, grid_size as f32 * step, rect);
            painter.line_segment([p1, p2], Stroke::new(1.0_f32, grid_color));

            let (p3, _) = self.project_3d(-grid_size as f32 * step, y_floor, coord, rect);
            let (p4, _) = self.project_3d(grid_size as f32 * step, y_floor, coord, rect);
            painter.line_segment([p3, p4], Stroke::new(1.0_f32, grid_color));
        }
    }
}

fn main() -> eframe::Result<()> {
    let native_options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1120.0, 740.0])
            .with_min_inner_size([800.0, 500.0])
            .with_title("MediaPipe Pose Studio — Rust Control Center"),
        ..Default::default()
    };

    eframe::run_native(
        "MediaPipe Pose Studio",
        native_options,
        Box::new(|cc| Ok(Box::new(AppState::new(cc)))),
    )
}
