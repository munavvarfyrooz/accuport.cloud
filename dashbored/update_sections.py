#!/usr/bin/env python3
"""Update section generators to use data tables with limits instead of alerts"""

with open("generate_vessel_report.py", "r") as f:
    content = f.read()

# 1. Update boiler section - add data table call before end_section, remove alerts
old_boiler_end = '''    # Add boiler alerts at end of section
    alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True)
    pdf.add_section_alerts(alerts, ['BOILER', 'AB1', 'AB2', 'EGE', 'CB', 'HOTWELL', 'HW'])

    pdf.end_section()'''

new_boiler_end = '''    # Add data tables with limit highlighting (replaces separate alerts)
    boiler_table_params = ['Phosphate', 'pH', 'Chloride', 'Conductivity', 'Alkalinity']
    if boiler_data:
        pdf.add_data_table_with_limits(boiler_data, 'AUX BOILER & EGE', boiler_table_params, "Aux Boiler Data")
    if hotwell_data:
        pdf.add_data_table_with_limits(hotwell_data, 'HOTWELL', boiler_table_params, "Hotwell Data")

    pdf.end_section()'''

content = content.replace(old_boiler_end, new_boiler_end)

# 2. Update main engine section
old_me_end = '''    # Add ME alerts at end
    alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True)
    pdf.add_section_alerts(alerts, ['ME', 'MAIN ENGINE', 'SCAVENGE'])

    pdf.end_section()'''

new_me_end = '''    # Add data table with limit highlighting
    me_table_params = ['TBN', 'Water', 'Viscosity']
    if lube_data:
        for item in lube_data:
            item['unit_id'] = item.get('sampling_point_name', 'ME')[:3]
        pdf.add_data_table_with_limits(lube_data, 'MAIN ENGINE', me_table_params, "Lube Oil Data")

    pdf.end_section()'''

content = content.replace(old_me_end, new_me_end)

# 3. Update aux engine section
old_ae_end = '''    # Add AE alerts at end
    alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True)
    pdf.add_section_alerts(alerts, ['AE', 'AUX ENGINE'])

    pdf.end_section()'''

new_ae_end = '''    # Add data table with limit highlighting
    ae_table_params = ['TBN', 'Water', 'Viscosity']
    if all_data:
        pdf.add_data_table_with_limits(all_data, 'AUX ENGINE', ae_table_params, "Aux Engine Data")

    pdf.end_section()'''

content = content.replace(old_ae_end, new_ae_end)

with open("generate_vessel_report.py", "w") as f:
    f.write(content)

print("Updated sections to use data tables with limits")
