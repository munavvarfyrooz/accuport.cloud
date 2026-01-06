#!/usr/bin/env python3
"""Complete fix for data tables - show ALL rows, use correct params"""

with open("generate_vessel_report.py", "r") as f:
    content = f.read()

# Fix 1: Update boiler section to use same params as charts
old_boiler_table = '''    # Add data tables with limit highlighting (replaces separate alerts)
    boiler_table_params = ['Phosphate', 'pH', 'Chloride', 'Conductivity', 'Alkalinity']
    if boiler_data:
        pdf.add_data_table_with_limits(boiler_data, 'AUX BOILER & EGE', boiler_table_params, "Aux Boiler Data")
    if hotwell_data:
        pdf.add_data_table_with_limits(hotwell_data, 'HOTWELL', boiler_table_params, "Hotwell Data")'''

new_boiler_table = '''    # Add data tables with limit highlighting - use same params as charts
    if boiler_data:
        pdf.add_data_table_with_limits(boiler_data, 'AUX BOILER & EGE', boiler_params, "Aux Boiler Data")
    if hotwell_data:
        pdf.add_data_table_with_limits(hotwell_data, 'HOTWELL', hotwell_params, "Hotwell Data")'''

content = content.replace(old_boiler_table, new_boiler_table)

# Fix 2: Replace add_data_table_with_limits to show ALL individual measurements
old_method_start = '''    def add_data_table_with_limits(self, data, equipment_type, params_list, title=None):
        """
        Add a data table showing ALL measurements with out-of-limit values highlighted.
        Table starts on a new page after charts.
        """
        if not data:
            return

        from reportlab.platypus import Table, TableStyle
        from report_utils import get_limits_for_pdf
        from collections import defaultdict

        # Start a new page for the data table
        self.c.showPage()
        self.start_content_page(self.current_section, is_continuation=True)

        if title:
            self.add_subsection(title)

        # Get all limits for this equipment type
        limits_cache = {}
        for param in params_list:
            low, high = get_limits_for_pdf(equipment_type, param)
            if low is not None and high is not None:
                limits_cache[param.lower()] = (float(low), float(high))

        # Build table with ALL data points (one row per measurement record)
        headers = ["Date", "Unit"] + params_list
        rows = []
        alert_cells = []

        # Group by date+unit to combine params on same row
        by_date_unit = defaultdict(lambda: defaultdict(dict))
        for item in data:
            date = item.get("measurement_date", "")[:10]
            unit = item.get("unit_id", "Unknown")
            param_name = item.get("parameter_name", "")
            value = item.get("value_numeric")

            for p in params_list:
                if p.lower() in param_name.lower():
                    by_date_unit[date][unit][p] = value
                    break

        if not by_date_unit:
            return

        row_idx = 1
        # Show ALL dates (no limit)
        for date in sorted(by_date_unit.keys(), reverse=True):
            for unit in sorted(by_date_unit[date].keys()):
                row = [date, unit]
                for col_idx, p in enumerate(params_list):
                    value = by_date_unit[date][unit].get(p)
                    if value is not None:
                        is_alert = False
                        for limit_key, (low, high) in limits_cache.items():
                            if limit_key in p.lower():
                                if value < low or value > high:
                                    is_alert = True
                                    alert_cells.append((row_idx, col_idx + 2))
                                break

                        if is_alert:
                            row.append(f"{value:.1f}*")
                        else:
                            row.append(f"{value:.1f}" if isinstance(value, (int, float)) else str(value))
                    else:
                        row.append("-")
                rows.append(row)
                row_idx += 1

        if not rows:
            return

        # Split into pages if too many rows (max 25 rows per page)
        max_rows_per_page = 25
        page_num = 0

        while page_num * max_rows_per_page < len(rows):
            start_idx = page_num * max_rows_per_page
            end_idx = min(start_idx + max_rows_per_page, len(rows))
            page_rows = rows[start_idx:end_idx]

            if page_num > 0:
                self.c.showPage()
                self.start_content_page(self.current_section, is_continuation=True)

            table_data = [headers] + page_rows
            col_widths = [60, 45] + [55] * len(params_list)

            total_width = sum(col_widths)
            if total_width > self.content_width:
                scale = self.content_width / total_width
                col_widths = [w * scale for w in col_widths]

            table = Table(table_data, colWidths=col_widths)

            style_commands = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5282")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
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

            # Highlight out-of-limit cells (adjust row index for current page)
            for (orig_row, col) in alert_cells:
                adjusted_row = orig_row - start_idx
                if 1 <= adjusted_row <= len(page_rows):
                    style_commands.append(("BACKGROUND", (col, adjusted_row), (col, adjusted_row), colors.HexColor("#ffcccc")))
                    style_commands.append(("TEXTCOLOR", (col, adjusted_row), (col, adjusted_row), colors.HexColor("#c53030")))
                    style_commands.append(("FONTNAME", (col, adjusted_row), (col, adjusted_row), "Helvetica-Bold"))

            table.setStyle(TableStyle(style_commands))

            table_height = len(table_data) * 18 + 10
            table.wrapOn(self.c, self.content_width, table_height)
            table.drawOn(self.c, self.margin_left, self.y_position - table_height)
            self.y_position -= (table_height + 15)

            page_num += 1

        # Add legend at the end
        if alert_cells:
            self.c.setFont("Helvetica-Oblique", 7)
            self.c.setFillColor(colors.HexColor("#c53030"))
            self.c.drawString(self.margin_left, self.y_position, "* Value outside limits (highlighted in red)")
            self.c.setFillColor(colors.black)
            self.y_position -= 15

'''

