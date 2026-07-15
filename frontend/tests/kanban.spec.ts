import { expect, test, type Page } from "@playwright/test";
import { initialData } from "../src/lib/kanban";

let consoleErrors: string[];

test.beforeEach(async ({ page }) => {
  consoleErrors = [];
  page.on("console", (message) => {
    if (
      message.type() === "error" &&
      !message.text().includes("status of 401")
    ) {
      consoleErrors.push(message.text());
    }
  });
});

test.afterEach(() => {
  expect(consoleErrors).toEqual([]);
});

const signIn = async (page: Page) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
};

const deleteCardsByTitle = async (page: Page, titles: string[]) => {
  await page.evaluate(async (cardTitles) => {
    const response = await fetch("/api/board");
    if (!response.ok) return;
    const board = (await response.json()) as {
      cards: Record<string, { id: string; title: string }>;
    };
    for (const card of Object.values(board.cards)) {
      if (cardTitles.includes(card.title)) {
        await fetch(`/api/cards/${card.id}`, { method: "DELETE" });
      }
    }
  }, titles);
};

test("requires sign in", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Kanban Studio" })
  ).not.toBeVisible();
});

test("rejects invalid credentials", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("wrong");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(
    page.getByText("Invalid username or password", { exact: true })
  ).toBeVisible();
});

test("persists login across a browser restart", async ({
  browser,
  context,
  page,
}) => {
  await signIn(page);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();

  const storageState = await context.storageState();
  const sessionCookie = storageState.cookies.find(
    (cookie) => cookie.name === "pm_session"
  );
  expect(sessionCookie?.expires).toBeGreaterThan(Date.now() / 1000);

  const restartedContext = await browser.newContext({ storageState });
  const restartedPage = await restartedContext.newPage();
  restartedPage.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await restartedPage.goto("/");
  await expect(
    restartedPage.getByRole("heading", { name: "Kanban Studio" })
  ).toBeVisible();
  await restartedContext.close();
});

test("loads the persistent kanban board", async ({ page }) => {
  await signIn(page);

  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
  await expect(page.locator('[data-testid^="card-"]')).toHaveCount(8);
});

test("persists card creation, editing, and deletion", async ({ page }) => {
  await signIn(page);
  const suffix = Date.now().toString();
  const originalTitle = `Playwright card ${suffix}`;
  const editedTitle = `Edited card ${suffix}`;
  const firstColumn = page.locator('[data-testid^="column-"]').first();

  try {
    await firstColumn.getByRole("button", { name: /add a card/i }).click();
    await firstColumn.getByPlaceholder("Card title").fill(originalTitle);
    await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
    await firstColumn.getByRole("button", { name: /add card/i }).click();
    await expect(firstColumn.getByText(originalTitle, { exact: true })).toBeVisible();

    await page.reload();
    const persistedCard = page
      .locator('[data-testid^="card-"]')
      .filter({ hasText: originalTitle });
    await expect(persistedCard).toBeVisible();
    const cardTestId = await persistedCard.getAttribute("data-testid");
    expect(cardTestId).not.toBeNull();
    const stableCard = page.locator(`[data-testid="${cardTestId}"]`);
    await stableCard.getByRole("button", { name: `Edit ${originalTitle}` }).click();
    await stableCard.getByLabel(`Edit title for ${originalTitle}`).fill(editedTitle);
    await stableCard
      .getByLabel(`Edit details for ${originalTitle}`)
      .fill("Persisted edited details.");
    await stableCard.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText(editedTitle, { exact: true })).toBeVisible();

    await page.reload();
    const editedCard = page
      .locator('[data-testid^="card-"]')
      .filter({ hasText: editedTitle });
    await expect(editedCard.getByText("Persisted edited details.")).toBeVisible();
    await editedCard.getByRole("button", { name: `Delete ${editedTitle}` }).click();
    await expect(editedCard).toHaveCount(0);

    await page.reload();
    await expect(page.getByText(editedTitle, { exact: true })).toHaveCount(0);
  } finally {
    await deleteCardsByTitle(page, [originalTitle, editedTitle]);
  }
});

