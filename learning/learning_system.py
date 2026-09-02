"""
Shadow Learning System — Document ingestion, text extraction, knowledge summarization, and retrieval.

Responsibilities:
  - Ingest individual files or entire directories (txt, md, py, pdf, json, etc.)
  - Extract text and handle optional dependencies like PyPDF2 for PDFs
  - Extract knowledge, summaries, key facts, and categories using Ollama or rule-based fallback
  - Maintain persistent index in KNOWLEDGE_DIR/index.json
  - Search and retrieve knowledge by topic or query
"""

import os
import sys
import json
import re
import time
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from config.config import KNOWLEDGE_DIR
from logging.logger import ShadowLogger

log = ShadowLogger.get("shadow.learning")

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll",
    "they're", "they've", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're",
    "we've", "were", "weren't", "what", "what's", "when", "when's", "where",
    "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with",
    "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've",
    "your", "yours", "yourself", "yourselves", "this", "that", "with", "from",
}


class LearningSystem:
    """Knowledge ingestion and retrieval subsystem for Shadow."""

    def __init__(self, ollama=None):
        self.ollama = ollama
        self.knowledge_dir = Path(KNOWLEDGE_DIR)
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.knowledge_dir / "index.json"

        # Lazy load OllamaInterface if not passed
        if self.ollama is None:
            try:
                from ollama.ollama_interface import OllamaInterface
                self.ollama = OllamaInterface()
            except Exception as e:
                log.warning(f"OllamaInterface not available for LearningSystem: {e}")
                self.ollama = None

        # Ensure index file exists
        if not self.index_file.exists():
            self._save_index({})

    def _load_index(self) -> dict:
        """Load the knowledge base index from JSON file."""
        if not self.index_file.exists():
            return {}
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Failed to load knowledge index: {e}")
            return {}

    def _save_index(self, index_data: dict) -> None:
        """Save the knowledge base index to JSON file."""
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"Failed to save knowledge index: {e}")

    def ingest_file(self, file_path: str) -> dict:
        """
        Ingest a file (txt, pdf, md, py, etc.), extract text, summarize, and store in KNOWLEDGE_DIR.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            log.warning(f"File not found for ingestion: {file_path}")
            return {"success": False, "error": f"File not found: {file_path}"}

        log.info(f"Ingesting file: {path.name}")
        ext = path.suffix.lower()
        text = ""

        # PDF handling
        if ext == ".pdf":
            text = self._read_pdf(path)
            if text is None:
                return {
                    "success": False,
                    "skipped": True,
                    "reason": "PyPDF2 or pypdf not available or unable to read PDF",
                    "file_path": str(path),
                }
        else:
            # Text file handling
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception as e:
                log.error(f"Failed to read text file {path.name}: {e}")
                return {"success": False, "error": f"Failed to read file: {str(e)}", "file_path": str(path)}

        if not text.strip():
            log.warning(f"No text extracted from file: {path.name}")
            return {"success": False, "error": "File is empty or contains no readable text", "file_path": str(path)}

        # Extract knowledge from text
        knowledge = self.extract_knowledge(text)

        topic = path.stem.replace("_", " ").replace("-", " ").title()
        entry_id = f"doc_{int(time.time())}_{path.name}"

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        entry = {
            "id": entry_id,
            "topic": topic,
            "source_file": str(path),
            "file_name": path.name,
            "date_ingested": now_iso,
            "summary": knowledge.get("summary", ""),
            "keywords": knowledge.get("keywords", []),
            "category": knowledge.get("category", "General"),
            "facts": knowledge.get("facts", []),
            "full_text": text,
        }

        # Store document JSON file in KNOWLEDGE_DIR
        doc_file = self.knowledge_dir / f"{entry_id}.json"
        try:
            with open(doc_file, "w", encoding="utf-8") as f:
                json.dump(entry, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"Failed to write knowledge document file: {e}")

        # Update index
        index = self._load_index()
        index[entry_id] = {
            "id": entry_id,
            "topic": topic,
            "source_file": str(path),
            "file_name": path.name,
            "date_ingested": now_iso,
            "summary": entry["summary"],
            "keywords": entry["keywords"],
            "category": entry["category"],
            "doc_file": str(doc_file),
        }
        self._save_index(index)

        log.info(f"Successfully ingested file '{path.name}' as topic '{topic}'")
        return {
            "success": True,
            "file_path": str(path),
            "topic": topic,
            "summary": entry["summary"],
            "keywords": entry["keywords"],
            "category": entry["category"],
            "entry_id": entry_id,
        }

    def _read_pdf(self, path: Path) -> Optional[str]:
        """Try reading a PDF file using PyPDF2 or pypdf."""
        # Try PyPDF2
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(str(path))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        except ImportError:
            pass
        except Exception as e:
            log.warning(f"PyPDF2 failed reading {path.name}: {e}")

        # Try pypdf
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        except ImportError:
            log.warning("Neither PyPDF2 nor pypdf is installed. Skipping PDF file.")
        except Exception as e:
            log.warning(f"pypdf failed reading {path.name}: {e}")

        return None

    def ingest_directory(self, dir_path: str) -> dict:
        """Recursively ingest all readable files in a directory."""
        path = Path(dir_path).resolve()
        if not path.is_dir():
            log.warning(f"Directory not found for ingestion: {dir_path}")
            return {"success": False, "error": f"Not a directory: {dir_path}"}

        log.info(f"Ingesting directory: {path}")
        ingested = 0
        skipped = 0
        file_results = []

        skip_extensions = {".pyc", ".exe", ".dll", ".so", ".o", ".a", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".tar", ".gz", ".db", ".sqlite"}

        for root, dirs, files in os.walk(path):
            # Exclude hidden directories and __pycache__
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

            for f in sorted(files):
                if f.startswith("."):
                    skipped += 1
                    continue

                f_path = Path(root) / f
                if f_path.suffix.lower() in skip_extensions:
                    skipped += 1
                    continue

                res = self.ingest_file(str(f_path))
                if res.get("success"):
                    ingested += 1
                    file_results.append(str(f_path))
                else:
                    skipped += 1

        log.info(f"Directory ingestion complete for '{path.name}': {ingested} ingested, {skipped} skipped.")
        return {
            "success": True,
            "dir_path": str(path),
            "ingested": ingested,
            "skipped": skipped,
            "files": file_results,
        }

    def extract_knowledge(self, text: str) -> dict:
        """
        Uses Ollama (if available) to extract key facts, summaries, and categories.
        Falls back to rule-based processing if Ollama is unavailable.
        """
        if self.ollama and hasattr(self.ollama, "is_available") and self.ollama.is_available():
            prompt = (
                f"Analyze the following text and extract knowledge in JSON format.\n\n"
                f"Text:\n{text[:4000]}\n\n"
                f"Return ONLY JSON with key structure:\n"
                f'{{\n  "summary": "A concise 2-3 sentence summary",\n'
                f'  "keywords": ["list", "of", "5-10", "key", "topics"],\n'
                f'  "category": "Documentation|Code|Research|General|Config",\n'
                f'  "facts": ["Key fact 1", "Key fact 2"]\n}}'
            )
            try:
                response = self.ollama.generate(prompt)
                match = re.search(r"\{.*\}", response, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    if isinstance(parsed, dict) and "summary" in parsed:
                        return parsed
            except Exception as e:
                log.warning(f"Ollama knowledge extraction failed: {e}")

        # Fallback rule-based extraction
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
        # Summary: first non-empty lines or characters
        summary = " ".join(lines[:3])[:300] if lines else "No summary available."

        # Keywords: frequency of non-stop words
        words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
        filtered_words = [w for w in words if w not in STOP_WORDS]
        word_counts = {}
        for w in filtered_words:
            word_counts[w] = word_counts.get(w, 0) + 1
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        keywords = [w for w, _ in sorted_words[:8]]

        # Category rule
        category = "General"
        if "def " in text or "class " in text or "import " in text:
            category = "Code"
        elif "# " in text or "==" in text:
            category = "Documentation"
        elif "{" in text and ":" in text:
            category = "Config"

        # Facts: first few informative sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)
        facts = [s.strip() for s in sentences if len(s.strip()) > 20][:3] if sentences else []

        return {
            "summary": summary,
            "keywords": keywords,
            "category": category,
            "facts": facts,
        }

    def search_knowledge(self, query: str) -> list[dict]:
        """Search the knowledge base for relevant entries matching the query."""
        if not query.strip():
            return []

        q_clean = query.lower().strip()
        q_words = set(re.findall(r"\w+", q_clean))
        index = self._load_index()
        results = []

        for entry_id, meta in index.items():
            score = 0
            topic = meta.get("topic", "").lower()
            summary = meta.get("summary", "").lower()
            file_name = meta.get("file_name", "").lower()
            category = meta.get("category", "").lower()
            keywords = [k.lower() for k in meta.get("keywords", [])]

            if q_clean in topic:
                score += 10
            if q_clean in file_name:
                score += 8
            if any(q_clean in k for k in keywords):
                score += 6
            if q_clean in summary:
                score += 4
            if q_clean in category:
                score += 2

            # Word level matching
            for word in q_words:
                if word in topic:
                    score += 3
                if any(word in k for k in keywords):
                    score += 2
                if word in summary:
                    score += 1

            if score > 0:
                results.append((score, meta))

        # Sort by match score descending
        results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in results]

    def get_knowledge(self, topic: str) -> Optional[dict]:
        """Retrieve knowledge entry about a specific topic."""
        if not topic.strip():
            return None

        t_clean = topic.lower().strip()
        index = self._load_index()

        # Check exact topic match, entry_id match, or source file match
        for entry_id, meta in index.items():
            if (
                meta.get("topic", "").lower() == t_clean
                or entry_id.lower() == t_clean
                or meta.get("file_name", "").lower() == t_clean
            ):
                return self._load_full_doc(meta)

        # Fallback: partial match
        for entry_id, meta in index.items():
            if t_clean in meta.get("topic", "").lower() or t_clean in meta.get("file_name", "").lower():
                return self._load_full_doc(meta)

        return None

    def _load_full_doc(self, meta: dict) -> dict:
        """Load full document JSON if available, else return index metadata."""
        doc_file_str = meta.get("doc_file")
        if doc_file_str:
            doc_path = Path(doc_file_str)
            if doc_path.exists():
                try:
                    with open(doc_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    log.error(f"Failed loading full doc file {doc_path}: {e}")
        return meta


def self_test() -> bool:
    """Component self-test required by run_tests.py."""
    try:
        ls = LearningSystem()

        # Test 1: Ingest test file
        test_file = ls.knowledge_dir / "test_sample.txt"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(
                "Shadow Learning System Test Document.\n"
                "Shadow is an autonomous AI network written in Python.\n"
                "It uses Ollama and local storage for knowledge management.\n"
            )

        ingest_res = ls.ingest_file(str(test_file))
        if not ingest_res.get("success"):
            log.error(f"LearningSystem self_test failed on ingest_file: {ingest_res}")
            return False

        # Test 2: Search knowledge
        search_res = ls.search_knowledge("autonomous")
        if not search_res:
            log.error("LearningSystem self_test search_knowledge returned empty")
            return False

        # Test 3: Get knowledge
        know = ls.get_knowledge("Test Sample")
        if not know or "Shadow" not in know.get("full_text", ""):
            log.error(f"LearningSystem self_test get_knowledge failed: {know}")
            return False

        # Cleanup test artifacts
        test_file.unlink(missing_ok=True)

        log.info("LearningSystem self_test passed successfully.")
        return True
    except Exception as e:
        log.error(f"LearningSystem self_test exception: {e}")
        return False


if __name__ == "__main__":
    if self_test():
        print("LearningSystem tests PASSED.")
    else:
        print("LearningSystem tests FAILED.")
        sys.exit(1)
