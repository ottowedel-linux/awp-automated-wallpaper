#!/usr/bin/env python3
import configparser
import json
import os
import sys
import time
import random
import subprocess
from pathlib import Path
from datetime import datetime

AWP_DIR = os.path.expanduser("~/awp")
CONFIG_PATH = os.path.join(AWP_DIR, "awp_config.ini")
STATE_PATH = os.path.join(AWP_DIR, "indexes.json")
# CONKY INTEGRATION: Path for the Conky state file
CONKY_STATE_PATH = os.path.expanduser('~/awp/conky/.awp_conky_state.txt')
DE = None
SESSION_TYPE = None
BLANKING_PAUSE = False
BLANKING_TIMEOUT = 0  # ← Will be loaded from INI
BLANKING_FORMATTED = "off"  # ← NEW: Human-readable for Conky

# ---------- backend XFCE ----------
SCALING_XFCE = {'centered': 1, 'scaled': 4, 'zoomed': 5}

def xfce_force_single_workspace_off():
    subprocess.run([
        "xfconf-query", "-c", "xfce4-desktop",
        "-p", "/backdrop/single-workspace-mode",
        "--set", "false"
    ])

def xfce_configure_screen_blanking(timeout_seconds):
    """
    Configure screen blanking for XFCE/X11 sessions.
    timeout_seconds: Time in seconds before screen blanks (0 = disable).
    """
    if timeout_seconds == 0:
        # Explicitly disable all blanking
        subprocess.run(["xset", "s", "off"], check=False)
        subprocess.run(["xset", "-dpms"], check=False)
        print(f"[AWP] Screen blanking explicitly disabled")
    else:
        # Enable and configure blanking
        subprocess.run(["xset", "s", str(timeout_seconds)], check=False)
        subprocess.run(["xset", "+dpms"], check=False)
        subprocess.run(["xset", "dpms", str(timeout_seconds), str(timeout_seconds), str(timeout_seconds)], check=False)
        print(f"[AWP] Screen blanking set to {timeout_seconds}s")

def xfce_get_monitors_for_workspace(ws_num):
    props = subprocess.check_output(
        ["xfconf-query", "-c", "xfce4-desktop", "-l"], text=True
    ).splitlines()
    monitors = []
    for p in props:
        if f"/workspace{ws_num}/last-image" in p:
            parts = p.split("/")
            if len(parts) >= 6 and parts[3].startswith("monitor"):
                monitors.append(parts[3])
    return sorted(set(monitors))

def xfce_set_wallpaper(ws_num, image_path, scaling):
    style_code = SCALING_XFCE.get(scaling, 5)
    for mon in xfce_get_monitors_for_workspace(ws_num):
        subprocess.run([
            "xfconf-query",
            "--channel", "xfce4-desktop",
            "--property", f"/backdrop/screen0/{mon}/workspace{ws_num}/last-image",
            "--set", image_path
        ])
        subprocess.run([
            "xfconf-query",
            "--channel", "xfce4-desktop",
            "--property", f"/backdrop/screen0/{mon}/workspace{ws_num}/image-style",
            "--set", str(style_code)
        ])
    subprocess.run(["xfdesktop", "--reload"])

def xfce_set_icon(icon_path):
    """
    Sets the Whisker Menu icon for XFCE by editing the config file and restarting the panel.
    """
    config_file = os.path.expanduser("~/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml")
    
    escaped_icon_path = icon_path.replace("/", "\\/")
    
    sed_command = (
        rf"sed -i '/<property name=\"plugin-1\" type=\"string\" value=\"whiskermenu\">/!b;n;c\\ \ \ \ \ \ \ \ \ <property name=\"button-icon\" type=\"string\" value=\"{escaped_icon_path}\"/>' {config_file}"
    )
    
    try:
        subprocess.run(sed_command, shell=True, check=True)
        subprocess.run(["killall", "xfconfd"], check=False)
        subprocess.run(["xfce4-panel", "-r"], check=True)
        print(f"Set XFCE icon to: {icon_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error setting XFCE icon: {e}")
        
