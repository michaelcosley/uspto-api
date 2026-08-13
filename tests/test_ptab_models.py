from __future__ import annotations

import json
from pathlib import Path

from uspto_client.ptab_models import (
    TrialDecisionResponse,
    TrialDocumentResponse,
    TrialProceedingResponse,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ptab_ipr2024_00001"


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_proceeding_fixture_exposes_typed_records() -> None:
    response = TrialProceedingResponse.model_validate(_fixture("proceeding.json"))

    assert response.proceedings[0].trial_number == "IPR2024-00001"
    assert response.proceedings[0].trial_metadata is not None
    assert response.proceedings[0].trial_metadata.trial_type_code == "IPR"
    assert response.proceedings[0].respondent_data is None


def test_document_fixture_exposes_download_metadata() -> None:
    response = TrialDocumentResponse.model_validate(_fixture("documents.json"))

    assert response.documents[0].document_data is not None
    assert response.documents[0].document_data.document_identifier == "171359735"
    assert response.documents[0].document_data.document_number == 1


def test_decision_response_accepts_live_document_bag_name() -> None:
    response = TrialDecisionResponse.model_validate(_fixture("decisions.json"))

    assert response.decisions[0].decision_data is not None
    assert response.decisions[0].decision_data.decision_type_category == (
        "Institution Decision"
    )


def test_decision_response_also_accepts_documented_decision_bag_name() -> None:
    payload = _fixture("decisions.json")
    payload["patentTrialDecisionDataBag"] = payload.pop("patentTrialDocumentDataBag")

    response = TrialDecisionResponse.model_validate(payload)

    assert response.decisions[0].trial_number == "IPR2024-00001"
    assert "patentTrialDocumentDataBag" in response.raw_data


def test_trial_models_preserve_additive_fields() -> None:
    payload = _fixture("proceeding.json")
    payload["futureTopLevelField"] = "preserved"
    payload["patentTrialProceedingDataBag"][0]["futureRecordField"] = 42  # type: ignore[index]

    response = TrialProceedingResponse.model_validate(payload)

    assert response.raw_data["futureTopLevelField"] == "preserved"
    assert response.proceedings[0].model_dump()["futureRecordField"] == 42
