import type { On } from "claude-code";
import { expect, test } from "claude-code/testing";

import type { InterviewProgress } from "../types";

const INTERVIEW_ID = "7d8f0c52-3a8e-4f0b-9a52-0f1c2b3d4e5f";
const TURN_TOOL = "mcp__prd-chat__record_interview_turn" as const;

const PROGRESS: InterviewProgress = {
    interviewId: INTERVIEW_ID,
    problemSummary: "Plan van routes",
    currentSectionId: "hard",
    fullCoverage: 3,
    sections: [
        {
            id: "assign",
            label: "Deliveries",
            question: "Which stops go on which van?",
            coverage: 3,
            captured: "Stops per van",
        },
        {
            id: "hard",
            label: "Driver rules",
            question: "What may a driver never do?",
            coverage: 1,
            captured: "No overtime",
        },
        {
            id: "soft",
            label: "Goals",
            question: "What makes a plan better?",
            coverage: 0,
            captured: "",
        },
    ],
};

const PANE = {
    plugin: "timefold-prd",
    component: "Pane",
    requestId: "prd-chat",
    props: {
        title: "Requirements coverage",
        isFocused: false,
        bodyColumns: 60,
        placement: "dock",
        scroll: { offset: 0, bodyRows: 30 },
        view: {},
    },
} as const;

test("a recorded turn fills the pane with every section and its status", async ($, on) => {
    const calls: {
        server: string;
        tool: string;
        args: Record<string, unknown>;
    }[] = [];

    on("tool.call", { tool: TURN_TOOL }, () => ({
        result: [],
        text: "Recorded.",
    }));
    on("mcp.call", ($, e) => {
        calls.push(e);

        return {
            value: { content: [], isError: false, structuredContent: PROGRESS },
        };
    });
    on("ui.open", () => ({ value: { isPlaced: true } }));

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });

    expect(calls).toEqual([
        {
            server: "prd-chat",
            tool: "get_interview_progress",
            args: { interviewId: INTERVIEW_ID },
        },
    ]);
    for (const surface of ["terminal", "desktop"] as const) {
        const ui = await $.ui.mount({ ...PANE, surface });

        expect((await ui.find({ type: "Text", text: "67%" }))?.props.color).toBe(
            "yellow",
        );
        expect(
            (await ui.find({ type: "Text", text: "#PRD-7D8F0C" }))?.type,
        ).toBe("Text");
        expect((await ui.find({ key: "toggle-assign" }))?.props.label).toBe(
            "▸ Deliveries",
        );
        expect(
            (await ui.findAll({ type: "Text", text: "◀ now" })).map(
                (marker) => marker.props.color,
            ),
        ).toEqual(["cyan"]);
        expect(
            await ui.find({ type: "Text", text: "No overtime" }),
        ).toBeUndefined();
    }
});

test("unfolding a section shows what was captured, and its button steers the interview there", async ($, on) => {
    const submitted: string[] = [];

    on("tool.call", { tool: TURN_TOOL }, () => ({
        result: [],
        text: "Recorded.",
    }));
    on("mcp.call", () => ({
        value: { content: [], isError: false, structuredContent: PROGRESS },
    }));
    on("ui.open", () => ({ value: { isPlaced: true } }));
    on("prompt.submit", ($, e) => {
        submitted.push(e.text);

        return { text: e.text };
    });

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    await ui.press({ key: "toggle-hard" });
    expect((await ui.find({ type: "Text", text: "No overtime" }))?.type).toBe(
        "Text",
    );

    await ui.press({ key: "talk-hard" });
    expect(submitted).toEqual([
        "Let's talk about Driver rules: What may a driver never do?",
    ]);
});

test("a covered section offers no button to talk about it", async ($, on) => {
    answerTurnAndProgress(on);

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    await ui.press({ key: "toggle-assign" });
    expect(
        (await ui.find({ type: "Text", text: "Stops per van" }))?.type,
    ).toBe("Text");
    expect(await ui.find({ key: "talk-assign" })).toBeUndefined();
});

test("a failed tool call leaves the pane empty and asks the server nothing", async ($, on) => {
    let progressCalls = 0;

    on("tool.call", { tool: TURN_TOOL }, () => ({
        result: "boom",
        isError: true,
        text: "No interview",
    }));
    on("mcp.call", () => {
        progressCalls += 1;

        return {
            value: { content: [], isError: false, structuredContent: PROGRESS },
        };
    });

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    expect(progressCalls).toBe(0);
    expect((await ui.drawn()).type).toBe("Text");
});

