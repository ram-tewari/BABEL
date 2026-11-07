import { render, screen } from "@testing-library/react";
import { Scenario } from "./Scenario";
import type { Block, Character } from "../lib/api";

const mira: Character = { id: 1, name: "Mira Vell", note: null, color: "slot:0", side: "right", lines: 3, is_pov: true, first_idx: 0 };
const tobin: Character = { id: 2, name: "Tobin", note: null, color: "slot:1", side: "left", lines: 2, is_pov: false, first_idx: 0 };
const b = (type: Block["type"], text: string, character_id: number | null = null, i = 0): Block => ({
  type, text, speaker: null, character_id, para: i, seg: [i], edited: false,
});
const blocks: Block[] = [
  b("narration", "The market opened at *dusk*.", null, 0),
  b("dialogue", "You're late,", 2, 1),
  b("tag", "Tobin said.", null, 2),
  b("dialogue", "I'm early.", 1, 3),
  b("dialogue", "For tomorrow.", 1, 4),
  b("system", "[Quest Updated]", null, 5),
  b("narration", "<img src=x onerror=alert(1)>", null, 6),
];
const chars = new Map([[1, mira], [2, tobin]]);

function setup(showTags = true) {
  return render(<Scenario blocks={blocks} characters={chars} showTags={showTags} showAvatars editing={false} onEdit={() => {}} onCharacter={() => {}} />);
}

test("renders bubbles with names, grouping consecutive lines", () => {
  setup();
  expect(screen.getByText("You're late,")).toBeInTheDocument();
  // Mira speaks twice in a row: name shown once
  expect(screen.getAllByText("Mira Vell")).toHaveLength(1);
  expect(screen.getByText("dusk").tagName).toBe("EM");
  expect(screen.getByText("[Quest Updated]")).toBeInTheDocument();
});

test("speech tags can be hidden", () => {
  setup(false);
  expect(screen.queryByText("Tobin said.")).not.toBeInTheDocument();
});

test("text is never interpreted as HTML", () => {
  const { container } = setup();
  expect(container.querySelector("img")).toBeNull();
  expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
});
