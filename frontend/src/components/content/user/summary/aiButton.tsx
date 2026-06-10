import { useEffect } from "react";

import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CircularProgress from "@mui/material/CircularProgress";

import "./aiButton.css";

import { useAIStore } from "../stores/aiStore";

const AIActionButton = () => {
  const { status, setStatus } = useAIStore();

  const loading =
    status === "summarizing" ||
    status === "moderating";

  // 🔥 auto reset sau 3s
  useEffect(() => {
    if (status === "success") {
      const timeout = setTimeout(() => {
        setStatus("idle");
      }, 3000);

      return () => clearTimeout(timeout);
    }
  }, [status, setStatus]);

  return (
    <div className="ai-side">
      <button
        className={`
          ai-btn
          ${loading ? "loading" : ""}
          ${status === "success" ? "success" : ""}
        `}
        disabled={loading}
      >
        <div className="ai-btn-content">
          {loading ? (
            <>
              <CircularProgress
                size={18}
                thickness={5}
                color="inherit"
              />

              <span>
                {status === "summarizing"
                  ? "UTEZone AI đang tóm tắt bài viết..."
                  : "UTEZone AI đang kiểm duyệt nội dung..."}
              </span>
            </>
          ) : status === "success" ? (
            <>
              <CheckCircleIcon />
              <span>Hoàn tất</span>
            </>
          ) : (
            <>
              <AutoAwesomeIcon />
              <span>UTEZone AI</span>
            </>
          )}
        </div>
      </button>
    </div>
  );
};

export default AIActionButton;