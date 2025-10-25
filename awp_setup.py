#!/usr/bin/env python3
"""
AWP - Automated Wallpaper Program
Initial Setup Wizard

Creates initial configuration file and directory structure for AWP.
Part of the AWP wallpaper automation system.

Features:
- Desktop environment auto-detection
- Professional user prompts with validation
- Workspace configuration with theme support
- Smart dependency checking
- Autostart setup
"""

import configparser
import os
import subprocess
import sys
import shutil
from PIL import Image
import textwrap

# =============================================================================
# PATHS AND CONSTANTS
# =============================================================================
AWP_DIR = os.path.expanduser("~/awp")
CONFIG_PATH = os.path.join(AWP_DIR, "awp_config.ini")
BACKUP_PATH = os.path.join(AWP_DIR, "awp_config.ini.bak")
BASE_FOLDER = os.path.expanduser("~")
ICON_DIR = os.path.join(AWP_DIR, "logos")
USER_HOME = os.path.expanduser("~")

# =============================================================================
# CONFIGURATION MAPPINGS
# =============================================================================
ORDER_MAP = {
    'a': 'name_az', 'z': 'name_za', 
    'm': 'name_old', 'M': 'name_new'
}
SCALING_MAP = {
    'c': 'centered', 's': 'scaled', 'z': 'zoomed'
}
MODE_MAP = {
    'r': 'random', 's': 'sequential'
}

def print_header(text: str):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f" {text.upper()} ")
    print(f"{'='*60}")

def print_success(message: str):
    """Print a success message."""
    print(f"✅ {message}")

def print_warning(message: str):
    """Print a warning message."""
    print(f"⚠️  {message}")

def print_error(message: str):
    """Print an error message."""
    print(f"❌ {message}")

def wrap_text(text: str, width: int = 70) -> str:
    """Wrap text to specified width for better readability."""
    return '\n'.join(textwrap.wrap(text, width=width))

def run_shell(cmd: str, error_msg: str = "Command failed") -> str:
    """
    Run shell command with proper error handling.
    
    Args:
        cmd (str): Command to execute
        error_msg (str): Custom error message
        
    Returns:
        str: Command output or None if failed
    """
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print_warning(f"{error_msg}: {e.stderr.strip()}")
        return None

def check_dependencies():
    """
    Check for required Python dependencies and inform user.
    Does not block setup - daemon works without PyQt5.
    """
    print_header("Dependency Check")
    
    required_packages = {
        'PIL': 'Pillow (image processing)',
        'PyQt5': 'PyQt5 (graphical interface)',
    }
    
    all_available = True
    
    for package, description in required_packages.items():
        try:
            if package == 'PIL':
                import PIL
            elif package == 'PyQt5':
                from PyQt5.QtWidgets import QApplication
            print_success(f"{package}: {description}")
        except ImportError:
            print_error(f"Missing: {package} - {description}")
            if package == 'PyQt5':
                print_warning("  → Dashboard will not work without PyQt5")
            else:
                print_warning("  → Core functionality affected")
            print_warning(f"  → Install with: pip3 install {package.lower()}")
            all_available = False
    
    # Simple Conky check
    conky_available = run_shell("which conky", "Checking Conky") is not None
    if not conky_available:
        print_warning("Conky not installed - required for experimental Conky features")
        print_warning("  → Install with: sudo apt install conky-all")
    
    if not all_available:
        print_warning("Note: AWP daemon will work, but some features require dependencies")
    else:
        print_success("All dependencies available")

def parse_timing(timing_str: str) -> int:
    """
    Convert timing string to seconds.
    
    Args:
        timing_str (str): Timing string (e.g., '30s', '5m', '1h')
        
    Returns:
        int: Seconds or None if invalid
    """
    units = {'s': 1, 'm': 60, 'h': 3600}
    
    if not timing_str:
        return None
        
    try:
        unit = timing_str[-1].lower()
        number = int(timing_str[:-1])
        return number * units.get(unit, 60)
    except (ValueError, IndexError):
        return None