def xfce_set_themes(ws_num, config):
    """
    Sets XFCE theme parameters by reading from config INI.
    ws_num is 0-based (0 for ws1, etc.).
    """
    section = f"ws{ws_num + 1}"
    
    if not config.has_section(section):
        print(f"No theme config found for {section}")
        return
    
    # Get theme settings with fallbacks
    icon_theme = config.get(section, 'icon_theme', fallback=None)
    gtk_theme = config.get(section, 'gtk_theme', fallback=None)
    cursor_theme = config.get(section, 'cursor_theme', fallback=None)
    wm_theme = config.get(section, 'wm_theme', fallback=None)
    
    # Apply themes if they exist in config
    if icon_theme:
        subprocess.run(["xfconf-query", "-c", "xsettings", "-p", "/Net/IconThemeName", "--set", icon_theme])
        print(f"✓ XFCE icon theme: {icon_theme}")
    
    if gtk_theme:
        subprocess.run(["xfconf-query", "-c", "xsettings", "-p", "/Net/ThemeName", "--set", gtk_theme])
        print(f"✓ XFCE GTK theme: {gtk_theme}")
    
    if cursor_theme:
        subprocess.run(["xfconf-query", "-c", "xsettings", "-p", "/Gtk/CursorThemeName", "--set", cursor_theme])
        print(f"✓ XFCE cursor theme: {cursor_theme}")
    
    if wm_theme:
        subprocess.run(["xfconf-query", "-c", "xfwm4", "-p", "/general/theme", "--set", wm_theme])
        print(f"✓ XFCE window theme: {wm_theme}")
    
    print(f"Applied XFCE themes for workspace {ws_num + 1}")


# ---------- backend GNOME ----------
SCALING_GNOME = {'centered': 'centered', 'scaled': 'scaled', 'zoomed': 'zoom'}

def gnome_force_single_workspace_off():
    pass

def gnome_set_wallpaper(ws_num, image_path, scaling):
    uri = f"file://{image_path}"
    style_val = SCALING_GNOME.get(scaling, 'zoom')
    subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri])
    subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri])
    subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-options", style_val])

def gnome_set_themes(ws_num, config):  # ← Add config parameter
    """GNOME theme setting"""
    section = f"ws{ws_num + 1}"
    if not config.has_section(section):
        return
    
    icon_theme = config.get(section, 'icon_theme', fallback=None)
    gtk_theme = config.get(section, 'gtk_theme', fallback=None)
    cursor_theme = config.get(section, 'cursor_theme', fallback=None)
    
    if icon_theme:
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", icon_theme])
        print(f"✓ GNOME icon theme: {icon_theme}")
    if gtk_theme:
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", gtk_theme])
        print(f"✓ GNOME GTK theme: {gtk_theme}")
    if cursor_theme:
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "cursor-theme", cursor_theme])
        print(f"✓ GNOME cursor theme: {cursor_theme}")

# ---------- backend Cinnamon ----------
SCALING_CINNAMON = {'centered': 'centered', 'scaled': 'scaled', 'zoomed': 'zoom'}

def cinnamon_force_single_workspace_off():
    pass

def cinnamon_set_wallpaper(ws_num, image_path, scaling):
    uri = f"file://{image_path}"
    style_val = SCALING_CINNAMON.get(scaling, 'zoom')
    subprocess.run(["gsettings", "set", "org.cinnamon.desktop.background", "picture-uri", uri])
    subprocess.run(["gsettings", "set", "org.cinnamon.desktop.background", "picture-options", style_val])

def cinnamon_set_icon(icon_path):
    """
    Sets the Cinnamon Menu icon by editing the menu JSON spice file directly.
    icon_path: Full path to the icon image.
    """
    import json
    config_file = os.path.expanduser("~/.config/cinnamon/spices/menu@cinnamon.org/0.json")
    
    try:
        # Load the JSON
        with open(config_file, "r") as f:
            data = json.load(f)
        
        # Set the menu icon value
        data["menu-icon"]["value"] = icon_path
        
        # Write it back
        with open(config_file, "w") as f:
            json.dump(data, f, indent=4)
        
        # Notify user
        print(f"Set Cinnamon menu icon to: {icon_path}")
        
        # Optional: reload the spice (works in most Cinnamon versions)
        #subprocess.run(["cinnamon-spice-tool", "reload", "menu@cinnamon.org"], check=False)
        
    except Exception as e:
        print(f"Error setting Cinnamon menu icon: {e}")