test("starting an interview reads its id from the result and opens the pane", async ($, on) => {
    const askedFor: unknown[] = [];
    const opened: string[] = [];

    on(
        "tool.call",
        { tool: "mcp__prd-chat__start_requirements_interview" },
        () => ({
            result: [],
            text: `THE GUIDE\n\ninterviewId: ${INTERVIEW_ID}\n\nInterview ${INTERVIEW_ID} for: Plan van routes`,
        }),
    );
    on("mcp.call", ($, e) => {
        askedFor.push(e.args.interviewId);

        return {
            value: { content: [], isError: false, structuredContent: PROGRESS },
        };
    });
    on("ui.open", ($, e) => {
        opened.push(e.id);

        return { value: { isPlaced: true } };
    });

    await $.tool.call({ tool: "mcp__prd-chat__start_requirements_interview" });

    expect(askedFor).toEqual([INTERVIEW_ID]);
    expect(opened).toEqual(["prd-chat"]);
});

test("a refused progress call still returns the turn and says why in a toast", async ($, on) => {
    const toasts: string[] = [];

    on("tool.call", { tool: TURN_TOOL }, () => ({
        result: [],
        text: "Recorded.",
    }));
    on("mcp.call", () => ({
        deny: "the auto mode classifier gave no verdict",
    }));
    on("ui.toast", ($, e) => {
        toasts.push(e.text);

        return { value: undefined };
    });

    const ran = await $.tool.call({
        tool: TURN_TOOL,
        interviewId: INTERVIEW_ID,
    });

    expect(ran.text).toBe("Recorded.");
    expect(toasts).toHaveLength(1);
    expect(toasts[0]).toContain("the requirements pane was not updated");
});

test("reads the progress from a JSON text block when the result has no structuredContent", async ($, on) => {
    on("tool.call", { tool: TURN_TOOL }, () => ({
        result: [],
        text: "Recorded.",
    }));
    on("mcp.call", () => ({
        value: {
            content: [{ type: "text", text: JSON.stringify(PROGRESS) }],
            isError: false,
        },
    }));
    on("ui.open", () => ({ value: { isPlaced: true } }));

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    expect((await ui.find({ type: "Text", text: "67%" }))?.type).toBe("Text");
});

test("skips the plain-text summary block and reads the JSON block after it", async ($, on) => {
    on("tool.call", { tool: TURN_TOOL }, () => ({
        result: [],
        text: "Recorded.",
    }));
    on("mcp.call", () => ({
        value: {
            content: [
                { type: "text", text: "Interview for: Plan van routes" },
                { type: "text", text: JSON.stringify(PROGRESS) },
            ],
            isError: false,
        },
    }));
    on("ui.open", () => ({ value: { isPlaced: true } }));

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    expect((await ui.find({ type: "Text", text: "67%" }))?.type).toBe("Text");
});

test("talking about a section while a question is open answers that question instead of queuing a prompt", async ($, on) => {
    const submitted: string[] = [];
    const QUESTION = {
        question: "How many orders fit on one trip?",
        header: "Trip limit",
        multiSelect: false,
        options: [
            { label: "Up to 3", description: "Three orders." },
            { label: "Up to 5", description: "Five orders." },
        ],
    };

    on("tool.call", { tool: TURN_TOOL }, () => ({
        result: [],
        text: "Recorded.",
    }));
    on(
        "tool.call",
        { tool: "AskUserQuestion" },
        ($, e, next) =>
            new Promise((resolve) => {
                next.signal.addEventListener("abort", () =>
                    resolve({
                        result: { questions: e.questions, answers: {} },
                    }),
                );
            }),
    );
    on("mcp.call", () => ({
        value: { content: [], isError: false, structuredContent: PROGRESS },
    }));
    on("ui.open", () => ({ value: { isPlaced: true } }));
    on("prompt.submit", ($, e) => {
        submitted.push(e.text);

        return { text: e.text };
    });

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const asked = $.tool.call({
        tool: "AskUserQuestion",
        questions: [QUESTION],
    });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    await ui.press({ key: "toggle-hard" });
    await ui.press({ key: "talk-hard" });

    expect((await asked).result).toEqual({
        questions: [QUESTION],
        answers: {
            [QUESTION.question]:
                "Let's talk about Driver rules: What may a driver never do?",
        },
    });
    expect(submitted).toEqual([]);
});