def ask(prompt: str, validate=None, default: str = None) -> str:
    """
    Prompt user with validation and default support.
    
    Args:
        prompt (str): Prompt text
        validate (callable): Validation function
        default (str): Default value if user presses Enter
        
    Returns:
        str: Validated user input
    """
    while True:
        # Always add default hint if provided
        if default is not None:
            full_prompt = f"{prompt} [{default}]: "
        else:
            full_prompt = f"{prompt}: "

        print(wrap_text(full_prompt), end='')
        user_input = input().strip()
        
        # Use default if provided and input is empty
        if not user_input and default is not None:
            return default
            
        if not user_input:
            print_warning("Input cannot be empty")
            continue
            
        if validate is None or validate(user_input):
            return user_input
            
        print_warning("Invalid input, please try again")

def detect_de() -> str:
    """Detect desktop environment."""
    de = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    
    if "xfce" in de:
        return "xfce"
    elif "gnome" in de:
        return "gnome"
    elif "cinnamon" in de:
        return "cinnamon"
    elif "mate" in de:
        return "mate"
    else:
        return "generic"  # Changed from "unknown" to "generic"

def detect_session_type() -> str:
    """Detect session type (X11 or Wayland)."""
    if os.environ.get('WAYLAND_DISPLAY'):
        return 'wayland'
    elif os.environ.get('DISPLAY'):
        return 'x11'
    else:
        return 'unknown'

def get_workspaces(de: str) -> tuple:
    """
    Detect workspace count and dynamic/fixed state.
    
    Args:
        de (str): Desktop environment name
        
    Returns:
        tuple: (workspace_count, is_dynamic) or (None, None) if undetectable
    """
    try:
        if de == "xfce":
            count = run_shell(
                "xfconf-query -c xfwm4 -p /general/workspace_count",
                "Failed to get XFCE workspace count"
            )
            return (int(count), False) if count else (None, None)
            
        elif de == "gnome":
            count = run_shell(
                "gsettings get org.gnome.desktop.wm.preferences num-workspaces",
                "Failed to get GNOME workspace count"
            )
            # Clean up gsettings output
            if count and count != '':
                count = count.strip("'")
                return (int(count), False) if count.isdigit() else (None, None)
                
        elif de == "mate":
            count = run_shell(
                "gsettings get org.mate.Marco.general num-workspaces",
                "Failed to get MATE workspace count"
            )
            if count and count != '':
                count = count.strip("'")
                return (int(count), False) if count.isdigit() else (None, None)
                
        elif de == "cinnamon":
            count = run_shell(
                "gsettings get org.cinnamon.desktop.wm.preferences num-workspaces",
                "Failed to get Cinnamon workspace count"
            )
            if count and count != '':
                count = count.strip("'")
                return (int(count), False) if count.isdigit() else (None, None)
                
    except (ValueError, TypeError) as e:
        print_warning(f"Could not parse workspace count: {e}")
        
    return (None, None)

def set_fixed_workspaces(de: str, num_ws: int):
    """
    Set fixed number of workspaces for supported DEs.
    
    Args:
        de (str): Desktop environment name
        num_ws (int): Number of workspaces
    """
    num_ws = int(num_ws)
    
    if de == "gnome":
        run_shell(
            "gsettings set org.gnome.shell.extensions.dash-to-dock dynamic-workspaces false",
            "Failed to disable GNOME dynamic workspaces"
        )
        run_shell(
            f"gsettings set org.gnome.desktop.wm.preferences num-workspaces {num_ws}",
            "Failed to set GNOME workspace count"
        )
        
    elif de == "mate":
        run_shell(
            f"gsettings set org.mate.Marco.general num-workspaces {num_ws}",
            "Failed to set MATE workspace count"
        )
        
    elif de == "cinnamon":
        run_shell(
            f"gsettings set org.cinnamon.desktop.wm.preferences num-workspaces {num_ws}",
            "Failed to set Cinnamon workspace count"
        )
        
    elif de == "xfce":
        run_shell(
            f"xfconf-query -c xfwm4 -p /general/workspace_count -s {num_ws}",
            "Failed to set XFCE workspace count"
        )
        
    else:
        print_warning("For generic window managers, configure workspaces manually")

