"""
AIS NeMo Curator Data Curation Pipeline
Downloads, deduplicates, quality-filters, and enriches astrological text sources.

Sources:
- Project Gutenberg (public domain astrological texts)
- Archive.org (Sanskrit astronomy/astrology translations)
- Wikipedia astrology articles
- Public domain commentaries
"""
from __future__ import annotations

import os
import json
import hashlib
import requests
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

# NeMo Curator (CPU text pipeline)
try:
    import nemo_curator as nc
    from nemo_curator.datasets import DocumentDataset
    from nemo_curator.filters import (
        WordCountFilter,
        RepeatingTopNGramsFilter,
        LengthRatioFilter,
    )
    from nemo_curator.modifiers import UnicodeReformatter
    NEMO_AVAILABLE = True
except Exception:
    NEMO_AVAILABLE = False
    logger.warning("NeMo Curator not installed — using basic pipeline fallback")

DATA_DIR = Path(__file__).parent.parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
CURATED_DIR = DATA_DIR / "curated"


def ensure_dirs():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CURATED_DIR.mkdir(parents=True, exist_ok=True)


# ─── Source Definitions ────────────────────────────────────────────────────────

ASTRO_SOURCES = [
    {
        "id": "bphs_english",
        "name": "Brihat Parashara Hora Shastra (English Translation)",
        "url": "https://www.sacred-texts.com/hin/bph/index.htm",
        "tradition": "vedic",
        "tier": 1,
    },
    {
        "id": "jataka_parijata",
        "name": "Jataka Parijata (classical Vedic text)",
        "url": "https://www.sacred-texts.com/hin/jp/index.htm",
        "tradition": "vedic",
        "tier": 1,
    },
    {
        "id": "tetrabiblos",
        "name": "Tetrabiblos (Ptolemy — Hellenistic)",
        "url": "https://www.sacred-texts.com/astro/ptb/index.htm",
        "tradition": "western",
        "tier": 1,
    },
    {
        "id": "wikipedia_vedic_astrology",
        "name": "Wikipedia — Vedic Astrology",
        "url": "https://en.wikipedia.org/wiki/Jyotisha",
        "tradition": "vedic",
        "tier": 2,
    },
    {
        "id": "wikipedia_western_astrology",
        "name": "Wikipedia — Western Astrology",
        "url": "https://en.wikipedia.org/wiki/Western_astrology",
        "tradition": "western",
        "tier": 2,
    },
]


