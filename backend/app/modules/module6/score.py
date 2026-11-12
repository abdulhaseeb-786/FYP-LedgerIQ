from datetime import date
from difflib import SequenceMatcher

# ---------- SETTINGS (the only numbers that tune the scores) ----------

# a unit price gap of 5% or more between invoice and PO gives a price score of 0
PRICE_TOLERANCE = 0.05

# a gap of 30 days or more between two dates gives a date score of 0
DATE_WINDOW_DAYS = 30

# if the invoice is dated BEFORE the PO's expected receipt date or the receipt date,
# the gap counts double (suspicious direction); a later invoice counts normally
EARLY_FACTOR = 1.5

# a pair of lines whose id score (or description score, if no id) is below this is not matched at all
MATCH_THRESHOLD = 0.2

# ---------- BLOCK 2: DATE SCORE ----------

def date_score(invoice_date, other_date):
    # invoice_date and other_date are real date objects (read_data already converted them)
    # other_date is the PO's expected receipt date or the receipt date

    # subtracting two dates gives a timedelta; .days turns it into a plain number of days
    # positive = invoice came AFTER the other date, negative = invoice came BEFORE it
    gap = (invoice_date - other_date).days

    # we only care how big the gap is, not its sign, so take the absolute value
    size = abs(gap)

    # an invoice dated before the goods were due/received is suspicious,
    # so its gap counts EARLY_FACTOR times (2 = double)
    if gap < 0:
        size = size * EARLY_FACTOR

    # straight-line score: gap 0 -> 1.0, gap = DATE_WINDOW_DAYS -> 0.0
    score = 1 - size / DATE_WINDOW_DAYS

    # a gap bigger than the window would go below 0, so we stop it at 0
    return max(0, score)

# ---------- BLOCK 3: PRICE SCORE ----------

def price_score(invoice_price, po_price):
    # both are floats (read_data already converted them)

    # guard: a PO price of 0 would make the division below crash
    # a zero-price PO cannot be compared by percentage, so it gets score 0
    if po_price == 0:
        return 0

    # how far apart the prices are, as a fraction of the PO price
    # e.g. PO 15.00 and invoice 15.75 -> 0.75 / 15.00 = 0.05 (a 5% gap)
    # abs() because here we only score the size of the gap, not its direction
    # (red vs yellow for higher vs lower price is decided later in main.py)
    gap = abs(invoice_price - po_price) / po_price

    # straight-line score: gap 0 -> 1.0, gap = PRICE_TOLERANCE -> 0.0
    score = 1 - gap / PRICE_TOLERANCE

    # a gap bigger than the tolerance would go below 0, so we stop it at 0
    return max(0, score)

# ---------- BLOCK 4: ID and NAME MATCH SCORES (each only returns a score between 0 and 1) ----------
# po id on purchase order and invoice
def id_score(id_a, id_b): 
    # longest run of characters that appears in BOTH ids, as a fraction of the longer id
    # e.g. "po_001" vs "po_001_x" -> shared run "po_001" (6 chars) / 8 = 0.75

    # a missing id (None) or an empty one cannot be compared, so it scores 0
    if not id_a or not id_b:
        return 0

    # find_longest_match looks at the whole of both strings and returns the longest shared run
    match = SequenceMatcher(None, id_a, id_b).find_longest_match(0, len(id_a), 0, len(id_b))

    # match.size = number of characters in that run; divide by the longer id so the score stays 0 to 1
    return match.size / max(len(id_a), len(id_b))

def description_score(desc_a, desc_b):
    # overall similarity of two descriptions: 1.0 = identical, 0.0 = nothing in common
    # (read_data already stripped and lowercased the descriptions, so case and spaces don't matter)

    # a missing or empty description cannot be compared, so it scores 0
    if not desc_a or not desc_b:
        return 0

    # ratio() compares the whole strings and returns a number from 0 to 1
    return SequenceMatcher(None, desc_a, desc_b).ratio()

# ---------- BLOCK 5: INVOICE-PO EDGES ----------

def invoice_po_scores(inv_nodes, po_nodes):
    # returns {(invoice_line_id, po_line_id): score}
    # no filtering here: your pseudocode says id/fuzzy filtering is not used for this fixture,
    # so EVERY invoice line is paired with EVERY PO line
    edges = {}                                           # empty dictionary, filled below

    for inv in inv_nodes:                                # one invoice line at a time

        inv_po_ref = inv.get("po_ref")
        id_available = bool(inv_po_ref) 

        for po in po_nodes:                              # pair it with every PO line

            
            # name similarity between the two lines, 0 to 1
            desc = description_score(inv["description"], po["description"])

            # GATE: if an id exists, compare PO numbers; otherwise compare descriptions
            # (po_id = the PO document number, the line id is not used here)
            if id_available:
                ident = id_score(inv_po_ref, po["po_id"])
                gate = ident
            else:
                ident = 0                                # no id, so it adds nothing to the sum
                gate = desc

            # below the threshold = not the same item: do NOT store the pair, so no triple can use it
            if gate < MATCH_THRESHOLD:
                edges[(inv["id"], po["id"])] = 0
                continue
            

            # if score below a threshold (0.25?), score 0 and continue

            # date part: invoice date vs the PO's expected receipt date
            # the field can be empty (None), and we cannot subtract a missing date, so it scores 0
            if po["expected_receipt_date"] is None:
                d = 0
            else:
                d = date_score(inv["date"], po["expected_receipt_date"])

            # price part: invoice unit price vs PO unit price
            p = price_score(inv["unit_price"], po["unit_price"])

            # fuzzy match score on name
            # character match on id

            # the edge score is the plain sum of the two parts (no weights), so it is between 0 and 2
            edges[(inv["id"], po["id"])] = d + p + desc # + ident

    return edges