def get_icon_color(image_path: str) -> str:
    """
    Detect dominant color from image.
    
    Args:
        image_path (str): Path to image file
        
    Returns:
        str: Hex color code or empty string on error
    """
    try:
        with Image.open(image_path) as img:
            rgba_img = img.convert("RGBA")
            for r, g, b, a in rgba_img.getdata():
                if a > 0:  # Ignore transparent pixels
                    return f'#{r:02x}{g:02x}{b:02x}'
            return ""
    except Exception as e:
        print_warning(f"Could not detect icon color: {e}")
        return ""

def setup_autostart():
    """Create autostart entry for AWP daemon."""
    autostart_dir = os.path.expanduser("~/.config/autostart")
    os.makedirs(autostart_dir, exist_ok=True)
    
    desktop_file = os.path.join(autostart_dir, "awp_start.desktop")
    desktop_content = """[Desktop Entry]
Type=Application
Exec=sh -c '$HOME/awp/awp_start.sh'
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=AWP Wallpaper Manager
Comment=Automated wallpaper and theme management
"""
    try:
        with open(desktop_file, "w") as f:
            f.write(desktop_content)
        print_success(f"Autostart entry created: {desktop_file}")
    except IOError as e:
        print_error(f"Failed to create autostart entry: {e}")

def print_keybinding_instructions():
    """Print instructions for setting up keybindings."""
    print_header("Optional Keybindings")
    print(wrap_text(
        "For manual wallpaper navigation, you can create these keybindings in your "
        "system settings:"
    ))
    print(f"\n  Next Wallpaper: ~/awp/awp_nav.py next")
    print(f"  Previous Wallpaper: ~/awp/awp_nav.py prev")
    print(f"  Delete Current Wallpaper: ~/awp/awp_nav.py delete")
    print("\nSuggested shortcuts:")
    print("  Next: Super+Right")
    print("  Previous: Super+Left") 
    print("  Delete: Super+Delete")

def configure_screen_blanking(config):
    """Configure screen blanking timeout."""
    print_header("Screen Blanking Configuration")
    
    print(wrap_text(
        "AWP can manage screen blanking timeouts for XFCE/X11 sessions. "
        "This controls when your screen goes blank during inactivity."
    ))
    
    use_blanking = ask(
        "Enable screen blanking management? [y/N]: ",
        lambda v: v.lower() in ['y', 'n', ''],
        default='n'
    )
    
    if use_blanking.lower() == 'y':
        timing = ask(
            "Blank after (e.g., 5m, 10m, 30m): ",
            lambda t: parse_timing(t) is not None,
            default='20m'
        )
        
        timeout_seconds = parse_timing(timing)
        if timeout_seconds:
            config['general']['blanking_timeout'] = str(timeout_seconds)
            config['general']['blanking_pause'] = 'false'
            print_success(f"Screen blanking enabled: {timing}")
        else:
            config['general']['blanking_timeout'] = '0'
            config['general']['blanking_pause'] = 'true'
            print_warning("Invalid timing, blanking disabled")
    else:
        config['general']['blanking_timeout'] = '0'
        config['general']['blanking_pause'] = 'true'
        print_success("Screen blanking management disabled")

