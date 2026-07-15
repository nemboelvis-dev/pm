import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";
import Home from "@/app/page";
import {
  ApiError,
  getBoard,
  getSession,
  login,
  logout,
} from "@/lib/api";
import { initialData } from "@/lib/kanban";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    getBoard: vi.fn(),
    getSession: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  };
});

const getSessionMock = vi.mocked(getSession);
const getBoardMock = vi.mocked(getBoard);
const loginMock = vi.mocked(login);
const logoutMock = vi.mocked(logout);

describe("Home authentication", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    getBoardMock.mockResolvedValue(structuredClone(initialData));
  });

  it("shows the login form when there is no session", async () => {
    getSessionMock.mockRejectedValue(
      new ApiError("Authentication required", 401)
    );

    render(<Home />);

    expect(
      await screen.findByRole("heading", { name: "Welcome back" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Kanban Studio" })
    ).not.toBeInTheDocument();
  });

  it("shows invalid credential errors", async () => {
    getSessionMock.mockRejectedValue(
      new ApiError("Authentication required", 401)
    );
    loginMock.mockRejectedValue(
      new ApiError("Invalid username or password", 401)
    );
    render(<Home />);
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Username"), "user");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid username or password"
    );
  });

  it("renders the board for a session and logs out", async () => {
    getSessionMock.mockResolvedValue({ username: "user" });
    logoutMock.mockResolvedValue(undefined);
    render(<Home />);
    const user = userEvent.setup();

    expect(
      await screen.findByRole("heading", { name: "Kanban Studio" })
    ).toBeInTheDocument();
    expect(screen.getByText("Signed in as user")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Log out" }));

    expect(
      await screen.findByRole("heading", { name: "Welcome back" })
    ).toBeInTheDocument();
    expect(logoutMock).toHaveBeenCalledOnce();
  });
});
