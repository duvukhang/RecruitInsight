import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
const mockApi = vi.hoisted(() => vi.fn());
vi.mock("./api", () => ({
  api: mockApi,
  remember: vi.fn(),
  clearSession: vi.fn(),
  csrfHeaders: () => ({}),
}));
beforeEach(() => {
  cleanup();
  mockApi.mockReset();
  mockApi.mockRejectedValue(Error("Phiên hết hạn"));
});
describe("authentication UI", () => {
  it("recovers to login after refresh fails and displays login failure", async () => {
    render(
      <MemoryRouter>
        <QueryClientProvider client={new QueryClient()}>
          <App />
        </QueryClientProvider>
      </MemoryRouter>,
    );
    await screen.findByRole("button", { name: /^Đăng nhập$/ });
    fireEvent.change(screen.getByLabelText("Tên đăng nhập"), {
      target: { value: "wrong-user" },
    });
    fireEvent.change(screen.getByLabelText("Mật khẩu"), {
      target: { value: "wrong-password" },
    });
    mockApi.mockRejectedValueOnce(
      Error("Tên đăng nhập hoặc mật khẩu không đúng."),
    );
    fireEvent.submit(
      screen.getByRole("button", { name: /^Đăng nhập$/ }).closest("form")!,
    );
    expect((await screen.findByRole("alert")).textContent).toContain(
      "mật khẩu không đúng",
    );
    await waitFor(() =>
      expect(
        (
          screen.getByRole("button", {
            name: /^Đăng nhập$/,
          }) as HTMLButtonElement
        ).disabled,
      ).toBe(false),
    );
  });
});
