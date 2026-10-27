import { atom, read, update } from "claude-code";
import type {
    EngineInterface,
    McpToolResult,
    Register,
    ToolInfo,
} from "claude-code";

import type {
    BuildPhase,
    InterviewProgress,
    InterviewSection,
    ModelBuild,
    SubmitConfirmation,
} from "../types";

const PANE = { id: "prd-chat", title: "Requirements coverage" };
const INTERVIEW_TOOL =
    /^mcp__(.+)__(start_requirements_interview|record_interview_turn)$/;
const INTERVIEW_ID = /interviewId: (\S+)/;
const SAVE_PRD_TOOL = /^mcp__(.+)__save_prd$/;
const START_BUILD_TOOL = "start_model_build";
const BUILD_TOOL =
    /^mcp__(.+)__(start_model_build|get_model_build|amend_model_constraints|complete_\w+)$/;
// why: each phase of a build ends with one complete_* tool, so these tools are the phases
const PHASE_TOOL = /^complete_(\w+?)(?:_phase)?$/;
const PHASE_ENDED = /\bends a build's (\w+) phase/i;
const NEXT_GUIDE = /\breturns the (\w+) guide/i;
const BUILD_PHASE = /\b(?:build is (?:now )?in|phase:) (\w+)/gi;
const BUILD_DONE = "DONE";
const ACRONYMS: Record<string, string> = { ui: "UI", dto: "DTO", dtos: "DTOs" };
const BUILD_PROMPT =
    "Please build the Timefold model from this PRD now: call start_model_build with the full PRD and follow the guide it returns.";
const REFERENCE_LENGTH = 6;
const MAX_SLUG_LENGTH = 60;
const BAR_WIDTH = 20;
const UPPER_THRESHOLD = 85;
const MIDDLE_THRESHOLD = 50;

let answerOpenQuestion: ((text: string) => void) | undefined;
let isDownloadRequested = false;
let pendingSubmitEmail: string | undefined;

const progress = atom(
    { plugin: "timefold-prd", key: "progress" } as const,
    null,
);
const expandedIds = atom(
    { plugin: "timefold-prd", key: "expandedIds" } as const,
    [],
);
const interviewServer = atom({ plugin: "timefold-prd", key: "server" } as const, null);
const confirmation = atom(
    { plugin: "timefold-prd", key: "confirmation" } as const,
    null,
);
const buildPhases = atom(
    { plugin: "timefold-prd", key: "buildPhases" } as const,
    null,
);
const modelBuild = atom({ plugin: "timefold-prd", key: "build" } as const, null);

type Status = "open" | "inProgress" | "covered";

const STATUS = {
    open: { glyph: "○", label: "Open", color: "gray" },
    inProgress: { glyph: "◐", label: "In progress", color: "yellow" },
    covered: { glyph: "●", label: "Covered", color: "green" },
} as const;

type PhaseStatus = "waiting" | "active" | "done";

const PHASE_STATUS = {
    waiting: { glyph: "○", label: "Not started", color: "gray" },
    active: { glyph: "◐", label: "In progress", color: "yellow" },
    done: { glyph: "●", label: "Done", color: "green" },
} as const;

function statusOf(section: InterviewSection, fullCoverage: number): Status {
    if (section.coverage >= fullCoverage) return "covered";

    return section.coverage > 0 ? "inProgress" : "open";
}

// why: the same square-rooted percentage as PRD Assistant's coverage bar, so the first answers move it fast
function coveragePercent(interview: InterviewProgress): number {
    const covered = interview.sections.reduce(
        (sum, section) =>
            sum + Math.min(section.coverage, interview.fullCoverage),
        0,
    );
    const whole = interview.sections.length * interview.fullCoverage;

    return whole === 0 ? 0 : Math.round(Math.sqrt(covered / whole) * 100);
}

function coverageColor(percent: number) {
    if (percent >= UPPER_THRESHOLD) return "green";

    return percent >= MIDDLE_THRESHOLD ? "yellow" : "red";
}

function coverageBar(percent: number) {
    const filled = Math.round((percent / 100) * BAR_WIDTH);

    return "█".repeat(filled) + "░".repeat(BAR_WIDTH - filled);
}

function referenceOf(interviewId: string) {
    const hex = interviewId.replaceAll("-", "").slice(0, REFERENCE_LENGTH);

    return `#PRD-${hex.toUpperCase()}`;
}