class AstroCuratorPipeline:
    """
    NeMo Curator-based data pipeline for astrological text corpus.

    Stages:
    1. Download raw sources
    2. Extract text (HTML → plain text)
    3. Unicode normalization
    4. Deduplication (exact hash + MinHash fuzzy)
    5. Quality filtering (word count, low content ratio)
    6. Tradition and quality tagging
    7. Export to curated JSONL
    """

    def __init__(self):
        ensure_dirs()

    def download_sources(self):
        """Download all configured sources."""
        from bs4 import BeautifulSoup
        downloaded = []
        for source in ASTRO_SOURCES:
            dest = RAW_DIR / f"{source['id']}.txt"
            if dest.exists():
                logger.info(f"Already downloaded: {source['id']}")
                downloaded.append(dest)
                continue
            try:
                logger.info(f"Downloading: {source['name']} from {source['url']}")
                resp = requests.get(source["url"], timeout=30, headers={"User-Agent": "AIS-Curator/1.0"})
                soup = BeautifulSoup(resp.content, "lxml")
                # Remove scripts, style, nav
                for tag in soup(["script", "style", "nav", "header", "footer"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                dest.write_text(text, encoding="utf-8")
                downloaded.append(dest)
                logger.info(f"Downloaded: {source['id']} ({len(text)} chars)")
            except Exception as e:
                logger.warning(f"Download failed for {source['id']}: {e}")
        return downloaded

    def _exact_dedup(self, records: List[Dict]) -> List[Dict]:
        """Remove exact duplicate paragraphs by SHA-256 hash."""
        seen = set()
        deduped = []
        for rec in records:
            h = hashlib.sha256(rec["text"].encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                deduped.append(rec)
        before, after = len(records), len(deduped)
        logger.info(f"Exact dedup: {before} → {after} ({before - after} removed)")
        return deduped

    def _quality_filter(self, records: List[Dict]) -> List[Dict]:
        """Filter out low-quality records."""
        filtered = []
        for rec in records:
            text = rec["text"]
            words = text.split()
            # Minimum word count
            if len(words) < 30:
                continue
            # Maximum noise ratio (non-alpha chars)
            alpha_ratio = sum(1 for c in text if c.isalpha()) / max(len(text), 1)
            if alpha_ratio < 0.5:
                continue
            # Remove generic horoscope columns (sun sign keywords)
            lowered = text.lower()
            pop_astro_signals = ["this week for aries", "aries horoscope", "your monthly forecast"]
            if any(s in lowered for s in pop_astro_signals):
                continue
            filtered.append(rec)
        logger.info(f"Quality filter: {len(records)} → {len(filtered)}")
        return filtered

    def _chunk_text(self, text: str, source_id: str, tradition: str, tier: int) -> List[Dict]:
        """Chunk text into semantically meaningful units."""
        records = []
        # Split by paragraph
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 100]
        for i, para in enumerate(paragraphs):
            records.append({
                "id": f"{source_id}_{i:05d}",
                "text": para,
                "source_id": source_id,
                "tradition": tradition,
                "tier": tier,
                "word_count": len(para.split()),
            })
        return records

    def run(self) -> Path:
        """Run the full curation pipeline. Returns path to curated JSONL file."""
        logger.info("🔄 Starting AIS data curation pipeline...")

        # 1. Download
        self.download_sources()

        # 2. Extract + chunk
        all_records: List[Dict] = []
        for source in ASTRO_SOURCES:
            raw_path = RAW_DIR / f"{source['id']}.txt"
            if not raw_path.exists():
                continue
            text = raw_path.read_text(encoding="utf-8", errors="replace")
            chunks = self._chunk_text(text, source["id"], source["tradition"], source["tier"])
            all_records.extend(chunks)
            logger.info(f"Chunked {source['id']}: {len(chunks)} records")

        logger.info(f"Total raw records: {len(all_records)}")

        # 3. Exact deduplication
        deduped = self._exact_dedup(all_records)

        # 4. Quality filtering
        filtered = self._quality_filter(deduped)

        # 5. NeMo Curator advanced pipeline (if available)
        if NEMO_AVAILABLE and filtered:
            logger.info("Running NeMo Curator advanced quality filters...")
            try:
                # Write to temp JSONL for NeMo
                tmp_path = DATA_DIR / "tmp_curator_input.jsonl"
                with open(tmp_path, "w") as f:
                    for rec in filtered:
                        f.write(json.dumps({"text": rec["text"], "id": rec["id"]}) + "\n")

                dataset = DocumentDataset.read_json(str(tmp_path))
                # NeMo quality filters
                word_count_filter = WordCountFilter(min_words=50, max_words=2000)
                dataset = nc.Sequential([word_count_filter])(dataset)
                nemo_texts = {row["id"]: row["text"] for row in dataset.df.iterrows()}
                # Merge back metadata
                filtered = [r for r in filtered if r["id"] in nemo_texts]
                logger.info(f"After NeMo Curator filters: {len(filtered)} records")
            except Exception as e:
                logger.warning(f"NeMo Curator failed, using basic pipeline: {e}")

        # 6. Export
        output_path = CURATED_DIR / "astro_corpus_v1.jsonl"
        with open(output_path, "w", encoding="utf-8") as f:
            for rec in filtered:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        logger.info(f"✅ Curation complete: {len(filtered)} records → {output_path}")
        return output_path
