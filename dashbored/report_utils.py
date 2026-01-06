"""
Utility functions for PDF report generation

This module provides chart generation and formatting utilities for creating
professional PDF reports. Uses Matplotlib with ARM64-compatible Agg backend
and website-matching color schemes for visual consistency.

Key functionality:
- Line charts with multiple units/series
- Scatter plots for parameter correlations
- Data normalization and limit lookups
- Table creation with ReportLab styling
- Date formatting and color scheme utilities
"""
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator
from datetime import datetime
import io
from collections import defaultdict

def is_valid_limit(ideal_low, ideal_high):
    """
    Check if parameter limits are valid for display on charts.

    Validates that limits are not None, not sentinel values (like -1),
    and form a valid range (low <= high).

    Args:
        ideal_low: Lower limit value
        ideal_high: Upper limit value

    Returns:
        bool: True if limits are valid for chart display
    """
    if ideal_low is None or ideal_high is None:
        return False
    try:
        low = float(ideal_low)
        high = float(ideal_high)
        # Reject -1 sentinel values and invalid ranges
        if low < 0 or high < 0:
            return False
        if high < low:
            return False
        return True
    except (ValueError, TypeError):
        return False





def normalize_date_for_plot(date_str):
    """
    Normalize a datetime string to midnight for consistent chart x-axis plotting.

    Strips the time component to group same-day measurements together,
    matching the behavior of the web dashboard charts.

    Args:
        date_str: ISO format datetime string

    Returns:
        datetime: Date normalized to midnight, or None if parsing fails
    """
    if not date_str:
        return None
    try:
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        # Normalize to midnight to group same-day measurements together
        return date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
    except:
        return None

def normalize_param_name_for_limits(param_name, equipment_type=None):
    """
    Normalize database parameter names to match limit lookup keys in users.sqlite

    Maps: "Phosphate (HR tab). ortho" -> "PHOSPHATE"
          "pH-Universal (liq)" -> "PH"
          etc.
    """
    if not param_name:
        return ""

    name = param_name.upper()

    # Direct mappings for common parameters
    # IMPORTANT: Check SULPHATE before PH because 'PH' is in 'SULPHATE'
    if 'SULPHATE' in name or 'SULFATE' in name:
        return 'SULPHATE (SO₄)'
    if 'PHOSPHAT' in name:
        return 'PHOSPHATE'
    # Alkalinity detection - context-aware
    if 'ALKALINITY' in name:
        # For boiler equipment, use ALKALINITY M/P (matches database)
        if equipment_type and ('BOILER' in equipment_type.upper() or 'EGE' in equipment_type.upper()):
            if ' M' in name or name.endswith('M' ) or 'M-ALK' in name or 'M (' in name:
                return 'ALKALINITY M'
            elif ' P' in name or name.endswith('P' ) or 'P-ALK' in name or 'P (' in name:
                return 'ALKALINITY P'
        # For potable water, use TOTAL ALKALINITY (AS CACO₃)
        if ' M ' in name or ' M(' in name or name.endswith(' M' ) or name == 'ALKALINITY M':
            return 'TOTAL ALKALINITY (AS CACO₃)'
        elif ' P ' in name or ' P(' in name or name.endswith(' P' ):
            return 'ALKALINITY P'
        return 'TOTAL ALKALINITY (AS CACO₃)'
    if 'CHLORIDE' in name:
        return 'CHLORIDE'
    # PH check - more specific to avoid matching SULPHATE, PHOSPHATE, etc.
    if name.startswith('PH') or ' PH' in name or 'PH-' in name or name == 'PH':
        return 'PH'
    if 'CONDUCTIV' in name:
        return 'CONDUCTIVITY'
    if 'DEHA' in name:
        return 'DEHA'
    if 'HYDRAZINE' in name:
        return 'HYDRAZINE'
    if 'NITRITE' in name:
        return 'NITRITE'
    # Hardness: return simpler version - fuzzy match will handle variations
    if 'HARDNESS' in name or 'HARDN' in name:
        return 'TOTAL HARDNESS'
    if 'COD' in name:
        return 'COD'
    if 'BOD' in name:
        return 'BOD'
    if 'TURBIDITY' in name:
        return 'TURBIDITY'
    if 'SUSPENDED' in name or 'TSS' in name:
        return 'TOTAL SUSPENDED SOLIDS'
    if 'CHLORINE' in name:
        if 'FREE' in name:
            return 'FREE CHLORINE'
        if 'TOTAL' in name:
            return 'TOTAL CHLORINE'
        if 'COMBINED' in name:
            return 'COMBINED CHLORINE'
        return 'TOTAL CHLORINE'
    if 'COPPER' in name:
        return 'COPPER (CU)'
    if 'IRON' in name and 'OIL' not in name:
        return 'IRON (FE)'
    if 'NICKEL' in name:
        return 'NICKEL (NI)'
    if 'ZINC' in name:
        return 'ZINC (ZN)'
    if 'TDS' in name or 'DISSOLVED SOLID' in name:
        return 'TOTAL DISSOLVED SOLIDS (TDS)'

    # Return original if no match
    return name.strip()