test("persists and restores a column rename", async ({ page }) => {
  await signIn(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  const title = firstColumn.getByLabel("Column title");
  const originalTitle = await title.inputValue();
  const renamedTitle = `Ideas ${Date.now()}`;

  try {
    await title.fill(renamedTitle);
    await title.press("Enter");
    await expect(page.getByText(renamedTitle, { exact: true })).toBeVisible();

    await page.reload();
    await expect(
      page.locator('[data-testid^="column-"]').first().getByLabel("Column title")
    ).toHaveValue(renamedTitle);
  } finally {
    const currentTitle = page
      .locator('[data-testid^="column-"]')
      .first()
      .getByLabel("Column title");
    await currentTitle.fill(originalTitle);
    await currentTitle.press("Enter");
    await expect(currentTitle).toHaveValue(originalTitle);
  }
});

test("persists a card move and restores its original position", async ({ page }) => {
  await signIn(page);
  const sourceColumn = page.locator('[data-testid^="column-"]').first();
  const targetColumn = page.locator('[data-testid^="column-"]').nth(3);
  const card = sourceColumn.locator('[data-testid^="card-"]').first();
  const cardTestId = await card.getAttribute("data-testid");
  const sourceTestId = await sourceColumn.getAttribute("data-testid");
  const targetTestId = await targetColumn.getAttribute("data-testid");
  if (!cardTestId || !sourceTestId || !targetTestId) {
    throw new Error("Unable to resolve persistent board IDs.");
  }
  const cardId = cardTestId.replace("card-", "");
  const sourceColumnId = sourceTestId.replace("column-", "");
  const targetCard = page.getByTestId(cardTestId);
  const dragHandle = card.getByRole("button", { name: /^Drag / });
  const handleBox = await dragHandle.boundingBox();
  const targetBox = await targetColumn.boundingBox();
  if (!handleBox || !targetBox) throw new Error("Unable to resolve drag coordinates.");

  try {
    await page.mouse.move(
      handleBox.x + handleBox.width / 2,
      handleBox.y + handleBox.height / 2
    );
    await page.mouse.down();
    await page.mouse.move(
      targetBox.x + targetBox.width / 2,
      targetBox.y + 120,
      { steps: 12 }
    );
    await page.mouse.up();
    await expect(targetColumn.getByTestId(cardTestId)).toBeVisible();

    await page.reload();
    await expect(page.getByTestId(targetTestId).getByTestId(cardTestId)).toBeVisible();
  } finally {
    await page.evaluate(
      async ({ movedCardId, originalColumnId }) => {
        await fetch(`/api/cards/${movedCardId}/move`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ column_id: Number(originalColumnId), position: 0 }),
        });
      },
      { movedCardId: cardId, originalColumnId: sourceColumnId }
    );
  }
  await page.reload();
  await expect(page.getByTestId(sourceTestId).getByTestId(cardTestId)).toBeVisible();
  await expect(targetCard).toHaveCount(1);
});

test("loads chat history and refreshes the board from an AI response", async ({
  page,
}) => {
  const chatBoard = structuredClone(initialData);
  chatBoard.cards["card-ai"] = {
    id: "card-ai",
    title: "AI-created launch checklist",
    details: "Added by the mocked assistant response.",
  };
  chatBoard.columns[0].cardIds.push("card-ai");
  let sentMessage: unknown;

  await page.route("**/api/chat", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "1",
            role: "assistant",
            content: "How can I help with the board?",
            created_at: "2026-07-15 12:00:00",
          },
        ]),
      });
      return;
    }

    sentMessage = route.request().postDataJSON();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        user_message: {
          id: "2",
          role: "user",
          content: "Create a launch checklist in Backlog",
          created_at: "2026-07-15 12:00:59",
        },
        message: {
          id: "3",
          role: "assistant",
          content: "I created the launch checklist in Backlog.",
          created_at: "2026-07-15 12:01:00",
        },
        board: chatBoard,
      }),
    });
  });

  await signIn(page);
  await expect(page.getByRole("heading", { name: "Board assistant" })).toBeVisible();
  await expect(page.getByText("How can I help with the board?")).toBeVisible();

  await page
    .getByLabel("Message the board assistant")
    .fill("Create a launch checklist in Backlog");
  await page.getByRole("button", { name: "Send message" }).click();

  await expect(
    page.getByText("I created the launch checklist in Backlog.")
  ).toBeVisible();
  await expect(page.getByText("AI-created launch checklist")).toBeVisible();
  expect(sentMessage).toEqual({ message: "Create a launch checklist in Backlog" });
});

test("logs out and protects the board", async ({ page }) => {
  await signIn(page);

  await page.getByRole("button", { name: "Log out" }).click();

  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
});
