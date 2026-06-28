import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import threading
import os
import sys
import shutil
import time
import json
import webbrowser
import ctypes
import re
import urllib.error
import urllib.request
import cv2
import numpy as np
import mss
import pytesseract
from PIL import Image, ImageTk
from datetime import datetime, timedelta, timezone

CONFIG_FILE = "config.json"
APP_VERSION = "2.0.2"
GITHUB_REPOSITORY = "ZICteam/EMS-Logger"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPOSITORY}/releases/latest"
GITHUB_API_LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
MOSCOW_TZ = timezone(timedelta(hours=3), "MSK")
DONATION_URL = "https://www.donationalerts.com/r/zic_team"
DEFAULT_WINDOW_GEOMETRY = "880x690"
MIN_WINDOW_SIZE = (760, 560)
DISCLAIMER_TEXT = (
    "EMS Logger не связана и не поддерживается Majestic РП, Take-Two, "
    "Rockstar North Interactive или любым другим правообладателем. Все "
    "используемые товарные знаки принадлежат их соответствующим владельцам "
    "и не связаны и не одобрены Take-Two, Rockstar North Interactive."
)

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

HWND_TOPMOST = -1
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

def set_window_absolute_position(window, left, top, width, height, topmost=False):
    window.update_idletasks()
    hwnd = window.winfo_id()
    insert_after = HWND_TOPMOST if topmost else 0
    flags = SWP_NOACTIVATE | SWP_SHOWWINDOW
    if not topmost:
        flags |= SWP_NOZORDER
    ctypes.windll.user32.SetWindowPos(
        hwnd,
        insert_after,
        int(left),
        int(top),
        int(width),
        int(height),
        flags,
    )

def moscow_now():
    return datetime.now(MOSCOW_TZ)

def get_default_config():
    return {
        "triggers": {
            "вакцинировали": "vaccines",
            "вы вылечили": "pills",
            "реанимировали": "reanim",
            "завершили": "fire",
            "физ": "fiz",
            "псих": "psih"
        },
        "save_path": "screenshots",
        "day_start": "10:00",
        "night_start": "20:00",
        "monitor": 1,
        "region": None,
        "version": APP_VERSION,
        "timezone": "MSK",
        "window_geometry": DEFAULT_WINDOW_GEOMETRY,
        "disclaimer_shown": False,
        "update_repo": GITHUB_REPOSITORY,
    }

def load_config():
    defaults = get_default_config()
    if not os.path.exists(CONFIG_FILE):
        return defaults
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    changed = False
    for key, value in defaults.items():
        if key not in loaded:
            loaded[key] = value
            changed = True
    if changed:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(loaded, f, indent=4, ensure_ascii=False)
    return loaded

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)

config = load_config()

def app_path(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.argv[0])))
    return os.path.join(base, *parts)

def find_tesseract():
    candidates = [
        app_path("tesseract", "tesseract.exe"),
        app_path("tesseract.exe"),
        app_path("_internal", "tesseract.exe"),
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "tesseract", "tesseract.exe"),
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "tesseract.exe"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        shutil.which("tesseract"),
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None

TESSERACT_PATH = find_tesseract()
if TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    tessdata_path = os.path.join(os.path.dirname(TESSERACT_PATH), "tessdata")
    if os.path.isdir(tessdata_path):
        os.environ["TESSDATA_PREFIX"] = tessdata_path

def load_icon(name, color="light", size=24):
    path = app_path("assets", "lucide_png", f"{name}_{color}.png")
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "assets", "lucide_png", f"{name}_{color}.png")
    if not os.path.exists(path):
        return None
    image = Image.open(path)
    return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))

MONITOR_INDEX = config.get("monitor", 1)
monitor_options = []
monitor = None
REGION = None
running = False
last_screenshot_times = {}
SCREENSHOT_COOLDOWN_SECONDS = 15

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.geometry(config.get("window_geometry", DEFAULT_WINDOW_GEOMETRY))
app.minsize(*MIN_WINDOW_SIZE)
app.configure(fg_color="#0B1220")
app.title(f"EMS Logger v{APP_VERSION} – Majestic RP")
geometry_save_after_id = None

def persist_window_geometry():
    global geometry_save_after_id
    geometry_save_after_id = None
    if app.state() == "normal":
        config["window_geometry"] = app.geometry()
        save_config(config)

def schedule_window_geometry_save(event=None):
    global geometry_save_after_id
    if event is not None and event.widget != app:
        return
    if geometry_save_after_id is not None:
        app.after_cancel(geometry_save_after_id)
    geometry_save_after_id = app.after(700, persist_window_geometry)

def on_app_close():
    persist_window_geometry()
    app.destroy()

app.bind("<Configure>", schedule_window_geometry_save)
app.protocol("WM_DELETE_WINDOW", on_app_close)

ICONS = {
    "activity": load_icon("activity", "blue", 22),
    "settings": load_icon("settings", "light", 20),
    "play": load_icon("play", "light", 20),
    "square": load_icon("square", "light", 20),
    "folder": load_icon("folder", "light", 20),
    "scan": load_icon("scan", "light", 20),
    "monitor": load_icon("monitor", "blue", 20),
    "clock": load_icon("clock", "light", 17),
    "rocket": load_icon("rocket", "blue", 30),
    "circle_check": load_icon("circle-check", "green", 18),
    "circle_alert": load_icon("circle-alert", "red", 18),
}

