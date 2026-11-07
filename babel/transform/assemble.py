"""Turn labeled segments into display blocks."""

from __future__ import annotations

from babel.models import Block, BlockType, Segment, SegmentKind
from babel.transform.segment import strip_marks

Label = tuple[BlockType, str | None]

_MERGEABLE = {BlockType.NARRATION, BlockType.SYSTEM}


def assemble(segments: list[Segment], labels: dict[int, Label]) -> list[Block]:
    """Build blocks, merging within a paragraph where it reads better.

    - Consecutive narration/system segments in a paragraph join into one block.
    - Dialogue split by a speech tag (`"Hi," he said, "come in."`) becomes one
      bubble followed by the tag, which the reader renders as a caption.
    """
    blocks: list[Block] = []
    para_start = 0
    for seg in segments:
        btype, speaker = labels.get(seg.id, (BlockType.NARRATION, None))
        text = strip_marks(seg.text, seg.kind) if btype in (BlockType.DIALOGUE, BlockType.THOUGHT) else seg.text
        if btype == BlockType.SYSTEM and seg.kind == SegmentKind.BRACKET:
            text = seg.text.strip()
        if not text:
            continue

        if blocks and blocks[-1].para == seg.para:
            prev = blocks[-1]
            # same-type prose merge
            if btype in _MERGEABLE and prev.type == btype:
                prev.text = f"{prev.text} {text}"
                prev.seg.append(seg.id)
                continue
            # "Hi," he said, "come in."  →  one bubble + tag (only when the tag
            # interrupts a sentence, so no content is reordered across sentences)
            if (
                btype in (BlockType.DIALOGUE, BlockType.THOUGHT)
                and prev.type == BlockType.TAG
                and prev.text.rstrip().endswith((",", "—", "–", "-"))
                and len(blocks) - para_start >= 2
            ):
                bubble = blocks[-2]
                if bubble.para == seg.para and bubble.type == btype and bubble.speaker == speaker:
                    bubble.text = f"{bubble.text} {text}"
                    bubble.seg.append(seg.id)
                    continue
            if btype == BlockType.TAG and prev.type == BlockType.TAG:
                prev.text = f"{prev.text} {text}"
                prev.seg.append(seg.id)
                continue
        else:
            para_start = len(blocks)
        blocks.append(Block(type=btype, text=text, speaker=speaker, para=seg.para, seg=[seg.id]))

    # A tag with no adjacent bubble is just narration.
    for i, b in enumerate(blocks):
        if b.type == BlockType.TAG:
            near = [blocks[j] for j in (i - 1, i + 1) if 0 <= j < len(blocks) and blocks[j].para == b.para]
            if not any(n.type in (BlockType.DIALOGUE, BlockType.THOUGHT) for n in near):
                b.type = BlockType.NARRATION
    return blocks


def coverage(segments: list[Segment], blocks: list[Block]) -> float:
    """Fraction of segments represented in blocks (should always be 1.0)."""
    if not segments:
        return 1.0
    seen = {i for b in blocks for i in b.seg}
    return len(seen & {s.id for s in segments}) / len(segments)
