from babel.models import BlockType
from babel.transform.assemble import assemble, coverage
from babel.transform.heuristic import (
    find_tag_speaker,
    is_speech_tag,
    label_segments,
    looks_like_sfx,
)
from babel.transform.segment import segment_text


def test_tag_speaker_patterns():
    assert find_tag_speaker("Tobin said, without looking up") == "Tobin"
    assert find_tag_speaker("asked Old Harrow") == "Old Harrow"
    assert find_tag_speaker("he said") is None
    assert is_speech_tag("she said slowly,")
    assert not is_speech_tag("The rain fell over the city for the third night in a row, drowning the lanterns.")


def test_sfx_detection():
    assert looks_like_sfx("CRASH!")
    assert looks_like_sfx("Boooom")
    assert not looks_like_sfx("He ran.")
    assert not looks_like_sfx("OK")


def test_sample_chapter_attribution(sample_text):
    body = sample_text.split("\n", 1)[1]
    segs = segment_text(body)
    blocks = assemble(segs, label_segments(segs))
    assert coverage(segs, blocks) == 1.0
    spoken = [(b.type, b.speaker, b.text) for b in blocks if b.type in (BlockType.DIALOGUE, BlockType.THOUGHT)]
    assert spoken[0] == (BlockType.DIALOGUE, "Tobin", "You're late,")
    assert spoken[1][1] == "Mira"
    by_text = {t: s for _, s, t in spoken}
    assert by_text["Not yet. Old Harrow says the bridge road flooded."] == "Tobin"
    assert by_text["See what?"] == "Tobin"
    thoughts = [b for b in blocks if b.type == BlockType.THOUGHT]
    assert thoughts and all(b.speaker == "Mira" for b in thoughts)
    assert any(b.type == BlockType.SYSTEM for b in blocks)
    assert any(b.type == BlockType.SFX and b.text == "CRASH!" for b in blocks)
    assert any(b.type == BlockType.BREAK for b in blocks)


def test_interrupted_sentence_merges_into_one_bubble():
    segs = segment_text('"Tobin," she said slowly, "do you see that?"')
    labels = {s.id: ((BlockType.DIALOGUE, "Mira") if s.kind.value == "quote" else (BlockType.TAG, None)) for s in segs}
    blocks = assemble(segs, labels)
    assert [(b.type, b.text) for b in blocks] == [
        (BlockType.DIALOGUE, "Tobin, do you see that?"), (BlockType.TAG, "she said slowly,")]
    assert sorted(i for b in blocks for i in b.seg) == [0, 1, 2]


def test_full_sentence_tag_does_not_reorder():
    segs = segment_text('"I\'m early," Mira replied. She sat. "Did he come?"')
    labels = {s.id: ((BlockType.DIALOGUE, "Mira") if s.kind.value == "quote" else (BlockType.TAG, None)) for s in segs}
    blocks = assemble(segs, labels)
    assert [b.text for b in blocks] == ["I'm early,", "Mira replied. She sat.", "Did he come?"]
