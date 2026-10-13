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
    plugin: "prd",
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

test("Download report asks Claude for the PRD and writes the saved document to a file named like PRD Chat's", async ($, on) => {
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

test("Submit for build is shown and does nothing yet", async ($, on) => {
    const toasts: string[] = [];
    const submitted: string[] = [];

    answerTurnAndProgress(on);
    on("ui.toast", ($, e) => {
        toasts.push(e.text);

        return { value: undefined };
    });
    on("prompt.submit", ($, e) => {
        submitted.push(e.text);

        return { text: e.text };
    });

    await $.tool.call({ tool: TURN_TOOL, interviewId: INTERVIEW_ID });
    const ui = await $.ui.mount({ ...PANE, surface: "terminal" });

    expect((await ui.find({ key: "submit-build" }))?.props.label).toBe(
        "Submit for build",
    );
    await ui.press({ key: "submit-build" });
    expect(toasts).toEqual([]);
    expect(submitted).toEqual([]);
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
        "PRD Chat: preparing the report.",
        "PRD Chat: the message was not sent: prompts from plugins are off",
    ]);
});