def get_available_themes() -> dict:
    """Discover available themes on the system and return categorized lists."""
    themes = {
        'icon_themes': [],
        'gtk_themes': [], 
        'cursor_themes': [],
        'desktop_themes': [],  # For Cinnamon desktop/panels
        'wm_themes': []        # For window borders specifically
    }
    
    # Discover icon themes
    icon_paths = [
        '/usr/share/icons', 
        os.path.expanduser('/usr/local/share/icons'),
        os.path.expanduser('~/.icons'),
        os.path.expanduser('~/.local/share/icons')
    ]
    
    for path in icon_paths:
        if os.path.exists(path):
            try:
                items = [d for d in os.listdir(path) 
                        if os.path.isdir(os.path.join(path, d))]
                themes['icon_themes'].extend(items)
            except (PermissionError, OSError):
                pass  # Skip directories we can't read
    
    # Discover ALL themes
    theme_paths = [
        '/usr/share/themes',
        '/usr/local/share/themes', 
        os.path.expanduser('~/.themes'),
        os.path.expanduser('~/.local/share/themes')
    ]
    
    all_themes = []
    for path in theme_paths:
        if os.path.exists(path):
            try:
                items = [d for d in os.listdir(path) 
                        if os.path.isdir(os.path.join(path, d))]
                all_themes.extend(items)
            except (PermissionError, OSError):
                pass  # Skip directories we can't read
    
    # Filter for themes that have Cinnamon support (desktop themes)
    desktop_themes = []
    wm_themes = []
    
    for theme in all_themes:
        # Check all possible theme paths
        theme_paths_to_check = []
        for base_path in theme_paths:
            if os.path.exists(base_path):
                # Check for various window manager/desktop components
                possible_paths = [
                    os.path.join(base_path, theme, 'cinnamon'),
                    os.path.join(base_path, theme, 'metacity-1'), 
                    os.path.join(base_path, theme, 'xfwm4'),
                    os.path.join(base_path, theme, 'gnome-shell'),
                    os.path.join(base_path, theme, 'openbox-3')
                ]
                theme_paths_to_check.extend(possible_paths)
        
        # Check if this theme has window manager components
        has_wm = any(os.path.exists(path) for path in theme_paths_to_check)
        
        if has_wm:
            wm_themes.append(theme)
            # Themes with Cinnamon specific support are desktop themes
            if any('cinnamon' in path for path in theme_paths_to_check if os.path.exists(path)):
                desktop_themes.append(theme)
    
    # Sort all lists alphabetically
    themes['gtk_themes'] = sorted(list(set(all_themes)))
    themes['desktop_themes'] = sorted(list(set(desktop_themes)))
    themes['wm_themes'] = sorted(list(set(wm_themes)))
    themes['icon_themes'] = sorted(list(set(themes['icon_themes'])))
    
    # Discover cursor themes
    cursor_themes = []
    for path in icon_paths:
        if os.path.exists(path):
            try:
                for theme in os.listdir(path):
                    cursor_path = os.path.join(path, theme, 'cursors')
                    if os.path.exists(cursor_path):
                        cursor_themes.append(theme)
            except (PermissionError, OSError):
                pass
    
    themes['cursor_themes'] = sorted(list(set(cursor_themes)))
    
    return themes

def show_numbered_menu(items: list, title: str, page_size: int = 20) -> str:
    """Display a paginated numbered menu for theme selection."""
    if not items:
        print(f"\nNo {title} found on system.")
        return None
    
    # Ensure items are sorted (double-check)
    sorted_items = sorted(items)
    
    print(f"\n{title}:")
    print("-" * 40)
    print(f"Found {len(sorted_items)} themes")
    print("-" * 40)
    
    # Paginate if too many items
    for page_start in range(0, len(sorted_items), page_size):
        page_end = min(page_start + page_size, len(sorted_items))
        page_items = sorted_items[page_start:page_end]
        
        for i, item in enumerate(page_items, 1):
            print(f"  {page_start + i:2d}. {item}")
        
        if page_end < len(sorted_items):
            cont = ask(f"\nShow more? {page_end}/{len(sorted_items)} shown (y/n): ", 
                      lambda v: v.lower() in ['y', 'n'])
            if cont.lower() != 'y':
                break
        print()
    
    while True:
        choice = ask(f"Select {title.lower()} by number (or Enter to skip): ")
        if not choice:
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(sorted_items):
                return sorted_items[idx]
            else:
                print(f"Please enter a number between 1 and {len(sorted_items)}")
        except ValueError:
            print("Please enter a valid number")

