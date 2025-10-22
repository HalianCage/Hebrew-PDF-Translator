# legend_utils.py

# Install dependencies
# These should be run once in your main application setup or environment:
# !pip install PyPDF2 pikepdf PyMuPDF reportlab python-abbreviate

import fitz  # PyMuPDF
import re
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, grey, whitesmoke
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import io

# Paragraph style for wrapping
styles = getSampleStyleSheet()
styleN = styles["Normal"]
styleN.fontName = "Helvetica"
styleN.fontSize = 9
styleN.wordWrap = 'CJK'


def refine_abbreviation(term, used_codes, max_len=3):
    """
    Generates a short, unique abbreviation for a given term without
    relying on any external libraries.

    Args:
        term (str): The full string to be abbreviated.
        used_codes (dict): A dictionary tracking terms and the codes
                           already assigned to them to prevent duplicates.
        max_len (int): The target length for abbreviations of single words.

    Returns:
        str: The generated unique abbreviation.
    """
    # 1. Generate a candidate abbreviation
    words = term.split()
    if len(words) > 1:
        # Use regex to find the first alphabetic character in each word
        acronym_parts = []
        for word in words:
            match = re.search(r'[a-zA-Z]', word)
            if match:
                acronym_parts.append(match.group(0).upper())
                if len(acronym_parts) > 2:
                    break
        candidate = "".join(acronym_parts)
    else:
        # If it's a single word, truncate it
        candidate = term[:max_len].upper()

    # 2. Ensure the candidate isn't empty
    if not candidate:
        candidate = term[:max_len].upper()

    # 3. Handle duplicates by adding a number
    if candidate in used_codes.values():
        # First, check if this exact term has already been abbreviated
        for k, v in used_codes.items():
            if k == term:
                return v # Return the existing abbreviation

        # If not, find a new unique code by appending a number
        idx = 1
        new_code = f"{candidate}{idx}"
        while new_code in used_codes.values():
            idx += 1
            new_code = f"{candidate}{idx}"
        candidate = new_code

    # 4. Store and return the unique code
    used_codes[term] = candidate
    return candidate


def determine_legend_font_size(avg_font_size, min_font_size=7):
    """
    Returns a readable legend font size based on a heuristic average, with a floor.
    """
    return max(avg_font_size, min_font_size)


def _create_legend_data_from_terms(legend_terms_dict):
    """
    Build a 2D list suitable for reportlab's Table from a dict of {code: term}.
    Wraps long meanings using a Paragraph so they line-break inside the table cell.
    """
    data = [["Code", "Meaning"]]
    for code, term in legend_terms_dict.items():
        meaning_para = Paragraph(term, styleN)
        data.append([code, meaning_para])
    return data


def create_legend_pdf_page(legend_terms, page_height, page_width):
    """
    Create a single-page PDF in memory containing ONLY the legend table.

    Inputs:
    - legend_terms: dict like {'GAD': 'General Arrangement Drawing'}
    - page_height: float
    - page_width: float

    Logic:
    - Use reportlab to create a Table from the legend_terms
    - Style the table via TableStyle
    - Draw onto an in-memory canvas sized to (page_width x page_height)

    Output:
    - Returns a fitz.Document loaded from the in-memory PDF stream
    """
    # Prepare table data
    table_data = _create_legend_data_from_terms(legend_terms)

    # Create reportlab table and style
    table = Table(table_data, colWidths=[70, page_width - 90])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, black),
        ('VALIGN', (0, 1), (-1, -1), 'TOP'),
    ]))

    # Lay out table and draw to a PDF page in memory
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))

    # Compute table size and place at a margin from the top-right inside legend page
    available_w = page_width - 20
    available_h = page_height - 20
    wrapped_w, wrapped_h = table.wrap(available_w, available_h)
    x = 10
    y = page_height - wrapped_h - 10
    table.drawOn(c, x, y)

    c.showPage()
    c.save()
    packet.seek(0)

    # Return as a fitz.Document
    legend_doc = fitz.open(stream=packet.read(), filetype="pdf")
    return legend_doc

# NOTE:
# The previous raster-based functions (get_corner_color, crop_blank_margins, create_canvas_with_image,
# add_legends_to_pdf, etc.) have been removed in favor of a vector-first, in-memory approach.