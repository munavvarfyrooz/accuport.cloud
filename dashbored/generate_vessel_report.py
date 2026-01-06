#!/usr/bin/env python3
"""
PDF Report Generator for Vessel Analysis
Generate comprehensive PDF reports with custom backgrounds and matplotlib charts
"""

import argparse
import sys
import os
import io
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader

# Add parent directory to path to import models
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import (
    get_all_limits_for_equipment,
    get_vessel_by_id,
    get_measurements_by_equipment_name,
    get_measurements_for_scavenge_drains,
    get_alerts_for_vessel
)
from report_utils import (
    create_legend_only_chart,
    get_limits_for_pdf,
    create_line_chart_by_unit,
    create_multi_line_chart,
    create_scatter_chart,
    create_summary_table,
    create_header_style,
    create_section_style,
    create_subsection_style,
    format_date,
    format_date_short,
    get_status_color,
    BOILER_COLORS,
    MAIN_ENGINE_COLORS,
    AUX_ENGINE_COLORS,
    GENERIC_COLORS
)

from vessel_details_models import get_vessel_details_for_display
# Static file paths
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'img')
COVER_IMAGE = os.path.join(STATIC_DIR, 'cover.jpg')
CONTENT_IMAGE = os.path.join(STATIC_DIR, 'content.jpg')
BACK_IMAGE = os.path.join(STATIC_DIR, 'back.jpg')

# Available sections for selection
AVAILABLE_SECTIONS = {
    'boiler': {
        'name': 'Boiler Water',
        'generator': 'generate_boiler_section'
    },
    'main_engines': {
        'name': 'Main Engines',
        'generator': 'generate_main_engine_section'
    },
    'aux_engines': {
        'name': 'Auxiliary Engines',
        'generator': 'generate_aux_engine_section'
    },
    'potable_water': {
        'name': 'Potable Water',
        'generator': 'generate_potable_water_section'
    },
    'treated_sewage': {
        'name': 'Treated Sewage',
        'generator': 'generate_treated_sewage_section'
    },
    'central_cooling': {
        'name': 'Central Cooling',
        'generator': 'generate_central_cooling_section'
    },
    'ballast_water': {
        'name': 'Ballast Water',
        'generator': 'generate_ballast_water_section'
    },
    'egcs': {
        'name': 'EGCS',
        'generator': 'generate_egcs_section'
    }
}


def sanitize_unit_for_pdf(unit_str):
    """Replace Unicode superscript/subscript characters with ASCII equivalents for PDF rendering."""
    if not unit_str:
        return unit_str
    replacements = {
        '⁻': '-',   # superscript minus
        '⁺': '+',   # superscript plus
        '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
        '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
        '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
        '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
    }
    result = unit_str
    for unicode_char, ascii_char in replacements.items():
        result = result.replace(unicode_char, ascii_char)
    return result