def get_limits_for_pdf(equipment_type, parameter_name):
    """
    Get limits from users.sqlite parameter_limits table

    Args:
        equipment_type: One of 'AUX BOILER & EGE', 'HOTWELL', 'HT & LT COOLING WATER',
                        'POTABLE WATER', 'SEWAGE'
        parameter_name: Database parameter name (will be normalized)

    Returns:
        (lower_limit, upper_limit) tuple, or (None, None) if not found
    """
    from models import get_all_limits_for_equipment

    limits = get_all_limits_for_equipment(equipment_type)
    if not limits:
        return None, None

    # Normalize the parameter name
    normalized = normalize_param_name_for_limits(parameter_name, equipment_type)

    # Try exact match first (after normalization this should work for most cases)
    if normalized in limits:
        return limits[normalized]['lower_limit'], limits[normalized]['upper_limit']

    # Strict fuzzy match - only match if normalized contains key AND key is substantial
    # (avoid "PH" matching "PHOSPHATE" since PH is too short)
    for key, val in limits.items():
        # Only allow fuzzy match if:
        # 1. Key is contained in normalized AND key length > 3 (avoid short matches like PH)
        # 2. OR normalized is contained in key AND normalized length > 3
        if len(key) > 3 and key in normalized:
            return val['lower_limit'], val['upper_limit']
        if len(normalized) > 3 and normalized in key:
            return val['lower_limit'], val['upper_limit']

    return None, None


from PIL import Image
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# Chart configuration
CHART_WIDTH_INCHES = 3.2
CHART_HEIGHT_INCHES = 2.2
SCATTER_HEIGHT_INCHES = 2.2
DPI = 250  # Higher DPI for sharper, refined rendering

# Website-matching color schemes
BOILER_COLORS = {
    'Aux1': '#0d6efd',   # Blue
    'Aux2': '#198754',   # Green
    'EGE': '#dc3545',    # Red
    'Hotwell': '#ffc107' # Yellow
}

MAIN_ENGINE_COLORS = {
    'ME1': '#dc3545',  # Red
    'ME2': '#0d6efd'   # Blue
}

AUX_ENGINE_COLORS = {
    1: '#2196F3',  # Blue
    2: '#4CAF50',  # Green
    3: '#FF9800'   # Orange
}

# Generic color palette for other sections
GENERIC_COLORS = ['#0d6efd', '#198754', '#dc3545', '#ffc107', '#6f42c1', '#fd7e14', '#20c997', '#6c757d']


