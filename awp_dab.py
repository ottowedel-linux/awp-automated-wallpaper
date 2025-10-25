#!/usr/bin/env python3
"""
AWP - Automated Wallpaper Program
Configuration Dashboard

Graphical interface for configuring workspace-specific wallpaper automation,
theme management, and desktop customization across multiple workspaces.

Features:
- Intuitive workspace configuration with real-time previews
- Automated wallpaper rotation with customizable timing and behavior
- System theme discovery and per-workspace theme switching
- Cross-platform desktop environment support (XFCE, Cinnamon, GNOME, MATE)
- Professional keyboard shortcuts and smart configuration management

Part of the AWP wallpaper automation ecosystem.
"""
import os
os.environ['NO_AT_BRIDGE'] = '1'  # Suppress GTK accessibility warnings

import sys
import shutil
import configparser
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QComboBox, QMessageBox, QTabWidget,
    QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PIL import Image

# =============================================================================
# PATHS AND CONSTANTS
# =============================================================================
AWP_DIR = os.path.expanduser("~/awp")
CONFIG_PATH = os.path.join(AWP_DIR, "awp_config.ini")
ICON_DIR = os.path.join(AWP_DIR, "logos")
BASE_FOLDER = os.path.expanduser("~")
USER_HOME = BASE_FOLDER
DEFAULT_ICON = os.path.join(AWP_DIR, "debian.png")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_icon_color(image_path):
    """
    Extract dominant color from an image file.
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        str: Hex color code of the first non-transparent pixel, or empty string on error
    """
    try:
        with Image.open(image_path) as img:
            rgba = img.convert("RGBA")
            pixels = list(rgba.getdata())
            for r, g, b, a in pixels:
                if a > 0:
                    return f'#{r:02x}{g:02x}{b:02x}'
            return ""
    except Exception:
        return ""

def get_available_themes():
    """
    Discover available themes on the system and return categorized lists.
    
    Returns:
        dict: Categorized theme lists including:
            - icon_themes: Available icon themes
            - gtk_themes: Available GTK themes
            - cursor_themes: Available cursor themes  
            - desktop_themes: Themes with Cinnamon desktop support
            - wm_themes: Themes with window manager components
    """
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

# =============================================================================
# WORKSPACE CONFIGURATION TAB
# =============================================================================

