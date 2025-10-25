#!/usr/bin/env python3
"""
AWP - Automated Wallpaper Program
Navigation Controller (awp_nav.py)

Provides manual wallpaper navigation with three commands:
  - next: Switch to next wallpaper
  - prev: Switch to previous wallpaper  
  - delete: Delete current wallpaper and advance to next

Can be bound to keyboard shortcuts for quick wallpaper control.
Part of the AWP wallpaper automation system.
"""
import configparser
import os
import sys
import random
import json
import subprocess
from pathlib import Path
import logging

try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from PyQt5.QtCore import Qt
    HAS_QT = True
except ImportError:
    HAS_QT = False

# =============================================================================
# CONFIGURATION
# =============================================================================

# Minimal logging for errors
logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")

# =============================================================================
# PATHS AND CONSTANTS
# =============================================================================
AWP_DIR = os.path.expanduser("~/awp")
CONFIG_PATH = os.path.join(AWP_DIR, "awp_config.ini")
STATE_PATH = os.path.join(AWP_DIR, "indexes.json")

# =============================================================================
# CONKY INTEGRATION (OPTIONAL)
# 
# To enable Conky integration:
# 1. Uncomment the update_conky_state() call in the apply_index() method below
# 2. Ensure the CONKY_STATE_PATH below matches your Conky configuration
# 3. Your Conky/Lua script can read from this file for real-time wallpaper info
#
# AVAILABLE VARIABLES for your Conky/Lua script:
# - wallpaper_path: Current wallpaper image path
# - workspace_name: Current workspace (e.g., 'ws1')  
# - logo_path: Workspace icon path
# - icon_color: Dominant color from workspace icon (hex)
# - intv: Wallpaper rotation interval (e.g., '5m', '30s')
# - flow: Rotation mode ('random' or 'sequential')
# - sort: Sort order ('name_az', 'name_za', 'name_old', 'name_new')
# - view: Scaling mode ('centered', 'scaled', 'zoomed')
# - blanking_timeout: Screen blanking timeout ('off', '30s', '5m', etc.)
# - blanking_paused: Whether blanking is paused ('True' or 'False')
#
# DEFAULT LOCATION: ~/awp/conky/.awp_conky_state.txt
# ↪ Customize CONKY_STATE_PATH below if needed
# =============================================================================
CONKY_STATE_PATH = os.path.expanduser('~/awp/conky/.awp_conky_state.txt')

DE = None

# =============================================================================
# DESKTOP ENVIRONMENT SCALING MAPPINGS
# =============================================================================
SCALING_XFCE = {'centered': 1, 'scaled': 4, 'zoomed': 5}
SCALING_GNOME = {'centered': 'zoom', 'scaled': 'scaled', 'zoomed': 'zoom'}
SCALING_CINNAMON = {'centered': 'centered', 'scaled': 'scaled', 'zoomed': 'zoom'}
SCALING_MATE = {'centered': 'centered', 'scaled': 'scaled', 'zoomed': 'zoom'}
SCALING_GENERIC = {'centered': 'center', 'scaled': 'scale', 'zoomed': 'fill'}

# =============================================================================
# XFCE BACKEND FUNCTIONS
# =============================================================================

def xfce_force_single_workspace_off():
    """Disable single workspace mode in XFCE."""
    subprocess.run([
        "xfconf-query", "-c", "xfce4-desktop",
        "-p", "/backdrop/single-workspace-mode",
        "--set", "false"
    ])

def xfce_get_monitors_for_workspace(ws_num: int):
    """Get list of monitors for specified XFCE workspace."""
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

def xfce_set_wallpaper(ws_num: int, image_path: str, scaling: str):
    """Set wallpaper for XFCE workspace with specified scaling."""
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

# =============================================================================
# GNOME BACKEND FUNCTIONS
# =============================================================================

def gnome_force_single_workspace_off():
    """GNOME doesn't have single workspace mode to disable."""
    pass

def gnome_set_wallpaper(ws_num: int, image_path: str, scaling: str):
    """Set wallpaper for GNOME with specified scaling."""
    uri = f"file://{image_path}"
    style_val = SCALING_GNOME.get(scaling, 'zoom')
    subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri])
    subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri])
    subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-options", style_val])

# =============================================================================
# CINNAMON BACKEND FUNCTIONS
# =============================================================================

def cinnamon_force_single_workspace_off():
    """Cinnamon doesn't have single workspace mode to disable."""
    pass

