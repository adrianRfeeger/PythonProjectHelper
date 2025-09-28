"""LLM-TDS (Token Dictionary Substitution) exporter."""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Dict

from .base import Exporter, register_exporter
from analysis.schema import ProjectAnalysis


@register_exporter
class LLMTDSExporter(Exporter):
    """LLM-friendly format using token dictionary substitution."""
    
    @property
    def name(self) -> str:
        return "llm-tds"
    
    def render(self, analysis: Dict[str, Any], options: Dict[str, Any]) -> str:
        """Render analysis as LLM-TDS format."""
        project_analysis = ProjectAnalysis(**analysis)
        
        # Build token dictionary from all text content
        all_text = self._extract_all_text(project_analysis)
        dictionary = self._build_token_dictionary(all_text, options.get("dictionary_size", 256))
        
        # Apply dictionary substitution
        compressed_content = self._apply_dictionary(all_text, dictionary)
        
        result = {
            "format": "llm-tds",
            "version": "1.0",
            "disclaimer": "LLM codec is lossy and not intended for project recovery.",
            "project": {
                "name": project_analysis.project.name,
                "generated_at": project_analysis.generated_at.isoformat(),
                "fingerprint": project_analysis.project.fingerprint,
                "totals": project_analysis.project.totals.dict()
            },
            "dictionary": dictionary,
            "content": {
                "codec": "tds_v1",
                "payload": compressed_content
            }
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False)
    
    def mimetype(self) -> str:
        return "application/json"
    
    def is_lossless(self) -> bool:
        return False
    
    def is_llm_friendly(self) -> bool:
        return True
    
    def _extract_all_text(self, analysis: ProjectAnalysis) -> str:
        """Extract all text content for dictionary building."""
        text_parts = []
        
        # Add project metadata
        text_parts.append(f"Project: {analysis.project.name}")
        
        # Add file information
        for file_info in analysis.files:
            text_parts.append(f"File: {file_info.path}")
            text_parts.append(f"Language: {file_info.language}")
            
            if file_info.responsibility:
                text_parts.append(f"Purpose: {file_info.responsibility}")
            
            # Add imports
            for imp in file_info.imports.internal + file_info.imports.external:
                text_parts.append(f"Import: {imp}")
            
            # Add class/function signatures
            for cls in file_info.classes:
                text_parts.append(f"Class: {cls.name}")
                if cls.doc1:
                    text_parts.append(cls.doc1)
                for method in cls.methods:
                    text_parts.append(f"Method: {method}")
            
            for func in file_info.functions:
                text_parts.append(f"Function: {func.signature}")
                if func.doc1:
                    text_parts.append(func.doc1)
        
        return " ".join(text_parts)
    
    def _build_token_dictionary(self, text: str, max_tokens: int) -> Dict[str, str]:
        """Build a dictionary of common tokens for compression."""
        # Extract word-like tokens
        word_pattern = re.compile(r'[A-Za-z_][A-Za-z0-9_]{2,}')
        words = word_pattern.findall(text)
        
        # Count frequency
        counter = Counter(words)
        most_common = counter.most_common(max_tokens)
        
        # Build dictionary with token markers
        dictionary = {}
        for i, (word, _) in enumerate(most_common, 1):
            token = f"§{i}"
            dictionary[token] = word
        
        return dictionary
    
    def _apply_dictionary(self, text: str, dictionary: Dict[str, str]) -> str:
        """Apply dictionary substitution to compress text."""
        # Reverse dictionary for lookup
        word_to_token = {word: token for token, word in dictionary.items()}
        
        # Sort words by length (longest first) to avoid partial matches
        sorted_words = sorted(word_to_token.keys(), key=len, reverse=True)
        
        # Replace words with tokens
        result = text
        for word in sorted_words:
            # Use word boundaries to avoid partial replacements
            pattern = r'\b' + re.escape(word) + r'\b'
            result = re.sub(pattern, word_to_token[word], result)
        
        return result