function titleSlug(title: string) {
    const [first = "", ...rest] = title
        .toLowerCase()
        .normalize("NFKD")
        .replace(/\p{Mark}/gu, "")
        .split(/[^a-z0-9]+/)
        .filter(Boolean);
    let slug = first.slice(0, MAX_SLUG_LENGTH);

    for (const word of rest) {
        const next = `${slug}-${word}`;

        if (next.length > MAX_SLUG_LENGTH) break;
        slug = next;
    }

    return slug;
}

// why: PRD Assistant names its download the same way: the title as a slug, then the reference
function prdFileName(interviewId: string, problemSummary: string | null) {
    const reference = referenceOf(interviewId).slice(1);
    const slug = problemSummary ? titleSlug(problemSummary) : "";

    return slug ? `${slug}-${reference}.md` : `${reference}.md`;
}

function phaseLabel(name: string) {
    const words = name
        .split("_")
        .map((word) => ACRONYMS[word] ?? word);
    const [first = "", ...rest] = words;

    return [first.charAt(0).toUpperCase() + first.slice(1), ...rest].join(" ");
}

// why: the connector changes its phases over time, so read them from its complete_* tools
function buildPhasesOf(tools: ToolInfo[], server: string): BuildPhase[] | null {
    const prefix = `mcp__${server}__`;
    const own = tools.filter((tool) => tool.name.startsWith(prefix));

    if (!own.some((tool) => tool.name === prefix + START_BUILD_TOOL)) return null;
    const ends = own.flatMap((tool) => {
        const name = tool.name.slice(prefix.length);
        const phaseName = PHASE_TOOL.exec(name)?.[1];

        if (phaseName === undefined) return [];
        const id = (
            PHASE_ENDED.exec(tool.description)?.[1] ?? phaseName
        ).toUpperCase();
        const next = NEXT_GUIDE.exec(tool.description)?.[1]?.toUpperCase();

        return [{ phase: { id, tool: name, label: phaseLabel(phaseName) }, next }];
    });
    const followers = new Set(ends.map((end) => end.next));
    const ordered: BuildPhase[] = [];
    // why: each description names the next phase's guide, so walk that chain from the phase no other one leads to
    let current = ends.find((end) => !followers.has(end.phase.id));

    while (current && !ordered.includes(current.phase)) {
        ordered.push(current.phase);
        const next = current.next;

        current = ends.find((end) => end.phase.id === next);
    }

    return [
        ...ordered,
        ...ends.map((end) => end.phase).filter((phase) => !ordered.includes(phase)),
    ];
}

function phaseIdIn(text: string, phases: BuildPhase[]) {
    return [...text.matchAll(BUILD_PHASE)]
        .map((match) => (match[1] ?? "").toUpperCase())
        .find(
            (id) =>
                id === BUILD_DONE || phases.some((phase) => phase.id === id),
        );
}

// why: a phase the result does not name is still known: start begins the first one, and complete_* moves on to the next
function phaseAfter(tool: string, phases: BuildPhase[]) {
    if (tool === START_BUILD_TOOL) return phases[0]?.id;
    const index = phases.findIndex((phase) => phase.tool === tool);

    if (index < 0) return undefined;

    return phases[index + 1]?.id ?? BUILD_DONE;
}

function phaseStatusOf(
    index: number,
    build: ModelBuild | null,
    phases: BuildPhase[],
): PhaseStatus {
    if (build === null) return "waiting";
    if (build.phaseId === BUILD_DONE) return "done";
    const activeIndex = phases.findIndex((phase) => phase.id === build.phaseId);

    if (activeIndex < 0 || index > activeIndex) return "waiting";

    return index === activeIndex ? "active" : "done";
}

function isInterviewProgress(value: unknown): value is InterviewProgress {
    if (typeof value !== "object" || value === null) return false;
    const candidate = value as Partial<InterviewProgress>;

    return (
        typeof candidate.interviewId === "string" &&
        typeof candidate.fullCoverage === "number" &&
        Array.isArray(candidate.sections)
    );
}

function parsedJson(text: string): unknown {
    try {
        return JSON.parse(text);
    } catch {
        return undefined;
    }
}

// why: Claude Code's $.mcp.call hands the structured result over as a JSON text block, not as structuredContent
function progressOf(result: McpToolResult): unknown {
    if (result.structuredContent !== undefined) return result.structuredContent;
    // why: the server also sends a plain-text summary block, so try each text block
    return result.content
        .map((block) => (block.type === "text" ? parsedJson(block.text ?? "") : undefined))
        .find(isInterviewProgress);
}

function interviewIdOf(
    input: Record<string, unknown>,
    resultText: string | undefined,
) {
    if (typeof input.interviewId === "string") return input.interviewId;

    return INTERVIEW_ID.exec(resultText ?? "")?.[1];
}

