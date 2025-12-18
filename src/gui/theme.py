"""Theme configuration for Desktop GUI."""

import customtkinter as ctk

# Brutalist dark theme colors
COLORS = {
    "background": "#1a1a1a",
    "surface": "#2d2d2d",
    "surface_light": "#3d3d3d",
    "primary": "#00ff00",
    "primary_dim": "#00aa00",
    "accent": "#ff6600",
    "text": "#e0e0e0",
    "text_muted": "#888888",
    "text_dim": "#666666",
    "error": "#ff3333",
    "warning": "#ffaa00",
    "success": "#00ff00",
    "info": "#3498db",
}

# Hold type colors
HOLD_COLORS = {
    "litigation": "#ff3333",
    "ediscovery": "#9b59b6",
    "retention": "#3498db",
    "none": "#00ff00",
}


def apply_theme() -> None:
    """Apply the brutalist dark theme to CustomTkinter."""
    # Set appearance mode
    ctk.set_appearance_mode("dark")

    # Set default color theme
    ctk.set_default_color_theme("dark-blue")


def get_button_colors(variant: str = "default") -> dict:
    """Get button colors for a variant.

    Args:
        variant: Button variant (default, primary, danger)

    Returns:
        Dictionary with fg_color, hover_color, text_color
    """
    if variant == "primary":
        return {
            "fg_color": COLORS["primary_dim"],
            "hover_color": COLORS["primary"],
            "text_color": COLORS["background"],
        }
    elif variant == "danger":
        return {
            "fg_color": COLORS["error"],
            "hover_color": "#ff5555",
            "text_color": COLORS["text"],
        }
    else:
        return {
            "fg_color": COLORS["surface_light"],
            "hover_color": COLORS["surface"],
            "text_color": COLORS["text"],
        }


def get_entry_colors() -> dict:
    """Get entry/input field colors.

    Returns:
        Dictionary with color settings
    """
    return {
        "fg_color": COLORS["surface"],
        "border_color": COLORS["surface_light"],
        "text_color": COLORS["text"],
        "placeholder_text_color": COLORS["text_dim"],
    }


def get_label_colors(style: str = "default") -> dict:
    """Get label colors for a style.

    Args:
        style: Label style (default, title, muted, error, success)

    Returns:
        Dictionary with text_color
    """
    if style == "title":
        return {"text_color": COLORS["primary"]}
    elif style == "muted":
        return {"text_color": COLORS["text_muted"]}
    elif style == "error":
        return {"text_color": COLORS["error"]}
    elif style == "success":
        return {"text_color": COLORS["success"]}
    elif style == "warning":
        return {"text_color": COLORS["warning"]}
    else:
        return {"text_color": COLORS["text"]}
