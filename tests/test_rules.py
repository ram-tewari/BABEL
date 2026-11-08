"""Tier 0/1: the deterministic converter and the memory-aware resolver."""

from babel.memory.akashic import Akashic
from babel.models import BlockType, Tier
from babel.scenario.assemble import assemble, coverage
from babel.scenario.convert import convert, is_speech_tag, looks_like_sfx, tag_speaker, tone_of
from babel.scenario.resolve import Resolver, is_first_person, title_gender
from babel.scenario.segment import segment_text


def run(store, text, pov=None, genders=None):
    nid = store.create_novel("t", [("c", text, "h")])
    ak = Akashic(store, nid)
    if pov:
        eid = ak.create(pov)
        ak.set_alias(eid, "I")
        ak.set_pov(eid)
    for name, g in (genders or {}).items():
        ak.create(name, gender=g)
    segs = segment_text(text)
    decisions, paras = convert(segs)
    Resolver(ak, is_first_person(segs)).run(segs, decisions, paras)
    return segs, decisions, assemble(segs, decisions)


def spoken(blocks):
    return [(b.text, b.speaker) for b in blocks if b.type in (BlockType.DIALOGUE, BlockType.THOUGHT)]


def test_patterns():
    assert tag_speaker("Tobin said, without looking up") == "Tobin"
    assert tag_speaker("asked Old Harrow") == "Old Harrow"
    assert tag_speaker("he said") is None
    assert is_speech_tag("she said slowly,")
    assert looks_like_sfx("CRASH!") and looks_like_sfx("Knock! Knock!") and looks_like_sfx("Skrrrrk.")
    assert not looks_like_sfx("He ran.") and not looks_like_sfx("OK")
    assert tone_of("she whispered", '"Run."') == "whisper"
    assert tone_of("he said", '"GET OUT NOW!!"') == "shout"
    assert title_gender("Mr. Okafor") == "m" and title_gender("Lady Audrey") == "f" and title_gender("Klein") is None


def test_types_and_coverage(store, sample_text):
    segs, decisions, blocks = run(store, sample_text.split("\n", 1)[1])
    assert coverage(segs, blocks) == 1.0
    kinds = {b.text[:12]: b.type for b in blocks}
    assert kinds["CRASH!"] == BlockType.SFX
    assert kinds["[Quest Updat"] == BlockType.SYSTEM
    assert kinds["* * *"] == BlockType.BREAK
    assert kinds["Tobin shook "] == BlockType.ACTION


def test_sample_attribution(store, sample_text):
    _, _, blocks = run(store, sample_text.split("\n", 1)[1])
    who = dict(spoken(blocks))
    assert who["You're late,"] == "Tobin"
    assert who["Not yet. Old Harrow says the bridge road flooded."] == "Tobin"
    assert who["He's hiding something,"] == "Mira"
    assert who["Tobin, do you see that?"] == "Mira"  # addressing Tobin → not Tobin
    assert who["See what?"] == "Tobin"


def test_confidence_and_candidates(store):
    _, decisions, _ = run(store, '"Run," Kai said.\n\n"Where?"\n\n"Anywhere!"')
    tagged, bare1, bare2 = [d for d in decisions.values() if d.type == BlockType.DIALOGUE]
    assert tagged.conf >= 0.95 and tagged.tier == Tier.RULE
    assert bare1.conf < 0.9  # untagged → will be asked about
    assert "Kai" in bare1.candidates


def test_vocative_name_only_line(store):
    text = ('"Level forty," Suki said.\n\n"Thirty-three," Ren said.\n\n"Oh, that changes everything."\n\n'
            'Something moved.\n\n"Ren."\n\n"I hear it."')
    _, _, blocks = run(store, text)
    who = dict(spoken(blocks))
    assert who["Ren."] == "Suki"
    assert who["I hear it."] == "Ren"


def test_pronoun_tag_uses_gender(store):
    text = '"Hello," Mira said.\n\n"Hi," Tobin said.\n\n"Took you long enough," she said.'
    _, _, blocks = run(store, text, genders={"Mira": "f", "Tobin": "m"})
    assert dict(spoken(blocks))["Took you long enough,"] == "Mira"


def test_first_person_narrator_joins_conversations(store):
    text = ('I clocked in at eleven. I had eight hours of mopping ahead, and I knew it.\n\n'
            'Dez was at the desk. "You look terrible."\n\n"Thank you. I worked on it."')
    _, _, blocks = run(store, text, pov="Sam")
    assert dict(spoken(blocks))["Thank you. I worked on it."] == "Sam"


def test_newcomer_speaks(store):
    text = '"Fine," Dez said.\n\nThe elevator dinged. Mr. Okafor stepped out.\n\n"Ah. You\'re here."'
    _, _, blocks = run(store, text)
    assert dict(spoken(blocks))["Ah. You're here."] == "Mr. Okafor"


def test_continued_speech_across_paragraphs(store):
    text = '"Then mend it," said Ilse. "By morning.\n\n"And Pell stays with me."'
    _, _, blocks = run(store, text)
    assert dict(spoken(blocks))["And Pell stays with me."] == "Ilse"


def test_inline_quotes_and_italics_stay_prose(store):
    _, _, blocks = run(store, 'He called it a "genius" move and was *very* tired.')
    assert [b.type for b in blocks] == [BlockType.NARRATION]
