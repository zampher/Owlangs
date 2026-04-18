# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
import csv
from io import StringIO

from ir.document import Document


class Glossary:
    def __init__(self, glossary_dict: dict[str:str] = None):
        self.glossary_dict = glossary_dict

    def update(self, update_dict: dict[str:str]):
        for src, dst in update_dict.items():
            if src not in self.glossary_dict:
                self.glossary_dict[src] = dst

    def append_system_prompt(self, text: str):
        flag = False
        prompt = "\nHere is the reference glossary:\n"
        for src, dst in self.glossary_dict.items():
            if src in text:
                prompt += f"{src}=>{dst}\n"
                flag = True
        prompt += "Glossary ends\n"
        if flag:
            return prompt
        else:
            return ""

    def build_append_prompt_with_stats(self, text: str, max_items: int = 100):
        """Build terminology fragments that need to be concatenated to system prompt based on input text, and return statistics.
        Returns: (prompt_text, hit_count, samples[List[Tuple[src, dst]]])
        Strategy:
        1. First, find terms that appear in the text (contextual matches)
        2. If no contextual matches found, include all terms (up to max_items) to ensure glossary is always available
        3. This ensures glossary is always included even if current chunk doesn't contain the terms
        """
        if not self.glossary_dict:
            return "", 0, []
        
        # Step 1: Find terms that appear in the text (contextual matches)
        contextual_matches = []
        for src, dst in self.glossary_dict.items():
            if src and src in text:
                contextual_matches.append((src, dst))
                if len(contextual_matches) >= max_items:
                    break
        
        # Step 2: If contextual matches found, use them
        if contextual_matches:
            matches = contextual_matches
        else:
            # No contextual matches: include all terms (up to max_items) to ensure glossary is always available
            # This is critical for cases where the current chunk doesn't contain the terms,
            # but the glossary should still be available for the translation agent
            matches = list(self.glossary_dict.items())[:max_items]
        
        if not matches:
            return "", 0, []
        
        prompt_lines = ["\nHere is the reference glossary:"]
        for src, dst in matches:
            prompt_lines.append(f"{src}=>{dst}")
        prompt_lines.append("Glossary ends\n")
        prompt_text = "\n".join(prompt_lines)
        # Return at most 3 as examples
        samples = matches[:3]
        return prompt_text, len(matches), samples

    @staticmethod
    def glossary_dict2csv(glossary_dict: dict[str, str], delimiter=",", stem="glossary_gen") -> Document:
        csv_rows = [[src, dst] for src, dst in glossary_dict.items()]
        content = StringIO()
        writer = csv.writer(content, delimiter=delimiter)
        writer.writerow(['src', 'dst'])
        writer.writerows(csv_rows)
        bom = '\ufeff'
        content_with_bom = bom + content.getvalue()
        return Document.from_bytes(content=content_with_bom.encode("utf-8"), suffix=".csv", stem=stem)