def compact_label(label):
    """
    Compact long parameter or equipment names to shorter display format.

    Maps common long names to abbreviated versions for better chart
    readability (e.g., "Phosphate (HR tab). ortho" -> "Phosphate").

    Args:
        label: Original label string

    Returns:
        str: Shortened label (max 12 characters unless special pattern)
    """
    import re
    label = str(label)
    lbl = label.lower()
    
    # Preserve comparison titles (e.g., "Iron vs BN")
    if ' vs ' in lbl:
        return label
    
    # Parameter name shortenings - check most specific first
    if 'conductiv' in lbl or 'ec' in lbl:
        return 'Conductivity'
    if 'phosphat' in lbl or 'ortho' in lbl:
        return 'Phosphate'
    if 'chloride' in lbl:
        return 'Chloride'
    if 'alkalinity' in lbl or 'alk' in lbl:
        if ' p' in lbl or '-p' in lbl or 'p-alk' in lbl:
            return 'Alkalinity P'
        elif ' m' in lbl or '-m' in lbl or 'm-alk' in lbl:
            return 'Alkalinity M'
        return 'Alkalinity'
    if 'hardness' in lbl:
        return 'Hardness'
    if 'iron' in lbl or 'fe' in lbl:
        return 'Iron'
    if 'base number' in lbl or 'tbn' in lbl or 'bn' in lbl:
        return 'BN'
    if 'nitrite' in lbl:
        return 'Nitrite'
    if 'nitrate' in lbl:
        return 'Nitrate'
    if 'silica' in lbl:
        return 'Silica'
    if 'sulphate' in lbl or 'sulfate' in lbl:
        return 'Sulphate'
    if 'viscosity' in lbl:
        return 'Viscosity'
    if 'turbidity' in lbl:
        return 'Turbidity'
    if 'coliform' in lbl or 'coli' in lbl:
        return 'Coliform'
    if 'tss' in lbl:
        return 'TSS'
    if 'cod' in lbl:
        return 'COD'
    if 'tds' in lbl:
        return 'TDS'
    if 'chlorine' in lbl:
        return 'Chlorine'
    if 'ph' == lbl or lbl.startswith('ph ') or ' ph' in lbl:
        return 'pH'
    
    # Fresh oil pattern (SD0 ME Fresh or similar)
    if 'fresh' in lbl or 'sd0' in lbl:
        return 'Fresh Oil'
    
    # Main Engine patterns - shorten to u1, u2, etc.
    if 'ME' in label.upper() and 'UNIT' in label.upper():
        unit_match = re.search(r'UNIT\s*(\d+)', label, re.IGNORECASE)
        if unit_match:
            return f"Cyl {unit_match.group(1)}"
    
    # Scavenge drain patterns - shorten to u1, u2, etc.
    if 'SD' in label.upper():
        unit_match = re.search(r'UNIT\s*(\d+)', label, re.IGNORECASE)
        if unit_match:
            return f"Cyl {unit_match.group(1)}"
    
    # Aux Boiler patterns
    if 'AUX' in label.upper() and 'BOILER' in label.upper():
        num_match = re.search(r'(\d+)', label)
        if num_match:
            return f"Aux{num_match.group(1)}"
    
    # Aux Engine patterns
    if 'AE' in label.upper() or ('AUX' in label.upper() and 'ENGINE' in label.upper()):
        num_match = re.search(r'(\d+)', label)
        if num_match:
            return f"AE{num_match.group(1)}"
    
    # If short enough, return as is
    if len(label) <= 12:
        return label
    
    return label[:12]

def get_unit_label(title):
    """
    Infer the appropriate Y-axis unit label from the chart title.

    Args:
        title: Chart title containing parameter name

    Returns:
        str: Unit label (e.g., "ppm", "pH", "mg/L") or empty string if unknown
    """
    title_lower = title.lower()
    if "conductivity" in title_lower:
        return "μS/cm"
    if "phosphate" in title_lower:
        return "ppm"
    if "chloride" in title_lower:
        return "ppm"
    if "alkalinity" in title_lower:
        return "mg/L"
    if "hardness" in title_lower:
        return "ppm"
    if "iron" in title_lower and "water" not in title_lower:
        return "mg/L"
    if "base number" in title_lower or "bn" in title_lower:
        return "mg KOH/g"
    if "ph" in title_lower:
        return "pH"
    if "tds" in title_lower:
        return "ppm"
    if "nitrate" in title_lower or "nitrite" in title_lower:
        return "mg/L"
    if "viscosity" in title_lower:
        return "cSt"
    if "water" in title_lower:
        return "ppm"
    return ""