function markdownOf(input: Record<string, unknown>) {
    return typeof input.markdown === "string" ? input.markdown : undefined;
}

function sendAsUser($: EngineInterface, text: string) {
    if (answerOpenQuestion) {
        answerOpenQuestion(text);

        return;
    }
    void $.prompt
        .submit({ text, asUser: true })
        .then((entered) => {
            if (entered.drop !== undefined)
                $.ui.toast(`PRD Assistant: the message was not sent: ${entered.drop}`);
        })
        .catch((error: unknown) =>
            $.ui.toast(`PRD Assistant: the message was not sent: ${String(error)}`),
        );
}

async function downloadReport(
    $: EngineInterface,
    interviewId: string,
    markdown: string,
) {
    const interview = await read($, progress);
    const problemSummary =
        interview?.interviewId === interviewId ? interview.problemSummary : null;
    const fileName = prdFileName(interviewId, problemSummary);

    await $.fs
        .write(fileName, markdown)
        .then(() => $.ui.toast(`PRD Assistant: the report is saved as ${fileName}.`))
        .catch((error: unknown) =>
            $.ui.toast(`PRD Assistant: the report was not saved: ${String(error)}`),
        );
}

function resultText(result: McpToolResult) {
    return result.content
        .map((block) => (block.type === "text" ? (block.text ?? "") : ""))
        .join(" ")
        .trim();
}

async function submitForBuild(
    $: EngineInterface,
    interviewId: string,
    contactEmail: string,
) {
    const server = await read($, interviewServer);

    if (server === null) {
        $.ui.toast("PRD Assistant: the interview's connector is not known yet.");

        return;
    }
    $.ui.toast("PRD Assistant: sending your requirements to Timefold.");
    const result = await $.mcp
        .call(server, "submit_for_build", { interviewId, contactEmail })
        .catch((error: unknown) => ({
            content: [{ type: "text" as const, text: String(error) }],
            isError: true,
        }));

    $.ui.toast(
        result.isError
            ? `PRD Assistant: not submitted: ${resultText(result)}`
            : `PRD Assistant: submitted. Our solutions team will contact you at ${contactEmail}.`,
    );
}

// why: the confirmation is drawn in the pane, not with $.ui.ask, which waits behind the interview's open question
async function openConfirmation(
    $: EngineInterface,
    interview: InterviewProgress,
) {
    if (interview.contactEmail === undefined) {
        $.ui.toast("PRD Assistant: this connector cannot submit for build yet.");

        return;
    }
    const contactEmail = interview.contactEmail;

    await update($, confirmation, () => ({
        interviewId: interview.interviewId,
        contactEmail,
    }));
}

// why: Submit in PRD Assistant's confirmation is the user's consent to the handoff
async function confirmSubmit($: EngineInterface, confirmed: SubmitConfirmation) {
    const interview = await read($, progress);

    await update($, confirmation, () => null);
    if (interview?.interviewId !== confirmed.interviewId) return;
    if (interview.hasCurrentPrd) {
        await submitForBuild($, interview.interviewId, confirmed.contactEmail);

        return;
    }
    pendingSubmitEmail = confirmed.contactEmail;
    $.ui.toast("PRD Assistant: Claude writes the requirements document first.");
    sendAsUser($, "Please write the PRD now.");
}

async function refreshBuildPhases($: EngineInterface, server: string) {
    const tools = await $.tool.list().catch(() => null);

    if (tools === null) return null;
    const phases = buildPhasesOf(tools, server);

    await update($, buildPhases, () => phases);

    return phases;
}

async function followBuild(
    $: EngineInterface,
    server: string,
    tool: string,
    text: string,
) {
    const phases = (await refreshBuildPhases($, server)) ?? [];
    const phaseId = phaseIdIn(text, phases) ?? phaseAfter(tool, phases);

    if (phaseId === undefined) return;
    await update($, modelBuild, () => ({ phaseId }));
    await $.ui.open(PANE);
}

function requestBuild($: EngineInterface) {
    $.ui.toast("PRD Assistant: Claude starts the model build.");
    sendAsUser($, BUILD_PROMPT);
}