root_frame = ctk.CTkFrame(app, fg_color="#0B1220")
root_frame.pack(fill="both", expand=True, padx=14, pady=12)

nav_frame = ctk.CTkFrame(root_frame, fg_color="#111827", corner_radius=12)
nav_frame.pack(pady=(4, 12))

content_frame = ctk.CTkFrame(root_frame, fg_color="#0B1220")
content_frame.pack(fill="both", expand=True)

main_tab = ctk.CTkFrame(content_frame, fg_color="#0B1220")
settings_tab = ctk.CTkFrame(content_frame, fg_color="#0B1220")

def show_page(page_name):
    main_tab.pack_forget()
    settings_tab.pack_forget()
    logger_nav_btn.configure(fg_color="#173B8F", hover_color="#1D4ED8" if page_name == "logger" else "#1E293B")
    settings_nav_btn.configure(fg_color="#173B8F", hover_color="#1D4ED8" if page_name == "settings" else "#1E293B")
    if page_name == "logger":
        logger_nav_btn.configure(fg_color="#2563EB")
        settings_nav_btn.configure(fg_color="#111827")
        main_tab.pack(fill="both", expand=True)
    else:
        logger_nav_btn.configure(fg_color="#111827")
        settings_nav_btn.configure(fg_color="#2563EB")
        settings_tab.pack(fill="both", expand=True)

logger_nav_btn = ctk.CTkButton(
    nav_frame,
    text="Логгер",
    image=ICONS["activity"],
    compound="left",
    command=lambda: show_page("logger"),
    width=118,
    height=34,
    fg_color="#2563EB",
    hover_color="#1D4ED8",
    corner_radius=10,
    font=ctk.CTkFont(size=11, weight="bold"),
)
logger_nav_btn.pack(side="left", padx=(4, 2), pady=4)
settings_nav_btn = ctk.CTkButton(
    nav_frame,
    text="Настройки",
    image=ICONS["settings"],
    compound="left",
    command=lambda: show_page("settings"),
    width=136,
    height=34,
    fg_color="#111827",
    hover_color="#1E293B",
    corner_radius=10,
    font=ctk.CTkFont(size=11, weight="bold"),
)
settings_nav_btn.pack(side="left", padx=(2, 4), pady=4)

# ===== Основной таб "Логгер" =====

app_card = ctk.CTkFrame(main_tab, fg_color="#111C2F", border_color="#20304A", border_width=1, corner_radius=16)
app_card.pack(fill="both", expand=True, padx=4, pady=(18, 8))

header_frame = ctk.CTkFrame(app_card, fg_color="transparent")
header_frame.pack(fill="x", padx=22, pady=(20, 14))
brand_icon = ctk.CTkFrame(header_frame, width=54, height=54, fg_color="#102A5C", border_color="#2563EB", border_width=2, corner_radius=16)
brand_icon.pack(side="left", padx=(0, 16))
brand_icon.pack_propagate(False)
ctk.CTkLabel(brand_icon, text="", image=ICONS["activity"]).pack(expand=True)

brand_text = ctk.CTkFrame(header_frame, fg_color="transparent")
brand_text.pack(side="left", fill="x", expand=True)
title_row = ctk.CTkFrame(brand_text, fg_color="transparent")
title_row.pack(anchor="w")
ctk.CTkLabel(
    title_row,
    text=f"EMS Logger v{APP_VERSION}",
    font=ctk.CTkFont(size=26, weight="bold"),
    text_color="#F8FAFC",
).pack(side="left")
version_badge = ctk.CTkFrame(title_row, fg_color="#102A5C", corner_radius=7)
version_badge.pack(side="left", padx=10)
ctk.CTkLabel(
    version_badge,
    text="НОВАЯ ВЕРСИЯ",
    font=ctk.CTkFont(size=11, weight="bold"),
    text_color="#60A5FA",
).pack(padx=12, pady=4)
ctk.CTkLabel(
    brand_text,
    text="Чтение выбранной области экрана, сохранение и сортировка скриншотов по МСК",
    font=ctk.CTkFont(size=14),
    text_color="#AAB4C0"
).pack(anchor="w", pady=(5, 0))

divider = ctk.CTkFrame(app_card, height=1, fg_color="#21324B")
divider.pack(fill="x")

workspace_frame = ctk.CTkFrame(app_card, fg_color="transparent")
workspace_frame.pack(fill="both", expand=True, padx=44, pady=22)

status_block = ctk.CTkFrame(workspace_frame, fg_color="transparent")
status_block.pack(fill="x", pady=(0, 12))
rocket_frame = ctk.CTkFrame(status_block, width=60, height=60, fg_color="#10203A", border_color="#2563EB", border_width=2, corner_radius=30)
rocket_frame.pack(side="left", padx=(140, 18))
rocket_frame.pack_propagate(False)
status_icon_label = ctk.CTkLabel(rocket_frame, text="", image=ICONS["rocket"])
status_icon_label.pack(expand=True)

