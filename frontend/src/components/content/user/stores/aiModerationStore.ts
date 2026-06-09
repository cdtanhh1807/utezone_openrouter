import { create } from "zustand";

interface AIModerationState {
  isModerating: boolean;

  setModerating: (value: boolean) => void;
}

export const useAIModerationStore =
  create<AIModerationState>((set) => ({
    isModerating: false,

    setModerating: (value) =>
      set({
        isModerating: value,
      }),
  }));