def cinnamon_set_themes(ws_num, config):
    """
    Sets Cinnamon theme parameters by reading from config INI.
    ws_num is 0-based (0 for ws1, etc.).
    """
    section = f"ws{ws_num + 1}"
    
    if not config.has_section(section):
        print(f"No theme config found for {section}")
        return
    
    # Get theme settings with fallbacks
    icon_theme = config.get(section, 'icon_theme', fallback=None)
    gtk_theme = config.get(section, 'gtk_theme', fallback=None)
    cursor_theme = config.get(section, 'cursor_theme', fallback=None)
    desktop_theme = config.get(section, 'desktop_theme', fallback=None)
    wm_theme = config.get(section, 'wm_theme', fallback=None)
    
    # Apply themes if they exist in config
    if icon_theme:
        subprocess.run(["gsettings", "set", "org.cinnamon.desktop.interface", "icon-theme", icon_theme])
        print(f"✓ Cinnamon icon theme: {icon_theme}")
    
    if gtk_theme:
        subprocess.run(["gsettings", "set", "org.cinnamon.desktop.interface", "gtk-theme", gtk_theme])
        print(f"✓ Cinnamon GTK theme: {gtk_theme}")
    
    if cursor_theme:
        subprocess.run(["gsettings", "set", "org.cinnamon.desktop.interface", "cursor-theme", cursor_theme])
        print(f"✓ Cinnamon cursor theme: {cursor_theme}")
    
    if desktop_theme:
        subprocess.run(["gsettings", "set", "org.cinnamon.theme", "name", desktop_theme])
        print(f"✓ Cinnamon desktop theme: {desktop_theme}")
    
    if wm_theme:
        subprocess.run(["gsettings", "set", "org.cinnamon.desktop.wm.preferences", "theme", wm_theme])
        print(f"✓ Cinnamon window theme: {wm_theme}")
    
    print(f"Applied Cinnamon themes for workspace {ws_num + 1}")

# ---------- backend MATE ----------
SCALING_MATE = {'centered': 'centered', 'scaled': 'scaled', 'zoomed': 'zoom'}

def mate_force_single_workspace_off():
    pass

def mate_set_wallpaper(ws_num, image_path, scaling):
    style_val = SCALING_MATE.get(scaling, 'zoom')
    subprocess.run(["gsettings", "set", "org.mate.background", "picture-filename", image_path])
    subprocess.run(["gsettings", "set", "org.mate.background", "picture-options", style_val])

def mate_set_themes(ws_num, config):
    """MATE theme setting"""
    section = f"ws{ws_num + 1}"
    if not config.has_section(section):
        return
    
    icon_theme = config.get(section, 'icon_theme', fallback=None)
    gtk_theme = config.get(section, 'gtk_theme', fallback=None)
    cursor_theme = config.get(section, 'cursor_theme', fallback=None)
    wm_theme = config.get(section, 'wm_theme', fallback=None)
    
    if icon_theme:
        subprocess.run(["gsettings", "set", "org.mate.interface", "icon-theme", icon_theme])
    if gtk_theme:
        subprocess.run(["gsettings", "set", "org.mate.interface", "gtk-theme", gtk_theme])
    if cursor_theme:
        subprocess.run(["gsettings", "set", "org.mate.peripherals-mouse", "cursor-theme", cursor_theme])
    if wm_theme:
        subprocess.run(["gsettings", "set", "org.mate.Marco.general", "theme", wm_theme])

# ---------- backend Openbox (feh) ----------
def openbox_force_single_workspace_off():
    # Openbox doesn't have this concept, so we can pass.
    pass

