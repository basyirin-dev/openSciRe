# SPDX-License-Identifier: Apache-2.0

"""MeSH term extraction from MEDLINE text and PubMed XML, plus in-memory indexing."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from openscire.references.models import MeshTerm


def extract_mesh_from_medline(medline_text: str) -> list[MeshTerm]:
    """Extract MeSH terms from MEDLINE format text (MH- lines).

    Lines look like:
        MH  - Myocardial Infarction
        MH  - Myocardial Infarction /therapy
        MH  - *Central Nervous System /drug effects

    Asterisk prefix indicates a major MeSH term (stored but noted).
    """
    terms: list[MeshTerm] = []
    for line in medline_text.splitlines():
        if not line.startswith("MH  - "):
            continue
        raw = line[6:].strip()

        is_major = raw.startswith("*")
        if is_major:
            raw = raw[1:].strip()

        if "/" in raw:
            descriptor, qualifier = raw.split("/", 1)
        else:
            descriptor = raw
            qualifier = ""

        terms.append(MeshTerm(descriptor=descriptor.strip(), qualifier=qualifier.strip()))
    return terms


def extract_mesh_from_xml(xml_content: str | bytes) -> list[MeshTerm]:
    """Extract MeSH terms from PubMed XML (MeshHeadingList element).

    XML structure:
        <MeshHeadingList>
            <MeshHeading>
                <DescriptorName UI="D009203">Term</DescriptorName>
                <QualifierName UI="Q000628">therapy</QualifierName>
            </MeshHeading>
        </MeshHeadingList>
    """
    if isinstance(xml_content, bytes):
        xml_content = xml_content.decode("utf-8", errors="replace")

    terms: list[MeshTerm] = []
    root = ET.fromstring(xml_content)

    for heading in root.iter("MeshHeading"):
        descriptor = None

        desc_el = heading.find("DescriptorName")
        if desc_el is not None:
            descriptor = MeshTerm(
                descriptor=desc_el.text or "",
                ui=desc_el.get("UI", ""),
            )

        has_qualifier = False
        for qual_el in heading.findall("QualifierName"):
            has_qualifier = True
            qualifier_str = qual_el.text or ""
            qualifier_ui = qual_el.get("UI", "")
            if descriptor is not None:
                terms.append(
                    MeshTerm(
                        descriptor=descriptor.descriptor,
                        qualifier=qualifier_str,
                        ui=qualifier_ui,
                    )
                )
            else:
                terms.append(
                    MeshTerm(descriptor=qualifier_str, qualifier="", ui=qualifier_ui)
                )

        if descriptor is not None and not has_qualifier:
            terms.append(descriptor)

    return terms


def extract_mesh_from_efetch_root(root: ET.Element) -> list[MeshTerm]:
    """Extract MeSH terms from an already-parsed PubMed efetch XML root.

    This avoids re-parsing when the caller already has an ElementTree.
    """
    terms: list[MeshTerm] = []
    for heading in root.iter("MeshHeading"):
        descriptor = None
        desc_el = heading.find("DescriptorName")
        if desc_el is not None:
            descriptor = MeshTerm(
                descriptor=desc_el.text or "",
                ui=desc_el.get("UI", ""),
            )
        for qual_el in heading.findall("QualifierName"):
            qualifier_str = qual_el.text or ""
            qualifier_ui = qual_el.get("UI", "")
            if descriptor is not None:
                terms.append(
                    MeshTerm(
                        descriptor=descriptor.descriptor,
                        qualifier=qualifier_str,
                        ui=qualifier_ui,
                    )
                )
            else:
                terms.append(
                    MeshTerm(
                        descriptor=qualifier_str, qualifier="", ui=qualifier_ui
                    )
                )
        if descriptor is not None and len(heading.findall("QualifierName")) == 0:
            terms.append(descriptor)
    return terms


class MeshIndex:
    """In-memory index mapping MeSH terms to PMIDs for lookup."""

    def __init__(self) -> None:
        self._by_descriptor: dict[str, set[str]] = {}
        self._by_ui: dict[str, set[str]] = {}
        self._article_terms: dict[str, list[MeshTerm]] = {}

    def add(self, pmid: str, terms: list[MeshTerm]) -> None:
        """Index MeSH terms for a given PMID."""
        self._article_terms[pmid] = terms
        for term in terms:
            if term.descriptor:
                self._by_descriptor.setdefault(term.descriptor.lower(), set()).add(pmid)
            if term.ui:
                self._by_ui.setdefault(term.ui, set()).add(pmid)

    def search_by_descriptor(self, descriptor: str) -> list[str]:
        """Find PMIDs matching a MeSH descriptor (case-insensitive)."""
        return list(self._by_descriptor.get(descriptor.lower(), set()))

    def search_by_ui(self, ui: str) -> list[str]:
        """Find PMIDs matching a MeSH unique ID."""
        return list(self._by_ui.get(ui, set()))

    def get_for_article(self, pmid: str) -> list[MeshTerm] | None:
        """Get all MeSH terms indexed for a PMID."""
        return self._article_terms.get(pmid)

    @property
    def article_count(self) -> int:
        return len(self._article_terms)

    @property
    def unique_descriptors(self) -> list[str]:
        return list(self._by_descriptor.keys())