class WorkspaceTab(QWidget):
    """
    Configuration tab for individual workspace settings.
    
    Provides interface for configuring:
    - Wallpaper folder and custom icons
    - Rotation timing and behavior
    - Theme customization per workspace
    - Real-time icon preview
    
    Attributes:
        index (int): Workspace number (1-based)
        parent_window (AWPDashboard): Reference to main dashboard window
    """
    
    def __init__(self, index, parent_window):
        """
        Initialize workspace configuration tab.
        
        Args:
            index (int): Workspace number (1-based)
            parent_window (AWPDashboard): Parent dashboard instance
        """
        super().__init__()
        self.index = index
        self.parent_window = parent_window

        layout = QVBoxLayout()
        layout.setSpacing(10)

        # --- Helper to create consistent combo boxes ---
        def create_theme_like_combo(items):
            """Create standardized combo box for theme-like options."""
            combo = QComboBox()
            combo.setMinimumWidth(250)
            combo.setMaximumWidth(250)
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.NoInsert)
            for text, data in items:
                combo.addItem(text, data)
            return combo

        # === WALLPAPER SETTINGS SECTION ===
        wallpaper_label = QLabel("<b>Wallpaper Settings</b>")
        layout.addWidget(wallpaper_label)

        # Folder selection row
        row = QHBoxLayout()
        row.setSpacing(10)
        lbl = QLabel("Folder:")
        lbl.setFixedWidth(60)
        lbl.setToolTip("Select folder containing wallpaper images for this workspace")
        row.addWidget(lbl)
        self.folder_edit = QLineEdit()
        self.folder_edit.setMaximumWidth(300)
        self.folder_edit.setPlaceholderText(f"{BASE_FOLDER}/...")
        self.folder_edit.setToolTip("Path to folder containing JPEG/PNG wallpapers")
        row.addWidget(self.folder_edit)
        self.folder_btn = QPushButton("Browse")
        self.folder_btn.setFixedWidth(80)
        self.folder_btn.setToolTip("Browse for wallpaper folder")
        self.folder_btn.clicked.connect(self.on_browse_folder)
        row.addWidget(self.folder_btn)
        row.addStretch(1)
        layout.addLayout(row)

        # Icon selection row
        row = QHBoxLayout()
        row.setSpacing(10)
        lbl = QLabel("Icon:")
        lbl.setFixedWidth(60)
        lbl.setToolTip("Custom icon for this workspace (appears in desktop menu)")
        row.addWidget(lbl)
        self.icon_edit = QLineEdit()
        self.icon_edit.setMaximumWidth(300)
        self.icon_edit.setPlaceholderText("Path to icon file...")
        self.icon_edit.setToolTip("Path to custom icon image (PNG, JPG, SVG)")
        self.icon_edit.textChanged.connect(self.update_icon_preview)
        row.addWidget(self.icon_edit)
        self.icon_btn = QPushButton("Browse")
        self.icon_btn.setFixedWidth(80)
        self.icon_btn.setToolTip("Browse for icon image file")
        self.icon_btn.clicked.connect(self.on_browse_icon)
        row.addWidget(self.icon_btn)
        row.addStretch(1)
        layout.addLayout(row)

        # --- Floating Icon Preview ---
        self.icon_preview = QLabel(self)
        self.icon_preview.setFixedSize(64, 64)
        self.icon_preview.setToolTip("Live preview of selected workspace icon")
        # Position it freely
        self.icon_preview.move(335, self.folder_edit.y() + 39)
        self.icon_preview.raise_()

        # === WORKSPACE BEHAVIOR SECTION ===
        behavior_label = QLabel("<b>Workspace Behavior</b>")
        layout.addWidget(behavior_label)

        # Create behavior combo boxes with tooltips
        self.timing_combo = create_theme_like_combo([
            ("30 seconds", "30s"), ("1 minute", "1m"), ("5 minutes", "5m"),
            ("10 minutes", "10m"), ("30 minutes", "30m"), ("1 hour", "1h"),
            ("24 hours", "24h")
        ])
        self.timing_combo.setToolTip("How often to rotate wallpapers automatically")

        self.mode_combo = create_theme_like_combo([
            ("Random", "random"), ("Sequential", "sequential")
        ])
        self.mode_combo.setToolTip("Random: random order each time\nSequential: fixed order through wallpapers")
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)

        self.order_combo = create_theme_like_combo([
            ("A-Z (Alphabetical)", "name_az"), ("Z-A (Reverse)", "name_za"),
            ("Oldest First", "name_old"), ("Newest First", "name_new")
        ])
        self.order_combo.setToolTip("Sort order for sequential mode wallpapers")

        self.scaling_combo = create_theme_like_combo([
            ("Centered", "centered"), ("Scaled", "scaled"), ("Zoomed", "zoomed")
        ])
        self.scaling_combo.setToolTip("How wallpapers fit the screen\nCentered: original size\nScaled: fit to screen\nZoomed: fill screen (cropped)")

        # Add behavior rows with labels and tooltips
        behavior_configs = [
            ("Timing:", self.timing_combo, "Wallpaper rotation interval"),
            ("Mode:", self.mode_combo, "Rotation pattern behavior"),
            ("Order:", self.order_combo, "Sorting method for sequential mode"),
            ("Scaling:", self.scaling_combo, "Wallpaper display style")
        ]
        
        for lbl_text, combo, tooltip in behavior_configs:
            row = QHBoxLayout()
            row.setSpacing(5)
            lbl = QLabel(lbl_text)
            lbl.setFixedWidth(120)
            lbl.setToolTip(tooltip)
            row.addWidget(lbl)
            row.addWidget(combo)
            row.addStretch(1)
            layout.addLayout(row)

        layout.addSpacing(15)

        # === THEME SETTINGS SECTION ===
        theme_label = QLabel("<b>Theme Settings</b>")
        theme_label.setToolTip("Per-workspace desktop theme customization")
        layout.addWidget(theme_label)

        self.theme_controls = {}
        theme_settings = [
            ("Icon Theme", "icon_theme", "icon_themes", "Desktop and application icons"),
            ("GTK Theme", "gtk_theme", "gtk_themes", "Application window appearance"),
            ("Cursor Theme", "cursor_theme", "cursor_themes", "Mouse cursor style"),
            ("Desktop Theme", "desktop_theme", "desktop_themes", "Cinnamon desktop panels and widgets"),
            ("Window Theme", "wm_theme", "wm_themes", "Window borders and controls")
        ]
        
        available_themes = get_available_themes()
        for label, key, theme_type, tooltip in theme_settings:
            row = QHBoxLayout()
            row.setSpacing(5)
            lbl = QLabel(f"{label}:")
            lbl.setFixedWidth(120)
            lbl.setToolTip(tooltip)
            row.addWidget(lbl)
            combo = create_theme_like_combo([("(Not set)", "")])
            combo.setToolTip(f"Select {label.lower()} for this workspace")
            for theme in available_themes.get(theme_type, []):
                combo.addItem(theme)
            row.addWidget(combo)
            row.addStretch(1)
            self.theme_controls[key] = combo
            layout.addLayout(row)

        # Initialize theme availability based on current DE
        self.update_theme_availability()
        
        layout.addStretch()
        self.setLayout(layout)
        self.update_icon_preview()

    def update_theme_availability(self):
        """Update theme dropdown availability based on current DE."""
        de = self.parent_window.get_current_de()
        
        # Define which themes are applicable for each DE
        theme_rules = {
            "xfce": {
                'icon_theme': True, 'gtk_theme': True, 'cursor_theme': True,
                'desktop_theme': False, 'wm_theme': True
            },
            "cinnamon": {
                'icon_theme': True, 'gtk_theme': True, 'cursor_theme': True,
                'desktop_theme': True, 'wm_theme': True
            },
            "gnome": {
                'icon_theme': True, 'gtk_theme': True, 'cursor_theme': True,
                'desktop_theme': False, 'wm_theme': False
            },
            "mate": {
                'icon_theme': True, 'gtk_theme': True, 'cursor_theme': True,
                'desktop_theme': False, 'wm_theme': True
            },
            "generic": {
                'icon_theme': False, 'gtk_theme': True, 'cursor_theme': False,
                'desktop_theme': False, 'wm_theme': False
            }
        }
        
        rules = theme_rules.get(de, theme_rules["generic"])
        
        # Apply to each theme control
        theme_mapping = {
            'icon_theme': 'Icon Theme',
            'gtk_theme': 'GTK Theme', 
            'cursor_theme': 'Cursor Theme',
            'desktop_theme': 'Desktop Theme',
            'wm_theme': 'Window Theme'
        }
        
        for theme_key, enabled in rules.items():
            if theme_key in self.theme_controls:
                combo = self.theme_controls[theme_key]
                combo.setEnabled(enabled)
                
                # Set tooltip to indicate why it's disabled
                if enabled:
                    combo.setToolTip(f"Select {theme_mapping[theme_key].lower()} for this workspace")
                else:
                    combo.setToolTip(f"{theme_mapping[theme_key]} not applicable for {de.upper()}")
                
    # --- SIGNAL HANDLERS ---
    
    def on_browse_folder(self):
        """Browse and select wallpaper folder for this workspace."""
        p = QFileDialog.getExistingDirectory(self, f"Select folder for WS{self.index}", BASE_FOLDER)
        if p:
            self.folder_edit.setText(p)

    def on_browse_icon(self):
        """Browse and select custom icon for this workspace."""
        start_dir = ICON_DIR if os.path.exists(ICON_DIR) else BASE_FOLDER
        f, _ = QFileDialog.getOpenFileName(
            self, f"Select icon for WS{self.index}", start_dir, 
            "Images (*.png *.jpg *.jpeg *.svg *.gif)"
        )
        if f:
            self.icon_edit.setText(f)

    def on_mode_changed(self, text):
        """
        Adjust order combo behavior based on rotation mode.
        
        Args:
            text (str): Current mode selection ("Random" or "Sequential")
        """
        if text == "Random":
            # Force 'n' for random mode
            found_n = False
            for i in range(self.order_combo.count()):
                if self.order_combo.itemData(i) == "n":
                    found_n = True
                    self.order_combo.setCurrentIndex(i)
                    break
            if not found_n:
                self.order_combo.addItem("Random (n)", "n")
                self.order_combo.setCurrentIndex(self.order_combo.count() - 1)
            self.order_combo.setEnabled(False)
        else:
            self.order_combo.setEnabled(True)
            # Remove 'n' if exists
            for i in range(self.order_combo.count()):
                if self.order_combo.itemData(i) == "n":
                    self.order_combo.removeItem(i)
                    break
            self.order_combo.setCurrentIndex(0)

    def update_icon_preview(self):
        """Update live preview of selected workspace icon."""
        path = self.icon_edit.text().strip()
        if not path or not os.path.isfile(path):
            path = DEFAULT_ICON if os.path.isfile(DEFAULT_ICON) else ""
        if path:
            pix = QPixmap(path)
            self.icon_preview.setPixmap(pix.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.icon_preview.clear()

    # --- CONFIG LOAD / SAVE ---
    
    def load_from_config(self, config_section):
        """
        Load settings from configuration section.
        
        Args:
            config_section (SectionProxy): Configuration section for this workspace
        """
        # Basic settings
        self.folder_edit.setText(config_section.get('folder', ''))
        self.icon_edit.setText(config_section.get('icon', ''))

        # Timing
        timing = config_section.get('timing', '5m')
        for i in range(self.timing_combo.count()):
            if self.timing_combo.itemData(i) == timing:
                self.timing_combo.setCurrentIndex(i)
                break
        else:
            self.timing_combo.setCurrentText("5 minutes")

        # Mode and order
        mode = config_section.get('mode', 'random')
        self.mode_combo.setCurrentText(mode.title())
        order = config_section.get('order', 'name_az')
        
        if mode == "random":
            found_n = False
            for i in range(self.order_combo.count()):
                if self.order_combo.itemData(i) == "n":
                    found_n = True
                    self.order_combo.setCurrentIndex(i)
                    break
            if not found_n:
                self.order_combo.addItem("Random (n)", "n")
                self.order_combo.setCurrentIndex(self.order_combo.count() - 1)
            self.order_combo.setEnabled(False)
        else:
            for i in range(self.order_combo.count()):
                if self.order_combo.itemData(i) == order:
                    self.order_combo.setCurrentIndex(i)
                    break
            self.order_combo.setEnabled(True)

        # Scaling
        scaling = config_section.get('scaling', 'scaled')
        for i in range(self.scaling_combo.count()):
            if self.scaling_combo.itemData(i) == scaling:
                self.scaling_combo.setCurrentIndex(i)
                break

        # Theme settings
        for key, combo in self.theme_controls.items():
            theme_value = config_section.get(key, '')
            if theme_value:
                found = False
                for i in range(combo.count()):
                    if combo.itemText(i) == theme_value:
                        combo.setCurrentIndex(i)
                        found = True
                        break
                if not found:
                    combo.addItem(theme_value)
                    combo.setCurrentText(theme_value)
            else:
                combo.setCurrentIndex(0)  # "(Not set)"

        # Update theme availability after loading values
        self.update_theme_availability()
        
        self.update_icon_preview()

    def save_to_config(self, config_section):
        """
        Save settings to configuration section.
        
        Args:
            config_section (SectionProxy): Configuration section for this workspace
        """
        config_section['folder'] = self.folder_edit.text().strip()
        config_section['icon'] = self.icon_edit.text().strip()
        config_section['timing'] = self.timing_combo.currentData() or '5m'
        config_section['mode'] = self.mode_combo.currentText().lower()
        config_section['order'] = self.order_combo.currentData() or 'name_az'
        config_section['scaling'] = self.scaling_combo.currentData() or 'scaled'

        # Theme settings
        for key, combo in self.theme_controls.items():
            if combo.currentText() and combo.currentText() != "(Not set)":
                config_section[key] = combo.currentText()
            elif key in config_section:
                del config_section[key]

# =============================================================================
# MAIN DASHBOARD WINDOW
# =============================================================================

class AWPDashboard(QWidget):
    """
    Main AWP Configuration Dashboard.
    
    Provides comprehensive interface for managing all AWP settings including:
    - Desktop environment and session configuration
    - Screen blanking controls
    - Workspace management and count
    - Individual workspace configuration tabs
    
    Features professional keyboard shortcuts and smart change detection.
    """
    
    def __init__(self):
        """Initialize dashboard and load existing configuration."""
        super().__init__()
        self.setWindowTitle("AWP Dashboard - Configuration Editor")
        self.resize(500, 670)

        if not os.path.exists(CONFIG_PATH):
            QMessageBox.critical(self, "Error", 
                f"Config file not found: {CONFIG_PATH}\n\nPlease run awp_setup.py first to create the initial configuration.")
            sys.exit(1)

        self.config = configparser.ConfigParser()
        self.config.read(CONFIG_PATH)

        self.workspace_tabs = []
        self.setup_ui()
        self.setup_keybindings()
        self.load_config()

    def setup_ui(self):
        """Initialize and arrange all user interface components."""
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("<h2>AWP Dashboard - Configuration Editor</h2>")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Tab widget
        self.tab_widget = QTabWidget()
                
        # General tab first
        general_tab = self.create_general_tab()
        self.tab_widget.addTab(general_tab, "General Settings")

        # Workspace tabs
        num_workspaces = int(self.config['general'].get('workspaces', 3))
        for i in range(1, num_workspaces + 1):
            tab = WorkspaceTab(i, self)
            self.workspace_tabs.append(tab)
            self.tab_widget.addTab(tab, f"Workspace {i}")

        layout.addWidget(self.tab_widget)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch(0)
        
        self.backup_btn = QPushButton("Backup Config")
        self.backup_btn.setFixedHeight(30)
        self.backup_btn.setFixedWidth(150)
        self.backup_btn.setToolTip("Create backup of current configuration (Ctrl+B)")
        self.backup_btn.clicked.connect(self.backup_config)
        button_layout.addWidget(self.backup_btn)
        
        button_layout.addSpacing(20)

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setFixedHeight(30)
        self.save_btn.setFixedWidth(150)
        self.save_btn.setToolTip("Save all configuration changes (Ctrl+S)")
        self.save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(self.save_btn)
        
        button_layout.addSpacing(20)

        self.exit_btn = QPushButton("Quit")
        self.exit_btn.setFixedHeight(30)
        self.exit_btn.setFixedWidth(150)
        self.exit_btn.setToolTip("Exit application (Ctrl+Q)")
        self.exit_btn.clicked.connect(self.close)
        button_layout.addWidget(self.exit_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def setup_keybindings(self):
        """
        Configure professional keyboard shortcuts.
        
        Shortcuts:
        - Ctrl+S: Save configuration changes
        - Ctrl+B: Create configuration backup  
        - Ctrl+Q: Quit application
        """
        self.save_btn.setShortcut("Ctrl+S")
        self.backup_btn.setShortcut("Ctrl+B")  
        self.exit_btn.setShortcut("Ctrl+Q")

    def create_general_tab(self):
        """Create and configure the general settings tab."""
        tab = QWidget()
        layout = QVBoxLayout()

        # Desktop Environment and Session Type
        de_row = QHBoxLayout()
        de_row.addWidget(QLabel("Desktop Environment:"))
        self.de_combo = QComboBox()
        self.de_combo.setMaximumWidth(200)
        self.de_combo.addItems(["xfce", "gnome", "cinnamon", "mate", "generic", "unknown"])
        self.de_combo.setToolTip("Select your desktop environment for proper theme integration")
        self.de_combo.currentTextChanged.connect(self.on_de_changed)
        de_row.addWidget(self.de_combo)
        de_row.addStretch()
        layout.addLayout(de_row)

        session_row = QHBoxLayout()
        session_row.addWidget(QLabel("Session Type:"))
        self.session_combo = QComboBox()
        self.session_combo.setMaximumWidth(200)
        self.session_combo.addItems(["x11", "wayland"])
        self.session_combo.setToolTip("Display server protocol (X11 or Wayland)")
        session_row.addWidget(self.session_combo)
        session_row.addStretch()
        layout.addLayout(session_row)

        # Screen Blanking Section
        layout.addWidget(QLabel("<b>Screen Blanking</b>"))
        blanking_row = QHBoxLayout()
        blanking_row.addWidget(QLabel("Timeout:"))
        self.blanking_combo = QComboBox()
        self.blanking_combo.setMaximumWidth(150)
        self.blanking_combo.addItem("Disabled", "0")
        self.blanking_combo.addItem("30 seconds", "30")
        self.blanking_combo.addItem("1 minute", "60")
        self.blanking_combo.addItem("5 minutes", "300")
        self.blanking_combo.addItem("10 minutes", "600")
        self.blanking_combo.addItem("20 minutes", "1200")
        self.blanking_combo.addItem("30 minutes", "1800")
        self.blanking_combo.addItem("1 hour", "3600")
        self.blanking_combo.setToolTip("Time before screen blanks/sleeps (XFCE/X11 only)")
        self.blanking_combo.currentTextChanged.connect(self.on_blanking_changed)
        blanking_row.addWidget(self.blanking_combo)

        self.blanking_pause_cb = QCheckBox("Paused")
        self.blanking_pause_cb.setToolTip("Temporarily disable screen blanking")
        self.blanking_pause_cb.toggled.connect(self.on_blanking_pause_toggled)
        blanking_row.addWidget(self.blanking_pause_cb)
        blanking_row.addStretch()
        layout.addLayout(blanking_row)

        # Workspace Management Section
        layout.addWidget(QLabel("<b>Workspace Management</b>"))
        ws_row = QHBoxLayout()
        ws_row.addWidget(QLabel("Number of workspaces:"))
        self.ws_count_combo = QComboBox()
        self.ws_count_combo.setMaximumWidth(80)
        for i in range(1, 9):
            self.ws_count_combo.addItem(str(i), str(i))
        self.ws_count_combo.setToolTip("Total number of workspaces to configure (1-8)")
        self.ws_count_combo.currentTextChanged.connect(self.on_workspace_count_changed)
        ws_row.addWidget(self.ws_count_combo)
        ws_row.addStretch()
        layout.addLayout(ws_row)

        layout.addStretch()
        tab.setLayout(layout)
        return tab

    def get_current_de(self):
        """Get current desktop environment selection."""
        return self.de_combo.currentText().lower()

    def on_de_changed(self, new_de):
        """Update all workspace tabs when DE changes."""
        for tab in self.workspace_tabs:
            if hasattr(tab, 'update_theme_availability'):
                tab.update_theme_availability()

    def on_blanking_changed(self, text):
        """
        Handle blanking timeout changes.
        
        Args:
            text (str): New timeout selection
        """
        if text == "Disabled":
            self.blanking_pause_cb.setChecked(True)
            self.blanking_pause_cb.setEnabled(True)
        else:
            self.blanking_pause_cb.setChecked(False)
            self.blanking_pause_cb.setEnabled(True)

    def on_blanking_pause_toggled(self, checked):
        """
        Handle blanking pause toggle.
        
        Args:
            checked (bool): Whether blanking is paused
        """
        if checked:
            self.blanking_combo.setCurrentText("Disabled")
        else:
            # Set to a reasonable default when unpausing
            self.blanking_combo.setCurrentText("20 minutes")

    def on_workspace_count_changed(self, new_count):
        """
        Update workspace tabs when count changes.
        
        Args:
            new_count (str): New workspace count
        """
        if not new_count:
            return
            
        new_count = int(new_count)
        current_count = len(self.workspace_tabs)
        
        if new_count > current_count:
            # Add new tabs
            for i in range(current_count + 1, new_count + 1):
                tab = WorkspaceTab(i, self)
                self.workspace_tabs.append(tab)
                self.tab_widget.addTab(tab, f"Workspace {i}")
        elif new_count < current_count:
            # Remove extra tabs
            for i in range(current_count, new_count, -1):
                self.tab_widget.removeTab(i)
                self.workspace_tabs.pop()

    def load_config(self):
        """Load all settings from configuration file."""
        # General settings
        general = self.config['general']
        self.de_combo.setCurrentText(general.get('os_detected', 'unknown'))
        self.session_combo.setCurrentText(general.get('session_type', 'x11'))
    
        # Screen blanking settings
        blanking_timeout = general.get('blanking_timeout', '0')
        blanking_paused = general.get('blanking_pause', 'false').lower() == 'true'
    
        if blanking_paused or blanking_timeout == '0':
            self.blanking_combo.setCurrentText("Disabled")
            self.blanking_pause_cb.setChecked(True)
        else:
            for i in range(self.blanking_combo.count()):
                if self.blanking_combo.itemData(i) == blanking_timeout:
                    self.blanking_combo.setCurrentIndex(i)
                    break
            self.blanking_pause_cb.setChecked(False)
    
        # Workspace count
        ws_count = general.get('workspaces', '3')
        self.ws_count_combo.setCurrentText(ws_count)

        # Workspace settings
        for i, tab in enumerate(self.workspace_tabs, 1):
            section_name = f"ws{i}"
            if section_name in self.config:
                tab.load_from_config(self.config[section_name])

    def save_config(self):
        """
        Perform smart configuration save with change detection.
        
        Features:
        - Only updates actually changed values
        - Automatic icon copying and color extraction
        - Creates configuration backups
        - Validates changes before saving
        
        Raises:
            Exception: If configuration file operations fail
        """
        try:
            # Read current config
            current_config = configparser.ConfigParser()
            current_config.read(CONFIG_PATH)
    
            # Create a copy to modify
            new_config = configparser.ConfigParser()
            new_config.read(CONFIG_PATH)
    
            has_changes = False
    
            # Update general section if changed
            if self.has_general_changes(current_config):
                has_changes = True
                new_config['general']['os_detected'] = self.de_combo.currentText()
                new_config['general']['session_type'] = self.session_combo.currentText()
                if self.blanking_pause_cb.isChecked():
                    new_config['general']['blanking_timeout'] = '0'
                    new_config['general']['blanking_pause'] = 'true'
                else:
                    new_config['general']['blanking_timeout'] = str(self.blanking_combo.currentData() or '0')
                    new_config['general']['blanking_pause'] = 'false'
                new_config['general']['workspaces'] = self.ws_count_combo.currentText()
    
            # Ensure logos directory exists
            os.makedirs(ICON_DIR, exist_ok=True)
    
            # Update workspace sections if changed
            for i, tab in enumerate(self.workspace_tabs, 1):
                section_name = f"ws{i}"
                old_section = current_config[section_name] if current_config.has_section(section_name) else {}
            
                if self.has_workspace_changes(tab, old_section):
                    has_changes = True
                    if not new_config.has_section(section_name):
                        new_config.add_section(section_name)
                
                    # Handle icon copying and color extraction
                    folder_path = tab.folder_edit.text().strip()
                    folder_name = os.path.basename(folder_path.rstrip("/")) if folder_path else f"ws{i}"
                    old_icon_path = old_section.get('icon', '')
                    new_icon_path = tab.icon_edit.text().strip()
                    icon_changed = (new_icon_path != old_icon_path)
                
                    if icon_changed and new_icon_path and os.path.isfile(new_icon_path):
                        # Copy new icon to logos folder
                        _, ext = os.path.splitext(new_icon_path)
                        if not ext:
                            ext = ".png"
                        dest_icon = os.path.join(ICON_DIR, f"{folder_name}{ext}")
                    
                        try:
                            shutil.copy(new_icon_path, dest_icon)
                            final_icon_path = dest_icon
                        except Exception as e:
                            print(f"Warning: Could not copy icon for {section_name}: {e}")
                            final_icon_path = new_icon_path
                    else:
                        final_icon_path = old_icon_path if old_icon_path and os.path.isfile(old_icon_path) else DEFAULT_ICON
                
                    # Save workspace config
                    tab.save_to_config(new_config[section_name])
                    new_config[section_name]['icon'] = final_icon_path
                
                    # Update icon color
                    color = get_icon_color(final_icon_path)
                    if color:
                        new_config[section_name]['icon_color'] = color
                        new_config[section_name]['color_variable'] = f"{section_name}_color"
                    else:
                        new_config[section_name]['icon_color'] = old_section.get('icon_color', '')
                        new_config[section_name]['color_variable'] = old_section.get('color_variable', '')
    
            if not has_changes:
                QMessageBox.information(self, "No Changes", "No changes detected.")
                return
    
            # Backup and save
            if os.path.exists(CONFIG_PATH):
                shutil.copy(CONFIG_PATH, CONFIG_PATH + ".bak")
        
            with open(CONFIG_PATH, 'w') as f:
                new_config.write(f)
        
            # Reload config to update UI
            self.config.read(CONFIG_PATH)
            self.load_config()
        
            QMessageBox.information(self, "Success", "Configuration saved!")
    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{str(e)}")

    def get_new_general_value(self, key):
        """
        Get the new value for a general setting.
        
        Args:
            key (str): Setting key name
            
        Returns:
            str: New value for the setting
        """
        if key == 'os_detected':
            return self.de_combo.currentText()
        elif key == 'session_type':
            return self.session_combo.currentText()
        elif key == 'blanking_timeout':
            if self.blanking_pause_cb.isChecked():
                return '0'
            else:
                return str(self.blanking_combo.currentData() or '0')
        elif key == 'blanking_pause':
            return str(self.blanking_pause_cb.isChecked()).lower()
        elif key == 'workspaces':
            return self.ws_count_combo.currentText()
        return ''
        
    def has_general_changes(self, current_config):
        """
        Check if general section has changes.
        
        Args:
            current_config (ConfigParser): Current configuration
            
        Returns:
            bool: True if general section has changes
        """
        if not current_config.has_section('general'):
            return True
        
        general = current_config['general']
        current_de = general.get('os_detected', '')
        current_session = general.get('session_type', '')
        current_blanking_timeout = general.get('blanking_timeout', '0')
        current_blanking_pause = general.get('blanking_pause', 'false')
        current_workspaces = general.get('workspaces', '3')
    
        new_de = self.de_combo.currentText()
        new_session = self.session_combo.currentText()
        new_workspaces = self.ws_count_combo.currentText()
    
        # Handle blanking safely
        if self.blanking_pause_cb.isChecked():
            new_blanking_timeout = '0'
            new_blanking_pause = 'true'
        else:
            new_blanking_timeout = str(self.blanking_combo.currentData() or '0')
            new_blanking_pause = 'false'
    
        return (new_de != current_de or
                new_session != current_session or
                new_blanking_timeout != current_blanking_timeout or
                new_blanking_pause != current_blanking_pause or
                new_workspaces != current_workspaces)

    def has_workspace_changes(self, tab, old_section):
        """
        Check if workspace tab has any changes.
        
        Args:
            tab (WorkspaceTab): Workspace tab to check
            old_section (SectionProxy): Original configuration section
            
        Returns:
            bool: True if workspace has changes
        """
        # Check basic settings
        if (tab.folder_edit.text().strip() != old_section.get('folder', '') or
            tab.icon_edit.text().strip() != old_section.get('icon', '') or
            (tab.timing_combo.currentData() or '5m') != old_section.get('timing', '5m') or
            tab.mode_combo.currentText().lower() != old_section.get('mode', 'random') or
            (tab.order_combo.currentData() or 'name_az') != old_section.get('order', 'name_az') or
            (tab.scaling_combo.currentData() or 'scaled') != old_section.get('scaling', 'scaled')):
            return True
        
        # Check theme settings
        for key, combo in tab.theme_controls.items():
            new_theme = combo.currentText() if combo.currentText() != "(Not set)" else ""
            old_theme = old_section.get(key, '')
            if new_theme != old_theme:
                return True
        
        return False

    def backup_config(self):
        """Create backup of current configuration file."""
        if os.path.exists(CONFIG_PATH):
            backup_path = CONFIG_PATH + ".backup"
            shutil.copy(CONFIG_PATH, backup_path)
            QMessageBox.information(self, "Backup Created", 
                                  f"Configuration backed up to:\n{backup_path}")

# =============================================================================
# APPLICATION ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """Main application entry point."""
    app = QApplication(sys.argv)
    window = AWPDashboard()
    window.show()
    sys.exit(app.exec_())
