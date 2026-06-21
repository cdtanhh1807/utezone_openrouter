import { create } from "zustand";

type AIStatus =
  | "idle"
  | "summarizing"
  | "moderating"
  | "success";

type AIStore = {
  status: AIStatus;
  summary: string;
  showSummary: boolean;
  postId?: string;
  setStatus: (status: AIStatus) => void;
  openSummary: (summary: string, postId?: string) => void;
  closeSummary: () => void;
};

export const useAIStore = create<AIStore>((set) => ({
  status: "idle",
  summary: "",
  showSummary: false,
  postId: undefined,

  setStatus: (status) => set({ status }),

  openSummary: (summary, postId) =>
    set({
      summary,
      postId,
      showSummary: true,
      status: "success",
    }),

  closeSummary: () =>
    set({
      showSummary: false,
      postId: undefined,
    }),
}));