def create_line_chart_by_unit(data, title, color_scheme=None, ideal_low=None, ideal_high=None, unit_field='unit_id', equipment_type=None, show_legend=True):
    """
    Create a line chart with multiple units/equipment, matching website styling.
    
    Args:
        data: List of dicts with measurement records (must have unit_field, parameter_name, measurement_date, value_numeric)
        title: Chart title
        color_scheme: Dict mapping unit_id to color (e.g., BOILER_COLORS)
        ideal_low: Lower ideal range for shading
        ideal_high: Upper ideal range for shading
        unit_field: Field name for unit identifier (e.g., 'unit_id', 'boiler_id', 'engine_id')
    
    Returns:
        BytesIO object containing PNG image
    """
    if not data:
        return None
    
    if color_scheme is None:
        color_scheme = {}
    
    # Organize data by unit
    units_data = defaultdict(list)
    for record in data:
        unit_id = record.get(unit_field, 'Unknown')
        date_str = record.get('measurement_date', '')
        value = record.get('value_numeric')
        
        if value is not None and date_str:
            try:
                date_obj = normalize_date_for_plot(date_str)
                if date_obj is None:
                    continue
                units_data[unit_id].append((date_obj, float(value)))
            except:
                continue
    
    if not units_data:
        return None
    
    # Create figure with website-matching style
    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES, CHART_HEIGHT_INCHES))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('#f8f9fa')
    
    # Add limit lines if provided (single legend entry)
    if is_valid_limit(ideal_low, ideal_high):
        ax.axhline(y=ideal_low, color='#ff8c00', linestyle='-', linewidth=0.8, alpha=0.7, label='Limits', zorder=2)
        ax.axhline(y=ideal_high, color='#ff8c00', linestyle='-', linewidth=0.8, alpha=0.7, zorder=2)
    
    # Plot each unit with website colors
    color_idx = 0
    for unit_id, points in sorted(units_data.items()):
        points.sort(key=lambda x: x[0])
        dates, values = zip(*points)
        
        # Get color from scheme or use generic
        color = color_scheme.get(unit_id, GENERIC_COLORS[color_idx % len(GENERIC_COLORS)])
        
        ax.plot(dates, values, marker='o', linestyle='-', linewidth=0.8,
                markersize=3, color=color, label=compact_label(unit_id), zorder=3)
        color_idx += 1
    
    # Website-matching formatting
    # Title with limits shown below
    ax.set_title(compact_label(title), fontsize=7, fontweight='normal', pad=6, color='#2c3e50')
    if is_valid_limit(ideal_low, ideal_high):
        ax.text(0.5, 1.01, f'Limits: {ideal_low:.1f} - {ideal_high:.1f}', transform=ax.transAxes,
                fontsize=3, color='#888888', ha='center', va='bottom')
    #ax.set_xlabel('Date', fontsize=5, color='#6c757d')  # Removed - intuitive
    ax.set_ylabel(get_unit_label(title), fontsize=5, color='#6c757d')
    
    # Grid styling to match website
    ax.yaxis.grid(True, alpha=0.15, linestyle='-', linewidth=0.5, color='#cccccc')
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    
    # Legend at top (optional)
    if show_legend:
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.22), ncol=10, frameon=False, fontsize=5, columnspacing=0.4)
    
    # Collect all dates to set appropriate x-axis limits
    all_dates = []
    for unit_id, points in units_data.items():
        all_dates.extend([p[0] for p in points])
    
    if all_dates:
        min_date = min(all_dates)
        max_date = max(all_dates)
        date_range = (max_date - min_date).days
        
        # If data spans less than 3 days, pad the axis to show meaningful range
        if date_range < 3:
            from datetime import timedelta
            ax.set_xlim(min_date - timedelta(days=1), max_date + timedelta(days=1))
    
    # Format x-axis dates with limited ticks to avoid overlap
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    # Use date_range (days span) to determine tick interval, not count of measurements
    if all_dates:
        if date_range == 0:
            # Single day - show date without tick marks
            ax.xaxis.set_major_locator(mdates.DayLocator())
            ax.tick_params(axis='x', length=0)
        elif date_range <= 7:
            ax.xaxis.set_major_locator(mdates.DayLocator())
        else:
            # For longer ranges, show ~5 evenly spaced ticks
            interval = max(1, date_range // 5)
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=interval))
    fig.autofmt_xdate(rotation=45, ha="right")
    ax.tick_params(axis='x', labelsize=5)
    ax.tick_params(axis='y', labelsize=5)
    
    # Clean spine styling
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    for spine in ['left', 'bottom']:
        ax.spines[spine].set_color('#dee2e6')
    
    # Extend Y-axis to include all data points with padding
    y_min, y_max = ax.get_ylim()
    padding = (y_max - y_min) * 0.1
    ax.set_ylim(y_min, y_max + padding)

    # plt.tight_layout()  # Disabled - using bbox_inches=tight
    
    # Convert to BytesIO
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf


def create_multi_line_chart(data, parameter_names, title, ideal_low=None, ideal_high=None, equipment_type=None):
    """
    Create a chart with multiple parameters (different lines for each parameter)
    
    Args:
        data: List of measurement records
        parameter_names: List of parameter patterns to include
        title: Chart title
        ideal_low: Lower limit line value
        ideal_high: Upper limit line value
    
    Returns:
        BytesIO object containing PNG image
    """
    if not data:
        return None
    
    # Organize data by parameter and extract limits if not provided
    param_data = defaultdict(list)
    found_low, found_high = None, None
    for record in data:
        param_name = record.get('parameter_name', '')
        date_str = record.get('measurement_date', '')
        value = record.get('value_numeric')
        
        if value is None or not date_str:
            continue
        
        # Extract limits from first record with limits
        if found_low is None and record.get('ideal_low') is not None:
            found_low = record.get('ideal_low')
            found_high = record.get('ideal_high')
        
        # Match parameter
        for pattern in parameter_names:
            if pattern.lower() in param_name.lower():
                try:
                    date_obj = normalize_date_for_plot(date_str)
                    if date_obj is None:
                        continue
                    param_data[param_name].append((date_obj, float(value)))
                except:
                    pass
                break
    
    if not param_data:
        return None
    
    # Use found limits if not explicitly provided
    if ideal_low is None and found_low is not None:
        ideal_low = float(found_low)
    if ideal_high is None and found_high is not None:
        ideal_high = float(found_high)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES, CHART_HEIGHT_INCHES))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('#f8f9fa')
    
    # Add limit lines if available (single legend entry)
    if is_valid_limit(ideal_low, ideal_high):
        ax.axhline(y=ideal_low, color='#ff8c00', linestyle='-', linewidth=0.8, alpha=0.7, label='Limits', zorder=2)
        ax.axhline(y=ideal_high, color='#ff8c00', linestyle='-', linewidth=0.8, alpha=0.7, zorder=2)
    
    color_idx = 0
    for param_name, points in sorted(param_data.items()):
        points.sort(key=lambda x: x[0])
        dates, values = zip(*points)
        
        ax.plot(dates, values, marker='o', linestyle='-', linewidth=0.8,
                markersize=3, color=GENERIC_COLORS[color_idx % len(GENERIC_COLORS)],
                label=compact_label(param_name), zorder=3)
        color_idx += 1
    
    # Title with limits shown below
    ax.set_title(compact_label(title), fontsize=7, fontweight='normal', pad=6, color='#2c3e50')
    if is_valid_limit(ideal_low, ideal_high):
        ax.text(0.5, 1.01, f'Limits: {ideal_low:.1f} - {ideal_high:.1f}', transform=ax.transAxes,
                fontsize=3, color='#888888', ha='center', va='bottom')
    #ax.set_xlabel('Date', fontsize=5, color='#6c757d')  # Removed - intuitive
    ax.set_ylabel(get_unit_label(title), fontsize=5, color='#6c757d')
    ax.yaxis.grid(True, alpha=0.15, linestyle='-', linewidth=0.5, color='#cccccc')
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.22), ncol=10, frameon=False, fontsize=5, columnspacing=0.4)
    
    # Collect all dates to set appropriate x-axis limits
    all_dates_multi = []
    for pname, points in param_data.items():
        all_dates_multi.extend([p[0] for p in points])
    
    if all_dates_multi:
        min_date = min(all_dates_multi)
        max_date = max(all_dates_multi)
        date_range = (max_date - min_date).days
        
        # If data spans less than 3 days, pad the axis
        if date_range < 3:
            from datetime import timedelta
            ax.set_xlim(min_date - timedelta(days=1), max_date + timedelta(days=1))
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    # Use date_range (days span) to determine tick interval
    if all_dates_multi:
        if date_range == 0:
            # Single day - show date without tick marks
            ax.xaxis.set_major_locator(mdates.DayLocator())
            ax.tick_params(axis='x', length=0)
        elif date_range <= 7:
            ax.xaxis.set_major_locator(mdates.DayLocator())
        else:
            interval = max(1, date_range // 5)
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=interval))
    fig.autofmt_xdate(rotation=45, ha="right")
    ax.tick_params(axis='x', labelsize=5)
    ax.tick_params(axis='y', labelsize=5)
    
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    for spine in ['left', 'bottom']:
        ax.spines[spine].set_color('#dee2e6')
    
    # Extend Y-axis to include all data points with padding
    y_min, y_max = ax.get_ylim()
    padding = (y_max - y_min) * 0.1
    ax.set_ylim(y_min, y_max + padding)

    # plt.tight_layout()  # Disabled - using bbox_inches=tight
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf


def create_scatter_chart(data, x_param, y_param, title, color_scheme=None, group_field='sampling_point_name', show_legend=True, size_multiplier=1.0):
    """
    Create scatter plot (e.g., for scavenge drain Iron vs Base Number)
    
    Args:
        data: List of measurement records
        x_param: X-axis parameter pattern
        y_param: Y-axis parameter pattern
        title: Chart title
        color_scheme: Dict mapping group values to colors
        group_field: Field to group/color by
    
    Returns:
        BytesIO object containing PNG image
    """
    if not data:
        return None
    
    if color_scheme is None:
        color_scheme = {}
    
    # Organize data by group and date for matching x/y pairs
    date_groups = defaultdict(lambda: defaultdict(dict))
    
    for record in data:
        group_val = record.get(group_field, 'Unknown')
        param_name = record.get('parameter_name', '')
        date_str = record.get('measurement_date', '')
        value = record.get('value_numeric')
        
        if value is None or not date_str:
            continue
        
        if x_param.lower() in param_name.lower():
            date_groups[group_val][date_str[:10]]['x'] = float(value)
        elif y_param.lower() in param_name.lower():
            date_groups[group_val][date_str[:10]]['y'] = float(value)
    
    # Create figure - scatter plots slightly wider for better aspect ratio
    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES * size_multiplier, CHART_HEIGHT_INCHES * size_multiplier))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('#f8f9fa')
    
    has_data = False
    color_idx = 0
    
    for group_val, date_points in sorted(date_groups.items()):
        x_vals = []
        y_vals = []
        
        for date_str, vals in date_points.items():
            if 'x' in vals and 'y' in vals:
                x_vals.append(vals['x'])
                y_vals.append(vals['y'])
        
        if x_vals and y_vals:
            color = color_scheme.get(group_val, GENERIC_COLORS[color_idx % len(GENERIC_COLORS)])
            
            ax.scatter(x_vals, y_vals, s=40, alpha=0.8, color=color,
                      label=compact_label(group_val), edgecolors='white', linewidth=0.5, zorder=3)
            has_data = True
            color_idx += 1
    
    if not has_data:
        plt.close(fig)
        return None
    
    ax.set_title(compact_label(title), fontsize=12, fontweight='normal', pad=6, color='#2c3e50')
    ax.set_xlabel(x_param, fontsize=8, color='#6c757d')
    ax.set_ylabel(y_param, fontsize=8, color='#6c757d')
    ax.yaxis.grid(True, alpha=0.15, linestyle='-', linewidth=0.5, color='#cccccc')
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    
    if show_legend:
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.22), ncol=10, frameon=False, fontsize=5, columnspacing=0.4)
    
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    for spine in ['left', 'bottom']:
        ax.spines[spine].set_color('#dee2e6')
    
    # Extend Y-axis to include all data points with padding
    y_min, y_max = ax.get_ylim()
    padding = (y_max - y_min) * 0.1
    ax.set_ylim(y_min, y_max + padding)

    # plt.tight_layout()  # Disabled - using bbox_inches=tight
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf


# ============================================================
# TABLE AND STYLE UTILITIES
# ============================================================

def create_summary_table(data, column_headers, title=None):
    """
    Create a formatted table for PDF

    Args:
        data: List of lists (rows)
        column_headers: List of column headers
        title: Optional table title

    Returns:
        Table object for ReportLab
    """
    if not data:
        return None

    # Prepare table data
    table_data = [column_headers] + data

    # Create table
    table = Table(table_data, repeatRows=1)

    # Professional styling
    table.setStyle(TableStyle([
        # Header style
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 14),
        ('TOPPADDING', (0, 0), (-1, 0), 14),
        # Body style
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))

    return table


def format_date(date_str):
    """Format date string for display"""
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d')
    except:
        return date_str


def format_date_short(date_obj):
    """Format date object for cover page display (e.g., '12 Nov 25')"""
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.fromisoformat(date_obj.replace('Z', '+00:00'))
        except:
            return date_obj
    return date_obj.strftime('%d %b %y')


def get_status_color(status):
    """Get color for status indicator"""
    status_colors = {
        'NORMAL': colors.HexColor('#28a745'),
        'OKAY': colors.HexColor('#28a745'),
        'LOW': colors.HexColor('#ffc107'),
        'HIGH': colors.HexColor('#dc3545'),
        'CRITICAL': colors.HexColor('#721c24')
    }
    return status_colors.get(status, colors.grey)


def create_header_style():
    """Create paragraph style for headers"""
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=16,
        spaceBefore=8,
        alignment=TA_LEFT,
        fontName='Helvetica-Bold'
    )
    return header_style


def create_section_style():
    """Create paragraph style for section headers"""
    styles = getSampleStyleSheet()
    section_style = ParagraphStyle(
        'CustomSection',
        parent=styles['Heading2'],
        fontSize=15,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=10,
        spaceBefore=14,
        alignment=TA_LEFT,
        fontName='Helvetica-Bold'
    )
    return section_style


