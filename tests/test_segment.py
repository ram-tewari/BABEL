import random
import re

from babel.models import SegmentKind
from babel.transform.segment import chunk_segments, segment_text, split_paragraphs, strip_marks


def kinds(text):
    return [(s.kind.value, s.text) for s in segment_text(text)]


def test_quote_and_tag_split():
    assert kinds('"Hello," he said, "come in."') == [
        ("quote", '"Hello,"'), ("prose", "he said,"), ("quote", '"come in."')]


def test_curly_and_cjk_quotes():
    assert [k for k, _ in kinds("“Run!” she cried.")] == ["quote", "prose"]
    assert [k for k, _ in kinds("「走吧」他说。")] == ["quote", "prose"]


def test_emphasis_bracket_and_break():
    segs = kinds("*Not again,* he thought.\n\n[Skill Acquired: Spirit Vision]\n\n* * *\n\nMorning came.")
    assert segs == [("emphasis", "*Not again,*"), ("prose", "he thought."),
                    ("bracket", "[Skill Acquired: Spirit Vision]"), ("break", "* * *"), ("prose", "Morning came.")]


def test_unclosed_quote_runs_to_paragraph_end():
    segs = segment_text('"This goes on\n\n"and on."')
    assert [s.kind for s in segs] == [SegmentKind.QUOTE, SegmentKind.QUOTE]
    assert segs[0].para == 0 and segs[1].para == 1


def test_punctuation_fragments_attach_to_previous():
    segs = kinds('"Wait"—')
    assert segs == [("quote", '"Wait"—')]


def test_lone_asterisk_is_not_emphasis():
    assert kinds("5 * 3 = 15") == [("prose", "5 * 3 = 15")]


def test_strip_marks():
    assert strip_marks('"Hello,"', SegmentKind.QUOTE) == "Hello,"
    assert strip_marks("“Run!”", SegmentKind.QUOTE) == "Run!"
    assert strip_marks("*hmm*", SegmentKind.EMPHASIS) == "hmm"


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def test_segmentation_is_lossless_on_random_text():
    rng = random.Random(7)
    pieces = ['"', "“", "”", "*", "[", "]", "word", "Name", ",", ".", " ", " ", "\n", "\n\n", "!", "—", "「", "」"]
    for _ in range(400):
        text = "".join(rng.choice(pieces) for _ in range(rng.randint(1, 60)))
        segs = segment_text(text)
        joined = "".join(s.text for s in segs)
        expected = "".join(p for p in split_paragraphs(text))
        assert _squash(joined) == _squash(expected), text
        assert [s.id for s in segs] == list(range(len(segs)))


def test_chunking_respects_paragraphs():
    text = "\n\n".join(f'"Line {i}," Bob said. More words here.' for i in range(200))
    segs = segment_text(text)
    chunks = chunk_segments(segs, max_tokens=200)
    assert len(chunks) > 3
    assert sum(len(c) for c in chunks) == len(segs)
    for a, b in zip(chunks, chunks[1:], strict=False):
        assert a[-1].para != b[0].para
