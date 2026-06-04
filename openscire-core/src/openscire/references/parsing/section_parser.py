from __future__ import annotations

import re

from openscire.references.models import ArticleSection, FullTextArticle, ReferenceAuthor

_ABSTRACT_HEADINGS = re.compile(
    r"^(abstract|summary|background|aims?|objective)s?[\s.:]*$",
    re.IGNORECASE,
)

_SECTION_HEADINGS = re.compile(
    r"^("
    r"introduction|background|methods?|materials?\s+(and\s+)?methods?|"
    r"methodology|experimental|theory|calculations?|"
    r"results?|findings|discussion|conclusion|"
    r"results?\s+(and\s+)?discussion|conclusions?|"
    r"acknowledgments?|acknowledgements?|funding|"
    r"conflict(ing)?\s+of\s+interest|competing\s+interests|"
    r"supplementary\s+materials?|references|bibliography|"
    r"appendix|supporting\s+information|data\s+availability|"
    r"author\s+contributions?|contributors?|"
    r"ethics|declaration|notes?|footnotes?"
    r")[\s.:]*$",
    re.IGNORECASE,
)

_ABSTRACT_MARKERS = re.compile(
    r"\b(abstract|summary|highlights)\b",
    re.IGNORECASE,
)

_AUTHOR_LINE = re.compile(
    r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s*,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)*)$",
)

_AUTHOR_SEPARATOR = re.compile(r",\s*|\s+and\s+|\s*;\s*")

_EMAIL_LINE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


class SectionParser:
    def parse(self, raw_text: str) -> FullTextArticle:
        lines = raw_text.split("\n")
        cleaned_lines = [ln.strip() for ln in lines if ln.strip()]

        article = FullTextArticle()
        article.raw_text = raw_text

        sections = self._extract_sections(cleaned_lines)

        for section in sections:
            if self._is_abstract_section(section.heading):
                article.abstract = section.body
            elif section.heading.lower().strip(" .:") == "references":
                ref_text = section.body
                refs = [
                    r.strip() for r in ref_text.split("\n") if r.strip() and not r.strip().isdigit()
                ]
                article.references = refs

        article.sections = [s for s in sections if not self._is_abstract_section(s.heading)]

        if not article.sections and not article.abstract and cleaned_lines:
            article.abstract = "\n".join(cleaned_lines[:5])

        author_block = self._extract_author_block_from_above(
            raw_text, article.abstract if article.abstract else ""
        )
        if author_block:
            article.authors = author_block

        first_line = cleaned_lines[0] if cleaned_lines else ""
        if first_line and not _SECTION_HEADINGS.match(first_line):
            article.title = first_line.strip(" .")

        return article

    def _extract_sections(self, lines: list[str]) -> list[ArticleSection]:
        sections: list[ArticleSection] = []
        current_heading = ""
        current_body: list[str] = []

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            heading_match = _SECTION_HEADINGS.match(line)
            if heading_match:
                if current_heading or current_body:
                    sections.append(
                        ArticleSection(
                            heading=current_heading,
                            body="\n".join(current_body).strip(),
                        )
                    )
                current_heading = heading_match.group(1).strip().title()
                current_body = []
            else:
                if _ABSTRACT_MARKERS.search(line) and not current_heading:
                    if current_body:
                        sections.append(
                            ArticleSection(
                                heading=current_heading,
                                body="\n".join(current_body).strip(),
                            )
                        )
                    current_heading = "Abstract"
                    current_body = []
                else:
                    current_body.append(line)

            i += 1

        if current_heading or current_body:
            sections.append(
                ArticleSection(
                    heading=current_heading,
                    body="\n".join(current_body).strip(),
                )
            )

        return sections

    def _extract_author_block_from_above(
        self,
        raw_text: str,
        abstract_text: str,
    ) -> list[ReferenceAuthor]:
        if not abstract_text:
            return []
        abstract_start = raw_text.find(abstract_text[:50])
        if abstract_start < 0:
            return []
        above = raw_text[:abstract_start].strip()
        lines = [ln.strip() for ln in above.split("\n") if ln.strip()]

        author_candidates: list[str] = []
        for line in lines:
            if _EMAIL_LINE.search(line):
                continue
            if len(line) < 5 or len(line) > 300:
                continue
            parts = re.split(r"[,\s;]+", line)
            name_like = all(
                p[0].isupper() if p else False for p in parts if p and not p.startswith("(")
            )
            if name_like and not _SECTION_HEADINGS.match(line):
                author_candidates.append(line)

        seen: set[str] = set()
        authors: list[ReferenceAuthor] = []
        for candidate in author_candidates:
            names = re.split(r"\s*,\s*|\s+and\s+|\s*;\s*", candidate)
            for name in names:
                name = name.strip().strip(".")
                if not name or len(name) < 2:
                    continue
                if name.lower() in seen:
                    continue
                seen.add(name.lower())
                parts = name.split(None, 1)
                if len(parts) == 1:
                    authors.append(ReferenceAuthor(full=name, last=name))
                elif len(parts) == 2:
                    authors.append(
                        ReferenceAuthor(
                            first=parts[0].strip("."), last=parts[1].strip("."), full=name
                        )
                    )

        return authors[:20]

    @staticmethod
    def _is_abstract_section(heading: str) -> bool:
        return bool(_ABSTRACT_HEADINGS.match(heading.strip()))
