#!/usr/bin/env python3
import configparser
import os
import subprocess
import sys
import shutil
from PIL import Image
import textwrap

# Define directories
AWP_DIR = os.path.expanduser("~/awp")
CONFIG_PATH = os.path.join(AWP_DIR, "awp_config.ini")
BACKUP_PATH = os.path.join(AWP_DIR, "awp_config.ini.bak")
BASE_FOLDER = os.path.expanduser("~")
ICON_DIR = os.path.join(AWP_DIR, "logos")
USER_HOME = os.path.expanduser("~")

def wrap_text(text, width=80):
    """Wrap text to a specified width for better readability in terminals."""
    return '\n'.join(textwrap.wrap(text, width=width))

def run_shell(cmd, error_msg="Command failed"):
    """Run a shell command and return True if successful, False otherwise."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(wrap_text(f"{error_msg}: {cmd}"))
        print(wrap_text(f"Error output: {e.stderr}"))
        return None

def install_dependencies(de):
    """Install required dependencies for AWP with verbose output."""
    print(wrap_text("Starting dependency installation..."))
    
    # Define dependencies
    deps = "conky-all python3-psutil libcairo2 libx11-6 libxft2"
    if de == "unknown":
        deps += " feh"
    
    # Update package lists
    print(wrap_text("Updating package lists with 'sudo apt update'..."))
    if not run_shell("sudo apt update", "Failed to update package lists"):
        print(wrap_text("Package list update failed. Please run 'sudo apt update' manually."))
        sys.exit(1)
    print(wrap_text("Package lists updated successfully."))

    # Install system dependencies
    print(wrap_text(f"Installing system dependencies: {deps}..."))
    if not run_shell(f"sudo apt install -y {deps}", "Failed to install system dependencies"):
        print(wrap_text(f"Please run 'sudo apt install -y {deps}' manually."))
        sys.exit(1)
    print(wrap_text("System dependencies installed successfully."))

    # Check if psutil is installed
    print(wrap_text("Checking for Python psutil module..."))
    if not run_shell("python3 -m pip show psutil", "Checking psutil..."):
        print(wrap_text("psutil not found. Installing psutil..."))
        if not run_shell("python3 -m pip install --user psutil", "Failed to install psutil"):
            print(wrap_text("Please run 'python3 -m pip install --user psutil' manually."))
            sys.exit(1)
        print(wrap_text("psutil installed successfully."))
    else:
        print(wrap_text("psutil is already installed."))
    
    print(wrap_text("All dependencies installed successfully."))

def parse_timing(timing_str):
    """Convert timing string (e.g., 30s, 7m, 2h) to seconds."""
    units = {'s': 1, 'm': 60, 'h': 3600}
    try:
        unit = timing_str[-1].lower()
        number = int(timing_str[:-1])
        return number * units.get(unit, 60)
    except Exception:
        return None

def ask(prompt, validate=None, err_msg="Invalid input, try again."):
    """Prompt user and validate input."""
    while True:
        print(wrap_text(prompt), end='')
        val = input().strip()
        if validate is None or validate(val):
            return val
        print(wrap_text(err_msg))

ORDER_MAP = {
    'a': 'name_az',
    'z': 'name_za',
    'm': 'name_old',
    'M': 'name_new'
}
SCALING_MAP = {'c': 'centered', 's': 'scaled', 'z': 'zoomed'}
MODE_MAP = {'r': 'random', 's': 'sequential'}

def detect_de():
    """Detect desktop environment via XDG_CURRENT_DESKTOP."""
    de = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "xfce" in de: return "xfce"
    elif "gnome" in de: return "gnome"
    elif "cinnamon" in de: return "cinnamon"
    elif "mate" in de: return "mate"
    return "unknown"

def detect_session_type():
    """Detect session type (X11 or Wayland)."""
    if os.environ.get('WAYLAND_DISPLAY'): return 'wayland'
    elif os.environ.get('DISPLAY'): return 'x11'
    else: return 'unknown'

def get_workspaces(de):
    """Detect workspace count and dynamic/fixed state."""
    try:
        if de == "xfce":
            count = run_shell("xfconf-query -c xfwm4 -p /general/workspace_count",
                              "Failed to get XFCE workspace count")
            return (int(count), False) if count else (None, None)
        elif de == "gnome":
            count = run_shell("gsettings get org.gnome.desktop.wm.preferences num-workspaces",
                              "Failed to get GNOME workspace count")
            dynamic = run_shell("gsettings get org.gnome.shell.extensions.dash-to-dock dynamic-workspaces",
                                "Failed to check GNOME dynamic workspaces")
            return (int(count), dynamic == "true") if count and dynamic else (None, None)
        elif de == "mate":
            count = run_shell("gsettings get org.mate.Marco.general num-workspaces",
                              "Failed to get MATE workspace count")
            return (int(count), False) if count else (None, None)
        elif de == "cinnamon":
            count = run_shell("gsettings get org.cinnamon.desktop.wm.preferences num-workspaces",
                              "Failed to get Cinnamon workspace count")
            return (int(count), False) if count else (None, None)
        else:
            return (None, None)
    except (ValueError, TypeError):
        print(wrap_text("Warning: Could not determine workspace count dynamically."))
        return (None, None)

def set_fixed_workspaces(de, num_ws):
    """Set a fixed number of workspaces for supported DEs."""
    num_ws = int(num_ws)
    if de == "gnome":
        run_shell("gsettings set org.gnome.shell.extensions.dash-to-dock dynamic-workspaces false",
                  "Failed to disable GNOME dynamic workspaces")
        run_shell(f"gsettings set org.gnome.desktop.wm.preferences num-workspaces {num_ws}",
                  "Failed to set GNOME workspace count")
    elif de == "mate":
        run_shell(f"gsettings set org.mate.Marco.general num-workspaces {num_ws}",
                  "Failed to set MATE workspace count")
    elif de == "cinnamon":
        run_shell(f"gsettings set org.cinnamon.desktop.wm.preferences num-workspaces {num_ws}",
                  "Failed to set Cinnamon workspace count")
    elif de == "xfce":
        run_shell(f"xfconf-query -c xfwm4 -p /general/workspace_count -s {num_ws}",
                  "Failed to set XFCE workspace count")
    else:
        print(wrap_text("For generic WM, configure fixed workspaces manually."))

def get_icon_color(image_path):
    """Detect main icon color (ignores transparency)."""
    try:
        with Image.open(image_path) as img:
            rgba_img = img.convert("RGBA")
            for r, g, b, a in rgba_img.getdata():
                if a > 0:
                    return f'#{r:02x}{g:02x}{b:02x}'
            return ""
    except Exception as e:
        print(wrap_text(f"Warning: Could not detect icon color. {e}"))
        return ""

def setup_autostart():
    """Create autostart entry for AWP."""
    autostart_dir = os.path.expanduser("~/.config/autostart")
    os.makedirs(autostart_dir, exist_ok=True)
    desktop_file = os.path.join(autostart_dir, "awp_start.desktop")
    desktop_content = """[Desktop Entry]
