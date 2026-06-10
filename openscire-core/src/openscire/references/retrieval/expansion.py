from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_WORD_TOKENIZE = re.compile(r"\w+")

_SCI_SYNONYMS: dict[str, list[str]] = {
    "dna": ["deoxyribonucleic acid"],
    "rna": ["ribonucleic acid"],
    "mrna": ["messenger rna"],
    "pcr": ["polymerase chain reaction"],
    "qpcr": ["quantitative pcr", "real time pcr"],
    "rt_pcr": ["reverse transcription pcr"],
    "elisa": ["enzyme linked immunosorbent assay"],
    "mri": ["magnetic resonance imaging"],
    "fmri": ["functional magnetic resonance imaging"],
    "pet": ["positron emission tomography"],
    "ct": ["computed tomography"],
    "crispr": ["clustered regularly interspaced short palindromic repeats"],
    "cas9": ["crispr associated protein 9"],
    "ms": ["mass spectrometry"],
    "nmr": ["nuclear magnetic resonance"],
    "hplc": ["high performance liquid chromatography"],
    "lc_ms": ["liquid chromatography mass spectrometry"],
    "gwas": ["genome wide association study"],
    "rnaseq": ["rna sequencing"],
    "chip_seq": ["chromatin immunoprecipitation sequencing"],
    "scrna_seq": ["single cell rna sequencing"],
    "em": ["electron microscopy"],
    "sem": ["scanning electron microscopy"],
    "tem": ["transmission electron microscopy"],
    "afm": ["atomic force microscopy"],
    "xrd": ["x ray diffraction"],
    "ftir": ["fourier transform infrared spectroscopy"],
    "uv_vis": ["ultraviolet visible spectroscopy"],
    "tumor": ["tumour", "neoplasm", "cancer"],
    "tumour": ["tumor", "neoplasm", "cancer"],
    "cancer": ["tumor", "tumour", "neoplasm", "malignancy"],
    "cell": ["cellular"],
    "protein": ["polypeptide"],
    "gene": ["genetic locus"],
    "enzym": ["catalyst"],  # stem: enzyme, enzymatic
    "antibody": ["immunoglobulin"],
    "patient": ["subject", "participant"],
    "drug": ["pharmaceutical", "medication"],
    "therapy": ["treatment", "intervention"],
    "surgery": ["operation", "surgical intervention"],
    "infection": ["pathogen invasion"],
    "inflammation": ["inflammatory response"],
    "apoptosis": ["programmed cell death"],
    "angiogenesis": ["blood vessel formation", "neovascularization"],
    "metastasis": ["metastatic spread", "tumor dissemination"],
    "genotype": ["genetic makeup"],
    "phenotype": ["observable trait"],
    "genome": ["whole genome", "entire genetic material"],
    "transcriptome": ["gene expression profile"],
    "proteome": ["protein complement"],
    "metabolome": ["metabolite profile"],
    "microbiome": ["microbial community"],
    "kinase": ["phosphotransferase"],
    "receptor": ["binding site"],
    "ligand": ["binding molecule"],
    "transcription": ["gene expression", "rna synthesis"],
    "translation": ["protein synthesis"],
    "mutation": ["variant", "alteration", "polymorphism"],
    "polymorphism": ["variant", "mutation", "genetic variation"],
    "methylation": ["dna methylation", "epigenetic modification"],
    "phosphorylation": ["protein phosphorylation"],
    "ubiquitination": ["ubiquitylation"],
    "glycosylation": ["glycation"],
    "oxidation": ["oxidative modification"],
    "reduction": ["reductive modification"],
    "stem_cell": ["progenitor cell"],
    "neuron": ["nerve cell"],
    "macrophage": ["phagocyte"],
    "lymphocyte": ["white blood cell"],
    "cytokine": ["interleukin", "chemokine"],
    "antibiotic": ["antimicrobial", "antibacterial"],
    "vaccine": ["immunization", "inoculation"],
    "genomic": ["genetic"],
    "proteomic": ["protein level"],
    "transcriptomic": ["gene expression"],
    "metabolomic": ["metabolite"],
    "bioinformatics": ["computational biology"],
    "phylogenetic": ["evolutionary"],
    "homolog": ["ortholog", "orthologue", "paralog", "paralogue"],
    "in_vitro": ["cell based", "in culture"],
    "in_vivo": ["in living organism", "in animal model"],
    "ex_vivo": ["outside living organism"],
    "in_silico": ["computational", "simulation based"],
    "clinical": ["patient based", "human study"],
    "preclinical": ["animal study", "animal model"],
}


class QueryExpander:
    def __init__(self, custom_dict: dict[str, list[str]] | None = None) -> None:
        self._synonyms: dict[str, list[str]] = {}
        self._synonyms.update(_SCI_SYNONYMS)
        if custom_dict:
            for key, values in custom_dict.items():
                key_lower = key.lower()
                if key_lower in self._synonyms:
                    combined = list(set(self._synonyms[key_lower] + values))
                    self._synonyms[key_lower] = combined
                else:
                    self._synonyms[key_lower] = values

    def expand(self, query: str) -> list[str]:
        if not query or not query.strip():
            return []

        tokens = _WORD_TOKENIZE.findall(query.lower())
        if not tokens:
            return [query.strip()]

        expanded_variants: list[str] = []
        expansions_by_token: dict[str, list[str]] = {}

        for token in tokens:
            expansions_by_token[token] = self._synonyms.get(token, [])

        has_any_expansion = any(expansions_by_token.values())
        if not has_any_expansion:
            return [query.strip()]

        expanded_token_groups: list[list[str]] = []
        for token in tokens:
            group = [token]
            group.extend(expansions_by_token.get(token, []))
            expanded_token_groups.append(group)

        original_tokens = [token for token in tokens]
        base_tokens = []
        for token in tokens:
            expansions = expansions_by_token.get(token, [])
            if expansions:
                base_tokens.append(f"({' '.join([token] + expansions)})")
            else:
                base_tokens.append(token)

        if base_tokens != original_tokens:
            expanded_variants.append(" ".join(base_tokens))

        extra_variants: list[str] = []
        for token, exps in expansions_by_token.items():
            if exps:
                for exp in exps[:1]:
                    variant_tokens = [exp if t == token else t for t in original_tokens]
                    variant = " ".join(variant_tokens)
                    if variant != query.lower():
                        extra_variants.append(variant)

        result: list[str] = [query.strip()]
        if expanded_variants:
            result.append(expanded_variants[0])
        result.extend(extra_variants[:3])

        return result