def openbox_set_wallpaper(ws_num, image_path, scaling):
    # 'feh' is not aware of workspaces in the same way,
    # so we set the wallpaper for all of them.
    scaling_options = {
        'centered': '--bg-center',
        'scaled': '--bg-scale',
        'zoomed': '--bg-fill'
    }
    
    style_val = scaling_options.get(scaling, '--bg-fill')
    
    # We use the subprocess to run feh in a separate process.
    subprocess.run(["feh", style_val, image_path])

def openbox_set_themes(ws_num, config):
    """Generic/Openbox theme setting - limited support"""
    section = f"ws{ws_num + 1}"
    if not config.has_section(section):
        return
    
    # Generic WMs typically only support basic GTK themes
    gtk_theme = config.get(section, 'gtk_theme', fallback=None)
    if gtk_theme:
        # This would set GTK theme for applications but not window manager
        print(f"Note: Generic WM - GTK theme would be: {gtk_theme}")
        # Could use gsettings for GTK apps: subprocess.run(["gsettings", "set", "org.gtk.Settings.FileChooser", "theme", gtk_theme])


# ---------- Backend Function Mapping ----------
backend_funcs = {
    "xfce": {
        "wallpaper": xfce_set_wallpaper,
        "icon": xfce_set_icon,
        "themes": xfce_set_themes,
        "workspace_off": xfce_force_single_workspace_off
    },
    "cinnamon": {
        "wallpaper": cinnamon_set_wallpaper,
        "icon": cinnamon_set_icon, 
        "themes": cinnamon_set_themes,
        "workspace_off": cinnamon_force_single_workspace_off
    },
    "gnome": {
        "wallpaper": gnome_set_wallpaper,
        "icon": None,  # Not implemented yet
        "themes": gnome_set_themes,
        "workspace_off": gnome_force_single_workspace_off
    },
    "mate": {
        "wallpaper": mate_set_wallpaper,
        "icon": None,  # Not implemented yet
        "themes": mate_set_themes,
        "workspace_off": mate_force_single_workspace_off
    },
    "generic": {
        "wallpaper": openbox_set_wallpaper,
        "icon": None,  # Not implemented yet
        "themes": openbox_set_themes,
        "workspace_off": openbox_force_single_workspace_off
    }
}


# ---------- Simplified Universal Functions ----------
def force_single_workspace_off():
    func = backend_funcs.get(DE, {}).get("workspace_off")
    if func:
        func()

def set_wallpaper(ws_num, image_path, scaling):
    func = backend_funcs.get(DE, {}).get("wallpaper")
    if func:
        func(ws_num, image_path, scaling)

def set_panel_icon(icon_path):
    func = backend_funcs.get(DE, {}).get("icon")
    if func:
        func(icon_path)

def set_themes(ws_num, config):
    func = backend_funcs.get(DE, {}).get("themes")
    if func:
        func(ws_num, config)

# Keep screen blanking separate since it's XFCE-specific
def configure_screen_blanking():
    """
    Configure screen blanking based on detected DE/session type.
    Only XFCE on X11 supports this currently.
    """
    if (SESSION_TYPE == "x11" and 
        DE == "xfce" and 
        not BLANKING_PAUSE and 
        BLANKING_TIMEOUT > 0):
        xfce_configure_screen_blanking(BLANKING_TIMEOUT)
    elif SESSION_TYPE == "x11" and DE == "xfce":
        print(f"[AWP] Screen blanking disabled (paused={BLANKING_PAUSE}, timeout={BLANKING_TIMEOUT}s)")
        xfce_configure_screen_blanking(0)

# ---------- CONKY INTEGRATION ----------
def update_conky_state(workspace_name, wallpaper_path):
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    icon_path = config.get(workspace_name, 'icon', fallback='')
    color_hex = config.get(workspace_name, 'icon_color', fallback='#109daf')
    intv_val = config.get(workspace_name, 'timing', fallback='10s')
    flow_val = config.get(workspace_name, 'mode', fallback='random')
    sort_val = config.get(workspace_name, 'order', fallback='n')
    view_val = config.get(workspace_name, 'scaling', fallback='scaled')
    with open(CONKY_STATE_PATH, 'w') as f:
        f.write(f"wallpaper_path={wallpaper_path}\n")
        f.write(f"workspace_name={workspace_name}\n")
        f.write(f"logo_path={icon_path}\n")
        f.write(f"icon_color={color_hex}\n")
        f.write(f"intv={intv_val}\n")
        f.write(f"flow={flow_val}\n")
        f.write(f"sort={sort_val}\n")
        f.write(f"view={view_val}\n")
        f.write(f"blanking_timeout={BLANKING_FORMATTED}\n")  # ← SUPER CLEAN: Just write global
        f.write(f"blanking_paused={str(BLANKING_PAUSE)}\n")  # ← Also use global

