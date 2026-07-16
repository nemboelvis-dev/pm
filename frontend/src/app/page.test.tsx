import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";
import Home from "@/app/page";
import {
  ApiError,
  getBoard,
  getSession,
  listBoards,
  login,
  logout,
  register,
} from "@/lib/api";
import { initialData } from "@/lib/kanban";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    getBoard: vi.fn(),
    getSession: vi.fn(),
    listBoards: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    register: vi.fn(),
  };
});

const getSessionMock = vi.mocked(getSession);
const getBoardMock = vi.mocked(getBoard);
const listBoardsMock = vi.mocked(listBoards);
const loginMock = vi.mocked(login);
const logoutMock = vi.mocked(logout);
const registerMock = vi.mocked(register);

describe("Home authentication", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    getBoardMock.mockResolvedValue(structuredClone(initialData));
    listBoardsMock.mockResolvedValue([
      {
        id: initialData.id,
        title: initialData.title,
        created_at: "2026-07-01 00:00:00",
        updated_at: "2026-07-01 00:00:00",
      },
    ]);
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
      await screen.findByDisplayValue("Kanban Studio")
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Kanban Studio" })
    ).not.toBeInTheDocument();
    expect(screen.getByText("Signed in as user")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Log out" }));

    expect(
      await screen.findByRole("heading", { name: "Welcome back" })
    ).toBeInTheDocument();
    expect(logoutMock).toHaveBeenCalledOnce();
  });

  it("switches to the register form and creates an account", async () => {
    getSessionMock.mockRejectedValue(
      new ApiError("Authentication required", 401)
    );
    registerMock.mockResolvedValue({ username: "new-user" });
    render(<Home />);
    const user = userEvent.setup();

    await user.click(
      await screen.findByRole("button", { name: "Create an account" })
    );
    expect(
      screen.getByRole("heading", { name: "Create your account" })
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText("Username"), "new-user");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(registerMock).toHaveBeenCalledWith("new-user", "correct-horse");
    expect(
      await screen.findByDisplayValue("Kanban Studio")
    ).toBeInTheDocument();
  });

  it("shows registration errors and can switch back to sign in", async () => {
    getSessionMock.mockRejectedValue(
      new ApiError("Authentication required", 401)
    );
    registerMock.mockRejectedValue(
      new ApiError("Username is already taken", 409)
    );
    render(<Home />);
    const user = userEvent.setup();

    await user.click(
      await screen.findByRole("button", { name: "Create an account" })
    );
    await user.type(screen.getByLabelText("Username"), "user");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Username is already taken"
    );

    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(
      screen.getByRole("heading", { name: "Welcome back" })
    ).toBeInTheDocument();
  });
});
