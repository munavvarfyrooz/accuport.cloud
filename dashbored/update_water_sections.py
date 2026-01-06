#!/usr/bin/env python3
"""Update potable water and treated sewage sections to use limit-highlighted tables"""

with open("generate_vessel_report.py", "r") as f:
    content = f.read()

# Update potable water section
old_pw = '''def generate_potable_water_section(pdf, vessel_id, start_date, end_date):
    """Generate potable water analysis section as table"""
    pw_params = ['pH', 'Alkalinity', 'Chlorine', 'TDS', 'Turbidity', 'Hardness', 'Chloride']

    all_data = []
    for pw_id in ['PW1', 'PW2']:
        data = get_measurements_by_equipment_name(vessel_id, f'{pw_id} Potable Water', pw_params, start_date, end_date)
        if data:
            all_data.extend(data)

    if not all_data:
        return  # Skip section if no data

    pdf.start_content_page("Potable Water")

    if all_data:
        # Group by date and parameter for table format
        from collections import defaultdict
        by_date = defaultdict(dict)
        for item in all_data:
            date = item.get('measurement_date', '')[:10]
            param = item.get('parameter_name', '')
            value = item.get('value_numeric', '')
            # Shorten param name
            for p in pw_params:
                if p.lower() in param.lower():
                    by_date[date][p] = f"{value:.1f}" if isinstance(value, (int, float)) else str(value)
                    break

        # Build table rows
        headers = ['Date'] + pw_params
        rows = []
        for date in sorted(by_date.keys(), reverse=True)[:15]:  # Last 15 dates
            row = [date]
            for p in pw_params:
                row.append(by_date[date].get(p, '-'))
            rows.append(row)

        if rows:
            col_widths = [70] + [60] * len(pw_params)
            pdf.add_table(rows, headers, col_widths)

    pdf.end_section()'''

new_pw = '''def generate_potable_water_section(pdf, vessel_id, start_date, end_date):
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
    pdf.add_data_table_with_limits(all_data, 'POTABLE WATER', pw_params)
    pdf.end_section()'''

content = content.replace(old_pw, new_pw)

# Update treated sewage section
old_gw = '''def generate_treated_sewage_section(pdf, vessel_id, start_date, end_date):
    """Generate treated sewage analysis section as table"""
    gw_params = ['pH', 'COD', 'Chlorine', 'Turbidity', 'Coliform', 'TSS']
    gw_data = get_measurements_by_equipment_name(vessel_id, 'GW Treated Sewage', gw_params, start_date, end_date)

    if not gw_data:
        return  # Skip section if no data

    pdf.start_content_page("Treated Sewage")

    if gw_data:
        from collections import defaultdict
        by_date = defaultdict(dict)
        for item in gw_data:
            date = item.get('measurement_date', '')[:10]
            param = item.get('parameter_name', '')
            value = item.get('value_numeric', '')
            for p in gw_params:
                if p.lower() in param.lower():
                    by_date[date][p] = f"{value:.1f}" if isinstance(value, (int, float)) else str(value)
                    break

        headers = ['Date'] + gw_params
        rows = []
        for date in sorted(by_date.keys(), reverse=True)[:15]:
            row = [date]
            for p in gw_params:
                row.append(by_date[date].get(p, '-'))
            rows.append(row)

        if rows:
            col_widths = [70] + [70] * len(gw_params)
            pdf.add_table(rows, headers, col_widths)

    pdf.end_section()'''

new_gw = '''def generate_treated_sewage_section(pdf, vessel_id, start_date, end_date):
    """Generate treated sewage analysis section with limit-highlighted table"""
    gw_params = ['pH', 'COD', 'Chlorine', 'Turbidity', 'TSS']
    gw_data = get_measurements_by_equipment_name(vessel_id, 'GW Treated Sewage', gw_params, start_date, end_date)

    if not gw_data:
        return

    pdf.start_content_page("Treated Sewage")
    for item in gw_data:
        item['unit_id'] = 'GW'
    pdf.add_data_table_with_limits(gw_data, 'SEWAGE', gw_params)
    pdf.end_section()'''

content = content.replace(old_gw, new_gw)

with open("generate_vessel_report.py", "w") as f:
    f.write(content)

print("Updated potable water and treated sewage sections")