# ---------- helpers ----------
def parse_timing(timing_str):
    units = {'s': 1, 'm': 60, 'h': 3600}
    try:
        unit = timing_str[-1].lower()
        number = int(timing_str[:-1])
        return number * units.get(unit, 60)
    except Exception:
        return None

def get_current_workspace():
    ws_num = subprocess.check_output(
        ["xprop", "-root", "_NET_CURRENT_DESKTOP"], text=True
    ).strip().split()[-1]
    return int(ws_num)

def ensure_awp_dir():
    if not os.path.isdir(AWP_DIR):
        os.makedirs(AWP_DIR, exist_ok=True)

def load_state():
    if not os.path.isfile(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_PATH)

def get_ws_key(ws_num):
    return f"ws{ws_num+1}"

def load_config():
    global DE, SESSION_TYPE, BLANKING_PAUSE, BLANKING_TIMEOUT, BLANKING_FORMATTED  # ← FIXED: Added BLANKING_FORMATTED
    config = configparser.ConfigParser()
    if not os.path.isfile(CONFIG_PATH):
        print(f"Config file {CONFIG_PATH} not found. Run awp_setup.py first.")
        sys.exit(1)
    config.read(CONFIG_PATH)
    
    # Load DE from config, with fallback to runtime detection
    valid_des = ["xfce", "gnome", "cinnamon", "mate", "generic"]
    DE = config.get('general', 'os_detected', fallback="unknown")
    if DE not in valid_des:
        print(f"Warning: Invalid or missing os_detected in config, falling back to runtime detection.")
        de = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        DE = next((de_type for de_type in valid_des if de_type in de), "unknown")
    
    # Load SESSION_TYPE from config
    SESSION_TYPE = config.get('general', 'session_type', fallback='x11')
    
    # Load BLANKING SETTINGS - load from INI
    BLANKING_PAUSE = config.getboolean('general', 'blanking_pause', fallback=False)
    timeout_str = config.get('general', 'blanking_timeout', fallback='0')
    BLANKING_TIMEOUT = int(timeout_str) if timeout_str.isdigit() else 0
    
    # Calculate formatted blanking info ONCE at startup
    if BLANKING_TIMEOUT == 0 or BLANKING_PAUSE:
        BLANKING_FORMATTED = "off"
    else:
        timeout_sec = BLANKING_TIMEOUT
        if timeout_sec < 60:
            BLANKING_FORMATTED = f"{timeout_sec}s"
        elif timeout_sec < 3600:
            BLANKING_FORMATTED = f"{timeout_sec//60}m"
        else:
            hours = timeout_sec // 3600
            minutes = (timeout_sec % 3600) // 60
            BLANKING_FORMATTED = f"{hours}h{minutes}m" if minutes > 0 else f"{hours}h"
        print(f"[AWP] Blanking formatted: {BLANKING_FORMATTED}")  # ← DEBUG: Confirm it works
    
    return config

def load_images(folder_path):
    p = Path(folder_path)
    if not p.is_dir():
        return []
    return list(p.glob("*.[jJ][pP][gG]")) + list(p.glob("*.[pP][nN][gG]"))

def sort_images(images, order_key):
    if order_key == 'name_az':
        return sorted(images, key=lambda f: f.name.lower())
    elif order_key == 'name_za':
        return sorted(images, key=lambda f: f.name.lower(), reverse=True)
    elif order_key == 'name_new':
        return sorted(images, key=lambda f: f.stat().st_mtime, reverse=True)
    elif order_key == 'name_old':
        return sorted(images, key=lambda f: f.stat().st_mtime)
    return images

