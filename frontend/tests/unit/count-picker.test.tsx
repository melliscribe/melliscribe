// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/** FR-004, FR-006k: the gloved count picker. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "../../src/i18n";
import { CountPicker } from "../../src/review/CountPicker";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

function render(initial: number | null, onChoose = vi.fn()) {
  act(() =>
    root.render(
      <I18nProvider language="en">
        <CountPicker initial={initial} onChoose={onChoose} onCancel={() => {}} />
      </I18nProvider>,
    ),
  );
  return onChoose;
}

function button(label: string): HTMLButtonElement {
  const found = [...container.querySelectorAll("button")].find((b) => b.textContent === label);
  if (!found) throw new Error(`no button ${label}`);
  return found;
}

const shown = () => container.querySelector("[data-testid=count-value]")?.textContent;

describe("CountPicker", () => {
  it("offers no number for a flagged count, and cannot save nothing", () => {
    render(null);
    expect(shown()).toBe("—");
    expect(button("Save").disabled).toBe(true);
  });

  it("sets a whole number in one tap and adds half frames", () => {
    const onChoose = render(null);
    act(() => button("5").click());
    act(() => button("+ ½ frame").click());
    expect(shown()).toBe("5.5 frames");
    act(() => button("Save").click());
    expect(onChoose).toHaveBeenCalledWith(5.5);
  });

  it("never goes below zero", () => {
    render(0);
    expect(button("− ½ frame").disabled).toBe(true);
  });

  it("never goes above the limit", () => {
    render(40);
    expect(button("+ ½ frame").disabled).toBe(true);
  });

  it("confirms not observed as null", () => {
    const onChoose = render(3);
    act(() => button("Not observed").click());
    expect(onChoose).toHaveBeenCalledWith(null);
  });
});