class ReportPDFGenerator:
    """PDF Generator with custom page backgrounds"""
    
    def __init__(self, output, vessel_name, start_date, end_date, imo_number=None, company_name=None):
        self.output = output
        self.vessel_name = vessel_name
        self.start_date = start_date
        self.end_date = end_date
        self.imo_number = imo_number or ''
        self.company_name = company_name or ''
        self.c = canvas.Canvas(output, pagesize=letter)
        self.width, self.height = letter
        self.current_section = None
        # Content area starts below green header bar (about 90pt from top)
        self.y_position = self.height - 115  
        self.margin_left = 25
        self.margin_right = 25
        self.content_width = self.width - self.margin_left - self.margin_right
        # Orange header bar height is about 90pt from top
        self.header_bar_bottom = self.height - 100
        
        # Grid layout for 2x2 charts
        self.grid_position = 0  # 0=top-left, 1=top-right, 2=bot-left, 3=bot-right
        self.grid_row_y = None  # Y position for current grid row
        self.section_page = 1  # Page counter within section
        
    def draw_cover_page(self):
        """Draw cover page with background image and vessel info in blue block"""
        # Draw background image
        if os.path.exists(COVER_IMAGE):
            self.c.drawImage(COVER_IMAGE, 0, 0, width=self.width, height=self.height,
                            preserveAspectRatio=False)
        
        # Right margin for text (from right edge)
        right_margin = 30
        text_x = self.width - right_margin
        
        # Vessel info positioned in the blue block area (center-right of page)
        # Text sizes increased by 250%
        vessel_y = self.height * 0.52      # Vessel name at top of blue block
        imo_y = vessel_y - 38              # IMO below vessel name
        company_y = imo_y - 32             # Company below IMO
        
        # Date period in white space below blue block - 2 lines
        report_label_y = self.height * 0.32  # "Onboard Test Report" label
        date_range_y = report_label_y - 20   # Date range on next line

        # Draw vessel name - WHITE text in blue block (75% of 45 = 34pt)
        self.c.setFont('Helvetica-Bold', 34)
        self.c.setFillColorRGB(1, 1, 1)  # White color
        self.c.drawRightString(text_x, vessel_y, self.vessel_name)

        # Draw IMO number - WHITE text (75% of 35 = 26pt)
        if self.imo_number:
            self.c.setFont("Helvetica", 13)
            self.c.setFillColorRGB(1, 1, 1)  # White color
            self.c.drawRightString(text_x, imo_y, f"IMO: {self.imo_number}")

        # Draw company name - WHITE text (75% of 30 = 22pt)
        if self.company_name:
            self.c.setFont("Helvetica", 15)
            self.c.setFillColorRGB(1, 1, 1)  # White color
            self.c.drawRightString(text_x, company_y, self.company_name)

        # Draw "Onboard Test Report" label and date range - GREY text (2 lines)
        self.c.setFont('Helvetica', 12)
        self.c.setFillColorRGB(0.4, 0.4, 0.4)  # Grey color
        self.c.drawRightString(text_x, report_label_y, "Onboard Test Report")
        self.c.setFont('Helvetica-Bold', 14)
        date_range = f"{format_date_short(self.start_date)} - {format_date_short(self.end_date)}"
        self.c.drawRightString(text_x, date_range_y, date_range)
        
        self.c.showPage()
    
    def draw_back_cover(self):
        """Draw back cover page"""
        if os.path.exists(BACK_IMAGE):
            self.c.drawImage(BACK_IMAGE, 0, 0, width=self.width, height=self.height,
                            preserveAspectRatio=False)
        self.c.showPage()
    
    def start_content_page(self, section_name, is_continuation=False):
        """Start a new content page with background and section header in green bar"""
        if not is_continuation:
            self.current_section = section_name
            self.section_page = 1
        else:
            self.section_page += 1

        # Draw background image
        if os.path.exists(CONTENT_IMAGE):
            self.c.drawImage(CONTENT_IMAGE, 0, 0, width=self.width, height=self.height,
                            preserveAspectRatio=False)

        # Draw section name in the green header bar
        self.c.setFont('Helvetica-Bold', 22)
        self.c.setFillColorRGB(1, 1, 1)  # White text on green bar
        header_y = self.height - 55
        text_x = self.margin_left

        # Show "Section Page N" for continuation pages
        if is_continuation:
            display_name = f"{self.current_section} Page {self.section_page}"
        else:
            display_name = section_name
        self.c.drawString(text_x, header_y, display_name)

        # Reset y position for content - start below green header bar
        self.y_position = self.header_bar_bottom - 40
        self.grid_position = 0  # Reset grid for new section
    
    def add_chart(self, chart_bytes, chart_width=None, chart_height=None):
        """Add a chart in 2x2 grid layout"""
        if chart_bytes is None:
            return False
        
        # Grid dimensions for 2x2 layout - wider charts with reduced margins
        grid_chart_width = 275   # Width for each chart in grid
        grid_chart_height = 245  # Height for each chart
        h_gap = 8                # Horizontal gap between charts
        v_gap = 15               # Vertical gap between rows
        
        # Start new row if needed
        if self.grid_position == 0:
            # Check if we need a new page
            if self.y_position - grid_chart_height < 85:
                self.c.showPage()
                self.start_content_page(self.current_section, is_continuation=True)
            self.grid_row_y = self.y_position
        
        # Calculate x position (left or right column)
        if self.grid_position % 2 == 0:  # Left column
            x_pos = self.margin_left
        else:  # Right column
            x_pos = self.margin_left + grid_chart_width + h_gap

        # Calculate y position
        if self.grid_position < 2:  # Top row
            y_pos = self.grid_row_y - grid_chart_height
        else:  # Bottom row
            y_pos = self.grid_row_y - (grid_chart_height * 2) - v_gap
        
        # Draw chart
        chart_bytes.seek(0)
        img = ImageReader(chart_bytes)
        self.c.drawImage(img, x_pos, y_pos, width=grid_chart_width, height=grid_chart_height)
        
        # Update grid position
        self.grid_position += 1
        
        # After 4 charts, reset grid and update y_position
        if self.grid_position >= 4:
            self.grid_position = 0
            self.y_position = y_pos - v_gap
        
        return True
    
    def flush_grid(self):
        """Flush remaining charts in grid and reset position"""
        if self.grid_position > 0:
            # Calculate how far down we went
            rows_used = (self.grid_position + 1) // 2
            chart_h = 260
            v_gap = 15
            self.y_position = self.grid_row_y - (rows_used * chart_h) - ((rows_used - 1) * v_gap) - v_gap
            self.grid_position = 0

    def add_wide_chart(self, chart_bytes):
        """Add a full-width chart (spans 2 columns)"""
        if chart_bytes is None:
            return False
        
        # Flush any pending grid charts first
        self.flush_grid()
        
        wide_chart_width = self.content_width  # Full width
        wide_chart_height = 280  # Slightly taller
        v_gap = 15
        
        # Check if we need a new page
        if self.y_position - wide_chart_height < 85:
            self.c.showPage()
            self.start_content_page(self.current_section, is_continuation=True)
        
        # Draw chart at full width
        chart_bytes.seek(0)
        img = ImageReader(chart_bytes)
        y_pos = self.y_position - wide_chart_height
        self.c.drawImage(img, self.margin_left, y_pos, width=wide_chart_width, height=wide_chart_height)
        
        self.y_position = y_pos - v_gap
        return True
    
    def add_subsection(self, title):
        """Add a subsection header"""
        if self.y_position < 180:
            self.c.showPage()
            self.start_content_page(self.current_section, is_continuation=True)
        
        self.c.setFont('Helvetica-Bold', 13)
        self.c.setFillColorRGB(0.2, 0.4, 0.35)  # Dark teal color
        self.c.drawString(self.margin_left, self.y_position, title)
        self.y_position -= 40  # Extra spacing before table
        self.y_position -= 22
    
    def add_text(self, text, italic=False):
        """Add text line"""
        if self.y_position < 85:
            self.c.showPage()
            self.start_content_page(self.current_section, is_continuation=True)
        
        if italic:
            self.c.setFont('Helvetica-Oblique', 10)
        else:
            self.c.setFont('Helvetica', 10)
        self.c.setFillColorRGB(0.35, 0.35, 0.35)
        self.c.drawString(self.margin_left, self.y_position, text)
        self.y_position -= 16
    
    def add_table(self, data, headers, col_widths=None):
        """Add a table to the current page"""
        if not data:
            return
        
        from reportlab.platypus import Table, TableStyle
        
        table_data = [headers] + data
        
        if col_widths is None:
            table_width = self.content_width * 0.9
            col_widths = [table_width / len(headers)] * len(headers)
        
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f57c00')),  # Orange header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        
        # Calculate table height
        table_height = len(table_data) * 22 + 10
        
        if self.y_position - table_height < 85:
            self.c.showPage()
            self.start_content_page(self.current_section, is_continuation=True)
        
        table.wrapOn(self.c, self.content_width, table_height)
        table_x = self.margin_left + (self.content_width - sum(col_widths)) / 2
        table.drawOn(self.c, table_x, self.y_position - table_height)
        self.y_position -= (table_height + 25)
    

    def add_data_table_with_limits(self, data, equipment_type, params_list, title=None, new_page=True):
        """
        Add a data table showing ALL measurements with out-of-limit values highlighted.
        Each measurement row shows: Date, Sampling Point, Parameter, Value, Limits, Status
        """
        if not data:
            return

        from reportlab.platypus import Table, TableStyle
        from report_utils import get_limits_for_pdf

        # Flush any pending chart grid to ensure y_position is correct
        self.flush_grid()
        # Start a new page for the data table (unless new_page=False)
        if new_page:
            self.c.showPage()
            self.start_content_page(self.current_section, is_continuation=True)

        if title:
            self.add_subsection(title)

        # Build table with ALL individual measurements (one row per measurement)
        headers = ["Date", "Sampling Point", "Parameter", "Value", "Unit", "Limits", "Status"]
        rows = []
        alert_cells = []

        row_idx = 1
        # Process each measurement record individually
        for item in sorted(data, key=lambda x: x.get("measurement_date", ""), reverse=True):
            date = item.get("measurement_date", "")[:10]
            unit = item.get("unit_id", "Unknown")
            param_name = item.get("parameter_name", "")
            value = item.get("value_numeric")

            if value is None:
                continue

            # Get limits for this parameter
            low, high = get_limits_for_pdf(equipment_type, param_name)
            limits_str = f"{low}-{high}" if low is not None and high is not None else "-"

            # Check if out of limits
            is_alert = False
            status = "OK"
            if low is not None and high is not None:
                try:
                    if float(value) < float(low) or float(value) > float(high):
                        is_alert = True
                        status = "ALERT"
                        alert_cells.append((row_idx, 3))  # Value column
                        alert_cells.append((row_idx, 6))  # Status column
                except:
                    pass

            # Shorten param name for display
            short_param = param_name[:20] if len(param_name) > 20 else param_name

            value_str = f"{value:.1f}" if isinstance(value, (int, float)) else str(value)
            if is_alert:
                value_str += "*"

            meas_unit = sanitize_unit_for_pdf(item.get("unit", "-") or "-")
            rows.append([date, unit, short_param, value_str, meas_unit, limits_str, status])
            row_idx += 1

        if not rows:
            return

        # Split into pages if too many rows (max 20 rows per page)
        max_rows_per_page = 24
        page_num = 0

        while page_num * max_rows_per_page < len(rows):
            start_idx = page_num * max_rows_per_page
            end_idx = min(start_idx + max_rows_per_page, len(rows))
            page_rows = rows[start_idx:end_idx]

            if page_num > 0:
                self.c.showPage()
                self.start_content_page(self.current_section, is_continuation=True)
                if title:
                    self.add_subsection(f"{title} (continued)")

            table_data = [headers] + page_rows
            col_widths = [50, 55, 95, 45, 35, 50, 40]

            # Always scale to full width
            total_width = sum(col_widths)
            scale = (self.content_width * 0.9) / total_width
            col_widths = [w * scale for w in col_widths]

            table = Table(table_data, colWidths=col_widths)

            style_commands = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5282")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ALIGN", (2, 1), (2, -1), "LEFT"),  # Parameter column left-aligned
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 7),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
                ("TOPPADDING", (0, 1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            ]

            # Highlight out-of-limit cells
            for (orig_row, col) in alert_cells:
                adjusted_row = orig_row - start_idx
                if 1 <= adjusted_row <= len(page_rows):
                    style_commands.append(("BACKGROUND", (col, adjusted_row), (col, adjusted_row), colors.HexColor("#ffcccc")))
                    style_commands.append(("TEXTCOLOR", (col, adjusted_row), (col, adjusted_row), colors.HexColor("#c53030")))
                    style_commands.append(("FONTNAME", (col, adjusted_row), (col, adjusted_row), "Helvetica-Bold"))

            table.setStyle(TableStyle(style_commands))

            table_height = len(table_data) * 18 + 10
            table_width = sum(col_widths)
            table_x = self.margin_left + (self.content_width - table_width) / 2
            table.wrapOn(self.c, table_width, table_height)
            table.drawOn(self.c, table_x, self.y_position - table_height)
            self.y_position -= (table_height + 15)

            page_num += 1

        # Add legend at the end
        if alert_cells:
            self.c.setFont("Helvetica-Oblique", 7)
            self.c.setFillColor(colors.HexColor("#c53030"))
            self.c.drawString(self.margin_left, self.y_position, "* Value outside limits (highlighted in red)")
            self.c.setFillColor(colors.black)
            self.y_position -= 15



    def add_scavenge_drain_table(self, data, vessel_id, title=None):
        """
        Add a full-width table showing all scavenge drain measurements with Alert column.
        Columns: Date, Sampling Point, Iron, BN, Alert
        """
        if not data:
            return

        from reportlab.platypus import Table, TableStyle
        from collections import defaultdict
        import re

        # Flush any pending chart grid first
        self.flush_grid()
        
        if title:
            self.add_subsection(title)

        # Organize data by date and unit
        # Structure: {date: {unit: {param: value}}}
        organized = defaultdict(lambda: defaultdict(dict))
        
        for item in data:
            date = item.get("measurement_date", "")[:10]
            sp_name = item.get("sampling_point_name", "")
            param_name = item.get("parameter_name", "").lower()
            value = item.get("value_numeric")
            
            if value is None or not date:
                continue
            
            # Extract unit identifier (Fresh Oil, Cyl 1, Cyl 2, etc.)
            if "fresh" in sp_name.lower() or "sd0" in sp_name.lower():
                unit = "Fresh Cyl Oil"
            else:
                unit_match = re.search(r"unit\s*(\d+)", sp_name, re.IGNORECASE)
                if unit_match:
                    unit = f"Cyl {unit_match.group(1)}"
                else:
                    unit = sp_name[:10]
            
            # Store sampling point name for alert lookup
            organized[date][unit]["sampling_point_name"] = sp_name
            
            # Determine parameter
            if "iron" in param_name or "fe" in param_name:
                organized[date][unit]["iron"] = value
            elif "base" in param_name or "bn" in param_name:
                organized[date][unit]["bn"] = value

        if not organized:
            return

        # Build table rows - compare values against limits from users.sqlite
        headers = ["Date", "Sampling Point", "Iron (ppm)", "BN (mg KOH/g)", "Alert"]
        rows = []
        alert_rows = []
        row_idx = 1
        
        # Get limits from users.sqlite for SCAVENGE DRAIN equipment type
        # Note: No limits are defined for SD in users.sqlite, so no alerts will be generated
        import sqlite3 as sqlite3_users
        users_db = sqlite3_users.connect("users.sqlite")
        users_db.row_factory = sqlite3_users.Row
        uc = users_db.cursor()
        
        # Get Iron and BN limits specifically for scavenge drain
        iron_limits = None
        bn_limits = None
        
        # Look for SD-specific limits (equipment type containing SCAVENGE or CYLINDER)
        uc.execute("SELECT parameter_name, lower_limit, upper_limit FROM parameter_limits WHERE equipment_type LIKE ? AND parameter_name LIKE ?", ("%SCAVENGE%", "%Iron%"))
        row = uc.fetchone()
        if row and row["lower_limit"] is not None and row["upper_limit"] is not None:
            iron_limits = (float(row["lower_limit"]), float(row["upper_limit"]))
        
        uc.execute("SELECT parameter_name, lower_limit, upper_limit FROM parameter_limits WHERE equipment_type LIKE ? AND (parameter_name LIKE ? OR parameter_name LIKE ?)", ("%SCAVENGE%", "%Base%", "%BN%"))
        row = uc.fetchone()
        if row and row["lower_limit"] is not None and row["upper_limit"] is not None:
            bn_limits = (float(row["lower_limit"]), float(row["upper_limit"]))
        
        users_db.close()
        
        for date in sorted(organized.keys(), reverse=True):
            for unit in sorted(organized[date].keys()):
                params = organized[date][unit]
                iron_val = params.get("iron")
                bn_val = params.get("bn")
                
                iron_str = f"{iron_val:.1f}" if iron_val is not None else "-"
                bn_str = f"{bn_val:.1f}" if bn_val is not None else "-"
                
                # Check against limits from users.sqlite
                has_alert = False
                if iron_val is not None and iron_limits:
                    if iron_val < iron_limits[0] or iron_val > iron_limits[1]:
                        has_alert = True
                if bn_val is not None and bn_limits:
                    if bn_val < bn_limits[0] or bn_val > bn_limits[1]:
                        has_alert = True
                
                alert_str = "Yes" if has_alert else "No"
                if has_alert:
                    alert_rows.append(row_idx)
                
                rows.append([date, unit, iron_str, bn_str, alert_str])
                row_idx += 1


        if not rows:
            return

        # Split into pages if too many rows (max 25 rows per page)
        max_rows_per_page = 24
        page_num = 0
        col_widths_base = [80, 50, 90, 90, 60]

        while page_num * max_rows_per_page < len(rows):
            start_idx = page_num * max_rows_per_page
            end_idx = min(start_idx + max_rows_per_page, len(rows))
            page_rows = rows[start_idx:end_idx]

            if page_num > 0:
                self.c.showPage()
                self.start_content_page(self.current_section, is_continuation=True)
                if title:
                    self.add_subsection(f"{title} (continued)")

            table_data = [headers] + page_rows

            # Scale to full content width
            total = sum(col_widths_base)
            scale = (self.content_width * 0.9) / total
            col_widths = [w * scale for w in col_widths_base]

            table = Table(table_data, colWidths=col_widths)

            style_commands = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5282")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
                ("TOPPADDING", (0, 1), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
            ]

            # Highlight alert rows (adjust index for current page)
            for orig_row_idx in alert_rows:
                adjusted_row = orig_row_idx - start_idx
                if 1 <= adjusted_row <= len(page_rows):
                    style_commands.append(("BACKGROUND", (4, adjusted_row), (4, adjusted_row), colors.HexColor("#ffcccc")))
                    style_commands.append(("TEXTCOLOR", (4, adjusted_row), (4, adjusted_row), colors.HexColor("#c53030")))
                    style_commands.append(("FONTNAME", (4, adjusted_row), (4, adjusted_row), "Helvetica-Bold"))

            table.setStyle(TableStyle(style_commands))

            table_height = len(table_data) * 20 + 10
            table_width = sum(col_widths)
            table_x = self.margin_left + (self.content_width - table_width) / 2
            table.wrapOn(self.c, table_width, table_height)
            table.drawOn(self.c, table_x, self.y_position - table_height)
            self.y_position -= (table_height + 15)

            page_num += 1

    def add_equipment_specs(self, vessel_id, equipment_filter):
        """Add equipment specifications section after data table"""
        # Flush any pending chart grid first
        self.flush_grid()
        specs = get_vessel_details_for_display(vessel_id, equipment_filter)
        if not specs:
            return
        
        # Filter out vessel_info category
        specs = {k: v for k, v in specs.items() if k != "vessel_info"}
        if not specs:
            return
        
        # Calculate space needed
        total_items = sum(len(fields) for fields in specs.values())
        space_needed = 30 + (total_items * 14) + (len(specs) * 20)
        
        # Check if we need a new page
        if self.y_position - space_needed < 85:
            self.c.showPage()
            self.start_content_page(self.current_section, is_continuation=True)
        
        # Add subsection header
        self.y_position -= 15
        self.c.setFont("Helvetica-Bold", 13)
        self.c.setFillColorRGB(0.2, 0.3, 0.5)
        self.c.drawString(self.margin_left, self.y_position, "Equipment Specifications")
        self.y_position -= 5
        
        # Draw a thin line under header
        self.c.setStrokeColorRGB(0.7, 0.7, 0.7)
        self.c.setLineWidth(0.5)
        self.c.line(self.margin_left, self.y_position, self.margin_left + self.content_width, self.y_position)
        self.y_position -= 15
        
        # Display specs
        self.c.setFont("Helvetica", 10)
        for category, fields in specs.items():
            if not fields:
                continue
            items_in_category = len(fields)
            space_for_category = 15 + (items_in_category * 12)
            if self.y_position - space_for_category < 85:
                self.c.showPage()
                self.start_content_page(self.current_section, is_continuation=True)
                self.c.setFont("Helvetica", 10)
            for field_name, field_value in fields.items():
                if field_value:
                    self.c.setFillColorRGB(0.4, 0.4, 0.4)
                    self.c.drawString(self.margin_left + 10, self.y_position, f"{field_name}:")
                    self.c.setFillColorRGB(0.1, 0.1, 0.1)
                    self.c.drawString(self.margin_left + 150, self.y_position, str(field_value))
                    self.y_position -= 15
        self.y_position -= 10


    def end_section(self):
        """End current section and start new page"""
        self.c.showPage()

    def add_section_alerts(self, alerts, equipment_patterns):
        """Add alerts for specific equipment inline"""
        if not alerts:
            return

        # Filter alerts matching equipment patterns
        section_alerts = []
        for alert in alerts:
            sp_name = alert.get('sampling_point_name', '').upper()
            for pattern in equipment_patterns:
                if pattern.upper() in sp_name:
                    section_alerts.append(alert)
                    break

        if not section_alerts:
            return

        # Flush any pending grid charts
        self.flush_grid()

        self.add_subsection("Alerts")
        headers = ['Date', 'Parameter', 'Value', 'Range']
        rows = []
        for alert in section_alerts[:10]:  # Limit to 10 per section
            rows.append([
                format_date(alert.get('alert_date', ''))[:10],
                alert.get('parameter_name', 'N/A')[:20],
                str(alert.get('measured_value', 'N/A'))[:8],
                f"{alert.get('expected_low', '-')}-{alert.get('expected_high', '-')}"[:12]
            ])

        col_widths = None  # Full width
        self.add_table(rows, headers, col_widths)

    def save(self):
        """Save the PDF"""
        self.c.save()


def generate_boiler_section(pdf, vessel_id, start_date, end_date):
    """Generate boiler water analysis section with separate Aux/EGE and Hotwell plots"""
    pdf.start_content_page("Boiler Water Analysis")
    
    # Parameters for Aux/EGE boilers
    boiler_params = ['Phosphate', 'Alkalinity P', 'Alkalinity M', 'Chloride', 'pH', 'Conductivity']
    # Parameters for Hotwell
    hotwell_params = ['Chloride', 'pH', 'Hydrazine', 'Conductivity']
    
    # Equipment mappings
    boiler_map = {
        'Aux1': 'AB1 Aux Boiler 1',
        'Aux2': 'AB2 Aux Boiler 2',
        'EGE': 'CB Composite Boiler'
    }
    hotwell_map = {
        'Hotwell': 'HW Hot Well'
    }
    
    # Collect data for Aux/EGE boilers
    boiler_data = []
    for boiler_id, equipment_name in boiler_map.items():
        data = get_measurements_by_equipment_name(vessel_id, equipment_name, boiler_params, start_date, end_date)
        if data:
            for item in data:
                item_copy = dict(item)
                item_copy['unit_id'] = boiler_id
                boiler_data.append(item_copy)
    
    # Collect data for Hotwell
    hotwell_data = []
    for hw_id, equipment_name in hotwell_map.items():
        data = get_measurements_by_equipment_name(vessel_id, equipment_name, hotwell_params, start_date, end_date)
        if data:
            for item in data:
                item_copy = dict(item)
                item_copy['unit_id'] = hw_id
                hotwell_data.append(item_copy)
    
    # Helper to extract limits from data
    def get_limits(data_list):
        for d in data_list:
            low = d.get('ideal_low')
            high = d.get('ideal_high')
            if low is not None and high is not None:
                return float(low), float(high)
        return None, None
    
    # Generate Aux/EGE boiler charts
    if boiler_data:
        params_found = set()
        for item in boiler_data:
            for param in boiler_params:
                if param.lower() in item.get('parameter_name', '').lower():
                    params_found.add(item.get('parameter_name'))
        
        for param_name in sorted(params_found):
            param_data = [d for d in boiler_data if param_name.lower() in d.get('parameter_name', '').lower()]
            if param_data:
                ideal_low, ideal_high = get_limits_for_pdf('AUX BOILER & EGE', param_name)
                chart = create_line_chart_by_unit(
                    param_data,
                    title=param_name,
                    color_scheme=BOILER_COLORS,
                    ideal_low=ideal_low,
                    ideal_high=ideal_high,
                    unit_field='unit_id',
                    equipment_type='AUX BOILER & EGE'
                )
                pdf.add_chart(chart)
    
    # Generate Hotwell charts (separate section)
    if hotwell_data:
        pdf.add_subsection("Hotwell")
        params_found = set()
        for item in hotwell_data:
            for param in hotwell_params:
                if param.lower() in item.get('parameter_name', '').lower():
                    params_found.add(item.get('parameter_name'))
        
        for param_name in sorted(params_found):
            param_data = [d for d in hotwell_data if param_name.lower() in d.get('parameter_name', '').lower()]
            if param_data:
                ideal_low, ideal_high = get_limits_for_pdf('HOTWELL', param_name)
                chart = create_line_chart_by_unit(
                    param_data,
                    title=param_name,
                    color_scheme={'Hotwell': '#ffc107'},
                    ideal_low=ideal_low,
                    ideal_high=ideal_high,
                    unit_field='unit_id',
                    equipment_type='HOTWELL'
                )
                pdf.add_chart(chart)
    
    # Add data tables with limit highlighting - use same params as charts
    if boiler_data:
        pdf.add_data_table_with_limits(boiler_data, "AUX BOILER & EGE", boiler_params, "Aux Boiler Data")
    if hotwell_data:
        pdf.add_data_table_with_limits(hotwell_data, 'HOTWELL', hotwell_params, "Hotwell Data", new_page=False)


    # Add equipment specifications
    pdf.add_equipment_specs(vessel_id, "boiler")
    pdf.end_section()


def generate_main_engine_section(pdf, vessel_id, start_date, end_date):
    """Generate main engine analysis section - Lube Oil and Scavenge Drain only"""
    pdf.start_content_page("Main Engine")

    # Lube oil
    lube_params = ['TBN', 'Water Content', 'Viscosity', 'BaseNumber']
    lube_data = get_measurements_by_equipment_name(vessel_id, 'ME Main Engine', lube_params, start_date, end_date)

    if lube_data:
        chart = create_multi_line_chart(lube_data, lube_params, "Lube Oil")
        pdf.add_chart(chart)

    # Scavenge drain time series and scatter plots
    scavenge_params = ['Iron', 'BaseNumber']
    scavenge_data = get_measurements_for_scavenge_drains(vessel_id, scavenge_params, start_date, end_date)

    if scavenge_data:
        # Filter data by parameter and create per-unit charts
        iron_data = [d for d in scavenge_data if 'iron' in d.get('parameter_name', '').lower()]
        bn_data = [d for d in scavenge_data if 'base' in d.get('parameter_name', '').lower() or 'bn' in d.get('parameter_name', '').lower()]

        # Iron in Oil time series chart - per SD unit
        if iron_data:
            chart = create_line_chart_by_unit(iron_data, "Iron in Oil", unit_field='sampling_point_name', show_legend=False)
            if chart:
                pdf.add_chart(chart)

        # Base Number time series chart - per SD unit
        if bn_data:
            chart = create_line_chart_by_unit(bn_data, "Base Number", unit_field='sampling_point_name', show_legend=False)
            if chart:
                pdf.add_chart(chart)

        # Iron vs Base Number scatter plot
        chart = create_scatter_chart(
            scavenge_data,
            'BaseNumber', 'Iron',
            "Iron vs BN",
            group_field='sampling_point_name', show_legend=False, size_multiplier=1.76
        )
        pdf.add_chart(chart)


        # Add legend-only panel for SD units - pass raw names for consistent color sorting
        raw_sd_names = set()
        for item in scavenge_data:
            sp_name = item.get("sampling_point_name", "")
            if sp_name:
                raw_sd_names.add(sp_name)
        if raw_sd_names:
            legend_chart = create_legend_only_chart(list(raw_sd_names), "Scavenge Drain Legend")
            if legend_chart:
                pdf.add_chart(legend_chart)

    # Add full-width scavenge drain table with Alert column
    if scavenge_data:
        pdf.add_scavenge_drain_table(scavenge_data, vessel_id, "Scavenge Drain Measurements")


    # Add equipment specifications
    pdf.add_equipment_specs(vessel_id, "main_engines")
    pdf.end_section()


def generate_aux_engine_section(pdf, vessel_id, start_date, end_date):
    """Generate auxiliary engines analysis section"""
    cooling_params = ['Nitrite', 'pH', 'Chloride']
    lube_params = ['TBN', 'BaseNumber', 'Viscosity']

    # First check if ANY aux engine has data
    has_any_data = False
    for engine_num in [1, 2, 3]:
        engine_name = f'AE{engine_num} Aux Engine'
        if get_measurements_by_equipment_name(vessel_id, engine_name, cooling_params, start_date, end_date):
            has_any_data = True
            break
        if get_measurements_by_equipment_name(vessel_id, engine_name, lube_params, start_date, end_date):
            has_any_data = True
            break

    if not has_any_data:
        return  # Skip entire section if no data

    pdf.start_content_page("Aux Engines")

    all_data = []  # Collect all data for the table
    for engine_num in [1, 2, 3]:
        engine_name = f'AE{engine_num} Aux Engine'
        cooling_data = get_measurements_by_equipment_name(vessel_id, engine_name, cooling_params, start_date, end_date)
        lube_data = get_measurements_by_equipment_name(vessel_id, engine_name, lube_params, start_date, end_date)

        if cooling_data:
            chart = create_multi_line_chart(cooling_data, cooling_params, f"AE{engine_num} Cooling", equipment_type='HT & LT COOLING WATER')
            pdf.add_chart(chart)
        if lube_data:
            for item in lube_data:
                item['unit_id'] = f'AE{engine_num}'
            all_data.extend(lube_data)
            chart = create_multi_line_chart(lube_data, lube_params, f"AE{engine_num} Lube")
            pdf.add_chart(chart)

    # Add data table with limit highlighting
    ae_table_params = ['TBN', 'Water', 'Viscosity']
    if all_data:
        pdf.add_data_table_with_limits(all_data, "AUX ENGINE", ae_table_params, "Aux Engine Data")


    # Add equipment specifications
    pdf.add_equipment_specs(vessel_id, "aux_engines")
    pdf.end_section()


def generate_potable_water_section(pdf, vessel_id, start_date, end_date):
    """Generate potable water analysis section with limit-highlighted table"""
    pw_params = ['pH', 'Chlorine', 'TDS', 'Turbidity', 'Hardness', 'Chloride']

    all_data = []
    for pw_id in ['PW1', 'PW2']:
        data = get_measurements_by_equipment_name(vessel_id, f'{pw_id} Potable Water', pw_params, start_date, end_date)
        if data:
            for item in data:
                item['unit_id'] = pw_id
            all_data.extend(data)

    if not all_data:
        return

    pdf.start_content_page("Potable Water")
    pdf.add_data_table_with_limits(all_data, 'POTABLE WATER', pw_params, new_page=False)

    # Add equipment specifications
    pdf.add_equipment_specs(vessel_id, "water_systems")
    pdf.end_section()


def generate_treated_sewage_section(pdf, vessel_id, start_date, end_date):
    """Generate treated sewage analysis section with limit-highlighted table"""
    gw_params = ['pH', 'COD', 'Chlorine', 'Turbidity', 'TSS']
    gw_data = get_measurements_by_equipment_name(vessel_id, 'GW Treated Sewage', gw_params, start_date, end_date)

    if not gw_data:
        return

    pdf.start_content_page("Treated Sewage")
    for item in gw_data:
        item['unit_id'] = 'GW'
    pdf.add_data_table_with_limits(gw_data, 'SEWAGE', gw_params, new_page=False)

    # Add equipment specifications
    pdf.add_equipment_specs(vessel_id, "water_systems")
    pdf.end_section()


def generate_alerts_section(pdf, vessel_id, start_date, end_date):
    """Generate alerts summary section"""
    pdf.start_content_page("Alerts Summary")
    
    alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True)
    
    if alerts:
        headers = ['Date', 'Location', 'Parameter', 'Value', 'Range', 'Type']
        rows = []
        
        for alert in alerts[:25]:  # Limit to 25 most recent
            rows.append([
                format_date(alert.get('alert_date', ''))[:10],
                alert.get('sampling_point_name', 'N/A')[:20],
                alert.get('parameter_name', 'N/A')[:15],
                str(alert.get('measured_value', 'N/A'))[:8],
                f"{alert.get('expected_low', '-')}-{alert.get('expected_high', '-')}"[:10],
                alert.get('alert_type', 'N/A')[:10]
            ])
        
        col_widths = None  # Full width
        pdf.add_table(rows, headers, col_widths)
        
        if len(alerts) > 25:
            pdf.add_text(f"Showing 25 of {len(alerts)} total alerts", italic=True)
    else:
        pdf.add_text("No unresolved alerts", italic=True)
    
    pdf.end_section()