def configure_workspace_themes(config, section: str, ws_num: int, de: str):
    """Configure themes for a specific workspace based on DE."""
    print(f"\n{'='*40}")
    print(f"THEME CONFIGURATION FOR WORKSPACE {ws_num} ({de.upper()})")
    print(f"{'='*40}")
    
    themes = get_available_themes()
    
    enable_themes = ask("Enable theme switching for this workspace? [y/N]: ",
                       lambda v: v.lower() in ['y','n'])
    
    if enable_themes.lower() != 'y':
        # USER SAID NO TO THEMES - STILL SET ALL DEFAULTS for INI compatibility
        config[section]['icon_theme'] = 'Adwaita'
        config[section]['gtk_theme'] = 'Adwaita' 
        config[section]['cursor_theme'] = 'Adwaita'
        config[section]['desktop_theme'] = 'Adwaita'
        config[section]['wm_theme'] = 'Adwaita'
        print("Theme switching disabled - all theme variables set to defaults for INI compatibility")
        return
    
    # USER SAID YES TO THEMES - proceed with configuration
    # SET ALL 5 THEME DEFAULTS (always written to INI)
    config[section]['icon_theme'] = 'Adwaita'
    config[section]['gtk_theme'] = 'Adwaita' 
    config[section]['cursor_theme'] = 'Adwaita'
    config[section]['desktop_theme'] = 'Adwaita'  # Cinnamon-only but always written
    config[section]['wm_theme'] = 'Adwaita'       # XFCE/MATE but always written
    
    # CORE THEMES: Available in ALL desktop environments (always ask)
    print("CORE THEMES (available in all desktop environments):")
    print("-" * 50)
    
    icon_theme = show_numbered_menu(themes['icon_themes'], "ICON THEMES")
    if icon_theme:
        config[section]['icon_theme'] = icon_theme
    
    gtk_theme = show_numbered_menu(themes['gtk_themes'], "GTK THEMES")
    if gtk_theme:
        config[section]['gtk_theme'] = gtk_theme
    
    cursor_theme = show_numbered_menu(themes['cursor_themes'], "CURSOR THEMES") 
    if cursor_theme:
        config[section]['cursor_theme'] = cursor_theme
    
    # DE-SPECIFIC THEMES: Only show menus for relevant themes
    print("\nEXTENDED THEMES (desktop environment specific):")
    print("-" * 50)
    
    if de == "cinnamon":
        # Only ask for desktop_theme (Cinnamon-specific)
        desktop_theme = show_numbered_menu(themes['desktop_themes'], "CINNAMON DESKTOP THEMES")
        if desktop_theme:
            config[section]['desktop_theme'] = desktop_theme
        # wm_theme remains as default (Adwaita) - not used in Cinnamon
        print("✓ Window borders included in desktop theme")
            
    elif de == "xfce":
        # Only ask for wm_theme (XFCE-specific)
        wm_theme = show_numbered_menu(themes['wm_themes'], "XFCE WINDOW THEMES")
        if wm_theme:
            config[section]['wm_theme'] = wm_theme
        # desktop_theme remains as default (Adwaita) - not used in XFCE
        print("✓ Desktop theme not applicable for XFCE")
            
    elif de == "gnome":
        # NO shell_theme anymore - just skip extended themes for GNOME
        print("✓ GNOME: Using core themes only (GTK, Icons, Cursors)")
        print("✓ Desktop theme not applicable for GNOME") 
        print("✓ Window theme handled by GTK theme in GNOME")
            
    elif de == "mate":
        # Only ask for wm_theme (MATE-specific)
        wm_theme = show_numbered_menu(themes['wm_themes'], "MATE WINDOW THEMES")
        if wm_theme:
            config[section]['wm_theme'] = wm_theme
        # desktop_theme remains as default (Adwaita) - not used in MATE
        print("✓ Desktop theme not applicable for MATE")
    
    # GENERIC/UNKNOWN DE: Offer window and desktop themes as optional
    elif de == "generic":
        print("Generic desktop - extended themes available as experimental:")
        
        # Offer window themes
        if themes['wm_themes']:
            wm_theme = show_numbered_menu(themes['wm_themes'], "WINDOW THEMES (Experimental)")
            if wm_theme:
                config[section]['wm_theme'] = wm_theme
        
        # Offer desktop themes  
        if themes['desktop_themes']:
            desktop_theme = show_numbered_menu(themes['desktop_themes'], "DESKTOP THEMES (Experimental)")
            if desktop_theme:
                config[section]['desktop_theme'] = desktop_theme
    
    print_success(f"Theme configuration for workspace {ws_num} complete")
    print(f"INI will contain all 5 theme variables for compatibility")

