"""Turn per-segment decisions into display blocks."""

from __future__ import annotations

from babel.models import Block, BlockType, Decision, Segment, SegmentKind
from babel.scenario.segment import strip_marks

_MERGEABLE = {BlockType.NARRATION, BlockType.SYSTEM, BlockType.ACTION}


def assemble(segments: list[Segment], decisions: dict[int, Decision]) -> list[Block]:
    """Build blocks, merging within a paragraph where it reads better.

    - Consecutive narration/system/action segments (same actor) in a paragraph join.
    - Dialogue split by a speech tag mid-sentence (`"Hi," he said, "come in."`)
      becomes one bubble followed by the tag (rendered as a caption).
    A block's confidence is the lowest of its segments'.
    """
    blocks: list[Block] = []
    para_start = 0
    for seg in segments:
        d = decisions.get(seg.id) or Decision(type=BlockType.NARRATION)
        btype, speaker = d.type, d.speaker
        if btype in (BlockType.DIALOGUE, BlockType.THOUGHT):
            text = strip_marks(seg.text, seg.kind)
        elif btype == BlockType.SFX:
            text = seg.text.strip().strip("*")
        else:
            text = seg.text if seg.kind != SegmentKind.BRACKET else seg.text.strip()
        if not text:
            continue

        if blocks and blocks[-1].para == seg.para:
            prev = blocks[-1]
            if btype in _MERGEABLE and prev.type == btype and prev.speaker == speaker:
                prev.text = f"{prev.text} {text}"
                prev.seg.append(seg.id)
                prev.conf = min(prev.conf, d.conf)
                continue
            if (btype in (BlockType.DIALOGUE, BlockType.THOUGHT) and prev.type == BlockType.TAG
                    and prev.text.rstrip().endswith((",", "—", "–", "-")) and len(blocks) - para_start >= 2):
                bubble = blocks[-2]
                if bubble.para == seg.para and bubble.type == btype and bubble.speaker == speaker:
                    bubble.text = f"{bubble.text} {text}"
                    bubble.seg.append(seg.id)
                    bubble.conf = min(bubble.conf, d.conf)
                    bubble.tone = bubble.tone or d.tone
                    continue
            if btype == BlockType.TAG and prev.type == BlockType.TAG:
                prev.text = f"{prev.text} {text}"
                prev.seg.append(seg.id)
                continue
        else:
            para_start = len(blocks)
        blocks.append(Block(type=btype, text=text, speaker=speaker, tone=d.tone, conf=d.conf, tier=d.tier,
                            para=seg.para, seg=[seg.id]))

    for i, b in enumerate(blocks):  # a tag with no adjacent bubble is just narration
        if b.type == BlockType.TAG:
            near = [blocks[j] for j in (i - 1, i + 1) if 0 <= j < len(blocks) and blocks[j].para == b.para]
            if not any(n.type in (BlockType.DIALOGUE, BlockType.THOUGHT) for n in near):
                b.type = BlockType.NARRATION
    return blocks


def coverage(segments: list[Segment], blocks: list[Block]) -> float:
    if not segments:
        return 1.0
    seen = {i for b in blocks for i in b.seg}
    return len(seen & {s.id for s in segments}) / len(segments)