Type=Application
Exec=sh -c '$HOME/awp/awp_start.sh'
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=AWP
Comment=Start AWP daemon (with optional Conky)
"""
    try:
        with open(desktop_file, "w") as f:
            f.write(desktop_content)
        print(wrap_text(f"[+] Autostart entry created at {desktop_file}"))
    except IOError as e:
        print(wrap_text(f"[!] Failed to create autostart entry: {e}"))

def print_keybinding_instructions():
    """Print keybinding instructions for wallpaper navigation."""
    print(wrap_text("\nTo use the previous/next wallpaper feature, create these keybindings:"))
    print(f"  - Next: python3 {USER_HOME}/awp/awp_prev_next.py next  (Shortcut: Super+Right)")
    print(f"  - Prev: python3 {USER_HOME}/awp/awp_prev_next.py prev  (Shortcut: Super+Left)")

def configure_screen_blanking(config):
    """Configure screen blanking timeout."""
    print("\n" + "="*50)
    print("SCREEN BLANKING CONFIGURATION")
    print("="*50)
    use_blanking = ask("Enable screen blanking after inactivity? [y/N]: ",
                       lambda v: v.lower() in ['y','n'], "Enter 'y' or 'n'.")
    if use_blanking.lower() == 'y':
        timing = ask("Screen blanking timeout (e.g., 20m, 30s, 1h) [20m]: ",
                     lambda t: parse_timing(t) is not None, "Enter valid timing.")
        if not timing: timing = "20m"
        timeout_seconds = parse_timing(timing)
        if timeout_seconds:
            config.set('general','blanking_timeout',str(timeout_seconds))
            config.set('general','blanking_pause','false')
            print(f"✓ Screen blanking enabled: {timing}")
        else:
            config.set('general','blanking_timeout','0')
            config.set('general','blanking_pause','true')
    else:
        config.set('general','blanking_timeout','0')
        config.set('general','blanking_pause','true')
        print("✓ Screen blanking disabled")
        
def get_available_themes():
    """Discover available themes on the system and return categorized lists."""
    themes = {
        'icon_themes': [],
        'gtk_themes': [], 
        'cursor_themes': [],
        'desktop_themes': [],  # For Cinnamon desktop/panels
        'wm_themes': []        # For window borders specifically
    }
    
    # Discover icon themes - FIXED: include home directory properly
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
    
    # Discover ALL themes - FIXED: include home directory properly
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
    
    # FIXED: Sort all lists alphabetically
    themes['gtk_themes'] = sorted(list(set(all_themes)))
    themes['desktop_themes'] = sorted(list(set(desktop_themes)))
    themes['wm_themes'] = sorted(list(set(wm_themes)))
    themes['icon_themes'] = sorted(list(set(themes['icon_themes'])))
    
    # Discover cursor themes - FIXED: include home directory and sort
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

def show_numbered_menu(items, title, page_size=20):
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

def configure_workspace_themes(config, section, ws_num, de):
    """Configure themes for a specific workspace based on DE."""
    print(f"\n{'='*40}")
    print(f"THEME CONFIGURATION FOR WORKSPACE {ws_num} ({de.upper()})")
    print(f"{'='*40}")
    
    # For generic/unknown DEs, offer limited theme support
    if de == "unknown":
        print("Generic desktop detected - limited theme support available")
        print("Only basic GTK and icon themes can be set automatically")
        
        enable_themes = ask("Enable basic theme switching? [y/N]: ",
                           lambda v: v.lower() in ['y','n'])
        if enable_themes.lower() != 'y':
            return
        
        themes = get_available_themes()
        
        icon_theme = show_numbered_menu(themes['icon_themes'], "ICON THEMES")
        if icon_theme:
            config[section]['icon_theme'] = icon_theme
            print(f"✓ Icon theme: {icon_theme}")
        
        gtk_theme = show_numbered_menu(themes['gtk_themes'], "GTK THEMES")
        if gtk_theme:
            config[section]['gtk_theme'] = gtk_theme
            print(f"✓ GTK theme: {gtk_theme}")
        
        print("Note: Cursor and window themes may need manual configuration")
        return
    
    # For supported DEs (cinnamon, xfce, gnome, mate)
    themes = get_available_themes()
    
    enable_themes = ask("Enable theme switching for this workspace? [y/N]: ",
                       lambda v: v.lower() in ['y','n'])
    
    if enable_themes.lower() != 'y':
        print("Skipping theme configuration for this workspace")
        return
    
    # SET DEFAULTS FOR ALL THEME TYPES FIRST
    config[section]['icon_theme'] = 'Adwaita'
    config[section]['gtk_theme'] = 'Adwaita'
    config[section]['cursor_theme'] = 'Adwaita'
    
    # Common theme menus for all supported DEs
    icon_theme = show_numbered_menu(themes['icon_themes'], "ICON THEMES")
    if icon_theme:
        config[section]['icon_theme'] = icon_theme
        print(f"✓ Icon theme: {icon_theme}")
    
    gtk_theme = show_numbered_menu(themes['gtk_themes'], "GTK THEMES")
    if gtk_theme:
        config[section]['gtk_theme'] = gtk_theme
        print(f"✓ GTK theme: {gtk_theme}")
    
    cursor_theme = show_numbered_menu(themes['cursor_themes'], "CURSOR THEMES")
    if cursor_theme:
        config[section]['cursor_theme'] = cursor_theme
        print(f"✓ Cursor theme: {cursor_theme}")
    
    # DE-specific configuration
    if de == "cinnamon":
        config[section]['desktop_theme'] = 'Adwaita'
        config[section]['wm_theme'] = 'Adwaita'
        
        desktop_theme = show_numbered_menu(themes['desktop_themes'], "CINNAMON DESKTOP THEMES")
        if desktop_theme:
            config[section]['desktop_theme'] = desktop_theme
            print(f"✓ Desktop theme: {desktop_theme}")
        
        wm_theme = show_numbered_menu(themes['wm_themes'], "CINNAMON WINDOW THEMES")
        if wm_theme:
            config[section]['wm_theme'] = wm_theme
            print(f"✓ Window theme: {wm_theme}")
    
    elif de == "xfce":
        config[section]['wm_theme'] = 'Adwaita'
        
        wm_theme = show_numbered_menu(themes['wm_themes'], "XFCE WINDOW THEMES")
        if wm_theme:
            config[section]['wm_theme'] = wm_theme
            print(f"✓ Window theme: {wm_theme}")
    
    elif de == "gnome":
        config[section]['shell_theme'] = 'Adwaita'
        
        shell_theme = show_numbered_menu(themes['gtk_themes'], "GNOME SHELL THEMES")
        if shell_theme:
            config[section]['shell_theme'] = shell_theme
            print(f"✓ Shell theme: {shell_theme}")
    
    elif de == "mate":
        config[section]['marco_theme'] = 'Adwaita'
        
        marco_theme = show_numbered_menu(themes['wm_themes'], "MATE MARCO THEMES")
        if marco_theme:
            config[section]['marco_theme'] = marco_theme
            print(f"✓ Marco theme: {marco_theme}")
    
    print(f"✓ Theme configuration for workspace {ws_num} complete")

def main():
    """Main setup routine."""
    print(wrap_text("Welcome to AWP initial configuration setup!"))

    de = detect_de()
    print(wrap_text(f"\nDetected desktop environment: {de}"))
    session_type = detect_session_type()
    print(wrap_text(f"\nDetected session type: {session_type}"))

    # Handle existing config
    if os.path.isfile(CONFIG_PATH):
        choice = ask("\nawp_config.ini exists. (c=create new, e=exit): ",
                     lambda v: v.lower() in ['c','e'])
        if choice == 'e':
            print("Exiting without changes.")
            sys.exit(0)
        shutil.copy(CONFIG_PATH,BACKUP_PATH)
        print(f"Backup created: {BACKUP_PATH}")
    else:
        print("No existing configuration, proceeding...")

    if ask("Install required dependencies? (y/n): ",
           lambda v: v.lower() in ['y','n']) == 'y':
        install_dependencies(de)

    config = configparser.ConfigParser()
    config['general'] = {'os_detected':de,'session_type':session_type}
    configure_screen_blanking(config)

    # Logos folder
    if os.path.exists(ICON_DIR): shutil.rmtree(ICON_DIR)
    os.makedirs(ICON_DIR)

    # Workspaces
    n_ws, is_dynamic = get_workspaces(de)
    if n_ws is None:
        n_ws = int(ask("Enter the number of workspaces: ",
                       lambda v: v.isdigit() and int(v)>0))
    else:
        print(f"Detected {n_ws} workspaces.")
    if is_dynamic:
        if ask("Dynamic workspaces detected. Set fixed number? (y/n): ",
               lambda v: v in ['y','n']) == 'y':
            n_ws = int(ask("How many fixed workspaces? ",
                           lambda v: v.isdigit() and int(v)>0))
            set_fixed_workspaces(de, n_ws)
    config['general']['workspaces'] = str(n_ws)

    # Workspace loop
    used_folders=set()
    for i in range(1,n_ws+1):
        section=f"ws{i}"; config[section]={}
        folder_name = ask(f"Folder name for workspace {i} (inside {BASE_FOLDER}): ",
                          lambda v: os.path.isdir(os.path.join(BASE_FOLDER,v))
                          and os.path.join(BASE_FOLDER,v) not in used_folders)
        full_path=os.path.join(BASE_FOLDER,folder_name)
        config[section]['folder']=full_path; used_folders.add(full_path)

        icon_path = ask(f"Icon file path for workspace {i}: ", os.path.isfile)
        _,ext=os.path.splitext(icon_path)
        dest=os.path.join(ICON_DIR,f"{folder_name}{ext}")
        shutil.copy(icon_path,dest); config[section]['icon']=dest
        color=get_icon_color(dest)
        if color:
            config[section]['icon_color']=color
            config[section]['color_variable']=f"{section}_color"

        timing=ask(f"Timing for workspace {i} (e.g. 30s,7m,2h): ",
                   lambda t: parse_timing(t) is not None)
        config[section]['timing']=timing
        mode=ask(f"Cycle mode for workspace {i} (r=random,s=sequential): ",
                 lambda v: v in MODE_MAP)
        config[section]['mode']=MODE_MAP[mode]
        if MODE_MAP[mode]=='sequential':
            order=ask(f"Order for workspace {i} (a,z,m,M): ",
                      lambda v: v in ORDER_MAP)
            config[section]['order']=ORDER_MAP[order]
        else:
            config[section]['order']='n'
        scaling=ask(f"Scaling for workspace {i} (c=centered,s=scaled,z=zoomed): ",
                    lambda v: v in SCALING_MAP)
        config[section]['scaling']=SCALING_MAP[scaling]
        
        configure_workspace_themes(config, section, i, de)

    # Conky
    config['conky']={}
    conky_enabled = ask("Enable AWP info for Conky/lua? (y/n): ",
                        lambda v: v in ['y','n'])
    config['conky']['enabled']='true' if conky_enabled=='y' else 'false'

    # Autostart
    if ask("Create autostart entry so AWP runs at login? (y/n): ",
           lambda v: v in ['y','n'])=='y':
        setup_autostart()
    else:
        print("[ ] Skipped autostart setup.")

    with open(CONFIG_PATH,'w') as f: config.write(f)
    print(f"Configuration saved to {CONFIG_PATH}")

    # Startup script check
    start_script=os.path.expanduser("~/awp/awp_start.sh")
    if os.path.exists(start_script):
        os.chmod(start_script,0o755)
        print(f"[+] Startup script ready: {start_script}")
    else:
        print(f"[!] Warning: {start_script} not found. Please create it.")

    # Final message (no immediate run!)
    print(wrap_text("\nAWP setup is complete. If you enabled autostart, "
                    "AWP will begin automatically on your next login.\n"
                    "You can also start it manually anytime with: ~/awp/awp_start.sh\n"))

    print_keybinding_instructions()

if __name__=="__main__":
    main()