def cinnamon_set_wallpaper(ws_num: int, image_path: str, scaling: str):
    """Set wallpaper for Cinnamon with specified scaling."""
    uri = f"file://{image_path}"
    style_val = SCALING_CINNAMON.get(scaling, 'zoom')
    subprocess.run(["gsettings", "set", "org.cinnamon.desktop.background", "picture-uri", uri])
    subprocess.run(["gsettings", "set", "org.cinnamon.desktop.background", "picture-options", style_val])

# =============================================================================
# MATE BACKEND FUNCTIONS
# =============================================================================

def mate_force_single_workspace_off():
    """MATE doesn't have single workspace mode to disable."""
    pass

def mate_set_wallpaper(ws_num: int, image_path: str, scaling: str):
    """Set wallpaper for MATE with specified scaling."""
    style_val = SCALING_MATE.get(scaling, 'zoom')
    subprocess.run(["gsettings", "set", "org.mate.background", "picture-filename", image_path])
    subprocess.run(["gsettings", "set", "org.mate.background", "picture-options", style_val])

# =============================================================================
# GENERIC BACKEND FUNCTIONS
# =============================================================================

def generic_force_single_workspace_off():
    """Generic WMs don't have single workspace mode to disable."""
    pass

def generic_set_wallpaper(ws_num: int, image_path: str, scaling: str):
    """Set wallpaper for generic WMs using feh."""
    style_val = SCALING_GENERIC.get(scaling, 'scale')
    subprocess.run(["feh", f"--bg-{style_val}", image_path])

# =============================================================================
# UNIVERSAL DESKTOP FUNCTIONS
# =============================================================================

def force_single_workspace_off():
    """Disable single workspace mode for current desktop environment."""
    if DE == "xfce":
        xfce_force_single_workspace_off()
    elif DE == "gnome":
        gnome_force_single_workspace_off()
    elif DE == "cinnamon":
        cinnamon_force_single_workspace_off()
    elif DE == "mate":
        mate_force_single_workspace_off()
    elif DE == "generic":
        generic_force_single_workspace_off()

def set_wallpaper(ws_num: int, image_path: str, scaling: str):
    """Set wallpaper for specified workspace with given scaling."""
    if DE == "xfce":
        xfce_set_wallpaper(ws_num, image_path, scaling)
    elif DE == "gnome":
        gnome_set_wallpaper(ws_num, image_path, scaling)
    elif DE == "cinnamon":
        cinnamon_set_wallpaper(ws_num, image_path, scaling)
    elif DE == "mate":
        mate_set_wallpaper(ws_num, image_path, scaling)
    elif DE == "generic":
        generic_set_wallpaper(ws_num, image_path, scaling)

# =============================================================================
# CONKY INTEGRATION
# =============================================================================

def update_conky_state(workspace_name: str, wallpaper_path: str):
    """
    Update Conky state file with current workspace and wallpaper information.
    
    Args:
        workspace_name (str): Current workspace name (e.g., 'ws1')
        wallpaper_path (str): Path to current wallpaper image
    """
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    icon_path = config.get(workspace_name, 'icon', fallback='')
    color_hex = config.get(workspace_name, 'icon_color', fallback='#109daf')
    intv_val = config.get(workspace_name, 'timing', fallback='10s')
    flow_val = config.get(workspace_name, 'mode', fallback='random')
    sort_val = config.get(workspace_name, 'order', fallback='n')
    view_val = config.get(workspace_name, 'scaling', fallback='scaled')
    try:
        with open(CONKY_STATE_PATH, 'w') as f:
            f.write(f"wallpaper_path={wallpaper_path}\n")
            f.write(f"workspace_name={workspace_name}\n")
            f.write(f"logo_path={icon_path}\n")
            f.write(f"icon_color={color_hex}\n")
            f.write(f"intv={intv_val}\n")
            f.write(f"flow={flow_val}\n")
            f.write(f"sort={sort_val}\n")
            f.write(f"view={view_val}\n")
    except OSError as e:
        logging.error(f"Failed to write Conky state file {CONKY_STATE_PATH}: {e}")

# =============================================================================
# WALLPAPER DELETION FUNCTIONALITY
# =============================================================================