async function refreshProgress(
    $: EngineInterface,
    server: string,
    interviewId: string,
) {
    const result = await $.mcp
        .call(server, "get_interview_progress", { interviewId })
        .catch((error: unknown) => {
            $.ui.toast(
                `PRD Assistant: the requirements pane was not updated: ${String(error)}`,
            );

            return null;
        });

    if (result === null) return;
    const loaded = result.isError ? undefined : progressOf(result);

    if (!isInterviewProgress(loaded)) {
        $.ui.toast("PRD Assistant: the interview progress could not be loaded.");

        return;
    }

    await update($, progress, () => loaded);
    await update($, interviewServer, () => server);
    await refreshBuildPhases($, server);
    await $.ui.open(PANE);
}

export const register: Register = (on) => {
    on(
        "tool.check",
        { tool: /^mcp__.+__get_interview_progress$/ },
        ($, e, next) =>
            next.origin.plugin === $.plugin.name
                ? {
                      decision: "allow",
                      reason: "The PRD Assistant pane reads the interview's progress.",
                  }
                : next(e),
    );
    on(
        "tool.check",
        { tool: /^mcp__.+__submit_for_build$/ },
        ($, e, next) =>
            next.origin.plugin === $.plugin.name
                ? {
                      decision: "allow",
                      reason: "The user confirmed Submit for build and the contact email in the PRD Assistant pane.",
                  }
                : next(e),
    );
    on("session.start", async ($, e, next) => {
        await $.command.register({
            name: "prd-panel",
            description:
                "Show the requirements of the current PRD Assistant interview",
        });

        return next(e);
    });

    on("command.run", { command: "prd-panel" }, async ($) => {
        await $.ui.open(PANE);

        return { text: "Requirements pane opened." };
    });

    on("tool.call", { tool: "AskUserQuestion" }, async ($, e, next) => {
        const redirected = new Promise<string>((resolve) => {
            answerOpenQuestion = resolve;
        });
        const asked = next(e);

        try {
            const outcome = await Promise.race([
                asked.then((ran) => ({ ran })),
                redirected.then((text) => ({ text })),
            ]);

            if ("ran" in outcome) return outcome.ran;
            const answers = Object.fromEntries(
                e.questions.map((question) => [
                    question.question,
                    outcome.text,
                ]),
            );

            return { result: { questions: e.questions, answers } };
        } finally {
            answerOpenQuestion = undefined;
        }
    });

    on("tool.call", { tool: INTERVIEW_TOOL }, async ($, e, next) => {
        const ran = await next(e);
        const server = INTERVIEW_TOOL.exec(e.tool)?.[1];
        const interviewId = interviewIdOf(e, ran.text);

        if (ran.deny === undefined && !ran.isError && server && interviewId)
            await refreshProgress($, server, interviewId);

        return ran;
    });

    on("tool.call", { tool: SAVE_PRD_TOOL }, async ($, e, next) => {
        const ran = await next(e);
        const isSaved = ran.deny === undefined && !ran.isError;
        const markdown = markdownOf(e);
        const interviewId = interviewIdOf(e, undefined);
        const server = SAVE_PRD_TOOL.exec(e.tool)?.[1];

        if (isSaved && server && interviewId)
            await refreshProgress($, server, interviewId);
        if (isSaved && interviewId && pendingSubmitEmail !== undefined) {
            const contactEmail = pendingSubmitEmail;

            pendingSubmitEmail = undefined;
            await submitForBuild($, interviewId, contactEmail);
        }
        if (
            isDownloadRequested &&
            isSaved &&
            markdown !== undefined &&
            interviewId !== undefined
        ) {
            isDownloadRequested = false;
            await downloadReport($, interviewId, markdown);
        }

        return ran;
    });

    on("tool.call", { tool: BUILD_TOOL }, async ($, e, next) => {
        const ran = await next(e);
        const match = BUILD_TOOL.exec(e.tool);
        const server = match?.[1];
        const tool = match?.[2];

        if (ran.deny === undefined && !ran.isError && server && tool)
            await followBuild($, server, tool, ran.text ?? "");

        return ran;
    });

    on("ui.render", { component: "Pane", requestId: PANE.id }, async ($, e) => {
        const { Box, Text, Button } = $.ui.resolve(e);
        const interview = await read($, progress);
        const expanded = await read($, expandedIds);
        const confirming = await read($, confirmation);
        const phases = await read($, buildPhases);
        const build = await read($, modelBuild);
        const buildSection = phases !== null && phases.length > 0 && (
            <Box key="build-phases" flexDirection="column">
                <Text bold>Model build</Text>
                {phases.map((phase, index) => {
                    const statusKey = phaseStatusOf(index, build, phases);
                    const status = PHASE_STATUS[statusKey];

                    return (
                        <Box key={`phase-${phase.id}`} gap={1}>
                            <Text color={status.color}>{status.glyph}</Text>
                            <Text>{phase.label}</Text>
                            <Text color={status.color} dimColor>
                                {status.label}
                            </Text>
                            {statusKey === "active" && (
                                <Text color="cyan" bold>
                                    ◀ now
                                </Text>
                            )}
                        </Box>
                    );
                })}
            </Box>
        );

        if (interview === null)
            return build === null ? (
                <Text dimColor>
                    No interview yet. Ask Claude to start a Timefold
                    requirements interview.
                </Text>
            ) : (
                <Box flexDirection="column">{buildSection}</Box>
            );
        const percent = coveragePercent(interview);
        const toggle = (id: string) =>
            update($, expandedIds, (ids) =>
                ids.includes(id)
                    ? ids.filter((each) => each !== id)
                    : [...ids, id],
            );
        const talkAbout = (section: InterviewSection) =>
            sendAsUser($, `Let's talk about ${section.label}: ${section.question}`);
        const requestDownload = () => {
            isDownloadRequested = true;
            $.ui.toast("PRD Assistant: preparing the report.");
            sendAsUser($, "Please write the PRD now.");
        };

        return (
            <Box flexDirection="column" gap={1}>
                <Box flexDirection="column">
                    {interview.problemSummary && (
                        <Text bold>{interview.problemSummary}</Text>
                    )}
                    <Text dimColor>{referenceOf(interview.interviewId)}</Text>
                    <Box gap={1}>
                        <Text color={coverageColor(percent)}>
                            {coverageBar(percent)}
                        </Text>
                        <Text color={coverageColor(percent)} bold>
                            {`${percent}%`}
                        </Text>
                    </Box>
                </Box>
                <Box flexDirection="column">
                    {interview.sections.map((section) => {
                        const statusKey = statusOf(
                            section,
                            interview.fullCoverage,
                        );
                        const status = STATUS[statusKey];
                        const isExpanded = expanded.includes(section.id);
                        const isCurrent =
                            section.id === interview.currentSectionId;

                        return (
                            <Box key={section.id} flexDirection="column">
                                <Box gap={1}>
                                    <Text color={status.color}>
                                        {status.glyph}
                                    </Text>
                                    <Button
                                        key={`toggle-${section.id}`}
                                        plain
                                        label={`${isExpanded ? "▾" : "▸"} ${section.label}`}
                                        onPress={() => toggle(section.id)}
                                    />
                                    <Text color={status.color} dimColor>
                                        {status.label}
                                    </Text>
                                    {isCurrent && (
                                        <Text color="cyan" bold>
                                            ◀ now
                                        </Text>
                                    )}
                                </Box>
                                {isExpanded && (
                                    <Box flexDirection="column" paddingLeft={4}>
                                        <Text dimColor>{section.question}</Text>
                                        <Text>
                                            {section.captured ||
                                                "Nothing captured yet."}
                                        </Text>
                                        {statusKey !== "covered" && (
                                            <Button
                                                key={`talk-${section.id}`}
                                                label="Talk about this"
                                                onPress={() => talkAbout(section)}
                                            />
                                        )}
                                    </Box>
                                )}
                            </Box>
                        );
                    })}
                </Box>
                {buildSection}
                {confirming?.interviewId === interview.interviewId ? (
                    <Box
                        key="submit-confirmation"
                        flexDirection="column"
                        borderStyle="round"
                        paddingX={1}
                    >
                        <Text bold>Submit for build?</Text>
                        <Text>
                            We send your requirements document, as Markdown and
                            PDF, to our solutions team.
                        </Text>
                        {/* why: no Change email: a text field in the pane gets no keys while Claude's question dialog is open */}
                        <Text>{`Contact email: ${confirming.contactEmail}`}</Text>
                        <Box gap={1}>
                            <Button
                                key="confirm-submit"
                                variant="primary"
                                label="Submit"
                                onPress={() => confirmSubmit($, confirming)}
                            />
                            <Button
                                key="cancel-submit"
                                label="Cancel"
                                onPress={() =>
                                    update($, confirmation, () => null)
                                }
                            />
                        </Box>
                    </Box>
                ) : (
                    <Box gap={1}>
                        <Button
                            key="download-report"
                            label="Download report"
                            onPress={requestDownload}
                        />
                        <Button
                            key="submit-build"
                            variant="primary"
                            label="Submit for build"
                            onPress={() => openConfirmation($, interview)}
                        />
                        {phases !== null && (
                            <Button
                                key="build-model"
                                label="Build model"
                                onPress={() => requestBuild($)}
                            />
                        )}
                    </Box>
                )}
            </Box>
        );
    });
};
