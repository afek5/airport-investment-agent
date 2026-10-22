// Answer markdown tables render at full height: no inner scroll box that could hide the top rows.
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MessageResponse } from "@/components/ai-elements/message";

const ROWS = Array.from({ length: 12 }, (_, i) => `| ${i + 1} | AP${i + 1} | ${(80 - i).toFixed(1)} |`).join("\n");
const TABLE = `| Rank | Airport | Score |\n|---|---|---|\n${ROWS}\n`;

describe("MessageResponse tables", () => {
  it.each([false, true])("has no max-height box (isAnimating=%s)", (isAnimating) => {
    const { container } = render(<MessageResponse isAnimating={isAnimating}>{TABLE}</MessageResponse>);
    const table = container.querySelector('[data-streamdown="table"]');
    expect(table).not.toBeNull();
    expect(table!.textContent).toContain("AP1");
    let box = table!.parentElement;
    while (box && box !== container) {
      expect((box as HTMLElement).style.maxHeight).toBe("");
      box = box.parentElement;
    }
  });
});