const SAVE_TOOL = "mcp__prd-chat__save_prd" as const;

function answerTurnAndProgress(on: On) {
    on("tool.call", { tool: TURN_TOOL }, () => ({
        result: [],
        text: "Recorded.",
    }));
    on("mcp.call", () => ({
        value: { content: [], isError: false, structuredContent: PROGRESS },
    }));
    on("ui.open", () => ({ value: { isPlaced: true } }));
}

test("Download report asks Claude for the PRD and writes the saved document to a file named like PRD Assistant's", async ($, on) => {
    const submitted: string[] = [];
    const written: { path: string; text: string }[] = [];

    answerTurnAndProgress(on);
    on("prompt.submit", ($, e) => {
        submitted.push(e.text);

        return { text: e.text };
    });
    on("tool.call", { tool: SAVE_TOOL }, () => ({
        result: [],
        text: "Saved PRD version 1 for alice@example.com.",
    }));
    on("fs.write", ($, e) => {
        written.push(e);

        return { value: undefined };
    });
    on("ui.toast", () => ({ value: undefined }));

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    await ui.press({ key: "download-report" });
    await $.tool.call({
        tool: SAVE_TOOL,
        interviewId: INTERVIEW_ID,
        markdown: "# Pizza delivery",
    });

    expect(submitted).toEqual(["Please write the PRD now."]);
    expect(
        written.map(({ path, text }) => [
            path.endsWith("/plan-van-routes-PRD-7D8F0C.md"),
            text,
        ]),
    ).toEqual([[true, "# Pizza delivery"]]);
});

test("a PRD Claude saves without a download request writes no file", async ($, on) => {
    const written: string[] = [];

    on("tool.call", { tool: SAVE_TOOL }, () => ({
        result: [],
        text: "Saved PRD version 1 for alice@example.com.",
    }));
    on("fs.write", ($, e) => {
        written.push(e.path);

        return { value: undefined };
    });

    await $.tool.call({
        tool: SAVE_TOOL,
        interviewId: INTERVIEW_ID,
        markdown: "# Pizza delivery",
    });

    expect(written).toEqual([]);
});

const SUBMITTABLE: InterviewProgress = {
    ...PROGRESS,
    contactEmail: "alice@example.com",
    hasCurrentPrd: true,
};

type McpCall = { server: string; tool: string; args: Record<string, unknown> };

function answerSubmit(on: On, progress: InterviewProgress) {
    const calls: McpCall[] = [];
    const toasts: string[] = [];
    const submitted: string[] = [];

    on("tool.call", { tool: TURN_TOOL }, () => ({
        result: [],
        text: "Recorded.",
    }));
    on("mcp.call", ($, e) => {
        calls.push(e);

        return e.tool === "submit_for_build"
            ? {
                  value: {
                      content: [{ type: "text", text: "Submitted PRD version 1." }],
                      isError: false,
                  },
              }
            : {
                  value: {
                      content: [],
                      isError: false,
                      structuredContent: progress,
                  },
              };
    });
    on("ui.open", () => ({ value: { isPlaced: true } }));
    on("ui.toast", ($, e) => {
        toasts.push(e.text);

        return { value: undefined };
    });
    on("prompt.submit", ($, e) => {
        submitted.push(e.text);

        return { text: e.text };
    });

    return {
        toasts,
        submitted,
        submits: () => calls.filter((call) => call.tool === "submit_for_build"),
    };
}

test("Submit for build confirms in the pane like PRD Assistant's dialog, then hands the current PRD over with the sign-in email", async ($, on) => {
    const dialog = answerSubmit(on, SUBMITTABLE);

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    expect((await ui.find({ key: "submit-build" }))?.props.label).toBe(
        "Submit for build",
    );
    await ui.press({ key: "submit-build" });

    expect(await ui.find({ text: "Submit for build?" })).toBeDefined();
    expect(
        await ui.find({ text: /as Markdown and\s+PDF, to our solutions team/ }),
    ).toBeDefined();
    expect(
        await ui.find({ text: "Contact email: alice@example.com" }),
    ).toBeDefined();
    expect(await ui.find({ key: "change-email" })).toBeUndefined();
    expect(await ui.find({ key: "submit-build" })).toBeUndefined();
    expect(dialog.submits()).toEqual([]);

    await ui.press({ key: "confirm-submit" });

    expect(dialog.submits()).toEqual([
        {
            server: "prd-chat",
            tool: "submit_for_build",
            args: { interviewId: INTERVIEW_ID, contactEmail: "alice@example.com" },
        },
    ]);
    expect(dialog.toasts).toContain(
        "PRD Assistant: submitted. Our solutions team will contact you at alice@example.com.",
    );
    expect(dialog.submitted).toEqual([]);
    expect(await ui.find({ key: "submit-build" })).toBeDefined();
});

