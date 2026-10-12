"""Master Chart of Accounts & Fifth Schedule Taxonomy (Companies Act 2017 & IFRS)."""

from typing import List, Dict, Optional, Any

LINE_ITEMS: List[Dict[str, Any]] = [
    # -------------------------------------------------- SOFP: Non-Current Assets
    {
        "id": "sofp.nca.ppe",
        "stmt": "SOFP",
        "section": "Non-current assets",
        "label": "Property, plant and equipment",
        "order": 10,
        "natural": "DR",
        "note_number": 4,
        "cf": "investing",
        "aliases": [
            "property plant and equipment", "property plant equipment", "ppe",
            "fixed assets", "fixed asset", "fixed assets cost", "fixed assets at cost",
            "fixed assets net", "operating fixed assets", "tangible fixed assets",
            "plant and equipment", "plant and machinery", "machinery",
            "furniture and fixtures", "furniture fixtures", "furniture and fittings",
            "office equipment", "computer equipment", "computers", "vehicles",
            "motor vehicles", "vehicle", "building", "buildings", "land",
            "land and building", "land and buildings", "leasehold improvements",
            "capital work in progress", "cwip", "electrical installation",
            "generator", "air conditioners", "air conditioner", "electronic equipment",
            "solar equipment", "computer and it equipment", "plot", "plot of land",
            "motorcycle", "motor cycle", "bike", "honda", "suzuki", "toyota",
            "civic", "corolla", "alto", "cultus", "hilux"
        ]
    },
    {
        "id": "sofp.nca.accdep",
        "stmt": "SOFP",
        "section": "Non-current assets",
        "label": "Accumulated depreciation",
        "order": 11,
        "natural": "CR",
        "contra_of": "sofp.nca.ppe",
        "note_number": 4,
        "cf": "depn",
        "aliases": [
            "accumulated depreciation", "accum depreciation", "acc depreciation",
            "accumulated dep", "less accumulated depreciation", "provision for depreciation",
            "accumulated amortisation", "accumulated amortization",
            "accumulated depreciation on fixed assets"
        ]
    },
    {
        "id": "sofp.nca.intangible",
        "stmt": "SOFP",
        "section": "Non-current assets",
        "label": "Intangible assets",
        "order": 20,
        "natural": "DR",
        "cf": "investing",
        "aliases": [
            "intangible assets", "intangible asset", "intangibles", "goodwill",
            "software", "computer software", "licenses", "licences", "trademark",
            "trademarks", "patents", "website development"
        ]
    },
    {
        "id": "sofp.nca.ltinvest",
        "stmt": "SOFP",
        "section": "Non-current assets",
        "label": "Long-term investments",
        "order": 30,
        "natural": "DR",
        "cf": "investing",
        "aliases": [
            "long term investments", "long term investment", "investments non current",
            "investment in subsidiary", "investment in associate", "investment in shares",
            "investment property"
        ]
    },
    {
        "id": "sofp.nca.ltdeposits",
        "stmt": "SOFP",
        "section": "Non-current assets",
        "label": "Long-term deposits and prepayments",
        "order": 40,
        "natural": "DR",
        "note_number": 5,
        "cf": "investing",
        "aliases": [
            "long term deposits", "long term deposit", "long term deposits and prepayments",
            "security deposits", "security deposit", "utility deposits", "rent deposit",
            "deposit against lease", "long term advances", "long term loans to employees"
        ]
    },
    {
        "id": "sofp.nca.dta",
        "stmt": "SOFP",
        "section": "Non-current assets",
        "label": "Deferred taxation - net asset",
        "order": 50,
        "natural": "DR",
        "cf": "tax",
        "aliases": [
            "deferred tax asset", "deferred taxation asset", "deferred tax assets"
        ]
    },

    # -------------------------------------------------- SOFP: Current Assets
    {
        "id": "sofp.ca.stores",
        "stmt": "SOFP",
        "section": "Current assets",
        "label": "Stores, spares and loose tools",
        "order": 100,
        "natural": "DR",
        "cf": "wcAsset",
        "aliases": [
            "stores and spares", "stores spares and loose tools", "stores",
            "spares", "loose tools", "store and spares", "consumable stores",
            "packing material"
        ]
    },
    {
        "id": "sofp.ca.stock",
        "stmt": "SOFP",
        "section": "Current assets",
        "label": "Stock-in-trade",
        "order": 110,
        "natural": "DR",
        "note_number": 6,
        "cf": "wcAsset",
        "aliases": [
            "stock in trade", "stock", "stocks", "inventory", "inventories",
            "closing stock", "closing inventory", "merchandise", "finished goods",
            "raw material", "raw materials", "work in process", "work in progress",
            "goods in transit"
        ]
    },
    {
        "id": "sofp.ca.debtors",
        "stmt": "SOFP",
        "section": "Current assets",
        "label": "Trade debts",
        "order": 120,
        "natural": "DR",
        "note_number": 7,
        "cf": "wcAsset",
        "aliases": [
            "trade debts", "trade debt", "trade debtors", "trade debtor", "debtors",
            "sundry debtors", "trade receivables", "trade receivable", "receivables",
            "receivable", "accounts receivable", "account receivable", "ar",
            "receivable customers", "customer receivables", "trade and other receivables",
            "bills receivable", "receivables from customers", "due from customers",
            "trade debtors un-secured considered good", "trade debtors - unsecured",
            "trade debts - local", "trade debts - export", "trade debts local", "trade debts export"
        ]
    },
    {
        "id": "sofp.ca.allowance_ecl",
        "stmt": "SOFP",
        "section": "Current assets",
        "label": "Allowance for expected credit loss",
        "order": 121,
        "natural": "CR",
        "contra_of": "sofp.ca.debtors",
        "note_number": 7,
        "cf": "wcAsset",
        "aliases": [
            "allowance for expected credit loss", "allowance for doubtful debts",
            "allowance for bad debts", "provision for doubtful debts", "provision for bad debts",
            "expected credit loss", "ecl allowance", "allowance for ecl"
        ]
    },
    {
        "id": "sofp.ca.advances",
        "stmt": "SOFP",
        "section": "Current assets",
        "label": "Advances, deposits, prepayments and other receivables",
        "order": 130,
        "natural": "DR",
        "cf": "wcAsset",
        "aliases": [
            "advances", "advance", "advances and prepayments", "advances deposits and prepayments",
            "advances deposits prepayments and other receivables", "advances deposits and other receivables",
            "prepayments", "prepaid expenses", "prepaid", "prepaid rent", "prepaid insurance",
            "deposits and prepayments", "other receivables", "other receivable",
            "advance to suppliers", "advance to supplier", "advances to suppliers",
            "advances to employees", "advance salary", "advance rent",
            "staff advances", "due from related parties", "due from related party",
            "receivable from directors", "accrued income", "other current assets",
            "short term deposits", "loan to", "loan to employees", "loan to employee",
            "loan to staff", "loan to directors", "loan to director", "directors loan account",
            "amount receivable", "amounts receivable", "employee loan", "staff loan", "staff loans",
            "trade deposits and short-term prepayments", "trade deposits and short term prepayments"
        ]
    },
    {
        "id": "sofp.ca.stinvest",
        "stmt": "SOFP",
        "section": "Current assets",
        "label": "Short-term investments",
        "order": 140,
        "natural": "DR",
        "cf": "investing",
        "aliases": [
            "short term investments", "short term investment", "term deposit",
            "term deposits", "tdr", "treasury bills", "mutual funds"
        ]
    },
    {
        "id": "sofp.ca.taxrefund",
        "stmt": "SOFP",
        "section": "Current assets",
        "label": "Tax refunds due from Government",
        "order": 150,
        "natural": "DR",
        "cf": "wcAsset",
        "aliases": [
            "tax refunds due from government", "advance income tax", "advance tax",
            "income tax refundable", "tax refundable", "withholding income tax",
            "withholding tax", "wht receivable", "wht", "sales tax refundable",
            "input tax", "sales tax receivable", "tax deducted at source",
            "withholding tax receivable"
        ]
    },
    {
        "id": "sofp.ca.cash",
        "stmt": "SOFP",
        "section": "Current assets",
        "label": "Cash and bank balances",
        "order": 160,
        "natural": "DR",
        "note_number": 8,
        "cf": "cash",
        "aliases": [
            "cash and bank balances", "cash and bank", "cash bank", "cash at bank",
            "cash in hand", "cash on hand", "cash", "bank", "bank balance",
            "bank balances", "petty cash", "bank current account", "bank current accounts",
            "bank - current accounts", "bank savings accounts", "bank - savings accounts",
            "bank - foreign currency account", "bank foreign currency account",
            "saving account", "savings account", "cash and cash equivalents",
            "hbl", "mcb", "ubl", "abl", "meezan", "bank alfalah", "askari bank"
        ]
    },

    # -------------------------------------------------- SOFP: Share Capital & Reserves
    {
        "id": "sofp.eq.sharecapital",
        "stmt": "SOFP",
        "section": "Share capital and reserves",
        "label": "Issued, subscribed and paid-up share capital",
        "order": 200,
        "natural": "CR",
        "note_number": 9,
        "cf": "financing",
        "aliases": [
            "share capital", "issued subscribed and paid up share capital", "paid up capital",
            "paid up share capital", "ordinary share capital", "issued share capital",
            "authorized share capital", "authorised share capital"
        ]
    },
    {
        "id": "sofp.eq.reserves",
        "stmt": "SOFP",
        "section": "Share capital and reserves",
        "label": "Reserves",
        "order": 210,
        "natural": "CR",
        "cf": "financing",
        "aliases": [
            "reserves", "reserve", "general reserve", "capital reserve",
            "share premium", "revaluation surplus", "revaluation reserve",
            "surplus on revaluation"
        ]
    },
    {
        "id": "sofp.eq.capitalaccount",
        "stmt": "SOFP",
        "section": "Share capital and reserves",
        "label": "Capital account",
        "order": 215,
        "natural": "CR",
        "note_number": 9,
        "cf": "financing",
        "aliases": [
            "capital account", "capital", "proprietor capital", "proprietors capital",
            "owners capital", "owner capital", "partners capital", "partner capital",
            "aimal khan capital", "partner 1 capital", "partner 2 capital"
        ]
    },
    {
        "id": "sofp.eq.retained",
        "stmt": "SOFP",
        "section": "Share capital and reserves",
        "label": "Unappropriated profit / (accumulated loss)",
        "order": 220,
        "natural": "CR",
        "cf": "equityPL",
        "aliases": [
            "retained earnings", "retained earning", "unappropriated profit",
            "accumulated profit", "accumulated profit loss", "accumulated loss",
            "accumulated profits", "profit and loss account", "opening retained earnings",
            "retained earnings opening", "retained earnings true opening balance",
            "accumulated profit brought forward", "balance brought forward",
            "opening balance equity"
        ]
    },
    {
        "id": "sofp.eq.cy_profit_summary",
        "stmt": "SOFP",
        "section": "Share capital and reserves",
        "label": "Current year profit / (loss) summary",
        "order": 225,
        "natural": "CR",
        "cf": "equityPL",
        "aliases": [
            "current year profit", "current year loss", "profit for the year",
            "loss for the year", "net profit for the year", "net loss for the year",
            "current year profit loss"
        ]
    },
    {
        "id": "sofp.eq.drawings",
        "stmt": "SOFP",
        "section": "Share capital and reserves",
        "label": "Drawings",
        "order": 230,
        "natural": "DR",
        "contra_of": "sofp.eq.capitalaccount",
        "note_number": 9,
        "cf": "financing",
        "aliases": [
            "drawings", "drawing", "proprietor drawings", "owners drawings", "partner drawings"
        ]
    },
    {
        "id": "sofp.eq.dividend",
        "stmt": "SOFP",
        "section": "Share capital and reserves",
        "label": "Dividends",
        "order": 240,
        "natural": "DR",
        "contra_of": "sofp.eq.retained",
        "cf": "financing",
        "aliases": [
            "dividend", "dividends", "dividend paid", "dividends paid",
            "interim dividend", "final dividend"
        ]
    },

    # -------------------------------------------------- SOFP: Non-Current Liabilities
    {
        "id": "sofp.ncl.ltborrow",
        "stmt": "SOFP",
        "section": "Non-current liabilities",
        "label": "Long-term borrowings",
        "order": 300,
        "natural": "CR",
        "cf": "financing",
        "aliases": [
            "loan", "loan account", "borrowings", "bank loan",
            "long term borrowings", "long term borrowing", "long term loan",
            "long term loans", "long term financing", "long term financing loans",
            "term finance", "term loan", "bank loan long term", "loan from bank",
            "mortgage loan", "term finance facility", "diminishing musharakah facility",
            "diminishing musharakah"
        ]
    },
    {
        "id": "sofp.ncl.lease",
        "stmt": "SOFP",
        "section": "Non-current liabilities",
        "label": "Lease liabilities",
        "order": 310,
        "natural": "CR",
        "cf": "financing",
        "aliases": [
            "lease liabilities", "lease liability", "liabilities against assets subject to finance lease",
            "finance lease liability", "ijarah payable", "lease payable",
            "lease liabilities - non-current", "lease liabilities non current",
            "non-current lease liabilities", "non current lease liabilities"
        ]
    },
    {
        "id": "sofp.ncl.deftax",
        "stmt": "SOFP",
        "section": "Non-current liabilities",
        "label": "Deferred taxation",
        "order": 320,
        "natural": "CR",
        "cf": "tax",
        "aliases": [
            "deferred taxation", "deferred tax", "deferred tax liability",
            "deferred tax liabilities", "deferred taxation net"
        ]
    },
    {
        "id": "sofp.ncl.ltprov",
        "stmt": "SOFP",
        "section": "Non-current liabilities",
        "label": "Long-term provisions",
        "order": 330,
        "natural": "CR",
        "cf": "wcLiab",
        "aliases": [
            "long term provisions", "long term provision", "staff gratuity",
            "gratuity payable", "provision for gratuity", "employee benefits obligation",
            "employee benefit obligations", "defined benefit obligation", "staff gratuity payable"
        ]
    },
    {
        "id": "sofp.ncl.directorloan",
        "stmt": "SOFP",
        "section": "Non-current liabilities",
        "label": "Loan from directors / related parties",
        "order": 340,
        "natural": "CR",
        "cf": "financing",
        "aliases": [
            "loan from director", "loan from directors", "directors loan",
            "director loan", "due to related party", "due to related parties",
            "payable to directors", "sponsor loan",
            "loan from sponsors", "loan from shareholders", "due to directors",
            "loan from ip commodities", "loan by zafran sb"
        ]
    },

    # -------------------------------------------------- SOFP: Current Liabilities
    {
        "id": "sofp.cl.payables",
        "stmt": "SOFP",
        "section": "Current liabilities",
        "label": "Trade and other payables",
        "order": 400,
        "natural": "CR",
        "note_number": 10,
        "cf": "wcLiab",
        "aliases": [
            "trade and other payables", "trade payables", "trade payable", "creditors",
            "sundry creditors", "accounts payable", "account payable", "payables",
            "payable", "trade creditors", "creditors accrued expenses and other liabilities",
            "creditors accrued exp and other liab", "creditors accrued and other liabilities",
            "accrued and other liabilities", "other payables", "advance from customers",
            "advances from customers", "security deposits payable", "bills payable",
            "trade creditors - local", "trade creditors - foreign",
            "trade creditors local", "trade creditors foreign",
            "directors current account", "directors' current account", "director current account"
        ]
    },
    {
        "id": "sofp.cl.accrued",
        "stmt": "SOFP",
        "section": "Current liabilities",
        "label": "Accrued liabilities",
        "order": 410,
        "natural": "CR",
        "note_number": 10,
        "cf": "wcLiab",
        "aliases": [
            "accrued liabilities", "accrued liability", "accrued expenses",
            "accrued expense", "accruals", "audit fee payable", "audit fees payable",
            "salaries payable", "salary payable", "wages payable", "rent payable",
            "utilities payable", "expenses payable", "accrued markup", "accrued interest",
            "accrued mark-up / interest", "accrued mark-up", "markup payable",
            "withholding tax payable", "sales tax payable", "eobi payable",
            "provident fund payable", "gst payable", "wht payable",
            "accrued salaries", "accrued utilities", "accrued rent"
        ]
    },
    {
        "id": "sofp.cl.stborrow",
        "stmt": "SOFP",
        "section": "Current liabilities",
        "label": "Short-term borrowings",
        "order": 420,
        "natural": "CR",
        "cf": "financing",
        "aliases": [
            "short term borrowings", "short term borrowing", "short term loan",
            "short term loans", "running finance", "running finance facility",
            "cash finance", "bank overdraft", "overdraft", "short term finance"
        ]
    },
    {
        "id": "sofp.cl.lease",
        "stmt": "SOFP",
        "section": "Current liabilities",
        "label": "Lease liabilities - current portion",
        "order": 425,
        "natural": "CR",
        "cf": "financing",
        "aliases": [
            "lease liabilities - current", "lease liabilities current",
            "current portion of lease liability", "current portion of lease liabilities",
            "current lease liabilities", "lease liability current", "current lease liability"
        ]
    },
    {
        "id": "sofp.cl.currentportion",
        "stmt": "SOFP",
        "section": "Current liabilities",
        "label": "Current portion of long-term liabilities",
        "order": 430,
        "natural": "CR",
        "cf": "financing",
        "aliases": [
            "current portion of long term liabilities", "current portion of long term loan",
            "current portion long term loan", "current maturity of long term debt",
            "current liability long term loan", "current portion of lease liability"
        ]
    },
    {
        "id": "sofp.cl.provtax",
        "stmt": "SOFP",
        "section": "Current liabilities",
        "label": "Provision for taxation",
        "order": 440,
        "natural": "CR",
        "cf": "tax",
        "aliases": [
            "provision for taxation", "provision for tax", "provision of taxation",
            "income tax payable", "tax payable", "current tax liability", "taxation payable"
        ]
    },
    {
        "id": "sofp.cl.unclaimeddiv",
        "stmt": "SOFP",
        "section": "Current liabilities",
        "label": "Unclaimed dividend",
        "order": 450,
        "natural": "CR",
        "cf": "financing",
        "aliases": [
            "unclaimed dividend", "unpaid dividend", "dividend payable"
        ]
    },

    # -------------------------------------------------- Statement of Profit or Loss
    {
        "id": "pl.revenue",
        "stmt": "PL",
        "section": "Revenue",
        "label": "Revenue - net",
        "order": 500,
        "natural": "CR",
        "aliases": [
            "revenue", "revenue net", "net revenue", "sales", "net sales",
            "sales revenue", "turnover", "gross sales", "service revenue",
            "services revenue", "income", "income from services", "fee income",
            "consultancy income", "contract revenue", "project revenue",
            "grant income", "revenue inl", "revenue ned", "operating revenue",
            "sales - local", "sales - export", "sales local", "sales export",
            "gross turnover"
        ]
    },
    {
        "id": "pl.salesreturns",
        "stmt": "PL",
        "section": "Revenue",
        "label": "Less: sales returns and discounts",
        "order": 505,
        "natural": "DR",
        "contra_of": "pl.revenue",
        "aliases": [
            "sales returns", "sales return", "returns inward", "sales discount",
            "discount allowed", "trade discount", "sales returns and discounts",
            "sales return and discount", "sales returns and discount",
            "sales returns & discounts"
        ]
    },
    {
        "id": "pl.cos",
        "stmt": "PL",
        "section": "Cost of sales",
        "label": "Cost of sales",
        "order": 510,
        "natural": "DR",
        "note_number": 11,
        "aliases": [
            "cost of sales", "cost of sale", "cos", "cogs", "cost of goods sold",
            "cost of revenue", "cost of services", "cost of service", "direct cost",
            "direct costs", "purchases", "purchase", "opening stock", "direct wages",
            "direct labour", "direct labor", "factory overheads", "manufacturing cost",
            "freight inward", "carriage inward", "subcontractor cost", "raw material consumed"
        ]
    },
    {
        "id": "pl.distribution",
        "stmt": "PL",
        "section": "Operating expenses",
        "label": "Distribution and selling expenses",
        "order": 520,
        "natural": "DR",
        "aliases": [
            "distribution expenses", "distribution cost", "distribution costs",
            "selling expenses", "selling and distribution expenses", "selling cost",
            "marketing expenses", "marketing", "advertisement", "advertising",
            "advertisement and publicity", "freight outward", "carriage outward",
            "delivery expenses", "commission expense", "sales commission"
        ]
    },
    {
        "id": "pl.admin",
        "stmt": "PL",
        "section": "Operating expenses",
        "label": "Administrative expenses",
        "order": 530,
        "natural": "DR",
        "note_number": 12,
        "aliases": [
            "administrative expenses", "administration expenses", "admin expenses",
            "general and administrative expenses", "operating expenses", "salaries",
            "salary", "salaries and wages", "salaries and benefits", "staff salaries",
            "wages", "staff cost", "staff costs", "employee benefits", "directors remuneration",
            "rent", "rent rates and taxes", "rent and rates", "utilities", "electricity",
            "gas", "water charges", "telephone", "communication", "internet",
            "printing and stationery", "stationery", "stationary", "office supplies",
            "office expenses", "office expenses food and refreshment", "entertainment",
            "food and refreshment", "refreshment", "travelling", "traveling", "travel",
            "travelling and conveyance", "conveyance", "vehicle running expenses",
            "vehicle charges", "fuel", "petrol", "pol", "repair and maintenance",
            "repairs and maintenance", "repair maintenance", "insurance",
            "legal and professional charges", "legal and professional", "professional charges",
            "consultancy charges", "audit fee", "audit fees", "audit fee expense",
            "auditors remuneration", "fees and subscription", "subscription", "training",
            "training expenses", "meeting", "meeting expenses", "conference", "seminar",
            "honorarium", "honorarium and transportation", "transcription", "translation",
            "security charges", "cleaning", "janitorial", "postage and courier",
            "courier", "newspaper and periodicals", "donation", "charity", "eobi",
            "social security", "miscellaneous expenses", "sundry expenses", "general expenses",
            "online content production", "project coordinator", "project team",
            "salaries-project coordinator", "salaries-finance asstt", "coorinator peshawar",
            "coordinator islamabad", "estimated pol per point", "vehicle charges per day",
            "stationery- one time cost", "bank charges"
        ]
    },
    {
        "id": "pl.depreciation",
        "stmt": "PL",
        "section": "Operating expenses",
        "label": "Depreciation and amortisation",
        "order": 540,
        "natural": "DR",
        "note_number": 12,
        "aliases": [
            "depreciation", "depreciation expense", "depn exp", "depn",
            "depreciation for the year", "amortisation", "amortization",
            "amortisation expense", "depreciation and amortisation",
            "depreciation and amortization"
        ]
    },
    {
        "id": "pl.otherexp",
        "stmt": "PL",
        "section": "Other",
        "label": "Other operating expenses",
        "order": 550,
        "natural": "DR",
        "aliases": [
            "other operating expenses", "other expenses", "other expense",
            "bad debts", "bad debts written off", "provision for doubtful debts",
            "impairment loss", "loss on disposal", "loss on disposal of fixed assets",
            "exchange loss", "penalty", "fine", "workers welfare fund", "wwf", "wppf"
        ]
    },
    {
        "id": "pl.otherincome",
        "stmt": "PL",
        "section": "Other",
        "label": "Other income",
        "order": 560,
        "natural": "CR",
        "aliases": [
            "other income", "other operating income", "miscellaneous income",
            "misc income", "sundry income", "profit on bank deposits", "bank profit",
            "interest income", "markup income", "rental income", "gain on disposal",
            "gain on disposal of fixed assets", "gain on disposal of assets",
            "gain on sale of assets", "dividend income", "profit on disposal", "exchange gain",
            "discount received", "scrap sales"
        ]
    },
    {
        "id": "pl.finance",
        "stmt": "PL",
        "section": "Finance cost",
        "label": "Finance cost",
        "order": 570,
        "natural": "DR",
        "aliases": [
            "finance cost", "finance costs", "financial charges", "financial charge",
            "finance charges", "bank charges", "bank charge", "bank commission",
            "markup expense", "mark up expense", "interest expense", "interest on loan",
            "lease finance charges", "lc charges"
        ]
    },
    {
        "id": "pl.tax",
        "stmt": "PL",
        "section": "Taxation",
        "label": "Taxation",
        "order": 580,
        "natural": "DR",
        "aliases": [
            "taxation", "tax expense", "income tax expense", "income tax",
            "current taxation", "current tax", "taxation for the year",
            "tax charge", "deferred tax expense", "current tax expense",
            "minimum tax", "turnover tax"
        ]
    },

    # -------------------------------------------------- Suspense
    # Unrecognised accounts land here rather than being silently absorbed into
    # administrative expenses or trade payables, where they would quietly move
    # reported profit. They carry no aliases: nothing matches them by name,
    # they are only ever assigned by the classifier's explicit fallback.
    {
        "id": "sofp.ca.suspense",
        "stmt": "SOFP",
        "section": "Current assets",
        "label": "Suspense account - unclassified debit balances",
        "order": 195,
        "natural": "DR",
        "cf": "wcAsset",
        "aliases": []
    },
    {
        "id": "sofp.cl.suspense",
        "stmt": "SOFP",
        "section": "Current liabilities",
        "label": "Suspense account - unclassified credit balances",
        "order": 495,
        "natural": "CR",
        "cf": "wcLiab",
        "aliases": []
    }
]

