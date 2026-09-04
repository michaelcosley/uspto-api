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
PATENT_OWNER_COUNSEL_NAME_FIELD = "patentOwnerData.counselName"
PETITIONER_COUNSEL_NAME_FIELD = "regularPetitionerData.counselName"
RESPONDENT_COUNSEL_NAME_FIELD = "respondentData.counselName"
DERIVATION_PETITIONER_COUNSEL_NAME_FIELD = "derivationPetitionerData.counselName"
PATENT_OWNER_NAME_FIELD = "patentOwnerData.patentOwnerName"
PETITIONER_RPI_NAME_FIELD = "regularPetitionerData.realPartyInInterestName"


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


def patent_owner_counsel_query(name: str) -> str:
    """Build a proceeding query for patent-owner counsel."""

    return _phrase_query(PATENT_OWNER_COUNSEL_NAME_FIELD, name)


def petitioner_counsel_query(name: str) -> str:
    """Build a proceeding query for regular-petitioner counsel."""

    return _phrase_query(PETITIONER_COUNSEL_NAME_FIELD, name)


def respondent_counsel_query(name: str) -> str:
    """Build a proceeding query for respondent counsel."""

    return _phrase_query(RESPONDENT_COUNSEL_NAME_FIELD, name)


def derivation_petitioner_counsel_query(name: str) -> str:
    """Build a proceeding query for derivation-petitioner counsel."""

    return _phrase_query(DERIVATION_PETITIONER_COUNSEL_NAME_FIELD, name)


def patent_owner_name_query(name: str) -> str:
    """Build a proceeding query for the patent-owner party name."""

    return _phrase_query(PATENT_OWNER_NAME_FIELD, name)


def petitioner_rpi_name_query(name: str) -> str:
    """Build a proceeding query for petitioner real-party-in-interest name."""

    return _phrase_query(PETITIONER_RPI_NAME_FIELD, name)


def _phrase_query(field: str, value: str) -> str:
    if not value:
        raise ValueError("query value is required")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'{field}:"{escaped}"'