status_text_frame = ctk.CTkFrame(status_block, fg_color="transparent")
status_text_frame.pack(side="left", fill="x")
status_label = ctk.CTkLabel(status_text_frame, text="Ожидание запуска...", font=ctk.CTkFont(size=15, weight="bold"), text_color="#F8FAFC")
status_label.pack(anchor="w", pady=(0, 6))
detected_row = ctk.CTkFrame(status_text_frame, fg_color="transparent")
detected_row.pack(anchor="w", pady=(0, 8))
ocr_state_icon_label = ctk.CTkLabel(detected_row, text="", width=24)
ocr_state_icon_label.pack(side="left", padx=(0, 8))
detected_text_label = ctk.CTkLabel(detected_row, text="Обнаруженный текст: —", font=ctk.CTkFont(size=14), text_color="#AAB4C0")
detected_text_label.pack(side="left")
time_row = ctk.CTkFrame(status_text_frame, fg_color="transparent")
time_row.pack(anchor="w")
ctk.CTkLabel(time_row, text="", image=ICONS["clock"]).pack(side="left", padx=(0, 8))
msk_time_label = ctk.CTkLabel(time_row, text="Время МСК: --:--:--", font=ctk.CTkFont(size=14), text_color="#D1D5DB")
msk_time_label.pack(side="left")

def refresh_msk_clock():
    msk_time_label.configure(text=f"Время МСК: {moscow_now().strftime('%H:%M:%S')}")
    app.after(1000, refresh_msk_clock)

def is_daytime():
    now = moscow_now().time()
    day_start = datetime.strptime(config['day_start'], "%H:%M").time()
    night_start = datetime.strptime(config['night_start'], "%H:%M").time()
    return day_start <= now < night_start

def get_monitor_options():
    options = []
    with mss.mss() as sct:
        for index, item in enumerate(sct.monitors[1:], start=1):
            label = (
                f"Монитор {index} — {item['width']}x{item['height']} "
                f"(x={item['left']}, y={item['top']})"
            )
            options.append({"index": index, "label": label, "monitor": item})
    return options

def get_virtual_screen():
    with mss.mss() as sct:
        return sct.monitors[0]

def monitor_label_for_index(index):
    for option in monitor_options:
        if option["index"] == index:
            return option["label"]
    return str(index)

def monitor_index_from_label(label):
    for option in monitor_options:
        if option["label"] == label:
            return option["index"]
    try:
        return int(label)
    except (TypeError, ValueError):
        return MONITOR_INDEX

def update_monitor(index):
    global MONITOR_INDEX, monitor, REGION, monitor_options
    monitor_options = get_monitor_options()
    if not monitor_options:
        return False
    if "monitor_selector" in globals():
        monitor_selector.configure(values=[option["label"] for option in monitor_options])
    valid_indexes = {option["index"] for option in monitor_options}
    if index not in valid_indexes:
        index = monitor_options[0]["index"]
    MONITOR_INDEX = index
    config['monitor'] = index
    save_config(config)
    monitor = next(option["monitor"] for option in monitor_options if option["index"] == index)
    REGION = get_saved_region() or get_default_region()
    update_region_label()
    update_monitor_label()
    return True
    return False

def get_default_region():
    width = min(800, monitor['width'])
    height = min(300, monitor['height'])
    return {
        "top": monitor['top'] + monitor['height'] - height,
        "left": monitor['left'] + (monitor['width'] - width) // 2,
        "width": width,
        "height": height
    }

def get_saved_region():
    region = config.get("region")
    if not region:
        return None
    try:
        region = {key: int(region[key]) for key in ("top", "left", "width", "height")}
    except (KeyError, TypeError, ValueError):
        return None
    if region["width"] <= 0 or region["height"] <= 0:
        return None
    right = region["left"] + region["width"]
    bottom = region["top"] + region["height"]
    monitor_right = monitor["left"] + monitor["width"]
    monitor_bottom = monitor["top"] + monitor["height"]
    if (
        region["left"] < monitor["left"] or
        region["top"] < monitor["top"] or
        right > monitor_right or
        bottom > monitor_bottom
    ):
        return None
    return region

def save_region(region):
    global REGION
    REGION = region
    config["region"] = region
    save_config(config)
    update_region_label()

def update_monitor_label():
    if "monitor_selector" in globals():
        monitor_selector.set(monitor_label_for_index(MONITOR_INDEX))
    if "monitor_info_label" in globals() and monitor:
        monitor_info_label.configure(
            text=f"{monitor['width']}x{monitor['height']}  x={monitor['left']}  y={monitor['top']}"
        )

def update_region_label():
    if "region_label" not in globals():
        return
    if REGION:
        text = f"Область:   x={REGION['left']}   y={REGION['top']}   {REGION['width']}x{REGION['height']}"
    else:
        text = "Область: по умолчанию"
    region_label.configure(text=text)

