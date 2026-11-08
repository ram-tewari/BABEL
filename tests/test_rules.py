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


def test_descriptive_tags():
    from babel.scenario.convert import tag_description

    assert tag_description("the circus fortune-teller said in a muted voice") == "Circus fortune-teller"
    assert tag_description("said the old guard") == "Old guard"
    assert tag_description("then curled her lips to reveal a smile and said,") is None
    assert tag_description("the voice said") is None


# ── patterns found by the real-text QC set (texts here are original paraphrases) ──

def test_lead_in_paragraph_attributes_next_quote(store):
    text = ('"Fine," Tobin said.\n\n"Then go."\n\nAs Mira reached the door, Old Harrow suddenly called out to her.\n\n'
            '"Wait. I forgot something."')
    _, _, blocks = run(store, text)
    assert dict(spoken(blocks))["Wait. I forgot something."] == "Old Harrow"


def test_pronoun_speech_verb_before_quote_uses_salience(store):
    text = ('"Me too," Suki said, laughing.\n\n'
            'She glanced left and right, then lowered her voice and said, "The courier is back."')
    _, _, blocks = run(store, text, genders={"Suki": "f", "Ren": "m"})
    assert dict(spoken(blocks))["The courier is back."] == "Suki"


def test_pronoun_with_two_men_prefers_antecedent_in_sentence(store):
    text = ('"Bring the ledger," Aldric said.\n\n"Yes."\n\n'
            '*Another errand.* Just as Pell was sighing over it, he answered, "I will."')
    _, _, blocks = run(store, text, genders={"Aldric": "m", "Pell": "m"})
    assert dict(spoken(blocks))["I will."] == "Pell"


def test_monologue_survives_beat_paragraphs(store):
    text = ('"Watch," Dez said. "This is one."\n\n"Okay," Sam said.\n\nThen, she raised a second finger.\n\n'
            '"This is two."')
    _, _, blocks = run(store, text, genders={"Dez": "f", "Sam": "m"})
    assert dict(spoken(blocks))["This is two."] == "Dez"


def test_address_words_only_count_as_vocatives(store):
    text = ('"Eat," Tobin said to Mira.\n\n"Praise the Lady." Mira finally took a bite.')
    _, _, blocks = run(store, text, genders={"Tobin": "m", "Mira": "f"})
    assert dict(spoken(blocks))["Praise the Lady."] == "Mira"


def test_untagged_thoughts_go_to_the_viewpoint_character(store):
    text = ('Ren walked in. Ren looked around. Ren sat down beside Suki, who smiled at Ren.\n\n*Too quiet.*\n\n'
            '"Hi," Suki said.\n\nRen nodded.')
    _, _, blocks = run(store, text)
    assert dict(spoken(blocks))["Too quiet."] == "Ren"


def test_descriptive_tags_need_a_speech_verb_not_a_noun():
    from babel.scenario.convert import tag_description
    assert tag_description("Mira handed over the four silver notes to Tobin.") is None
    assert tag_description("the old guard said") == "Old guard"


def test_italic_sound_words_and_options():
    from babel.models import Segment, SegmentKind
    from babel.scenario.ask import kind_ok, type_options
    assert looks_like_sfx("*Gulp.*") and looks_like_sfx("Groan!")
    assert "spoken aloud" not in type_options(SegmentKind.EMPHASIS)
    assert "spoken aloud" in type_options(SegmentKind.QUOTE)
    seg = Segment(id=0, para=0, kind=SegmentKind.EMPHASIS, text="Odd.")
    assert not kind_ok(seg, BlockType.DIALOGUE)
