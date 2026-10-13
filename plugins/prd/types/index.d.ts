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
};

declare module "claude-code" {
    interface PluginState {
        "prd": {
            progress: InterviewProgress | null;
            expandedIds: string[];
        };
    }
}