def select_region():
    if running:
        status_label.configure(text="Остановите бота перед выбором области")
        return
    if not update_monitor(MONITOR_INDEX):
        status_label.configure(text="Монитор не найден")
        return

    monitor_left = int(monitor["left"])
    monitor_top = int(monitor["top"])
    monitor_width = int(monitor["width"])
    monitor_height = int(monitor["height"])

    with mss.mss() as sct:
        shot = np.array(sct.grab(monitor))
    shot = cv2.cvtColor(shot, cv2.COLOR_BGRA2RGB)
    image = Image.fromarray(shot)

    max_width = max(640, app.winfo_screenwidth() - 140)
    max_height = max(480, app.winfo_screenheight() - 180)
    scale = min(max_width / monitor_width, max_height / monitor_height, 1.0)
    view_width = max(1, int(monitor_width * scale))
    view_height = max(1, int(monitor_height * scale))
    if scale != 1.0:
        image = image.resize((view_width, view_height), Image.Resampling.LANCZOS)

    selector = tk.Toplevel(app)
    selector.title(f"Выбор области - монитор {MONITOR_INDEX}")
    selector.configure(bg="#0B1220")
    selector.attributes("-topmost", True)
    selector.transient(app)

    info = tk.Label(
        selector,
        text=f"Монитор {MONITOR_INDEX}: {monitor_width}x{monitor_height}  x={monitor_left} y={monitor_top}. Выделите область мышью, Esc - отмена.",
        bg="#0B1220",
        fg="#E5E7EB",
        font=("Segoe UI", 11),
        padx=12,
        pady=10,
    )
    info.pack(fill="x")

    canvas = tk.Canvas(
        selector,
        width=view_width,
        height=view_height,
        highlightthickness=0,
        cursor="crosshair",
        bg="#000000",
    )
    canvas.pack(padx=12, pady=(0, 12))
    preview = ImageTk.PhotoImage(image)
    canvas.image = preview
    canvas.create_image(0, 0, anchor="nw", image=preview)

    start = {"x": 0, "y": 0}
    rect = {"id": None}

    def clamp_view(x, y):
        x = max(0, min(view_width - 1, int(x)))
        y = max(0, min(view_height - 1, int(y)))
        return x, y

    def to_monitor(value):
        return int(round(value / scale))

    def on_press(event):
        x, y = clamp_view(event.x, event.y)
        start["x"] = x
        start["y"] = y
        if rect["id"] is not None:
            canvas.delete(rect["id"])
        rect["id"] = canvas.create_rectangle(x, y, x, y, outline="#EF4444", width=2)

    def on_drag(event):
        if rect["id"] is not None:
            x, y = clamp_view(event.x, event.y)
            canvas.coords(rect["id"], start["x"], start["y"], x, y)

    def on_release(event):
        end_x, end_y = clamp_view(event.x, event.y)
        local_left = to_monitor(min(start["x"], end_x))
        local_top = to_monitor(min(start["y"], end_y))
        width = to_monitor(abs(end_x - start["x"]))
        height = to_monitor(abs(end_y - start["y"]))
        selector.destroy()
        if width < 10 or height < 10:
            status_label.configure(text="Область слишком маленькая")
            return
        save_region({
            "left": monitor_left + local_left,
            "top": monitor_top + local_top,
            "width": min(width, monitor_width - local_left),
            "height": min(height, monitor_height - local_top),
        })
        status_label.configure(text="Область сохранена")

    def cancel(_event=None):
        selector.destroy()
        status_label.configure(text="Выбор области отменён")

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    selector.bind("<Escape>", cancel)
    selector.update_idletasks()
    x = app.winfo_x() + max(20, (app.winfo_width() - selector.winfo_width()) // 2)
    y = app.winfo_y() + max(20, (app.winfo_height() - selector.winfo_height()) // 2)
    selector.geometry(f"+{x}+{y}")
    selector.lift()
    selector.focus_force()
def reset_region():
    if running:
        status_label.configure(text="Остановите бота перед сбросом области")
        return
    if update_monitor(MONITOR_INDEX):
        save_region(get_default_region())
        status_label.configure(text="Область по умолчанию сохранена")

def ensure_folders():
    for folder in set(config['triggers'].values()):
        os.makedirs(os.path.join(config['save_path'], "day", folder), exist_ok=True)
        os.makedirs(os.path.join(config['save_path'], "night", folder), exist_ok=True)

def save_screenshot(img, folder_name):
    timestamp = moscow_now().strftime("%Y%m%d_%H%M%S_MSK")
    section = "day" if is_daytime() else "night"
    full_path = os.path.join(config['save_path'], section, folder_name, f"{timestamp}.png")

    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        print(f"[INFO] Попытка сохранить скриншот: {full_path}")
        print(f"[DEBUG] Размер изображения: {img.shape}")
        success, encoded = cv2.imencode(".png", img)
        if success:
            encoded.tofile(full_path)
            if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                print(f"[✅] Скриншот сохранён: {full_path}")
                return True
            print(f"[❌] Файл не появился после сохранения: {full_path}")
            status_label.configure(text="Ошибка сохранения: файл не создан")
            return False

        print(f"[❌] Не удалось закодировать PNG: {full_path}")
        status_label.configure(text="Ошибка сохранения: PNG не создан")
        return False
    except Exception as e:
        print(f"[⛔️] Ошибка при сохранении скриншота: {e}")
        status_label.configure(text=f"Ошибка сохранения: {e}")
        return False


def grab_fullscreen():
    with mss.mss() as sct:
        img = np.array(sct.grab(monitor))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

def grab_region():
    with mss.mss() as sct:
        img = np.array(sct.grab(REGION))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

def update_ui(text):
    if not text:
        ocr_state_icon_label.configure(image=None, text="")
        detected_text_label.configure(text="Обнаруженный текст: —", text_color="#AAB4C0")
        return
    is_error = "error" in text.lower() or "tesseract not found" in text.lower()
    if is_error:
        ocr_state_icon_label.configure(image=ICONS["circle_alert"], text="")
        detected_text_label.configure(text=f"Обнаруженный текст: {text}", text_color="#F87171")
    else:
        ocr_state_icon_label.configure(image=ICONS["circle_check"], text="")
        detected_text_label.configure(text=f"Обнаруженный текст: {text}", text_color="#22C55E")

def main_loop():
    global running, last_screenshot_times
    ensure_folders()
    update_monitor(MONITOR_INDEX)
    last_screenshot_times = {}

    while running:
        try:
            img = grab_fullscreen()
            region_img = grab_region()
        except Exception as e:
            status_label.configure(text=f"Ошибка захвата экрана: {e}")
            print(f"[⛔️] Ошибка захвата экрана: {e}")
            time.sleep(1)
            continue

        gray = cv2.cvtColor(region_img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        try:
            text = pytesseract.image_to_string(thresh, lang='rus+eng').strip().lower()
        except pytesseract.TesseractNotFoundError:
            update_ui("Tesseract not found")
            status_label.configure(text="Установите Tesseract OCR")
            running = False
            break
        except pytesseract.TesseractError as e:
            update_ui(f"OCR error: {e}")
            time.sleep(1)
            continue
        update_ui(text)

        if text:
            print(f"[TEXT] Распознанный текст: '{text}'")
            matched = False
            for trig, folder in config['triggers'].items():
                if trig.lower().strip() in text.lower():
                    matched = True
                    now_time = time.time()
                    time_since_last = now_time - last_screenshot_times.get(folder, 0)
                    if time_since_last >= SCREENSHOT_COOLDOWN_SECONDS:
                        print(f"[TRIGGER] Сработал триггер: '{trig}' → сохраняем в '{folder}'")
                        if save_screenshot(img, folder):
                            last_screenshot_times[folder] = now_time
                            status_label.configure(text=f"Скриншот сохранён: {folder}")
                    else:
                        remaining = SCREENSHOT_COOLDOWN_SECONDS - time_since_last
                        print(f"[⏳] Триггер найден, но КД: подождите ещё {remaining:.1f} сек")
                        status_label.configure(text=f"{folder}: КД {remaining:.1f} сек")
            if not matched:
                print("[INFO] Текст есть, но триггеры не найдены")
        time.sleep(0.5)

def start():
    global running
    if not running:
        running = True
        status_label.configure(text="Бот работает, сортировка по МСК")
        threading.Thread(target=main_loop, daemon=True).start()

def stop():
    global running
    running = False
    status_label.configure(text="Остановлено")

def open_folder():
    os.makedirs(config['save_path'], exist_ok=True)
    os.startfile(config['save_path'])

def open_donations():
    webbrowser.open(DONATION_URL)

def parse_version(value):
    parts = re.findall(r"\d+", str(value))
    return tuple(int(part) for part in parts[:4]) if parts else (0,)

def is_newer_version(latest, current):
    latest_parts = parse_version(latest)
    current_parts = parse_version(current)
    size = max(len(latest_parts), len(current_parts))
    latest_parts += (0,) * (size - len(latest_parts))
    current_parts += (0,) * (size - len(current_parts))
    return latest_parts > current_parts

def get_update_endpoints():
    repo = config.get("update_repo") or GITHUB_REPOSITORY
    return (
        f"https://api.github.com/repos/{repo}/releases/latest",
        f"https://github.com/{repo}/releases/latest",
    )

def fetch_latest_release():
    api_url, release_url = get_update_endpoints()
    request = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"EMS-Logger/{APP_VERSION}",
        },
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        data = json.loads(response.read().decode("utf-8"))
    latest_version = data.get("tag_name") or data.get("name") or ""
    return {
        "version": latest_version.lstrip("vV"),
        "url": data.get("html_url") or release_url,
    }

def check_for_updates(show_current=False):
    def worker():
        try:
            release = fetch_latest_release()
            latest_version = release["version"]
            release_url = release["url"]
            if latest_version and is_newer_version(latest_version, APP_VERSION):
                app.after(0, lambda: show_update_available(latest_version, release_url))
            elif show_current:
                app.after(0, lambda: status_label.configure(text="Установлена актуальная версия"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
            if show_current:
                message = str(error)
                app.after(0, lambda: status_label.configure(text=f"Не удалось проверить обновления: {message}"))

    threading.Thread(target=worker, daemon=True).start()

def show_update_available(version, url):
    status_label.configure(text=f"Доступна новая версия: {version}")
    update_notice_frame.pack(fill="x", pady=(0, 12), before=btn_frame)
    update_notice_label.configure(text=f"Доступно обновление EMS Logger v{version}")
    update_notice_button.configure(command=lambda: webbrowser.open(url))

# Монитор выбор
def monitor_change(val):
    idx = monitor_index_from_label(val)
    if update_monitor(idx):
        status_label.configure(text=f"Выбран {monitor_label_for_index(MONITOR_INDEX)}")
    else:
        status_label.configure(text="Мониторы не найдены")

def refresh_monitors():
    if update_monitor(MONITOR_INDEX):
        status_label.configure(text="Список мониторов обновлён")
    else:
        status_label.configure(text="Мониторы не найдены")

update_notice_frame = ctk.CTkFrame(workspace_frame, fg_color="#102A5C", border_color="#2563EB", border_width=1, corner_radius=12)
update_notice_label = ctk.CTkLabel(
    update_notice_frame,
    text="Доступно обновление EMS Logger",
    font=ctk.CTkFont(size=14, weight="bold"),
    text_color="#DBEAFE",
)
update_notice_label.pack(side="left", padx=16, pady=10)
update_notice_button = ctk.CTkButton(
    update_notice_frame,
    text="Открыть релиз",
    height=32,
    width=128,
    font=ctk.CTkFont(size=13, weight="bold"),
    fg_color="#2563EB",
    hover_color="#1D4ED8",
    corner_radius=8,
)
update_notice_button.pack(side="right", padx=10, pady=8)

btn_frame = ctk.CTkFrame(workspace_frame, fg_color="transparent")
btn_frame.pack(fill="x", pady=(0, 12))
btn_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="actions")
ctk.CTkButton(
    btn_frame,
    text="Запуск",
    image=ICONS["play"],
    compound="left",
    command=start,
    height=48,
    font=ctk.CTkFont(size=16, weight="bold"),
    fg_color="#2563EB",
    hover_color="#1D4ED8",
    corner_radius=10,
).grid(row=0, column=0, sticky="ew", padx=(0, 8))
ctk.CTkButton(
    btn_frame,
    text="Стоп",
    image=ICONS["square"],
    compound="left",
    command=stop,
    height=48,
    font=ctk.CTkFont(size=13),
    fg_color="#151F31",
    hover_color="#1E293B",
    border_color="#2A3B58",
    border_width=1,
    corner_radius=10,
).grid(row=0, column=1, sticky="ew", padx=8)
ctk.CTkButton(
    btn_frame,
    text="Папка",
    image=ICONS["folder"],
    compound="left",
    command=open_folder,
    height=48,
    font=ctk.CTkFont(size=13),
    fg_color="#151F31",
    hover_color="#1E293B",
    border_color="#2A3B58",
    border_width=1,
    corner_radius=10,
).grid(row=0, column=2, sticky="ew", padx=8)
ctk.CTkButton(
    btn_frame,
    text="Пожертвовать",
    command=open_donations,
    height=48,
    font=ctk.CTkFont(size=14, weight="bold"),
    fg_color="#16A34A",
    hover_color="#15803D",
    border_color="#22C55E",
    border_width=1,
    corner_radius=10,
).grid(row=0, column=3, sticky="ew", padx=(8, 0))

monitor_frame = ctk.CTkFrame(workspace_frame, fg_color="#151F31", border_color="#243652", border_width=1, corner_radius=12)
monitor_frame.pack(fill="x", pady=(0, 12))
monitor_frame.grid_columnconfigure(0, weight=1)
monitor_inner = ctk.CTkFrame(monitor_frame, fg_color="transparent")
monitor_inner.pack(pady=12)
ctk.CTkLabel(monitor_inner, text="", image=ICONS["monitor"]).pack(side="left", padx=(0, 8))
ctk.CTkLabel(monitor_inner, text="Монитор для распознавания:", font=ctk.CTkFont(size=14), text_color="#CBD5E1").pack(side="left", padx=(0, 8))
monitor_options = get_monitor_options()
monitor_values = [option["label"] for option in monitor_options] or ["Монитор не найден"]
monitor_selector = ctk.CTkOptionMenu(
    monitor_inner,
    values=monitor_values,
    command=monitor_change,
    width=300,
    height=34,
    font=ctk.CTkFont(size=14),
    fg_color="#111827",
    button_color="#17233A",
    button_hover_color="#1E3A8A",
    dropdown_fg_color="#111827",
    dropdown_hover_color="#1E3A8A",
    corner_radius=9,
)
monitor_selector.set(monitor_label_for_index(MONITOR_INDEX) if monitor_options else "Монитор не найден")
monitor_selector.pack(side="left", padx=(0, 8))
ctk.CTkButton(
    monitor_inner,
    text="Обновить",
    command=refresh_monitors,
    width=88,
    height=34,
    font=ctk.CTkFont(size=13),
    fg_color="#151F31",
    hover_color="#1E293B",
    border_color="#2A3B58",
    border_width=1,
    corner_radius=9,
).pack(side="left")
monitor_info_label = ctk.CTkLabel(monitor_frame, text="", font=ctk.CTkFont(size=14), text_color="#93A4BF")
monitor_info_label.pack(pady=(0, 16))

region_frame = ctk.CTkFrame(workspace_frame, fg_color="transparent")
region_frame.pack(fill="x", pady=(0, 12))
region_frame.grid_columnconfigure((0, 1), weight=1, uniform="region_buttons")
ctk.CTkButton(
    region_frame,
    text="Выбрать область",
    image=ICONS["scan"],
    compound="left",
    command=select_region,
    height=50,
    font=ctk.CTkFont(size=13),
    fg_color="#151F31",
    hover_color="#1E293B",
    border_color="#2A3B58",
    border_width=1,
    corner_radius=10,
).grid(row=0, column=0, sticky="ew", padx=(0, 8))
ctk.CTkButton(
    region_frame,
    text="Область по умолчанию",
    image=ICONS["scan"],
    compound="left",
    command=reset_region,
    height=50,
    font=ctk.CTkFont(size=13),
    fg_color="#151F31",
    hover_color="#1E293B",
    border_color="#2A3B58",
    border_width=1,
    corner_radius=10,
).grid(row=0, column=1, sticky="ew", padx=(12, 0))

region_panel = ctk.CTkFrame(workspace_frame, fg_color="#151F31", border_color="#243652", border_width=1, corner_radius=12)
region_panel.pack(fill="x")
region_label = ctk.CTkLabel(
    region_panel,
    text="Область: по умолчанию",
    font=ctk.CTkFont(size=14),
    text_color="#93A4BF",
    anchor="w",
)
region_label.pack(fill="x", padx=34, pady=12)
update_monitor(MONITOR_INDEX)

settings_card = ctk.CTkFrame(settings_tab, fg_color="#111C2F", border_color="#20304A", border_width=1, corner_radius=16)
settings_card.pack(fill="both", expand=True, padx=4, pady=(18, 8))

settings_header = ctk.CTkFrame(settings_card, fg_color="transparent")
settings_header.pack(fill="x", padx=22, pady=(20, 12))
settings_icon = ctk.CTkFrame(settings_header, width=46, height=46, fg_color="#102A5C", border_color="#2563EB", border_width=2, corner_radius=18)
settings_icon.pack(side="left", padx=(0, 8))
settings_icon.pack_propagate(False)
ctk.CTkLabel(settings_icon, text="", image=ICONS["settings"]).pack(expand=True)
settings_title = ctk.CTkFrame(settings_header, fg_color="transparent")
settings_title.pack(side="left", fill="x", expand=True)
ctk.CTkLabel(
    settings_title,
    text="Настройки",
    font=ctk.CTkFont(size=24, weight="bold"),
    text_color="#F8FAFC",
).pack(anchor="w")
ctk.CTkLabel(
    settings_title,
    text="Фразы-триггеры, папки, расписание дня/ночи и путь сохранения",
    font=ctk.CTkFont(size=13),
    text_color="#AAB4C0",
).pack(anchor="w", pady=(4, 0))

settings_divider = ctk.CTkFrame(settings_card, height=1, fg_color="#21324B")
settings_divider.pack(fill="x")

settings_body = ctk.CTkFrame(settings_card, fg_color="transparent")
settings_body.pack(fill="both", expand=True, padx=28, pady=18)

triggers_card = ctk.CTkFrame(settings_body, fg_color="#151F31", border_color="#243652", border_width=1, corner_radius=14)
triggers_card.pack(fill="both", expand=True, pady=(0, 14))
triggers_head = ctk.CTkFrame(triggers_card, fg_color="transparent")
triggers_head.pack(fill="x", padx=18, pady=(14, 8))
ctk.CTkLabel(
    triggers_head,
    text="Фразы-триггеры и папки",
    font=ctk.CTkFont(size=16, weight="bold"),
    text_color="#F8FAFC",
).pack(side="left")
ctk.CTkButton(
    triggers_head,
    text="Сохранить триггеры",
    command=lambda: save_triggers(),
    height=34,
    width=155,
    font=ctk.CTkFont(size=13, weight="bold"),
    fg_color="#2563EB",
    hover_color="#1D4ED8",
    corner_radius=9,
).pack(side="right")

columns_frame = ctk.CTkFrame(triggers_card, fg_color="transparent")
columns_frame.pack(fill="x", padx=18, pady=(0, 4))
ctk.CTkLabel(columns_frame, text="Фраза", width=270, anchor="w", text_color="#93A4BF").grid(row=0, column=0, padx=(0, 8), sticky="w")
ctk.CTkLabel(columns_frame, text="Папка", width=220, anchor="w", text_color="#93A4BF").grid(row=0, column=1, sticky="w")

triggers_frame = ctk.CTkScrollableFrame(
    triggers_card,
    fg_color="#111827",
    scrollbar_button_color="#334155",
    scrollbar_button_hover_color="#475569",
    corner_radius=12,
)
triggers_frame.pack(fill="both", expand=True, padx=18, pady=(0, 16))

entries = []
def populate_triggers():
    for widget in triggers_frame.winfo_children():
        widget.destroy()
    entries.clear()
    for i, (key, val) in enumerate(config['triggers'].items()):
        entry1 = ctk.CTkEntry(
            triggers_frame,
            width=270,
            height=32,
            fg_color="#0F172A",
            border_color="#334155",
            text_color="#E5E7EB",
        )
        entry1.insert(0, key)
        entry1.grid(row=i, column=0, padx=(0, 8), pady=4, sticky="w")
        entry2 = ctk.CTkEntry(
            triggers_frame,
            width=220,
            height=32,
            fg_color="#0F172A",
            border_color="#334155",
            text_color="#E5E7EB",
        )
        entry2.insert(0, val)
        entry2.grid(row=i, column=1, padx=(0, 0), pady=4, sticky="w")
        entries.append((entry1, entry2))

def save_triggers():
    config['triggers'] = {e1.get(): e2.get() for e1, e2 in entries if e1.get().strip() and e2.get().strip()}
    save_config(config)
    populate_triggers()
populate_triggers()

bottom_settings = ctk.CTkFrame(settings_body, fg_color="transparent")
bottom_settings.pack(fill="x")
bottom_settings.grid_columnconfigure((0, 1), weight=1, uniform="settings_bottom")

time_frame = ctk.CTkFrame(bottom_settings, fg_color="#151F31", border_color="#243652", border_width=1, corner_radius=14)
time_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
ctk.CTkLabel(
    time_frame,
    text="Время смен",
    font=ctk.CTkFont(size=15, weight="bold"),
    text_color="#F8FAFC",
).grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 8), sticky="w")
ctk.CTkLabel(time_frame, text="Начало дня (HH:MM)", text_color="#CBD5E1").grid(row=1, column=0, padx=16, pady=5, sticky="w")
day_start_entry = ctk.CTkEntry(time_frame, width=88, height=32, fg_color="#0F172A", border_color="#334155")
day_start_entry.insert(0, config['day_start'])
day_start_entry.grid(row=1, column=1, padx=16, pady=5, sticky="e")

ctk.CTkLabel(time_frame, text="Начало ночи (HH:MM)", text_color="#CBD5E1").grid(row=2, column=0, padx=16, pady=5, sticky="w")
night_start_entry = ctk.CTkEntry(time_frame, width=88, height=32, fg_color="#0F172A", border_color="#334155")
night_start_entry.insert(0, config['night_start'])
night_start_entry.grid(row=2, column=1, padx=16, pady=5, sticky="e")

def save_times():
    config['day_start'] = day_start_entry.get()
    config['night_start'] = night_start_entry.get()
    save_config(config)
    status_label.configure(text="Время и путь сохранены")

ctk.CTkButton(
    time_frame,
    text="Сохранить время",
    command=save_times,
    height=34,
    font=ctk.CTkFont(size=13, weight="bold"),
    fg_color="#2563EB",
    hover_color="#1D4ED8",
    corner_radius=9,
).grid(row=3, column=0, columnspan=2, padx=16, pady=(10, 16), sticky="ew")

def choose_folder():
    folder = filedialog.askdirectory()
    if folder:
        config['save_path'] = folder
        folder_label.configure(text=folder)

updates_frame = ctk.CTkFrame(settings_body, fg_color="#151F31", border_color="#243652", border_width=1, corner_radius=14)
updates_frame.pack(fill="x", pady=(14, 0))
ctk.CTkLabel(
    updates_frame,
    text="Обновления",
    font=ctk.CTkFont(size=15, weight="bold"),
    text_color="#F8FAFC",
).pack(side="left", padx=16, pady=14)
ctk.CTkLabel(
    updates_frame,
    text=f"Текущая версия: v{APP_VERSION}",
    font=ctk.CTkFont(size=13),
    text_color="#AAB4C0",
).pack(side="left", padx=(0, 14), pady=14)
ctk.CTkButton(
    updates_frame,
    text="Проверить",
    command=lambda: check_for_updates(show_current=True),
    height=34,
    width=120,
    font=ctk.CTkFont(size=13, weight="bold"),
    fg_color="#2563EB",
    hover_color="#1D4ED8",
    corner_radius=9,
).pack(side="right", padx=16, pady=12)

target_frame = ctk.CTkFrame(bottom_settings, fg_color="#151F31", border_color="#243652", border_width=1, corner_radius=14)
target_frame.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
ctk.CTkLabel(
    target_frame,
    text="Папка сохранения",
    font=ctk.CTkFont(size=15, weight="bold"),
    text_color="#F8FAFC",
).pack(anchor="w", padx=16, pady=(14, 8))
folder_label = ctk.CTkLabel(
    target_frame,
    text=config['save_path'],
    font=ctk.CTkFont(size=13),
    text_color="#AAB4C0",
    fg_color="#0F172A",
    corner_radius=9,
    anchor="w",
)
folder_label.pack(fill="x", padx=16, pady=(0, 10), ipady=7)
ctk.CTkButton(
    target_frame,
    text="Выбрать папку",
    image=ICONS["folder"],
    compound="left",
    command=choose_folder,
    height=34,
    font=ctk.CTkFont(size=13, weight="bold"),
    fg_color="#2563EB",
    hover_color="#1D4ED8",
    corner_radius=9,
).pack(fill="x", padx=16, pady=(0, 16))

def show_disclaimer_once():
    if config.get("disclaimer_shown"):
        return

    dialog = ctk.CTkToplevel(app)
    dialog.title("Дисклеймер")
    dialog.configure(fg_color="#0B1220")
    dialog.resizable(False, False)
    dialog.transient(app)
    dialog.grab_set()

    card = ctk.CTkFrame(dialog, fg_color="#111C2F", border_color="#20304A", border_width=1, corner_radius=16)
    card.pack(fill="both", expand=True, padx=18, pady=18)

    ctk.CTkLabel(
        card,
        text="Дисклеймер",
        font=ctk.CTkFont(size=20, weight="bold"),
        text_color="#F8FAFC",
    ).pack(anchor="w", padx=20, pady=(18, 8))
    ctk.CTkLabel(
        card,
        text=DISCLAIMER_TEXT,
        font=ctk.CTkFont(size=14),
        text_color="#CBD5E1",
        justify="left",
        wraplength=520,
    ).pack(fill="x", padx=20, pady=(0, 18))

    def acknowledge():
        config["disclaimer_shown"] = True
        save_config(config)
        dialog.destroy()

    ctk.CTkButton(
        card,
        text="Понятно",
        command=acknowledge,
        height=36,
        font=ctk.CTkFont(size=14, weight="bold"),
        fg_color="#2563EB",
        hover_color="#1D4ED8",
        corner_radius=9,
    ).pack(fill="x", padx=20, pady=(0, 18))

    dialog.protocol("WM_DELETE_WINDOW", acknowledge)
    dialog.update_idletasks()
    x = app.winfo_x() + max(20, (app.winfo_width() - dialog.winfo_width()) // 2)
    y = app.winfo_y() + max(20, (app.winfo_height() - dialog.winfo_height()) // 2)
    dialog.geometry(f"+{x}+{y}")

if __name__ == "__main__":
    pass
show_page("logger")
refresh_msk_clock()
app.after(250, show_disclaimer_once)
app.after(1500, check_for_updates)
app.mainloop()