test("the confirmation shows while Claude's question stays open, and asks no question of its own", async ($, on) => {
    const dialog = answerSubmit(on, SUBMITTABLE);
    const questions: string[] = [];
    let answerQuestion = (_answer: string) => {};

    on("tool.call", { tool: "AskUserQuestion" }, ($, e) => {
        const [question] = e.questions;

        questions.push(question?.question ?? "");

        return new Promise((resolve) => {
            answerQuestion = (answer) =>
                resolve({
                    result: {
                        questions: e.questions,
                        answers: { [question?.question ?? ""]: answer },
                    },
                });
        });
    });
    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });
    const asked = $.tool.call({
        tool: "AskUserQuestion",
        questions: [
            {
                question: "Can a driver carry only a few pizzas?",
                header: "Capacity",
                options: [
                    { label: "Yes", description: "A fixed number" },
                    { label: "No limit", description: "Any number" },
                ],
                multiSelect: false,
            },
        ],
    });

    await ui.press({ key: "submit-build" });

    expect(await ui.find({ text: "Submit for build?" })).toBeDefined();
    await ui.press({ key: "confirm-submit" });

    expect(dialog.submits()).toHaveLength(1);
    expect(questions).toEqual(["Can a driver carry only a few pizzas?"]);

    answerQuestion("Yes");
    expect((await asked).result).toMatchObject({
        answers: { "Can a driver carry only a few pizzas?": "Yes" },
    });
});

test("Cancel closes the confirmation and sends nothing", async ($, on) => {
    const dialog = answerSubmit(on, SUBMITTABLE);

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    await ui.press({ key: "submit-build" });
    await ui.press({ key: "cancel-submit" });

    expect(await ui.find({ key: "submit-confirmation" })).toBeUndefined();
    expect(await ui.find({ key: "submit-build" })).toBeDefined();
    expect(dialog.submits()).toEqual([]);
    expect(dialog.submitted).toEqual([]);
});

test("without a current PRD, Submit asks Claude for the PRD and submits once it is saved", async ($, on) => {
    const dialog = answerSubmit(on, { ...SUBMITTABLE, hasCurrentPrd: false });

    on("tool.call", { tool: SAVE_TOOL }, () => ({
        result: [],
        text: "Saved PRD version 1 for alice@example.com.",
    }));
    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    await ui.press({ key: "submit-build" });
    await ui.press({ key: "confirm-submit" });

    expect(dialog.submitted).toEqual(["Please write the PRD now."]);
    expect(dialog.submits()).toEqual([]);

    await $.tool.call({
        tool: SAVE_TOOL,
        interviewId: INTERVIEW_ID,
        markdown: "# Van routes",
    });
    await $.tool.call({
        tool: SAVE_TOOL,
        interviewId: INTERVIEW_ID,
        markdown: "# Van routes, again",
    });

    expect(dialog.submits().map((call) => call.args)).toEqual([
        { interviewId: INTERVIEW_ID, contactEmail: "alice@example.com" },
    ]);
});

test("a refused submit says why in a toast", async ($, on) => {
    const toasts: string[] = [];

    on("tool.call", { tool: TURN_TOOL }, () => ({
        result: [],
        text: "Recorded.",
    }));
    on("mcp.call", ($, e) =>
        e.tool === "submit_for_build"
            ? {
                  value: {
                      content: [
                          {
                              type: "text",
                              text: "We couldn't send your requirements. Try again in a moment.",
                          },
                      ],
                      isError: true,
                  },
              }
            : {
                  value: {
                      content: [],
                      isError: false,
                      structuredContent: SUBMITTABLE,
                  },
              },
    );
    on("ui.open", () => ({ value: { isPlaced: true } }));
    on("ui.toast", ($, e) => {
        toasts.push(e.text);

        return { value: undefined };
    });

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    await ui.press({ key: "submit-build" });
    await ui.press({ key: "confirm-submit" });

    expect(toasts).toContain(
        "PRD Assistant: not submitted: We couldn't send your requirements. Try again in a moment.",
    );
});