def generate_central_cooling_section(pdf, vessel_id, start_date, end_date):
    """Generate central cooling water analysis section with one chart per parameter (HT & LT on each)"""
    from report_utils import create_line_chart_by_unit, get_limits_for_pdf

    # Central cooling parameters - match web page order
    cooling_params = ['Chloride', 'Nitrite', 'pH']

    # Get data for HT/LT cooling systems
    ht_data = get_measurements_by_equipment_name(vessel_id, 'HT Cooling', cooling_params, start_date, end_date)
    lt_data = get_measurements_by_equipment_name(vessel_id, 'LT Cooling', cooling_params, start_date, end_date)

    if not ht_data and not lt_data:
        return  # Skip section if no data

    pdf.start_content_page("Central Cooling Water")

    # Color scheme for HT and LT
    cooling_colors = {
        'HT': '#dc3545',  # Red for HT
        'LT': '#0d6efd'   # Blue for LT
    }

    # Create one chart per parameter with both HT and LT lines
    for param in cooling_params:
        # Filter data for this parameter
        param_data = []

        if ht_data:
            for item in ht_data:
                if param.lower() in item.get('parameter_name', '').lower():
                    item_copy = dict(item)
                    item_copy['unit_id'] = 'HT'
                    param_data.append(item_copy)

        if lt_data:
            for item in lt_data:
                if param.lower() in item.get('parameter_name', '').lower():
                    item_copy = dict(item)
                    item_copy['unit_id'] = 'LT'
                    param_data.append(item_copy)

        if param_data:
            # Get limits for this parameter
            low, high = get_limits_for_pdf('HT & LT COOLING WATER', param)

            # Shorten title for display
            display_title = param
            if 'Chloride' in param:
                display_title = 'Chloride'
            elif 'Nitrite' in param:
                display_title = 'Nitrite'
            elif 'pH' in param.lower():
                display_title = 'pH'

            chart = create_line_chart_by_unit(
                param_data,
                display_title,
                color_scheme=cooling_colors,
                ideal_low=low,
                ideal_high=high,
                equipment_type='HT & LT COOLING WATER'
            )
            if chart:
                pdf.add_chart(chart)

    # Add data table with limit checking
    all_cooling_data = []
    if ht_data:
        for item in ht_data:
            item_copy = dict(item)
            item_copy['unit_id'] = 'HT'
            all_cooling_data.append(item_copy)
    if lt_data:
        for item in lt_data:
            item_copy = dict(item)
            item_copy['unit_id'] = 'LT'
            all_cooling_data.append(item_copy)

    if all_cooling_data:
        pdf.add_data_table_with_limits(all_cooling_data, "HT & LT COOLING WATER", cooling_params, "Cooling Water Data")

    # Add equipment specifications
    pdf.add_equipment_specs(vessel_id, "water_systems")
    pdf.end_section()


