from dataclasses import dataclass


@dataclass(frozen=True)
class Citation:
    source: str
    page: int | None = None


citations = []
for page in [12, 7, 7]:
    citation = Citation(source="/notes/lab.pdf", page=page)
    if citation not in citations:
        citations.append(citation)

print(citations)
