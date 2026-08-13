"""Known PTAB trial search field paths and filter helpers."""

from __future__ import annotations

from uspto_client.models import SearchFilter

TRIAL_NUMBER_FIELD = "trialNumber"
TRIAL_TYPE_FIELD = "trialMetaData.trialTypeCode"
TRIAL_STATUS_FIELD = "trialMetaData.trialStatusCategory"
PATENT_NUMBER_FIELD = "patentOwnerData.patentNumber"
APPLICATION_NUMBER_FIELD = "patentOwnerData.applicationNumberText"
PETITION_FILING_DATE_FIELD = "trialMetaData.petitionFilingDate"
INSTITUTION_DECISION_DATE_FIELD = "trialMetaData.institutionDecisionDate"
DOCUMENT_CATEGORY_FIELD = "documentData.documentCategory"
FILING_PARTY_FIELD = "documentData.filingPartyCategory"
DECISION_TYPE_FIELD = "decisionData.decisionTypeCategory"
TRIAL_OUTCOME_FIELD = "decisionData.trialOutcomeCategory"
STATUTE_AND_RULE_FIELD = "decisionData.statuteAndRuleBag"


def trial_type_filter(*values: str) -> SearchFilter:
    """Build a filter for IPR, PGR, CBM, DER, or future trial types."""

    return SearchFilter(name=TRIAL_TYPE_FIELD, value=list(values))


def trial_status_filter(*values: str) -> SearchFilter:
    """Build a filter for one or more PTAB trial statuses."""

    return SearchFilter(name=TRIAL_STATUS_FIELD, value=list(values))


def document_category_filter(*values: str) -> SearchFilter:
    """Build a filter for one or more trial document categories."""

    return SearchFilter(name=DOCUMENT_CATEGORY_FIELD, value=list(values))


def decision_type_filter(*values: str) -> SearchFilter:
    """Build a filter for one or more PTAB decision types."""

    return SearchFilter(name=DECISION_TYPE_FIELD, value=list(values))
