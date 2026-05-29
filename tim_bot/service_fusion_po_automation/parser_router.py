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
from parser_broadway_national import parse_broadway_national_po
from parser_frontstreet import parse_frontstreet_po
from parser_smile_doctors import parse_smile_doctors_po
from parser_rolland import parse_rolland_po
from parser_cornell import parse_cornell_po
from parser_tcg import parse_tcg_po
from parser_lakeside import parse_lakeside_po
from parser_ems import parse_ems_po
from parser_evo import parse_evo_po
from parser_23rdgroup import parse_23rdgroup_po
from parser_prs import parse_prs_po
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

    if (
        "enternest.com" in lower
        or "isp connect" in lower
        or "megan.ryan@enternest.com" in lower
    ):
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
    
    if "broadway national" in lower or "umbrava" in lower:
        return parse_broadway_national_po(pdf_path)

    if "frontstreet" in lower or "front street" in lower or "frontstreetfs.com" in lower:
        return parse_frontstreet_po(pdf_path)

    if "smile doctors" in lower:
        return parse_smile_doctors_po(pdf_path)

    if "rolland holding company" in lower or "rollandsolutions.com" in lower or "rslc.net" in lower:
        return parse_rolland_po(pdf_path)

    if "cornell storefront" in lower or "clopay" in lower or "cornellstorefronts.com" in lower:
        return parse_cornell_po(pdf_path)

    if "tcg services" in lower or "tcgfm.com" in lower:
        return parse_tcg_po(pdf_path)

    if "lakeside project solutions" in lower or "lpsfacilities.com" in lower:
        return parse_lakeside_po(pdf_path)

    if "emergency maintenance solutions" in lower or "570-730-7760" in lower:
        return parse_ems_po(pdf_path)

    if "evo door" in lower or "evo office" in lower or "844-344-3012" in lower:
        return parse_evo_po(pdf_path)

    if (
        "23rdgroup.com" in lower
        or "work order contact:" in lower
        or "kimberlyp@23rdgroup.com" in lower
        or "704-823-6108" in lower
    ):
        return parse_23rdgroup_po(pdf_path)

    if "professional retail services" in lower or "profretail.com" in lower:
        return parse_prs_po(pdf_path)

    raise ValueError("Unknown PO format. Add a new provider parser.")