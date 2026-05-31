"""
Phase-4: Sectionization and hybrid chunking.

Pass 1 (structural grouping) groups consecutive ExtractedUnits by section_path.
Pass 2 (semantic splitting) splits long structural groups via embedding boundary scores.
Pass 3 (atomic preservation) isolates tables and code blocks from mixed semantic chunks.
Pass 4 (overlap insertion) adds prefix overlap between adjacent prose siblings and emits final chunks.
"""
