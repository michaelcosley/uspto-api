"""Pydantic models for PTAB AIA trial proceedings and documents."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, Field

from uspto_client.models import UsptoModel, UsptoResponse


class TrialMetadata(UsptoModel):
    """Metadata shared by PTAB trial proceedings, documents, and decisions."""

    trial_type_code: str | None = Field(default=None, alias="trialTypeCode")
    trial_status_category: str | None = Field(
        default=None,
        alias="trialStatusCategory",
    )
    trial_last_modified_date: str | None = Field(
        default=None,
        alias="trialLastModifiedDate",
    )
    petition_filing_date: str | None = Field(
        default=None,
        alias="petitionFilingDate",
    )
    trial_last_modified_datetime: str | None = Field(
        default=None,
        alias="trialLastModifiedDateTime",
    )
    accorded_filing_date: str | None = Field(
        default=None,
        alias="accordedFilingDate",
    )
    institution_decision_date: str | None = Field(
        default=None,
        alias="institutionDecisionDate",
    )
    latest_decision_date: str | None = Field(
        default=None,
        alias="latestDecisionDate",
    )
    termination_date: str | None = Field(default=None, alias="terminationDate")
    file_download_uri: str | None = Field(default=None, alias="fileDownloadURI")


class TrialPartyData(UsptoModel):
    """Party data whose available fields vary by PTAB trial type."""

    application_number_text: str | None = Field(
        default=None,
        alias="applicationNumberText",
    )
    patent_number: str | None = Field(default=None, alias="patentNumber")
    real_party_in_interest_name: str | None = Field(
        default=None,
        alias="realPartyInInterestName",
    )
    grant_date: str | None = Field(default=None, alias="grantDate")
    patent_owner_name: str | None = Field(default=None, alias="patentOwnerName")
    inventor_name: str | None = Field(default=None, alias="inventorName")
    counsel_name: str | None = Field(default=None, alias="counselName")
    technology_center_number: str | None = Field(
        default=None,
        alias="technologyCenterNumber",
    )
    group_art_unit_number: str | None = Field(
        default=None,
        alias="groupArtUnitNumber",
    )


class TrialProceeding(UsptoModel):
    """One PTAB AIA trial proceeding."""

    trial_number: str = Field(alias="trialNumber")
    trial_record_identifier: str | None = Field(
        default=None,
        alias="trialRecordIdentifier",
    )
    last_modified_datetime: str | None = Field(
        default=None,
        alias="lastModifiedDateTime",
    )
    trial_metadata: TrialMetadata | None = Field(
        default=None,
        alias="trialMetaData",
    )
    patent_owner_data: TrialPartyData | None = Field(
        default=None,
        alias="patentOwnerData",
    )
    regular_petitioner_data: TrialPartyData | None = Field(
        default=None,
        alias="regularPetitionerData",
    )
    respondent_data: TrialPartyData | None = Field(
        default=None,
        alias="respondentData",
    )
    derivation_petitioner_data: TrialPartyData | None = Field(
        default=None,
        alias="derivationPetitionerData",
    )


class TrialDocumentData(UsptoModel):
    """Metadata and download location for one PTAB trial document."""

    document_identifier: str | None = Field(
        default=None,
        alias="documentIdentifier",
    )
    document_name: str | None = Field(default=None, alias="documentName")
    document_ocr_text: str | None = Field(default=None, alias="documentOCRText")
    document_category: str | None = Field(default=None, alias="documentCategory")
    mime_type_identifier: str | None = Field(
        default=None,
        alias="mimeTypeIdentifier",
    )
    document_size_quantity: int | str | None = Field(
        default=None,
        alias="documentSizeQuantity",
    )
    document_type_description_text: str | None = Field(
        default=None,
        alias="documentTypeDescriptionText",
    )
    document_filing_date: str | None = Field(
        default=None,
        alias="documentFilingDate",
    )
    document_number: int | str | None = Field(default=None, alias="documentNumber")
    filing_party_category: str | None = Field(
        default=None,
        alias="filingPartyCategory",
    )
    document_title_text: str | None = Field(
        default=None,
        alias="documentTitleText",
    )
    file_download_uri: str | None = Field(default=None, alias="fileDownloadURI")


class TrialDecisionData(UsptoModel):
    """Decision-specific metadata included with a PTAB trial document."""

    trial_outcome_category: str | None = Field(
        default=None,
        alias="trialOutcomeCategory",
    )
    decision_type_category: str | None = Field(
        default=None,
        alias="decisionTypeCategory",
    )
    decision_issue_date: str | None = Field(
        default=None,
        alias="decisionIssueDate",
    )
    issue_type_bag: list[Any] = Field(default_factory=list, alias="issueTypeBag")
    statute_and_rule_bag: list[Any] = Field(
        default_factory=list,
        alias="statuteAndRuleBag",
    )
    appeal_outcome_category: str | None = Field(
        default=None,
        alias="appealOutcomeCategory",
    )


class TrialDocument(UsptoModel):
    """One PTAB trial document, optionally enriched with decision metadata."""

    trial_number: str = Field(alias="trialNumber")
    last_modified_datetime: str | None = Field(
        default=None,
        alias="lastModifiedDateTime",
    )
    trial_document_category: str | None = Field(
        default=None,
        alias="trialDocumentCategory",
    )
    trial_type_code: str | None = Field(default=None, alias="trialTypeCode")
    trial_metadata: TrialMetadata | None = Field(
        default=None,
        alias="trialMetaData",
    )
    patent_owner_data: TrialPartyData | None = Field(
        default=None,
        alias="patentOwnerData",
    )
    regular_petitioner_data: TrialPartyData | None = Field(
        default=None,
        alias="regularPetitionerData",
    )
    respondent_data: TrialPartyData | None = Field(
        default=None,
        alias="respondentData",
    )
    derivation_petitioner_data: TrialPartyData | None = Field(
        default=None,
        alias="derivationPetitionerData",
    )
    document_data: TrialDocumentData | None = Field(
        default=None,
        alias="documentData",
    )
    decision_data: TrialDecisionData | None = Field(
        default=None,
        alias="decisionData",
    )


class TrialProceedingResponse(UsptoResponse):
    """USPTO response containing PTAB trial proceedings."""

    proceedings: list[TrialProceeding] = Field(
        default_factory=list,
        alias="patentTrialProceedingDataBag",
    )
    facets: list[dict[str, Any]] = Field(default_factory=list)


class TrialDocumentResponse(UsptoResponse):
    """USPTO response containing PTAB trial documents."""

    documents: list[TrialDocument] = Field(
        default_factory=list,
        alias="patentTrialDocumentDataBag",
    )
    facets: list[dict[str, Any]] = Field(default_factory=list)


class TrialDecisionResponse(UsptoResponse):
    """USPTO response containing trial decisions under either known bag name."""

    decisions: list[TrialDocument] = Field(
        default_factory=list,
        validation_alias=AliasChoices(
            "patentTrialDocumentDataBag",
            "patentTrialDecisionDataBag",
        ),
        serialization_alias="patentTrialDocumentDataBag",
    )
    facets: list[dict[str, Any]] = Field(default_factory=list)
