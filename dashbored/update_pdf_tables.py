#!/usr/bin/env python3
"""Script to add data table with limits method to generate_vessel_report.py"""

new_method = '''
    def add_data_table_with_limits(self, data, equipment_type, params_list, title=None):
        """
        Add a data table showing all measurements with out-of-limit values highlighted.
        """
        if not data:
            return

        from reportlab.platypus import Table, TableStyle
        from report_utils import get_limits_for_pdf
        from collections import defaultdict

        if title:
            self.add_subsection(title)

        # Get all limits for this equipment type
        limits_cache = {}
        for param in params_list:
            low, high = get_limits_for_pdf(equipment_type, param)
            if low is not None and high is not None:
                limits_cache[param.lower()] = (float(low), float(high))

        # Group data by date and unit
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

        headers = ["Date", "Unit"] + params_list
        rows = []
        alert_cells = []

        row_idx = 1
        for date in sorted(by_date_unit.keys(), reverse=True)[:20]:
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

        table_data = [headers] + rows
        col_widths = [55, 45] + [50] * len(params_list)

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

        for (row, col) in alert_cells:
            style_commands.append(("BACKGROUND", (col, row), (col, row), colors.HexColor("#ffcccc")))
            style_commands.append(("TEXTCOLOR", (col, row), (col, row), colors.HexColor("#c53030")))
            style_commands.append(("FONTNAME", (col, row), (col, row), "Helvetica-Bold"))

        table.setStyle(TableStyle(style_commands))

        table_height = len(table_data) * 18 + 10

        if self.y_position - table_height < 85:
            self.c.showPage()
            self.start_content_page(self.current_section, is_continuation=True)

        table.wrapOn(self.c, self.content_width, table_height)
        table.drawOn(self.c, self.margin_left, self.y_position - table_height)
        self.y_position -= (table_height + 15)

        if alert_cells:
            self.c.setFont("Helvetica-Oblique", 7)
            self.c.setFillColor(colors.HexColor("#c53030"))
            self.c.drawString(self.margin_left, self.y_position, "* Value outside limits (highlighted in red)")
            self.c.setFillColor(colors.black)
            self.y_position -= 15

'''

with open("generate_vessel_report.py", "r") as f:
    content = f.read()

insert_marker = "    def end_section(self):"
if insert_marker in content:
    content = content.replace(insert_marker, new_method + "\n" + insert_marker)

with open("generate_vessel_report.py", "w") as f:
    f.write(content)

print("Added add_data_table_with_limits method")
