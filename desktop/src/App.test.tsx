import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("App", () => {
  it("renders the empty drop-zone state on first load", async () => {
    render(<App />);
    expect(await screen.findByText("Выберите аудиофайл встречи")).toBeInTheDocument();
  });
});