_LINE_ITEMS_BY_ID: Dict[str, Dict[str, Any]] = {li["id"]: li for li in LINE_ITEMS}


def get_line_items() -> List[Dict[str, Any]]:
    """Return the entire master list of Fifth Schedule line items."""
    return LINE_ITEMS


def get_line_item(item_id: str) -> Optional[Dict[str, Any]]:
    """Lookup a single line item by its identifier."""
    return _LINE_ITEMS_BY_ID.get(item_id)


# Marker for an account deliberately eliminated during verification (for
# example a pre-closing profit summary that duplicates the detailed P&L).
# It renders on no statement, and the leakage check knows to expect that.
ELIMINATED_ID = "elim.duplicate"

SUSPENSE_DR_ID = "sofp.ca.suspense"
SUSPENSE_CR_ID = "sofp.cl.suspense"
SUSPENSE_IDS = frozenset({SUSPENSE_DR_ID, SUSPENSE_CR_ID})


# -------------------------------------------------------------------------
# Presentation polarity — the single source of truth shared by the notes
# compiler, the balance sheet and the profit or loss statement.
#
# A line item is "presented positively" on one side only. Getting this wrong
# in one place and right in another is what lets a note subtotal disagree with
# the face line it is supposed to support, so every consumer must call these
# helpers rather than re-deriving the rule locally.
# -------------------------------------------------------------------------

_FACE_CR_PREFIXES = ("sofp.eq.", "sofp.ncl.", "sofp.cl.")
_FACE_DR_PREFIXES = ("sofp.nca.", "sofp.ca.")
# Sales returns are a contra-revenue: presenting them on the credit side makes
# them a negative inside the revenue group, so a plain sum nets them off.
_PL_CR_IDS = frozenset({"pl.revenue", "pl.otherincome", "pl.salesreturns"})


def face_polarity(line_id: str) -> str:
    """Return the side ('DR' or 'CR') on which `line_id` is presented positively.

    Contra items intentionally inherit the polarity of the section they sit in,
    so accumulated depreciation inside non-current assets returns 'DR' and
    therefore lands as a negative amount.
    """
    lid = line_id or ""
    if lid.startswith(_FACE_DR_PREFIXES):
        return "DR"
    if lid.startswith(_FACE_CR_PREFIXES):
        return "CR"
    if lid in _PL_CR_IDS:
        return "CR"
    return "DR"


def face_amount(line_id: str, debit: float, credit: float) -> float:
    """Signed amount for `line_id` in its presentation direction."""
    if face_polarity(line_id) == "DR":
        return debit - credit
    return credit - debit