# ---------- BLOCK 6: INVOICE-RECEIPT EDGES ----------

def invoice_receipt_scores(inv_nodes, rcpt_nodes):
    # returns {(invoice_line_id, receipt_line_id): score}
    # pairs every invoice line with every receipt line
    edges = {}                                           # empty dictionary, filled below

    for inv in inv_nodes:                                # one invoice line at a time
        for rcpt in rcpt_nodes:                          # pair it with every receipt line

            
            # name similarity between the two lines, 0 to 1
            # (rcpt["description"] holds sku_raw from read_data)
            desc = description_score(inv["description"], rcpt["description"])

            # below the threshold = not the same item: do NOT store the pair, so no triple can use it
            if desc < MATCH_THRESHOLD:
                edges[(inv["id"], rcpt["id"])] = 0
                continue
            

            # date part: invoice date vs receipt date (when goods were actually received)
            # if date is missing (None), cannot calculate difference, so score is 0
            if rcpt["date"] is None or inv["date"] is None:
                d = 0
            else:
                d = date_score(inv["date"], rcpt["date"])

            # the edge score is currently based on the date score (0 to 1)
            # (uncomment + desc above and below if description matching is enabled later)
            edges[(inv["id"], rcpt["id"])] = d + desc

    return edges


# ---------- BLOCK 7: PO-RECEIPT EDGES ----------

def po_receipt_scores(po_nodes, rcpt_nodes):
    # returns {(po_line_id, receipt_line_id): score}
    # pairs every PO line with every receipt line
    edges = {}                                           # empty dictionary, filled below

    for po in po_nodes:                                  # one PO line at a time
        for rcpt in rcpt_nodes:                          # pair it with every receipt line

            # PO reference id on receipt (e.g. "po_ref" or "related_purchase_order_id")
            rcpt_po_ref = rcpt.get("po_ref") or rcpt.get("related_purchase_order_id")
            id_available = bool(rcpt_po_ref)

            # name similarity between the two lines, 0 to 1
            # (po["description"] vs receipt sku_raw, stored in rcpt["description"])
            desc = description_score(rcpt["description"], po["description"])

            # GATE: if an id exists, compare PO numbers; otherwise compare descriptions
            # (po["po_id"] = the PO document number, e.g. "po_001")
            if id_available:
                ident = id_score(rcpt_po_ref, po["po_id"])
                gate = ident
            else:
                ident = 0                                # no id, so it adds nothing to the sum
                gate = desc

            # below the threshold = not the same item: filter out by setting score to 0
            if gate < MATCH_THRESHOLD:
                edges[(po["id"], rcpt["id"])] = 0
                continue

            # date part: expected receipt date on PO vs actual receipt date
            # if expected date or received date is missing (None), cannot calculate difference, so score is 0
            if po["expected_receipt_date"] is None or rcpt["date"] is None:
                d = 0
            else:
                d = date_score(rcpt["date"], po["expected_receipt_date"])

            # edge score: sum of date score, id match (if present), and description similarity
            edges[(po["id"], rcpt["id"])] = d + desc # + ident 

    return edges


# ---------- BLOCK 8: TRIPLE SCORES (INVOICE, PO, RECEIPT) ----------

def build_triples(inv_nodes = None, po_nodes = None, rcpt_nodes = None, inv_po_edges=None, inv_rcpt_edges=None, po_rcpt_edges=None):
    # returns {(invoice_line_id, po_line_id, receipt_line_id): total_score}
    #
    # if edge dictionaries are not already provided, calculate them using the functions above:
    if inv_po_edges is None:
        inv_po_edges = invoice_po_scores(inv_nodes, po_nodes)

    if inv_rcpt_edges is None:
        inv_rcpt_edges = invoice_receipt_scores(inv_nodes, rcpt_nodes)

    if po_rcpt_edges is None:
        po_rcpt_edges = po_receipt_scores(po_nodes, rcpt_nodes)

    triples = {}                                         # empty dictionary, filled below

    # triple loop: combine every invoice line with every PO line and every receipt line
    for inv in inv_nodes:
        inv_id = inv["id"]

        for po in po_nodes:
            po_id = po["id"]
            s_inv_po = inv_po_edges.get((inv_id, po_id), 0)

            for rcpt in rcpt_nodes:
                rcpt_id = rcpt["id"]
                s_inv_rcpt = inv_rcpt_edges.get((inv_id, rcpt_id), 0)
                s_po_rcpt = po_rcpt_edges.get((po_id, rcpt_id), 0)

                # sum all three edge scores for this triple
                total_score = s_inv_po + s_inv_rcpt + s_po_rcpt

                # optional: reward connection if both invoice-po and invoice-receipt are strong
                # reward = max(s_inv_po, s_inv_rcpt) * 0.1
                # total_score += reward

                # round to 4 decimals to avoid tiny floating point precision artifacts (e.g. 2.7000000000000002)
                triples[(inv_id, po_id, rcpt_id)] = round(total_score, 4)

    return triples

# alias so both build_triples and triple_scores can be used
triple_scores = build_triples

"""
triples = {
    ("inv1", "po1", "r1"): 2.7,
    ("inv1", "po1", "r2"): 2.1,
    ("inv2", "po1", "r1"): 2.4,
    ("inv2", "po1", "r2"): 1.5,
}
"""