test("an older connector without the sign-in email is told apart", async ($, on) => {
    const dialog = answerSubmit(on, PROGRESS);

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    await ui.press({ key: "submit-build" });

    expect(await ui.find({ key: "submit-confirmation" })).toBeUndefined();
    expect(dialog.toasts).toContain(
        "PRD Assistant: this connector cannot submit for build yet.",
    );
});

test("a refused download prompt says why in a toast", async ($, on) => {
    const toasts: string[] = [];

    answerTurnAndProgress(on);
    on("ui.toast", ($, e) => {
        toasts.push(e.text);

        return { value: undefined };
    });
    on("prompt.submit", () => ({ drop: "prompts from plugins are off" }));

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    await ui.press({ key: "download-report" });

    expect(toasts).toEqual([
        "PRD Assistant: preparing the report.",
        "PRD Assistant: the message was not sent: prompts from plugins are off",
    ]);
});

const BUILD_SERVER = "mcp__prd-chat__";

// why: the order differs from the build's on purpose: the pane orders the phases by the guide each one returns
const BUILD_TOOLS = [
    ["start_model_build", "Starts building a Timefold model from a PRD and returns the build process and the planning guide, with a link to the model archetype. Use it once per model."],
    ["complete_constraints_phase", "Ends a build's CONSTRAINTS phase with every constraint's implementation, the full test run and the independent review, and returns the GOLDEN_FILE_TEST guide."],
    ["complete_planning", "Ends a build's planning phase: locks the constraint list and returns the DTOS_AND_DOMAIN guide."],
    ["complete_ui_build_phase", "Ends a build's UI_BUILD phase with the browser check of the running model, and returns the final steps."],
    ["complete_domain_phase", "Ends a build's DTOS_AND_DOMAIN phase with the build result and returns the CONSTRAINTS guide."],
    ["get_model_build", "Returns a model build's phase, its registered constraints and the guide for its current phase."],
    ["complete_profiling_phase", "Ends a build's CONSTRAINT_PROFILING phase with the before and after findings, and returns the UI_BUILD guide."],
    ["complete_golden_file_phase", "Ends a build's GOLDEN_FILE_TEST phase with the ConstraintAnalysis report and the live solve result, and returns the CONSTRAINT_PROFILING guide."],
].map(([name, description]) => ({
    name: `${BUILD_SERVER}${name}`,
    description: description ?? "",
    mcp: true,
}));

const OTHER_TOOLS = [
    { name: "Read", description: "Reads a file.", mcp: false },
    {
        name: "mcp__other__complete_task",
        description: "Ends a task.",
        mcp: true,
    },
];

const PHASE_LABELS = [
    "Planning",
    "Domain",
    "Constraints",
    "Golden file",
    "Profiling",
    "UI build",
];

const BUILD_ID = "0b6f4a8e-2c1d-4e3f-9a7b-5c6d7e8f9a0b";

function answerBuildTools(on: On, tools = [...OTHER_TOOLS, ...BUILD_TOOLS]) {
    on("tool.list", () => ({ value: tools }));
}

test("the build phases come from the connector's complete tools, in the order their guides chain", async ($, on) => {
    answerTurnAndProgress(on);
    answerBuildTools(on);

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    expect(await ui.find({ type: "Text", text: "Model build" })).toBeDefined();
    const labels = (await ui.findAll({ type: "Text" }))
        .map((text) => text.text)
        .filter((text) => PHASE_LABELS.includes(text));

    expect(labels).toEqual(PHASE_LABELS);
    expect(
        (await ui.findAll({ type: "Text", text: "Not started" })).length,
    ).toBe(PHASE_LABELS.length);
    expect(await ui.findAll({ type: "Text", text: "◀ now" })).toHaveLength(1);
    expect((await ui.find({ key: "build-model" }))?.props.label).toBe(
        "Build model",
    );
    expect(await ui.find({ key: "download-report" })).toBeDefined();
    expect(await ui.find({ key: "submit-build" })).toBeDefined();
});

test("a connector without start_model_build shows no build phases and no Build model button", async ($, on) => {
    answerTurnAndProgress(on);
    answerBuildTools(on, OTHER_TOOLS);

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    expect(await ui.find({ type: "Text", text: "Model build" })).toBeUndefined();
    expect(await ui.find({ key: "build-model" })).toBeUndefined();
    expect(await ui.find({ key: "submit-build" })).toBeDefined();
});