def universal_confirm_deletion(wallpaper_name: str) -> bool:
    """
    Display confirmation dialog for wallpaper deletion.
    
    Args:
        wallpaper_name (str): Path to wallpaper file for deletion
        
    Returns:
        bool: True if user confirms deletion, False otherwise
    """
    if HAS_QT:
        try:
            # Create app instance if needed
            app = QApplication.instance()
            if app is None:
                app = QApplication([])
            
            # Create and show confirmation dialog
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Question)
            msg.setWindowTitle("Delete Wallpaper")
            msg.setText(f"Are you sure you want to delete this wallpaper?")
            msg.setInformativeText(os.path.basename(wallpaper_name))
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.No)
            
            # Make it always on top
            msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
            
            result = msg.exec_()
            return result == QMessageBox.Yes
            
        except Exception as e:
            logging.error(f"Qt confirmation dialog failed: {e}")
    
    # Fallback to terminal if Qt fails or not available
    print(f"\n🚨 WARNING: About to delete: {os.path.basename(wallpaper_name)}")
    response = input("Type 'DELETE' to confirm, or anything else to cancel: ")
    return response.strip().upper() == "DELETE"

def delete_current_wallpaper_and_advance() -> bool:
    """
    Delete current wallpaper and advance to next one.
    
    Returns:
        bool: True if deletion successful, False otherwise
    """
    ws_num = get_current_workspace()
    ws_key = get_ws_key(ws_num)
    
    # Load config and state
    cfg = load_config()
    state = load_state()
    sec = f"ws{ws_num+1}"
    
    if sec not in cfg:
        logging.error(f"Config section [{sec}] not found")
        return False
    
    folder = cfg[sec].get('folder')
    mode = cfg[sec].get('mode', 'random')
    order = cfg[sec].get('order', 'name_az')
    scaling = cfg[sec].get('scaling', 'scaled')
    
    # Get current images and index
    imgs = load_images(folder)
    if not imgs:
        logging.error(f"No images in {folder}")
        return False
    
    if mode == 'sequential':
        imgs = sort_images(imgs, order)
    else:
        imgs = sort_images(imgs, 'name_az')
    
    current_idx = int(state.get(ws_key, 0) or 0)
    last_idx = int(state.get(ws_key + '_last', -1) or -1)
    
    if current_idx >= len(imgs):
        current_idx = 0
    
    current_wallpaper = imgs[current_idx]
    
    # Confirm deletion
    if not universal_confirm_deletion(str(current_wallpaper)):
        print("Deletion cancelled")
        return False
    
    # Delete the file
    try:
        os.remove(current_wallpaper)
        print(f"Deleted: {current_wallpaper}")
    except Exception as e:
        logging.error(f"Failed to delete {current_wallpaper}: {e}")
        return False
    
    # Reload images (without deleted one) and re-sort
    imgs = load_images(folder)
    if not imgs:
        logging.error("No wallpapers left after deletion")
        return True
    
    if mode == 'sequential':
        imgs = sort_images(imgs, order)
    else:
        imgs = sort_images(imgs, 'name_az')
    
    # Calculate new index
    if mode == 'random':
        if len(imgs) == 1:
            new_idx = 0
        else:
            new_idx = current_idx
            while new_idx == current_idx:
                new_idx = random.randint(0, len(imgs)-1)
    else:  # sequential
        new_idx = current_idx % len(imgs)  # This handles wrap-around
    
    # Update state
    state[ws_key + '_last'] = current_idx  # Store the old index (before deletion)
    state[ws_key] = new_idx                # Store the new index
    
    save_state(state)
    
    # Set new wallpaper
    wallpaper_path = str(imgs[new_idx])
    set_wallpaper(ws_num, wallpaper_path, scaling)
    update_conky_state(f"ws{ws_num+1}", wallpaper_path)
    
    print(f"WS{ws_num+1}: After deletion -> index {new_idx}, wallpaper '{wallpaper_path}'")
    return True

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_current_workspace() -> int:
    """Get current workspace number using xprop."""
    try:
        ws_num = subprocess.check_output(
            ["xprop", "-root", "_NET_CURRENT_DESKTOP"], text=True
        ).strip().split()[-1]
        return int(ws_num)
    except Exception as e:
        logging.error(f"Could not determine current workspace: {e}")
        sys.exit(1)

def get_ws_key(ws_num: int) -> str:
    """Get workspace key for state storage."""
    return f"ws{ws_num+1}"

def load_state() -> dict:
    """Load workspace state from JSON file."""
    if not os.path.isfile(STATE_PATH):
        logging.error(f"State file {STATE_PATH} not found")
        return {}
    try:
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load state file {STATE_PATH}: {e}")
        return {}

def save_state(state: dict):
    """Save workspace state to JSON file."""
    tmp = STATE_PATH + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(state, f)
        os.replace(tmp, STATE_PATH)
    except Exception as e:
        logging.error(f"Failed to save state file {STATE_PATH}: {e}")

