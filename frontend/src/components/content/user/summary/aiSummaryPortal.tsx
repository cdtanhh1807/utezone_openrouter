import { createPortal } from "react-dom";

import SummaryBox from "../summary/summaryPost";

import { useAIStore } from "../stores/aiStore";

const AISummaryPortal = () => {
  const {
    summary,
    showSummary,
    closeSummary,
  } = useAIStore();

  if (!showSummary) return null;

  return createPortal(
    <div
      style={{
        position: "fixed",

        top: "200px",
        left: "350px",

        zIndex: 2147483647,
      }}
    >
      <SummaryBox
        summary={summary}
        onClose={closeSummary}
      />
    </div>,

    document.body,
  );
};

export default AISummaryPortal;