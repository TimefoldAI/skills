export type InterviewSection = {
    id: string;
    label: string;
    question: string;
    coverage: number;
    captured: string;
};

export type InterviewProgress = {
    interviewId: string;
    problemSummary: string | null;
    currentSectionId: string | null;
    fullCoverage: number;
    sections: InterviewSection[];
    contactEmail?: string;
    hasCurrentPrd?: boolean;
};

export type SubmitConfirmation = {
    interviewId: string;
    contactEmail: string;
};

export type BuildPhase = {
    id: string;
    tool: string;
    label: string;
};

export type ModelBuild = {
    phaseId: string;
};

declare module "claude-code" {
    interface PluginState {
        "timefold-prd": {
            progress: InterviewProgress | null;
            expandedIds: string[];
            server: string | null;
            confirmation: SubmitConfirmation | null;
            buildPhases: BuildPhase[] | null;
            build: ModelBuild | null;
        };
    }
}