def create_subsection_style():
    """Create paragraph style for subsection headers"""
    styles = getSampleStyleSheet()
    subsection_style = ParagraphStyle(
        'CustomSubsection',
        parent=styles['Heading3'],
        fontSize=13,
        textColor=colors.HexColor('#5a6c7d'),
        spaceAfter=8,
        spaceBefore=10,
        alignment=TA_LEFT,
        fontName='Helvetica-Bold'
    )
    return subsection_style


# ============================================================
# LEGACY CHART FUNCTIONS (for page_report_utils.py compatibility)
# ============================================================

def prepare_chart_data(raw_data, parameter_names):
    """
    Reorganize raw measurement data for charting

    Args:
        raw_data: List of measurement records from database
        parameter_names: List of parameter name patterns to match

    Returns:
        dict: {parameter_name: [(date, value), ...]}
    """
    organized = defaultdict(list)

    for record in raw_data:
        param_name = record.get('parameter_name', '')
        value = record.get('value_numeric')
        date_str = record.get('measurement_date')

        if value is None or not date_str:
            continue

        try:
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))

            # Match parameter name with fuzzy matching
            for pattern in parameter_names:
                if pattern.lower() in param_name.lower():
                    organized[param_name].append((date_obj, float(value)))
                    break
        except:
            continue

    # Sort by date
    for param in organized:
        organized[param].sort(key=lambda x: x[0])

    return dict(organized)


# Legacy color palette
COLORS = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6A994E', '#BC4B51', '#5B8E7D', '#8B5A3C']


def create_multi_parameter_chart(data, parameter_names, title, equipment_name=None):
    """
    Create a chart with multiple parameters on same plot (legacy function)

    Args:
        data: List of measurement records
        parameter_names: List of parameter patterns to plot
        title: Chart title
        equipment_name: Optional equipment filter

    Returns:
        PIL Image object
    """
    if not data:
        return None

    # Prepare data
    chart_data = prepare_chart_data(data, parameter_names)

    if not chart_data:
        return None

    # Create figure with professional styling
    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES, CHART_HEIGHT_INCHES))
    fig.patch.set_facecolor('white')

    # Plot each parameter with different color
    color_idx = 0
    for param_name, dates_values in chart_data.items():
        if dates_values:
            dates, values = zip(*dates_values)
            ax.plot(dates, values, marker='o', linestyle='-', linewidth=1.0,
                   markersize=4, color=COLORS[color_idx % len(COLORS)],
                   label=param_name, alpha=0.9, zorder=3)
            color_idx += 1

    # Formatting
    ax.set_title(compact_label(title), fontsize=7, fontweight='normal', pad=6, color='#2c3e50')
    ax.set_xlabel('Date', fontsize=5, fontweight='600', color='#34495e')
    ax.set_ylabel(get_unit_label(title), fontsize=5, fontweight='600', color='#34495e')
    ax.yaxis.grid(True, alpha=0.15, linestyle='-', linewidth=0.5, color='#cccccc')
    ax.xaxis.grid(False)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.22), ncol=10, frameon=False, fontsize=5, columnspacing=0.4)  #

    # Collect all dates to set appropriate x-axis limits
    all_dates_chart = []
    for pname, points in chart_data.items():
        all_dates_chart.extend([p[0] for p in points])
    
    if all_dates_chart:
        min_date = min(all_dates_chart)
        max_date = max(all_dates_chart)
        date_range = (max_date - min_date).days
        
        # If data spans less than 3 days, pad the axis
        if date_range < 3:
            from datetime import timedelta
            ax.set_xlim(min_date - timedelta(days=1), max_date + timedelta(days=1))
    
    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    # Use date_range (days span) to determine tick interval
    if all_dates_chart:
        if date_range == 0:
            # Single day - show date without tick marks
            ax.xaxis.set_major_locator(mdates.DayLocator())
            ax.tick_params(axis='x', length=0)
        elif date_range <= 7:
            ax.xaxis.set_major_locator(mdates.DayLocator())
        else:
            interval = max(1, date_range // 5)
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=interval))
    fig.autofmt_xdate(rotation=45, ha="right")
    ax.tick_params(axis='x', labelsize=5)
    ax.tick_params(axis='y', labelsize=5)

    # Style improvements
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cccccc')
    ax.spines['bottom'].set_color('#cccccc')

    # Extend Y-axis to include all data points with padding
    y_min, y_max = ax.get_ylim()
    padding = (y_max - y_min) * 0.1
    ax.set_ylim(y_min, y_max + padding)

    # plt.tight_layout()  # Disabled - using bbox_inches=tight

    # Convert to image
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)

    buf.seek(0); return buf


