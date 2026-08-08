"""Flexible site identity inference — no industry hardcode."""
from __future__ import annotations

import pytest

from app.services.knowledge_profile_generation.models import (
    MetadataDataset,
    PageCategory,
    PageRecord,
    WebsiteHierarchy,
)
from app.services.knowledge_profile_generation.site_identity import (
    ground_topic_label,
    infer_site_identity,
)


def _page(
    *,
    url: str,
    title: str,
    path_segments: list[str],
    texts: list[str],
    is_homepage: bool = False,
    source_id: int = 1,
) -> PageRecord:
    return PageRecord(
        source_id=source_id,
        url=url,
        title=title,
        document_type="generic_page",
        path_segments=path_segments,
        headings=[title],
        texts=texts,
        content_hints=[],
        is_homepage=is_homepage,
    )


@pytest.mark.unit
def test_identity_from_about_definitional_sentence():
    pages = [
        _page(
            url="https://example.com/",
            title="Home",
            path_segments=[],
            texts=["Welcome | promo banner mash"],
            is_homepage=True,
            source_id=1,
        ),
        _page(
            url="https://example.com/about",
            title="About",
            path_segments=["about"],
            texts=["NordicBank is a regional financial institution serving families."],
            source_id=2,
        ),
    ]
    hierarchy = WebsiteHierarchy(
        categories=[
            PageCategory(
                category="about",
                url=pages[1].url,
                title="About",
                confidence=0.9,
                signals=[],
            )
        ],
        menu_links=["about"],
        preset_seed="generic_corporate",
    )
    identity = infer_site_identity(
        organization_name="NordicBank",
        pages=pages,
        metadata=MetadataDataset(),
        hierarchy=hierarchy,
        top_url_segments=["about", "products"],
    )
    assert "NordicBank" in identity.site_subject
    assert "|" not in identity.site_subject
    assert "financial" in identity.entity_type.lower() or "institution" in identity.entity_type.lower()
    assert identity.entity_type_source.startswith("https://") or identity.entity_type_source


@pytest.mark.unit
def test_identity_schema_type_preferred():
    pages = [
        _page(
            url="https://shop.example/",
            title="Shop",
            path_segments=[],
            texts=['{"@type": "Organization"}', "We sell things."],
            is_homepage=True,
        )
    ]
    identity = infer_site_identity(
        organization_name="Shop",
        pages=pages,
        metadata=None,
        hierarchy=None,
        top_url_segments=["catalog", "catalog", "catalog", "blog"],
    )
    assert identity.entity_type == "Organization"
    assert identity.entity_type_source.startswith("schema:")


@pytest.mark.unit
def test_identity_url_structure_fallback_for_diverse_sites():
    pages = [
        _page(
            url="https://docs.example/",
            title="Docs",
            path_segments=[],
            texts=["Welcome"],
            is_homepage=True,
        )
    ]
    identity = infer_site_identity(
        organization_name="DocsCo",
        pages=pages,
        metadata=None,
        hierarchy=None,
        top_url_segments=["guides", "guides", "guides", "api", "api", "changelog"],
    )
    assert identity.site_subject.startswith("DocsCo")
    assert "guides" in identity.site_subject.lower() or identity.site_subject == "DocsCo"
    assert identity.entity_type == "guides"


@pytest.mark.unit
def test_identity_rejects_pipe_banner_subject():
    pages = [
        _page(
            url="https://bank.example/",
            title="Home",
            path_segments=[],
            texts=[
                "BANK | Promo 5% COMFY details and more marketing copy without a period"
            ],
            is_homepage=True,
        )
    ]
    identity = infer_site_identity(
        organization_name="BANK",
        pages=pages,
        metadata=None,
        hierarchy=None,
        top_url_segments=[],
    )
    # No clean sentence → fall back to organization name, never pipe mashup
    assert "|" not in identity.site_subject
    assert identity.site_subject == "BANK"


@pytest.mark.unit
def test_ground_topic_label_rejects_ungrounded_english_placeholder():
    assert (
        ground_topic_label(
            "About the organization",
            evidence_text="Картки та депозити UKRSIBBANK",
            fallback="Картки",
        )
        == "Картки"
    )
    # Keep labels that literally appear on the site
    assert (
        ground_topic_label(
            "About the organization",
            evidence_text="About the organization and history",
            fallback="History",
        )
        == "About the organization"
    )


@pytest.mark.unit
def test_ecommerce_like_site_without_bank_vocab():
    """Same algorithm on a non-bank site — no vertical assumptions."""
    pages = [
        _page(
            url="https://craft.example/about",
            title="About",
            path_segments=["about"],
            texts=["CraftHouse is an online marketplace for handmade goods."],
            source_id=1,
        ),
        _page(
            url="https://craft.example/",
            title="Home",
            path_segments=[],
            texts=["Shop handmade"],
            is_homepage=True,
            source_id=2,
        ),
    ]
    hierarchy = WebsiteHierarchy(
        categories=[
            PageCategory(
                category="about",
                url=pages[0].url,
                title="About",
                confidence=0.9,
                signals=[],
            )
        ],
        menu_links=["shop", "about"],
        preset_seed="generic_corporate",
    )
    identity = infer_site_identity(
        organization_name="CraftHouse",
        pages=pages,
        metadata=None,
        hierarchy=hierarchy,
        top_url_segments=["shop", "shop", "makers", "about"],
    )
    assert "CraftHouse" in identity.site_subject
    assert "marketplace" in identity.entity_type.lower() or "online" in identity.entity_type.lower()