def generate_ballast_water_section(pdf, vessel_id, start_date, end_date):
    """Generate ballast water analysis section"""
    bw_params = ['Viable Count', 'E.coli', 'Enterococci', 'Vibrio', 'Chlorine']
    bw_data = get_measurements_by_equipment_name(vessel_id, 'BW Ballast', bw_params, start_date, end_date)
    
    if not bw_data:
        return  # Skip section if no data
    
    pdf.start_content_page("Ballast Water")
    
    # Add unit_id for table
    for item in bw_data:
        item['unit_id'] = 'BW'
    
    # Add data table with limits (BALLAST WATER has no limits in users.sqlite)
    pdf.add_data_table_with_limits(bw_data, 'BALLAST WATER', bw_params, "Ballast Water Data", new_page=False)
    
    pdf.end_section()


def generate_egcs_section(pdf, vessel_id, start_date, end_date):
    """Generate EGCS (Exhaust Gas Cleaning System) analysis section"""
    egcs_params = ['pH', 'PAH', 'Turbidity', 'Nitrate']
    egcs_data = get_measurements_by_equipment_name(vessel_id, 'EGCS', egcs_params, start_date, end_date)
    
    if not egcs_data:
        return  # Skip section if no data
    
    pdf.start_content_page("EGCS")
    
    # Add unit_id for table
    for item in egcs_data:
        item['unit_id'] = 'EGCS'
    
    # Add data table with limits (EGCS has no limits in users.sqlite)
    pdf.add_data_table_with_limits(egcs_data, 'EGCS', egcs_params, "EGCS Data", new_page=False)
    
    pdf.end_section()