def create_scatter_plot(data, x_param, y_param, title, group_by='sampling_point_code'):
    """
    Create scatter plot (legacy function for page_report_utils.py)

    Args:
        data: List of measurement records
        x_param: X-axis parameter pattern
        y_param: Y-axis parameter pattern
        title: Chart title
        group_by: Field to group points by (for coloring)

    Returns:
        PIL Image object
    """
    if not data:
        return None

    # Organize data by groups
    groups = defaultdict(lambda: {'x': [], 'y': []})

    for record in data:
        group_val = record.get(group_by, 'Unknown')
        param_name = record.get('parameter_name', '')
        value = record.get('value_numeric')

        if value is None:
            continue

        # Match to x or y parameter
        if x_param.lower() in param_name.lower():
            groups[group_val]['x'].append(float(value))
        elif y_param.lower() in param_name.lower():
            groups[group_val]['y'].append(float(value))

    # Create figure
    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES, CHART_HEIGHT_INCHES))
    fig.patch.set_facecolor('white')

    has_data = False
    color_idx = 0

    for group_name, group_data in groups.items():
        # Match x and y by ensuring equal lengths
        x_vals = group_data['x']
        y_vals = group_data['y']

        if x_vals and y_vals:
            # Take minimum length to avoid mismatched data
            min_len = min(len(x_vals), len(y_vals))
            if min_len > 0:
                ax.scatter(x_vals[:min_len], y_vals[:min_len],
                          s=50, alpha=0.7, color=COLORS[color_idx % len(COLORS)],
                          label=group_name, edgecolors='white', linewidth=0.5, zorder=3)
                has_data = True
                color_idx += 1

    if not has_data:
        plt.close(fig)
        return None

    # Formatting
    ax.set_title(compact_label(title), fontsize=7, fontweight='normal', pad=6, color='#2c3e50')
    ax.set_xlabel(x_param, fontsize=5, fontweight='600', color='#34495e')
    ax.set_ylabel(get_unit_label(title), fontsize=5, fontweight='600', color='#34495e')
    ax.yaxis.grid(True, alpha=0.15, linestyle='-', linewidth=0.5, color='#cccccc')
    ax.xaxis.grid(False)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.22), ncol=10, frameon=False, fontsize=5, columnspacing=0.4)  #

    # Style improvements
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cccccc')
    ax.spines['bottom'].set_color('#cccccc')

    # Extend Y-axis to include all data points with padding
    y_min, y_max = ax.get_ylim()
    padding = (y_max - y_min) * 0.1
    ax.set_ylim(y_min, y_max + padding)

    # plt.tight_layout()  # Disabled - using bbox_inches=tight

    # Convert to image
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)

    buf.seek(0); return buf
    ax.tick_params(axis='y', labelsize=5)


def create_legend_only_chart(raw_unit_names, title="Scavenge Drain Legend"):
    """
    Create a chart that only displays a legend (no data plot).
    Uses same sorting as charts for color consistency.
    
    Args:
        raw_unit_names: List of raw sampling_point_names (will be sorted and compacted)
        title: Title for the legend panel
    
    Returns:
        BytesIO object containing PNG image
    """
    if not raw_unit_names:
        return None
    
    # Create figure - 25% smaller
    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES * 1.55, CHART_HEIGHT_INCHES * 1.55))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('#f8f9fa')
    
    # Hide all axes
    ax.axis('off')
    
    # Sort the same way as charts do (by raw name), then apply compact_label
    handles = []
    for idx, raw_name in enumerate(sorted(raw_unit_names)):
        color = GENERIC_COLORS[idx % len(GENERIC_COLORS)]
        display_label = compact_label(raw_name)
        line, = ax.plot([], [], marker='o', linestyle='-', linewidth=2,
                       markersize=8, color=color, label=display_label)
        handles.append(line)
    
    # Create large, centered legend
    legend = ax.legend(
        handles=handles,
        loc='center',
        ncol=3,  # 3 columns for better layout
        frameon=True,
        fontsize=6,
        columnspacing=1.5,
        handlelength=2,
        handleheight=1.5,
        borderpad=1.5,
        labelspacing=1.2
    )
    legend.get_frame().set_facecolor('white')
    legend.get_frame().set_edgecolor('#dee2e6')
    legend.get_frame().set_linewidth(0.5)
    
    # Convert to image
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    
    return buf
