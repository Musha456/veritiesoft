# -*- coding: utf-8 -*-
import base64
import io
from PIL import Image
from odoo import api, fields, models, _


class HotelHotel(models.Model):
    _inherit = "hotel.hotel"

    primary_color = fields.Char(
        string="Primary Brand Color",
        default="#1e3a8a",
        help="Primary color for booking engine headers, buttons, and highlights (Hex: #RRGGBB).",
    )

    secondary_color = fields.Char(
        string="Secondary Brand Color",
        default="#2563eb",
        help="Secondary accent color for gradients and secondary buttons (Hex: #RRGGBB).",
    )

    accent_color = fields.Char(
        string="Accent Gold / Warm Color",
        default="#f59e0b",
        help="Color for ratings, special badges, and call-to-actions.",
    )

    theme_style = fields.Text(
        string="Theme Dynamic CSS Variables",
        compute="_compute_theme_style",
        help="Pre-computed CSS variables block for web templates.",
    )

    @api.depends("primary_color", "secondary_color", "accent_color")
    def _compute_theme_style(self):
        for hotel in self:
            p = hotel.primary_color or "#1e3a8a"
            s = hotel.secondary_color or "#2563eb"
            a = hotel.accent_color or "#f59e0b"
            hotel.theme_style = (
                f"--hotel-primary: {p}; "
                f"--hotel-secondary: {s}; "
                f"--hotel-accent: {a}; "
                f"--hotel-primary-rgb: {self._hex_to_rgb(p)};"
            )

    @staticmethod
    def _hex_to_rgb(hex_str):
        hex_clean = hex_str.lstrip("#")
        if len(hex_clean) == 6:
            try:
                r, g, b = tuple(int(hex_clean[i:i + 2], 16) for i in (0, 2, 4))
                return f"{r}, {g}, {b}"
            except Exception:
                pass
        return "30, 58, 138"

    @api.onchange("logo")
    def _onchange_logo_extract_colors(self):
        """Automatically detect dominant colors from uploaded hotel logo."""
        if self.logo:
            colors = self._extract_dominant_colors(self.logo)
            if colors:
                self.primary_color = colors[0]
                if len(colors) > 1:
                    self.secondary_color = colors[1]

    def action_extract_theme_colors(self):
        """Action button on hotel form to re-extract brand colors from logo."""
        self.ensure_one()
        if not self.logo:
            return
        colors = self._extract_dominant_colors(self.logo)
        if colors:
            self.primary_color = colors[0]
            if len(colors) > 1:
                self.secondary_color = colors[1]

    def _extract_dominant_colors(self, image_base64, max_colors=2):
        """Extract vibrant dominant colors from base64 image bytes."""
        try:
            image_data = base64.b64decode(image_base64)
            img = Image.open(io.BytesIO(image_data))
            img = img.convert("RGBA")
            img.thumbnail((120, 120))

            color_counts = {}
            for r, g, b, a in img.getdata():
                # Ignore transparent and near-white/near-black background pixels
                if a < 128:
                    continue
                if (r > 240 and g > 240 and b > 240) or (r < 15 and g < 15 and b < 15):
                    continue

                # Quantize slightly to group similar shades
                qr = (r // 16) * 16
                qg = (g // 16) * 16
                qb = (b // 16) * 16
                color_counts[(qr, qg, qb)] = color_counts.get((qr, qg, qb), 0) + 1

            if not color_counts:
                return ["#1e3a8a", "#2563eb"]

            sorted_colors = sorted(color_counts.items(), key=lambda x: x[1], reverse=True)
            hex_colors = []
            for (r, g, b), count in sorted_colors[:max_colors]:
                hex_colors.append(f"#{r:02x}{g:02x}{b:02x}")

            return hex_colors
        except Exception:
            return ["#1e3a8a", "#2563eb"]
