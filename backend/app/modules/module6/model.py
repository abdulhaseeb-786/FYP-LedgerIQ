"""
HOW TO BUILD AND USE THE PuLP MODEL (read top to bottom, this is the order of the code)

PuLP is a library where you first DESCRIBE a problem and then call solve() once.
Nothing has a value until solve() runs.

STEP 1: Initialize the model
    model = pulp.LpProblem("three_way_match", pulp.LpMaximize)
    -> creates an empty model. LpMaximize means the objective is made as large as possible.

STEP 2: Create the variables (one per triple)
    x[t] = pulp.LpVariable("x_inv1_po1_r1", lowBound=0, cat="Integer")
    newer version: x[t] = self.model.add_variable(name, lowBound=0, cat=pulp.LpInteger
    -> x[t] is a placeholder for "units matched through triple t".
    -> lowBound=0: cannot be negative. cat="Integer": whole units only.
    -> the name string must be unique per variable.

STEP 3: Set the objective (what to maximize)
    model += pulp.lpSum(score[t] * x[t] for t in triples)
    -> `model += <expression>` with NO comparison operator sets the objective.
    -> lpSum is a sum over a list. It builds the formula, it does not calculate it.

STEP 4: Add the constraints (what must never be broken)
    model += pulp.lpSum(x[t] for t in triples if t[0] == i) <= inv_qty[i]
    -> `model += <expression> <= number` WITH a comparison operator adds a constraint.
    -> this line reads: "total units over all triples that contain invoice line i
       must not exceed the quantity of invoice line i".
    -> repeat the same line for every invoice line (t[0]), every PO line (t[1])
       and every receipt line (t[2]). One line per node = one constraint per node.

STEP 5: Solve once
    model.solve(pulp.PULP_CBC_CMD(msg=0))
    newer version: self.model.solve(pulp.COIN_CMD(msg=0))
    -> runs the solver. msg=0 suppresses the solver log.

STEP 6: Read the result
    x[t].value()
    -> the units the solver chose for triple t. Keep triples where value > 0.

INPUTS
    inv_qty, po_qty, rec_qty : {line_id: quantity}
    triples                  : {(invoice_id, po_id, receipt_id): combined_score}

OUTPUT
    {(invoice_id, po_id, receipt_id): matched_units}, nonzero entries only.
    Leftover units of a line = its quantity - sum of matched units on its triples.

Call solve() once for ALL invoices, not once per invoice, so that invoices sharing
a PO or receipt are resolved together and no line is over-used.
"""
import pulp

class Model:
    def __init__(self, triples, inv_nodes, po_nodes, rec_nodes):
        self.model = pulp.LpProblem("three_way_match", pulp.LpMaximize)

        self.triples = triples
        self.inv_qty = {n["id"]: n["quantity"] for n in inv_nodes}
        self.po_qty = {n["id"]: n["quantity"] for n in po_nodes}
        self.rec_qty = {n["id"]: n["quantity"] for n in rec_nodes}

        self.units = {}      # units matched through each triple (as in your original model)
        self.selected = {}   # 1 = triple is kept (units >= 1)
        for n, t in enumerate(self.triples):
            self.units[t] = self.model.add_variable(f"u_{n}", lowBound=0, cat=pulp.LpInteger)
            self.selected[t] = self.model.add_variable(f"sel_{n}", cat=pulp.LpBinary)

        self.inv_po = {}     # 1 = this PO is linked to this invoice
        for n, (i, j) in enumerate({(t[0], t[1]) for t in self.triples}):
            self.inv_po[(i, j)] = self.model.add_variable(f"ip_{n}", cat=pulp.LpBinary)

        self.po_rec = {}     # 1 = this receipt is linked to this PO
        for n, (j, k) in enumerate({(t[1], t[2]) for t in self.triples}):
            self.po_rec[(j, k)] = self.model.add_variable(f"pr_{n}", cat=pulp.LpBinary)

        # group once, so rules don't rescan all triples for every line
        self.by_inv, self.by_po, self.by_rec, self.by_ip = {}, {}, {}, {}
        for t in self.triples:
            self.by_inv.setdefault(t[0], []).append(t)
            self.by_po.setdefault(t[1], []).append(t)
            self.by_rec.setdefault(t[2], []).append(t)
            self.by_ip.setdefault((t[0], t[1]), []).append(t)

    def objective(self):
        self.model += pulp.lpSum(self.triples[t] * self.units[t] for t in self.triples)

    def rules(self):
        # ---------- ORIGINAL CAPS ----------
        for i, q in self.inv_qty.items():
            self.model += pulp.lpSum(self.units[t] for t in self.by_inv.get(i, [])) <= q
        for j, q in self.po_qty.items():
            self.model += pulp.lpSum(self.units[t] for t in self.by_po.get(j, [])) <= q
        for k, q in self.rec_qty.items():
            self.model += pulp.lpSum(self.units[t] for t in self.by_rec.get(k, [])) <= q

        # ---------- selected[t] = 1 exactly when units[t] >= 1 ----------
        for t in self.triples:
            big = min(self.inv_qty[t[0]], self.po_qty[t[1]], self.rec_qty[t[2]])
            self.model += self.units[t] <= big * self.selected[t]
            self.model += self.selected[t] <= self.units[t]

        # ---------- LINK VARIABLES ----------
        for (i, j), v in self.inv_po.items():
            self.model += v <= pulp.lpSum(self.selected[t] for t in self.by_ip[(i, j)])
        for t in self.triples:
            self.model += self.po_rec[(t[1], t[2])] >= self.selected[t]

        # ---------- RULE 1: INVOICE <= SUM OF LINKED POs ----------
        linked_po_total = {
            i: pulp.lpSum(self.po_qty[j] * v for (ii, j), v in self.inv_po.items() if ii == i)
            for i in self.inv_qty
        }
        for t in self.triples:
            self.model += self.inv_qty[t[0]] * self.selected[t] <= linked_po_total[t[0]]

        # ---------- RULE 2: SUM OF LINKED RECEIPTS <= PO ----------
        linked_rec_total = {
            j: pulp.lpSum(self.rec_qty[k] * v for (jj, k), v in self.po_rec.items() if jj == j)
            for j in self.po_qty
        }
        for j, q in self.po_qty.items():
            self.model += linked_rec_total[j] <= q

    def solve(self):
        self.objective()
        self.rules()
        self.model.solve(pulp.COIN_CMD(msg=0))

        matches = {}
        for t in self.triples:
            value = self.units[t].value()
            if value is None:
                print("no solution found")
                return {}
            qty = round(value)
            if qty > 0:
                matches[t] = qty
                print(t, qty)

        return matches