def load_config():
    """Load and parse configuration file."""
    global DE
    config = configparser.ConfigParser()
    if not os.path.isfile(CONFIG_PATH):
        logging.error(f"Config file {CONFIG_PATH} not found. Run awp_setup.py first.")
        sys.exit(1)
    try:
        config.read(CONFIG_PATH)
        valid_des = ["xfce", "gnome", "cinnamon", "mate", "generic"]
        
        DE = config.get('general', 'os_detected', fallback=None)
        
        if DE is None:
            logging.error("No 'os_detected' found in config. Run awp_setup.py first.")
            sys.exit(1)
        elif DE not in valid_des:
            logging.error(f"Invalid os_detected '{DE}' in config. Valid options: {valid_des}")
            sys.exit(1)
        else:
            logging.info(f"Using os_detected from config: {DE}")
            
        return config
    except Exception as e:
        logging.error(f"Failed to load config {CONFIG_PATH}: {e}")
        sys.exit(1)

def load_images(folder_path: str) -> list:
    """Load all JPEG and PNG images from specified folder."""
    p = Path(folder_path)
    if not p.is_dir():
        logging.error(f"Folder {folder_path} is not a directory")
        return []
    images = list(p.glob("*.[jJ][pP][gG]")) + list(p.glob("*.[pP][nN][gG]"))
    return images

def sort_images(images: list, order_key: str) -> list:
    """Sort images based on specified order preference."""
    if order_key == 'name_az':
        return sorted(images, key=lambda f: f.name.lower())
    elif order_key == 'name_za':
        return sorted(images, key=lambda f: f.name.lower(), reverse=True)
    elif order_key == 'name_new':
        return sorted(images, key=lambda f: f.stat().st_mtime, reverse=True)
    elif order_key == 'name_old':
        return sorted(images, key=lambda f: f.stat().st_mtime)
    return images

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main navigation controller entry point."""
    if len(sys.argv) != 2 or sys.argv[1] not in ("next", "prev", "delete"):
        logging.error(f"Usage: {sys.argv[0]} next|prev|delete")
        sys.exit(1)

    command = sys.argv[1]
    
    # Handle deletion command
    if command == "delete":
        os.makedirs(AWP_DIR, exist_ok=True)
        force_single_workspace_off()
        success = delete_current_wallpaper_and_advance()
        sys.exit(0 if success else 1)
    
    # Handle next/prev navigation commands
    direction = command
    os.makedirs(AWP_DIR, exist_ok=True)
    force_single_workspace_off()

    ws_num = get_current_workspace()
    ws_key = get_ws_key(ws_num)

    # Load configuration and workspace settings
    cfg = load_config()
    sec = f"ws{ws_num+1}"
    if sec not in cfg:
        logging.error(f"Config section [{sec}] not found")
        sys.exit(1)

    folder = cfg[sec].get('folder')
    mode = cfg[sec].get('mode', 'random')
    order = cfg[sec].get('order', 'name_az')
    scaling = cfg[sec].get('scaling', 'scaled')

    # Load and sort images
    imgs = load_images(folder)
    if not imgs:
        logging.error(f"No images in {folder}")
        sys.exit(1)

    if mode == 'sequential':
        imgs = sort_images(imgs, order)
    else:
        imgs = sort_images(imgs, 'name_az')

    # Load state and calculate new index
    state = load_state()
    idx = int(state.get(ws_key, 0) or 0)
    last_idx = int(state.get(ws_key + '_last', -1) or -1)
    if idx >= len(imgs):
        idx = 0

    # Calculate new index based on direction and mode
    if direction == "next":
        if mode == 'random':
            if len(imgs) == 1:
                new_idx = 0
            else:
                new_idx = idx
                while new_idx == idx:
                    new_idx = random.randint(0, len(imgs)-1)
        else:
            new_idx = (idx + 1) % len(imgs)
    else:  # prev
        if mode == 'random':
            new_idx = last_idx if last_idx >= 0 and last_idx < len(imgs) else idx
        else:
            new_idx = (idx - 1) % len(imgs)

    # Update state and apply changes
    state[ws_key + '_last'] = idx
    state[ws_key] = new_idx
    save_state(state)

    # Apply new wallpaper and update Conky
    wallpaper_path = str(imgs[new_idx])
    set_wallpaper(ws_num, wallpaper_path, scaling)
    
    # =========================================================================
    # CONKY INTEGRATION (OPTIONAL)
    # Uncomment the line below to enable real-time wallpaper info for Conky
    # update_conky_state(f"ws{self.num+1}", current_wallpaper_path)
    # =========================================================================
    
    print(f"WS{ws_num+1}: {direction} -> index {new_idx}, scaling '{scaling}', wallpaper '{wallpaper_path}'")

if __name__ == "__main__":
    main()
