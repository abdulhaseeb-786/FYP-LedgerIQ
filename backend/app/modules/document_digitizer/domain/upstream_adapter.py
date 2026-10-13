"""Upstream Payload Adapter for Seamless Inter-Module Compilation (Module 7).

Converts digitized ExtractedDocument records directly into UpstreamModulePayload
and StandardizedAccountRecords to feed Module 1 (COA Normalizer), Module 2 (AJEs),
Module 3 (Financial Statements), Module 5 (Tax Matrix), and Module 6 (3-Way Match).
"""

from typing import Dict, Any, List
from app.modules.document_digitizer.domain.models import ExtractedDocument, DocumentLineItem

try:
    from fyp_module3.core.models import StandardizedAccountRecord, UpstreamModulePayload
    HAS_FYP_CORE = True
except ImportError:
    HAS_FYP_CORE = False


class UpstreamDocumentAdapter:
    """Translates digitized documents into standardized enterprise data contracts."""

    def to_upstream_payload(self, doc: ExtractedDocument) -> Dict[str, Any]:
        """
        Produce normalized dictionary payload ready for downstream accounting pipeline.
        """
        if doc.document_type == "SCANNED_TRIAL_BALANCE":
            return self._build_trial_balance_payload(doc)
        elif doc.document_type == "TAX_CHALLAN":
            return self._build_tax_challan_payload(doc)
        else:
            return self._build_procurement_payload(doc)

    def _build_trial_balance_payload(self, doc: ExtractedDocument) -> Dict[str, Any]:
        records = []
        for item in doc.line_items:
            dr = item.debit if item.debit > 0 else (item.amount if item.amount > 0 and item.credit == 0 else 0.0)
            cr = item.credit if item.credit > 0 else 0.0

            rec = {
                "account_code": item.account_code,
                "account_name": item.description,
                "debit": dr,
                "credit": cr,
                "confidence": item.confidence,
                "source_bounding_box": item.bbox.model_dump() if item.bbox else None,
            }
            records.append(rec)

        return {
            "payload_type": "TRIAL_BALANCE",
            "entity_name": doc.vendor_or_entity or "Client Entity",
            "reporting_period": doc.date or "Current Period",
            "accounts_count": len(records),
            "accounts": records,
            "total_debits": sum(r["debit"] for r in records),
            "total_credits": sum(r["credit"] for r in records),
            "is_balanced": abs(sum(r["debit"] for r in records) - sum(r["credit"] for r in records)) < 0.02,
        }

    def _build_tax_challan_payload(self, doc: ExtractedDocument) -> Dict[str, Any]:
        return {
            "payload_type": "FBR_TAX_CHALLAN",
            "cpr_number": doc.document_no,
            "taxpayer_name": doc.vendor_or_entity,
            "tax_id": doc.tax_id,
            "payment_date": doc.date,
            "total_tax_paid": doc.total,
            "line_breakup": [
                {
                    "head": i.description,
                    "amount": i.amount,
                    "is_disambiguated": i.is_disambiguated,
                }
                for i in doc.line_items
            ],
            "ready_for_wht_module5": True,
        }

    def _build_procurement_payload(self, doc: ExtractedDocument) -> Dict[str, Any]:
        return {
            "payload_type": "INVOICE_OR_RECEIPT",
            "document_no": doc.document_no,
            "vendor_name": doc.vendor_or_entity,
            "date": doc.date,
            "subtotal": doc.subtotal,
            "tax_amount": doc.tax,
            "discount_amount": doc.discount,
            "grand_total": doc.total,
            "line_items": [
                {
                    "row_index": i.row_index,
                    "item_description": i.description,
                    "quantity": i.quantity,
                    "unit_price": i.unit_price,
                    "line_amount": i.amount,
                    "disambiguation_applied": i.is_disambiguated,
                }
                for i in doc.line_items
            ],
            "ready_for_3way_module6": True,
        }