def main():
    """Main setup routine for AWP configuration."""
    print_header("AWP Automated Wallpaper Program")
    print(wrap_text(
        "Welcome to AWP setup! This wizard will guide you through configuring "
        "automated wallpaper rotation and theme management for your workspaces."
    ))
    
    # -------------------------------------------------------------------------
    # DEPENDENCY CHECK
    # -------------------------------------------------------------------------
    # Just check and inform - don't block setup
    check_dependencies()
    
    # -------------------------------------------------------------------------
    # ENVIRONMENT DETECTION
    # -------------------------------------------------------------------------
    print_header("Environment Detection")
    de = detect_de()
    print_success(f"Desktop environment: {de}")
    
    session_type = detect_session_type()
    print_success(f"Session type: {session_type}")
    
    # -------------------------------------------------------------------------
    # EXISTING CONFIG HANDLING
    # -------------------------------------------------------------------------
    if os.path.isfile(CONFIG_PATH):
        print_warning("Existing configuration file found")
        choice = ask(
            "Create new config (c) or exit (e) [c/e]? ",
            lambda v: v.lower() in ['c', 'e'],
            default='c'
        )
        if choice == 'e':
            print_success("Setup cancelled - existing configuration preserved")
            sys.exit(0)
        
        # Create backup
        shutil.copy(CONFIG_PATH, BACKUP_PATH)
        print_success(f"Backup created: {BACKUP_PATH}")
    
    # -------------------------------------------------------------------------
    # BASIC CONFIGURATION
    # -------------------------------------------------------------------------
    config = configparser.ConfigParser()
    config['general'] = {
        'os_detected': de,
        'session_type': session_type,
        'blanking_timeout': '0',      # Default: disabled
        'blanking_pause': 'true'      # Default: paused
    }
    
    configure_screen_blanking(config)
    
    # -------------------------------------------------------------------------
    # DIRECTORY SETUP
    # -------------------------------------------------------------------------
    print_header("Directory Setup")
    if os.path.exists(ICON_DIR):
        shutil.rmtree(ICON_DIR)
    os.makedirs(ICON_DIR)
    print_success(f"Icon directory created: {ICON_DIR}")
    
    # -------------------------------------------------------------------------
    # WORKSPACE CONFIGURATION
    # -------------------------------------------------------------------------
    print_header("Workspace Configuration")
    
    n_ws, is_dynamic = get_workspaces(de)
    if n_ws is None:
        n_ws = ask(
            "Number of workspaces to configure: ",
            lambda v: v.isdigit() and 1 <= int(v) <= 8,
            default='3'
        )
        n_ws = int(n_ws)
    else:
        print_success(f"Detected {n_ws} workspaces")
    
    if is_dynamic:
        print_warning("Dynamic workspaces detected")
        set_fixed = ask(
            "Set fixed number of workspaces? [y/N]: ",
            lambda v: v.lower() in ['y', 'n', ''],
            default='n'
        )
        if set_fixed.lower() == 'y':
            n_ws = ask(
                "Fixed workspace count: ",
                lambda v: v.isdigit() and 1 <= int(v) <= 8,
                default=str(n_ws)
            )
            n_ws = int(n_ws)
            set_fixed_workspaces(de, n_ws)
    
    config['general']['workspaces'] = str(n_ws)
    
    # -------------------------------------------------------------------------
    # INDIVIDUAL WORKSPACE SETUP
    # -------------------------------------------------------------------------
    used_folders = set()
    
    for i in range(1, n_ws + 1):
        print_header(f"Workspace {i} Configuration")
        
        section = f"ws{i}"
        config[section] = {}
        
        # Folder selection
        while True:
            folder_name = ask(
                f"Wallpaper folder name (in {BASE_FOLDER}): ",
                default=f"wallpapers-ws{i}"
            )
            full_path = os.path.join(BASE_FOLDER, folder_name)
            
            if not os.path.isdir(full_path):
                print_warning(f"Folder does not exist: {full_path}")
                create = ask("Create this folder? [Y/n]: ", default='y')
                if create.lower() == 'y':
                    os.makedirs(full_path)
                    print_success(f"Created folder: {full_path}")
                else:
                    continue
            
            if full_path in used_folders:
                print_warning("This folder is already used by another workspace")
                continue
                
            break
        
        config[section]['folder'] = full_path
        used_folders.add(full_path)
        
        # Icon selection
        while True:
            icon_path = ask(
                "Workspace icon file path: ",
                default=f"{USER_HOME}/Pictures/icon-ws{i}.png"
            )
            
            if os.path.isfile(icon_path):
                break
            print_warning(f"Icon file not found: {icon_path}")
        
        # Copy icon to AWP directory
        folder_base = os.path.basename(folder_name)
        _, ext = os.path.splitext(icon_path)
        dest_icon = os.path.join(ICON_DIR, f"{folder_base}{ext or '.png'}")
        shutil.copy(icon_path, dest_icon)
        config[section]['icon'] = dest_icon
        print_success(f"Icon configured: {dest_icon}")
        
        # Extract icon color
        color = get_icon_color(dest_icon)
        if color:
            config[section]['icon_color'] = color
            config[section]['color_variable'] = f"{section}_color"
            print_success(f"Icon color: {color}")
        
        # Timing configuration
        timing = ask(
            "Wallpaper rotation interval (e.g., 30s, 5m, 1h): ",
            lambda t: parse_timing(t) is not None,
            default='5m'
        )
        config[section]['timing'] = timing
        
        # Mode selection
        mode = ask(
            "Rotation mode - (r)andom or (s)equential [r/s]? ",
            lambda v: v.lower() in ['r', 's'],
            default='r'
        )
        config[section]['mode'] = MODE_MAP[mode.lower()]
        
        # Order configuration (only for sequential mode)
        if MODE_MAP[mode.lower()] == 'sequential':
            order = ask(
                "Sort order - (a) A-Z, (z) Z-A, (m) oldest, (M) newest [a/z/m/M]? ",
                lambda v: v.lower() in ['a', 'z', 'm', 'M'],
                default='a'
            )
            config[section]['order'] = ORDER_MAP[order.lower()]
        else:
            config[section]['order'] = 'n'
        
        # Scaling configuration
        scaling = ask(
            "Wallpaper scaling - (c)entered, (s)caled, (z)oomed [c/s/z]? ",
            lambda v: v.lower() in ['c', 's', 'z'],
            default='s'
        )
        config[section]['scaling'] = SCALING_MAP[scaling.lower()]
        
        # Theme configuration
        configure_workspace_themes(config, section, i, de)
        
        print_success(f"Workspace {i} configuration complete")
    
    # -------------------------------------------------------------------------
    # AUTOSTART SETUP
    # -------------------------------------------------------------------------
    print_header("Autostart Configuration")
    
    setup_autostart = ask(
        "Start AWP automatically at login? [Y/n]: ",
        lambda v: v.lower() in ['y', 'n', ''],
        default='y'
    )
    
    if setup_autostart.lower() == 'y':
        setup_autostart()
    else:
        print_success("Autostart skipped - start manually with ~/awp/awp_start.sh")
    
    # -------------------------------------------------------------------------
    # SAVE CONFIGURATION & COMPLETION
    # -------------------------------------------------------------------------
    print_header("Saving Configuration")
    
    with open(CONFIG_PATH, 'w') as f:
        config.write(f)
    
    print_success(f"Configuration saved: {CONFIG_PATH}")
    
    # -------------------------------------------------------------------------
    # STARTUP INSTRUCTIONS
    # -------------------------------------------------------------------------
    print_header("Setup Complete")
    
    print_success("AWP configuration file created successfully!")
    
    # Autostart status
    autostart_file = os.path.expanduser("~/.config/autostart/awp_start.desktop")
    if os.path.exists(autostart_file):
        print_success("AWP will start automatically on next login")
    else:
        print("Start AWP manually with:")
        print(f"  ~/awp/awp_start.sh")
        print(f"  or")
        print(f"  python3 ~/awp/awp_daemon.py")
    
    # Dashboard info
    print("\nConfigure settings with graphical dashboard:")
    print(f"  python3 ~/awp/awp_dab.py")
    
    print_keybinding_instructions()

if __name__ == "__main__":
    main()