def generate_report_bytes(vessel_id, vessel_name, start_date, end_date, selected_sections=None, imo_number=None, company_name=None):
    """
    Generate PDF report and return as bytes (for web integration)
    """
    if selected_sections is None:
        selected_sections = list(AVAILABLE_SECTIONS.keys())
    
    # Create PDF in memory
    output = io.BytesIO()
    pdf = ReportPDFGenerator(output, vessel_name, start_date, end_date, imo_number, company_name)
    
    # Cover page
    pdf.draw_cover_page()
    
    # Generate selected sections
    section_generators = {
        'boiler': generate_boiler_section,
        'main_engines': generate_main_engine_section,
        'aux_engines': generate_aux_engine_section,
        'potable_water': generate_potable_water_section,
        'treated_sewage': generate_treated_sewage_section,
        'central_cooling': generate_central_cooling_section,
        'ballast_water': generate_ballast_water_section,
        'egcs': generate_egcs_section
    }
    
    for section_key in selected_sections:
        if section_key in section_generators:
            try:
                section_generators[section_key](pdf, vessel_id, start_date, end_date)
            except Exception as e:
                print(f"Error generating section {section_key}: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    # Back cover
    pdf.draw_back_cover()
    
    # Save and return
    pdf.save()
    output.seek(0)
    return output.getvalue()


def main():
    """CLI main function"""
    parser = argparse.ArgumentParser(description='Generate PDF report for vessel measurements')
    parser.add_argument('vessel_id', type=int, help='Vessel database ID')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--output-dir', type=str, default='reports', help='Output directory')
    parser.add_argument('--sections', type=str, nargs='+', choices=list(AVAILABLE_SECTIONS.keys()))

    args = parser.parse_args()

    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    else:
        end_date = datetime.now()

    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    else:
        start_date = end_date - timedelta(days=30)

    vessel = get_vessel_by_id(args.vessel_id)
    if not vessel:
        print(f"Error: Vessel ID {args.vessel_id} not found")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    filename = f"{vessel['vessel_name'].replace(' ', '_')}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
    output_path = os.path.join(args.output_dir, filename)

    print(f"Generating report for {vessel['vessel_name']}...")
    print(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    sections = args.sections if args.sections else list(AVAILABLE_SECTIONS.keys())
    # Fetch vessel details for cover page
    import sqlite3
    imo_number = None
    company_name = None
    try:
        users_conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'users.sqlite'))
        users_cursor = users_conn.cursor()
        users_cursor.execute('SELECT imo_number, company_name FROM vessel_details WHERE vessel_id = ?', (args.vessel_id,))
        details = users_cursor.fetchone()
        if details:
            imo_number = details[0]
            company_name = details[1]
        users_conn.close()
    except Exception as e:
        print(f'Warning: Could not fetch vessel details: {e}')
    
    pdf_bytes = generate_report_bytes(args.vessel_id, vessel['vessel_name'], start_date, end_date, sections, imo_number, company_name)

    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)

    print(f"\nReport generated successfully: {output_path}")
    print(f"File size: {len(pdf_bytes) / 1024:.1f} KB")


if __name__ == '__main__':
    main()


