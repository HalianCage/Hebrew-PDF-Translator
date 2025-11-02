# ==============================================================================
# ALL OUTPUT PDF RELATED FUNCTIONS FILE
# ==============================================================================


import fitz
from utils.legends_util import refine_abbreviation


def get_optimal_fontsize(rect, text, fontname="helv", max_fontsize=12, line_height_factor=1.2):
    """
    Calculates the optimal font size to fit text within a rectangle,
    considering BOTH width and height.
    """
    # 1. Calculate optimal size based on width (same as before)
    width_optimal_size = max_fontsize
    text_len_at_size_1 = fitz.get_text_length(text, fontname=fontname, fontsize=1)
    if text_len_at_size_1 > 0:
        width_optimal_size = rect.width / text_len_at_size_1

    # 2. Calculate optimal size based on height
    # The rendered height of a line of text is roughly fontsize * 1.2
    height_optimal_size = rect.height / line_height_factor

    # 3. The true optimal size is the SMALLER of the two constraints
    optimal_size = min(width_optimal_size, height_optimal_size)

    # 4. Return the final size, capped by the maximum allowed font size
    return min(int(optimal_size), max_fontsize)





def prepare_display_data(translated_data):
    """
    Enrich translated items by deciding whether to display full text or an abbreviation,
    and collect legend terms for any abbreviated entries.

    Input: translated_data (list of dicts from translate_chinese_to_english)
    Output: (enriched_translated_data, legend_terms)
    - enriched_translated_data: list with additional 'display_text' per item
    - legend_terms: dict mapping {code: full term}
    """
    legend_terms = {}
    used_codes = {}
    enriched = []

    for item in translated_data:
        english = (item.get("english_translation") or "").strip()
        display_text = english
        # Simple heuristic: abbreviate if longer than 4 words

        original_bbox = fitz.Rect(item["bbox"])
        max_fontsize_possible = get_optimal_fontsize(original_bbox, display_text)

        if max_fontsize_possible < 4:
            code = refine_abbreviation(english, used_codes)
            display_text = code
            legend_terms[code] = english
        enriched.append({**item, "display_text": display_text})

    return enriched, legend_terms

def create_translated_doc_in_memory(doc, enriched_translated_data):
    """
    Build a translated PDF (vector-first) in memory. Instead of writing to disk, return the fitz.Document.
    Uses 'display_text' for overlayed content (may be full term or abbreviation).
    """
    output_doc = fitz.open()
    for page_num in range(doc.page_count):
        page = doc[page_num]
        output_page = output_doc.new_page(width=page.rect.width, height=page.rect.height)
        output_page.show_pdf_page(page.rect, doc, page_num)
        for item in enriched_translated_data:
            if item["page"] == page_num:
                original_bbox = fitz.Rect(item["bbox"])
                display_text = item.get("display_text", item.get("english_translation", ""))
                if display_text:
        
                    best_fsize = get_optimal_fontsize(original_bbox, display_text)

                    leftover = -1
                    font_size = best_fsize

                    while leftover<0 and font_size >= 4:

                        # Draw the rectangle
                        output_page.draw_rect(original_bbox, color=(1, 1, 1), fill=(1, 1, 1), overlay=True, )

                        # Insert the text
                        leftover = output_page.insert_textbox(
                            original_bbox, display_text, fontsize=font_size, fontname="helv",
                            color=(0, 0, 0), align=fitz.TEXT_ALIGN_CENTER, overlay=True
                        )

                        font_size -= 1

                    print(f"display_text:{display_text}, leftover: {leftover}")
                    
    return output_doc


def assemble_final_pdf(translated_doc, legend_doc, output_path):
    """
    Assemble each translated page with a corresponding legend page on the right
    into a new, wider final PDF, and save to output_path.
    """
    final_doc = fitz.open()

    # Assume single-page legend reused for each page; size defines legend panel width
    legend_page = legend_doc[0] if legend_doc and legend_doc.page_count > 0 else None

    for i in range(translated_doc.page_count):
        t_page = translated_doc[i]
        t_rect = t_page.rect
        l_rect = legend_page.rect if legend_page else fitz.Rect(0, 0, 0, t_rect.height)
        new_width = t_rect.width + l_rect.width
        new_height = max(t_rect.height, l_rect.height)
        new_page = final_doc.new_page(width=new_width, height=new_height)

        # Stamp translated page at left
        new_page.show_pdf_page(fitz.Rect(0, 0, t_rect.width, t_rect.height), translated_doc, i)

        # Stamp legend page at right (if exists)
        if legend_page:
            new_page.show_pdf_page(
                fitz.Rect(t_rect.width, 0, t_rect.width + l_rect.width, l_rect.height), legend_doc, 0
            )

    final_doc.save(output_path)
    final_doc.close()