test("Build model asks Claude to call start_model_build", async ($, on) => {
    const submitted: string[] = [];

    answerTurnAndProgress(on);
    answerBuildTools(on);
    on("ui.toast", () => ({ value: undefined }));
    on("prompt.submit", ($, e) => {
        submitted.push(e.text);

        return { text: e.text };
    });

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    await ui.press({ key: "build-model" });

    expect(submitted).toEqual([
        "Please build the Timefold model from this PRD now: call start_model_build with the full PRD and follow the guide it returns.",
    ]);
});

type DrawnPane = {
    findAll: (query: { type: string }) => Promise<{ text: string }[]>;
};

async function phaseStatuses(ui: DrawnPane) {
    const texts = (await ui.findAll({ type: "Text" })).map(
        (text) => text.text,
    );
    const statuses = PHASE_LABELS.map((label) => {
        const index = texts.indexOf(label);

        return texts[index + 1];
    });
    const active = PHASE_LABELS.filter(
        (label) => texts[texts.indexOf(label) + 2] === "◀ now",
    );

    return { statuses, active };
}

test("the pane marks the phase the build is in as Claude moves through the build", async ($, on) => {
    answerTurnAndProgress(on);
    answerBuildTools(on);
    on("tool.call", { tool: `${BUILD_SERVER}start_model_build` }, () => ({
        result: [],
        text: `TIMEFOLD MODEL BUILD\nPHASES\n1. PLANNING: scaffold\nbuildId: ${BUILD_ID}\nPHASE: PLANNING\n- Read the files.`,
    }));
    on("tool.call", { tool: `${BUILD_SERVER}complete_planning` }, () => ({
        result: [],
        text: `Phase complete. The build is now in DTOS_AND_DOMAIN.\nbuildId: ${BUILD_ID}\nPHASE: DTOS_AND_DOMAIN`,
    }));
    on("tool.call", { tool: `${BUILD_SERVER}complete_domain_phase` }, () => ({
        result: [],
        text: "Done.",
    }));
    on("tool.call", { tool: `${BUILD_SERVER}get_model_build` }, () => ({
        result: [],
        text: `buildId: ${BUILD_ID}\nmodel: Van Routes (van-routes)\nphase: UI_BUILD\nconstraints (locked):\n- H1 (hard): Capacity`,
    }));
    on("tool.call", { tool: `${BUILD_SERVER}complete_ui_build_phase` }, () => ({
        isError: true,
        result: [],
        text: "The plan did not render.",
    }));

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    await $.tool.call({ tool: `${BUILD_SERVER}start_model_build` });
    expect(await phaseStatuses(ui)).toEqual({
        statuses: ["In progress", ...Array(5).fill("Not started")],
        active: ["Planning"],
    });

    await $.tool.call({ tool: `${BUILD_SERVER}complete_planning` });
    expect((await phaseStatuses(ui)).active).toEqual(["Domain"]);

    // why: a result that names no phase still moves the build on to the phase after the completed one
    await $.tool.call({ tool: `${BUILD_SERVER}complete_domain_phase` });
    expect(await phaseStatuses(ui)).toEqual({
        statuses: ["Done", "Done", "In progress", ...Array(3).fill("Not started")],
        active: ["Constraints"],
    });

    await $.tool.call({ tool: `${BUILD_SERVER}get_model_build` });
    expect((await phaseStatuses(ui)).active).toEqual(["UI build"]);

    await $.tool.call({ tool: `${BUILD_SERVER}complete_ui_build_phase` });
    expect((await phaseStatuses(ui)).active).toEqual(["UI build"]);
});

test("the last phase's completion marks every phase done", async ($, on) => {
    answerTurnAndProgress(on);
    answerBuildTools(on);
    on("tool.call", { tool: `${BUILD_SERVER}complete_ui_build_phase` }, () => ({
        result: [],
        text: `Phase complete. The build is now in DONE.\nbuildId: ${BUILD_ID}\nTHE BUILD IS DONE`,
    }));

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    await $.tool.call({ tool: `${BUILD_SERVER}complete_ui_build_phase` });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    expect(await phaseStatuses(ui)).toEqual({
        statuses: Array(6).fill("Done"),
        active: [],
    });
});
