# parser_router.py
from parser_colt import parse_colt_po
from parser_dynamic import parse_dynamic_po
from parser_legacy import parse_legacy_po
from parser_nest import parse_nest_po
from parser_bass import parse_bass_po
from parser_keuper import parse_keuper_po
from parser_rram import parse_rram_po
from parser_buckle import parse_buckle_po
from parser_true_source import parse_true_source_po
from parser_retailmds import parse_retailmds_po
from parser_dhpace import parse_dhpace_po
from parser_cellular_sales import parse_cellular_sales_po
from pdf_text import extract_text


def parse_po(pdf_path):
    text = extract_text(pdf_path)
    lower = text.lower()

    if "coltfacility.com" in lower or "service partner dispatch" in lower:
        return parse_colt_po(pdf_path)

    if "dynamic-es.com" in lower or "dynamics order #" in lower:
        return parse_dynamic_po(pdf_path)

    if "legacy group enterprises" in lower or "legacyfms.com" in lower:
        return parse_legacy_po(pdf_path)

    if "nest details" in lower or ("work order #" in lower and "not to exceed" in lower):
        return parse_nest_po(pdf_path)
        
    if "bass-security.com" in lower or "bass security" in lower or "bass number" in lower:
        return parse_bass_po(pdf_path)
    
    if "gobuildit.com" in lower or "keuper construction" in lower or "pnc work task" in lower:
        return parse_keuper_po(pdf_path)

    if "rram services" in lower or "rramservices.com" in lower:
        return parse_rram_po(pdf_path)

    if "the buckle" in lower or "fexa.io" in lower:
        return parse_buckle_po(pdf_path)

    if "truesource" in lower or "true source" in lower or "affiliate connect" in lower:
        return parse_true_source_po(pdf_path)
    
    if "retail mds" in lower or "retailmds.com" in lower:
        return parse_retailmds_po(pdf_path)

    if "dh pace" in lower or "dhpace.com" in lower:
        return parse_dhpace_po(pdf_path)

    if "cellular sales" in lower or "cellularsales.com" in lower:
        return parse_cellular_sales_po(pdf_path)

    raise ValueError("Unknown PO format. Add a new provider parser.")