new_method = '''    def add_data_table_with_limits(self, data, equipment_type, params_list, title=None):
        """
        Add a data table showing ALL measurements with out-of-limit values highlighted.
        Each measurement row shows: Date, Unit, Parameter, Value, Limits, Status
        """
        if not data:
            return

        from reportlab.platypus import Table, TableStyle
        from report_utils import get_limits_for_pdf

        # Start a new page for the data table
        self.c.showPage()
        self.start_content_page(self.current_section, is_continuation=True)

        if title:
            self.add_subsection(title)

        # Build table with ALL individual measurements (one row per measurement)
        headers = ["Date", "Unit", "Parameter", "Value", "Limits", "Status"]
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
                        alert_cells.append((row_idx, 5))  # Status column
                except:
                    pass

            # Shorten param name for display
            short_param = param_name[:20] if len(param_name) > 20 else param_name

            value_str = f"{value:.1f}" if isinstance(value, (int, float)) else str(value)
            if is_alert:
                value_str += "*"

            rows.append([date, unit, short_param, value_str, limits_str, status])
            row_idx += 1

        if not rows:
            return

        # Split into pages if too many rows (max 20 rows per page)
        max_rows_per_page = 20
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
            col_widths = [55, 40, 120, 50, 60, 45]

            total_width = sum(col_widths)
            if total_width > self.content_width:
                scale = self.content_width / total_width
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
            table.wrapOn(self.c, self.content_width, table_height)
            table.drawOn(self.c, self.margin_left, self.y_position - table_height)
            self.y_position -= (table_height + 15)

            page_num += 1

        # Add legend at the end
        if alert_cells:
            self.c.setFont("Helvetica-Oblique", 7)
            self.c.setFillColor(colors.HexColor("#c53030"))
            self.c.drawString(self.margin_left, self.y_position, "* Value outside limits (highlighted in red)")
            self.c.setFillColor(colors.black)
            self.y_position -= 15

'''

content = content.replace(old_method_start, new_method)

with open("generate_vessel_report.py", "w") as f:
    f.write(content)

print("Fixed table to show ALL individual measurements")
