# todo - duplicate check in data

import json  
import os 
from datetime import datetime

class Data:
    # Reads the fixtures file and holds one list of nodes each for PO, receipt and invoice
    def __init__(self, folder):
        self.folder = folder   # folder that holds our input files, e.g. "input"

    def read_fixtures(self):
        # builds the full path, e.g. "input/fixtures_v1_0.json"
        path = os.path.join(self.folder, "fixtures_v1_0.json")
        with open(path, "r", encoding="utf-8") as f:   # open the file for reading; "with" closes it for us
            self.fixtures = json.load(f)               # json.load turns the file into a Python dictionary
        print(list(self.fixtures.keys()))              # check: print the table names found inside the file

    def inspect(self):
        # prints the first 5 lines of the PO, invoice and receipt tables, with every field
        tables = ["purchase_order_lines", "invoice_lines", "receipt_lines"]   # the three tables we want to look at
        for table in tables:                                  # one table at a time
            print("---", table)                               # title, so you know which table is being shown
            for line in self.fixtures[table][:5]:             # [:5] = only the first 5 lines of the table
                print(line)                                   # each line is one dictionary, printed with all its fields

    def normalize_node(self, node):
        # turns the raw text values of ONE node into clean values we can calculate with

        for field in ("quantity", "unit_price", "amount"):    # the three number fields
            if node[field] is not None:                       # receipts have no price, so skip empty ones
                node[field] = float(node[field])              # text "8" -> number 8.0
        node["date"] = datetime.strptime(node["date"], "%Y-%m-%d").date()   # text "2026-01-10" -> a real date
        # only PO nodes have this key, so invoice and receipt nodes skip this block
        if "expected_receipt_date" in node:
            # skip it if the field is empty, same idea as the price check at the top of this function
            if node["expected_receipt_date"] is not None:
                # text "2026-01-20" -> a real date, so two dates can be subtracted later
                node["expected_receipt_date"] = datetime.strptime(node["expected_receipt_date"], "%Y-%m-%d").date()
        node["description"] = node["description"].strip().lower()           # remove extra spaces and lowercase it
        node["id"] = node["id"].strip().lower()
        if node.get("po_ref"):
            node["po_ref"] = node["po_ref"].strip().lower()
        return node                                          # give the cleaned node back
    
    def build_po_nodes(self):
        # STEP 1: make a lookup, so that given a PO id we can find its header
        headers = {}                                      # empty dictionary, will be filled below
        for po in self.fixtures["purchase_orders"]:       # po = one header dictionary (like the po_001 one you pasted)
            po_id = po["purchase_order_id"]               # take its id, e.g. "po_001"
            headers[po_id] = po                           # save the whole header under that id
        # after the loop, headers["po_001"] gives you the full po_001 header dictionary

        # STEP 2: make one node for every PO line
        self.po_nodes = []                                # empty list, will hold all PO nodes
        for line in self.fixtures["purchase_order_lines"]:   # line = one line dictionary (product, quantity, price)
            header = headers[line["purchase_order_id"]]   # the line says which PO it belongs to, so fetch that header
            node = {
                "id": line["po_line_id"],                 # the line's own id, e.g. "po_line_001_001"
                "po_id": line["purchase_order_id"],       # which PO it belongs to, e.g. "po_001"
                "description": line["description"],       # product name
                "quantity": line["quantity_ordered"],     # how many units were ordered (still text for now)
                "unit_price": line["unit_price"],         # price per unit (still text for now)
                "amount": line["line_total"],             # quantity x price (still text for now)
                "date": header["issue_date"],             # the date comes from the HEADER, not the line
                "expected_receipt_date": header["expected_receipt_date"]  # the expected receipt date comes from the LINE
            }
            # {'id': 'po_line_001_001', 'po_id': 'po_001', 'description': 'Synthetic Item 001 Alpha', 
            # 'quantity': '8', 'unit_price': '15.00', 'amount': '120.00', 'date': '2026-01-10'}

            self.po_nodes.append(self.normalize_node(node))      # add this node to the list

        print(len(self.po_nodes))                         # check: how many nodes were built
        print(self.po_nodes[0])                           # check: show the first node

    def build_invoice_nodes(self):
        # one node = one invoice line, carrying its header info (invoice id and date)
        # STEP 1: make a lookup, so that given an invoice id we can find its header
        headers = {}                                          # empty dictionary, will be filled below
        for inv in self.fixtures["invoices"]:                 # inv = one invoice header dictionary
            headers[inv["invoice_id"]] = inv                  # save the whole header under its id, e.g. "inv_001_a"

        # STEP 2: make one node for every invoice line
        self.invoice_nodes = []                               # empty list, will hold all invoice nodes
        for line in self.fixtures["invoice_lines"]:           # line = one invoice line dictionary
            header = headers[line["invoice_id"]]              # the line says which invoice it belongs to, so fetch that header
            node = {
                "id": line["invoice_line_id"],                # the line's own id, e.g. "inv_line_001_main_001"
                "invoice_id": line["invoice_id"],             # which invoice it belongs to, e.g. "inv_001_a"
                "description": line["description"],           # item name as written on the invoice
                "quantity": line["quantity_billed"],          # how many units were billed (still text for now)
                "unit_price": line["unit_price"],             # price per unit (still text for now)
                "amount": line["line_total"],                 # quantity x price (still text for now)
                "date": header["invoice_date"],               # the date comes from the HEADER, not the line
            }
            self.invoice_nodes.append(self.normalize_node(node))   # clean the text into numbers/dates, then keep it

        print(len(self.invoice_nodes))                        # check: how many nodes were built
        print(self.invoice_nodes[0])                          # check: show the first (already cleaned) node

    def build_receipt_nodes(self):
        # one node = one receipt line, carrying header info (receipt id, date, and related PO id)
        # STEP 1: make a lookup, so that given a receipt id we can find its header
        headers = {}                                          # empty dictionary, will be filled below
        for rcpt in self.fixtures["receipts"]:                 # rcpt = one receipt header dictionary
            headers[rcpt["receipt_id"]] = rcpt                # save the whole header under its id, e.g. "rcpt_001"

        # STEP 2: make one node for every receipt line
        self.receipt_nodes = []                               # empty list, will hold all receipt nodes
        for line in self.fixtures["receipt_lines"]:           # line = one receipt line dictionary
            header = headers.get(line["receipt_id"], {})      # fetch the corresponding receipt header
            node = {
                "id": line["receipt_line_id"],                # the line's own id, e.g. "rcpt_line_001_001"
                "receipt_id": line["receipt_id"],             # which receipt it belongs to, e.g. "rcpt_001"
                "description": line["sku_raw"],               # item name as written on the receipt (receipts have no "description" field)
                "quantity": line["quantity_received"],        # how many units arrived (still text for now)
                "unit_price": None,                           # a receipt has no price, so we keep the field empty
                "amount": None,                               # same here, so the node has the same keys as PO and invoice nodes
                "date": line["received_date"],                # date goods arrived (still text for now)
                "po_ref": header.get("related_purchase_order_id"),  # related PO id from receipt header, e.g. "po_001"
            }
            self.receipt_nodes.append(self.normalize_node(node))   # clean the text, then keep the node

        print(len(self.receipt_nodes))                        # check: how many nodes were built
        print(self.receipt_nodes[0])                          # check: show the first (already cleaned) node

    def get_data(self):
        # runs the whole reading pipeline and hands back the three lists of nodes
        self.read_fixtures()          # load the json file into self.fixtures
        self.build_po_nodes()         # fill self.po_nodes (cleaned)
        self.build_invoice_nodes()    # fill self.invoice_nodes (cleaned)
        self.build_receipt_nodes()    # fill self.receipt_nodes (cleaned)
        return self.po_nodes, self.invoice_nodes, self.receipt_nodes   # always in this order: PO, invoice, receipt