# ---------- workspace model ----------
class Workspace:
    def __init__(self, num, section):
        self.num = num
        self.key = get_ws_key(num)
        self.folder = section.get('folder')
        self.timing_str = section.get('timing', '1m')
        self.timing = parse_timing(self.timing_str) or 60
        self.mode = section.get('mode', 'random')
        self.order = section.get('order', 'name_az')
        self.scaling = section.get('scaling', 'scaled')
        self.images = []
        self.index = 0
        self.next_switch_time = time.time() + self.timing
        self.reload_images_and_index()

    def reload_images_and_index(self):
        # Reload all config fields
        config = configparser.ConfigParser()
        config.read(CONFIG_PATH)
        section = f"ws{self.num+1}"
        if section in config:
            self.folder = config[section].get('folder', self.folder)
            self.timing_str = config[section].get('timing', '1m')
            self.timing = parse_timing(self.timing_str) or 60
            self.mode = config[section].get('mode', 'random')
            self.order = config[section].get('order', 'name_az')
            self.scaling = config[section].get('scaling', 'scaled')

        # Reload images and index
        self.images = load_images(self.folder)
        if self.mode == 'sequential':
            self.images = sort_images(self.images, self.order)
        else:
            self.images = sort_images(self.images, 'name_az')

        state = load_state()
        self.index = int(state.get(self.key, 0) or 0)
        if not self.images or self.index >= len(self.images):
            self.index = 0

    def pick_next_index(self):
        if not self.images:
            return 0
        if self.mode == 'random':
            if len(self.images) == 1:
                return 0
            new_idx = self.index
            while new_idx == self.index:
                new_idx = random.randint(0, len(self.images)-1)
            return new_idx
        return (self.index + 1) % len(self.images)

    def apply_index(self, new_index):
        state = load_state()
        self.index = new_index
        state[self.key] = self.index
        save_state(state)

        current_wallpaper_path = str(self.images[self.index])
        set_wallpaper(self.num, current_wallpaper_path, self.scaling)
        update_conky_state(f"ws{self.num+1}", current_wallpaper_path)

# ---------- main loop ----------
def main_loop(workspaces):
    last_ws = None
    while True:
        now = time.time()
        ws_num = get_current_workspace()
        ws = workspaces.get(ws_num)
        if not ws:
            time.sleep(0.5)
            continue

        force_single_workspace_off()

        if ws_num != last_ws:
            ws.reload_images_and_index()
            ws.apply_index(ws.index)
            ws.next_switch_time = now + ws.timing
            
            config = load_config()
            ws_key = get_ws_key(ws_num)
            if ws_key in config:
                icon_path = config[ws_key].get('icon', '')
                if icon_path:
                    # Call the new universal function
                    set_panel_icon(icon_path)
            
            # Apply theme changes on workspace switch
            set_themes(ws_num, config)
            
            last_ws = ws_num

        if now >= ws.next_switch_time:
            ws.reload_images_and_index()
            if ws.images:
                new_idx = ws.pick_next_index()
                ws.apply_index(new_idx)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] WS{ws.num+1}: index -> {ws.index}")
            ws.next_switch_time = now + ws.timing

        time.sleep(0.5)

def main():
    ensure_awp_dir()
    
    config = load_config()

    # ← UPDATED: Configure screen blanking - now uses INI values
    configure_screen_blanking()
    
    force_single_workspace_off()
    
    try:
        n_ws = int(config['general']['workspaces'])
    except Exception:
        print("Invalid [general]::workspaces in config.")
        sys.exit(1)

    workspaces = {}
    for i in range(1, n_ws+1):
        sec = f"ws{i}"
        if sec not in config:
            print(f"Warning: missing section [{sec}] in config, skipping.")
            continue
        ws = Workspace(i-1, config[sec])
        workspaces[ws.num] = ws

    print(f"Loaded {len(workspaces)} workspaces. State: {STATE_PATH}")
    main_loop(workspaces)

if __name__ == "__main__":
    main()
