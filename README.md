# AWP - Automated Wallpaper Program

![AWP Logo](https://img.shields.io/badge/AWP-Automated%20Wallpaper%20Program-blue)
![Python](https://img.shields.io/badge/Python-3.6%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

A professional wallpaper and theme management system for Linux desktop environments.
Per-workspace automated wallpaper rotation with dynamic theme switching.

## 🌟 Features

- **Multi-Desktop Support**: XFCE, Cinnamon, GNOME, MATE, and generic WMs
- **Per-Workspace Configuration**: Different wallpapers and themes for each workspace
- **Smart Automation**: Automatic rotation with customizable timing
- **Theme Management**: Dynamic icon, GTK, cursor, and window theme switching
- **Professional Dashboard**: Graphical configuration interface
- **Manual Controls**: Keyboard shortcuts for navigation and deletion
- **Screen Blanking**: Intelligent power management for XFCE/X11

## 🚀 Quick Start

### Installation
```bash
# Clone the repository
git clone https://github.com/ottowedel-linux/awp-automated-wallpaper.git
cd awp-automated-wallpaper

# Run the setup wizard
python3 awp_setup.py
```

### First-Time Setup
1. Run `python3 awp_setup.py` to create your initial configuration
2. Follow the interactive wizard to configure workspaces
3. The daemon will start automatically on login

### Manual Start
```bash
# Start the daemon manually
python3 awp_daemon.py

# Or use the startup script
./awp_start.sh
```

## 🎮 Usage

### Dashboard (Recommended)
```bash
python3 awp_dab.py
```

### Manual Navigation
```bash
# Next wallpaper
python3 awp_nav.py next

# Previous wallpaper
python3 awp_nav.py prev

# Delete current wallpaper
python3 awp_nav.py delete
```

### Recommended Keybindings
- `Super+Right` → Next wallpaper
- `Super+Left` → Previous wallpaper
- `Super+Delete` → Delete current wallpaper

## 🛠️ Configuration

Edit `~/awp/awp_config.ini` directly or use the dashboard:

```bash
python3 awp_dab.py
```

### Example Configuration
See `awp_config.ini.example` for a complete configuration reference.

## 📁 Project Structure

```
awp-automated-wallpaper/
├── awp_setup.py          # Initial configuration wizard
├── awp_daemon.py         # Main background service
├── awp_dab.py            # Graphical configuration dashboard
├── awp_nav.py            # Manual navigation controls
├── awp_start.sh          # Startup script
├── awp_config.ini.example # Example configuration
└── README.md             # This file
```

## 🌐 Supported Desktop Environments

| DE | Wallpapers | Icons | GTK | Cursors | Window | Desktop |
|----|------------|-------|-----|---------|--------|---------|
| **XFCE** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Cinnamon** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **GNOME** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **MATE** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Generic** | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with Python 3 and PyQt5
- Tested on Linux Mint XFCE, Cinnamon, and other major distributions
- Icons from the system theme collections
